"use client";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { AgentEvent } from "@/lib/types";
import {
  ArrowRightLeft,
  Wrench,
  WrenchIcon,
  RefreshCw,
  MessageSquareMore,
  ChevronDown,
} from "lucide-react";
import { useState } from "react";
import { PanelSection } from "./panel-section";

interface RunnerOutputProps {
  runnerEvents: AgentEvent[];
}

function formatEventName(type: string) {
  return (type.charAt(0).toUpperCase() + type.slice(1)).replace(/_/g, " ");
}

function EventIcon({ type, icon }: { type: string; icon?: string }) {
  const className = "h-4 w-4 text-zinc-600";
  switch (type) {
    case "handoff":
      return <ArrowRightLeft className={className} />;
    case "tool_call":
      return <Wrench className={className} />;
    case "tool_output":
      return <WrenchIcon className={className} />;
    case "context_update":
      return <RefreshCw className={className} />;
    default:
      return null;
  }
}

function inlineValue(value: any) {
  if (value === null || value === undefined || value === "") return "null";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return "object";
  }
}

function tryParseJson(value: any) {
  if (value === null || value === undefined) return null;
  if (typeof value === "object") return value;
  if (typeof value === "string") {
    try {
      return JSON.parse(value);
    } catch {
      return null;
    }
  }
  return null;
}

function groupRunnerEvents(events: AgentEvent[]) {
  const groups: AgentEvent[][] = [];
  for (let i = 0; i < events.length; i++) {
    const current = events[i];
    if (current.type === "tool_call") {
      const group = [current];
      let j = i + 1;
      while (
        j < events.length &&
        events[j].type === "tool_output" &&
        events[j].agent === current.agent
      ) {
        group.push(events[j]);
        j++;
      }
      groups.push(group);
      i = j - 1;
      continue;
    }
    groups.push([current]);
  }
  return groups;
}

function buildEventText(event: AgentEvent) {
  switch (event.type) {
    case "handoff":
      return event.content || `${event.metadata?.source_agent ?? ""} -> ${event.metadata?.target_agent ?? ""}`.trim();
    case "tool_call": {
      const args = event.metadata?.tool_args;
      const argsText = args !== undefined ? ` - ${inlineValue(args)}` : "";
      return `${event.content || "Tool call"}${argsText}`;
    }
    case "tool_output": {
      const result = event.metadata?.tool_result;
      if (result !== undefined) return inlineValue(result);
      return event.content || "Tool output";
    }
    case "context_update": {
      const changes = event.metadata?.changes;
      if (!changes) return event.content || "";
      return Object.entries(changes)
        .map(([key, value]) => `${key}: ${inlineValue(value)}`)
        .join(" · ");
    }
    default:
      return event.content || "";
  }
}

