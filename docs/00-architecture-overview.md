# MCP Architecture Overview - Authorization Header + OAuth Identity Passthrough

## Purpose

This document provides a comprehensive overview of the MCP (Model Context Protocol) implementation using **Authorization Header** for authentication and **OAuth Identity Passthrough** for user-delegated access.

## Design Philosophy

### Core Principles

1. **Authentication via Headers**: All authentication credentials are passed via HTTP Authorization headers, never in tool arguments
2. **OAuth Identity Passthrough**: User-delegated tokens enable API calls on behalf of authenticated users
3. **MCP Standard Compliance**: Arguments contain only business parameters, following MCP best practices
4. **Standard HTTP Security Model**: MCP servers use the same security patterns as traditional HTTP APIs

### Why This Approach?

**Previous Implementation Issues:**
- OAuth tokens were injected into MCP `tools/call` arguments
- Tokens were exposed in Foundry Tool Trace and Approval logs
- Deviated from MCP and OAuth design principles
- Led to temporary workarounds due to `mcpToolTrigger` constraints

**Current Implementation Benefits:**
- ✅ Tokens are securely passed via Authorization headers
- ✅ No token exposure in traces or logs
- ✅ Follows MCP official design patterns
- ✅ Self-hosted MCP server with HTTP + JSON-RPC
- ✅ Clean separation between authentication and business logic

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          User's Browser                          │
│                    (Web App / CopilotKit UI)                    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Chat Messages
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│               Azure App Service (Node.js Web App)                │
│                    CopilotKit Server (/api/copilot)              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Foundry Agent V2 API
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│              Azure AI Foundry Agent (V2)                         │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  OAuth Identity Passthrough                              │  │
│  │  - User consent (first time)                             │  │
│  │  - Obtains user-delegated access token                   │  │
│  │  - Refreshes token automatically                         │  │
│  │  - Passes token in Authorization header                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Authorization: Bearer <user-token>
                                │ (No token in arguments!)
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│              Azure API Management (APIM)                         │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Inbound Policy                                          │  │
│  │  - Forward Authorization header as-is                    │  │
│  │  - No JWT validation (hands-on mode)                    │  │
│  │  - Add correlation ID for tracing                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Authorization: Bearer <user-token>
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│        Azure Functions (Python) - Self-hosted MCP Server         │
│                   HTTP + JSON-RPC Implementation                 │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  MCP Endpoints:                                          │  │
│  │  - initialize                                            │  │
│  │  - tools/list                                            │  │
│  │  - tools/call                                            │  │
│  │                                                           │  │
│  │  Token Handling:                                         │  │
│  │  - Extract from Authorization header                     │  │
│  │  - Never log full token value                           │  │
│  │  - Pass to Microsoft Graph API                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Authorization: Bearer <user-token>
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Microsoft Graph API                           │
│                    GET /v1.0/me                                  │
│                    (User-delegated permissions)                  │
└─────────────────────────────────────────────────────────────────┘
```

## OAuth Identity Passthrough Patterns

Azure AI Foundry supports OAuth Identity Passthrough, allowing MCP servers to receive user-delegated access tokens. There are two main patterns:

### Pattern A: Direct Graph API Access (Current Implementation)

**Use Case**: PoC, demonstrations, simple applications

```
Foundry Agent → [Graph Token] → MCP Server → Graph API
```

**Flow:**
1. Foundry obtains token with **Microsoft Graph scopes** (e.g., `User.Read`)
2. Token is passed to MCP server via Authorization header
3. MCP server calls Graph API directly with the received token
4. No additional token exchange required

**Advantages:**
- ✅ Simple architecture
- ✅ Fewer moving parts
- ✅ Ideal for PoC and demonstrations
- ✅ Direct token usage

**Considerations:**
- MCP server directly handles Graph API tokens
- All Graph permissions must be granted to the OAuth app

### Pattern B: On-Behalf-Of (OBO) Flow (Future Extension)

**Use Case**: Production, complex scenarios, boundary separation

```
Foundry Agent → [MCP Token] → MCP Server → [OBO Exchange] → Graph API
```

**Flow:**
1. Foundry obtains token with **MCP server API scopes**
2. Token is passed to MCP server via Authorization header
3. MCP server validates the token (audience = MCP server)
4. MCP server uses OBO flow to obtain Graph API token
5. MCP server calls Graph API with the exchanged token

**Advantages:**
- ✅ Clear security boundaries
- ✅ MCP server can validate incoming tokens
- ✅ Fine-grained permission control
- ✅ Production-ready pattern

**Considerations:**
- Requires additional Entra ID app registration for MCP server
- More complex token flow
- OBO requires proper app registration setup

**Note**: This repository demonstrates **Pattern A**. Pattern B is recommended for production deployments and can be implemented as a future enhancement.

## Component Responsibilities

### Web App (CopilotKit)
- Provides chat UI for users
- Calls Foundry Agent V2 API
- Manages conversation threads and messages
- No direct OAuth handling (delegated to Foundry)

### Azure AI Foundry Agent
- Orchestrates AI agent behavior
- **Manages OAuth Identity Passthrough**:
  - Prompts user for consent (first time)
  - Obtains and stores user-delegated tokens
  - Refreshes tokens automatically
  - Includes tokens in Authorization header when calling MCP tools
- Decides when to invoke MCP tools
- Processes tool responses

### API Management (APIM)
- Acts as gateway for MCP server
- **Forwards Authorization header** without modification
- Adds correlation IDs for tracing
- Provides rate limiting and monitoring
- Does NOT validate JWT (in hands-on mode)

### Azure Functions MCP Server
- Self-hosted MCP server implementation
- HTTP endpoint with JSON-RPC protocol
- **Extracts token from Authorization header**
- Calls Microsoft Graph API with user token
- Returns structured responses to Foundry

### Microsoft Graph API
- Provides user data and operations
- Validates user-delegated tokens
- Returns data based on granted permissions

## Authentication Flow

### First-Time User Flow

```
1. User sends message: "Who am I?"
   └─> Web App → Foundry Agent

