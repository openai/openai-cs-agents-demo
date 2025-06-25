"use client";

import { PanelSection } from "./panel-section";
import { Card, CardContent } from "@/components/ui/card";
import { ShieldAlert, ShieldCheck, AlertTriangle } from "lucide-react";
import type { GuardrailCheck } from "@/lib/types";

interface GuardrailsProps {
  guardrails: GuardrailCheck[];
  inputGuardrails: string[];
}

export function Guardrails({ guardrails, inputGuardrails }: GuardrailsProps) {
  const guardrailStatus = new Map(guardrails.map((gr) => [gr.name, gr.passed]));

  const getGuardrailDescription = (name: string) => {
    const descriptions: Record<string, string> = {
      "Relevance Guardrail": "Ensures queries relate to cinema services",
      "Jailbreak Guardrail": "Prevents system exploitation attempts",
    };
    return descriptions[name] || "Security check";
  };

  return (
    <PanelSection
      title="Security Guardrails"
      icon={<ShieldAlert className="h-4 w-4 text-black" />}
    >
      <Card className="bg-gradient-to-r from-white to-gray-50 border-gray-200 shadow-sm">
        <CardContent className="p-3">
          <div className="space-y-3">
            {inputGuardrails.map((name) => {
              const passed = guardrailStatus.get(name) ?? true;
              const guardrailData = guardrails.find((gr) => gr.name === name);

              return (
                <div
                  key={name}
                  className={`flex items-start gap-3 p-3 rounded-md border transition-all ${
                    passed
                      ? "bg-green-50 border-green-200 hover:bg-green-100"
                      : "bg-red-50 border-red-200 hover:bg-red-100"
                  }`}
                >
                  <div className="flex-shrink-0 mt-0.5">
                    {passed ? (
                      <ShieldCheck className="w-4 h-4 text-green-600" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-red-600" />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-zinc-900">
                        {name}
                      </span>
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                          passed
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {passed ? "PASSED" : "TRIGGERED"}
                      </span>
                    </div>

                    <p className="text-xs text-gray-600 mb-2">
                      {getGuardrailDescription(name)}
                    </p>

                    {!passed && guardrailData?.reasoning && (
                      <div className="bg-white p-2 rounded border border-red-200">
                        <p className="text-xs text-red-700 font-medium mb-1">
                          Violation Details:
                        </p>
                        <p className="text-xs text-red-600">
                          {guardrailData.reasoning}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {inputGuardrails.length === 0 && (
              <div className="text-center py-4 text-gray-500">
                <ShieldAlert className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No guardrails configured</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </PanelSection>
  );
}
