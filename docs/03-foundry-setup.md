## Microsoft Foundry Setup Guide (New Portal / Agent V2)

This guide explains how to configure **Microsoft Foundry Agent V2** with
**OAuth Identity Passthrough** and **MCP tools using Authorization header authentication**.

---

## Overview

### What you will configure in this section

- Microsoft Foundry **Agent V2**
- MCP tool (via APIM)
- OAuth Identity Passthrough (user-delegated)
- Token transfer via Authorization header

### Important assumptions

- **Do not include the access token in MCP arguments**
- Authentication information is passed **only via the Authorization header**
- Microsoft Foundry is responsible for the OAuth flow and token management

---

## Step 1: Create an Agent in the Microsoft Foundry portal

1. Go to https://ai.azure.com
2. Select your **Project**
3. In the left menu, select **Agents** → **Create agent**
4. Choose **Agent V2** (New API)

### Basic settings

- Name: `mcp-oauth-demo-agent`
- Description:

   ```
   Agent using MCP tools with OAuth Identity Passthrough.
   Calls Microsoft Graph API on behalf of the signed-in user.
   ```
- Model: Any model (e.g., GPT-4.1 / GPT-4o)

### Instructions (example)

```markdown
You are an assistant with access to MCP tools.

When the user asks about their identity or profile,
use the whoami MCP tool to retrieve user information
from Microsoft Graph API.

The tool uses OAuth Identity Passthrough, so:
- The first call will require user consent
- Subsequent calls reuse the delegated token
```

---

## Step 2: Create an MCP tool from the Agent screen

> ⚠️ In the New Portal, MCP tools are created **from the Agent**.

1. Open the Agent you created
2. Open the **Tools** tab
3. Click **Add tool**
4. Select **MCP**

---

## Step 3: Configure the MCP tool (OAuth Identity Passthrough)

### Basic information

- Tool name: `whoami`
- Description:

   ```
   Returns information about the current authenticated user
   using Microsoft Graph API.

   Authentication is handled via OAuth Identity Passthrough.
   The access token is passed via Authorization header.
   ```

### Endpoint

- Endpoint URL:

   ```
   https://<apim-name>.azure-api.net/mcp
   ```
- Method: `POST`

> APIM acts as a reverse proxy to the Azure Functions MCP server.

---

## Step 4: Select OAuth Identity Passthrough

### Authentication

- Authentication type: OAuth
- OAuth mode: **Identity Passthrough**

### OAuth settings

| Field             | Value                                                                 |
| ----------------- | --------------------------------------------------------------------- |
| Client ID         | Client ID of your Entra ID app                                        |
| Client Secret     | Client Secret of your Entra ID app                                    |
| Authorization URL | `https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/authorize` |
| Token URL         | `https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/token`     |
| Refresh URL         | `https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/token`   |
| Scope             | `openid profile email User.Read`                                     |

> Based on this configuration, Microsoft Foundry obtains user-delegated tokens.

---

## Step 5: Add the Redirect URI to Entra ID

### Important points (specific to the New Portal)

- When creating the MCP tool, **Microsoft Foundry automatically generates a Redirect URI**.
- Example:

   ```
   https://global.consent.azure-apim.net/redirect/xxxxx
   ```

### Steps

1. In the MCP tool configuration screen, copy the **Redirect URI**
2. In Entra ID, go to App registrations → your app → **Authentication**
3. Under **Web** Redirect URIs, add the copied value
4. Save

> ⚠️ If you skip this, you will get an AADSTS error at sign-in and the consent screen will not appear.

---

## Step 6: Test in the Microsoft Foundry portal

### First execution

1. Open the Playground for the Agent you created
2. Example:

    ```
    Who am I?
    ```
3. An **OAuth consent screen** appears in the browser
4. Review and accept the requested Microsoft Graph permissions

### What to verify

- The consent screen appears
- The tool executes successfully
- The response contains your own user information

### Subsequent runs

- Execution works without showing the consent screen again
- The same user’s delegated token is reused

---

## Signs that OAuth Identity Passthrough is working correctly

- Results differ per user
- There is no `access_token` field in MCP arguments
- On the APIM / Functions side, the token is received via the Authorization header

---

## Architecture: Microsoft Foundry × MCP × OAuth

```
User
 ↓
Microsoft Foundry Agent V2
 - OAuth Identity Passthrough
 - Token management
 ↓ Authorization: Bearer <user token>
APIM
 ↓
Azure Functions (Self-hosted MCP)
 ↓
Microsoft Graph API
```

---

## Common mistakes (not valid in the New Portal)

- Trying to create a standalone OAuth connection in advance
- Putting `access_token` into MCP arguments
- Forgetting to register the Redirect URI in Entra ID
- Reusing instructions based on the old Agent / old API

---

## Completion checklist (Microsoft Foundry)

- [ ] Agent is created in the New Portal (Agent V2)
- [ ] MCP tool is configured with OAuth Identity Passthrough
- [ ] Redirect URI is registered in Entra ID
- [ ] Consent screen appears on first execution
- [ ] Graph API is called using the Authorization header

---

## References (official)

- Microsoft Foundry MCP Authentication  
   https://learn.microsoft.com/azure/ai-studio/how-to/mcp-authentication
- Microsoft Foundry Agents (New API)  
   https://learn.microsoft.com/azure/ai-studio/how-to/agents
  
