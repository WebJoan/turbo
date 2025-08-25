import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  OpenAIAdapter
} from '@copilotkit/runtime';
import { NextRequest } from 'next/server';
import { HttpAgent } from '@ag-ui/client';

const serviceAdapter = new OpenAIAdapter();

export const POST = async (req: NextRequest) => {
  const cookie = req.headers.get('cookie') || '';
  const authorization = req.headers.get('authorization') || '';

  const agnoAgent = new HttpAgent({
    url: process.env.NEXT_PUBLIC_AGNO_URL || 'http://agno:8080/agno-agent',
    headers: {
      ...(cookie ? { cookie } : {}),
      ...(authorization ? { authorization } : {})
    }
  });

  const runtime = new CopilotRuntime({
    agents: {
      // @ts-ignore
      agnoAgent
    }
  });

  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: '/api/copilotkit'
  });
  return handleRequest(req);
};



