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
    relevance_guardrail: "Enterprise Relevance Guardrail",
    jailbreak_guardrail: "Prompt Safety Guardrail",
    sensitive_data_guardrail: "Tenant Data Guardrail",
  };

  const guardrailDescriptionMap: Record<string, string> = {
    "Enterprise Relevance Guardrail": "限制在企业 AI 服务范围内",
    "Prompt Safety Guardrail": "检测提示词注入和越权工具调用",
    "Tenant Data Guardrail": "阻止凭据泄露和跨租户数据访问",
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
      title="安全护栏"
      icon={<Shield className="h-4 w-4 text-teal-700" />}
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {guardrailsToShow.map((gr) => (
          <Card
            key={gr.id}
            className={`rounded-md border-zinc-200 bg-white transition-all ${
              !gr.input ? "opacity-60" : ""
            }`}
          >
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-sm flex items-center text-zinc-900">
                {extractGuardrailName(gr.name)}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-1">
              <p className="text-xs font-light text-zinc-500 mb-1">
                {(() => {
                  const title = extractGuardrailName(gr.name);
                  return guardrailDescriptionMap[title] ?? gr.input;
                })()}
              </p>
              <div className="flex text-xs">
                {!gr.input || gr.passed ? (
                  <Badge className="mt-2 px-2 py-1 bg-emerald-500 hover:bg-emerald-600 flex items-center text-white">
                    <CheckCircle className="h-4 w-4 mr-1 text-white" />
                    通过
                  </Badge>
                ) : (
                  <Badge className="mt-2 px-2 py-1 bg-red-500 hover:bg-red-600 flex items-center text-white">
                    <XCircle className="h-4 w-4 mr-1 text-white" />
                    拦截
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
