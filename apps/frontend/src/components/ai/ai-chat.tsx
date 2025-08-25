'use client';

import { CopilotChat } from '@copilotkit/react-ui';
import { useCoAgent } from '@copilotkit/react-core';
import { ToolLogs } from './tool-logs';

type AIChatProps = {
    className?: string;
};

export default function AIChat({ className }: AIChatProps) {
    const { state } = useCoAgent({ name: 'agnoAgent', initialState: {} as any });

    return (
        <div className="flex flex-col gap-3">
            <ToolLogs logs={(state as any)?.tool_logs ?? []} />
            <CopilotChat
                className={className ?? 'h-[80vh]'}
                labels={{
                    initial:
                        'Я Agno-агент. Задайте вопрос. Например: "Суммируй моё сообщение" или просто поздоровайтесь.'
                }}
            />
        </div>
    );
}


