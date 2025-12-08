"use client";

import { ChatKit, useChatKit } from "@openai/chatkit-react";
import React from "react";

type ChatKitPanelProps = {
  initialThreadId?: string | null;
  onThreadChange?: (threadId: string | null) => void;
  onResponseEnd?: () => void;
  onRunnerUpdate?: () => void;
  onRunnerEventDelta?: (events: any[]) => void;
  onRunnerBindThread?: (threadId: string) => void;
};

const CHATKIT_DOMAIN_KEY =
  process.env.NEXT_PUBLIC_CHATKIT_DOMAIN_KEY ?? "domain_pk_localhost_dev";

export function ChatKitPanel({
  initialThreadId,
  onThreadChange,
  onResponseEnd,
  onRunnerUpdate,
  onRunnerEventDelta,
  onRunnerBindThread,
}: ChatKitPanelProps) {
  const chatkit = useChatKit({
    api: {
      url: "/chatkit",
      domainKey: CHATKIT_DOMAIN_KEY,
    },
    composer: {
      placeholder: "Message...",
    },
    history: {
      enabled: false,
    },
    theme: {
      colorScheme: "light",
      radius: "round",
      density: "normal",
      color: {
        accent: {
          primary: "#2563eb",
          level: 1,
        },
      },
    },
    initialThread: initialThreadId ?? null,
    startScreen: {
      greeting: "Hi! I'm your airline assistant. How can I help today?",
      prompts: [
        { label: "Change my seat", prompt: "Can you move me to seat 14C?" },
        {
          label: "Flight status",
          prompt: "What's the status of flight FLT-123?",
        },
        {
          label: "Missed connection",
          prompt:
            "My flight from Paris to New York was delayed and I missed my connection to Austin. Also, my checked bag is missing and I need to spend the night in New York. Can you help me?",
        },
      ],
    },
    threadItemActions: {
      feedback: false,
    },
    onThreadChange: ({ threadId }) => onThreadChange?.(threadId ?? null),
    onResponseEnd: () => onResponseEnd?.(),
    onError: ({ error }) => {
      console.error("ChatKit error", error);
    },
    onEffect: async ({ name }) => {
      if (name === "runner_state_update") {
        onRunnerUpdate?.();
      }
      if (name === "runner_event_delta") {
        // runner_event_delta includes events payload in the effect data
        onRunnerEventDelta?.((arguments as any)?.[0]?.data?.events ?? []);
      }
       if (name === "runner_bind_thread") {
        const tid = (arguments as any)?.[0]?.data?.thread_id;
        if (tid) {
          onRunnerBindThread?.(tid);
        }
      }
    },
  });

  return (
    <div className="flex flex-col h-full flex-1 bg-white shadow-sm border border-gray-200 border-t-0 rounded-xl">
      <div className="bg-blue-600 text-white h-12 px-4 flex items-center rounded-t-xl">
        <h2 className="font-semibold text-sm sm:text-base lg:text-lg">
          Customer View
        </h2>
      </div>
      <div className="flex-1 overflow-hidden pb-1.5">
        <ChatKit
          control={chatkit.control}
          className="block h-full w-full"
          style={{ height: "100%", width: "100%" }}
          onThreadChange={(e: any) =>
            console.info("[ChatKit component thread change]", e?.detail ?? e)
          }
          onResponseStart={() => console.info("[ChatKit component response start]", Date.now())}
          onResponseEnd={() => console.info("[ChatKit component response end]", Date.now())}
        />
      </div>
    </div>
  );
}
