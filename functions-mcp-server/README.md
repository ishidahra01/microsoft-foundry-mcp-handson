# Azure Functions MCP Server (Legacy)

> ⚠️ **Note**: This is the legacy MCP server implementation. For the current **Authorization Header + OAuth Identity Passthrough** implementation, see [functions-mcp-selfhosted](../functions-mcp-selfhosted/).

## Overview

This directory contains an earlier version of the MCP server implementation. The current hands-on uses the **self-hosted MCP server** in the `functions-mcp-selfhosted` directory.

### Key Differences

| Aspect | This (Legacy) | Current (Selfhosted) |
|--------|---------------|----------------------|
| **MCP Protocol** | Function endpoints | HTTP + JSON-RPC 2.0 |
| **Architecture** | Separate HTTP endpoints | Unified MCP endpoint |
| **Token Handling** | Per-function extraction | Standardized context extraction |
| **Recommended** | No | ✅ Yes |

### Migration Guide

If you're using this legacy implementation, migrate to the current implementation:

1. Review [functions-mcp-selfhosted README](../functions-mcp-selfhosted/README.md)
2. Follow [MCP Server Setup Guide](../docs/06-mcp-server-setup.md)
3. Update APIM to point to new `/mcp` endpoint
4. Test with Foundry Agent

## Legacy Documentation

This is an Azure Functions-based MCP (Model Context Protocol) server that supports OAuth Identity Passthrough from Azure AI Foundry Agent.

## Features

- **OAuth Identity Passthrough**: Receives delegated user access tokens from Foundry Agent
- **Microsoft Graph API Integration**: Calls Graph API on behalf of the authenticated user
- **MCP Tool Implementation**: Exposes `whoami` tool that returns current user information
- **No Token Validation**: For hands-on purposes, tokens are not validated locally

## Endpoints

### MCP Tools

#### POST /api/mcp/whoami
Retrieves information about the current authenticated user via Microsoft Graph API `/me` endpoint.

**Headers:**
- `Authorization: Bearer <access_token>` (provided by Foundry OAuth Identity Passthrough)

**Response:**
```json
{
  "tool": "whoami",
  "user": {
    "displayName": "John Doe",
    "userPrincipalName": "john.doe@contoso.com",
    "id": "12345678-1234-1234-1234-123456789012",
    "jobTitle": "Software Engineer",
    "mail": "john.doe@contoso.com"
  },
  "token_info": {
    "received": true,
    "preview": "eyJ0eXAiOi...",
    "length": 1234
  }
}
```

#### GET /api/mcp/tools
Lists all available MCP tools.

#### GET /api/mcp/health
Health check endpoint.

## Local Development

### Prerequisites

- Python 3.9 or higher
- Azure Functions Core Tools v4
- Azure CLI (optional)

### Setup

1. Install dependencies:
```bash
cd functions-mcp-server
pip install -r requirements.txt
```

2. Copy local settings:
```bash
cp local.settings.json.template local.settings.json
```

3. Start the Functions runtime:
```bash
func start
```

The server will be available at `http://localhost:7071/api/mcp/`

### Testing Locally

You can test the endpoint with curl:

```bash
# Test with a dummy token (will fail Graph API call)
curl -X POST http://localhost:7071/api/mcp/whoami \
  -H "Authorization: Bearer dummy_token_for_testing" \
  -H "Content-Type: application/json"

# List tools
curl http://localhost:7071/api/mcp/tools

# Health check
curl http://localhost:7071/api/mcp/health
```

## Deployment to Azure

### Using Azure CLI

1. Create a Function App:
```bash
az functionapp create \
  --resource-group <resource-group-name> \
  --consumption-plan-location <location> \
  --runtime python \
  --runtime-version 3.9 \
  --functions-version 4 \
  --name <function-app-name> \
  --storage-account <storage-account-name>
```

2. Deploy the function:
```bash
func azure functionapp publish <function-app-name>
```

### Configuration

No special application settings are required for this hands-on implementation.

## Security Notes

⚠️ **This implementation is for hands-on/demonstration purposes:**

- **No JWT validation**: Tokens are accepted as-is without signature verification
- **No audience checks**: Token audience is not validated
- **Token logging**: Token preview (first 10 chars) and length are logged for debugging

For production use, you should:
- Implement proper JWT validation
- Verify token audience and scopes
- Remove token logging
- Use managed identities where possible
- Enable Private Endpoints

## Integration with APIM

After deploying, configure APIM to import this Functions API:

1. Get the Function App URL: `https://<function-app-name>.azurewebsites.net`
2. Import the OpenAPI specification or manually configure routes
3. Set up passthrough policy (see main README for details)

## Troubleshooting

### Token Not Received
- Check that OAuth Identity Passthrough is enabled in Foundry Agent
- Verify APIM is forwarding Authorization header
- Check Function logs for token preview

### Graph API Errors
- Ensure the token has `User.Read` scope
- Verify the token is valid (not expired)
- Check network connectivity to `graph.microsoft.com`

## License

See LICENSE file in the root directory.
