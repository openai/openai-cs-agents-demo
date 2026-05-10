"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AgentPanel } from "@/components/agent-panel";
import { ChatKitPanel } from "@/components/chatkit-panel";
import type { Agent, AgentEvent, GuardrailCheck } from "@/lib/types";
import { fetchBootstrapState, fetchThreadState } from "@/lib/api";

function parseSnapshot(data: any): {
  agents?: Agent[];
  events?: AgentEvent[];
  guardrails?: GuardrailCheck[];
  currentAgent?: string;
  context?: Record<string, any>;
} {
  const result: ReturnType<typeof parseSnapshot> = {};
  if (data.current_agent) result.currentAgent = data.current_agent;
  if (data.context) result.context = data.context;
  if (Array.isArray(data.agents)) result.agents = data.agents;
  if (Array.isArray(data.events)) {
    result.events = data.events.map((e: any) => ({
      ...e,
      timestamp: new Date(e.timestamp ?? Date.now()),
    }));
  }
  if (Array.isArray(data.guardrails)) {
    result.guardrails = data.guardrails.map((g: any) => ({
      ...g,
      timestamp: new Date(g.timestamp ?? Date.now()),
    }));
  }
  return result;
}

export default function Home() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string>("");
  const [guardrails, setGuardrails] = useState<GuardrailCheck[]>([]);
  const [context, setContext] = useState<Record<string, any>>({});
  const [threadId, setThreadId] = useState<string | null>(null);
  const [initialThreadId, setInitialThreadId] = useState<string | null>(null);
  const sseRef = useRef<EventSource | null>(null);

  const applySnapshot = useCallback((data: any) => {
    const parsed = parseSnapshot(data);
    if (parsed.currentAgent !== undefined) setCurrentAgent(parsed.currentAgent);
    if (parsed.context !== undefined) setContext(parsed.context);
    if (parsed.agents !== undefined) setAgents(parsed.agents);
    if (parsed.events !== undefined) setEvents(parsed.events);
    if (parsed.guardrails !== undefined) setGuardrails(parsed.guardrails);
  }, []);

  const hydrateState = useCallback(async (id: string | null) => {
    if (!id) return;
    const data = await fetchThreadState(id);
    if (data) applySnapshot(data);
  }, [applySnapshot]);

  // Open SSE stream for the active thread — receives full snapshot + delta on every agent step
  useEffect(() => {
    if (!threadId) return;
    sseRef.current?.close();
    const es = new EventSource(`/chatkit/state/stream?thread_id=${encodeURIComponent(threadId)}`);
    sseRef.current = es;
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        applySnapshot(data);
      } catch {}
    };
    return () => {
      es.close();
      sseRef.current = null;
    };
  }, [threadId, applySnapshot]);

  useEffect(() => {
    (async () => {
      const bootstrap = await fetchBootstrapState();
      if (!bootstrap) return;
      setInitialThreadId(bootstrap.thread_id || null);
      setThreadId(bootstrap.thread_id || null);
      applySnapshot(bootstrap);
    })();
  }, [applySnapshot]);

  const handleThreadChange = useCallback((id: string | null) => {
    setThreadId(id);
  }, []);

  const handleBindThread = useCallback((id: string) => {
    setThreadId(id);
  }, []);

  const handleResponseEnd = useCallback(() => {
    void hydrateState(threadId);
  }, [hydrateState, threadId]);

  // Apply delta events streamed via ChatKit effect (supplements SSE during active responses)
  const handleRunnerEventDelta = useCallback((deltaEvents: any[]) => {
    if (!deltaEvents.length) return;
    setEvents((prev) => {
      const existingIds = new Set(prev.map((e) => e.id));
      const newEvs: AgentEvent[] = deltaEvents
        .filter((e) => !existingIds.has(e.id))
        .map((e) => ({ ...e, timestamp: new Date(e.timestamp ?? Date.now()) }));
      return newEvs.length ? [...prev, ...newEvs] : prev;
    });
  }, []);

  return (
    <main className="flex h-screen gap-2 bg-gray-100 p-2">
      <AgentPanel
        agents={agents}
        currentAgent={currentAgent}
        events={events}
        guardrails={guardrails}
        context={context}
      />
      <ChatKitPanel
        initialThreadId={initialThreadId}
        onThreadChange={handleThreadChange}
        onResponseEnd={handleResponseEnd}
        onRunnerBindThread={handleBindThread}
        onRunnerEventDelta={handleRunnerEventDelta}
        onRunnerUpdate={() => void hydrateState(threadId)}
      />
    </main>
  );
}
