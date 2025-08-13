"use client";

import type { FC, PropsWithChildren } from "react";
import { Thread, MessagePrimitive } from "@assistant-ui/react";
import { MarkdownText } from "@/components/MarkdownText";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";

// Wrapped MarkdownText filters unknown DOM props

export const ToolGroup: FC<
    PropsWithChildren<{ startIndex: number; endIndex: number }>
> = ({ startIndex, endIndex, children }) => {
    const toolCount = endIndex - startIndex + 1;
    return (
        <details className="my-2">
            <summary className="cursor-pointer font-medium">
                {toolCount} tool {toolCount === 1 ? "call" : "calls"}
            </summary>
            <div className="space-y-2 pl-4">{children}</div>
        </details>
    );
};

export function AssistantThread() {
    return (
        <Thread
            components={{}}
            assistantMessage={{
                components: {
                    ToolFallback,
                    Text: MarkdownText,
                },
            }}
        >
            {/* Example of passing custom parts components if/when exposed */}
            <MessagePrimitive.Content components={{ Text: MarkdownText }} />
        </Thread>
    );
}


