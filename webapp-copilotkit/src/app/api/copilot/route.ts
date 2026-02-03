/**
 * CopilotKit API Route
 * 
 * This endpoint handles chat requests from CopilotKit UI and forwards them
 * to Azure AI Foundry Agent V2 API.
 */

import { NextRequest, NextResponse } from 'next/server';
import { sendMessage, type FoundryConfig } from '@/lib/foundry-client';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Thread storage (in production, use Redis or database)
const threadStore = new Map<string, string>();

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { messages, sessionId } = body;

    // Validate configuration
    const foundryConfig: FoundryConfig = {
      endpoint: process.env.FOUNDRY_ENDPOINT || '',
      apiKey: process.env.FOUNDRY_API_KEY || '',
      agentId: process.env.FOUNDRY_AGENT_ID || '',
      projectId: process.env.FOUNDRY_PROJECT_ID || '',
    };

    if (!foundryConfig.endpoint || !foundryConfig.apiKey || !foundryConfig.agentId) {
      return NextResponse.json(
        {
          error: 'Missing Foundry configuration. Please check environment variables.',
        },
        { status: 500 }
      );
    }

    // Get the last user message
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || lastMessage.role !== 'user') {
      return NextResponse.json(
        {
          error: 'Invalid message format',
        },
        { status: 400 }
      );
    }

    // Get or create thread ID for this session
    const threadId = sessionId ? threadStore.get(sessionId) : undefined;

    // Send message to Foundry Agent
    const result = await sendMessage(
      foundryConfig,
      lastMessage.content,
      threadId
    );

    // Store thread ID for this session
    if (sessionId && !threadStore.has(sessionId)) {
      threadStore.set(sessionId, result.threadId);
    }

    // Return response in CopilotKit format
    return NextResponse.json({
      message: {
        role: 'assistant',
        content: result.response,
      },
      threadId: result.threadId,
    });
  } catch (error: any) {
    console.error('Error processing request:', error);
    return NextResponse.json(
      {
        error: error.message || 'An error occurred while processing your request',
      },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    status: 'ok',
    message: 'CopilotKit API endpoint for Foundry Agent V2',
  });
}
