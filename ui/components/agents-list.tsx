"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Bot, Circle } from "lucide-react";
import { PanelSection } from "./panel-section";
import type { Agent } from "@/lib/types";

interface AgentsListProps {
  agents: Agent[];
  currentAgent: string;
}

export function AgentsList({ agents, currentAgent }: AgentsListProps) {
  const activeAgent = agents.find((a) => a.name === currentAgent);
  return (
    <PanelSection
      title="Agent 团队"
      icon={<Bot className="h-4 w-4 text-teal-700" />}
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {agents.map((agent) => (
          <Card
            key={agent.name}
            className={`min-h-[112px] rounded-md border-zinc-200 bg-white transition-all ${
              agent.name === currentAgent ||
              activeAgent?.handoffs.includes(agent.name)
                ? ""
                : "opacity-50 filter grayscale cursor-not-allowed pointer-events-none"
            } ${
              agent.name === currentAgent
                ? "border-teal-600 ring-1 ring-teal-600"
                : ""
            }`}
          >
            <CardHeader className="p-3 pb-1">
              <CardTitle className="flex items-start gap-2 text-sm leading-5 text-zinc-900">
                <Circle className={`mt-1 h-2.5 w-2.5 shrink-0 ${agent.name === currentAgent ? "fill-emerald-500 text-emerald-500" : "fill-zinc-200 text-zinc-200"}`} />
                <span>{agent.name}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-1">
              <p className="text-xs font-light text-zinc-500">
                {agent.description}
              </p>
              {agent.name === currentAgent && (
                <Badge className="mt-2 rounded-sm bg-teal-700 text-white hover:bg-teal-700">
                  当前执行
                </Badge>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </PanelSection>
  );
}
