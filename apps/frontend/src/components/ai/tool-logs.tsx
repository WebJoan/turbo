"use client";

import { Check } from "lucide-react";
import React from "react";

export interface ToolLogItem {
    id: string | number;
    message: string;
    status: "processing" | "completed" | "error";
}

export function ToolLogs({ logs }: { logs: ToolLogItem[] }) {
    if (!Array.isArray(logs) || logs.length === 0) return null;

    return (
        <div className="flex flex-col gap-2 p-2">
            {logs.map((log) => (
                <div
                    key={log.id}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2 border text-sm font-medium shadow-sm transition-colors
            ${log.status === "processing"
                            ? "bg-yellow-50 border-yellow-200 text-yellow-800"
                            : log.status === "completed"
                                ? "bg-green-50 border-green-200 text-green-800"
                                : "bg-red-50 border-red-200 text-red-800"
                        }
          `}
                >
                    {log.status === "processing" ? (
                        <span className="relative flex h-4 w-4">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-4 w-4 bg-yellow-400"></span>
                        </span>
                    ) : log.status === "completed" ? (
                        <Check size={18} className="text-green-600" />
                    ) : (
                        <span className="relative inline-flex rounded-full h-4 w-4 bg-red-500" />
                    )}
                    <span className="text-xs font-semibold">{log.message}</span>
                </div>
            ))}
        </div>
    );
}


