# CopilotKit × Foundry Agent (V2) × OAuth Identity Passthrough MCP - Hands-on

[Japanese follows English / 日本語は英語の後にあります]

This repository contains a complete hands-on implementation of a chat application using **CopilotKit UI** connected to **Azure AI Foundry Agent V2 API** with **OAuth Identity Passthrough** to a **self-hosted MCP Server** running on Azure Functions.

## 🎯 Purpose

Demonstrate the **official MCP design pattern** for authentication:

- **Authorization Header Pattern**: Authentication credentials passed via HTTP headers, not tool arguments
- **OAuth Identity Passthrough**: User-delegated tokens enable API calls on behalf of authenticated users
- **Self-hosted MCP Server**: HTTP + JSON-RPC implementation on Azure Functions
- **Standard Security Model**: MCP servers follow the same security practices as traditional HTTP APIs
- **No Token Exposure**: Tokens never appear in tool arguments, traces, or approval logs

### What You'll Learn

- Build a modern chat UI with CopilotKit
- Connect to Azure AI Foundry Agent V2 API (Threads/Runs/Messages model)
- Implement OAuth Identity Passthrough with proper header-based authentication
- Create a self-hosted MCP server that extracts tokens from Authorization headers
- Call Microsoft Graph API on behalf of authenticated users
- Follow MCP and OAuth best practices

> ⚠️ **Note**: This is a hands-on/demonstration project. Security enhancements like JWT validation in APIM are intentionally omitted for simplicity. See [Architecture Overview](./docs/00-architecture-overview.md) for production recommendations.

## 🏗️ Architecture

### High-Level Overview

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
│                    CopilotKit Server (/api/copilot)              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Foundry Agent API (V2)
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Azure AI Foundry Agent (V2)                     │
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
                                │ (Token in header, NOT in arguments!)
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
│  │  - Call Microsoft Graph API                             │  │
│  │  - Return user information                               │  │
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

### Key Design Principles

1. **Authorization Header Pattern**
   - ✅ Tokens passed via `Authorization: Bearer <token>` header
   - ✅ MCP tool arguments contain only business parameters
   - ✅ No token exposure in Foundry traces or approval logs

2. **OAuth Identity Passthrough**
   - ✅ User consent flow on first use
   - ✅ User-delegated tokens for Graph API
   - ✅ Automatic token refresh by Foundry
   - ✅ Each user's token is separate and secure

3. **Self-hosted MCP Server**
   - ✅ HTTP + JSON-RPC 2.0 protocol
   - ✅ Token extraction from HTTP headers
   - ✅ Standard HTTP security practices
   - ✅ Full control over authentication logic

📖 **For detailed architecture explanation, see**: [Architecture Overview](./docs/00-architecture-overview.md)

## 📦 Components

### 1. Web App (webapp-copilotkit/)
- **Framework**: Next.js 14 with TypeScript
- **UI**: CopilotKit for chat interface
- **API**: `/api/copilot` endpoint that calls Foundry Agent V2
- **Features**:
  - Modern chat UI with streaming support
  - Session management via Foundry Threads API
  - No direct OAuth handling (delegated to Foundry)

### 2. Azure Functions MCP Server (functions-mcp-selfhosted/)
- **Runtime**: Python 3.11+
- **Framework**: FastMCP (HTTP + JSON-RPC)
- **Protocol**: MCP (Model Context Protocol)
- **Authentication**: Authorization header-based
- **MCP Tools**:
  - `whoami` - Get current user info from Graph API
  - `greet` - Simple test tool
- **Key Features**:
  - ✅ Self-hosted HTTP + JSON-RPC server
  - ✅ Token extraction from Authorization header
  - ✅ Calls Microsoft Graph API with user-delegated tokens
  - ✅ No token validation (hands-on mode)
  - ✅ Stateless operation

📖 **Detailed setup guide**: [MCP Server Setup](./docs/06-mcp-server-setup.md)

