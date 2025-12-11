"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Terminal } from "lucide-react";
import type { AgentEvent } from "@/lib/types";

interface RunnerOutputProps {
  runnerEvents: AgentEvent[];
}

export function RunnerOutput({ runnerEvents }: RunnerOutputProps) {
  const [expanded, setExpanded] = useState(false);

  if (runnerEvents.length === 0) return null;

  return (
    <div className="mb-5">
      <h2
        className="text-lg font-semibold mb-3 text-zinc-900 flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center">
          <span className="bg-gradient-to-r from-[#a1c4fd] to-[#c2e9fb] bg-opacity-10 p-1.5 rounded-md mr-2 shadow-sm">
            <Terminal className="h-4 w-4 text-black" />
          </span>
          <span>Agent Execution Log</span>
        </div>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-zinc-900" />
        ) : (
          <ChevronRight className="h-4 w-4 text-zinc-900" />
        )}
      </h2>
      {expanded && (
        <div className="space-y-3 transition-all duration-300 ease-in-out">
          {runnerEvents.map((event, index) => (
            <div
              key={index}
              className="text-xs p-3 bg-white rounded-md border border-gray-200 shadow-sm"
            >
              <div className="font-medium text-black">{event.type}</div>
              <div className="text-zinc-900">{event.content}</div>
              {event.metadata && (
                <pre className="mt-2 text-xs text-zinc-500 overflow-x-auto">
                  {JSON.stringify(event.metadata, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
