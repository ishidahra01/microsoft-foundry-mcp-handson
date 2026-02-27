"""
Foundry Agent OAuth UI — Backend Server

FastAPI server with SSE streaming that:
  - Proxies Foundry Responses API (openai/v1/responses, streaming)
  - Detects `oauth_consent_request` events from MCP tool calls
  - Persists conversation state (previous_response_id) in memory
  - Exposes /api/chat  (start / continue a chat turn)
  - Exposes /api/continue (resume after OAuth consent)

SSE events sent to the frontend
────────────────────────────────
  {"type": "text.delta",            "delta": "..."}
  {"type": "tool.start",            "toolName": "...", "callId": "..."}
  {"type": "tool.end",              "toolName": "...", "callId": "..."}
  {"type": "tool.error",            "toolName": "...", "callId": "...", "error": "..."}
  {"type": "oauth_consent_required","consentLink": "...",
                                    "responseId": "...", "connectionName": "..."}
  {"type": "done",                  "responseId": "..."}
  {"type": "error",                 "message": "..."}

References
──────────
  MCP server authentication / OAuth Identity Passthrough:
    https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication
  Foundry Responses API (openai-compatible):
    https://learn.microsoft.com/azure/ai-foundry/agents/responses-api/overview
"""

from __future__ import annotations

import json
import logging
import os
from typing import AsyncIterator, Optional

import httpx
from azure.identity.aio import DefaultAzureCredential
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# In-memory conversation state
# conversationId -> { previous_response_id: str | None }
#
# NOTE: This is intentionally simple for hands-on purposes.
#       In production use Redis, a DB, or a session store.
# ──────────────────────────────────────────────────────────────────────────────
_conversations: dict[str, dict] = {}


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    conversationId: str
    userMessage: str


class ContinueRequest(BaseModel):
    conversationId: str


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Foundry OAuth UI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    # Allow the Next.js dev server and any additional origins configured via env
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# Auth helper
# ──────────────────────────────────────────────────────────────────────────────
async def _get_token() -> str:
    """Acquire Azure access token for the Foundry scope (ai.azure.com)."""
    credential = DefaultAzureCredential()
    try:
        token = await credential.get_token("https://ai.azure.com/.default")
        return token.token
    finally:
        await credential.close()