### 3. Azure Resources
- **Azure AI Foundry**: Agent V2 with OAuth Identity Passthrough connection
- **Azure API Management**: Gateway that forwards Authorization headers
- **Azure App Service**: Hosts the Next.js web application
- **Entra ID**: App registration for OAuth flows

## 📚 Documentation

### Core Documentation

1. **[Architecture Overview](./docs/00-architecture-overview.md)** ⭐ **Start Here**
   - Complete architecture explanation
   - OAuth Identity Passthrough patterns (Pattern A vs B)
   - Design principles and security model
   - Authentication flow diagrams

2. **[MCP Server Setup](./docs/06-mcp-server-setup.md)**
   - Self-hosted MCP server implementation
   - Local development setup
   - Azure deployment guide
   - Code structure explanation

### Setup Guides

3. **[Entra ID App Registration](./docs/01-entra-id-setup.md)**
   - Create OAuth app registration
   - Configure Microsoft Graph permissions
   - Set up client secrets

4. **[APIM Setup](./docs/02-apim-setup.md)**
   - Create APIM instance
   - Import Functions API
   - Configure Authorization header forwarding policies

5. **[Foundry Setup](./docs/03-foundry-setup.md)**
   - Create OAuth connection with Identity Passthrough
   - Configure MCP tool
   - Create Agent V2

6. **[Deployment Guide](./docs/04-deployment-guide.md)**
   - Complete deployment automation
   - Azure CLI commands
   - CI/CD setup

7. **[Troubleshooting Guide](./docs/05-troubleshooting.md)**
   - Common issues and solutions
   - OAuth debugging
   - Token flow verification

### Component READMEs

- **[Functions MCP Server README](./functions-mcp-selfhosted/README.md)**
- **[Web App README](./webapp-copilotkit/README.md)**

## 🚀 Quick Start

### Prerequisites

- Azure subscription with permissions to create resources
- Node.js 20+
- Python 3.11+
- Azure CLI (authenticated)
- Azure Functions Core Tools v4

### Setup Overview

This hands-on follows a specific order to build understanding:

```
1. Deploy MCP Server → 2. Setup APIM → 3. Configure Entra ID → 
4. Setup Foundry → 5. Deploy Web App → 6. Test End-to-End
```

### 1. Clone Repository

```bash
git clone https://github.com/ishidahra01/microsoft-foundry-mcp-handson.git
cd microsoft-foundry-mcp-handson
```

### 2. Deploy Azure Functions MCP Server

📖 **Full guide**: [MCP Server Setup](./docs/06-mcp-server-setup.md)

#### Option A: Quick Deploy with Script

```powershell
cd functions-mcp-selfhosted

# Install dependencies
pip install -r requirements.txt

# Test locally (optional)
func start

# Deploy to Azure
..\scripts\deploy-functions.ps1
```

The script creates:
- Resource group: `rg-ms-foundry-mcp`
- Storage account with standard settings
- Function App with unique name (e.g., `func-mcp-server-123456`)

**Save the Function App URL for next steps!**

#### Option B: Manual Azure CLI Deployment

```bash
cd functions-mcp-selfhosted

# Create resource group
az group create \
  --name rg-foundry-mcp \
  --location eastus

# Create storage account
az storage account create \
  --name stmcpserver$(date +%s) \
  --resource-group rg-foundry-mcp \
  --location eastus \
  --sku Standard_LRS

# Create Function App
az functionapp create \
  --resource-group rg-foundry-mcp \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name func-mcp-server-$(date +%s) \
  --storage-account stmcpserver123456

# Deploy
func azure functionapp publish func-mcp-server-123456
```

**Verify deployment:**
```bash
curl https://func-mcp-server-123456.azurewebsites.net/api/health
# Expected: {"status":"healthy",...}
```

### 3. Set Up Azure Resources

Follow these guides in order:

1. **[Create Entra ID App Registration](./docs/01-entra-id-setup.md)**
   - OAuth app for Identity Passthrough
   - Microsoft Graph `User.Read` permission
   - Client ID and secret

