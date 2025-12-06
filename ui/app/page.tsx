"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
  const prevEventCount = useRef(0);

  const hydrateState = useCallback(async (id: string | null) => {
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
  }, []);

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

  useEffect(() => {
    if (!threadId) return;
    let cancelled = false;
    const connect = () => {
      if (cancelled) return;
      const evtSource = new EventSource(
        `/chatkit/state/stream?thread_id=${threadId}`
      );
      console.info("[SSE] Connecting to state stream", threadId);
      evtSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.current_agent) setCurrentAgent(data.current_agent);
          if (Array.isArray(data.agents)) setAgents(data.agents);
          if (data.context) setContext(data.context);
          if (Array.isArray(data.events_delta) && data.events_delta.length > 0) {
            const mapped = data.events_delta.map((e: any) => ({
              ...e,
              timestamp: new Date(e.timestamp ?? Date.now()),
            }));
            setEvents((prev) => [...prev, ...mapped]);
            const count = (prevEventCount.current || 0) + mapped.length;
            console.info("[SSE] Streamed runner events", {
              total: count,
              new: mapped.length,
            });
            prevEventCount.current = count;
          } else if (Array.isArray(data.events)) {
            setEvents(
              data.events.map((e: any) => ({
                ...e,
                timestamp: new Date(e.timestamp ?? Date.now()),
              }))
            );
            const count = data.events.length;
            if (count !== prevEventCount.current) {
              console.info("[SSE] Streamed runner events", {
                total: count,
                new: Math.max(count - prevEventCount.current, 0),
              });
              prevEventCount.current = count;
            }
          }
          if (Array.isArray(data.guardrails)) {
            setGuardrails(
              data.guardrails.map((g: any) => ({
                ...g,
                timestamp: new Date(g.timestamp ?? Date.now()),
              }))
            );
          }
        } catch (err) {
        console.error("Failed to parse SSE state event", err, event.data);
      }
    };
    evtSource.onerror = (err) => {
      console.error("[SSE] error", err);
        evtSource.close();
        if (!cancelled) {
          setTimeout(connect, 1000);
        }
      };
      return evtSource;
    };
    const source = connect();
    return () => {
      cancelled = true;
      console.info("[SSE] Disconnected", threadId);
      source?.close();
    };
  }, [threadId, hydrateState]);

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
