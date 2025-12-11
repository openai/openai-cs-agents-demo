"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Bot } from "lucide-react";
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
      title="Available Agents"
      icon={<Bot className="h-4 w-4 text-blue-600" />}
    >
      <div className="grid grid-cols-3 gap-3">
        {agents.map((agent) => (
          <Card
            key={agent.name}
            className={`bg-white border-gray-200 h-[130px] transition-all ${
              agent.name === currentAgent ||
              activeAgent?.handoffs.includes(agent.name)
                ? ""
                : "opacity-50 filter grayscale cursor-not-allowed pointer-events-none"
            } ${
              agent.name === currentAgent
                ? "ring-1 ring-blue-500 shadow-md"
                : ""
            }`}
          >
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-sm flex items-center text-zinc-900">
                {agent.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-1">
              <p className="text-xs font-light text-zinc-500">
                {agent.description}
              </p>
              {agent.name === currentAgent && (
                <Badge className="mt-2 bg-blue-600 hover:bg-blue-700 text-white">
                  Active
                </Badge>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </PanelSection>
  );
}
