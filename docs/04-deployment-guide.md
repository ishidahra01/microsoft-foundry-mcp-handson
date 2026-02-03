# Deployment Guide

This guide provides step-by-step instructions for deploying all components of the CopilotKit × Foundry Agent V2 × OAuth Identity Passthrough MCP hands-on project to Azure.

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
4. Entra ID App Registration (manual)
5. Azure AI Foundry Configuration (manual)
6. Azure App Service for Web App

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

# Entra ID (will be filled after manual creation)
export TENANT_ID="your-tenant-id"
export CLIENT_ID="your-client-id"
export CLIENT_SECRET="your-client-secret"

# Foundry (will be filled after manual configuration)
export FOUNDRY_ENDPOINT="https://your-project.eastus.api.azureml.ms"
export FOUNDRY_API_KEY="your-api-key"
export FOUNDRY_AGENT_ID="your-agent-id"
export FOUNDRY_PROJECT_ID="your-project-id"
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

## Step 7: Deploy Web App

### Create App Service Plan

```bash
az appservice plan create \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku B1 \
  --is-linux

echo "✅ App Service Plan created: $APP_SERVICE_PLAN"
```

### Create Web App

```bash
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $WEB_APP \
  --runtime "NODE:18-lts"

echo "✅ Web App created: $WEB_APP"
```

### Configure App Settings

```bash
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --settings \
    FOUNDRY_ENDPOINT="$FOUNDRY_ENDPOINT" \
    FOUNDRY_API_KEY="$FOUNDRY_API_KEY" \
    FOUNDRY_AGENT_ID="$FOUNDRY_AGENT_ID" \
    FOUNDRY_PROJECT_ID="$FOUNDRY_PROJECT_ID"

echo "✅ App settings configured"
```

### Build and Deploy Web App

```bash
cd webapp-copilotkit

# Install dependencies
npm install

# Build for production
npm run build

# Create deployment package
zip -r ../webapp.zip .next package.json package-lock.json next.config.js public

cd ..

# Deploy
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --src webapp.zip

echo "✅ Web App deployed to: https://${WEB_APP}.azurewebsites.net"
```

### Configure Startup Command

```bash
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $WEB_APP \
  --startup-file "npm start"

echo "✅ Startup command configured"
```

## Step 8: Verify End-to-End Deployment

### Test Web App

```bash
curl https://${WEB_APP}.azurewebsites.net/api/copilot

# Expected: {"status":"ok","message":"CopilotKit API endpoint for Foundry Agent V2"}
```

### Open in Browser

```bash
echo "🌐 Open your web app:"
echo "https://${WEB_APP}.azurewebsites.net"
```

### Test OAuth Flow

1. Open the web app in browser
2. Type: **"Who am I?"**
3. First time: OAuth consent appears
4. Grant permissions
5. Verify your user info is displayed

## Step 9: Enable Monitoring (Optional but Recommended)

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
| Web App | `https://${WEB_APP}.azurewebsites.net` |
| Entra App | Client ID: `$CLIENT_ID` |
| Foundry Agent | Agent ID: `$FOUNDRY_AGENT_ID` |

## Cleanup

To delete all resources:

```bash
az group delete \
  --name $RESOURCE_GROUP \
  --yes \
  --no-wait

echo "🗑️ Resource group deletion initiated"
```

> **Note**: Also manually delete the Entra ID App Registration

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
