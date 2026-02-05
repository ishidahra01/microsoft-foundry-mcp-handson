# CopilotKit × Foundry Agent (V2) × OAuth Identity Passthrough MCP - Hands-on

[Japanese follows English / 日本語は英語の後にあります]

This repository contains a complete hands-on implementation of a chat application using **CopilotKit UI** connected to **Azure AI Foundry Agent V2 API** with **OAuth Identity Passthrough** to an **MCP Server** running on Azure Functions.

## 🎯 Purpose

Demonstrate how to:
- Build a modern chat UI with CopilotKit
- Connect to Azure AI Foundry Agent V2 API (Threads/Runs/Messages model)
- Implement OAuth Identity Passthrough for user-delegated API access
- Create an MCP server that receives user tokens
- Call Microsoft Graph API on behalf of authenticated users

> ⚠️ **Note**: This is a hands-on/demonstration project. Security enhancements like JWT validation in APIM are intentionally omitted for simplicity.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          User's Browser                          │
│                     (Web App / CopilotKit UI)                    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Chat Messages
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Azure App Service (Node.js)                    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CopilotKit Server (/api/copilot)                       │   │
│  │  - Manages chat sessions                                 │   │
│  │  - Calls Foundry Agent V2 API                           │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Foundry Agent API (V2)
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Azure AI Foundry Agent (V2)                     │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────────────────────┐   │
│  │  Agent           │  │  OAuth Identity Passthrough       │   │
│  │  - Instructions  │  │  - User consent (first time)      │   │
│  │  - Model         │  │  - Delegated access token         │   │
│  │  - MCP Tools     │  │  - Token refresh                  │   │
│  └──────────────────┘  └──────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Authorization: Bearer <user-token>
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│              Azure API Management (APIM)                         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Inbound Policy                                          │   │
│  │  - Forward Authorization header                          │   │
│  │  - No JWT validation (hands-on)                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Forward token
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│           Azure Functions (Python) - MCP Server                  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  MCP Tool: whoami                                        │   │
│  │  - Receive Authorization header                          │   │
│  │  - Extract user token                                    │   │
│  │  - Call Microsoft Graph API /me                         │   │
│  │  - Return user information                               │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Authorization: Bearer <user-token>
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Microsoft Graph API                           │
│                    GET /v1.0/me                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 Components

### 1. Web App (webapp-copilotkit/)
- **Framework**: Next.js 14 with TypeScript
- **UI**: CopilotKit for chat interface
- **API**: `/api/copilot` endpoint that calls Foundry Agent V2
- **Features**:
  - Modern chat UI
  - Session management
  - Streaming support (via CopilotKit)

### 2. Azure Functions MCP Server (functions-mcp-server/)
- **Runtime**: Python 3.12+
- **Framework**: Azure Functions v4
- **MCP Tools**:
  - `whoami` - Get current user info from Graph API
  - `tools` - List available tools
  - `health` - Health check
- **Features**:
  - Receives user-delegated OAuth tokens
  - Calls Microsoft Graph API
  - No token validation (hands-on mode)

### 3. Azure Resources
- **Azure AI Foundry**: Agent V2 with OAuth connection
- **Azure API Management**: Gateway for MCP server
- **Azure App Service**: Hosts the web app
- **Entra ID**: App registration for OAuth

## 📚 Documentation

Detailed setup guides:

1. **[Entra ID App Registration](./docs/01-entra-id-setup.md)**
   - Create app registration
   - Configure OAuth settings
   - Set up Microsoft Graph permissions

2. **[APIM Setup](./docs/02-apim-setup.md)**
   - Create APIM instance
   - Import Functions API
   - Configure passthrough policies

3. **[Foundry Setup](./docs/03-foundry-setup.md)**
   - Create OAuth connection with Identity Passthrough
   - Configure MCP tool
   - Create Agent V2

Component-specific documentation:

- **[Functions MCP Server README](./functions-mcp-server/README.md)**
- **[Web App README](./webapp-copilotkit/README.md)**

## 🚀 Quick Start