function EventDetails({ event }: { event: AgentEvent }) {
  const [expanded, setExpanded] = useState(false);
  const toolArgs = event.metadata?.tool_args;
  const toolResult = event.metadata?.tool_result;
  const contextChanges = event.metadata?.changes;

  const parsedArgs = tryParseJson(toolArgs);
  const parsedResult = tryParseJson(toolResult);
  const parsedContext = tryParseJson(contextChanges);
  const isJsonResult = parsedResult !== null;

  const collapsedArgsText =
    toolArgs !== undefined ? (parsedArgs ? JSON.stringify(parsedArgs) : inlineValue(toolArgs)) : null;
  const collapsedResultText =
    toolResult !== undefined ? (isJsonResult ? JSON.stringify(parsedResult) : inlineValue(toolResult)) : null;

  const text =
    event.type === "tool_call"
      ? null
      : event.type === "tool_output" && collapsedResultText
        ? collapsedResultText
        : buildEventText(event);
  const clampStyle = !expanded
    ? { display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical" as const }
    : undefined;

  return (
    <div className="flex items-start gap-2">
      <div className="flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-[11px] text-gray-600 shrink-0">
        <EventIcon type={event.type} icon={event.metadata?.icon} />
        <span className="whitespace-nowrap">{formatEventName(event.type)}</span>
      </div>
      <div className="flex-1 min-w-0">
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          aria-expanded={expanded}
          className="group w-full text-left flex items-start gap-2"
        >
          <div
            className={`flex-1 overflow-hidden transition-[max-height] duration-200 ease-out ${
              expanded ? "max-h-[420px]" : "max-h-6"
            }`}
          >
            <div
              style={clampStyle}
              className="text-sm leading-relaxed text-gray-800 whitespace-pre-wrap flex flex-wrap items-start gap-1"
            >
              {event.type === "tool_call" ? (
                <>
                  <span className="font-mono text-[13px] text-gray-800">
                    {event.content || "Tool call"}
                  </span>
                  {collapsedArgsText && !expanded && (
                    <span className="font-mono text-[13px] text-gray-700">
                      - {collapsedArgsText}
                    </span>
                  )}
                </>
              ) : event.type === "tool_output" && collapsedResultText ? (
                isJsonResult ? (
                  <span className="font-mono text-[13px] bg-gray-100 border border-gray-200 px-2 py-1 rounded">
                    {collapsedResultText}
                  </span>
                ) : (
                  <span className="text-sm text-gray-800">{collapsedResultText}</span>
                )
              ) : event.type === "context_update" && contextChanges ? (
                Object.entries(contextChanges).map(([key, value]) => (
                  <span key={key} className="font-mono text-[12px] text-gray-800">
                    {key}: {inlineValue(value)}
                  </span>
                ))
              ) : (
                text
              )}
            </div>
          </div>
          <ChevronDown
            className={`mt-0.5 h-4 w-4 text-gray-400 transition-transform duration-200 group-hover:text-gray-600 ${
              expanded ? "rotate-180" : ""
            }`}
          />
        </button>
        {expanded && event.type === "tool_call" && toolArgs !== undefined && (
          <pre className="mt-2 bg-gray-100 border border-gray-200 font-mono text-xs text-gray-800 p-2 rounded-md whitespace-pre-wrap break-words">
            {JSON.stringify(parsedArgs ?? toolArgs, null, 2)}
          </pre>
        )}
        {expanded && event.type === "tool_output" && toolResult !== undefined && (
          isJsonResult ? (
            <pre className="mt-2 bg-gray-100 border border-gray-200 font-mono text-xs text-gray-800 p-2 rounded-md whitespace-pre-wrap break-words">
              {JSON.stringify(parsedResult, null, 2)}
            </pre>
          ) : (
            <div className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">{inlineValue(toolResult)}</div>
          )
        )}
        {expanded && event.type === "context_update" && contextChanges && (
          <pre className="mt-2 bg-gray-100 border border-gray-200 font-mono text-xs text-gray-800 p-2 rounded-md whitespace-pre-wrap break-words">
            {JSON.stringify(parsedContext ?? contextChanges, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

export function RunnerOutput({ runnerEvents }: RunnerOutputProps) {
  const groupedEvents = groupRunnerEvents(runnerEvents);

  return (
    <div className="flex-1 overflow-hidden">
      <PanelSection
        title="Runner Output"
        icon={<MessageSquareMore className="h-4 w-4 text-blue-600" />}
      >
        <ScrollArea className="h-[calc(100%-2rem)] rounded-md border border-gray-200 bg-gray-100 shadow-sm">
          <div className="p-3 space-y-2.5">
            {runnerEvents.length === 0 ? (
              <p className="text-center text-zinc-500 p-4">
                No runner events yet
              </p>
            ) : (
              groupedEvents.map((group) => {
                const agentName = group[0]?.agent ?? "Agent";
                const key = group.map((ev) => ev.id).join("-");
                return (
                  <Card
                    key={key}
                    className="border border-gray-200 bg-white shadow-sm rounded-lg"
                  >
                    <CardHeader className="flex flex-row items-center px-3 py-2">
                      <span className="text-sm text-gray-800 font-medium">{agentName}</span>
                    </CardHeader>

                    <CardContent className="p-3 pt-0 space-y-2">
                      {group.map((event) => (
                        <EventDetails key={event.id} event={event} />
                      ))}
                    </CardContent>
                  </Card>
                );
              })
            )}
          </div>
        </ScrollArea>
      </PanelSection>
    </div>
  );
}
