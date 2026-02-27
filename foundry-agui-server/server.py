"""AG-UI server that exposes an existing Azure AI Foundry Agent (V2)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential

from agent_framework.azure import AzureAIProjectAgentProvider
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint

load_dotenv()

DEFAULT_SCOPE = "https://ai.azure.com/.default"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable '{name}' is required.")
    return value


def _cors_origins() -> list[str]:
    raw = os.getenv("AGUI_CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


PROJECT_ENDPOINT = _required_env("AZURE_AI_PROJECT_ENDPOINT")
AGENT_NAME = _required_env("AZURE_AI_PROJECT_AGENT_NAME")
AGENT_VERSION = os.getenv("AZURE_AI_PROJECT_AGENT_VERSION")
AGUI_PATH = os.getenv("AGUI_PATH", "/ag-ui")
AGUI_HOST = os.getenv("AGUI_HOST", "0.0.0.0")
AGUI_PORT = int(os.getenv("AGUI_PORT", "8000"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)

    try:
        await credential.get_token(DEFAULT_SCOPE)

        async with project_client, AzureAIProjectAgentProvider(project_client=project_client) as provider:
            if AGENT_VERSION:
                agent = await provider.get_agent(name=AGENT_NAME, version=AGENT_VERSION)
            else:
                agent = await provider.get_agent(name=AGENT_NAME)

            if agent is None:
                version_hint = f" version '{AGENT_VERSION}'" if AGENT_VERSION else ""
                raise RuntimeError(
                    f"Agent '{AGENT_NAME}'{version_hint} was not found in project '{PROJECT_ENDPOINT}'."
                )

            add_agent_framework_fastapi_endpoint(
                app=app,
                agent=agent,
                path=AGUI_PATH,
            )

            app.state.agent = agent
            app.state.agent_name = AGENT_NAME
            app.state.agent_version = AGENT_VERSION or "latest"
            app.state.agui_path = AGUI_PATH

            print(
                f"AG-UI endpoint ready at {AGUI_PATH} for agent '{AGENT_NAME}' "
                f"(version: {app.state.agent_version})"
            )
            yield
    finally:
        await credential.close()


app = FastAPI(
    title="Foundry Agent AG-UI Server",
    description="Expose an existing Azure AI Foundry agent via AG-UI.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "agent_name": getattr(app.state, "agent_name", None),
        "agent_version": getattr(app.state, "agent_version", None),
        "agui_path": getattr(app.state, "agui_path", AGUI_PATH),
        "agent_loaded": hasattr(app.state, "agent"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host=AGUI_HOST, port=AGUI_PORT, reload=True)
