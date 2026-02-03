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
from typing import Any, Dict, Optional

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def call_graph_api(access_token: str, endpoint: str = "me") -> Dict[str, Any]:
    """
    Call Microsoft Graph API with the provided access token.
    
    Args:
        access_token: User delegated access token
        endpoint: Graph API endpoint (e.g., 'me', 'me/photo')
    
    Returns:
        API response as dictionary
    """
    url = f"https://graph.microsoft.com/v1.0/{endpoint}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return {
            "success": True,
            "data": response.json()
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Graph API call failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        }


@app.route(route="mcp/whoami", methods=["POST"])
def whoami(req: func.HttpRequest) -> func.HttpResponse:
    """
    MCP Tool: whoami
    
    Returns information about the current user using Microsoft Graph API.
    This tool uses the delegated access token passed via OAuth Identity Passthrough.
    """
    logger.info("whoami tool called")
    
    # Get authorization header
    auth_header = req.headers.get("Authorization")
    token_info = get_token_info(auth_header)
    
    logger.info(f"Token status: {token_info['status']}, "
               f"preview: {token_info['preview']}, "
               f"length: {token_info['length']}")
    
    # If no token is present, return error
    if token_info["status"] == "no_token":
        logger.warning("No authorization token provided")
        return func.HttpResponse(
            json.dumps({
                "error": "No authorization token provided",
                "message": "This tool requires OAuth Identity Passthrough to be configured"
            }),
            mimetype="application/json",
            status_code=401
        )
    
    # Extract the actual token
    access_token = auth_header.replace("Bearer ", "").strip()
    
    # Call Microsoft Graph API /me endpoint
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
                "mail": user_data.get("mail")
            },
            "token_info": {
                "received": True,
                "preview": token_info["preview"],
                "length": token_info["length"]
            }
        }
        
        logger.info(f"Successfully retrieved user info for: {user_data.get('userPrincipalName')}")
        
        return func.HttpResponse(
            json.dumps(result, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )
    else:
        logger.error(f"Failed to call Graph API: {graph_result.get('error')}")
        return func.HttpResponse(
            json.dumps({
                "error": "Failed to call Microsoft Graph API",
                "details": graph_result.get("error"),
                "status_code": graph_result.get("status_code")
            }),
            mimetype="application/json",
            status_code=500
        )


@app.route(route="mcp/tools", methods=["GET"])
def list_tools(req: func.HttpRequest) -> func.HttpResponse:
    """
    MCP Extension: List available tools
    
    Returns metadata about available MCP tools in this server.
    """
    tools = {
        "tools": [
            {
                "name": "whoami",
                "description": "Get information about the current authenticated user via Microsoft Graph API",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    }
    
    return func.HttpResponse(
        json.dumps(tools),
        mimetype="application/json",
        status_code=200
    )


@app.route(route="mcp/health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint for monitoring."""
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "service": "MCP Server",
            "version": "1.0.0"
        }),
        mimetype="application/json",
        status_code=200
    )
