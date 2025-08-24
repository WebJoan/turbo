import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  OpenAIAdapter
} from '@copilotkit/runtime';
import { NextRequest } from 'next/server';
import { HttpAgent } from '@ag-ui/client';

const agnoAgent = new HttpAgent({
  url: process.env.NEXT_PUBLIC_AGNO_URL || 'http://agno:8080/agno-agent'
});

const serviceAdapter = new OpenAIAdapter();

const runtime = new CopilotRuntime({
  agents: {
    // @ts-ignore
    agnoAgent
  }
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: '/api/copilotkit'
  });
  return handleRequest(req);
};



