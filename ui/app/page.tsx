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

  const normalizeEvents = useCallback((items: AgentEvent[]) => {
    if (!items.length) return items;
    const now = Date.now();
    const latestNonProgress = items
      .filter((e) => e.type !== "progress_update")
      .reduce((max, e) => Math.max(max, e.timestamp.getTime()), 0);
    const pruned = items.filter((e) => {
      if (e.type !== "progress_update") return true;
      const ts = e.timestamp.getTime();
      // Drop old progress once a newer non-progress exists, or after 15s
      if (latestNonProgress && ts < latestNonProgress) return false;
      if (now - ts > 15000) return false;
      return true;
    });
    return pruned;
  }, []);

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
          normalizeEvents(
            bootstrap.events.map((e: any) => ({
              ...e,
              timestamp: new Date(e.timestamp ?? Date.now()),
            }))
          )
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
    console.info("[App] thread change", id, "at", new Date().toISOString());
    setThreadId(id);
  }, []);

  const handleBindThread = useCallback((id: string) => {
    console.info("[Runner] bind thread from effect", id, "at", new Date().toISOString());
    setThreadId(id);
  }, []);

  const handleResponseEnd = useCallback(() => {
    void hydrateState(threadId);
  }, [hydrateState, threadId]);

  const handleRunnerUpdate = useCallback(() => {
    if (threadId) {
      console.info("[Runner] refresh on client effect", new Date().toISOString());
      void hydrateState(threadId);
    }
  }, [hydrateState, threadId]);

  const handleRunnerEventDelta = useCallback(
    (newEvents: any[]) => {
      if (!newEvents?.length) return;
      console.info("[Runner] delta received via client effect", {
        count: newEvents.length,
        ts: new Date().toISOString(),
      });
      setEvents((prev) =>
        normalizeEvents([
          ...prev,
          ...newEvents.map((e: any) => ({
            ...e,
            timestamp: new Date(e.timestamp ?? Date.now()),
          })),
        ])
      );
    },
    [normalizeEvents]
  );

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
          const now = new Date().toISOString();
          const deltaCount = Array.isArray(data.events_delta)
            ? data.events_delta.length
            : 0;
          console.info("[SSE] received", {
            now,
            deltaCount,
            totalEvents: data.events?.length ?? "n/a",
            thread: threadId,
          });
          if (data.current_agent) setCurrentAgent(data.current_agent);
          if (Array.isArray(data.agents)) setAgents(data.agents);
          if (data.context) setContext(data.context);
          if (Array.isArray(data.events_delta) && data.events_delta.length > 0) {
            const mapped = data.events_delta.map((e: any) => ({
              ...e,
              timestamp: new Date(e.timestamp ?? Date.now()),
            }));
            setEvents((prev) => normalizeEvents([...prev, ...mapped]));
            const count = (prevEventCount.current || 0) + mapped.length;
            console.info("[SSE] Streamed runner events", {
              total: count,
              new: mapped.length,
            });
            prevEventCount.current = count;
          } else if (Array.isArray(data.events)) {
            setEvents(
              normalizeEvents(
                data.events.map((e: any) => ({
                  ...e,
                  timestamp: new Date(e.timestamp ?? Date.now()),
                }))
              )
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
        onRunnerUpdate={handleRunnerUpdate}
        onRunnerEventDelta={handleRunnerEventDelta}
        onRunnerBindThread={handleBindThread}
      />
    </main>
  );
}
