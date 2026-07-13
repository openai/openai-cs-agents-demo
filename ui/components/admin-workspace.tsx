"use client";

import { useCallback, useEffect, useState } from "react";
import { MessageSquare, Workflow } from "lucide-react";
import { AgentPanel } from "@/components/agent-panel";
import { ChatKitPanel } from "@/components/chatkit-panel";
import { fetchBootstrapState, fetchThreadState } from "@/lib/api";
import type { Agent, AgentEvent, GuardrailCheck } from "@/lib/types";
import { useAdminContext } from "@/components/admin-shell";

export function AdminWorkspace() {
  const { branding } = useAdminContext();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [currentAgent, setCurrentAgent] = useState("");
  const [guardrails, setGuardrails] = useState<GuardrailCheck[]>([]);
  const [context, setContext] = useState<Record<string, any>>({});
  const [threadId, setThreadId] = useState<string | null>(null);
  const [initialThreadId, setInitialThreadId] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<"runner" | "conversation">("runner");
  const [ready, setReady] = useState(false);

  const hydrateState = useCallback(async (id: string | null) => {
    if (!id) return;
    const data = await fetchThreadState(id);
    if (!data) return;
    setCurrentAgent(data.current_agent || "");
    setContext(data.context || {});
    if (Array.isArray(data.agents)) setAgents(data.agents);
    if (Array.isArray(data.events)) {
      setEvents(data.events.map((event: any) => ({ ...event, timestamp: new Date(event.timestamp ?? Date.now()) })));
    }
    if (Array.isArray(data.guardrails)) {
      setGuardrails(data.guardrails.map((item: any) => ({ ...item, timestamp: new Date(item.timestamp ?? Date.now()) })));
    }
  }, []);

  useEffect(() => {
    (async () => {
      const bootstrap = await fetchBootstrapState();
      if (bootstrap) {
        setInitialThreadId(bootstrap.thread_id || null);
        setThreadId(bootstrap.thread_id || null);
        setCurrentAgent(bootstrap.current_agent || "");
        setContext(bootstrap.context || {});
        setAgents(Array.isArray(bootstrap.agents) ? bootstrap.agents : []);
        setEvents(
          Array.isArray(bootstrap.events)
            ? bootstrap.events.map((event: any) => ({ ...event, timestamp: new Date(event.timestamp ?? Date.now()) }))
            : [],
        );
        setGuardrails(
          Array.isArray(bootstrap.guardrails)
            ? bootstrap.guardrails.map((item: any) => ({ ...item, timestamp: new Date(item.timestamp ?? Date.now()) }))
            : [],
        );
      }
      setReady(true);
    })();
  }, []);

  useEffect(() => {
    if (threadId) void hydrateState(threadId);
  }, [hydrateState, threadId]);

  return (
    <section className="flex h-full min-h-0 flex-col">
      <nav className="grid h-12 shrink-0 grid-cols-2 border-b border-zinc-200 bg-white p-1 lg:hidden">
        <button
          type="button"
          onClick={() => setMobileView("runner")}
          className={`flex items-center justify-center gap-2 text-sm font-medium ${mobileView === "runner" ? "bg-zinc-900 text-white" : "text-zinc-600"}`}
        >
          <Workflow className="h-4 w-4" /> 执行轨迹
        </button>
        <button
          type="button"
          onClick={() => setMobileView("conversation")}
          className={`flex items-center justify-center gap-2 text-sm font-medium ${mobileView === "conversation" ? "bg-zinc-900 text-white" : "text-zinc-600"}`}
        >
          <MessageSquare className="h-4 w-4" /> 测试会话
        </button>
      </nav>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col lg:flex-row">
        <div className={`${mobileView === "runner" ? "flex" : "hidden"} min-h-0 min-w-0 flex-1 lg:flex lg:basis-3/5`}>
          <AgentPanel
            agents={agents}
            currentAgent={currentAgent}
            events={events}
            guardrails={guardrails}
            context={context}
          />
        </div>
        <div className={`${mobileView === "conversation" ? "flex" : "hidden"} min-h-0 min-w-0 flex-1 lg:flex lg:basis-2/5`}>
          {ready ? (
            <ChatKitPanel
              surface="admin"
              assistantName={branding.assistant_name}
              greeting={branding.welcome_message}
              prompts={branding.suggested_prompts}
              accentColor={branding.primary_color}
              initialThreadId={initialThreadId}
              onThreadChange={setThreadId}
              onResponseEnd={() => void hydrateState(threadId)}
              onRunnerBindThread={setThreadId}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center bg-white text-sm text-zinc-500">
              正在加载会话
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
