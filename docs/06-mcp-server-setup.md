# MCP Server Setup Guide

This guide covers setting up the self-hosted MCP (Model Context Protocol) server on Azure Functions using the Authorization Header pattern for OAuth Identity Passthrough.

## Overview

### What is a Self-hosted MCP Server?

A self-hosted MCP server is an HTTP API that implements the Model Context Protocol using JSON-RPC 2.0. Unlike managed MCP services, you have full control over:
- Authentication mechanisms
- Business logic implementation
- API integrations
- Deployment infrastructure

### Why Self-hosted?

**Benefits:**
- ✅ Full control over authentication (Authorization header support)
- ✅ Custom business logic and integrations
- ✅ Direct access to Azure services
- ✅ No vendor lock-in for MCP implementation
- ✅ Standard HTTP security practices

**This Implementation:**
- HTTP endpoint with JSON-RPC 2.0 protocol
- Authorization header-based token passing
- Azure Functions for serverless hosting
- Python runtime with FastMCP framework

## Architecture

```
┌──────────────────────────────────────────────┐
│     Azure Functions (Python 3.11+)           │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  MCP Server (FastMCP)                  │ │
│  │  - HTTP + JSON-RPC                     │ │
│  │  - Port: 8080 (customizable)           │ │
│  │                                        │ │
│  │  Endpoints:                            │ │
│  │  POST /mcp                             │ │
│  │    - initialize                        │ │
│  │    - tools/list                        │ │
│  │    - tools/call                        │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  Token Extraction                      │ │
│  │  - Read Authorization header           │ │
│  │  - Extract Bearer token                │ │
│  │  - Never accept tokens in arguments    │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  MCP Tools                             │ │
│  │  - whoami: Get user info from Graph    │ │
│  │  - greet: Simple test tool             │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

## Prerequisites

### Local Development
- Python 3.11 or higher
- Azure Functions Core Tools v4
- pip (Python package manager)
- Virtual environment (recommended)

### Azure Deployment
- Azure subscription
- Azure CLI (authenticated)
- Resource group
- Storage account (for Functions)

## Local Setup

### 1. Create Python Virtual Environment

```bash
cd functions-mcp-selfhosted

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
# Install required packages
pip install -r requirements.txt
```

**Key dependencies:**
- `azure-functions`: Azure Functions Python SDK
- `mcp`: Model Context Protocol SDK
- `requests`: HTTP client for Graph API calls

### 3. Configure Local Settings

```bash
# Copy template
cp local.settings.json.template local.settings.json
```

Edit `local.settings.json`:
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "FUNCTIONS_CUSTOMHANDLER_PORT": "8080"
  }
}
```

**Note**: No sensitive values needed for local development! OAuth tokens come from HTTP headers at runtime.

### 4. Start Local Server

```bash
func start
```

Expected output:
```
Azure Functions Core Tools
Core Tools Version:       4.x
Function Runtime Version: 4.x

Functions:
  mcp: [POST] http://localhost:7071/mcp

MCP server listening on port 8080
```

### 5. Test Local Server

#### Health Check
```bash
# Basic connectivity test
curl http://localhost:7071/api/health
```

#### Test with Mock Token
```bash
# Test MCP JSON-RPC endpoint
curl -X POST http://localhost:7071/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_token_12345" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

Expected response:
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

## Understanding the Code Structure

### Directory Layout

```
functions-mcp-selfhosted/
├── function_app.py          # Main MCP server implementation
├── host.json               # Functions host configuration
├── requirements.txt        # Python dependencies
├── local.settings.json     # Local development settings
├── .funcignore            # Files to exclude from deployment
└── README.md              # Component README
```

### function_app.py - Core Implementation

#### 1. MCP Server Initialization

```python
from mcp.server.fastmcp import FastMCP

# Configure MCP server
mcp_port = int(os.environ.get("FUNCTIONS_CUSTOMHANDLER_PORT", 8080))
mcp = FastMCP(
    "calculator",
    stateless_http=True,
    port=mcp_port,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )
)
```

**Key points:**
- `stateless_http=True`: HTTP-based MCP (not stdio)
- Custom port from environment variable
- Transport security configured for Azure Functions

#### 2. Token Extraction

```python
def extract_bearer_token_from_context(ctx: Context) -> str | None:
    """Extract Bearer token from Authorization header in MCP request context."""
    request_context = getattr(ctx, "request_context", None)
    if request_context is None:
        return None
    
    request = getattr(request_context, "request", None)
    if request is not None:
        headers = getattr(request, "headers", None)
        auth = headers.get("authorization") or headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            return auth[7:].strip()
    
    return None
