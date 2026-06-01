# Deployment Guide

This guide provides step-by-step instructions for deploying all components of the Foundry Agent V2 × OAuth Identity Passthrough MCP hands-on project to Azure.

The official front-end application is **`webapp-foundry-oauth`** (Next.js + FastAPI). It is deployed as a **single Linux App Service** with Easy Auth (Entra ID) enabled so that only authenticated users can access the app. The Next.js UI is built as a static export and served by the FastAPI backend from the same Python App Service. `webapp-copilotkit` and `foundry-agui-server` are kept in the repository for reference but are not the primary deployment target.

> **Important identity design**: The App Service backend must call Azure AI Foundry as the signed-in Easy Auth user, not as the App Service managed identity. Easy Auth must forward a user token to the backend, and each signed-in user must have a Foundry project role such as **Foundry User**. This keeps Foundry OAuth Identity Passthrough token caching aligned with the actual front-end user.

## Prerequisites

- Azure subscription with Owner or Contributor role
- Permission to create/update Entra ID App Registrations
- Permission to grant admin consent for the Easy Auth app, or access to an Entra administrator who can grant it
- Azure CLI installed and logged in (`az login`)
- Azure Functions Core Tools v4 (`npm install -g azure-functions-core-tools@4`)
- Node.js 18+ and npm
- Python 3.9+
- Git

## Overview

We'll deploy in this order:

1. Resource Group
2. Azure Functions MCP Server
3. Azure API Management
4. Entra ID App Registration for OAuth Identity Passthrough (manual)
5. Azure AI Foundry Configuration (manual)
6. Deploy webapp-foundry-oauth to Azure App Service (frontend + backend)
7. Enable Easy Auth on the App Service (Entra ID login + token store)
8. Grant signed-in users access to the Foundry project

## Step 1: Set Environment Variables