### Prerequisites

- Azure subscription
- Node.js 20+
- Python 3.12+
- Azure CLI
- Azure Functions Core Tools

### 1. Clone Repository

```bash
git clone https://github.com/ishidahra01/microsoft-foundry-mcp-handson.git
cd microsoft-foundry-mcp-handson
```

### 2. Deploy Azure Functions MCP Server

#### Option A: Use the provided deployment script (hands-on, relaxed settings)

```powershell
cd functions-mcp-server

# Install dependencies
pip install -r requirements.txt

# Test locally (optional)
func start

# Deploy to Azure (storage/network settings are relaxed for hands-on)
..\scripts\deploy-functions.ps1
```

This script will:
- Create a resource group (default: `rg-ms-foundry-mcp`) if it does not exist
- Create a Storage Account with standard settings (no network ACL `Deny`)
- Create a Blob container `mcp-data`
- Create a Function App with a unique name and publish the code

> ⚠️ **Security note (hands-on only)**: The script does **not** lock down Storage Account network access. This is intentional for the hands-on to avoid 403 errors when Azure Functions creates required file shares. For production, tighten network rules and shared key access according to your governance.

The script will print the generated Function App name (for example, `func-mcp-server-123456`). Use that name/URL in subsequent steps (APIM import, Foundry configuration, etc.).

#### Option B: Manual deployment with Azure CLI

```bash
cd functions-mcp-server

# Install dependencies
pip install -r requirements.txt

# Test locally
func start

# Create resource group (once)
az group create \
  --name rg-foundry-mcp \
  --location eastus

# Create storage account for the Function App (once)
az storage account create \
  --name stmcpserver \
  --resource-group rg-foundry-mcp \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-shared-key-access true \

# (Optional) Create a Blob container
az storage container create \
  --name mcp-data \
  --account-name stmcpserver \
  --auth-mode login

# Deploy to Azure
az functionapp create \
  --resource-group rg-foundry-mcp \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name func-mcp-server-unique \
  --storage-account stmcpserver

func azure functionapp publish func-mcp-server-unique
```

### 3. Set Up Azure Resources

Follow the detailed guides:

1. [Create Entra ID App Registration](./docs/01-entra-id-setup.md)
2. [Set up APIM](./docs/02-apim-setup.md)
3. [Configure Foundry Agent](./docs/03-foundry-setup.md)

### 4. Deploy Web App

```bash
cd webapp-copilotkit

# Install dependencies
npm install

# Configure environment
cp .env.local.template .env.local
# Edit .env.local with your values

# Test locally
npm run dev
# Open http://localhost:3000

# Build for production
npm run build

# Deploy to Azure App Service
az webapp create \
  --resource-group rg-foundry-mcp \
  --plan asp-foundry-mcp \
  --name webapp-mcp-handson-unique \
  --runtime "NODE:20-lts"

# Configure app settings
az webapp config appsettings set \
  --resource-group rg-foundry-mcp \
  --name webapp-mcp-handson-unique \
  --settings \
    FOUNDRY_ENDPOINT="https://your-project.eastus.api.azureml.ms" \
    FOUNDRY_API_KEY="your-api-key" \
    FOUNDRY_AGENT_ID="your-agent-id" \
    FOUNDRY_PROJECT_ID="your-project-id"

# Deploy (ZIP deployment)
npm run build
zip -r app.zip .next package.json package-lock.json next.config.js
az webapp deployment source config-zip \
  --resource-group rg-foundry-mcp \
  --name webapp-mcp-handson-unique \
  --src app.zip
```

### 5. Test End-to-End

1. Access your web app: `https://webapp-mcp-handson-unique.azurewebsites.net`
2. Type in the chat: **"Who am I?"**
3. **First time**: OAuth consent screen appears (via Foundry)
   - Sign in with your Microsoft account
   - Grant permission to read your profile
4. Agent calls the `whoami_tool` via APIM
5. MCP server receives your delegated token
6. MCP server calls Microsoft Graph API `/me`
7. Your user information is returned in the chat!