```

**Important principles:**
- ✅ Extract from HTTP Authorization header
- ✅ Handle case-insensitive header names
- ✅ Strip "Bearer " prefix
- ❌ Never accept tokens from tool arguments

#### 3. MCP Tool Implementation

```python
@mcp.tool()
def whoami(ctx: Context) -> Dict[str, Any]:
    """Get information about the current user via Microsoft Graph.
    
    Expects a delegated Microsoft Graph access token provided via the
    HTTP Authorization header ("Bearer <token>").
    """
    # Extract token from header
    access_token = extract_bearer_token_from_context(ctx)
    if not access_token:
        return {
            "error": "Missing Authorization header",
            "message": (
                "Pass a delegated Microsoft Graph access token via the "
                "'Authorization: Bearer <token>' HTTP header; do not include "
                "tokens in tool arguments."
            )
        }
    
    # Call Graph API
    logger.info("whoami MCP tool called (self-hosted, header-based)")
    return build_whoami_response(access_token)
```

**Key aspects:**
- Decorated with `@mcp.tool()` for automatic registration
- Context parameter provides access to request metadata
- Clear error message if token is missing
- Token is passed to business logic, not exposed in logs

#### 4. Graph API Integration

```python
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
        return {
            "success": False,
            "error": str(exc),
            "status_code": getattr(exc.response, "status_code", None)
        }
```

**Security considerations:**
- Token is used immediately for API call
- Not stored or cached (stateless)
- Errors are logged without exposing token
- Timeout set to prevent hanging requests

### host.json Configuration

```json
{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "maxTelemetryItemsPerSecond": 20
      }
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

**Purpose:**
- Specifies Functions runtime version (2.0)
- Configures logging and telemetry
- Defines extension bundle version

### requirements.txt

```
azure-functions
mcp
requests
```

**Dependencies explained:**
- `azure-functions`: Core Functions SDK for Python
- `mcp`: Model Context Protocol implementation (FastMCP)
- `requests`: HTTP library for calling Microsoft Graph API

## Azure Deployment

### Option A: Using Deployment Script (Recommended)

The repository includes a PowerShell script for automated deployment:

```powershell
cd functions-mcp-selfhosted

# Run deployment script
..\scripts\deploy-functions.ps1
```

**What the script does:**
1. Creates resource group (if not exists)
2. Creates storage account with appropriate settings
3. Creates blob container for data
4. Creates Function App with unique name
5. Publishes function code
6. Displays the Function App URL

**Script output:**
```
Resource Group: rg-ms-foundry-mcp
Storage Account: stmcpserver123456
Function App: func-mcp-server-123456
Function App URL: https://func-mcp-server-123456.azurewebsites.net
```

### Option B: Manual Deployment with Azure CLI

#### Step 1: Create Resource Group

```bash
az group create \
  --name rg-foundry-mcp \
  --location eastus
```

#### Step 2: Create Storage Account

```bash
az storage account create \
  --name stmcpserver$(date +%s) \
  --resource-group rg-foundry-mcp \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-shared-key-access true
```

**Note**: For hands-on purposes, shared key access is enabled. For production, use managed identities.

#### Step 3: Create Function App

```bash
az functionapp create \
  --resource-group rg-foundry-mcp \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name func-mcp-server-$(date +%s) \
  --storage-account stmcpserver123456 \
  --os-type Linux
```

#### Step 4: Deploy Function Code

```bash
cd functions-mcp-selfhosted

# Deploy using Functions Core Tools
func azure functionapp publish func-mcp-server-123456
```

Expected output:
```
Deployment successful.
Remote build succeeded!
Functions in func-mcp-server-123456:
    mcp - [httpTrigger]
        Invoke url: https://func-mcp-server-123456.azurewebsites.net/mcp
```

### Verify Deployment

```bash
# Test health endpoint
curl https://func-mcp-server-123456.azurewebsites.net/api/health

# Test MCP endpoint
curl -X POST https://func-mcp-server-123456.azurewebsites.net/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_token" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Configuration

### Environment Variables

The MCP server supports these environment variables:

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `FUNCTIONS_CUSTOMHANDLER_PORT` | MCP server port | 8080 | No |
| `FUNCTIONS_WORKER_RUNTIME` | Runtime type | python | Yes |
| `AzureWebJobsStorage` | Storage connection | - | Yes |

**Note**: No Graph API credentials needed! Tokens come from Authorization headers at runtime.

### Application Settings (Azure)

For Azure deployment:

```bash
# No special settings required for basic operation
# Token is passed via Authorization header from Foundry
```

Optional settings for monitoring:

```bash
az functionapp config appsettings set \
  --name func-mcp-server-123456 \
  --resource-group rg-foundry-mcp \
  --settings \
    "APPLICATIONINSIGHTS_CONNECTION_STRING=<your-app-insights-connection-string>"
```

## Integration with APIM

After deploying the MCP server, configure APIM to expose it:

### 1. Get Function App URL

```bash
FUNCTION_URL="https://func-mcp-server-123456.azurewebsites.net"
echo $FUNCTION_URL
```

### 2. Import to APIM

Follow the [APIM Setup Guide](./02-apim-setup.md) to:
- Import the Functions API
- Configure Authorization header forwarding
- Set up CORS if needed
- Test the integration

### 3. Use APIM URL in Foundry

Configure your Foundry MCP tool to use:
```
https://apim-foundry-mcp-handson.azure-api.net/mcp
```

## Testing the MCP Server

### Test Tools/List

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

### Test Whoami (with real token)

To test with a real Microsoft Graph token:

```bash
# Get a token (using Azure CLI)
TOKEN=$(az account get-access-token \
  --resource https://graph.microsoft.com \
  --query accessToken \
  --output tsv)

