"""
Azure Functions MCP Server with OAuth Identity Passthrough support.

This server implements an MCP extension that receives delegated user tokens
from Foundry Agent via APIM and can call Microsoft Graph API on behalf of the user.
"""

import azure.functions as func
import logging
import json
import os
import requests
import base64
from typing import Any, Dict, Optional

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_ACCESS_TOKEN_PROPERTY_NAME = "access_token"

def normalize_bearer(token: str) -> str:
    t = (token or "").strip()
    return t[7:].strip() if t.lower().startswith("bearer ") else t


def decode_jwt_payload(token: str) -> Dict[str, Any]:
    """
    Decode JWT payload WITHOUT signature validation (debug only).
    """
    t = normalize_bearer(token)
    parts = t.split(".")
    if len(parts) < 2:
        return {"_error": "not_a_jwt"}
    payload_b64 = parts[1]
    # pad base64
    payload_b64 += "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
        return payload
    except Exception as e:
        return {"_error": f"decode_failed: {e}"}


def log_token_debug(access_token: str) -> None:
    """
    Print minimal claims always, optionally print full token when explicitly enabled.
    """
    payload = decode_jwt_payload(access_token)
    minimal = {
        "aud": payload.get("aud"),
        "scp": payload.get("scp"),
        "roles": payload.get("roles"),
        "iss": payload.get("iss"),
        "tid": payload.get("tid"),
        "appid": payload.get("appid"),
        "azp": payload.get("azp"),
        "ver": payload.get("ver"),
    }
    logger.info("token claims (minimal): %s", json.dumps(minimal, ensure_ascii=False))

    # Only dump full token when explicitly enabled
    if os.getenv("DUMP_ACCESS_TOKEN", "false").lower() == "true":
        # ⚠️ debug only. Make sure to turn off and scrub logs later.
        logger.warning("DUMP_ACCESS_TOKEN=true. Dumping FULL access token for debugging.")
        logger.warning("access_token_full=%s", access_token)


def _whoami_tool_properties_json() -> str:
    """Return the MCP tool properties definition for whoami as JSON.

    This MCP tool expects a delegated Microsoft Graph access token as input.
    """
    tool_properties = [
        {
            "propertyName": _ACCESS_TOKEN_PROPERTY_NAME,
            "propertyType": "string",
            "description": (
                "User delegated Microsoft Graph access token (Bearer token). "
                "For hands-on purposes this token is passed directly to Microsoft Graph."
            ),
        }
    ]
    return json.dumps(tool_properties)


def get_token_info(authorization_header: Optional[str]) -> Dict[str, str]:
    """Extract token information safely (without logging the full token)."""
    if not authorization_header:
        return {"status": "no_token", "preview": "N/A", "length": 0}
    
    token = authorization_header.replace("Bearer ", "").strip()
    token_length = len(token)
    token_preview = token[:10] + "..." if token_length > 10 else token
    
    return {
        "status": "present",
        "preview": token_preview,
        "length": token_length
    }


def _safe(obj: Any) -> Any:
    """Safely dump objects for logging, masking token-like fields."""
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in [
                "authorization",
                "access_token",
                "token",
                "id_token",
                "refresh_token",
            ]:
                if isinstance(v, str):
                    out[k] = f"<masked len={len(v)}>"
                else:
                    out[k] = "<masked>"
            else:
                out[k] = _safe(v)
        return out
    if isinstance(obj, list):
        return [_safe(x) for x in obj]
    return obj


def _find_auth(content: Dict[str, Any]) -> Optional[str]:
    """Search common locations in the MCP context for an Authorization header."""
    paths = [
        ("headers",),
        ("http", "headers"),
        ("request", "headers"),
        ("metadata", "headers"),
        ("context", "headers"),
    ]

    for path in paths:
        cur: Any = content
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and isinstance(cur, dict):
            for hk in ["authorization", "Authorization"]:
                if hk in cur and isinstance(cur[hk], str):
                    return cur[hk]

    return None


