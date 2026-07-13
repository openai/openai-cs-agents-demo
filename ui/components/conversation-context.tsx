"use client";

import { PanelSection } from "./panel-section";
import { Card, CardContent } from "@/components/ui/card";
import { BookText } from "lucide-react";

interface ConversationContextProps {
  context: Record<string, any>;
}

export function ConversationContext({ context }: ConversationContextProps) {
  const labelMap: Record<string, string> = {
    customer_name: "联系人",
    company_name: "企业",
    account_id: "账户 ID",
    plan: "套餐",
    deployment_environment: "部署环境",
    product_area: "产品模块",
    issue_summary: "问题摘要",
    severity: "严重级别",
    ticket_id: "工单 ID",
    ticket_status: "工单状态",
    opportunity_id: "商机 ID",
    billing_case_id: "账单案例",
    compliance_topics: "合规主题",
    recommended_architecture: "建议架构",
    escalation_required: "需要升级",
    human_approval_required: "等待确认",
  };
  const formatValue = (value: any) => {
    if (value === null || value === undefined || value === "") return "null";
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
    if (Array.isArray(value)) {
      if (value.length === 0) return "[]";
      const primitives = value.every(
        (item) => ["string", "number", "boolean"].includes(typeof item)
      );
      if (primitives && value.length <= 3) {
        return value.join(", ");
      }
      return `${value.length} item${value.length === 1 ? "" : "s"}`;
    }
    if (typeof value === "object") {
      const keys = Object.keys(value);
      if (keys.length === 0) return "object";
      return `{${keys.slice(0, 3).join(", ")}${keys.length > 3 ? ", ..." : ""}}`;
    }
    return String(value);
  };

  return (
    <PanelSection
      title="业务上下文"
      icon={<BookText className="h-4 w-4 text-teal-700" />}
    >
      <Card className="rounded-md border-zinc-200 bg-white shadow-none">
        <CardContent className="p-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {Object.entries(context).map(([key, value]) => (
              <div
                key={key}
                className="flex min-w-0 items-start gap-2 border-b border-zinc-100 p-2"
              >
                {(() => {
                  const rendered = formatValue(value);
                  return (
                    <>
                      <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-teal-600"></div>
                      <div className="min-w-0 space-y-1 text-xs">
                        <div className="text-zinc-500">{labelMap[key] ?? key}</div>
                        <span
                          className={
                            value ? "text-zinc-900 font-light break-words" : "text-gray-400 italic"
                          }
                        >
                          {rendered}
                        </span>
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