# Call whoami
curl -X POST https://func-mcp-server-123456.azurewebsites.net/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
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

Expected response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tool": "whoami",
    "user": {
      "displayName": "John Doe",
      "userPrincipalName": "john.doe@contoso.com",
      "id": "12345...",
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

## Monitoring and Debugging

### View Logs (Local)

```bash
# Logs appear in terminal where 'func start' is running
# Look for lines like:
[2024-01-01T12:00:00.000Z] whoami MCP tool called (self-hosted, header-based)
```

### View Logs (Azure)

```bash
# Stream logs
az webapp log tail \
  --name func-mcp-server-123456 \
  --resource-group rg-foundry-mcp

# Or use Application Insights if configured
```

### Common Log Patterns

**Successful token extraction:**
```
Token status: present, preview: eyJ0eXAiOi..., length: 1234
```

**Missing token:**
```
No authorization token provided
```

**Graph API call:**
```
whoami MCP tool called (self-hosted, header-based)
Graph API call successful
```

## Troubleshooting

### Problem: "No authorization token provided"

**Symptoms:**
- MCP tool returns error about missing Authorization header
- Function logs show "No authorization token provided"

**Solutions:**
1. Verify APIM forwards Authorization header:
   - Check APIM policy includes `<set-header name="Authorization"...>`
2. Verify OAuth connection is attached to MCP tool in Foundry
3. Ensure Identity Passthrough is enabled in OAuth connection
4. Test direct Function call with Authorization header

### Problem: Graph API returns 401 Unauthorized

**Symptoms:**
- Token is received but Graph API rejects it
- Error: "Invalid token" or "Unauthorized"

**Solutions:**
1. Verify token has required scopes:
   ```bash
   # Decode JWT at https://jwt.ms to check scopes
   ```
2. Check token hasn't expired
3. Verify OAuth app has Microsoft Graph permissions
4. Ensure admin consent was granted

### Problem: Function deployment fails

**Symptoms:**
- `func azure functionapp publish` fails
- Error about Python version or dependencies

**Solutions:**
1. Verify Python version matches (3.11):
   ```bash
   python --version
   ```
2. Check requirements.txt is valid
3. Ensure Functions Core Tools is v4:
   ```bash
   func --version
   ```
4. Try cleaning and redeploying:
   ```bash
   rm -rf .python_packages
   func azure functionapp publish <app-name> --build remote
   ```

### Problem: MCP server not receiving requests

**Symptoms:**
- APIM returns 502 Bad Gateway
- Function logs show no incoming requests

**Solutions:**
1. Verify Function App is running:
   ```bash
   az functionapp show \
     --name func-mcp-server-123456 \
     --resource-group rg-foundry-mcp \
     --query state
   ```
2. Check Function App URL is correct in APIM
3. Verify APIM policy doesn't block requests
4. Test Function App directly (bypass APIM)

## Security Best Practices

### For Hands-on/Demo

✅ **Current implementation:**
- Tokens via Authorization header
- HTTPS for all communication
- Token preview logging (not full token)
- No token storage

### For Production

Enhance with:

1. **Token Validation**
   ```python
   # Add JWT signature validation
   # Verify token audience and issuer
   # Check token expiration
   ```

2. **Request Validation**
   ```python
   # Validate JSON-RPC structure
   # Sanitize input parameters
   # Rate limit requests
   ```

3. **Secure Logging**
   ```python
   # Remove token preview from logs
   # Use structured logging
   # Implement audit trail
   ```

4. **Network Security**
   - Use VNet integration
   - Enable Private Endpoints
   - Restrict outbound traffic

5. **Managed Identity**
   - Use managed identity for Azure services
   - Avoid storing secrets in config

## Next Steps

After setting up the MCP server:

1. ✅ [Configure APIM](./02-apim-setup.md) to expose the server
2. ✅ [Set up Foundry Agent](./03-foundry-setup.md) with OAuth connection
3. ✅ Test end-to-end OAuth flow
4. ✅ Deploy web app for user interface

## References

- [Azure Functions Python Developer Guide](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)
- [FastMCP Documentation](https://github.com/modelcontextprotocol/python-sdk)
- [Self-hosted MCP on Azure Functions (Japanese)](https://zenn.dev/microsoft/articles/host-existing-mcp-server-on-azure-functions)
- [Microsoft Graph API Reference](https://learn.microsoft.com/graph/api/overview)

## Additional Resources

- [Architecture Overview](./00-architecture-overview.md) - Understanding the overall design
- [OAuth Patterns](./00-architecture-overview.md#oauth-identity-passthrough-patterns) - Pattern A vs Pattern B
- [Troubleshooting Guide](./05-troubleshooting.md) - Common issues and solutions
