'use client';

import { CopilotChat } from '@copilotkit/react-ui';

type AIChatProps = {
    className?: string;
};

export default function AIChat({ className }: AIChatProps) {
    return (
        <CopilotChat
            className={className ?? 'h-[80vh]'}
            labels={{
                initial:
                    'Я Agno-агент. Задайте вопрос. Например: "Суммируй моё сообщение" или просто поздоровайтесь.'
            }}
        />
    );
}


