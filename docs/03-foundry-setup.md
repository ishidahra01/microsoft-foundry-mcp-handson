# Azure AI Foundry Setup Guide

This guide covers setting up Azure AI Foundry Agent V2 with OAuth Identity Passthrough and MCP tools.

## Prerequisites

- Azure AI Foundry Project created
- Entra ID App Registration completed ([Guide](./01-entra-id-setup.md))
- APIM with Functions API imported ([Guide](./02-apim-setup.md))
- Azure Functions MCP Server deployed

## Overview

We'll configure:
1. **OAuth Connection** with Identity Passthrough
2. **MCP Tool** pointing to APIM
3. **Agent V2** with the MCP tool

## Step 1: Create OAuth Connection

### Navigate to Foundry Portal

1. Go to [Azure AI Foundry](https://ai.azure.com)
2. Select your **Project**
3. In the left menu, go to **Shared resources** → **Connections**
4. Click **+ New connection**

### Configure OAuth Connection

Select **Custom** or **OAuth 2.0** connection type:

#### Basic Settings

- **Name**: `graph-oauth-passthrough`
- **Description**: `OAuth connection for MCP with Identity Passthrough`
- **Connection type**: `OAuth 2.0`

#### OAuth Configuration

| Field | Value |
|-------|-------|
| **Client ID** | `<application-client-id>` from Entra ID |
| **Client Secret** | `<client-secret-value>` from Entra ID |
| **Authorization URL** | `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize` |
| **Token URL** | `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token` |
| **Scope** | `https://graph.microsoft.com/.default` |
| **Redirect URI** | (Usually auto-filled by Foundry) |

#### Identity Passthrough

**⚠️ IMPORTANT**: Enable **Identity Passthrough**

- ✅ **Enable OAuth Identity Passthrough**: `ON`

This setting ensures that Foundry:
1. Prompts the user for consent (first time)
2. Obtains user-delegated access token
3. Passes the token to the MCP server

#### Save Connection

1. Click **Create** or **Save**
2. Test the connection if prompted
3. Note the connection name: `graph-oauth-passthrough`

## Step 2: Create MCP Tool

### Navigate to Tools

1. In your Project, go to **Tools** (or **Toolbox**)
2. Click **+ Add tool** or **+ New tool**
3. Select **MCP** or **Custom API** tool type

### Configure MCP Tool

#### Basic Information

- **Tool name**: `whoami_tool`
- **Display name**: `Who Am I`
- **Description**: 
  ```
  Get information about the current authenticated user via Microsoft Graph API.
  This tool uses OAuth Identity Passthrough to call the Graph API on behalf of the user.
  ```

#### Endpoint Configuration

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **URL** | `https://apim-foundry-mcp-handson.azure-api.net/mcp/whoami` |
| **Authentication** | Select the OAuth connection: `graph-oauth-passthrough` |

#### Request Configuration

**Headers**: (Usually auto-configured by OAuth connection)
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer {token}"
}
```

**Body**: (Empty for this tool)
```json
{}
```

#### Response Configuration

Define the expected response schema (optional but recommended):

```json
{
  "type": "object",
  "properties": {
    "tool": { "type": "string" },
    "user": {
      "type": "object",
      "properties": {
        "displayName": { "type": "string" },
        "userPrincipalName": { "type": "string" },
        "id": { "type": "string" },
        "jobTitle": { "type": "string" },
        "mail": { "type": "string" }
      }
    },
    "token_info": {
      "type": "object",
      "properties": {
        "received": { "type": "boolean" },
        "preview": { "type": "string" },
        "length": { "type": "number" }
      }
    }
  }
}
```

#### Save Tool

1. Click **Save**
2. Test the tool if testing interface is available
   - You may see an OAuth consent prompt
   - Grant permissions
   - Verify response contains user information

## Step 3: Create Foundry Agent (V2)

### Navigate to Agents

1. In your Project, go to **Agents** or **Build**
2. Click **+ New agent** or **+ Create agent**
3. Ensure you're using **Agent V2** (check API version)

### Configure Agent

#### Basic Settings

- **Agent name**: `mcp-oauth-demo-agent`
- **Description**: `Demo agent for OAuth Identity Passthrough with MCP`
- **Model deployment**: Select your deployed model (e.g., `gpt-4`, `gpt-35-turbo`)

#### Instructions

Provide clear instructions for the agent:

```markdown
You are a helpful AI assistant with access to Microsoft Graph API through MCP tools.

When a user asks about their identity or profile information, use the "whoami_tool" to retrieve their information from Microsoft Graph API.

The tool uses OAuth Identity Passthrough, which means:
- The first time it's called, the user will need to consent to Microsoft Graph access
- Subsequent calls will reuse the user's delegated access token
- The tool returns information about the authenticated user

Be helpful and informative in your responses. When you use the tool, explain what information you found.

