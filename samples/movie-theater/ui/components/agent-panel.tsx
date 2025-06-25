"use client";

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
    customer_name?: string;
    confirmation_number?: string;
    seats?: string[];
    movie_title?: string;
    cinema_name?: string;
    city?: string;
    session_datetime?: string;
    room_number?: string;
    ticket_count?: number;
    ticket_type?: string;
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
    <div className="w-3/5 h-full flex flex-col border-r border-gray-200 bg-white rounded-xl shadow-sm">
      <div className="bg-gradient-to-r from-[#a1c4fd] to-[#c2e9fb] text-black h-12 px-4 flex items-center gap-3 shadow-sm rounded-t-xl">
        <h1 className="text-sm sm:text-base lg:text-lg">
          <span className="font-semibold">AGENT</span>
          <span className="font-light">VIEW</span>
        </h1>
        <span className="ml-auto text-xs font-light tracking-wide opacity-80">
          Cinema&nbsp;Co.
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-gray-50/50">
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
