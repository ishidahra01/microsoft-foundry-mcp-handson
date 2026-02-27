# webapp-foundry-oauth

Foundry Agent + MCP OAuth Identity Passthrough の **Agent UI** 実装サンプルです。

AG-UI / CopilotKit に依存せず、以下を実現します。

| 機能 | 内容 |
|------|------|
| リアルタイムストリーミング | Foundry Responses API の SSE をそのままフロントへ転送 |
| **OAuth Consent UI** | MCP ツールが `oauth_consent_request` を出したらカード表示 + ポップアップ同意 |
| **Continue（再開）** | 同意後に `previous_response_id` を使ってエージェントを再開 |
| ツール実行ログ | tool.start / tool.end / tool.error を右パネルにリアルタイム表示 |

---

## アーキテクチャ

```
Browser (Next.js)
  │  /api/* (Next.js rewrites → FastAPI)
  │
FastAPI backend (server.py)
  │  POST /openai/v1/responses  (stream=true)
  │
Azure AI Foundry (Responses API V2)
  │  MCP ツール呼び出し
  │
Azure Functions MCP Server
  │  Authorization: Bearer <user-token>
  │
Microsoft Graph API
```

### OAuth Consent フロー

```
User sends message
    │
    ▼
FastAPI → Foundry Responses API (stream)
    │
    │  event: oauth_consent_request
    │  {"consent_link": "https://login.microsoftonline.com/..."}
    ▼
Frontend shows ConsentCard
    │
    ├── [Open Consent Page] → popup window → user grants permission
    │
    └── [I've Consented — Continue]
            │
            ▼
        POST /api/continue
            │
            ▼
        FastAPI → Foundry Responses API
            body: { previous_response_id: "resp_xxx" }
            │
            ▼
        Agent resumes → tool executes → response streams to UI
```

---

## ディレクトリ構成

```
webapp-foundry-oauth/
├── backend/
│   ├── server.py          # FastAPI SSE サーバー
│   ├── requirements.txt
│   └── .env.template
└── frontend/
    ├── src/app/
    │   ├── page.tsx        # チャット UI（メインコンポーネント）
    │   ├── layout.tsx
    │   └── globals.css
    ├── next.config.js      # /api/* → FastAPI へのリライト設定
    ├── package.json
    ├── tailwind.config.ts
    └── .env.local.template
```

---

## セットアップ

### 前提条件

- **Azure AI Foundry プロジェクト**と **Agent V2**（MCP ツール付き）が作成済みであること
- プロジェクトに対して **Azure AI User** 以上のロールが割り当てられていること
  （[参照](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication)）
- ローカル開発時は `az login` 済みであること
- Node.js 18+ / Python 3.11+ がインストール済みであること

---

### 1. バックエンド（FastAPI）

```bash
cd webapp-foundry-oauth/backend

# 仮想環境を作成・有効化
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 依存関係インストール
pip install -r requirements.txt

# 環境変数を設定
cp .env.template .env
# .env を編集: PROJECT_ENDPOINT, AGENT_ID を入力

# サーバー起動（ポート 8000）
uvicorn server:app --reload --port 8000
```

`.env` の設定例:

```env
PROJECT_ENDPOINT=https://your-hub.openai.azure.com/
AGENT_ID=asst_xxxxxxxxxxxx
CORS_ORIGINS=http://localhost:3000
```

> **認証について**
> バックエンドは `DefaultAzureCredential` を使用して `https://ai.azure.com/.default` スコープのトークンを取得します。
> ローカルでは `az login` で認証してください。
> 本番環境（Azure App Service など）ではマネージド ID を使用してください。

---

### 2. フロントエンド（Next.js）

```bash
cd webapp-foundry-oauth/frontend

# 依存関係インストール
npm install

# 環境変数を設定
cp .env.local.template .env.local
# バックエンドが localhost:8000 以外の場合は BACKEND_URL を変更

# 開発サーバー起動（ポート 3000）
npm run dev
```

ブラウザで http://localhost:3000 を開くと UI が表示されます。

---

## 動作確認

1. チャット欄に **「Who am I?」** と入力して送信
2. MCP ツール（whoami）が初回呼び出しされると、右パネルに `⏳ whoami` が表示される
3. OAuth 同意が必要な場合、画面に **ConsentCard** が表示される
   - 「Open Consent Page」をクリック → ポップアップで Microsoft アカウントにサインイン
   - 同意後、「I've Consented — Continue」をクリック
4. エージェントが再開し、Graph API 経由でユーザー情報が返答として表示される
5. 右パネルのツールログが `✅ whoami` に変わる

---

## SSE イベント仕様

バックエンドからフロントエンドへ流れる SSE イベントの一覧です。

| `type` | 内容 |
|--------|------|
| `text.delta` | テキスト差分（`delta: string`） |
| `tool.start` | ツール呼び出し開始（`toolName`, `callId`） |
| `tool.end` | ツール呼び出し完了（`toolName`, `callId`） |
| `tool.error` | ツール呼び出しエラー（`toolName`, `callId`, `error`） |
| `oauth_consent_required` | OAuth 同意が必要（`consentLink`, `responseId`, `connectionName`） |
| `done` | ストリーム完了（`responseId`） |
| `error` | エラー（`message`） |

---

## API エンドポイント

### `POST /api/chat`

新しいメッセージを送信してストリーミングレスポンスを取得します。

**Request body:**
```json
{
  "conversationId": "abc123",
  "userMessage": "Who am I?"
}
```

- `conversationId` は会話を識別するランダムな文字列（フロントエンドが生成）
- 同じ `conversationId` で再送すると、会話履歴が引き継がれます

**Response:** `text/event-stream`（上記 SSE イベント）

---

### `POST /api/continue`

OAuth 同意後に会話を再開します。

**Request body:**
```json
{
  "conversationId": "abc123"
}
```

バックエンドが保存している `previous_response_id` を使って Foundry Responses API を再呼び出しします。
（[参照: MCP server authentication](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication)）

**Response:** `text/event-stream`（上記 SSE イベント）

---

## セキュリティに関する注意

- **`consent_link` はログに残さない**
  OAuth state / nonce が含まれる可能性があるため、バックエンドではリンク本体をログ出力しません。
- **トークンはヘッダーで渡す**（Foundry の Authorization Header Pattern）
  MCP ツール引数にトークンを含めません。
- **本番環境では**:
  - マネージド ID を使用する
  - セッションストア（Redis 等）で会話状態を管理する
  - HTTPS を必須にする
  - Foundry プロジェクトへのアクセスは **Azure AI User** 以上のロールに限定する

---

## 参考リンク

- [MCP server authentication / OAuth Identity Passthrough](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication)
- [Foundry Responses API](https://learn.microsoft.com/azure/ai-foundry/agents/responses-api/overview)
- [DefaultAzureCredential (azure-identity)](https://learn.microsoft.com/python/api/azure-identity/azure.identity.defaultazurecredential)
