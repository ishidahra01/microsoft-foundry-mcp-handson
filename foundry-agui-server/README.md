# Foundry Agent V2 as AG-UI Server

This server loads an **existing Azure AI Foundry Agent (V2)** by name and exposes it as an **AG-UI endpoint** for CopilotKit.

## Why this exists

Your Next.js API route (`webapp-copilotkit/src/app/api/copilot/route.ts`) now uses `HttpAgent`, which requires an AG-UI-compatible backend URL.

Set that URL as:

- `FOUNDRY_AGENT_URL=http://localhost:8000/ag-ui` (local)
- or your deployed AG-UI URL in production.

## Prerequisites

- Python 3.10+
- `az login` completed (or managed identity / other credential source for `DefaultAzureCredential`)
- Existing Foundry project + existing Foundry agent name

## Setup

```bash
cd foundry-agui-server
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# Agent Framework packages are frequently prerelease-first.
pip install --pre -r requirements.txt

cp .env.template .env
```

Edit `.env`:

```env
AZURE_AI_PROJECT_ENDPOINT=https://<your-project>.services.ai.azure.com/api/projects/<your-project>
AZURE_AI_PROJECT_AGENT_NAME=<your-agent-name>
AGUI_PATH=/ag-ui
AGUI_CORS_ORIGINS=http://localhost:3000
```

Optional:

```env
AZURE_AI_PROJECT_AGENT_VERSION=1
AGUI_HOST=0.0.0.0
AGUI_PORT=8000
```

## Run

```bash
python server.py
# or
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/
```

## Connect from CopilotKit

In `webapp-copilotkit/.env.local`:

```env
FOUNDRY_AGENT_URL=http://localhost:8000/ag-ui
FOUNDRY_AUTH_MODE=none
```

- Use `FOUNDRY_AUTH_MODE=none` for local AG-UI server without auth.
- Use `FOUNDRY_AUTH_MODE=entra` when the AG-UI endpoint itself expects Entra bearer auth.

## Notes

- The Foundry project endpoint is **not** the AG-UI endpoint.
- `FOUNDRY_AGENT_URL` must point to this FastAPI AG-UI server path.