Create a file `deploy.env` (don't commit this):

```bash
# Resource names (customize as needed)
export RESOURCE_GROUP="rg-foundry-mcp-handson"
export LOCATION="eastus"
export STORAGE_ACCOUNT="stmcphandson$(date +%s)"
export FUNCTION_APP="func-mcp-handson-$(date +%s)"
export APIM_NAME="apim-foundry-mcp-$(date +%s)"
export APIM_EMAIL="your-email@example.com"
export APIM_ORG="Your Organization"
export APP_SERVICE_PLAN="asp-foundry-mcp"
export WEB_APP="webapp-mcp-handson-$(date +%s)"

# Entra ID — OAuth Identity Passthrough app (created in Step 5)
export TENANT_ID="your-tenant-id"
export CLIENT_ID="your-client-id"
export CLIENT_SECRET="your-client-secret"

# Foundry (will be filled after manual configuration)
export PROJECT_ENDPOINT="https://your-project.services.ai.azure.com/api/projects/your-project-id"
export AGENT_REFERENCE_NAME="your-agent-name"
export FOUNDRY_RESOURCE_ID="/subscriptions/<subscription-id>/resourceGroups/<foundry-rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>/projects/<foundry-project>"

# Entra ID — Easy Auth app (created in Step 8; can reuse the same app registration or create a new one)
export EASY_AUTH_CLIENT_ID="your-easy-auth-client-id"
export EASY_AUTH_CLIENT_SECRET="your-easy-auth-client-secret"

# Azure AI Foundry resource app used by Easy Auth to request a user-delegated Foundry token.
export AZURE_AI_RESOURCE_APP_ID="18a66f5f-dbdf-4c17-9dd7-1634712a9cbe"
```

Load the environment:

```bash
source deploy.env
```

## Step 2: Create Resource Group

```bash
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

echo "✅ Resource group created: $RESOURCE_GROUP"
```

## Step 3: Deploy Azure Functions MCP Server

### Create Storage Account

```bash
az storage account create \
  --name $STORAGE_ACCOUNT \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP \
  --sku Standard_LRS

echo "✅ Storage account created: $STORAGE_ACCOUNT"
```

### Create Function App

```bash
az functionapp create \
  --resource-group $RESOURCE_GROUP \
  --consumption-plan-location $LOCATION \
  --runtime python \
  --runtime-version 3.9 \
  --functions-version 4 \
  --name $FUNCTION_APP \
  --storage-account $STORAGE_ACCOUNT \
  --os-type Linux

echo "✅ Function App created: $FUNCTION_APP"
```

### Deploy Function Code

Use **`functions-mcp-selfhosted`** for the Foundry MCP tool endpoint. This implementation reads the user-delegated token from the HTTP `Authorization` header. Do not deploy `functions-mcp-server` for the OAuth Identity Passthrough path; that older implementation expects token arguments and will not match the Foundry authorization-header flow.

```bash
cd functions-mcp-selfhosted

# Install dependencies locally (for deployment package)
pip install -r requirements.txt -t .python_packages/lib/site-packages

# Deploy
func azure functionapp publish $FUNCTION_APP

cd ..

echo "✅ Functions deployed to: https://${FUNCTION_APP}.azurewebsites.net"
```

### Verify Deployment

```bash
curl https://${FUNCTION_APP}.azurewebsites.net/api/mcp/health

# Expected: {"status":"healthy","service":"MCP Server","version":"1.0.0"}
```

## Step 4: Deploy Azure API Management

> ⏱️ Note: APIM creation takes 30-45 minutes

```bash
az apim create \
  --name $APIM_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --publisher-name "$APIM_ORG" \
  --publisher-email "$APIM_EMAIL" \
  --sku-name Developer \
  --no-wait

echo "⏳ APIM creation started (this takes 30-45 minutes): $APIM_NAME"
echo "You can continue with other steps while waiting"
```

### Check APIM Creation Status

```bash
az apim show \
  --name $APIM_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "provisioningState" \
  --output tsv

# Wait until it shows "Succeeded"
```

### Import Functions API to APIM

Once APIM is created:

```bash
# Get Function App ID
FUNCTION_APP_ID=$(az functionapp show \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --query id \
  --output tsv)

# Import API
az apim api import \
  --path mcp \
  --resource-group $RESOURCE_GROUP \
  --service-name $APIM_NAME \
  --specification-format OpenApi \
  --specification-url https://${FUNCTION_APP}.azurewebsites.net/api/swagger.json \
  --display-name "MCP Server API"

echo "✅ API imported to APIM"
```

### Configure APIM Policy

Create a file `apim-policy.xml`:

```xml
<policies>
    <inbound>
        <base />
        <set-header name="Authorization" exists-action="override">
            <value>@(context.Request.Headers.GetValueOrDefault("Authorization",""))</value>
        </set-header>
        <set-header name="X-Correlation-ID" exists-action="override">
            <value>@(Guid.NewGuid().ToString())</value>
        </set-header>
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
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

Apply the policy:

```bash
az apim api operation policy create \
  --resource-group $RESOURCE_GROUP \
  --service-name $APIM_NAME \
  --api-id mcp-server-api \
  --operation-id '*' \
  --xml-policy-file apim-policy.xml

echo "✅ APIM policy configured"
```

### Verify APIM

```bash
APIM_URL="https://${APIM_NAME}.azure-api.net"
curl ${APIM_URL}/mcp/health

# Expected: {"status":"healthy","service":"MCP Server","version":"1.0.0"}
```

## Step 5: Configure Entra ID App Registration

This step is manual. Follow the guide:

**[Entra ID Setup Guide](./docs/01-entra-id-setup.md)**

After creating the app registration:

1. Copy the **Client ID**
2. Copy the **Tenant ID**
3. Copy the **Client Secret**
4. Update your `deploy.env` file with these values

## Step 6: Configure Azure AI Foundry

This step is manual. Follow the guide:

**[Foundry Setup Guide](./docs/03-foundry-setup.md)**

Key steps:

1. Create OAuth Connection with Identity Passthrough
2. Create MCP Tool pointing to APIM
3. Create Agent V2 with the tool
4. Copy the Project endpoint and Agent reference name
5. Update your `deploy.env` file

## Step 7: Deploy webapp-foundry-oauth to App Service

`webapp-foundry-oauth` contains a **Next.js frontend** and a **FastAPI backend**. For App Service deployment, the Next.js app is built as a static export (`frontend/out`) and the FastAPI backend serves both the static UI and `/api/*` endpoints from a single **Python Linux App Service**.

### 7-1. Build the Next.js Frontend Locally

```bash
cd webapp-foundry-oauth/frontend

# Install dependencies
npm install

# Build for production
npm run build

# Confirm static export exists
test -f out/index.html

cd ../..
```

### 7-2. Create App Service Plan

```bash
az appservice plan create \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku B1 \
  --is-linux

echo "✅ App Service Plan created: $APP_SERVICE_PLAN"
```

### 7-3. Create Web App (Python Runtime)

```bash
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $WEB_APP \
  --runtime "PYTHON:3.11"

echo "✅ Web App created: $WEB_APP"
```

### 7-4. Configure App Settings

```bash
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --settings \
    PROJECT_ENDPOINT="$PROJECT_ENDPOINT" \
    AGENT_REFERENCE_NAME="$AGENT_REFERENCE_NAME" \
    TENANT_ID="$TENANT_ID" \
    EASY_AUTH_CLIENT_ID="$EASY_AUTH_CLIENT_ID" \
    EASY_AUTH_CLIENT_SECRET="$EASY_AUTH_CLIENT_SECRET" \
    REQUIRE_EASY_AUTH_USER_FOR_FOUNDRY="true" \
    CORS_ORIGINS="https://${WEB_APP}.azurewebsites.net" \
    WEBSITES_PORT="8000" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="false"

echo "✅ App settings configured"
```

> **Notes:**
>
> - `REQUIRE_EASY_AUTH_USER_FOR_FOUNDRY=true` prevents falling back to the App Service managed identity when Easy Auth does not forward a user token. This avoids cross-user OAuth token reuse in Foundry.
> - `WEBSITES_PORT=8000`: The FastAPI process listens on the App Service Python container port.
> - `SCM_DO_BUILD_DURING_DEPLOYMENT=false`: Disables Oryx auto-build because the frontend is pre-built locally and included as `frontend/out`.
> - `BACKEND_URL` is not used in App Service because the static frontend and FastAPI backend are served from the same origin.

### 7-5. Deploy Code

```bash
# Create deployment zip with files at the zip root.
# The zip root must contain startup.sh, backend/, and frontend/out/.
cd webapp-foundry-oauth
zip -r ../webapp.zip \
  startup.sh \
  backend/server.py \
  backend/requirements.txt \
  frontend/out
cd ..

# Deploy
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --src webapp.zip

echo "✅ Code deployed"
```

### 7-6. Set Startup Command

```bash
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --startup-file "/bin/bash /home/site/wwwroot/startup.sh"

echo "✅ Startup command configured"
```

### 7-7. Grant Foundry Access to Signed-In Users

The backend calls Azure AI Foundry with the signed-in Easy Auth user's delegated token. Therefore, every user who signs in to the App Service and chats with the agent needs access to the Foundry project.

```bash
# Assign Foundry User to a signed-in user.
USER_OBJECT_ID=$(az ad user show \
  --id user@example.com \
  --query id \
  --output tsv)

az role assignment create \
  --assignee-object-id $USER_OBJECT_ID \
  --assignee-principal-type User \
  --role "Foundry User" \
  --scope $FOUNDRY_RESOURCE_ID

echo "✅ Foundry project access granted to user"
```

> If your tenant uses older role names, `Azure AI User` may appear instead of `Foundry User`. Use the role available in your tenant for Foundry project access.

## Step 8: Enable Easy Auth (Entra ID Login)

Easy Auth adds a user-login layer in front of the App Service so that only authenticated Entra ID users can access the web app. The backend also uses the Easy Auth user token to call Azure AI Foundry as that signed-in user. This user-scoped Foundry call is what keeps Foundry OAuth Identity Passthrough aligned with the front-end user.

### 8-1. Create an Entra ID App Registration for Easy Auth

> You can reuse the app registration created in Step 5, or create a new one dedicated to Easy Auth. A dedicated registration is recommended for clarity.

1. Go to [Azure Portal](https://portal.azure.com) → **Entra ID** → **App registrations** → **+ New registration**
2. **Name**: `webapp-foundry-oauth-easyauth` (or your preferred name)
3. **Supported account types**: *Accounts in this organizational directory only*
4. **Redirect URI**:
   - Platform: **Web**
   - URI: `https://${WEB_APP}.azurewebsites.net/.auth/login/aad/callback`
     (Replace `${WEB_APP}` with your actual App Service name)
5. Click **Register**

After registration:

- Copy **Application (client) ID** → set as `EASY_AUTH_CLIENT_ID` in `deploy.env`
- Copy **Directory (tenant) ID** → already in `TENANT_ID`
- Go to **Certificates & secrets** → create a client secret → set as `EASY_AUTH_CLIENT_SECRET` in `deploy.env`

Additional required settings:

1. Go to **Authentication** → **Implicit grant and hybrid flows**
2. Enable **ID tokens**
3. Go to **API permissions** and add a delegated permission for the Azure AI Foundry resource:

   | Field | Value |
  | ------ | ------ |
   | Resource | `https://ai.azure.com` |
   | Resource app ID | `18a66f5f-dbdf-4c17-9dd7-1634712a9cbe` |
   | Delegated permission | `user_impersonation` |

4. Grant admin consent for the tenant, or ask an Entra administrator to grant it.

If the Azure AI resource does not appear in the portal's API permission picker, discover the scope ID and add it with Azure CLI:

```bash
AZURE_AI_SCOPE_ID=$(az ad sp show \
  --id $AZURE_AI_RESOURCE_APP_ID \
  --query "oauth2PermissionScopes[?value=='user_impersonation'] | [0].id" \
  --output tsv)

az ad app permission add \
  --id $EASY_AUTH_CLIENT_ID \
  --api $AZURE_AI_RESOURCE_APP_ID \
  --api-permissions ${AZURE_AI_SCOPE_ID}=Scope

# Requires an Entra administrator role, such as Global Administrator,
# Privileged Role Administrator, or Cloud Application Administrator.
az ad app permission admin-consent \
  --id $EASY_AUTH_CLIENT_ID
```

> `az ad app permission admin-consent` requires Entra administrator privileges. Azure subscription Owner or Contributor is not sufficient.

### 8-2. Enable Easy Auth via Azure CLI

```bash
# Configure Easy Auth classic with the Microsoft identity provider.
az webapp auth-classic update \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --enabled true \
  --action LoginWithAzureActiveDirectory \
  --aad-client-id $EASY_AUTH_CLIENT_ID \
  --aad-client-secret $EASY_AUTH_CLIENT_SECRET \
  --aad-token-issuer-url "https://sts.windows.net/${TENANT_ID}/" \
  --token-store true

# Ask Easy Auth to acquire and store an Azure AI Foundry user token.
# This makes x-ms-token-aad-access-token available to the FastAPI backend.
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
AUTH_ID="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Web/sites/${WEB_APP}/config/authsettings"

az resource show \
  --ids $AUTH_ID \
  --api-version 2022-03-01 \
  --output json > authsettings-current.json

python - <<'PY'
import json

with open("authsettings-current.json", "r", encoding="utf-8") as f:
    auth = json.load(f)

auth.setdefault("properties", {})["additionalLoginParams"] = ["resource=https://ai.azure.com"]
auth["properties"]["tokenStoreEnabled"] = True

with open("authsettings-updated.json", "w", encoding="utf-8") as f:
    json.dump(auth, f, indent=2)
PY

az rest \
  --method PUT \
  --uri "https://management.azure.com${AUTH_ID}?api-version=2022-03-01" \
  --body @authsettings-updated.json \
  --headers "Content-Type=application/json"

az webapp restart \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP

echo "✅ Easy Auth enabled"
```

Verify the Easy Auth settings:

```bash
az webapp auth-classic show \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --query "{tokenStoreEnabled:tokenStoreEnabled,additionalLoginParams:additionalLoginParams,action:unauthenticatedClientAction}" \
  --output json

# Expected:
# tokenStoreEnabled: true
# additionalLoginParams: ["resource=https://ai.azure.com"]
# action: RedirectToLoginPage
```

### 8-3. (Optional) Enable Easy Auth via Azure Portal

If you prefer the portal wizard:

1. Go to your App Service → **Settings** → **Authentication**
2. Click **Add identity provider**
3. Select **Microsoft**
4. Choose *Provide the details of an existing app registration*
5. Enter **App (client) ID** and **Client Secret**
6. Set **Unauthenticated requests** to **HTTP 302 Redirect: Recommended for websites**
7. Click **Add**

After using the portal wizard, still run the `authsettings` update from Step 8-2 to enable token store and set `resource=https://ai.azure.com`. The portal wizard does not expose all required settings for this hands-on.

## Step 9: Verify End-to-End Deployment

### Test Web App

```bash
echo "🌐 Open your web app:"
echo "https://${WEB_APP}.azurewebsites.net"
```

1. Open the URL — you should be redirected to Microsoft login (Easy Auth)
2. Sign in with your Entra ID account
3. After login, the chat UI appears
4. Type: **"Who am I?"**
5. The first time, an OAuth consent card appears (Foundry OAuth Identity Passthrough for Graph API)
6. Grant permissions → the agent resumes → your user info is displayed

### Check App Service Logs

```bash
az webapp log tail \
  --name $WEB_APP \
  --resource-group $RESOURCE_GROUP
```

Look for:

```text
[backend] Starting FastAPI on 0.0.0.0:8000 ...
Uvicorn running on http://0.0.0.0:8000
```

### Verify User Isolation

Test with two different Entra ID users:

1. Open the web app with user A and ask **"Who am I?"**
2. Complete the Foundry OAuth consent flow if prompted
3. Open a private browser session with user B and ask **"Who am I?"**
4. User B should either see a separate consent prompt or receive user B's Graph profile

If user B receives user A's profile, verify:

- App Service `REQUIRE_EASY_AUTH_USER_FOR_FOUNDRY=true`
- Easy Auth token store is enabled
- Easy Auth `additionalLoginParams` includes `resource=https://ai.azure.com`
- Both users have a Foundry project role such as `Foundry User`

### Verify Environment Variables

```bash
az webapp config appsettings list \
  --name $WEB_APP \
  --resource-group $RESOURCE_GROUP
```

## Step 10: Enable Monitoring (Optional but Recommended)

### Create Application Insights

```bash
az monitor app-insights component create \
  --app ${WEB_APP}-insights \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP

# Get instrumentation key
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
  --app ${WEB_APP}-insights \
  --resource-group $RESOURCE_GROUP \
  --query instrumentationKey \
  --output tsv)

# Configure Function App
az functionapp config appsettings set \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --settings "APPINSIGHTS_INSTRUMENTATIONKEY=$INSTRUMENTATION_KEY"

# Configure Web App
az webapp config appsettings set \
  --name $WEB_APP \
  --resource-group $RESOURCE_GROUP \
  --settings "APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=$INSTRUMENTATION_KEY"

echo "✅ Application Insights enabled"
```

## Deployment Summary

After successful deployment:

| Component | URL/ID |
| --------- | ------ |
| Resource Group | `$RESOURCE_GROUP` |
| Functions MCP | `https://${FUNCTION_APP}.azurewebsites.net` |
| APIM Gateway | `https://${APIM_NAME}.azure-api.net` |
| Web App (webapp-foundry-oauth) | `https://${WEB_APP}.azurewebsites.net` |
| Entra App (OAuth Identity Passthrough) | Client ID: `$CLIENT_ID` |
| Entra App (Easy Auth) | Client ID: `$EASY_AUTH_CLIENT_ID` |
| Foundry Agent | Agent Reference: `$AGENT_REFERENCE_NAME` |

## Cleanup

To delete all resources:

```bash
az group delete \
  --name $RESOURCE_GROUP \
  --yes \
  --no-wait

echo "🗑️ Resource group deletion initiated"
```

> **Note**: Also manually delete both Entra ID App Registrations (OAuth Identity Passthrough and Easy Auth)

## Troubleshooting Deployment

### Functions deployment fails

```bash
# Check deployment logs
az functionapp log deployment show \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP

# Restart function app
az functionapp restart \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP
```

### Web App not starting

```bash
# Check logs
az webapp log tail \
  --name $WEB_APP \
  --resource-group $RESOURCE_GROUP

# Verify environment variables
az webapp config appsettings list \
  --name $WEB_APP \
  --resource-group $RESOURCE_GROUP
```

### Chat returns "Easy Auth user token was not forwarded"

The backend did not receive `x-ms-token-aad-access-token` from Easy Auth. This usually means token store or the Azure AI resource login parameter is missing, or the user is still using an old Easy Auth session.

Check Easy Auth settings:

```bash
az webapp auth-classic show \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --query "{tokenStoreEnabled:tokenStoreEnabled,additionalLoginParams:additionalLoginParams}" \
  --output json
```

Expected:

```json
{
  "tokenStoreEnabled": true,
  "additionalLoginParams": [
    "resource=https://ai.azure.com"
  ]
}
```

After changing Easy Auth settings, sign out and sign in again:

```text
https://${WEB_APP}.azurewebsites.net/.auth/logout
```

### Login callback fails with AADSTS650057 invalid resource

This means the Easy Auth App Registration is requesting a token for `https://ai.azure.com`, but that resource is not listed in the app registration API permissions.

Relevant values:

| Field | Value |
| ------ | ------ |
| Resource | `https://ai.azure.com` |
| Resource app ID | `18a66f5f-dbdf-4c17-9dd7-1634712a9cbe` |
| Delegated permission | `user_impersonation` |

Add the delegated permission to the Easy Auth app and grant admin consent. If `az ad` commands fail with `TokenCreatedWithOutdatedPolicies`, run `az logout` and sign in again with Graph scope:

```bash
az logout
az login --tenant $TENANT_ID --scope https://graph.microsoft.com/.default
```

### Chat returns Foundry API HTTP 403

The signed-in user can authenticate to App Service, but does not have access to the Foundry project. Grant the user a project role:

```bash
USER_OBJECT_ID=$(az ad user show \
  --id user@example.com \
  --query id \
  --output tsv)

az role assignment create \
  --assignee-object-id $USER_OBJECT_ID \
  --assignee-principal-type User \
  --role "Foundry User" \
  --scope $FOUNDRY_RESOURCE_ID
```

RBAC propagation can take a few minutes. Ask the user to sign out and sign in again after the assignment.

### APIM creation timeout

- APIM creation can take up to 60 minutes
- Check Azure status page for service issues
- Verify you have sufficient quota

## CI/CD Setup (Optional)

For automated deployments, see:

- [GitHub Actions for Functions](https://learn.microsoft.com/azure/azure-functions/functions-how-to-github-actions)
- [GitHub Actions for App Service](https://learn.microsoft.com/azure/app-service/deploy-github-actions)

## Next Steps

- Configure custom domain names
- Set up SSL certificates
- Implement monitoring and alerting
- Review security best practices
- Plan for production enhancements

## References

- [Azure CLI Reference](https://learn.microsoft.com/cli/azure/)
- [Azure Functions Deployment](https://learn.microsoft.com/azure/azure-functions/functions-deployment-technologies)
- [App Service Deployment](https://learn.microsoft.com/azure/app-service/deploy-best-practices)
