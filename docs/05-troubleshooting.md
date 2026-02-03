# Troubleshooting Guide

This guide provides solutions to common issues you might encounter when setting up or running the CopilotKit × Foundry Agent V2 × OAuth Identity Passthrough MCP hands-on project.

## Table of Contents

1. [General Issues](#general-issues)
2. [Azure Functions MCP Server](#azure-functions-mcp-server)
3. [Azure API Management](#azure-api-management)
4. [Entra ID & OAuth](#entra-id--oauth)
5. [Azure AI Foundry](#azure-ai-foundry)
6. [Web App](#web-app)
7. [End-to-End Flow](#end-to-end-flow)
8. [Performance Issues](#performance-issues)

---

## General Issues

### Cannot access Azure Portal

**Symptoms**: "Access Denied" or "Unauthorized"

**Solutions**:
1. Verify you're logged into the correct Azure tenant
2. Check you have appropriate permissions (Contributor or Owner role)
3. Clear browser cache and cookies
4. Try incognito/private browsing mode

### Azure CLI not authenticated

**Symptoms**: `az` commands fail with authentication errors

**Solutions**:
```bash
# Re-login to Azure CLI
az login

# Verify current account
az account show

# Switch to correct subscription
az account set --subscription "Your Subscription Name"
```

---

## Azure Functions MCP Server

### Function App not responding

**Symptoms**: `curl` to function endpoints times out or returns 500

**Check 1: Function App is running**
```bash
az functionapp show \
  --name <function-app-name> \
  --resource-group <resource-group> \
  --query "state" \
  --output tsv

# Should show: Running
```

**Check 2: View logs**
```bash
az functionapp log tail \
  --name <function-app-name> \
  --resource-group <resource-group>
```

**Check 3: Restart Function App**
```bash
az functionapp restart \
  --name <function-app-name> \
  --resource-group <resource-group>
```

### "ModuleNotFoundError: No module named 'requests'"

**Symptoms**: Function logs show Python import errors

**Solution**: Ensure requirements.txt is properly deployed
```bash
cd functions-mcp-server

# Install dependencies locally
pip install -r requirements.txt

# Re-deploy
func azure functionapp publish <function-app-name>
```

### "Authorization header not found" even when provided

**Symptoms**: MCP server logs "no_token" status

**Check 1: APIM is forwarding headers**
- Verify APIM inbound policy has `set-header` for Authorization
- Check APIM trace logs (Portal → API → Test → Trace)

**Check 2: Test directly to Functions**
```bash
curl -X POST https://<function-app>.azurewebsites.net/api/mcp/whoami \
  -H "Authorization: Bearer test123" \
  -H "Content-Type: application/json"

# Should see token in response even if Graph call fails
```

### Microsoft Graph API returns 401

**Symptoms**: `whoami` tool logs "Graph API call failed: 401"

**Possible causes**:
1. Token is invalid or expired
2. Token doesn't have `User.Read` scope
3. Token is for wrong audience

**Solution**: Verify token scopes using jwt.ms
```bash
# Decode token (copy from logs)
# Go to https://jwt.ms/ and paste token
# Check "scp" or "roles" claim includes "User.Read"
```

---

## Azure API Management

### APIM returns 404 "Resource not found"

**Symptoms**: APIM gateway URL returns 404

**Check 1: API is imported**
```bash
az apim api list \
  --resource-group <resource-group> \
  --service-name <apim-name> \
  --output table
```

**Check 2: Correct URL path**
- APIM URL should be: `https://<apim-name>.azure-api.net/mcp/health`
- Not: `https://<apim-name>.azure-api.net/api/mcp/health`

**Check 3: API is published**
- In Azure Portal, go to APIM → APIs → MCP Server API
- Ensure it's added to a Product (e.g., "Unlimited")

### APIM returns 401 "Access denied"

**Symptoms**: "Access denied due to missing subscription key"

**Solution 1: Disable subscription requirement**
1. Go to APIM → APIs → MCP Server API → Settings
2. Uncheck "Subscription required"
3. Save

**Solution 2: Use subscription key**
```bash
# Get subscription key
az apim subscription show \
  --name unlimited \
  --resource-group <resource-group> \
  --service-name <apim-name> \
  --query "primaryKey" \
  --output tsv

# Use in request
curl https://<apim-name>.azure-api.net/mcp/health \
  -H "Ocp-Apim-Subscription-Key: <subscription-key>"
```

### APIM creation stuck at "Creating"

**Symptoms**: APIM shows "Creating" status for over 60 minutes

**Solutions**:
1. Check Azure status page for known issues
2. Verify you have sufficient quota in the subscription
3. Try different region
4. Contact Azure support if persists beyond 90 minutes

### Authorization header not reaching Functions

**Symptoms**: Functions logs show no token, but token is sent to APIM

**Check APIM policy**:
```xml
<!-- This should be in Inbound processing -->
<set-header name="Authorization" exists-action="override">
    <value>@(context.Request.Headers.GetValueOrDefault("Authorization",""))</value>
</set-header>
```

**Test with APIM Test Console**:
1. Portal → APIM → APIs → MCP Server API → Test
2. Select POST /whoami operation
3. Add header: `Authorization: Bearer test123`
4. Send request
5. Check "Backend" tab in trace to see headers sent to Functions

---

## Entra ID & OAuth

### "AADSTS700016: Application not found"

**Symptoms**: OAuth flow fails with this error

**Solutions**:
1. Verify Client ID is correct (no extra spaces/characters)
2. Check app registration hasn't been deleted
3. Ensure using correct tenant ID in URLs

### "AADSTS7000215: Invalid client secret"

**Symptoms**: Token request fails with invalid secret

**Solutions**:
1. Client secret may have expired - create new one
2. Ensure you copied the secret **Value**, not Secret ID
3. Check for extra spaces when pasting secret

### "AADSTS65001: User consent required"

**Symptoms**: Every request prompts for consent

**This is expected behavior** when:
- Admin consent hasn't been granted
- User hasn't consented yet
- Token has expired

**To avoid repeated prompts**:
- Grant admin consent in Entra ID app registration
- Or users consent once, then token is cached

### "AADSTS50105: The signed in user is not assigned to a role"

**Symptoms**: User can't complete OAuth flow

**Solution**: Grant User.Read permission
1. Entra ID → App registrations → Your App
2. API permissions → Add Microsoft Graph → User.Read
3. Grant admin consent

### Token doesn't have expected scopes

**Symptoms**: Graph API returns 403 "Insufficient privileges"

**Check token scopes**:
```bash
# Use jwt.ms to decode token
# Check "scp" claim for scopes
# Should include: "User.Read"
```

**Solution**: Update scope in Foundry OAuth connection
```
Scope: https://graph.microsoft.com/.default
```

---

## Azure AI Foundry

### Cannot create OAuth connection

**Symptoms**: Error when saving OAuth connection in Foundry

**Check 1: All fields filled**
- Client ID
- Client Secret
- Authorization URL (with tenant ID)
- Token URL (with tenant ID)
- Scope

**Check 2: URLs are correct**
```
Authorization URL: https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize
Token URL: https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token
```

### MCP Tool test fails

**Symptoms**: Tool test returns error or timeout

**Check 1: APIM endpoint is accessible**
```bash
curl https://<apim-name>.azure-api.net/mcp/health
```

**Check 2: OAuth connection is valid**
- Test OAuth connection separately in Foundry
- Check it can obtain tokens

**Check 3: Identity Passthrough is enabled**
- OAuth Connection settings → Enable Identity Passthrough: ON

### Agent doesn't call MCP tool

**Symptoms**: Agent responds without using tool, even when appropriate

**Check 1: Tool is enabled for agent**
- Agent configuration → Tools → Verify tool is checked

**Check 2: Agent instructions mention the tool**
```markdown
When user asks about their identity, use the whoami_tool.
```

**Check 3: Try explicit prompt**
```
User: Use the whoami tool to get my information
```

### "Agent execution failed"

**Symptoms**: Agent shows error instead of response

**Check logs**:
1. Foundry Portal → Agent → Runs/History
2. Look for specific error message
3. Check if MCP tool call succeeded

**Common causes**:
- MCP endpoint unreachable
- OAuth token expired
- Tool response format invalid

### OAuth consent doesn't appear

**Symptoms**: Tool fails immediately without showing consent

**Solutions**:
1. Verify Identity Passthrough is enabled
2. Clear browser cache and try incognito mode
3. Check Entra ID redirect URIs are configured
4. Try with different user account

---

## Web App

### "Missing Foundry configuration" error

**Symptoms**: Web app shows error about missing configuration

**Check environment variables**:
```bash
# For local development (.env.local)
cat .env.local

# For Azure App Service
az webapp config appsettings list \
  --name <webapp-name> \
  --resource-group <resource-group>
```

**Required variables**:
- `FOUNDRY_ENDPOINT`
- `FOUNDRY_API_KEY`
- `FOUNDRY_AGENT_ID`
- `FOUNDRY_PROJECT_ID`

**Solution**: Set missing variables
```bash
# Local
cp .env.local.template .env.local
# Edit .env.local

# Azure
az webapp config appsettings set \
  --name <webapp-name> \
  --resource-group <resource-group> \
  --settings \
    FOUNDRY_ENDPOINT="https://..." \
    FOUNDRY_API_KEY="..."
```

### "Failed to create thread" error

**Symptoms**: Chat fails immediately with thread creation error

**Check 1: Foundry endpoint is correct**
```bash
# Test endpoint manually
curl -X POST https://<project>.eastus.api.azureml.ms/agents/v2/threads \
  -H "api-key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Check 2: API key is valid**
- Go to Foundry Portal → Project Settings → Keys
- Verify key hasn't been regenerated
- Try with alternate key

**Check 3: Project exists and is active**
- Verify project is not deleted or suspended

### Web app doesn't start on Azure

**Symptoms**: App Service shows "Application Error"

**Check logs**:
```bash
az webapp log tail \
  --name <webapp-name> \
  --resource-group <resource-group>
```

**Common issues**:
1. **Missing node_modules**: Ensure dependencies are in deployment package
2. **Wrong startup command**: Should be `npm start`
3. **Port binding**: Next.js should listen on `PORT` env var

**Solution**: Verify deployment
```bash
# Check deployment logs
az webapp log deployment show \
  --name <webapp-name> \
  --resource-group <resource-group>

# Set startup command
az webapp config set \
  --name <webapp-name> \
  --resource-group <resource-group> \
  --startup-file "npm start"
```

### CopilotKit UI not displaying

**Symptoms**: Page loads but chat interface is missing

**Check browser console**:
- Open DevTools (F12)
- Look for React errors
- Check network requests for failures

**Solution**: Rebuild web app
```bash
cd webapp-copilotkit
rm -rf .next node_modules
npm install
npm run build
```

---

## End-to-End Flow

### OAuth consent shows wrong app name

**Symptoms**: Consent screen shows unexpected app name

**This is normal**: The consent screen shows the Entra ID app name
- Not the Foundry agent name
- Not the web app name

**To customize**: Update app name in Entra ID
1. App registration → Branding & properties
2. Change "Name"
3. Save

### User info returned is for different user

**Symptoms**: whoami returns someone else's info

**This should NOT happen** if Identity Passthrough is working correctly

**Check**:
1. Verify Identity Passthrough is enabled
2. Check user is signed into correct account
3. Clear all tokens and re-authenticate
4. Check Function logs for token preview (should be different per user)

### Tool returns cached/stale data

**Symptoms**: User info doesn't reflect recent changes

**This is expected**: Microsoft Graph may cache data

**Solution**: Wait a few minutes and try again

### Second request doesn't require consent

**Symptoms**: First request shows consent, second doesn't

**This is correct behavior!**: Token is cached by Foundry
- Tokens are valid for ~1 hour
- Refresh tokens allow longer sessions
- This proves OAuth is working correctly

---

## Performance Issues

### Agent responses are slow

**Typical response times**:
- Simple query: 2-5 seconds
- With MCP tool call: 5-10 seconds
- Complex multi-tool: 15-30 seconds

**If slower than this**:

**Check 1: Model deployment**
- Some models are slower than others
- Consider using GPT-3.5-turbo for faster responses

**Check 2: APIM latency**
```bash
# Check APIM analytics
# Portal → APIM → Analytics
# Look for high latency operations
```

**Check 3: Function cold start**
- Functions on Consumption plan have cold starts (~5-10s)
- Consider using Premium plan for faster starts

### High memory usage in Functions

**Symptoms**: Function app crashes or restarts frequently

**Solutions**:
1. **Scale up**: Switch to higher tier plan
2. **Optimize code**: Reduce memory allocations
3. **Add monitoring**: Track memory usage over time

### Web app is slow to load

**Check**:
1. Next.js build is optimized (`npm run build`)
2. App Service plan has adequate resources
3. CDN is configured for static assets (optional)

---

## Getting More Help

### Enable detailed logging

**Functions**:
```bash
# Set logging level
az functionapp config appsettings set \
  --name <function-app> \
  --resource-group <resource-group> \
  --settings "FUNCTIONS_WORKER_PROCESS_COUNT=1" \
              "AzureWebJobsSecretStorageType=files"
```

**APIM**:
```bash
# Enable verbose tracing
# Portal → APIM → APIs → Settings
# Enable "Verbose" logging
```

**Web App**:
```bash
# Enable detailed errors
az webapp config set \
  --name <webapp-name> \
  --resource-group <resource-group> \
  --detailed-error-messages true
```

### Use Application Insights

Query examples:

**Function errors**:
```kusto
exceptions
| where cloud_RoleName contains "func-mcp"
| where timestamp > ago(1h)
| project timestamp, message, outerMessage
| order by timestamp desc
```

**APIM requests**:
```kusto
requests
| where url contains "apim"
| where timestamp > ago(1h)
| summarize count() by resultCode, url
```

**Web app errors**:
```kusto
traces
| where cloud_RoleName contains "webapp"
| where severityLevel >= 3
| where timestamp > ago(1h)
| order by timestamp desc
```

### Still stuck?

1. **Check Azure Status**: https://status.azure.com/
2. **Review documentation**: Links in main README
3. **Create GitHub Issue**: Include logs and error messages
4. **Azure Support**: For Azure-specific issues

---

## Common Pitfalls to Avoid

1. ❌ Forgetting to enable Identity Passthrough
2. ❌ Using wrong token URL format
3. ❌ Not granting Microsoft Graph permissions
4. ❌ Mixing up Client ID and Object ID
5. ❌ Copying secret ID instead of secret value
6. ❌ Not updating environment variables after changes
7. ❌ Testing with expired tokens
8. ❌ Forgetting to restart services after configuration changes
9. ❌ Not checking logs when troubleshooting
10. ❌ Assuming errors are in one component without checking the full flow

---

## Prevention Tips

1. ✅ Always test components individually before integration
2. ✅ Keep track of all IDs and secrets in a secure place
3. ✅ Use descriptive names for all Azure resources
4. ✅ Enable monitoring from the start
5. ✅ Document any customizations you make
6. ✅ Test OAuth flow in incognito mode
7. ✅ Verify tokens using jwt.ms during development
8. ✅ Check logs at each layer (Web → Foundry → APIM → Functions)
9. ✅ Have a rollback plan before making changes
10. ✅ Test with multiple user accounts

---

Remember: Most issues are configuration-related. Double-check all settings before assuming a bug!
