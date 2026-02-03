# Azure API Management (APIM) Setup Guide

This guide walks through setting up Azure API Management to import and expose the Azure Functions MCP Server.

## Prerequisites

- Azure subscription
- Azure Functions MCP Server deployed
- Resource group for APIM

## Step 1: Create APIM Instance

### Using Azure Portal

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Click **+ Create a resource**
3. Search for **API Management**
4. Click **Create**

### Configuration

- **Subscription**: Select your subscription
- **Resource group**: Select or create new (e.g., `rg-foundry-mcp-handson`)
- **Region**: Same as your Functions app (e.g., `East US`)
- **Resource name**: `apim-foundry-mcp-handson` (must be globally unique)
- **Organization name**: Your organization name
- **Administrator email**: Your email address
- **Pricing tier**: 
  - **Developer** (for hands-on/testing) - No SLA, cheaper
  - **Standard** or **Premium** (for production)

5. Click **Review + create**
6. Click **Create**

⏱️ **Note**: APIM creation takes 30-45 minutes

### Using Azure CLI

```bash
# Create resource group
az group create \
  --name rg-foundry-mcp-handson \
  --location eastus

# Create APIM instance
az apim create \
  --name apim-foundry-mcp-handson \
  --resource-group rg-foundry-mcp-handson \
  --location eastus \
  --publisher-name "Your Organization" \
  --publisher-email "your-email@example.com" \
  --sku-name Developer
```

## Step 2: Import Functions API

Once APIM is created:

### Method A: Import from Functions (Recommended)

1. In APIM portal, go to **APIs** in the left menu
2. Click **+ Add API**
3. Select **Function App**
4. Click **Browse** to select your Functions app
5. Select your Function App: `func-mcp-server`
6. Select the functions to import:
   - ✅ `mcp/whoami`
   - ✅ `mcp/tools`
   - ✅ `mcp/health`
7. Configure API:
   - **Display name**: `MCP Server API`
   - **Name**: `mcp-server-api`
   - **API URL suffix**: `mcp`
   - **Products**: Select `Unlimited` (for hands-on)
8. Click **Create**

### Method B: Manual Configuration

If auto-import doesn't work:

1. Click **+ Add API**
2. Select **HTTP** (manual)
3. Configure:
   - **Display name**: `MCP Server API`
   - **Name**: `mcp-server-api`
   - **Web service URL**: `https://<function-app-name>.azurewebsites.net/api`
   - **API URL suffix**: `mcp`
4. Click **Create**
5. Add operations manually:

#### Operation 1: whoami
- **URL**: POST `/whoami`
- **Display name**: `whoami`
- **Description**: `Get current user information`

#### Operation 2: List Tools
- **URL**: GET `/tools`
- **Display name**: `List Tools`

#### Operation 3: Health Check
- **URL**: GET `/health`
- **Display name**: `Health Check`

## Step 3: Configure Policies

For OAuth Identity Passthrough to work, we need to configure APIM to forward the Authorization header without modification.

### Global Policy (All Operations)

1. In the **MCP Server API**, click **All operations**
2. In the **Inbound processing** section, click **</>** (Code editor)
3. Replace with:

```xml
<policies>
    <inbound>
        <base />
        <!-- Forward Authorization header as-is -->
        <set-header name="Authorization" exists-action="override">
            <value>@(context.Request.Headers.GetValueOrDefault("Authorization",""))</value>
        </set-header>
        <!-- Optional: Add correlation ID for tracking -->
        <set-header name="X-Correlation-ID" exists-action="override">
            <value>@(Guid.NewGuid().ToString())</value>
        </set-header>
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
        <!-- Optional: Add CORS headers if needed -->
        <cors>
            <allowed-origins>
                <origin>*</origin>
            </allowed-origins>
            <allowed-methods>
                <method>GET</method>
                <method>POST</method>
                <method>OPTIONS</method>
            </allowed-methods>
            <allowed-headers>
                <header>*</header>
            </allowed-headers>
        </cors>
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
```

4. Click **Save**

### Why No validate-jwt?

For this hands-on, we're **not validating JWT** in APIM:

