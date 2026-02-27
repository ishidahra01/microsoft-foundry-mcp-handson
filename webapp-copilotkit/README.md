# Web App - CopilotKit x Foundry Agent (via AG-UI)

This is a Next.js web app that uses CopilotKit UI and routes chat requests to an AG-UI endpoint, which can wrap an existing Azure AI Foundry Agent V2.

## Architecture

1. Browser UI (`@copilotkit/react-ui`)
2. Next.js API route (`/api/copilot`) with `@copilotkitnext/runtime`
3. `HttpAgent` forwards to AG-UI endpoint (`FOUNDRY_AGENT_URL`)
4. AG-UI server bridges to existing Foundry Agent V2

## Prerequisites

- Node.js 18+
- npm
- AG-UI backend URL (local or deployed)

## Installation

```bash
cd webapp-copilotkit
npm install
cp .env.local.template .env.local
```

Set environment variables in `.env.local`:

```env
# AG-UI endpoint URL
FOUNDRY_AGENT_URL=http://localhost:8000/ag-ui

# Auth mode for calling AG-UI backend
# entra | bearer | none
FOUNDRY_AUTH_MODE=none

# Optional when auth mode is entra
FOUNDRY_SCOPE=https://ai.azure.com/.default

# Optional when auth mode is bearer
# FOUNDRY_BEARER_TOKEN=<token>

# Optional agent key used inside CopilotRuntime
COPILOTKIT_AGENT_NAME=foundry
```

## Development

```bash
npm run dev
```

Open `http://localhost:3000`.

## API Route

`src/app/api/copilot/route.ts`

- Builds Copilot runtime dynamically per request
- Uses `HttpAgent` to connect to AG-UI server
- Supports auth mode switch:
  - `entra`: acquires token with `DefaultAzureCredential`
  - `bearer`: uses static bearer token from env
  - `none`: no Authorization header

## Run with local Foundry AG-UI server

1. Start AG-UI server:

```bash
cd ../foundry-agui-server
python server.py
```

2. Start Next.js app:

```bash
cd ../webapp-copilotkit
npm run dev
```

3. Send a chat message from UI.

## Troubleshooting

- `Missing agent URL`
  - Set `FOUNDRY_AGENT_URL` (or fallback `AGENT_URL` / `FOUNDRY_ENDPOINT`).
- `Failed to acquire access token`
  - Use `FOUNDRY_AUTH_MODE=none` for local server, or run `az login` for `entra` mode.
- Connection errors to AG-UI
  - Verify AG-UI path matches server (`/ag-ui` by default).
  - Verify CORS includes `http://localhost:3000`.

## Learn more

- AG-UI integration (Microsoft Agent Framework): https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/
- AG-UI getting started: https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/getting-started
- Azure AI Foundry project SDK: https://learn.microsoft.com/en-us/azure/ai-studio/how-to/develop/sdk-overview
