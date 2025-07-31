"use client";

import { Bot } from "lucide-react";
import { ThemePicker } from "@/components/theme-picker";
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
  context: {
    passenger_name?: string;
    confirmation_number?: string;
    seat_number?: string;
    flight_number?: string;
    account_number?: string;
  };
}

export function AgentPanel({
  agents,
  currentAgent,
  events,
  guardrails,
  context,
}: AgentPanelProps) {
  const activeAgent = agents.find((a) => a.name === currentAgent);
  const runnerEvents = events.filter((e) => e.type !== "message");

  return (
    <div className="w-3/5 h-full flex flex-col border-r border-border bg-card text-card-foreground rounded-xl shadow-sm">
      <div className="bg-primary text-primary-foreground h-12 px-4 flex items-center gap-3 shadow-sm rounded-t-xl">
        <Bot className="h-5 w-5" />
        <h1 className="font-semibold text-sm sm:text-base lg:text-lg">Agent View</h1>
        <div className="ml-auto flex items-center gap-3">
          <ThemePicker />
          <span className="text-xs font-light tracking-wide opacity-80">
            Airline&nbsp;Co.
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-background">
        <AgentsList agents={agents} currentAgent={currentAgent} />
        <Guardrails
          guardrails={guardrails}
          inputGuardrails={activeAgent?.input_guardrails ?? []}
        />
        <ConversationContext context={context} />
        <RunnerOutput runnerEvents={runnerEvents} />
      </div>
    </div>
  );
}