# Azure API Management (APIM) Setup Guide

This guide walks through setting up Azure API Management to import and expose the self-hosted MCP Server with **Authorization header forwarding** for OAuth Identity Passthrough.

## Overview

### APIM's Role in OAuth Identity Passthrough

APIM acts as a secure gateway between Azure AI Foundry Agent and the MCP Server:

1. **Receives requests from Foundry** with `Authorization: Bearer <user-token>` header
2. **Forwards the Authorization header** unchanged to the MCP server
3. **Provides monitoring and logging** without exposing tokens
4. **Enables policy-based security** (optional JWT validation, rate limiting)

**Critical for this architecture**: APIM must **preserve and forward** the Authorization header so the MCP server can extract user tokens.

📖 **Learn more**: [Architecture Overview](./00-architecture-overview.md#component-responsibilities)

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

## Step 3: Configure Policies for Authorization Header Forwarding

**This is the most critical step** for OAuth Identity Passthrough to work correctly.

### Why Authorization Header Forwarding is Essential

By default, APIM may:
- Strip certain headers when forwarding requests
- Modify or normalize header values
- Add its own authentication headers

For OAuth Identity Passthrough:
- ✅ **Must preserve** the original Authorization header from Foundry
- ✅ **Must forward** it unchanged to the MCP server
- ✅ **Must not** replace or remove it

### Understanding the Policy

The inbound policy ensures:
1. Authorization header from Foundry is captured
2. Header is explicitly set on the backend request
3. Header value is preserved exactly as received
4. MCP server receives the user-delegated token

### Global Policy (All Operations)

1. In the **MCP Server API**, click **All operations**
2. In the **Inbound processing** section, click **</>** (Code editor)
3. Replace with:

```xml
<policies>
    <inbound>
        <base />
        <!-- 
            CRITICAL: Forward Authorization header for OAuth Identity Passthrough
            This header contains the user-delegated access token from Foundry
        -->
        <set-header name="Authorization" exists-action="override">
            <value>@(context.Request.Headers.GetValueOrDefault("Authorization",""))</value>
        </set-header>
        
        <!-- Optional: Add correlation ID for request tracing -->
        <set-header name="X-Correlation-ID" exists-action="override">
            <value>@(Guid.NewGuid().ToString())</value>
        </set-header>
        
        <!-- Optional: Add timestamp for debugging -->
        <set-header name="X-Request-Time" exists-action="override">
            <value>@(DateTime.UtcNow.ToString("o"))</value>
        </set-header>
    </inbound>
    
    <backend>
        <base />
    </backend>
    
    <outbound>
        <base />
        <!-- Optional: Add CORS headers if calling from web apps -->
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
            <expose-headers>
                <header>*</header>
            </expose-headers>
        </cors>
    </outbound>
    
    <on-error>
        <base />
        <!-- Optional: Custom error handling -->
    </on-error>
</policies>
```

4. Click **Save**

### Policy Explanation

**Key Policy Elements**:

1. **`<set-header name="Authorization" exists-action="override">`**
   - Ensures Authorization header is present on backend request
   - `exists-action="override"` replaces any existing value
   - Critical for token forwarding

2. **`context.Request.Headers.GetValueOrDefault("Authorization","")`**
   - Reads Authorization header from incoming request
   - Returns empty string if header is missing (will cause error in MCP server)
   - Preserves exact token value

3. **`<base />`**
   - Applies parent policy settings
   - Important for policy inheritance

### Verifying Policy Configuration

After saving, verify the policy:

1. Click on any operation (e.g., `/whoami`)
2. In the **Inbound processing** section, you should see:
   - "set-header: Authorization"
   - "set-header: X-Correlation-ID"
3. Policy should be visible in the code editor

### Testing Authorization Header Forwarding

Test that APIM forwards the header correctly:

```bash
# Test with a dummy token
curl -X POST https://apim-foundry-mcp-handson.azure-api.net/mcp/whoami \
  -H "Authorization: Bearer test_token_12345" \
  -H "Content-Type: application/json" \
  -v

# Look for these in the response:
# - Error about invalid token (expected - token is fake)
# - NOT "Missing Authorization header" (that means forwarding failed)
```

**Expected behavior**:
- ❌ If you see "Missing Authorization header" → Policy is not forwarding correctly
- ✅ If you see "Invalid token" or Graph API errors → Forwarding works! (Token is just invalid)

### Why No validate-jwt in This Hands-on?

For this hands-on, we're **intentionally not validating JWT** in APIM:

**Reasons**:
- ✅ Simplifies initial setup and learning
- ✅ Faster to demonstrate OAuth Identity Passthrough flow
- ✅ JWT validation delegated to Foundry's OAuth mechanism
- ✅ Focus on understanding the token flow pattern

**In hands-on mode**: Token validation happens at Microsoft Graph API

**For production**: Add JWT validation (see Production section below)

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

After completing this setup, your architecture will be:

```
Azure AI Foundry Agent
    ↓ [Authorization: Bearer <user-token>]
    ↓ [Token in header, NOT in arguments!]
APIM Gateway (apim-foundry-mcp-handson.azure-api.net/mcp)
    ↓ [Forward Authorization header unchanged]
    ↓ [No JWT validation in hands-on mode]
    ↓ [Add correlation ID for tracing]
Azure Functions MCP Server (func-mcp-server.azurewebsites.net/mcp)
    ↓ [Extract token from Authorization header]
    ↓ [Use token for Graph API]
Microsoft Graph API
```

**Key Points**:
1. Token flows through APIM **in the Authorization header**
2. APIM **does not modify or validate** the token (hands-on mode)
3. MCP server **extracts token from header**, never from arguments
4. This follows **MCP official design pattern** for authentication

## Security Notes for Hands-on

⚠️ **Current setup is for demonstration only**:

- ❌ No JWT signature validation
- ❌ No token audience verification
- ❌ No IP restrictions
- ❌ No rate limiting (besides APIM defaults)
- ❌ No private endpoints

**Why this is acceptable for hands-on**:
- Focus on learning OAuth Identity Passthrough flow
- Simplified setup for demonstrations
- Token validation happens at Graph API level
- Foundry manages OAuth lifecycle

### Production Recommendations

For production deployments, enhance APIM policies:

#### 1. JWT Validation

Validate token signature and claims:

```xml
<inbound>
    <base />
    <!-- Validate JWT signature and claims -->
    <validate-jwt header-name="Authorization" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized">
        <openid-config url="https://login.microsoftonline.com/{tenant-id}/v2.0/.well-known/openid-configuration" />
        <required-claims>
            <!-- For Pattern A: Validate Graph API audience -->
            <claim name="aud">
                <value>https://graph.microsoft.com</value>
            </claim>
            <!-- For Pattern B: Validate MCP API audience -->
            <!-- <claim name="aud"><value>api://your-mcp-api-id</value></claim> -->
            
            <!-- Verify required scopes -->
            <claim name="scp" match="any">
                <value>User.Read</value>
            </claim>
        </required-claims>
    </validate-jwt>
    
    <!-- Then forward the validated token -->
    <set-header name="Authorization" exists-action="override">
        <value>@(context.Request.Headers.GetValueOrDefault("Authorization",""))</value>
    </set-header>
</inbound>
```

**Benefits**:
- Verifies token signature (prevents forgery)
- Validates token audience (prevents token reuse)
- Checks token hasn't expired
- Ensures required scopes are present

#### 2. Rate Limiting

Prevent abuse and ensure fair usage:

```xml
<inbound>
    <base />
    
    <!-- Global rate limit -->
    <rate-limit calls="100" renewal-period="60" />
    
    <!-- Per-user rate limit (based on token) -->
    <rate-limit-by-key calls="20" renewal-period="60" 
        counter-key="@(context.Request.Headers.GetValueOrDefault("Authorization","").AsJwt()?.Subject ?? "anonymous")" />
    
    <!-- Daily quota -->
    <quota calls="10000" renewal-period="86400" />
</inbound>
```

#### 3. IP Restrictions

Allow only trusted sources:

```xml
<inbound>
    <base />
    
    <!-- Restrict to specific IP ranges -->
    <ip-filter action="allow">
        <address>203.0.113.0/24</address>  <!-- Your corporate network -->
        <address>198.51.100.0/24</address>  <!-- Your VPN -->
    </ip-filter>
</inbound>
```

#### 4. Enhanced Logging (Without Exposing Tokens)

Log requests safely:

```xml
<inbound>
    <base />
    
    <!-- Log request details without token -->
    <set-variable name="requestTime" value="@(DateTime.UtcNow)" />
    <set-variable name="hasAuth" value="@(context.Request.Headers.ContainsKey("Authorization"))" />
    
    <trace source="apim-policy">
        Request received: @(context.Request.Method) @(context.Request.Url.Path)
        Has Authorization: @((bool)context.Variables["hasAuth"])
        Correlation ID: @(context.Request.Headers.GetValueOrDefault("X-Correlation-ID",""))
    </trace>
</inbound>
```

#### 5. Circuit Breaker Pattern

Protect backend from cascading failures:

```xml
<backend>
    <retry condition="@(context.Response.StatusCode >= 500)" count="3" interval="1" first-fast-retry="true">
        <base />
    </retry>
</backend>
```

📖 **For complete security model**: [Architecture Overview - Security Model](./00-architecture-overview.md#security-model)

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
