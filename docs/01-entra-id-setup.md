# Entra ID App Registration Setup Guide

This guide walks through creating an Entra ID App Registration for use with Azure AI Foundry OAuth Identity Passthrough.

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
- **Redirect URI**: 
  - Select **Web**
  - Enter: `https://login.microsoftonline.com/common/oauth2/nativeclient`
  - (This is a standard redirect URI for OAuth flows)

5. Click **Register**

## Step 2: Note Application IDs

After creation, you'll see the overview page. **Save these values**:

- **Application (client) ID**: `12345678-1234-1234-1234-123456789012`
- **Directory (tenant) ID**: `87654321-4321-4321-4321-210987654321`

## Step 3: Create Client Secret

1. In the left menu, click **Certificates & secrets**
2. Click **+ New client secret**
3. Enter a description: `Foundry OAuth Secret`
4. Select expiration period: `24 months` (or as per your policy)
5. Click **Add**
6. **IMPORTANT**: Copy the secret **Value** immediately (not the Secret ID)
   - Format: `abc123def456...`
   - ⚠️ This value is only shown once!

## Step 4: Configure API Permissions

### Add Microsoft Graph Permissions

1. In the left menu, click **API permissions**
2. Click **+ Add a permission**
3. Select **Microsoft Graph**
4. Select **Delegated permissions**
5. Search and add these permissions:
   - **User.Read** - Read user profile
   
6. Click **Add permissions**

### Grant Admin Consent (Optional but Recommended)

1. Click **Grant admin consent for [Your Organization]**
2. Click **Yes** to confirm
3. Status should change to **Granted**

> If you don't grant admin consent, users will see a consent prompt on first use.

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
