# Azure Functions Self-hosted MCP Server

This is a **self-hosted MCP (Model Context Protocol) server** implementation on Azure Functions that supports **OAuth Identity Passthrough** via **Authorization Header** authentication.

## Overview

### What is this?

A production-ready MCP server that:
- Runs on Azure Functions (serverless, scalable)
- Implements HTTP + JSON-RPC 2.0 protocol
- Extracts user tokens from `Authorization` headers
- Calls Microsoft Graph API on behalf of authenticated users
- Never accepts tokens in tool arguments

### Key Features

- ✅ **Authorization Header Pattern**: Tokens passed via HTTP headers, not arguments
- ✅ **OAuth Identity Passthrough**: Receives user-delegated access tokens from Foundry
- ✅ **Microsoft Graph Integration**: Calls Graph API on behalf of authenticated users
- ✅ **MCP Tool Implementation**: Exposes `whoami` and `greet` tools
- ✅ **Secure Logging**: Never logs full token values
- ✅ **Stateless Operation**: No token storage or caching

### Architecture

```
Azure AI Foundry Agent
    ↓ Authorization: Bearer <user-token>
APIM Gateway
    ↓ Forward Authorization header
Azure Functions MCP Server ← You are here
    ↓ Extract token from header
    ↓ Call Graph API with token
Microsoft Graph API
```

## Quick Start

### Prerequisites

- Python 3.11+
- Azure Functions Core Tools v4
- Azure CLI (for deployment)

### Local Development

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Start the server**:
```bash
func start
```

Server will be available at `http://localhost:7071/mcp`

3. **Test locally**:
```bash
# Test tools/list
curl -X POST http://localhost:7071/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Test whoami with dummy token (will fail Graph API call, but shows token extraction works)
curl -X POST http://localhost:7071/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_token_12345" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"whoami","arguments":{}}}'
```

### Deploy to Azure

See [MCP Server Setup Guide](../docs/06-mcp-server-setup.md) for detailed deployment instructions.

Quick deploy:
```bash
# Option A: Use provided script
..\scripts\deploy-functions.ps1

# Option B: Manual deployment
az functionapp create \
  --resource-group rg-foundry-mcp \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name func-mcp-server-$(date +%s) \
  --storage-account stmcpserver123456

func azure functionapp publish func-mcp-server-123456
```

## MCP Endpoints

### POST /mcp

Main MCP endpoint implementing JSON-RPC 2.0 protocol.

#### Supported Methods

1. **initialize**: Initialize MCP connection
2. **tools/list**: List available tools
3. **tools/call**: Execute a tool

#### Example: List Tools

```bash
curl -X POST https://func-mcp-server-123456.azurewebsites.net/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

Response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "whoami",
        "description": "Get information about the current user via Microsoft Graph",
        "inputSchema": {
          "type": "object",
          "properties": {}
        }
      },
      {
        "name": "greet",
        "description": "Simple greeting tool",
        "inputSchema": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string",
              "description": "Name to greet"
            }
          }
        }
      }
    ]
  }
}
```

#### Example: Call whoami Tool

```bash
curl -X POST https://func-mcp-server-123456.azurewebsites.net/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <valid-graph-token>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "whoami",
      "arguments": {}
    }
  }'
```

Response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
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
}
```

## Available Tools

### whoami

Get information about the current authenticated user via Microsoft Graph API `/me` endpoint.

**Required**: Authorization header with valid Microsoft Graph token

**Arguments**: None (empty object `{}`)

**Returns**: User profile information including display name, email, job title

**Example usage from Foundry Agent**:
- User asks: "Who am I?"
- Agent calls whoami tool
- Agent responds with user's information

### greet

Simple greeting tool for testing.

**Arguments**:
- `name` (string, optional): Name to greet (defaults to "World")

**Returns**: Greeting message

**Example**:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "greet",
    "arguments": {
      "name": "Alice"
    }
  }
}
```

Returns: `"Hello, Alice!"`

## Implementation Details

### Token Extraction

The server extracts Bearer tokens from the `Authorization` HTTP header:

```python
def extract_bearer_token_from_context(ctx: Context) -> str | None:
    """Extract Bearer token from Authorization header in MCP request context."""
    # Read from HTTP Authorization header
    # Never from tool arguments!
    ...
```

**Key principles**:
- ✅ Extract from HTTP Authorization header
- ✅ Handle case-insensitive header names
- ✅ Strip "Bearer " prefix
- ❌ Never accept tokens from tool arguments

### Graph API Integration

```python
def call_graph_api(access_token: str, endpoint: str = "me") -> Dict[str, Any]:
    """Call Microsoft Graph API with the provided delegated access token."""
    url = f"https://graph.microsoft.com/v1.0/{endpoint}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    # Call Graph API...
```

**Security considerations**:
- Token is used immediately for API call
- Not stored or cached (stateless)
- Errors are logged without exposing token
- Timeout set to prevent hanging requests

### Secure Logging

```python
def get_token_info(access_token: str) -> Dict[str, Any]:
    """Inspect the access token without logging the full value."""
    token = (access_token or "").strip()
    if not token:
        return {"received": False, "preview": "N/A", "length": 0}
    
    token_length = len(token)
    token_preview = token[:10] + "..." if token_length > 10 else token
    
    return {
        "received": True,
        "preview": token_preview,  # Only first 10 chars
        "length": token_length,
    }
```

**Logging principles**:
- ✅ Log token presence (true/false)
- ✅ Log token preview (first 10 chars only)
- ✅ Log token length
- ❌ Never log full token value

## File Structure

