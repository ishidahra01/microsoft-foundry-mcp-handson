"use client";

/**
 * Foundry Agent OAuth UI — Chat Page
 *
 * Features:
 *  - Real-time streaming chat with the Foundry Agent (SSE)
 *  - MCP approval card when `require_approval=always` triggers
 *    `mcp_approval_request`
 *  - OAuth consent card when the agent needs MCP delegated access
 *    (triggered by `oauth_consent_request` from Foundry)
 *  - After consent the user clicks "Continue" which calls /api/continue
 *    with the stored `previous_response_id` to resume the run.
 *  - Collapsible tool-call log panel on the right side.
 *
 * SSE event protocol (from backend/server.py):
 *   {"type":"text.delta",            "delta":"..."}
 *   {"type":"tool.start",            "toolName":"...", "callId":"..."}
 *   {"type":"tool.end",              "toolName":"...", "callId":"..."}
 *   {"type":"tool.error",            "toolName":"...", "callId":"...", "error":"..."}
 *   {"type":"mcp_approval_required", "approvalRequestId":"...",
 *                                       "serverLabel":"...", "toolName":"..."}
 *   {"type":"oauth_consent_required","consentLink":"...",
 *                                    "responseId":"...", "connectionName":"..."}
 *   {"type":"done",                  "responseId":"..."}
 *   {"type":"error",                 "message":"..."}
 *
 * References:
 *   MCP OAuth Identity Passthrough (consent_link / previous_response_id):
 *     https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication
 */

import { useEffect, useRef, useState } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

interface ToolLog {
  id: string;
  toolName: string;
  callId: string;
  status: "running" | "done" | "error";
  error?: string;
  startedAt: Date;
}

interface ConsentInfo {
  consentLink: string;
  connectionName: string;
  conversationId: string;
}

interface ApprovalInfo {
  approvalRequestId: string;
  serverLabel: string;
  toolName: string;
  arguments: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

/** Parse an SSE ReadableStream and yield parsed JSON objects. */
async function* readSSE(
  response: Response
): AsyncGenerator<Record<string, unknown>> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const jsonStr = trimmed.slice(5).trim();
      if (jsonStr === "[DONE]") return;
      try {
        yield JSON.parse(jsonStr) as Record<string, unknown>;
      } catch {
        // Non-JSON data line — skip
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────
export default function ChatPage() {
  // Stable conversation ID for the session
  const conversationId = useRef<string>(uid());

  const [messages, setMessages] = useState<Message[]>([]);
  const [toolLogs, setToolLogs] = useState<ToolLog[]>([]);
  const [approvalInfo, setApprovalInfo] = useState<ApprovalInfo | null>(null);
  const [consentInfo, setConsentInfo] = useState<ConsentInfo | null>(null);

  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [toolPanelOpen, setToolPanelOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── SSE consumer ──────────────────────────────────────────────────────────
  /**
   * Reads the SSE stream from `response` and applies events to component state.
   * Returns when the stream ends or when `oauth_consent_required` is received
   * (the latter stops streaming and shows the consent card instead).
   */
  async function consumeStream(response: Response): Promise<void> {
    const msgId = uid();

    // Add an empty assistant bubble that will be filled incrementally
    setMessages((prev) => [
      ...prev,
      { id: msgId, role: "assistant", content: "", streaming: true },
    ]);

    const finishMessage = (append?: string) =>
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? {
                ...m,
                content: m.content + (append ?? ""),
                streaming: false,
              }
            : m
        )
      );

    for await (const event of readSSE(response)) {
      const type = event.type as string;

      if (type === "text.delta") {
        const delta = event.delta as string;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId ? { ...m, content: m.content + delta } : m
          )
        );
      } else if (type === "tool.start") {
        const { toolName, callId } = event as {
          toolName: string;
          callId: string;
        };
        setToolLogs((prev) => [
          ...prev,
          {
            id: uid(),
            toolName,
            callId,
            status: "running",
            startedAt: new Date(),
          },
        ]);
        setToolPanelOpen(true);
      } else if (type === "tool.end") {
        const { callId } = event as { callId: string };
        setToolLogs((prev) =>
          prev.map((t) =>
            t.callId === callId ? { ...t, status: "done" } : t
          )
        );
      } else if (type === "tool.error") {
        const { callId, error } = event as { callId: string; error: string };
        setToolLogs((prev) =>
          prev.map((t) =>
            t.callId === callId ? { ...t, status: "error", error } : t
          )
        );
      } else if (type === "mcp_approval_required") {
        const { approvalRequestId, serverLabel, toolName, arguments: args } =
          event as {
            approvalRequestId: string;
            serverLabel: string;
            toolName: string;
            arguments: string;
          };

        finishMessage("Waiting for MCP tool approval...");

        setApprovalInfo({
          approvalRequestId,
          serverLabel,
          toolName,
          arguments: args ?? "{}",
        });

        return;
      } else if (type === "oauth_consent_required") {
        /**
         * The Foundry agent requires OAuth consent for an MCP connection.
         *
         * 1. We update the assistant message to indicate consent is needed.
         * 2. We show the ConsentCard so the user can open the popup.
         * 3. After the user grants access and clicks "Continue", the app
         *    calls /api/continue with the conversationId so the backend can
         *    resume using `previous_response_id`.
         *
         * Reference:
         *   https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication
         */
        const { consentLink, connectionName } = event as {
          consentLink: string;
          connectionName: string;
        };

        finishMessage("Waiting for OAuth consent...");

        setConsentInfo({
          consentLink,
          connectionName,
          conversationId: conversationId.current,
        });

        // Stop consuming the stream — the run is paused server-side
        return;
      } else if (type === "error") {
        const { message } = event as { message: string };
        finishMessage(`\n\n⚠️ Error: ${message}`);
        return;
      } else if (type === "done") {
        // Normal completion
        finishMessage();
        return;
      }
    }

