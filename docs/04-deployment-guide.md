# Deployment Guide

This guide provides step-by-step instructions for deploying all components of the Foundry Agent V2 × OAuth Identity Passthrough MCP hands-on project to Azure.

The official front-end application is **`webapp-foundry-oauth`** (Next.js + FastAPI). It is deployed as a **single Linux App Service** with Easy Auth (Entra ID) enabled so that only authenticated users can access the app. `webapp-copilotkit` and `foundry-agui-server` are kept in the repository for reference but are not the primary deployment target.

## Prerequisites

- Azure subscription with Owner or Contributor role
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
7. Enable Easy Auth on the App Service (Entra ID login)
8. Enable Managed Identity for Foundry access

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

# Entra ID — Easy Auth app (created in Step 8; can reuse the same app registration or create a new one)
export EASY_AUTH_CLIENT_ID="your-easy-auth-client-id"
export EASY_AUTH_CLIENT_SECRET="your-easy-auth-client-secret"
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

```bash
cd functions-mcp-server

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
4. Copy Agent ID, Project ID, API Key
5. Update your `deploy.env` file

## Step 7: Deploy webapp-foundry-oauth to App Service

`webapp-foundry-oauth` contains both a **Next.js frontend** and a **FastAPI backend**. The startup script (`startup.sh`) starts both processes inside a single Linux App Service.

### 7-1. Build the Next.js Frontend Locally

```bash
cd webapp-foundry-oauth/frontend

# Install dependencies
npm install

# Build for production
npm run build

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

### 7-3. Create Web App (Node.js Runtime)

```bash
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $WEB_APP \
  --runtime "NODE:20-lts"

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
    CORS_ORIGINS="https://${WEB_APP}.azurewebsites.net" \
    WEBSITES_PORT="8080" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="false"

echo "✅ App settings configured"
```

> **Notes:**
> - `WEBSITES_PORT=8080`: Tells App Service to route inbound traffic to the Next.js process on port 8080. App Service also sets the `PORT` environment variable to this same value, which the `startup.sh` script reads.
> - `SCM_DO_BUILD_DURING_DEPLOYMENT=false`: Disables Oryx auto-build (npm install / npm build) during zip deployment, because the Next.js app is **pre-built locally** before creating the zip and the `.next` directory is included directly. This avoids a redundant build step on the server.
> - `BACKEND_URL` is intentionally omitted because the startup script runs FastAPI on `localhost:8000`, which matches the default value already used by `next.config.js`.

### 7-5. Deploy Code

```bash
# Create deployment zip (include the pre-built .next directory)
zip -r webapp.zip \
  webapp-foundry-oauth/startup.sh \
  webapp-foundry-oauth/backend \
  webapp-foundry-oauth/frontend/.next \
  webapp-foundry-oauth/frontend/public \
  webapp-foundry-oauth/frontend/package.json \
  webapp-foundry-oauth/frontend/package-lock.json \
  webapp-foundry-oauth/frontend/next.config.js

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

### 7-7. Enable Managed Identity for Foundry Access

The backend uses `DefaultAzureCredential` to call Azure AI Foundry.
Assign a System-Assigned Managed Identity and grant it the **Azure AI User** role on the Foundry project.

```bash
# Enable System-Assigned Managed Identity
az webapp identity assign \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP

# Retrieve the principal ID
PRINCIPAL_ID=$(az webapp identity show \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --query principalId \
  --output tsv)

# Get the Foundry project resource ID
# Azure AI Foundry projects use the Microsoft.MachineLearningServices/workspaces provider.
# Find your resource ID in Azure Portal: Foundry project → Properties → Resource ID.
FOUNDRY_RESOURCE_ID="/subscriptions/<subscription-id>/resourceGroups/<foundry-rg>/providers/Microsoft.MachineLearningServices/workspaces/<foundry-project>"

# Assign Azure AI User role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Azure AI User" \
  --scope $FOUNDRY_RESOURCE_ID

echo "✅ Managed Identity configured"
```

## Step 8: Enable Easy Auth (Entra ID Login)

Easy Auth adds a user-login layer in front of the App Service so that only authenticated Entra ID users can access the web app. This is separate from the OAuth Identity Passthrough used by Foundry for MCP tool calls.

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

### 8-2. Enable Easy Auth via Azure CLI

```bash
# Configure the Microsoft identity provider
az webapp auth microsoft update \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --client-id $EASY_AUTH_CLIENT_ID \
  --client-secret $EASY_AUTH_CLIENT_SECRET \
  --tenant-id $TENANT_ID \
  --yes

# Enable authentication and require login
az webapp auth update \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --enabled true \
  --action LoginWithAzureActiveDirectory

echo "✅ Easy Auth enabled"
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
```
[backend] Starting FastAPI on 127.0.0.1:8000 ...
[frontend] Starting Next.js on port 8080 ...
```

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
|-----------|---------|
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