# ──────────────────────────────────────────────────────────────────────────────
# SSE streaming from Foundry Responses API
# ──────────────────────────────────────────────────────────────────────────────
async def _stream_response(
    project_endpoint: str,
    agent_id: str,
    user_message: Optional[str],
    previous_response_id: Optional[str],
    conversation_id: str,
) -> AsyncIterator[str]:
    """
    Call the Foundry Responses API with streaming and translate the raw SSE
    events into the simplified event schema consumed by the frontend.

    The Foundry API is OpenAI-compatible; the endpoint is:
        POST {project_endpoint}/openai/v1/responses

    With `stream: true` the server returns Server-Sent Events.
    Foundry additionally emits `oauth_consent_request` events when MCP tools
    require user-delegated OAuth consent.
    See: https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication
    """
    token = await _get_token()

    # ── Build request body ───────────────────────────────────────────────────
    body: dict = {
        "model": agent_id,
        "stream": True,
    }

    if previous_response_id:
        # Continue the previous response (after OAuth consent or multi-turn)
        # Reference: https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication
        body["previous_response_id"] = previous_response_id

    if user_message:
        body["input"] = [{"role": "user", "content": user_message}]

    url = f"{project_endpoint.rstrip('/')}/openai/v1/responses"
    logger.info(
        "Calling Foundry Responses API url=%s previous_response_id=%s",
        url,
        previous_response_id,
    )

    # ── SSE helper ───────────────────────────────────────────────────────────
    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    # ── Mutable state across the stream ─────────────────────────────────────
    response_id: Optional[str] = None
    active_tool_calls: dict[str, str] = {}  # call_id → tool_name

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream(
                "POST",
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
                json=body,
            ) as resp:
                resp.raise_for_status()

                current_event_type: Optional[str] = None

                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        # Empty line = end of one SSE event block
                        current_event_type = None
                        continue

                    # SSE `event:` field
                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()
                        continue

                    # SSE `data:` field
                    if not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.debug("Non-JSON SSE data (skipped): %s", data_str[:120])
                        continue

                    # Use the SSE event field, or fall back to the "type" key in data
                    event_type = current_event_type or data.get("type", "")

                    # ── Response created → capture response ID ───────────────
                    if event_type == "response.created":
                        response_id = (
                            data.get("response", {}).get("id")
                            or data.get("id")
                        )

                    # ── Text output delta ────────────────────────────────────
                    elif event_type in (
                        "response.output_text.delta",
                        "response.text.delta",
                    ):
                        delta = data.get("delta", "")
                        if delta:
                            yield _sse({"type": "text.delta", "delta": delta})

                    elif event_type == "response.content_part.delta":
                        delta = data.get("delta", {})
                        text = (
                            delta.get("text", "")
                            if isinstance(delta, dict)
                            else str(delta)
                        )
                        if text:
                            yield _sse({"type": "text.delta", "delta": text})

                    # ── Tool call started ────────────────────────────────────
                    elif event_type == "response.output_item.added":
                        item = data.get("item", {})
                        if item.get("type") == "function_call":
                            call_id = item.get("call_id") or item.get("id", "")
                            tool_name = item.get("name", "unknown_tool")
                            active_tool_calls[call_id] = tool_name
                            logger.info(
                                "Tool call started: %s (call_id=%s)", tool_name, call_id
                            )
                            yield _sse(
                                {
                                    "type": "tool.start",
                                    "toolName": tool_name,
                                    "callId": call_id,
                                }
                            )

                    # ── Tool call completed ──────────────────────────────────
                    elif event_type == "response.output_item.done":
                        item = data.get("item", {})
                        if item.get("type") == "function_call":
                            call_id = item.get("call_id") or item.get("id", "")
                            tool_name = active_tool_calls.get(
                                call_id, item.get("name", "unknown_tool")
                            )
                            logger.info(
                                "Tool call done: %s (call_id=%s)", tool_name, call_id
                            )
                            yield _sse(
                                {
                                    "type": "tool.end",
                                    "toolName": tool_name,
                                    "callId": call_id,
                                }
                            )

                    # ── OAuth consent required ───────────────────────────────
                    # Foundry emits this event when an MCP tool needs the user
                    # to grant OAuth delegated access.
                    # After the user grants consent, the app must call
                    # /api/continue with the stored previous_response_id.
                    # Reference:
                    #   https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication
                    elif event_type == "oauth_consent_request":
                        consent_link = data.get("consent_link", "")
                        connection_name = data.get("connection_name", "")
                        # Store response_id for the upcoming /api/continue call
                        _conversations[conversation_id] = {
                            "previous_response_id": response_id
                        }
                        # SECURITY: Do NOT log the full consent_link as it may
                        # contain OAuth state / nonce parameters.
                        logger.info(
                            "OAuth consent required — connection=%s response_id=%s",
                            connection_name,
                            response_id,
                        )
                        yield _sse(
                            {
                                "type": "oauth_consent_required",
                                "consentLink": consent_link,
                                "responseId": response_id,
                                "connectionName": connection_name,
                            }
                        )
                        # Stop streaming; the client will call /api/continue
                        return

                    # Handle oauth_consent_request embedded as a key in data
                    elif "oauth_consent_request" in data:
                        consent_obj = data["oauth_consent_request"]
                        consent_link = consent_obj.get("consent_link", "")
                        connection_name = consent_obj.get("connection_name", "")
                        _conversations[conversation_id] = {
                            "previous_response_id": response_id
                        }
                        logger.info(
                            "OAuth consent required (embedded) — connection=%s",
                            connection_name,
                        )
                        yield _sse(
                            {
                                "type": "oauth_consent_required",
                                "consentLink": consent_link,
                                "responseId": response_id,
                                "connectionName": connection_name,
                            }
                        )
                        return

                    # ── Response completed → persist response_id ────────────
                    elif event_type == "response.completed":
                        resp_obj = data.get("response", {})
                        response_id = resp_obj.get("id", response_id)
                        _conversations[conversation_id] = {
                            "previous_response_id": response_id
                        }
                        logger.info("Response completed: %s", response_id)

                    # ── Error event ──────────────────────────────────────────
                    elif event_type == "error":
                        err = data.get("error", data)
                        msg = (
                            err.get("message", str(err))
                            if isinstance(err, dict)
                            else str(err)
                        )
                        logger.error("Foundry error event: %s", msg)
                        yield _sse({"type": "error", "message": msg})

            yield _sse({"type": "done", "responseId": response_id or ""})

        except httpx.HTTPStatusError as exc:
            try:
                body_preview = exc.response.text[:300]
            except Exception:
                body_preview = ""
            msg = f"Foundry API HTTP {exc.response.status_code}: {body_preview}"
            logger.error(msg)
            yield _sse({"type": "error", "message": msg})

        except Exception as exc:
            msg = f"Unexpected error: {exc}"
            logger.exception(msg)
            yield _sse({"type": "error", "message": msg})


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/")
async def health():
    return {
        "status": "ok",
        "service": "foundry-oauth-ui-backend",
        "version": "1.0.0",
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Start a new conversation turn (or continue an existing one).

    If the conversation already has a `previous_response_id` stored
    (from a prior turn), it is included automatically so the agent
    maintains context across turns.

    Returns: text/event-stream (SSE)
    """
    project_endpoint = os.environ.get("PROJECT_ENDPOINT", "")
    agent_id = os.environ.get("AGENT_ID", "")
    if not project_endpoint or not agent_id:
        raise HTTPException(
            status_code=500,
            detail="PROJECT_ENDPOINT and AGENT_ID environment variables must be set.",
        )

    state = _conversations.get(req.conversationId, {})
    previous_response_id = state.get("previous_response_id")

    return StreamingResponse(
        _stream_response(
            project_endpoint=project_endpoint,
            agent_id=agent_id,
            user_message=req.userMessage,
            previous_response_id=previous_response_id,
            conversation_id=req.conversationId,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


@app.post("/api/continue")
async def continue_after_consent(req: ContinueRequest):
    """
    Resume a paused conversation after the user has completed OAuth consent.

    The stored `previous_response_id` is sent to Foundry so the agent can
    pick up exactly where it left off before requesting consent.

    Reference:
      https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication

    Returns: text/event-stream (SSE)
    """
    project_endpoint = os.environ.get("PROJECT_ENDPOINT", "")
    agent_id = os.environ.get("AGENT_ID", "")
    if not project_endpoint or not agent_id:
        raise HTTPException(
            status_code=500,
            detail="PROJECT_ENDPOINT and AGENT_ID environment variables must be set.",
        )

    state = _conversations.get(req.conversationId)
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"No conversation found for conversationId={req.conversationId}",
        )

    previous_response_id = state.get("previous_response_id")
    if not previous_response_id:
        raise HTTPException(
            status_code=400,
            detail="No previous_response_id stored; cannot continue.",
        )

    logger.info(
        "Continuing conversation %s with previous_response_id=%s",
        req.conversationId,
        previous_response_id,
    )

    return StreamingResponse(
        _stream_response(
            project_endpoint=project_endpoint,
            agent_id=agent_id,
            user_message=None,  # No new message; resume the paused run
            previous_response_id=previous_response_id,
            conversation_id=req.conversationId,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