Example interactions:
- User: "Who am I?" → Use whoami_tool and summarize the user's profile
- User: "What's my job title?" → Use whoami_tool and return the job title
- User: "Tell me about my account" → Use whoami_tool and provide relevant details
```

#### Tools

1. Click **+ Add tool**
2. Select **whoami_tool** from the list
3. Enable the tool for this agent

#### Advanced Settings (Optional)

- **Temperature**: `0.7` (default)
- **Max tokens**: `1000` (or as needed)
- **Top P**: `0.95` (default)

#### Save Agent

1. Click **Create** or **Save**
2. Note the **Agent ID** (you'll need this for the web app)
   - Usually in format: `agent_abc123xyz`
3. Note the **Project ID** if not already recorded

### Get Required IDs

You need these values for the web app:

1. **Agent ID**:
   - Found in agent details page
   - Or in the agent's API endpoint URL

2. **Project Endpoint**:
   - Go to Project **Settings** → **Overview**
   - Look for **API endpoint**
   - Format: `https://<project-name>.<region>.api.azureml.ms`

3. **API Key**:
   - Go to Project **Settings** → **Keys**
   - Copy the primary or secondary key

## Step 4: Test Agent in Foundry Portal

Before integrating with the web app, test in Foundry:

1. Open the agent in **Playground** or **Test** interface
2. Start a conversation:
   ```
   User: Who am I?
   ```

3. **First-time OAuth Flow**:
   - You should see an OAuth consent screen
   - Sign in with your Microsoft account
   - Grant permission to read your profile
   - Consent is given

4. **Agent Response**:
   - Agent should call the `whoami_tool`
   - Tool should return your user information
   - Agent should summarize the response

5. **Subsequent Requests**:
   - Ask again: "What's my email?"
   - Should work without new consent
   - Token is reused

### Verify OAuth Identity Passthrough

Check the tool logs in Foundry:
- Should show tool was called successfully
- Response should contain actual user data
- Token should have been passed to APIM

## Step 5: Get Configuration for Web App

Collect all required values for the web app's `.env.local`:

```env
# From Foundry Project Settings
FOUNDRY_ENDPOINT=https://<project-name>.<region>.api.azureml.ms

# From Foundry Project Keys
FOUNDRY_API_KEY=<your-api-key>

# From Agent Details
FOUNDRY_AGENT_ID=<agent-id>

# From Foundry Project
FOUNDRY_PROJECT_ID=<project-id>
```

## Architecture: How OAuth Identity Passthrough Works

```
┌─────────────────┐
│  User           │
│  (Web App)      │
└────────┬────────┘
         │ 1. Send message
         ↓
┌─────────────────────────────┐
│  Foundry Agent V2           │
│  - Receives user message    │
│  - Decides to use MCP tool  │
└────────┬────────────────────┘
         │ 2. First time: OAuth flow
         │    - Prompt user for consent
         │    - Get delegated token
         │ 3. Call MCP tool with token
         ↓
┌──────────────────────────────────┐
│  APIM                             │
│  - Receives Authorization header │
│  - Forwards to Functions         │
└────────┬─────────────────────────┘
         │ 4. Forward token
         ↓
┌──────────────────────────────────┐
│  Azure Functions MCP Server      │
│  - Receives Bearer token         │
│  - Calls Graph API /me           │
└────────┬─────────────────────────┘
         │ 5. Call with user token
         ↓
┌──────────────────────┐
│  Microsoft Graph API │
│  - Returns user info │
└──────────────────────┘
```

## Troubleshooting

### OAuth connection test fails

**Error**: "Invalid client ID or secret"
- Verify Client ID matches Entra ID App Registration
- Check Client Secret hasn't expired
- Ensure tenant ID in URLs is correct

### MCP tool returns 401 Unauthorized

- Check APIM endpoint is correct
- Verify OAuth connection is attached to the tool
- Ensure Identity Passthrough is enabled
- Test APIM endpoint directly

### Agent doesn't call the tool

- Review agent instructions
- Ensure tool is enabled for the agent
- Try more explicit prompts: "Use the whoami tool"
- Check agent logs for errors

### OAuth consent screen doesn't appear

- Verify Identity Passthrough is enabled
- Check OAuth connection configuration
- Ensure authorization URL is correct
- Try in incognito/private browser window

### Tool returns user info but for wrong user

This is expected! With Identity Passthrough:
- Each user sees their own information
- Token is user-specific, not app-specific
- This proves OAuth Identity Passthrough is working

## Next Steps

After completing Foundry setup:

1. ✅ Deploy Web App ([README](../webapp-copilotkit/README.md))
2. ✅ Configure web app environment variables
3. ✅ Test end-to-end flow
4. ✅ Review logs and monitoring

## Production Considerations

For production deployment:

1. **Security**:
   - Add JWT validation in APIM
   - Implement token caching
   - Use managed identities where possible
   - Regular secret rotation

2. **Monitoring**:
   - Enable Application Insights for all components
   - Set up alerts for failures
   - Monitor OAuth token refresh rates
   - Track MCP tool usage

3. **Scalability**:
   - Use premium APIM tier
   - Configure appropriate Functions plan
   - Implement caching where appropriate
   - Consider CDN for web app

4. **Compliance**:
   - Document data flows
   - Review Microsoft Graph permissions
   - Implement audit logging
   - Follow zero-trust principles

## References

- [Azure AI Foundry Agents Documentation](https://learn.microsoft.com/azure/ai-studio/how-to/agents)
- [OAuth 2.0 in Azure](https://learn.microsoft.com/azure/active-directory/develop/v2-oauth2-auth-code-flow)
- [Microsoft Graph API](https://learn.microsoft.com/graph/overview)
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io/)