- ✅ Simplifies setup
- ✅ Faster to demonstrate OAuth Identity Passthrough
- ✅ Validation is delegated to Foundry's OAuth flow
- ⚠️ **Not recommended for production**

## Step 4: Test APIM Endpoints

### Get APIM Gateway URL

Your APIM endpoints will be at:
```
https://apim-foundry-mcp-handson.azure-api.net/mcp/whoami
https://apim-foundry-mcp-handson.azure-api.net/mcp/tools
https://apim-foundry-mcp-handson.azure-api.net/mcp/health
```

### Test Health Endpoint

```bash
curl https://apim-foundry-mcp-handson.azure-api.net/mcp/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "MCP Server",
  "version": "1.0.0"
}
```

### Test with Authorization Header

```bash
curl -X POST https://apim-foundry-mcp-handson.azure-api.net/mcp/whoami \
  -H "Authorization: Bearer test_token_12345" \
  -H "Content-Type: application/json"
```

This should return an error about invalid token (expected), but confirms the endpoint is working.

## Step 5: Configure Subscription Keys (Optional)

For hands-on purposes, you can disable subscription requirement:

1. Go to **APIs** → **MCP Server API**
2. Click **Settings** tab
3. Under **Subscription required**, uncheck the box
4. Click **Save**

Alternatively, use the subscription key from **Subscriptions** menu.

## Step 6: Monitor and Test

### Enable Application Insights (Recommended)

1. In APIM, go to **Application Insights** in left menu
2. Click **Enable**
3. Select or create Application Insights resource
4. Enable logging:
   - ✅ Requests
   - ✅ Errors
   - ✅ Dependencies

### View Logs

1. Go to **Application Insights**
2. Click **Logs**
3. Query example:

```kusto
requests
| where timestamp > ago(1h)
| where url contains "mcp"
| project timestamp, name, resultCode, duration, url
| order by timestamp desc
```

## Architecture Overview

```
Foundry Agent
    ↓ [Authorization: Bearer <token>]
APIM Gateway (apim-foundry-mcp-handson.azure-api.net/mcp)
    ↓ [Forward Authorization header]
    ↓ [No JWT validation]
Azure Functions (func-mcp-server.azurewebsites.net/api/mcp)
    ↓ [Use token for Graph API]
Microsoft Graph API
```

## Security Notes for Hands-on

⚠️ **Current setup is for demonstration only**:

- ❌ No JWT validation
- ❌ No IP restrictions
- ❌ No rate limiting (besides default)
- ❌ No private endpoints

### Production Recommendations

For production, add these policies:

1. **JWT Validation**:
```xml
<validate-jwt header-name="Authorization">
    <openid-config url="https://login.microsoftonline.com/{tenant-id}/v2.0/.well-known/openid-configuration" />
    <required-claims>
        <claim name="aud">
            <value>api://<your-api-app-id></value>
        </claim>
    </required-claims>
</validate-jwt>
```

2. **Rate Limiting**:
```xml
<rate-limit calls="100" renewal-period="60" />
```

3. **IP Restrictions**:
```xml
<ip-filter action="allow">
    <address>x.x.x.x</address>
</ip-filter>
```

## Troubleshooting

### APIM returns 401 Unauthorized
- Check subscription key is provided (if required)
- Verify API is published
- Check product association

### APIM returns 404 Not Found
- Verify API URL suffix matches: `/mcp`
- Check operation paths are correct
- Ensure API is added to a product

### Authorization header not reaching Functions
- Verify inbound policy is configured
- Check `set-header` policy syntax
- Review APIM trace logs

### APIM creation stuck
- APIM creation takes 30-45 minutes
- Check Azure status page for issues
- Verify subscription has quota

## Next Steps

After completing APIM setup:

1. ✅ Configure Foundry OAuth Connection (see [Foundry Setup Guide](./03-foundry-setup.md))
2. ✅ Create Foundry Agent with MCP tools
3. ✅ Deploy Web App
4. ✅ Test end-to-end flow

## References

- [Azure API Management Documentation](https://learn.microsoft.com/azure/api-management/)
- [Import Azure Functions as APIs](https://learn.microsoft.com/azure/api-management/import-function-app-as-api)
- [API Management policies](https://learn.microsoft.com/azure/api-management/api-management-policies)