2. **[Set up APIM](./docs/02-apim-setup.md)**
   - Import Functions API
   - Configure Authorization header forwarding
   - Test APIM gateway

3. **[Configure Foundry Agent](./docs/03-foundry-setup.md)**
   - OAuth connection with Identity Passthrough
   - MCP tool pointing to APIM
   - Agent V2 configuration

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
3. **First time**: OAuth consent screen appears
   - Foundry initiates OAuth Identity Passthrough flow
   - Sign in with your Microsoft account
   - Grant `User.Read` permission
   - Consent is saved for future requests
4. **Behind the scenes**:
   - Foundry obtains your user-delegated access token
   - Agent calls MCP tool via APIM
   - Token is passed in `Authorization: Bearer <token>` header (NOT in arguments)
   - MCP server extracts token from header
   - MCP server calls Microsoft Graph API `/me`
5. **Result**: Your user information is displayed in the chat!

### 6. Verify the Authorization Header Pattern

Check Function logs to confirm token was received via header:

```bash
az webapp log tail \
  --name func-mcp-server-123456 \
  --resource-group rg-foundry-mcp
```

Look for:
```
Token status: present, preview: eyJ0eXAiOi..., length: 1234
whoami MCP tool called (self-hosted, header-based)
```

This confirms:
- ✅ Token received via Authorization header
- ✅ Not passed in tool arguments
- ✅ OAuth Identity Passthrough working correctly

## 🔑 Key Concepts

### Authorization Header vs Arguments

**❌ Old Pattern (Problematic)**:
```json
{
  "method": "tools/call",
  "params": {
    "name": "whoami",
    "arguments": {
      "access_token": "eyJ0eXAiOi..."  ← Token in arguments!
    }
  }
}
```
- Exposes tokens in Foundry traces
- Visible in Tool Approval UI
- Violates MCP/OAuth design principles

**✅ New Pattern (Current)**:
```http
POST /mcp
Authorization: Bearer eyJ0eXAiOi...  ← Token in header!
Content-Type: application/json

{
  "method": "tools/call",
  "params": {
    "name": "whoami",
    "arguments": {}  ← Only business parameters
  }
}
```
- Tokens in standard HTTP Authorization header
- Not exposed in traces or logs
- Follows MCP official design
- Standard HTTP security model

### OAuth Identity Passthrough Flow

```
1. User initiates action requiring MCP tool
2. Foundry checks: Does this connection need user consent?
3. First time: Redirect user to OAuth consent
4. User grants permission (User.Read for Graph)
5. Foundry stores user-delegated token
6. When calling MCP tool:
   - Foundry adds: Authorization: Bearer <user-token>
   - Arguments contain only business data
7. APIM forwards Authorization header unchanged
8. MCP server extracts token from header
9. MCP server calls Graph API with user token
10. User sees their data!
```

**Important**: Each user has their own token. The MCP server always operates with the current user's permissions.

## 🧪 Verification Steps

### Check 1: MCP Server Health

```bash
curl https://func-mcp-server-123456.azurewebsites.net/api/health
```

Expected: `{"status":"healthy","service":"MCP Server","version":"1.0.0"}`

### Check 2: APIM Gateway

```bash
curl https://apim-foundry-mcp-handson.azure-api.net/mcp/health
```

Expected: Same as MCP server health response

### Check 3: MCP Tools List

```bash
curl -X POST https://func-mcp-server-123456.azurewebsites.net/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Expected: List of available tools (whoami, greet)

### Check 4: OAuth Flow in Web App

1. Open web app in browser
2. Send message: "Who am I?"
3. Verify OAuth consent appears (first time)
4. After consent, verify user info is displayed
5. Send another message requiring the tool
6. Verify no consent needed (token cached)

### Check 5: Token Passed via Header

Check Function logs:

```bash
# Via Azure CLI
az webapp log tail \
  --name func-mcp-server-123456 \
  --resource-group rg-foundry-mcp