    finishMessage();
  }

  // ── Send a user message ───────────────────────────────────────────────────
  async function sendMessage(): Promise<void> {
    const text = input.trim();
    if (!text || streaming) return;

    setInput("");
    setApprovalInfo(null);
    setConsentInfo(null);
    setMessages((prev) => [
      ...prev,
      { id: uid(), role: "user", content: text },
    ]);
    setStreaming(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversationId: conversationId.current,
          userMessage: text,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }

      await consumeStream(res);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: "assistant",
          content: `⚠️ ${err instanceof Error ? err.message : String(err)}`,
        },
      ]);
    } finally {
      setStreaming(false);
    }
  }

  // ── Continue after consent ────────────────────────────────────────────────
  /**
   * Called after the user has granted OAuth consent in the popup.
   *
   * Sends a POST /api/continue request; the backend uses the stored
   * `previous_response_id` to resume the Foundry run.
   *
   * Reference:
   *   https://learn.microsoft.com/azure/ai-foundry/agents/how-to/mcp-authentication
   */
  async function continueConversation(options?: {
    approve?: boolean;
    approvalRequestIds?: string[];
    clearConsent?: boolean;
  }): Promise<void> {
    if (!consentInfo && !approvalInfo) return;
    if (options?.clearConsent) {
      setConsentInfo(null);
    }
    setStreaming(true);

    try {
      const res = await fetch("/api/continue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversationId: conversationId.current,
          approve: options?.approve ?? true,
          approvalRequestIds: options?.approvalRequestIds,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }

      await consumeStream(res);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: "assistant",
          content: `⚠️ Failed to continue: ${
            err instanceof Error ? err.message : String(err)
          }`,
        },
      ]);
    } finally {
      setStreaming(false);
    }
  }

  async function approveMcpCall(approve: boolean): Promise<void> {
    if (!approvalInfo) return;
    const approvalRequestId = approvalInfo.approvalRequestId;
    setApprovalInfo(null);

    await continueConversation({
      approve,
      approvalRequestIds: [approvalRequestId],
      clearConsent: false,
    });
  }

  async function continueAfterConsent(): Promise<void> {
    await continueConversation({ clearConsent: true });
  }

  // ── Open consent popup ────────────────────────────────────────────────────
  function openConsentPopup(): void {
    if (!consentInfo?.consentLink) return;
    const popup = window.open(
      consentInfo.consentLink,
      "foundry-oauth-consent",
      "width=600,height=720,scrollbars=yes,resizable=yes"
    );
    if (!popup) {
      alert(
        "Popup was blocked by your browser.\n" +
          "Please allow popups for this page and try again."
      );
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* ── Main chat column ─────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <header className="flex-shrink-0 border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-semibold text-gray-900">
                Foundry Agent + MCP OAuth UI
              </h1>
              <p className="mt-0.5 text-sm text-gray-500">
                Azure AI Foundry · OAuth Identity Passthrough · Tool Logs
              </p>
            </div>
            {/* Tool log toggle (visible on small screens) */}
            <button
              onClick={() => setToolPanelOpen((o) => !o)}
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
              title="Toggle tool logs"
            >
              <span>🛠️</span>
              <span className="hidden sm:inline">Tool Logs</span>
              {toolLogs.some((t) => t.status === "running") && (
                <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
              )}
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center text-gray-400 space-y-3">
              <div className="text-5xl">🤖</div>
              <p className="text-lg font-medium">
                Ask the Foundry agent anything
              </p>
              <div className="text-sm space-y-1">
                <p>Try: &ldquo;Who am I?&rdquo;</p>
                <p>Try: &ldquo;What&apos;s my job title?&rdquo;</p>
                <p>Try: &ldquo;List my recent emails&rdquo;</p>
              </div>
              <p className="text-xs text-gray-300 max-w-xs">
                The first MCP tool call may ask for OAuth consent — this is
                expected and only happens once per connection.
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-2xl rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-white border border-gray-200 text-gray-800 shadow-sm"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.streaming && (
                  <span className="inline-block w-[2px] h-4 bg-current animate-blink ml-0.5 align-middle" />
                )}
              </div>
            </div>
          ))}

          {/* MCP Approval Card */}
          {approvalInfo && (
            <div className="flex justify-start">
              <ApprovalCard
                approvalInfo={approvalInfo}
                onApprove={() => approveMcpCall(true)}
                onReject={() => approveMcpCall(false)}
                disabled={streaming}
              />
            </div>
          )}

          {/* OAuth Consent Card */}
          {consentInfo && (
            <div className="flex justify-start">
              <ConsentCard
                consentInfo={consentInfo}
                onOpenPopup={openConsentPopup}
                onContinue={continueAfterConsent}
                disabled={streaming}
              />
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="flex-shrink-0 border-t border-gray-200 bg-white px-4 py-4">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder={
                streaming ? "Agent is responding..." : "Send a message…"
              }
              disabled={streaming}
              className="flex-1 rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none placeholder-gray-400
                         focus:border-blue-500 focus:ring-1 focus:ring-blue-500
                         disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed"
            />
            <button
              onClick={sendMessage}
              disabled={streaming || !input.trim()}
              className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white
                         hover:bg-blue-700 active:bg-blue-800
                         disabled:opacity-50 disabled:cursor-not-allowed
                         transition-colors"
            >
              {streaming ? (
                <span className="flex items-center gap-1.5">
                  <LoadingSpinner />
                </span>
              ) : (
                "Send"
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ── Tool logs panel ───────────────────────────────────────────────── */}
      <aside
        className={`flex-shrink-0 border-l border-gray-200 bg-white transition-all duration-200 ${
          toolPanelOpen ? "w-72" : "w-0 overflow-hidden"
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-gray-700">
              🛠️ Tool Calls
            </h2>
            <button
              onClick={() => setToolPanelOpen(false)}
              className="text-gray-400 hover:text-gray-600 text-lg leading-none"
              title="Close"
            >
              ×
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {toolLogs.length === 0 ? (
              <p className="text-center text-xs text-gray-400 mt-6">
                No tool calls yet.
                <br />
                Tool executions will appear here.
              </p>
            ) : (
              [...toolLogs].reverse().map((log) => (
                <ToolLogCard key={log.id} log={log} />
              ))
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function ApprovalCard({
  approvalInfo,
  onApprove,
  onReject,
  disabled,
}: {
  approvalInfo: ApprovalInfo;
  onApprove: () => void;
  onReject: () => void;
  disabled: boolean;
}) {
  return (
    <div className="max-w-xl w-full rounded-2xl border border-blue-300 bg-blue-50 p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="text-2xl select-none" aria-hidden>
          ✅
        </span>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-blue-900 text-sm">
            MCP Tool Approval Required
          </h3>

          <p className="mt-1 text-xs text-blue-700">
            Server: <span className="font-mono font-medium">{approvalInfo.serverLabel || "(unknown)"}</span>
          </p>
          <p className="mt-0.5 text-xs text-blue-700">
            Tool: <span className="font-mono font-medium">{approvalInfo.toolName || "(unknown)"}</span>
          </p>

          <p className="mt-2 text-sm text-blue-800 leading-relaxed">
            This MCP call requires explicit approval before it can run. Review
            and choose whether to continue.
          </p>

          {approvalInfo.arguments && approvalInfo.arguments !== "{}" && (
            <pre className="mt-2 max-h-32 overflow-auto rounded-lg border border-blue-200 bg-white p-2 text-xs text-blue-900">
              {approvalInfo.arguments}
            </pre>
          )}

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={onApprove}
              disabled={disabled}
              className="inline-flex items-center gap-1.5 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white
                         hover:bg-green-700 active:bg-green-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              ✅ Approve and Continue
            </button>

            <button
              onClick={onReject}
              disabled={disabled}
              className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white
                         hover:bg-red-700 active:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              ❌ Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * OAuth consent card shown when the Foundry agent requires delegated access.
 *
 * The user clicks "Open Consent Page" to open the OAuth authorization URL in a
 * popup, then clicks "I've Consented — Continue" to resume the agent run via
 * /api/continue (which uses `previous_response_id` internally).
 */
function ConsentCard({
  consentInfo,
  onOpenPopup,
  onContinue,
  disabled,
}: {
  consentInfo: ConsentInfo;
  onOpenPopup: () => void;
  onContinue: () => void;
  disabled: boolean;
}) {
  return (
    <div className="max-w-xl w-full rounded-2xl border border-amber-300 bg-amber-50 p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="text-2xl select-none" aria-hidden>
          🔐
        </span>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-amber-900 text-sm">
            OAuth Consent Required
          </h3>

          {consentInfo.connectionName && (
            <p className="mt-0.5 text-xs text-amber-700">
              Connection:{" "}
              <span className="font-mono font-medium">
                {consentInfo.connectionName}
              </span>
            </p>
          )}

          <p className="mt-2 text-sm text-amber-800 leading-relaxed">
            The agent needs your permission to access a connected service via
            MCP. Please open the consent page and sign in, then return here and
            click{" "}
            <strong>&ldquo;I&apos;ve Consented&rdquo;</strong> to continue.
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={onOpenPopup}
              disabled={disabled}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white
                         hover:bg-amber-600 active:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              🔓 Open Consent Page
            </button>

            <button
              onClick={onContinue}
              disabled={disabled}
              className="inline-flex items-center gap-1.5 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white
                         hover:bg-green-700 active:bg-green-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              ✅ I&apos;ve Consented — Continue
            </button>
          </div>

          <p className="mt-2 text-xs text-amber-600">
            After approving in the popup, click &ldquo;Continue&rdquo; to
            resume. The agent will pick up exactly where it left off.
          </p>
        </div>
      </div>
    </div>
  );
}

function ToolLogCard({ log }: { log: ToolLog }) {
  const statusIcon =
    log.status === "running" ? "⏳" : log.status === "error" ? "❌" : "✅";

  const borderColor =
    log.status === "running"
      ? "border-blue-200 bg-blue-50"
      : log.status === "error"
      ? "border-red-200 bg-red-50"
      : "border-green-200 bg-green-50";

  return (
    <div className={`rounded-lg border p-2.5 text-xs ${borderColor}`}>
      <div className="flex items-center gap-1.5 font-medium font-mono">
        <span>{statusIcon}</span>
        <span className="truncate text-gray-800">{log.toolName}</span>
        {log.status === "running" && (
          <span className="ml-auto flex-shrink-0">
            <LoadingSpinner size="sm" />
          </span>
        )}
      </div>

      <div className="mt-0.5 font-mono text-gray-500 truncate">
        {log.callId.slice(0, 16)}
        {log.callId.length > 16 ? "…" : ""}
      </div>

      {log.error && (
        <div className="mt-1 text-red-600 break-words">{log.error}</div>
      )}

      <div className="mt-1 text-gray-400">
        {log.startedAt.toLocaleTimeString()}
      </div>
    </div>
  );
}

function LoadingSpinner({ size = "md" }: { size?: "sm" | "md" }) {
  const dim = size === "sm" ? "h-3 w-3" : "h-4 w-4";
  return (
    <svg
      className={`${dim} animate-spin text-current`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}
