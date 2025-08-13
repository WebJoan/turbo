"use client";

import {
  AssistantRuntimeProvider,
  useEdgeRuntime,
  useAssistantInstructions,
  makeAssistantTool,
} from "@assistant-ui/react";
import { MarkdownText } from "@/components/MarkdownText";
import { z } from "zod";
import { StockPriceToolUI } from "./StockPriceToolUI";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { AgentActivityBar } from "./AgentActivityBar";
import { ToolLogPanel } from "./ToolLogPanel";
import { Thread } from "@assistant-ui/react";
import { MetalPriceToolUI } from "./MetalPriceToolUI";
import { DuckSearchToolUI } from "./DuckSearchToolUI";

// Wrapped MarkdownText filters unknown DOM props

// Пример: объявляем инструменты как компоненты для удобного переиспользования
const RefreshPageTool = makeAssistantTool({
  toolName: "refresh_page",
  description: "Перезагрузить страницу",
  parameters: z.object({}).strict(),
  execute: async () => {
    window.location.reload();
    return { ok: true } as const;
  },
});

const SubmitFormTool = makeAssistantTool({
  toolName: "submitForm",
  description: "Отправка формы на фронтенде (демо)",
  parameters: z.object({
    email: z.string().email(),
    name: z.string().min(1),
  }),
  execute: async ({ email, name }) => {
    await new Promise((r) => setTimeout(r, 500));
    return { success: true, email, name } as const;
  },
});

function AssistantUI() {
  useAssistantInstructions("Ты — полезный русскоязычный ассистент. Отвечай кратко и по делу. Если пользователь просит найти товар, то используй инструмент search_products_smart. Если пользователь спросит 'чей товр?/кто менеджер?/кто отвечает за?' в контексте вопроса про товар, то найди товар через search_products_smart и там возьми его менеджера, назови его имя и фамилию. Когда пользователь попросит создать RFQ, то сначала сделай поиск клиента в базе данных клиентов, а потом так же поищи каждый товар в базе даных и правильно заполни RFQ.");

  return (
    <>
      {/* Рендер Thread с Markdown и кастомным ToolFallback */}
      <Thread
        assistantMessage={{
          components: {
            Text: MarkdownText,
            ToolFallback,
          },
        }}
      />

      {/* Подключаем инструменты к ассистенту через компоненты */}
      <RefreshPageTool />
      <SubmitFormTool />
    </>
  );
}

export function MyAssistant() {
  const runtime = useEdgeRuntime({
    api: process.env.NEXT_PUBLIC_CHAT_API ?? "/api/chat",
    unstable_AISDKInterop: true,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="mx-auto grid h-dvh max-w-6xl grid-cols-1 gap-4 p-3 md:p-6">
        <section className="flex min-h-0 flex-col rounded-xl border border-gray-200 bg-white p-3 shadow-sm md:p-4">
          <div className="mb-2 border-b border-gray-100 pb-2">
            <h1 className="text-base font-semibold text-gray-900 md:text-lg">Диалог</h1>
          </div>
          <div className="min-h-0 flex-1 space-y-3 overflow-auto">
            <AssistantUI />
            {/* Панель статуса и лога инструментов прямо под окном AI */}
            <div className="space-y-2">
              <AgentActivityBar variant="inline" />
              <ToolLogPanel variant="inline" title="Лог инструментов" />
            </div>
            <StockPriceToolUI />
            <MetalPriceToolUI />
            <DuckSearchToolUI />
          </div>
        </section>
      </div>
    </AssistantRuntimeProvider>
  );
}