```
functions-mcp-selfhosted/
├── function_app.py          # Main MCP server implementation
├── host.json               # Functions host configuration
├── requirements.txt        # Python dependencies
├── .funcignore            # Files to exclude from deployment
├── .gitignore             # Git ignore patterns
└── README.md              # This file
```

### Key Files

**function_app.py**: Core MCP server implementation
- MCP server initialization with FastMCP
- Token extraction from Authorization header
- MCP tool implementations (whoami, greet)
- Graph API integration

**host.json**: Azure Functions configuration
- Runtime version: 2.0
- Logging and telemetry settings
- Extension bundle configuration

**requirements.txt**: Python dependencies
- `azure-functions`: Functions SDK
- `mcp`: Model Context Protocol implementation
- `requests`: HTTP client for Graph API

## Configuration

### Environment Variables

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `FUNCTIONS_CUSTOMHANDLER_PORT` | MCP server port | 8080 | No |
| `FUNCTIONS_WORKER_RUNTIME` | Runtime type | python | Yes |
| `AzureWebJobsStorage` | Storage connection | - | Yes |

**Important**: No Graph API credentials needed! Tokens come from Authorization headers at runtime.

### Application Settings (Azure)

No special application settings required for basic operation. Tokens are passed via Authorization headers from Foundry through APIM.

Optional settings:
- `APPLICATIONINSIGHTS_CONNECTION_STRING`: For monitoring (recommended)

## Security Notes

### Current Implementation (Hands-on Mode)

This implementation demonstrates the **Authorization Header pattern** in a simplified way:

**What IS implemented**:
- ✅ **Header-based token passing**: Tokens in Authorization headers
- ✅ **Token extraction**: Reading tokens from headers, not arguments
- ✅ **Secure logging**: Only token preview (first 10 chars) logged
- ✅ **HTTPS encryption**: All communication encrypted
- ✅ **Stateless operation**: No token storage

**What is NOT implemented** (intentionally for hands-on):
- ❌ **JWT validation**: Token signature not verified locally
- ❌ **Token audience checks**: Audience not validated
- ❌ **Token caching**: Each request re-validates with Graph API
- ❌ **Rate limiting**: No request throttling

**Rationale**: This is a hands-on/demonstration focused on:
1. Understanding OAuth Identity Passthrough flow
2. Learning Authorization Header pattern
3. Implementing MCP with proper authentication
4. Accessible learning experience

### Production Enhancements

For production deployments, add:

1. **JWT Validation**
   - Validate token signature against Entra ID public keys
   - Verify token audience matches expected value
   - Check token hasn't expired
   - Validate issuer

2. **Token Caching**
   - Cache tokens with appropriate TTL (5-60 minutes)
   - Reduce redundant Graph API calls
   - Implement cache invalidation on errors

3. **Error Handling**
   - Retry logic for transient failures
   - Circuit breaker pattern for Graph API
   - Detailed error messages without exposing tokens

4. **Monitoring**
   - Application Insights integration
   - Custom metrics for token usage
   - Alerts on failures
   - Performance tracking

5. **Network Security**
   - VNet integration
   - Private endpoints
   - Managed identity for Azure services

📖 **Detailed security recommendations**: [Architecture Overview - Security Model](../docs/00-architecture-overview.md#security-model)

## Troubleshooting

### "Missing Authorization header" Error

**Symptoms**: Tool returns error about missing token

**Solutions**:
1. Verify APIM forwards Authorization header
2. Check OAuth connection is attached to MCP tool in Foundry
3. Ensure Identity Passthrough is enabled
4. Test direct Functions call with Authorization header

### Graph API Returns 401

**Symptoms**: Token is received but Graph API rejects it

**Solutions**:
1. Verify token has `User.Read` scope (decode at jwt.ms)
2. Check token hasn't expired
3. Verify OAuth app has Microsoft Graph permissions
4. Test token with [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer)

### Function Not Responding

**Symptoms**: Requests timeout or return 502

**Solutions**:
1. Check Function App is running: `az functionapp show --name <app> --query state`
2. Review Function App logs: `az webapp log tail --name <app>`
3. Verify cold start isn't causing timeouts
4. Check Application Insights for errors

## Testing

### Local Testing

```bash
# Start Functions
func start

# Test in another terminal
# 1. Test tools/list (no auth needed)
curl -X POST http://localhost:7071/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# 2. Get a real token
TOKEN=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)

# 3. Test whoami with real token
curl -X POST http://localhost:7071/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"whoami","arguments":{}}}'
```

### Azure Testing

```bash
# Replace with your Function App name
FUNC_APP="func-mcp-server-123456"

# Test health endpoint
curl https://${FUNC_APP}.azurewebsites.net/api/health

# Test MCP endpoint (through APIM in production)
curl -X POST https://${FUNC_APP}.azurewebsites.net/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Documentation

- **[Architecture Overview](../docs/00-architecture-overview.md)** - Complete architecture explanation
- **[MCP Server Setup Guide](../docs/06-mcp-server-setup.md)** - Detailed setup and deployment
- **[APIM Setup](../docs/02-apim-setup.md)** - Configure APIM for this server
- **[Foundry Setup](../docs/03-foundry-setup.md)** - Configure Foundry Agent
- **[Troubleshooting](../docs/05-troubleshooting.md)** - Common issues and solutions

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/modelcontextprotocol/python-sdk)
- [Azure Functions Python Developer Guide](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)
- [Microsoft Graph API Reference](https://learn.microsoft.com/graph/api/overview)
- [Self-hosted MCP on Azure Functions (Japanese)](https://zenn.dev/microsoft/articles/host-existing-mcp-server-on-azure-functions)

## License

See [LICENSE](../LICENSE) file in the repository root.