# Or via Application Insights (if configured)
az monitor app-insights query \
  --app your-app-insights \
  --analytics-query "traces | where message contains 'Token status'"
```

Look for: `Token status: present, preview: eyJ0eXAiOi..., length: 1234`

## 🔍 Troubleshooting

### Common Issues

#### OAuth Consent Doesn't Appear

**Symptoms**: When using MCP tool, no consent prompt shows

**Solutions**:
1. Verify Identity Passthrough is enabled in Foundry OAuth connection
2. Check OAuth app redirect URIs in Entra ID
3. Try in incognito/private browser window
4. Verify OAuth connection is attached to MCP tool in Foundry

#### "No authorization token provided" Error

**Symptoms**: MCP tool returns error about missing Authorization header

**Solutions**:
1. Check APIM policy forwards Authorization header:
   ```xml
   <set-header name="Authorization" exists-action="override">
       <value>@(context.Request.Headers.GetValueOrDefault("Authorization",""))</value>
   </set-header>
   ```
2. Verify OAuth connection is attached to MCP tool
3. Ensure Identity Passthrough is enabled
4. Test APIM endpoint directly with Authorization header

#### Graph API Call Fails with 401

**Symptoms**: Token is received but Graph API rejects it

**Solutions**:
1. Verify token has `User.Read` scope (decode at jwt.ms)
2. Check token hasn't expired
3. Verify OAuth app has Microsoft Graph permissions
4. Ensure admin consent was granted (if required)
5. Test token manually with [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer)

#### MCP Server Not Receiving Requests

**Symptoms**: APIM returns 502 Bad Gateway

**Solutions**:
1. Verify Function App is running:
   ```bash
   az functionapp show --name func-mcp-server-123456 \
     --resource-group rg-foundry-mcp --query state
   ```
2. Check Function App URL is correct in APIM
3. Test Function App directly (bypass APIM)
4. Review Function App logs for errors

📖 **For more troubleshooting**: [Troubleshooting Guide](./docs/05-troubleshooting.md)

## ⚠️ Security Notes

### Current Implementation (Hands-on Mode)

This implementation demonstrates **OAuth Identity Passthrough with Authorization Header pattern** in a simplified, hands-on-friendly way:

**What IS implemented:**
- ✅ **Authorization Header Pattern**: Tokens in headers, not arguments
- ✅ **OAuth 2.0 Authorization Code Flow**: Standard OAuth flow
- ✅ **User Consent and Delegation**: Proper user authorization
- ✅ **HTTPS Encryption**: All communication encrypted
- ✅ **Token Scoping**: Tokens limited to granted permissions
- ✅ **Secure Logging**: Only token preview (first 10 chars) logged

**What is NOT implemented (intentionally for hands-on):**
- ❌ **JWT Validation in APIM**: Tokens accepted without signature verification
- ❌ **Token Audience Checks**: Audience not validated
- ❌ **Rate Limiting**: Only default APIM limits apply
- ❌ **IP Restrictions**: Services publicly accessible
- ❌ **Private Endpoints**: No VNet integration

**Rationale**: This is a hands-on/demonstration project focused on:
1. Understanding OAuth Identity Passthrough
2. Learning Authorization Header pattern
3. Implementing self-hosted MCP servers
4. Accessible learning experience

### Production Enhancements

For production deployments, implement these security measures:

#### 1. JWT Validation in APIM

```xml
<validate-jwt header-name="Authorization">
    <openid-config url="https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration" />
    <required-claims>
        <claim name="aud"><value>api://your-api-id</value></claim>
        <claim name="scp" match="any">
            <value>User.Read</value>
        </claim>
    </required-claims>
</validate-jwt>
```

#### 2. Rate Limiting & Quotas

```xml
<rate-limit calls="100" renewal-period="60" />
<quota calls="10000" renewal-period="86400" />
<rate-limit-by-key calls="20" renewal-period="60" 
    counter-key="@(context.Request.Headers.GetValueOrDefault("Authorization","").Split(' ')[1].Substring(0,10))" />
