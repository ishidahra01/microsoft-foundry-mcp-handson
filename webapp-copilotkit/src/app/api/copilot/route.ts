import { DefaultAzureCredential } from "@azure/identity";
import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotEndpointSingleRoute } from "@copilotkitnext/runtime";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ENDPOINT_PATH = "/api/copilot";
const DEFAULT_AGENT_NAME = "foundry";
const DEFAULT_SCOPE = "https://ai.azure.com/.default";

function getAgentUrl(): string {
  const agentUrl =
    process.env.FOUNDRY_AGENT_URL ||
    process.env.AGENT_URL ||
    process.env.FOUNDRY_ENDPOINT;

  if (!agentUrl) {
    throw new Error(
      "Missing agent URL. Set FOUNDRY_AGENT_URL (preferred), AGENT_URL, or FOUNDRY_ENDPOINT."
    );
  }

  return agentUrl;
}

async function getAuthorizationHeader(): Promise<string | undefined> {
  const authMode = (process.env.FOUNDRY_AUTH_MODE || "entra").toLowerCase();

  if (authMode === "none") {
    return undefined;
  }

  if (authMode === "bearer") {
    const token = process.env.FOUNDRY_BEARER_TOKEN;
    if (!token) {
      throw new Error("FOUNDRY_AUTH_MODE=bearer requires FOUNDRY_BEARER_TOKEN.");
    }
    return `Bearer ${token}`;
  }

  const scope = process.env.FOUNDRY_SCOPE || DEFAULT_SCOPE;
  const credential = new DefaultAzureCredential();
  const token = await credential.getToken(scope);

  if (!token?.token) {
    throw new Error(`Failed to acquire access token for scope: ${scope}`);
  }

  return `Bearer ${token.token}`;
}

async function createRuntime(): Promise<CopilotRuntime> {
  const agentName = process.env.COPILOTKIT_AGENT_NAME || DEFAULT_AGENT_NAME;
  const agentUrl = getAgentUrl();
  const authHeader = await getAuthorizationHeader();

  const headers: Record<string, string> = {};
  if (authHeader) {
    headers.Authorization = authHeader;
  }

  return new CopilotRuntime({
    agents: {
      [agentName]: new HttpAgent({
        url: agentUrl,
        headers,
      }),
    },
  });
}

async function handle(request: Request): Promise<Response> {
  try {
    const runtimeInstance = await createRuntime();
    const app = createCopilotEndpointSingleRoute({
      runtime: runtimeInstance,
      basePath: ENDPOINT_PATH,
    });
    return app.fetch(request);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return Response.json({ error: message }, { status: 500 });
  }
}

export const POST = handle;
export const GET = handle;
export const OPTIONS = handle;
