"use client";

import { useCallback, useEffect, useState } from "react";
import { FileClock, RefreshCw } from "lucide-react";
import { fetchAuditLogs, type AuditLogEntry } from "@/lib/platform-api";

export function AuditLogViewer() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setEntries(await fetchAuditLogs());
    } catch (err) {
      setError(err instanceof Error ? err.message : "审计日志加载失败");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-50">
      <div className="flex min-h-16 shrink-0 items-center border-b border-zinc-200 bg-white px-4 py-3 sm:px-6">
        <div>
          <h1 className="text-base font-semibold text-zinc-900">审计日志</h1>
          <p className="text-xs text-zinc-500">敏感读取、草稿、连接器、知识和权限操作</p>
        </div>
        <button
          type="button"
          title="刷新"
          onClick={() => void refresh()}
          className="ml-auto flex h-9 w-9 items-center justify-center border border-zinc-300 text-zinc-700 hover:bg-zinc-50"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>
      {error && <div className="border-b border-red-200 bg-red-50 px-6 py-2 text-sm text-red-700">{error}</div>}
      <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-6">
        <div className="mx-auto max-w-6xl overflow-hidden border border-zinc-200 bg-white">
          {entries.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center text-sm text-zinc-500">
              <FileClock className="h-6 w-6" />
              <p className="mt-3">暂无审计记录</p>
            </div>
          ) : (
            <div className="min-w-[780px]">
              <div className="grid grid-cols-[170px_1fr_150px_160px] border-b border-zinc-200 bg-zinc-50 px-4 py-2 text-xs font-semibold text-zinc-500">
                <span>时间</span><span>动作</span><span>操作者</span><span>资源</span>
              </div>
              {entries.map((entry) => (
                <div key={entry.id} className="grid grid-cols-[170px_1fr_150px_160px] border-b border-zinc-100 px-4 py-3 text-xs last:border-b-0">
                  <span className="text-zinc-500">{new Date(entry.created_at).toLocaleString("zh-CN")}</span>
                  <div className="min-w-0">
                    <p className="truncate font-medium text-zinc-900">{entry.action}</p>
                    <p className="mt-1 truncate text-zinc-500">{JSON.stringify(entry.metadata)}</p>
                  </div>
                  <span className="truncate text-zinc-600">{entry.actor_user_id}</span>
                  <span className="truncate text-zinc-600">{entry.resource_type} · {entry.resource_id ?? "-"}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