```

#### 3. Network Security

- **VNet Integration**: Connect Functions to private VNet
- **Private Endpoints**: Use private endpoints for all Azure services
- **NSG Rules**: Configure network security groups
- **APIM Internal Mode**: Deploy APIM in internal VNet mode

#### 4. Token Security

- **Remove Token Logging**: Delete all token preview logging
- **Token Caching**: Implement with appropriate TTL (5-60 minutes)
- **Certificate-based Auth**: Use certificates instead of client secrets
- **Secret Rotation**: Automate client secret rotation (e.g., Key Vault integration)
- **Short-lived Tokens**: Request tokens with minimal lifetime

#### 5. Monitoring & Auditing

- **Application Insights**: Enable for all components
- **Alerts**: Configure alerts for:
  - Authentication failures
  - Unusual token usage patterns
  - API errors and throttling
  - Performance degradation
- **Audit Logging**: Log OAuth consent events, token usage
- **Security Scanning**: Regular vulnerability scans

#### 6. On-Behalf-Of (OBO) Pattern

Consider **Pattern B** from [Architecture Overview](./docs/00-architecture-overview.md):

```
Foundry → [MCP Token] → MCP Server → [OBO Exchange] → Graph API
```

Benefits:
- MCP server validates incoming tokens (audience = MCP API)
- Clear security boundaries between services
- Fine-grained permission control
- Production-ready pattern

📖 **Detailed security recommendations**: [Architecture Overview - Security Model](./docs/00-architecture-overview.md#security-model)

## 📊 Monitoring

### Application Insights Queries

#### MCP Server Token Usage
```kusto
traces
| where cloud_RoleName contains "func-mcp-server"
| where message contains "Token status"
| project timestamp, message, severityLevel
| order by timestamp desc
```

#### MCP Tool Invocations
```kusto
traces
| where cloud_RoleName contains "func-mcp-server"
| where message contains "whoami MCP tool called"
| summarize count() by bin(timestamp, 1h)
| render timechart
```

#### APIM Analytics
```kusto
requests
| where url contains "apim"
| summarize count(), avg(duration) by resultCode
| order by count_ desc
```

## 📖 References

### Official Documentation

- **[Azure AI Foundry MCP Authentication](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication)** - OAuth Identity Passthrough guide
- **[Model Context Protocol](https://modelcontextprotocol.io/)** - Official MCP specification
- **[OAuth 2.0 on Microsoft Identity Platform](https://learn.microsoft.com/entra/identity-platform/v2-oauth2-auth-code-flow)** - Authorization code flow
- **[Microsoft Graph API](https://learn.microsoft.com/graph/overview)** - Graph API reference

### Implementation Resources

- **[Self-hosted MCP Server on Azure Functions (Japanese)](https://zenn.dev/microsoft/articles/host-existing-mcp-server-on-azure-functions)** - Implementation guide
- **[Azure Functions Python Developer Guide](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)** - Functions development
- **[Azure API Management](https://learn.microsoft.com/azure/api-management/)** - APIM documentation

### Tools

- **[JWT Decoder](https://jwt.ms)** - Decode and inspect JWT tokens
- **[Graph Explorer](https://developer.microsoft.com/graph/graph-explorer)** - Test Graph API calls
- **[Postman](https://www.postman.com/)** - API testing

## 🤝 Contributing

This is a hands-on demonstration repository. Contributions welcome for:
- 📝 Documentation improvements
- 🐛 Bug fixes
- 🔧 Additional MCP tools examples
- ✨ Enhanced error handling
- 🌐 Translations

## 📄 License

See [LICENSE](./LICENSE) file.

## 🙏 Acknowledgments

- [CopilotKit](https://copilotkit.ai/) - Chat UI framework
- [Azure AI Foundry](https://ai.azure.com) - Agent platform with OAuth Identity Passthrough
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) - Protocol specification
- [FastMCP](https://github.com/modelcontextprotocol/python-sdk) - Python MCP implementation

---

## 日本語 / Japanese

# CopilotKit × Foundry Agent (V2) × OAuth Identity Passthrough MCP - ハンズオン

このリポジトリは、**CopilotKit UI** を使用したチャットアプリケーションを **Azure AI Foundry Agent V2 API** に接続し、**OAuth Identity Passthrough** を介して Azure Functions 上で動作する **セルフホスト型 MCP Server** を呼び出す完全なハンズオン実装です。

## 🎯 目的

**MCP 公式設計パターン**による認証を実証します：

- **Authorization Header パターン**: 認証情報は HTTP ヘッダーで渡し、ツール引数には含めない
- **OAuth Identity Passthrough**: ユーザー委任トークンにより、認証されたユーザーの代わりに API を呼び出す
- **セルフホスト型 MCP サーバー**: Azure Functions 上の HTTP + JSON-RPC 実装
- **標準的なセキュリティモデル**: MCP サーバーは従来の HTTP API と同じセキュリティプラクティスに従う
- **トークン露出なし**: トークンはツール引数、トレース、承認ログに決して現れない

### 学習内容

- CopilotKit を使用したモダンなチャット UI の構築
- Azure AI Foundry Agent V2 API（Threads/Runs/Messages モデル）への接続
- 適切なヘッダーベース認証による OAuth Identity Passthrough の実装
- Authorization ヘッダーからトークンを抽出するセルフホスト型 MCP サーバーの作成
- 認証済みユーザーの代わりに Microsoft Graph API を呼び出す
- MCP および OAuth のベストプラクティスに従う

> ⚠️ **注意**: これはハンズオン/デモンストレーションプロジェクトです。APIM での JWT 検証などのセキュリティ強化は、簡素化のため意図的に省略されています。本番環境向けの推奨事項については [アーキテクチャ概要](./docs/00-architecture-overview.md) を参照してください。

## 🏗️ アーキテクチャ

英語セクションのアーキテクチャ図を参照してください。

### 重要な設計原則

1. **Authorization Header パターン**
   - ✅ トークンは `Authorization: Bearer <token>` ヘッダーで渡される
   - ✅ MCP ツールの引数にはビジネスパラメータのみを含める
   - ✅ Foundry のトレースや承認ログにトークンが露出しない

2. **OAuth Identity Passthrough**
   - ✅ 初回利用時にユーザー同意フロー
   - ✅ Graph API 用のユーザー委任トークン
   - ✅ Foundry による自動トークン更新
   - ✅ 各ユーザーのトークンは分離され安全

3. **セルフホスト型 MCP サーバー**
   - ✅ HTTP + JSON-RPC 2.0 プロトコル
   - ✅ HTTP ヘッダーからのトークン抽出
   - ✅ 標準的な HTTP セキュリティプラクティス
   - ✅ 認証ロジックの完全な制御

📖 **詳細なアーキテクチャ説明**: [アーキテクチャ概要](./docs/00-architecture-overview.md)

## 📦 コンポーネント

### 1. Web App (webapp-copilotkit/)
- **フレームワーク**: TypeScript を使用した Next.js 14
- **UI**: チャットインターフェース用の CopilotKit
- **API**: Foundry Agent V2 を呼び出す `/api/copilot` エンドポイント

### 2. Azure Functions MCP Server (functions-mcp-selfhosted/)
- **ランタイム**: Python 3.11+
- **フレームワーク**: FastMCP（HTTP + JSON-RPC）
- **プロトコル**: MCP（Model Context Protocol）
- **認証**: Authorization ヘッダーベース
- **MCP ツール**: `whoami`、`greet`

📖 **詳細なセットアップガイド**: [MCP サーバーセットアップ](./docs/06-mcp-server-setup.md)

### 3. Azure リソース
- **Azure AI Foundry**: OAuth Identity Passthrough 接続を持つ Agent V2
- **Azure API Management**: Authorization ヘッダーを転送するゲートウェイ
- **Azure App Service**: Next.js Web アプリをホスト
- **Entra ID**: OAuth フロー用のアプリ登録

## 📚 ドキュメント

### コアドキュメント

1. **[アーキテクチャ概要](./docs/00-architecture-overview.md)** ⭐ **ここから開始**
   - 完全なアーキテクチャ説明
   - OAuth Identity Passthrough パターン（パターン A vs B）
   - 設計原則とセキュリティモデル
   - 認証フロー図

2. **[MCP サーバーセットアップ](./docs/06-mcp-server-setup.md)**
   - セルフホスト型 MCP サーバー実装
   - ローカル開発環境のセットアップ
   - Azure デプロイメントガイド
   - コード構造の説明

### セットアップガイド

3. **[Entra ID アプリ登録](./docs/01-entra-id-setup.md)**
4. **[APIM セットアップ](./docs/02-apim-setup.md)**
5. **[Foundry セットアップ](./docs/03-foundry-setup.md)**
6. **[デプロイメントガイド](./docs/04-deployment-guide.md)**
7. **[トラブルシューティングガイド](./docs/05-troubleshooting.md)**

## 🚀 クイックスタート

詳細な手順については、英語セクションを参照してください。主要な流れ：

1. MCP サーバーをデプロイ
2. APIM をセットアップ
3. Entra ID を構成
4. Foundry をセットアップ
5. Web アプリをデプロイ
6. エンドツーエンドでテスト

## 🔑 重要な概念

### Authorization Header vs 引数

**❌ 旧パターン（問題あり）**:
- トークンをツール引数に含める
- Foundry トレースにトークンが露出
- MCP/OAuth 設計原則に違反

**✅ 新パターン（現在）**:
- トークンは標準 HTTP Authorization ヘッダー
- トレースやログに露出しない
- MCP 公式設計に従う
- 標準 HTTP セキュリティモデル

## ✅ 受け入れ条件

- [x] CopilotKit UI から Foundry Agent を実行できる
- [x] OAuth Identity Passthrough によりユーザー同意が発生する
- [x] MCP Server が Authorization ヘッダーからトークンを受け取れる
- [x] トークンがツール引数に含まれない
- [x] Graph API がユーザー権限で実行される
- [x] セルフホスト型 MCP サーバー（HTTP + JSON-RPC）が動作する
- [x] validate-jwt を使っていない状態で一連が動作する

## 🔒 セキュリティに関する注意

本実装は **ハンズオン目的** のため、以下の点に注意してください：

- Authorization Header パターンは実装済み
- JWT 検証は APIM で行われていません（ハンズオンモード）
- 本番環境では、適切な JWT 検証、レート制限、プライベートエンドポイントの実装が必要です

📖 **本番環境向け推奨事項**: [アーキテクチャ概要 - セキュリティモデル](./docs/00-architecture-overview.md#security-model)

## 📖 参考資料

### 公式ドキュメント

- **[Azure AI Foundry MCP 認証](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication)** - OAuth Identity Passthrough ガイド
- **[Model Context Protocol](https://modelcontextprotocol.io/)** - MCP 公式仕様
- **[Microsoft ID プラットフォームでの OAuth 2.0](https://learn.microsoft.com/ja-jp/entra/identity-platform/v2-oauth2-auth-code-flow)** - 認可コードフロー
- **[Microsoft Graph API](https://learn.microsoft.com/ja-jp/graph/overview)** - Graph API リファレンス

### 実装リソース

- **[Azure Functions でセルフホスト型 MCP サーバー（日本語）](https://zenn.dev/microsoft/articles/host-existing-mcp-server-on-azure-functions)** - 実装ガイド
- **[Azure Functions Python 開発者ガイド](https://learn.microsoft.com/ja-jp/azure/azure-functions/functions-reference-python)** - Functions 開発

## 📄 ライセンス

[LICENSE](./LICENSE) ファイルを参照してください。