## 🧪 Verification Steps

### Check 1: Web App is Running

```bash
curl https://webapp-mcp-handson-unique.azurewebsites.net/api/copilot
```

Expected: `{"status":"ok","message":"CopilotKit API endpoint for Foundry Agent V2"}`

### Check 2: Functions MCP Server

```bash
curl https://func-mcp-server-unique.azurewebsites.net/api/mcp/health
```

Expected: `{"status":"healthy","service":"MCP Server","version":"1.0.0"}`

### Check 3: APIM Gateway

```bash
curl https://apim-foundry-mcp-handson.azure-api.net/mcp/health
```

Expected: Same as Functions health response

### Check 4: OAuth Flow

1. Open web app
2. Send message: "Who am I?"
3. Check browser console for any errors
4. Verify OAuth consent appears (first time)
5. After consent, verify user info is displayed

### Check 5: Token is Passed

Check Functions logs:

```bash
az monitor app-insights logs query \
  --app your-app-insights \
  --analytics-query "traces | where message contains 'Token status' | top 10 by timestamp desc"
```

Look for: `Token status: present, preview: eyJ0eXAiOi..., length: 1234`

## 🔍 Troubleshooting

### Web App Issues

**Problem**: "Missing Foundry configuration"
- **Solution**: Check `.env.local` or App Service app settings

**Problem**: "Failed to create thread"
- **Solution**: Verify Foundry endpoint and API key

### OAuth Issues

**Problem**: OAuth consent doesn't appear
- **Solution**: 
  - Verify Identity Passthrough is enabled in Foundry OAuth connection
  - Check Entra ID app registration redirect URIs
  - Try in incognito/private browser window

**Problem**: "AADSTS700016: Application not found"
- **Solution**: Verify Client ID in OAuth connection matches Entra ID app

### MCP Server Issues

**Problem**: "No authorization token provided"
- **Solution**:
  - Check APIM policy forwards Authorization header
  - Verify OAuth connection is attached to MCP tool in Foundry
  - Ensure Identity Passthrough is enabled

**Problem**: Graph API call fails
- **Solution**:
  - Verify token has `User.Read` scope
  - Check token hasn't expired
  - Test token manually with Graph Explorer

### APIM Issues

**Problem**: APIM returns 404
- **Solution**: 
  - Verify API URL suffix is `/mcp`
  - Check operations are correctly imported
  - Ensure API is published

**Problem**: APIM returns 401
- **Solution**:
  - If subscription key is required, provide it
  - Or disable subscription requirement in API settings

## ⚠️ Security Notes

### Current Implementation (Hands-on Mode)

This implementation is simplified for hands-on purposes:

- ❌ **No JWT validation in APIM** - Tokens are not verified
- ❌ **No audience checks** - Any valid Microsoft token is accepted
- ❌ **No rate limiting** - Only default APIM limits apply
- ❌ **Token logging** - Token preview is logged for debugging
- ❌ **No private endpoints** - Services are publicly accessible

### Production Enhancements (Future Issue)

For production, implement:

1. **JWT Validation in APIM**:
   ```xml
   <validate-jwt header-name="Authorization">
       <openid-config url="https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration" />
       <required-claims>
           <claim name="aud"><value>api://your-api-id</value></claim>
       </required-claims>
   </validate-jwt>
   ```

2. **Rate Limiting**:
   ```xml
   <rate-limit calls="100" renewal-period="60" />
   ```

3. **Private Endpoints**:
   - Use VNet integration for Functions
   - Configure APIM in internal mode
   - Use Private Endpoints for all Azure services

4. **Token Security**:
   - Remove all token logging
   - Implement token caching
   - Use short-lived tokens
   - Regular secret rotation

5. **Monitoring & Alerts**:
   - Application Insights for all components
   - Alerts on failures and anomalies
   - Audit logging for OAuth flows

## 📊 Monitoring

### Application Insights Queries

#### Web App Requests
```kusto
requests
| where cloud_RoleName == "webapp-copilotkit"
| where timestamp > ago(1h)
| summarize count(), avg(duration) by name, resultCode
```