2. Foundry Agent determines MCP tool is needed
   └─> Checks for user token
   └─> No token exists

3. Foundry generates OAuth consent URL
   └─> Returns consent URL to user

4. User clicks consent link
   └─> Redirected to Entra ID login
   └─> Signs in with Microsoft account
   └─> Grants requested permissions

5. Entra ID returns authorization code
   └─> Foundry exchanges for access token
   └─> Token stored for this user + connection

6. Foundry calls MCP tool with token
   POST https://apim.../mcp
   Authorization: Bearer <user-token>
   
   {
     "method": "tools/call",
     "params": {
       "name": "whoami",
       "arguments": {}  ← No token in arguments!
     }
   }

7. APIM forwards request to Functions
   └─> Authorization header preserved

8. MCP Server extracts token from header
   └─> Calls Graph API: GET /v1.0/me
   └─> Returns user information

9. Foundry receives response
   └─> Sends to LLM for response generation
   └─> Returns to Web App
   └─> User sees their information
```

### Subsequent Requests Flow

```
1. User sends another message requiring MCP tool
   └─> Web App → Foundry Agent

2. Foundry checks for stored token
   └─> Token exists and is valid
   └─> No consent needed

3. Foundry calls MCP tool immediately
   Authorization: Bearer <cached-user-token>

4. Same flow as steps 7-9 above
   └─> No user interaction required
```

### Token Refresh Flow

```
1. Foundry detects token is expired or expiring soon
   └─> Uses refresh token automatically
   └─> Obtains new access token
   └─> Updates stored token

2. User experiences no interruption
   └─> Token refresh is transparent
