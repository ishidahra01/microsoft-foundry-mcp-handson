from typing import Any, Dict
from collections.abc import Mapping
import os
import sys
import logging
import requests
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.transport_security import TransportSecuritySettings


logging.getLogger("mcp").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configure MCP server with transport security settings: https://github.com/modelcontextprotocol/python-sdk/issues/1798
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

mcp_port = int(os.environ.get("FUNCTIONS_CUSTOMHANDLER_PORT", 8080))
mcp = FastMCP("calculator", stateless_http=True, port=mcp_port, transport_security=transport_security)


def _normalize_bearer(token: str) -> str:
    """Normalize a Bearer token value by stripping the scheme prefix."""
    t = (token or "").strip()
    return t[7:].strip() if t.lower().startswith("bearer ") else t


def _get_authorization_from_headers(headers: Any) -> str | None:
    """Safely extract the Authorization header from a headers mapping."""
    if isinstance(headers, Mapping):
        auth = headers.get("authorization") or headers.get("Authorization")
        if isinstance(auth, str) and auth.strip():
            return auth
    return None


def extract_bearer_token_from_context(ctx: Context) -> str | None:
    """Extract a Bearer token from the Authorization header in the MCP request context.

    This reads the HTTP Authorization header forwarded to the MCP server and
    normalizes it to a bare access token string.
    """
    try:
        request_context = getattr(ctx, "request_context", None)
        if request_context is None:
            return None

        request = getattr(request_context, "request", None)

        # 1) Direct headers on the request object
        if request is not None:
            headers = getattr(request, "headers", None)
            auth = _get_authorization_from_headers(headers)
            if auth:
                return _normalize_bearer(auth)

            # 2) Headers inside request.meta["headers"] (transport-specific)
            meta = getattr(request, "meta", None)
            if isinstance(meta, dict):
                auth = _get_authorization_from_headers(meta.get("headers"))
                if auth:
                    return _normalize_bearer(auth)

        # 3) Fallback: headers in request_context.meta["headers"]
        meta = getattr(request_context, "meta", None)
        if isinstance(meta, dict):
            auth = _get_authorization_from_headers(meta.get("headers"))
            if auth:
                return _normalize_bearer(auth)

    except Exception as exc:  # noqa: BLE001
        # Do not log token values; only the failure reason.
        logger.warning("Failed to extract Authorization header from context: %s", exc)

    return None


def get_token_info(access_token: str) -> Dict[str, Any]:
    """Inspect the access token without logging the full value."""
    token = (access_token or "").strip()
    if not token:
        return {"received": False, "preview": "N/A", "length": 0}

    token_length = len(token)
    token_preview = token[:10] + "..." if token_length > 10 else token

    return {
        "received": True,
        "preview": token_preview,
        "length": token_length,
    }


def call_graph_api(access_token: str, endpoint: str = "me") -> Dict[str, Any]:
    """Call Microsoft Graph API with the provided delegated access token."""
    url = f"https://graph.microsoft.com/v1.0/{endpoint}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.RequestException as exc:
        logger.error("Graph API call failed: %s", str(exc))
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return {
            "success": False,
            "error": str(exc),
            "status_code": status_code,
        }


def build_whoami_response(access_token: str) -> Dict[str, Any]:
    """Core whoami logic mirroring function_app.py behavior."""
    token_info = get_token_info(access_token)
    graph_result = call_graph_api(access_token, "me")

    if graph_result.get("success"):
        user_data = graph_result.get("data", {})
        return {
            "tool": "whoami",
            "user": {
                "displayName": user_data.get("displayName"),
                "userPrincipalName": user_data.get("userPrincipalName"),
                "id": user_data.get("id"),
                "jobTitle": user_data.get("jobTitle"),
                "mail": user_data.get("mail"),
            },
            "token_info": token_info,
        }

    logger.error(
        "Failed to call Graph API: %s", graph_result.get("error")
    )
    return {
        "error": "Failed to call Microsoft Graph API",
        "details": graph_result.get("error"),
        "status_code": graph_result.get("status_code"),
    }


@mcp.tool()
def whoami(ctx: Context) -> Dict[str, Any]:
    """Get information about the current user via Microsoft Graph.

    Expects a delegated Microsoft Graph access token provided via the
    HTTP Authorization header ("Bearer <token>") on the MCP HTTP request,
    and returns basic profile information for /me.
    """
    access_token = extract_bearer_token_from_context(ctx)
    if not access_token:
        return {
            "error": "Missing Authorization header",
            "message": (
                "Pass a delegated Microsoft Graph access token via the "
                "'Authorization: Bearer <token>' HTTP header; do not include "
                "tokens in tool arguments."
            ),
        }

    logger.info("whoami MCP tool called (self-hosted, header-based)")
    return build_whoami_response(access_token)


@mcp.tool()
def greet(name: str = "World") -> str:
    """Simple greeting tool kept for testing the MCP server."""
    return f"Hello, {name}!"


if __name__ == "__main__":
    try:
        print("Starting MCP server (Graph whoami)...")
        mcp.run(transport="streamable-http")
    except Exception as exc:  # noqa: BLE001
        print(f"Error while running MCP server: {exc}", file=sys.stderr)