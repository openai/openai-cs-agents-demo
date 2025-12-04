"use client";

import { PanelSection } from "./panel-section";
import { Card, CardContent } from "@/components/ui/card";
import { BookText } from "lucide-react";

interface ConversationContextProps {
  context: Record<string, any>;
}

export function ConversationContext({ context }: ConversationContextProps) {
  const formatValue = (value: any) => {
    if (value === null || value === undefined || value === "") return "null";
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
    if (Array.isArray(value)) {
      if (value.length === 0) return "[]";
      // Render small arrays directly, otherwise summarize count.
      if (value.length <= 3) {
        try {
          return JSON.stringify(value, null, 2);
        } catch {
          return `${value.length} items`;
        }
      }
      return `${value.length} items`;
    }
    if (typeof value === "object") {
      try {
        return JSON.stringify(value, null, 2);
      } catch {
        return "object";
      }
    }
    return String(value);
  };

  return (
    <PanelSection
      title="Conversation Context"
      icon={<BookText className="h-4 w-4 text-blue-600" />}
    >
      <Card className="bg-gradient-to-r from-white to-gray-50 border-gray-200 shadow-sm">
        <CardContent className="p-3">
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(context).map(([key, value]) => (
              <div
                key={key}
                className="flex items-center gap-2 bg-white p-2 rounded-md border border-gray-200 shadow-sm transition-all"
              >
                {(() => {
                  const rendered = formatValue(value);
                  const multiline = String(rendered).includes("\n");
                  return (
                    <>
                      <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                      <div className="text-xs space-y-1">
                        <div className="text-zinc-500 font-light">{key}:</div>
                        {multiline ? (
                          <pre className="text-[11px] leading-4 text-zinc-900 bg-gray-50 p-2 rounded border border-gray-200 overflow-auto max-h-40">
                            {rendered}
                          </pre>
                        ) : (
                          <span
                            className={
                              value
                                ? "text-zinc-900 font-light"
                                : "text-gray-400 italic"
                            }
                          >
                            {rendered}
                          </span>
                        )}
                      </div>
                    </>
                  );
                })()}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </PanelSection>
  );
}
