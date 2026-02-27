'use client';

import { CopilotKit } from '@copilotkit/react-core';
import { CopilotChat } from '@copilotkit/react-ui';
import '@copilotkit/react-ui/styles.css';

export default function Home() {
  return (
    <CopilotKit runtimeUrl="/api/copilot" agent="foundry">
      <main className="flex min-h-screen flex-col items-center justify-between p-24">
        <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm">
          <h1 className="text-4xl font-bold text-center mb-8">
            CopilotKit × Foundry Agent V2
          </h1>
          <p className="text-center mb-8 text-gray-600">
            Azure AI Foundry Agent with OAuth Identity Passthrough MCP
          </p>
          
          <div className="bg-white shadow-lg rounded-lg p-6 mb-8">
            <h2 className="text-xl font-semibold mb-4">About This Demo</h2>
            <ul className="list-disc list-inside space-y-2 text-gray-700">
              <li>Chat UI powered by CopilotKit</li>
              <li>Backend: Azure AI Foundry Agent V2 API</li>
              <li>MCP Server: Azure Functions with OAuth Identity Passthrough</li>
              <li>First request triggers Microsoft sign-in via Foundry</li>
              <li>MCP tools can access Microsoft Graph API with user delegation</li>
            </ul>
          </div>

          <div className="h-[600px] border-2 border-gray-200 rounded-lg overflow-hidden">
            <CopilotChat
              labels={{
                title: 'Ask me anything',
                initial: 'Hello! I can help you with various tasks. Try asking me "Who am I?" to test the OAuth Identity Passthrough!',
              }}
            />
          </div>

          <div className="mt-8 p-4 bg-blue-50 rounded-lg">
            <h3 className="font-semibold mb-2">Try these examples:</h3>
            <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
              <li>"Who am I?" - Uses MCP tool to call Microsoft Graph API</li>
              <li>"What's my job title?" - Retrieves your profile information</li>
              <li>"Tell me about OAuth Identity Passthrough" - General question</li>
            </ul>
          </div>
        </div>
      </main>
    </CopilotKit>
  );
}
