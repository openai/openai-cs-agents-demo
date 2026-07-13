"use client";

import { Activity, Bot } from "lucide-react";
import type { Agent, AgentEvent, GuardrailCheck } from "@/lib/types";
import { AgentsList } from "./agents-list";
import { Guardrails } from "./guardrails";
import { ConversationContext } from "./conversation-context";
import { RunnerOutput } from "./runner-output";

interface AgentPanelProps {
  agents: Agent[];
  currentAgent: string;
  events: AgentEvent[];
  guardrails: GuardrailCheck[];
  context: Record<string, any>;
}

export function AgentPanel({
  agents,
  currentAgent,
  events,
  guardrails,
  context,
}: AgentPanelProps) {
  const activeAgent = agents.find((a) => a.name === currentAgent);
  const runnerEvents = events.filter(
    (e) => e.type !== "message" && e.type !== "progress_update"
  );

  return (
    <section className="flex h-full min-h-0 min-w-0 w-full flex-1 flex-col bg-zinc-50">
      <div className="flex h-14 min-w-0 shrink-0 items-center gap-3 border-b border-zinc-200 bg-white px-4 sm:px-5">
        <span className="flex h-8 w-8 items-center justify-center bg-teal-700 text-white">
          <Bot className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold text-zinc-900">企业 Agent 编排工作台</h1>
          <p className="truncate text-xs text-zinc-500">支持、售前与合规协作</p>
        </div>
        <span className="ml-auto flex items-center gap-1.5 text-xs text-zinc-500">
          <Activity className="h-3.5 w-3.5 text-emerald-600" /> 实时运行
        </span>
      </div>

      <div className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto p-4 sm:p-5">
        <AgentsList agents={agents} currentAgent={currentAgent} />
        <ConversationContext context={context} />
        <Guardrails
          guardrails={guardrails}
          inputGuardrails={activeAgent?.input_guardrails ?? []}
        />
        <RunnerOutput runnerEvents={runnerEvents} />
      </div>
    </section>
  );
}