def call_graph_api(access_token: str, endpoint: str = "me") -> Dict[str, Any]:
    url = f"https://graph.microsoft.com/v1.0/{endpoint}"
    token = normalize_bearer(access_token)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code >= 400:
            # Log Graph error body (often contains "InvalidAuthenticationToken" details)
            logger.error("Graph error status=%s body=%s", r.status_code, r.text[:2000])
        r.raise_for_status()
        return {"success": True, "data": r.json()}
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "status_code": getattr(e.response, "status_code", None) if hasattr(e, "response") else None,
        }


def _build_whoami_result(access_token: str, token_info: Dict[str, Any]) -> Dict[str, Any]:
    """Core whoami logic shared by HTTP and MCP implementations.

    Returns a dict with keys:
    - ok: bool
    - result: success payload (when ok is True)
    - error / status_code: error information (when ok is False)
    """
    graph_result = call_graph_api(access_token, "me")

    if graph_result["success"]:
        user_data = graph_result["data"]
        result = {
            "tool": "whoami",
            "user": {
                "displayName": user_data.get("displayName"),
                "userPrincipalName": user_data.get("userPrincipalName"),
                "id": user_data.get("id"),
                "jobTitle": user_data.get("jobTitle"),
                "mail": user_data.get("mail"),
            },
            "token_info": {
                "received": True,
                "preview": token_info.get("preview"),
                "length": token_info.get("length"),
            },
        }

        return {
            "ok": True,
            "result": result,
        }

    logger.error(f"Failed to call Graph API: {graph_result.get('error')}")
    return {
        "ok": False,
        "error": "Failed to call Microsoft Graph API",
        "details": graph_result.get("error"),
        "status_code": graph_result.get("status_code"),
    }


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="whoami",
    description=(
        "Get information about the current authenticated user via Microsoft Graph API. "
        "This MCP tool expects a delegated access token as an argument."
    ),
    toolProperties=_whoami_tool_properties_json(),
)
def whoami_mcp(context: str) -> str:
    """MCP tool implementation for whoami using the MCP extension.

    The runtime passes a JSON string in `context` that contains
    an `arguments` object with the tool parameters. This version
    expects an `access_token` argument that is forwarded to
    Microsoft Graph API `/me` endpoint.
    """
    logger.info("whoami MCP tool called")
    content: Dict[str, Any] = {}
    try:
        content = json.loads(context or "{}")
    except Exception as e:  # noqa: BLE001 - broad for logging/debug safety
        logger.warning(f"Invalid JSON context received by whoami MCP tool: {e}")
        return json.dumps(
            {
                "error": "Invalid MCP context JSON",
                "message": "The tool context payload could not be parsed as JSON.",
            },
            ensure_ascii=False,
        )

    logger.info(f"context keys: {list(content.keys())}")
    logger.info(
        "context safe dump: "
        + json.dumps(_safe(content), ensure_ascii=False)[:4000]
    )

    auth_header = _find_auth(content)
    auth_header_info = get_token_info(auth_header)
    logger.info(f"auth header status: {auth_header_info}")

    args = content.get("arguments", {}) or {}
    access_token = (args.get(_ACCESS_TOKEN_PROPERTY_NAME) or "").strip()

    if not access_token:
        logger.warning("whoami MCP tool called without access_token argument")
        return json.dumps(
            {
                "error": "Missing required argument: access_token",
                "message": "Pass a delegated Microsoft Graph access token in the 'access_token' argument.",
            },
            ensure_ascii=False,
        )
    access_token = normalize_bearer(access_token)
    log_token_debug(access_token)

    # Reuse the same token inspection logic used by the HTTP endpoint
    token_info = get_token_info(f"Bearer {access_token}")
    core_result = _build_whoami_result(access_token, token_info)

    if core_result["ok"]:
        logger.info("Successfully retrieved user info in MCP whoami tool")
        return json.dumps(core_result["result"], ensure_ascii=False)

    return json.dumps(
        {
            "error": core_result["error"],
            "details": core_result.get("details"),
            "status_code": core_result.get("status_code"),
        },
        ensure_ascii=False,
    )
