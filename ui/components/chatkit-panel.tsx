"use client";

import { ChatKit, useChatKit } from "@openai/chatkit-react";
import React, {
  forwardRef,
  useCallback,
  useImperativeHandle,
} from "react";
import { authenticatedFetch } from "@/lib/auth";
import type { SuggestedPrompt } from "@/lib/platform-api";

type ChatKitPanelProps = {
  initialThreadId?: string | null;
  onThreadChange?: (threadId: string | null) => void;
  onResponseEnd?: () => void;
  onRunnerUpdate?: () => void;
  onRunnerEventDelta?: (events: any[]) => void;
  onRunnerBindThread?: (threadId: string) => void;
  surface?: "portal" | "admin";
  assistantName?: string;
  greeting?: string;
  prompts?: SuggestedPrompt[];
  accentColor?: string;
  headerEnabled?: boolean;
  historyEnabled?: boolean;
  showStartScreen?: boolean;
  onReady?: () => void;
};

export type ChatKitPanelHandle = {
  sendUserMessage: (params: { text: string; newThread?: boolean }) => Promise<void>;
  setThreadId: (threadId: string | null) => Promise<void>;
  focusComposer: () => Promise<void>;
};

const CHATKIT_DOMAIN_KEY =
  process.env.NEXT_PUBLIC_CHATKIT_DOMAIN_KEY ?? "domain_pk_localhost_dev";

export const ChatKitPanel = forwardRef<ChatKitPanelHandle, ChatKitPanelProps>(function ChatKitPanel({
  initialThreadId,
  onThreadChange,
  onResponseEnd,
  onRunnerUpdate,
  onRunnerEventDelta,
  onRunnerBindThread,
  surface = "portal",
  assistantName = "AI 服务助手",
  greeting = "您好，请问今天需要产品、技术、方案还是账户支持？",
  prompts,
  accentColor = "#0f766e",
  headerEnabled = true,
  historyEnabled = true,
  showStartScreen = true,
  onReady,
}, ref) {
  const surfaceFetch = useCallback(
    (input: RequestInfo | URL, init: RequestInit = {}) => {
      const headers = new Headers(init.headers);
      headers.set("X-Client-Surface", surface);
      return authenticatedFetch(input, { ...init, headers });
    },
    [surface],
  );

  const startPrompts = prompts ?? [
    {
      label: "技术故障",
      prompt: "我们的 API 持续出现 429 和超时，请帮我诊断并给出下一步。",
    },
    {
      label: "方案咨询",
      prompt: "我们想建设带权限控制的企业知识库 Agent，请给出初步架构。",
    },
    {
      label: "安全合规",
      prompt: "请介绍私有化部署、数据留存和安全合规相关能力。",
    },
    {
      label: "账户服务",
      prompt: "请帮我查询当前套餐、用量和续费信息。",
    },
  ];
  const chatKitStartPrompts = startPrompts.map(({ label, prompt }) => ({
    label,
    prompt,
  }));

  const chatkit = useChatKit({
    api: {
      url: "/chatkit",
      domainKey: CHATKIT_DOMAIN_KEY,
      fetch: surfaceFetch,
    },
    composer: {
      placeholder: "请输入产品、技术或业务问题...",
    },
    header: {
      enabled: headerEnabled,
    },
    history: {
      enabled: historyEnabled,
    },
    theme: {
      colorScheme: "light",
      radius: "soft",
      density: "normal",
      color: {
        accent: {
          primary: accentColor,
          level: 1,
        },
      },
    },
    initialThread: initialThreadId ?? null,
    startScreen: showStartScreen
      ? { greeting, prompts: chatKitStartPrompts }
      : { greeting: "", prompts: [] },
    threadItemActions: {
      feedback: false,
    },
    onThreadChange: ({ threadId }) => onThreadChange?.(threadId ?? null),
    onResponseEnd: () => onResponseEnd?.(),
    onError: ({ error }) => {
      console.error("ChatKit error", error);
    },
    onReady,
    onEffect: async (effect) => {
      const { name, data } = effect as { name: string; data?: Record<string, any> };
      if (surface !== "admin") return;
      if (name === "runner_state_update") {
        onRunnerUpdate?.();
      }
      if (name === "runner_event_delta") {
        onRunnerEventDelta?.((data?.events as any[]) ?? []);
      }
      if (name === "runner_bind_thread") {
        const tid = data?.thread_id;
        if (tid) {
          onRunnerBindThread?.(String(tid));
        }
      }
    },
  });

  useImperativeHandle(
    ref,
    () => ({
      async sendUserMessage(params) {
        await chatkit.sendUserMessage(params);
      },
      async setThreadId(threadId) {
        await chatkit.setThreadId(threadId);
      },
      async focusComposer() {
        await chatkit.focusComposer();
      },
    }),
    [chatkit],
  );

  return (
    <section className={`flex h-full min-h-0 min-w-0 w-full flex-1 flex-col bg-white ${surface === "admin" ? "border-l border-zinc-200" : ""}`}>
      {surface === "admin" && (
        <div className="flex h-14 shrink-0 items-center border-b border-zinc-200 px-5">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900">内部测试会话</h2>
            <p className="text-xs text-zinc-500">{assistantName}</p>
          </div>
          <span className="ml-auto h-2 w-2 rounded-full bg-emerald-500" title="服务在线" />
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-hidden">
        <ChatKit
          control={chatkit.control}
          className="block h-full w-full"
          style={{ height: "100%", width: "100%" }}
        />
      </div>
    </section>
  );
});

ChatKitPanel.displayName = "ChatKitPanel";
