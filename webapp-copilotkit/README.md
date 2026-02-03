# Web App - CopilotKit × Foundry Agent V2

This is a Next.js web application that provides a chat interface using CopilotKit UI, connected to Azure AI Foundry Agent V2 API.

## Features

- **CopilotKit UI**: Modern chat interface with streaming support
- **Foundry Agent V2 API**: Integration with Azure AI Foundry using Threads/Runs/Messages model
- **Session Management**: Maintains conversation context across messages
- **OAuth Identity Passthrough**: Transparent user authentication flow handled by Foundry

## Prerequisites

- Node.js 18 or higher
- npm or yarn
- Azure AI Foundry Project with Agent configured
- Agent ID from Foundry

## Installation

1. Install dependencies:
```bash
cd webapp-copilotkit
npm install
```

2. Configure environment variables:
```bash
cp .env.local.template .env.local
```

Edit `.env.local` and fill in your values:
```env
FOUNDRY_ENDPOINT=https://your-project.eastus.api.azureml.ms
FOUNDRY_API_KEY=your_api_key_here
FOUNDRY_AGENT_ID=your_agent_id_here
FOUNDRY_PROJECT_ID=your_project_id_here
```

## Development

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Build and Deploy

### Build for production:

```bash
npm run build
npm start
```

### Deploy to Azure App Service:

1. Create an App Service (Node.js 18 LTS):
```bash
az webapp create \
  --resource-group <resource-group> \
  --plan <app-service-plan> \
  --name <app-name> \
  --runtime "NODE:18-lts"
```

2. Configure environment variables in App Service:
```bash
az webapp config appsettings set \
  --resource-group <resource-group> \
  --name <app-name> \
  --settings \
    FOUNDRY_ENDPOINT="https://your-project.eastus.api.azureml.ms" \
    FOUNDRY_API_KEY="your_api_key" \
    FOUNDRY_AGENT_ID="your_agent_id" \
    FOUNDRY_PROJECT_ID="your_project_id"
```

3. Deploy using ZIP deployment:
```bash
npm run build
zip -r app.zip .next package.json package-lock.json next.config.js
az webapp deployment source config-zip \
  --resource-group <resource-group> \
  --name <app-name> \
  --src app.zip
```

Or use GitHub Actions for continuous deployment.

## Project Structure

```
webapp-copilotkit/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   └── copilot/
│   │   │       └── route.ts          # API endpoint for CopilotKit
│   │   ├── layout.tsx                # Root layout
│   │   ├── page.tsx                  # Main chat page
│   │   └── globals.css               # Global styles
│   └── lib/
│       └── foundry-client.ts         # Foundry Agent V2 API client
├── package.json
├── tsconfig.json
├── next.config.js
└── tailwind.config.js
```

## API Endpoints

### POST /api/copilot

Main CopilotKit endpoint that forwards messages to Foundry Agent.

**Request:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Who am I?"
    }
  ],
  "sessionId": "optional-session-id"
}
```

**Response:**
```json
{
  "message": {
    "role": "assistant",
    "content": "Response from Foundry Agent"
  },
  "threadId": "thread_abc123"
}
```

### GET /api/copilot

Health check endpoint.

## How It Works

1. **User sends message** → CopilotKit UI
2. **UI calls** → `/api/copilot` endpoint
3. **API creates/uses** → Foundry Thread
4. **API adds** → User message to thread
5. **API creates** → Run with Agent ID
6. **API polls** → Run status until completion
7. **Agent may call** → MCP tools with OAuth tokens
8. **API retrieves** → Assistant messages
9. **API returns** → Response to CopilotKit
10. **UI displays** → Assistant response

## OAuth Identity Passthrough Flow

When the agent needs to call MCP tools:

1. **First request**: Foundry initiates OAuth flow
2. **User consent**: Microsoft sign-in page appears (in agent context)
3. **Token obtained**: Foundry gets user delegated access token
4. **MCP call**: Token is passed to MCP server via APIM
5. **Subsequent requests**: Foundry reuses token until expiration

## Troubleshooting

### "Missing Foundry configuration" error
- Check that all environment variables are set in `.env.local`
- Ensure values don't have quotes or extra spaces
- Restart the dev server after changing environment variables

### "Failed to create thread" error
- Verify `FOUNDRY_ENDPOINT` is correct
- Check that `FOUNDRY_API_KEY` is valid
- Ensure the project endpoint is accessible

### "Run did not complete in time" error
- Agent execution is taking too long
- Check Foundry agent configuration
- Review agent instructions and tool definitions

### OAuth consent screen not appearing
- This happens in the agent context, not in the web UI
- Check Foundry agent logs for OAuth flow details
- Verify OAuth connection is configured in Foundry

## Learn More

- [CopilotKit Documentation](https://docs.copilotkit.ai/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Azure AI Foundry](https://learn.microsoft.com/azure/ai-studio/)

## License

See LICENSE file in the root directory.
