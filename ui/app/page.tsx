"use client";

import { useCallback, useEffect, useState } from "react";
import { AgentPanel } from "@/components/agent-panel";
import { ChatKitPanel } from "@/components/chatkit-panel";
import type { Agent, AgentEvent, GuardrailCheck } from "@/lib/types";
import { fetchBootstrapState, fetchThreadState } from "@/lib/api";

export default function Home() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string>("");
  const [guardrails, setGuardrails] = useState<GuardrailCheck[]>([]);
  const [context, setContext] = useState<Record<string, any>>({});
  const [threadId, setThreadId] = useState<string | null>(null);
  const [initialThreadId, setInitialThreadId] = useState<string | null>(null);

  const hydrateState = useCallback(
    async (id: string | null) => {
      if (!id) return;
      const data = await fetchThreadState(id);
      if (!data) return;

      setCurrentAgent(data.current_agent || "");
      setContext(data.context || {});
      if (Array.isArray(data.agents)) setAgents(data.agents);
      if (Array.isArray(data.events)) {
        setEvents(
          data.events.map((e: any) => ({
            ...e,
            timestamp: new Date(e.timestamp ?? Date.now()),
          }))
        );
      }
      if (Array.isArray(data.guardrails)) {
        setGuardrails(
          data.guardrails.map((g: any) => ({
            ...g,
            timestamp: new Date(g.timestamp ?? Date.now()),
          }))
        );
      }
    },
    []
  );

  useEffect(() => {
    if (threadId) {
      void hydrateState(threadId);
    }
  }, [threadId, hydrateState]);

  useEffect(() => {
    (async () => {
      const bootstrap = await fetchBootstrapState();
      if (!bootstrap) return;
      setInitialThreadId(bootstrap.thread_id || null);
      setThreadId(bootstrap.thread_id || null);
      if (bootstrap.current_agent) setCurrentAgent(bootstrap.current_agent);
      if (Array.isArray(bootstrap.agents)) setAgents(bootstrap.agents);
      if (bootstrap.context) setContext(bootstrap.context);
      if (Array.isArray(bootstrap.events)) {
        setEvents(
          bootstrap.events.map((e: any) => ({
            ...e,
            timestamp: new Date(e.timestamp ?? Date.now()),
          }))
        );
      }
      if (Array.isArray(bootstrap.guardrails)) {
        setGuardrails(
          bootstrap.guardrails.map((g: any) => ({
            ...g,
            timestamp: new Date(g.timestamp ?? Date.now()),
          }))
        );
      }
    })();
  }, []);

  const handleThreadChange = useCallback((id: string | null) => {
    setThreadId(id);
  }, []);

  const handleResponseEnd = useCallback(() => {
    void hydrateState(threadId);
  }, [hydrateState, threadId]);

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
      />
    </main>
  );
}
