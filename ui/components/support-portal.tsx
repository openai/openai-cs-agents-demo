"use client";

import { useEffect, useState } from "react";
import { PortalChatExperience } from "@/components/portal-chat-experience";
import { fetchPortalConfig, type PortalConfig } from "@/lib/platform-api";

export function SupportPortal() {
  const [config, setConfig] = useState<PortalConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPortalConfig()
      .then(setConfig)
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "客户服务加载失败");
      });
  }, []);

  if (error) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-zinc-100 p-6">
        <section className="w-full max-w-md border border-red-200 bg-white p-6 text-center">
          <h1 className="text-base font-semibold text-zinc-900">暂时无法连接客户服务</h1>
          <p className="mt-2 text-sm text-red-700">{error}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 h-10 bg-zinc-900 px-4 text-sm font-medium text-white"
          >
            重新连接
          </button>
        </section>
      </main>
    );
  }

  if (!config) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-zinc-100 text-sm text-zinc-500">
        正在连接客户服务
      </main>
    );
  }

  return <PortalChatExperience config={config} />;
}