```

## Security Model

### Current Implementation (Hands-on Mode)

**What is implemented:**
- ✅ OAuth 2.0 authorization code flow
- ✅ User consent and delegation
- ✅ Token passed via Authorization header
- ✅ HTTPS encryption for all communication
- ✅ Token preview logging (first 10 chars only)

**What is NOT implemented (intentionally):**
- ❌ JWT signature validation in APIM
- ❌ Token audience validation
- ❌ Rate limiting (beyond defaults)
- ❌ IP restrictions
- ❌ Private endpoints

**Rationale**: This is a hands-on/demonstration project focused on showing OAuth Identity Passthrough and MCP integration. Security is simplified to make the learning experience accessible.

### Production Recommendations

For production deployments, implement:

1. **JWT Validation in APIM**
   ```xml
   <validate-jwt header-name="Authorization">
       <openid-config url="https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration" />
       <required-claims>
           <claim name="aud"><value>api://your-api-id</value></claim>
       </required-claims>
   </validate-jwt>
   ```

2. **Rate Limiting**
   ```xml
   <rate-limit calls="100" renewal-period="60" />
   <quota calls="10000" renewal-period="86400" />
   ```

3. **Private Endpoints**
   - Use VNet integration for Functions
   - Configure APIM in internal mode
   - Private Endpoints for all Azure services

4. **Token Security**
   - Remove all token logging
   - Implement token caching with appropriate TTL
   - Use short-lived tokens (5-60 minutes)
   - Regular secret rotation for OAuth client secrets
   - Consider certificate-based authentication

5. **Monitoring & Alerting**
   - Application Insights for all components
   - Alerts on authentication failures
   - Monitor token refresh rates
   - Track OAuth consent patterns
   - Audit logging for compliance

## MCP Server Implementation

### HTTP + JSON-RPC Protocol

The MCP server is implemented as a standard HTTP API using JSON-RPC 2.0 protocol:

```python
# Endpoint: POST /mcp
# Content-Type: application/json

Request:
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "whoami",
    "arguments": {}  # Business parameters only, no tokens!
  }
}

Response:
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tool": "whoami",
    "user": {
      "displayName": "John Doe",
      "userPrincipalName": "john.doe@contoso.com"
    }
  }
}
```

### Token Extraction

```python
def extract_bearer_token_from_context(ctx: Context) -> str | None:
    """Extract Bearer token from Authorization header in MCP request context."""
    # Read from HTTP Authorization header
    # Never from tool arguments!
    auth = context.request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip()
    return None
```

### Key Principles

1. **Header-based authentication**: Always extract tokens from HTTP headers
2. **No token in arguments**: MCP tool arguments contain only business data
3. **Secure logging**: Never log full token values (only previews)
4. **Error handling**: Return clear errors when tokens are missing or invalid

## References

### Official Documentation

- **Azure AI Foundry MCP Authentication**: [Microsoft Learn - MCP Authentication](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/mcp-authentication?view=foundry)
- **Model Context Protocol Specification**: [MCP Specification](https://modelcontextprotocol.io/)
- **OAuth 2.0 Authorization Code Flow**: [Microsoft Identity Platform](https://learn.microsoft.com/entra/identity-platform/v2-oauth2-auth-code-flow)
- **Microsoft Graph API**: [Graph API Overview](https://learn.microsoft.com/graph/overview)

### Implementation Guides

- **Self-hosted MCP Server on Azure Functions**: [Zenn Article (Japanese)](https://zenn.dev/microsoft/articles/host-existing-mcp-server-on-azure-functions)
- **Azure Functions Python**: [Functions Python Developer Guide](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)
- **Azure API Management**: [APIM Documentation](https://learn.microsoft.com/azure/api-management/)

### Related Documentation in this Repository

- [Entra ID App Registration Guide](./01-entra-id-setup.md)
- [APIM Setup Guide](./02-apim-setup.md)
- [Foundry Agent Setup Guide](./03-foundry-setup.md)
- [MCP Server Setup Guide](./06-mcp-server-setup.md)
- [Deployment Guide](./04-deployment-guide.md)
- [Troubleshooting Guide](./05-troubleshooting.md)

## Conclusion

This architecture demonstrates the **official MCP design pattern** for authentication:
- Credentials in headers, not arguments
- OAuth Identity Passthrough for user delegation
- Standard HTTP security practices
- Clean separation of concerns

The implementation provides a solid foundation for understanding MCP + OAuth integration while remaining accessible for hands-on learning.
