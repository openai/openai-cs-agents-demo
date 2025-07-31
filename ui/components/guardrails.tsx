"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Shield, CheckCircle, XCircle } from "lucide-react";
import { PanelSection } from "./panel-section";
import type { GuardrailCheck } from "@/lib/types";

interface GuardrailsProps {
  guardrails: GuardrailCheck[];
  inputGuardrails: string[];
}

export function Guardrails({ guardrails, inputGuardrails }: GuardrailsProps) {
  const guardrailNameMap: Record<string, string> = {
    relevance_guardrail: "Relevance Guardrail",
    jailbreak_guardrail: "Jailbreak Guardrail",
  };

  const guardrailDescriptionMap: Record<string, string> = {
    "Relevance Guardrail": "Ensure messages are relevant to airline support",
    "Jailbreak Guardrail":
      "Detect and block attempts to bypass or override system instructions",
  };

  const extractGuardrailName = (rawName: string): string =>
    guardrailNameMap[rawName] ?? rawName;

  const guardrailsToShow: GuardrailCheck[] = inputGuardrails.map((rawName) => {
    const existing = guardrails.find((gr) => gr.name === rawName);
    if (existing) {
      return existing;
    }
    return {
      id: rawName,
      name: rawName,
      input: "",
      reasoning: "",
      passed: false,
      timestamp: new Date(),
    };
  });

  return (
    <PanelSection
      title="Guardrails"
      icon={<Shield className="h-4 w-4 text-primary" />}
    >
      <div className="grid grid-cols-3 gap-3">
        {guardrailsToShow.map((gr) => (
          <Card
            key={gr.id}
            className={`bg-card border-border transition-all ${
              !gr.input ? "opacity-60" : ""
            }`}
          >
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-sm flex items-center text-foreground">
                {extractGuardrailName(gr.name)}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-1">
              <p className="text-xs font-light text-muted-foreground mb-1">
                {(() => {
                  const title = extractGuardrailName(gr.name);
                  return guardrailDescriptionMap[title] ?? gr.input;
                })()}
              </p>
              <div className="flex text-xs">
                {!gr.input || gr.passed ? (
                  <Badge className="mt-2 px-2 py-1 flex items-center">
                    <CheckCircle className="h-4 w-4 mr-1" />
                    Passed
                  </Badge>
                ) : (
                  <Badge variant="destructive" className="mt-2 px-2 py-1 flex items-center">
                    <XCircle className="h-4 w-4 mr-1" />
                    Failed
                  </Badge>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </PanelSection>
  );
}
