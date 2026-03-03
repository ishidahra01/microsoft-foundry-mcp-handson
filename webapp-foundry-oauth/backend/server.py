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
    {"type": "mcp_approval_required", "approvalRequestId": "...",
                                                                        "serverLabel": "...", "toolName": "..."}
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
from typing import Any, AsyncIterator, Optional

import httpx
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def _extract_text_from_response(response_obj: dict[str, Any]) -> str:
    """Extract assistant text from a Responses API response payload."""
    output_items = response_obj.get("output", [])
    if not isinstance(output_items, list):
        return ""

    chunks: list[str] = []
    for item in output_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type in ("output_text", "text", "input_text"):
                text = part.get("text", "")
                if isinstance(text, str) and text:
                    chunks.append(text)
    return "".join(chunks)

# ──────────────────────────────────────────────────────────────────────────────
# In-memory conversation state
# conversationId -> {
#   previous_response_id: str | None,
#   pending_approvals: list[dict]
# }
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
    approve: bool = True
    approvalRequestIds: Optional[list[str]] = None


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
    agent_id: Optional[str],
    agent_reference_name: Optional[str],
    user_message: Optional[str],
    previous_response_id: Optional[str],
    approval_inputs: Optional[list[dict[str, Any]]],
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
        "stream": True,
    }

    if agent_reference_name:
        body["agent_reference"] = {
            "type": "agent_reference",
            "name": agent_reference_name,
        }
    elif agent_id:
        body["model"] = agent_id
    else:
        raise ValueError("Either agent_id or agent_reference_name is required.")

    if previous_response_id:
        # Continue the previous response (after OAuth consent or multi-turn)
        # Reference: https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication
        body["previous_response_id"] = previous_response_id

    if approval_inputs is not None:
        body["input"] = approval_inputs

    if user_message:
        user_input_item = {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": user_message}],
        }
        if "input" in body and isinstance(body["input"], list):
            body["input"].append(user_input_item)
        else:
            body["input"] = [user_input_item]

    if previous_response_id and "input" not in body:
        body["input"] = []

    url = f"{project_endpoint.rstrip('/')}/openai/v1/responses"
    logger.info(
        "Calling Foundry Responses API url=%s previous_response_id=%s mode=%s",
        url,
        previous_response_id,
        "agent_reference" if agent_reference_name else "model",
    )

    # ── SSE helper ───────────────────────────────────────────────────────────
    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    # ── Mutable state across the stream ─────────────────────────────────────
    response_id: Optional[str] = None
    emitted_text = False
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
                            emitted_text = True
                            yield _sse({"type": "text.delta", "delta": delta})

                    elif event_type == "response.content_part.delta":
                        delta = data.get("delta", {})
                        text = (
                            delta.get("text", "")
                            if isinstance(delta, dict)
                            else str(delta)
                        )
                        if text:
                            emitted_text = True
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
                        elif item.get("type") == "oauth_consent_request":
                            consent_link = item.get("consent_link", "")
                            connection_name = item.get("server_label", "")
                            state = _conversations.setdefault(
                                conversation_id,
                                {
                                    "previous_response_id": None,
                                    "pending_approvals": [],
                                },
                            )
                            state["previous_response_id"] = response_id
                            logger.info(
                                "OAuth consent required (output item) — connection=%s response_id=%s",
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
                            return
                        elif item.get("type") == "mcp_approval_request":
                            approval_id = item.get("id", "")
                            approval_payload = {
                                "id": approval_id,
                                "serverLabel": item.get("server_label", ""),
                                "toolName": item.get("name", ""),
                                "arguments": item.get("arguments", "{}"),
                            }
                            state = _conversations.setdefault(
                                conversation_id,
                                {
                                    "previous_response_id": response_id or previous_response_id,
                                    "pending_approvals": [],
                                },
                            )
                            state["previous_response_id"] = response_id or previous_response_id
                            state["pending_approvals"] = [approval_payload]
                            logger.info(
                                "MCP approval required: server=%s tool=%s approval_id=%s",
                                approval_payload["serverLabel"],
                                approval_payload["toolName"],
                                approval_id,
                            )
                            yield _sse(
                                {
                                    "type": "mcp_approval_required",
                                    "approvalRequestId": approval_id,
                                    "serverLabel": approval_payload["serverLabel"],
                                    "toolName": approval_payload["toolName"],
                                    "arguments": approval_payload["arguments"],
                                    "responseId": response_id,
                                }
                            )
                            return

                    elif event_type == "mcp_approval_request":
                        approval_id = data.get("id", "")
                        approval_payload = {
                            "id": approval_id,
                            "serverLabel": data.get("server_label", ""),
                            "toolName": data.get("name", ""),
                            "arguments": data.get("arguments", "{}"),
                        }
                        state = _conversations.setdefault(
                            conversation_id,
                            {
                                "previous_response_id": response_id or previous_response_id,
                                "pending_approvals": [],
                            },
                        )
                        state["previous_response_id"] = response_id or previous_response_id
                        state["pending_approvals"] = [approval_payload]
                        logger.info(
                            "MCP approval required (direct event): server=%s tool=%s approval_id=%s",
                            approval_payload["serverLabel"],
                            approval_payload["toolName"],
                            approval_id,
                        )
                        yield _sse(
                            {
                                "type": "mcp_approval_required",
                                "approvalRequestId": approval_id,
                                "serverLabel": approval_payload["serverLabel"],
                                "toolName": approval_payload["toolName"],
                                "arguments": approval_payload["arguments"],
                                "responseId": response_id,
                            }
                        )
                        return

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
                    elif event_type in (
                        "oauth_consent_request",
                        "response.oauth_consent_requested",
                    ):
                        consent_link = data.get("consent_link", "")
                        connection_name = (
                            data.get("connection_name", "")
                            or data.get("server_label", "")
                        )
                        # Store response_id for the upcoming /api/continue call
                        state = _conversations.setdefault(
                            conversation_id,
                            {
                                "previous_response_id": None,
                                "pending_approvals": [],
                            },
                        )
                        state["previous_response_id"] = response_id
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
                        state = _conversations.setdefault(
                            conversation_id,
                            {
                                "previous_response_id": None,
                                "pending_approvals": [],
                            },
                        )
                        state["previous_response_id"] = response_id
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
                        if not emitted_text and isinstance(resp_obj, dict):
                            final_text = _extract_text_from_response(resp_obj)
                            if final_text:
                                emitted_text = True
                                yield _sse({"type": "text.delta", "delta": final_text})
                        response_id = resp_obj.get("id", response_id)
                        state = _conversations.setdefault(
                            conversation_id,
                            {
                                "previous_response_id": None,
                                "pending_approvals": [],
                            },
                        )
                        state["previous_response_id"] = response_id
                        state["pending_approvals"] = []
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
                body_preview = (await exc.response.aread()).decode("utf-8", "ignore")[:1000]
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
    agent_id = os.environ.get("AGENT_ID", "").strip() or None
    agent_reference_name = os.environ.get("AGENT_REFERENCE_NAME", "").strip() or None
    if not project_endpoint or (not agent_id and not agent_reference_name):
        raise HTTPException(
            status_code=500,
            detail=(
                "PROJECT_ENDPOINT and either AGENT_ID or AGENT_REFERENCE_NAME "
                "environment variables must be set."
            ),
        )

    state = _conversations.get(req.conversationId, {})
    previous_response_id = state.get("previous_response_id")

    return StreamingResponse(
        _stream_response(
            project_endpoint=project_endpoint,
            agent_id=agent_id,
            agent_reference_name=agent_reference_name,
            user_message=req.userMessage,
            previous_response_id=previous_response_id,
            approval_inputs=None,
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
    agent_id = os.environ.get("AGENT_ID", "").strip() or None
    agent_reference_name = os.environ.get("AGENT_REFERENCE_NAME", "").strip() or None
    if not project_endpoint or (not agent_id and not agent_reference_name):
        raise HTTPException(
            status_code=500,
            detail=(
                "PROJECT_ENDPOINT and either AGENT_ID or AGENT_REFERENCE_NAME "
                "environment variables must be set."
            ),
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

    approval_inputs: Optional[list[dict[str, Any]]] = None
    pending_approvals = state.get("pending_approvals", [])
    if pending_approvals:
        selected_ids = req.approvalRequestIds or [
            item.get("id") for item in pending_approvals if item.get("id")
        ]
        if not selected_ids:
            raise HTTPException(
                status_code=400,
                detail="No approval_request_id available for pending MCP approval.",
            )
        approval_inputs = [
            {
                "type": "mcp_approval_response",
                "approve": req.approve,
                "approval_request_id": approval_id,
            }
            for approval_id in selected_ids
        ]
        logger.info(
            "Sending MCP approval response(s): conversation=%s approve=%s count=%d",
            req.conversationId,
            req.approve,
            len(approval_inputs),
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
            agent_reference_name=agent_reference_name,
            user_message=None,  # No new message; resume the paused run
            previous_response_id=previous_response_id,
            approval_inputs=approval_inputs,
            conversation_id=req.conversationId,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
