"use client";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { AgentEvent } from "@/lib/types";
import {
  ArrowRightLeft,
  Wrench,
  WrenchIcon,
  RefreshCw,
  MessageSquareMore,
} from "lucide-react";
import { PanelSection } from "./panel-section";

interface RunnerOutputProps {
  runnerEvents: AgentEvent[];
}

function formatEventName(type: string) {
  return (type.charAt(0).toUpperCase() + type.slice(1)).replace("_", " ");
}

function EventIcon({ type }: { type: string }) {
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

function EventDetails({ event }: { event: AgentEvent }) {
  let details = null;
  const className =
    "border border-border text-xs p-2.5 rounded-md flex flex-col gap-2 bg-card";
  switch (event.type) {
    case "handoff":
      details = event.metadata && (
        <div className={className}>
          <div className="text-muted-foreground">
            <span className="text-foreground font-medium">From:</span>{" "}
            {event.metadata.source_agent}
          </div>
          <div className="text-muted-foreground">
            <span className="text-foreground font-medium">To:</span>{" "}
            {event.metadata.target_agent}
          </div>
        </div>
      );
      break;
    case "tool_call":
      details = event.metadata && event.metadata.tool_args && (
        <div className={className}>
          <div className="text-xs text-muted-foreground mb-1 font-medium">
            Arguments
          </div>
          <pre className="text-xs text-muted-foreground bg-muted p-2 rounded overflow-x-auto">
            {JSON.stringify(event.metadata.tool_args, null, 2)}
          </pre>
        </div>
      );
      break;
    case "tool_output":
      details = event.metadata && event.metadata.tool_result && (
        <div className={className}>
          <div className="text-xs text-muted-foreground mb-1 font-medium">Result</div>
          <pre className="text-xs text-muted-foreground bg-muted p-2 rounded overflow-x-auto">
            {JSON.stringify(event.metadata.tool_result, null, 2)}
          </pre>
        </div>
      );
      break;
    case "context_update":
      details = event.metadata?.changes && (
        <div className={className}>
          {Object.entries(event.metadata.changes).map(([key, value]) => (
            <div key={key} className="text-xs">
              <div className="text-muted-foreground">
                <span className="text-foreground font-medium">{key}:</span>{" "}
                {value ?? "null"}
              </div>
            </div>
          ))}
        </div>
      );
      break;
    default:
      return null;
  }

  return (
    <div className="mt-1 text-sm">
      {event.content && (
        <div className="text-foreground font-mono mb-2">{event.content}</div>
      )}
      {details}
    </div>
  );
}

function TimeBadge({ timestamp }: { timestamp: Date }) {
  const date =
    timestamp && typeof (timestamp as any)?.toDate === "function"
      ? (timestamp as any).toDate()
      : timestamp;
  const formattedDate = new Date(date).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  return (
    <Badge
      variant="outline"
      className="text-[10px] h-5 bg-white text-zinc-500 border-gray-200"
    >
      {formattedDate}
    </Badge>
  );
}

export function RunnerOutput({ runnerEvents }: RunnerOutputProps) {
  return (
    <div className="flex-1 overflow-hidden">
      <PanelSection title="Runner Output" icon={<MessageSquareMore className="h-4 w-4 text-primary" />}>
        <ScrollArea className="h-[calc(100%-2rem)] rounded-md border border-border bg-muted shadow-sm">
        <div className="p-4 space-y-3">
          {runnerEvents.length === 0 ? (
            <p className="text-center text-muted-foreground p-4">
              No runner events yet
            </p>
          ) : (
            runnerEvents.map((event) => (
              <Card
                key={event.id}
                className="border border-border bg-card shadow-sm rounded-lg"
              >
                <CardHeader className="flex flex-row justify-between items-center p-4">
                  <span className="font-medium text-foreground text-sm">
                    {event.agent}
                  </span>
                  <TimeBadge timestamp={event.timestamp} />
                </CardHeader>

                <CardContent className="flex items-start gap-3 p-4">
                  <div className="rounded-full p-2 bg-muted flex items-center gap-2">
                    <EventIcon type={event.type} />
                    <div className="text-xs text-muted-foreground">
                      {formatEventName(event.type)}
                    </div>
                  </div>

                  <div className="flex-1">
                    <EventDetails event={event} />
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
        </ScrollArea>
      </PanelSection>
    </div>
  );
}
