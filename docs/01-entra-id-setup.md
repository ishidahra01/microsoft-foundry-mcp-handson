# Entra ID App Registration Setup Guide

This guide walks through creating an Entra ID App Registration for **OAuth Identity Passthrough** with Azure AI Foundry Agent.

## Overview

### What is OAuth Identity Passthrough?

OAuth Identity Passthrough enables Azure AI Foundry Agent to:
1. Prompt users for consent (first time)
2. Obtain **user-delegated access tokens**
3. Pass tokens to MCP servers via **Authorization headers**
4. Call APIs (like Microsoft Graph) **on behalf of the authenticated user**

This ensures that API calls are made with the user's identity and permissions, not the application's identity.

📖 **Learn more**: [Architecture Overview - OAuth Identity Passthrough](./00-architecture-overview.md#oauth-identity-passthrough-patterns)

## Prerequisites

- Access to Azure Portal
- Permissions to create App Registrations in your Entra ID tenant
- Tenant ID (found in Entra ID overview page)

## Step 1: Create App Registration

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Go to **Entra ID** (formerly Azure Active Directory)
3. Click **App registrations** in the left menu
4. Click **+ New registration**

### Registration Details

- **Name**: `Foundry-OAuth-MCP-Handson` (or your preferred name)
- **Supported account types**: 
  - Select **Accounts in this organizational directory only (Single tenant)**
  - For multi-tenant scenarios, choose appropriate option
- **Redirect URI**: 
  - Select **Web**
  - Enter: `https://login.microsoftonline.com/common/oauth2/nativeclient`
  - **Note**: Foundry will provide its own redirect URI later; this is a placeholder
  - You'll add Foundry's redirect URI in Step 7

5. Click **Register**

## Step 2: Note Application IDs

After creation, you'll see the overview page. **Save these values**:

- **Application (client) ID**: `12345678-1234-1234-1234-123456789012`
- **Directory (tenant) ID**: `87654321-4321-4321-4321-210987654321`

You'll need these for:
- Foundry OAuth connection configuration
- Token URL and authorization URL construction

## Step 3: Create Client Secret

1. In the left menu, click **Certificates & secrets**
2. Click **+ New client secret**
3. Enter a description: `Foundry OAuth Secret`
4. Select expiration period: `24 months` (or as per your policy)
5. Click **Add**
6. **IMPORTANT**: Copy the secret **Value** immediately (not the Secret ID)
   - Format: `abc123def456...`
   - ⚠️ This value is only shown once!
   - Store securely (e.g., Azure Key Vault for production)

## Step 4: Configure API Permissions

### Understanding Delegated Permissions

For **OAuth Identity Passthrough**, we use **Delegated permissions**:
- User consents to the requested permissions
- Token contains user's identity and permissions
- API calls are made **on behalf of the user**
- User must have the permission to perform the action

This is different from **Application permissions** (app-only access).

### Add Microsoft Graph Permissions

1. In the left menu, click **API permissions**
2. Click **+ Add a permission**
3. Select **Microsoft Graph**
4. Select **Delegated permissions**
5. Search and add these permissions:
   - **User.Read** - Read user profile information
   
6. Click **Add permissions**

### Understanding Permission Scopes

- **User.Read**: Allows reading basic profile (name, email, job title)
- Minimal scope for this hands-on
- For production, add only required scopes:
  - `Mail.Read` for reading emails
  - `Calendars.Read` for reading calendar
  - `Files.Read.All` for reading files
  - etc.

### Grant Admin Consent (Recommended)

1. Click **Grant admin consent for [Your Organization]**
2. Click **Yes** to confirm
3. Status should change to **Granted** with green checkmark

**Why admin consent?**
- Pre-approves permissions for all users in the organization
- Users won't see consent prompt (unless you want them to)
- Recommended for internal applications

> If you don't grant admin consent, users will see a consent prompt on first use. This is fine for hands-on purposes.

## Step 5: Configure Authentication Settings

1. In the left menu, click **Authentication**
2. Under **Implicit grant and hybrid flows**, ensure nothing is checked (not needed for this flow)
3. Under **Allow public client flows**:
   - Set to **No** (we're using confidential client)
4. Click **Save**

## Step 6: Note All Required Values

You now have all the values needed for Foundry OAuth Connection:

```plaintext
Client ID:              <application-client-id>
Client Secret:          <secret-value>
Tenant ID:              <directory-tenant-id>
Authorization URL:      https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize
Token URL:              https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token
Scopes:                 https://graph.microsoft.com/.default
```

### Understanding OAuth URLs

**Authorization URL**: Where users are redirected for consent
- Contains tenant ID for single-tenant apps
- Use `/common/` for multi-tenant apps

**Token URL**: Where Foundry exchanges authorization code for token
- Must match tenant configuration
- Returns access token and refresh token

**Scopes**: Defines what permissions the token will have
- `https://graph.microsoft.com/.default` = all delegated permissions granted to the app
- Can specify individual scopes: `https://graph.microsoft.com/User.Read`

## Step 7: Add Foundry Redirect URI (After Creating OAuth Connection)

After you create the OAuth connection in Foundry (see [Foundry Setup Guide](./03-foundry-setup.md)), Foundry will provide a redirect URI.

1. Copy the redirect URI from Foundry OAuth connection
2. Return to Entra ID App Registration
3. Go to **Authentication**
4. Under **Web** platform, click **+ Add URI**
5. Paste the Foundry redirect URI
6. Click **Save**

**Typical Foundry redirect URI format**:
```
https://auth.azure.com/redirect
```
(The actual URI will be provided by Foundry)

## OAuth Identity Passthrough: Pattern A vs Pattern B

This hands-on implements **Pattern A** (Direct Graph API Access):

### Pattern A: Direct Graph Access (Current)

```
Entra ID App Registration:
- API Permissions: Microsoft Graph (Delegated)
  - User.Read
- Token audience: https://graph.microsoft.com
```

**Flow**:
1. Foundry requests token with Graph API scopes
2. User consents to Graph API permissions
3. Token is issued for Graph API (audience = Graph)
4. MCP server receives token via Authorization header
5. MCP server calls Graph API directly with the token

### Pattern B: OBO Flow (Future Enhancement)

For production scenarios with clear security boundaries:

```
Entra ID App Registrations (2 apps):
1. MCP Server API App:
   - Expose API with scopes
   - API Permissions: Microsoft Graph (Delegated)
   
2. OAuth Client App:
   - API Permissions: MCP Server API (Delegated)
```

**Flow**:
1. Foundry requests token for MCP Server API
2. User consents to MCP Server permissions
3. Token is issued for MCP Server (audience = MCP API)
4. MCP server validates incoming token
5. MCP server uses OBO flow to get Graph token
6. MCP server calls Graph API with exchanged token

📖 **Learn more**: [Architecture Overview - OAuth Patterns](./00-architecture-overview.md#oauth-identity-passthrough-patterns)

## Security Best Practices

### For Hands-on/Demo

✅ **Current setup is acceptable for demonstration**:
- Client secret with 24-month expiration
- User.Read permission only
- Standard OAuth 2.0 flow

### For Production

Consider these enhancements:

1. **Certificate-based authentication** instead of client secret
2. **Shorter secret expiration** (e.g., 6 months) with rotation process
3. **Conditional Access policies** to restrict access
4. **Monitoring and logging** of authentication events
5. **Least privilege permissions** - add only what's strictly needed
6. **Separate app registrations** for different environments

## Testing the App Registration

You can test if the app registration works using this PowerShell script:

```powershell
# Install MSAL.PS if needed
Install-Module MSAL.PS -Scope CurrentUser

# Get token
$clientId = "<your-client-id>"
$tenantId = "<your-tenant-id>"
$clientSecret = "<your-client-secret>"

$secureSecret = ConvertTo-SecureString $clientSecret -AsPlainText -Force
$credential = New-Object System.Management.Automation.PSCredential($clientId, $secureSecret)

$token = Get-MsalToken `
    -ClientId $clientId `
    -TenantId $tenantId `
    -ClientSecret $secureSecret `
    -Scopes "https://graph.microsoft.com/.default"

Write-Host "Token obtained successfully!"
Write-Host "Expires: $($token.ExpiresOn)"
```

## Troubleshooting

### "AADSTS700016: Application not found"
- Verify the Client ID is correct
- Ensure the app registration wasn't deleted
- Check you're using the right tenant

### "AADSTS7000215: Invalid client secret"
- Client secret may have expired
- Create a new secret
- Ensure you copied the secret **Value**, not Secret ID

### "AADSTS65001: User consent required"
- Admin consent wasn't granted
- Have admin grant consent, or
- Users will see consent prompt on first use

### "Insufficient privileges"
- API permissions weren't added
- Admin consent wasn't granted
- Check permission configuration

## Next Steps

After completing this setup:

1. ✅ Configure APIM (see [APIM Setup Guide](./02-apim-setup.md))
2. ✅ Configure Foundry OAuth Connection (see [Foundry Setup Guide](./03-foundry-setup.md))
3. ✅ Deploy Functions MCP Server
4. ✅ Test the complete flow

## References

- [Microsoft identity platform documentation](https://learn.microsoft.com/entra/identity-platform/)
- [Register an application](https://learn.microsoft.com/entra/identity-platform/quickstart-register-app)
- [OAuth 2.0 authorization code flow](https://learn.microsoft.com/entra/identity-platform/v2-oauth2-auth-code-flow)