#### Functions MCP Server Logs
```kusto
traces
| where cloud_RoleName == "func-mcp-server"
| where message contains "whoami"
| project timestamp, message, severityLevel
| order by timestamp desc
```

#### APIM Analytics
```kusto
requests
| where url contains "apim-foundry-mcp-handson"
| summarize count() by resultCode, url
| order by count_ desc
```

## 🤝 Contributing

This is a hands-on demonstration repository. Contributions for:
- Documentation improvements
- Bug fixes
- Additional MCP tools
- Enhanced error handling

are welcome!

## 📄 License

See [LICENSE](./LICENSE) file.

## 🙏 Acknowledgments

- [CopilotKit](https://copilotkit.ai/) for the chat UI framework
- [Azure AI Foundry](https://ai.azure.com) for the agent platform
- [MCP](https://modelcontextprotocol.io/) for the protocol specification

---

## 日本語 / Japanese

# CopilotKit × Foundry Agent (V2) × OAuth Identity Passthrough MCP - ハンズオン

このリポジトリは、**CopilotKit UI** を使用したチャットアプリケーションを **Azure AI Foundry Agent V2 API** に接続し、**OAuth Identity Passthrough** を介して Azure Functions 上で動作する **MCP Server** を呼び出す完全なハンズオン実装です。

## 🎯 目的

以下の方法を実証します：
- CopilotKit を使用したモダンなチャット UI の構築
- Azure AI Foundry Agent V2 API（Threads/Runs/Messages モデル）への接続
- ユーザー委任 API アクセスのための OAuth Identity Passthrough の実装
- ユーザートークンを受け取る MCP サーバーの作成
- 認証済みユーザーの代わりに Microsoft Graph API を呼び出す

> ⚠️ **注意**: これはハンズオン/デモンストレーションプロジェクトです。APIM での JWT 検証などのセキュリティ強化は、簡素化のため意図的に省略されています。

## 🏗️ アーキテクチャ

上記の英語セクションのアーキテクチャ図を参照してください。

## 📦 コンポーネント

### 1. Web App (webapp-copilotkit/)
- **フレームワーク**: TypeScript を使用した Next.js 14
- **UI**: チャットインターフェース用の CopilotKit
- **API**: Foundry Agent V2 を呼び出す `/api/copilot` エンドポイント

### 2. Azure Functions MCP Server (functions-mcp-server/)
- **ランタイム**: Python 3.11+
- **フレームワーク**: Azure Functions v4
- **MCP ツール**: `whoami`、`tools`、`health`

### 3. Azure リソース
- **Azure AI Foundry**: OAuth 接続を持つ Agent V2
- **Azure API Management**: MCP サーバーのゲートウェイ
- **Azure App Service**: Web アプリをホスト
- **Entra ID**: OAuth 用のアプリ登録

## 📚 ドキュメント

詳細なセットアップガイド：

1. **[Entra ID アプリ登録](./docs/01-entra-id-setup.md)** (英語)
2. **[APIM セットアップ](./docs/02-apim-setup.md)** (英語)
3. **[Foundry セットアップ](./docs/03-foundry-setup.md)** (英語)

## 🚀 クイックスタート

詳細な手順については、上記の英語セクションを参照してください。

## ✅ 受け入れ条件

- [x] CopilotKit UI から Foundry Agent を実行できる
- [x] OAuth Identity Passthrough によりユーザー同意が発生する
- [x] MCP Server が Authorization ヘッダーを受け取れる
- [x] Graph API がユーザー権限で実行される
- [x] validate-jwt を使っていない状態で一連が動作する

## 🔒 セキュリティに関する注意

本実装は **ハンズオン目的** のため、以下の点に注意してください：

- JWT 検証は APIM で行われていません
- 本番環境では、適切な JWT 検証、レート制限、プライベートエンドポイントの実装が必要です

## 📄 ライセンス

[LICENSE](./LICENSE) ファイルを参照してください。
