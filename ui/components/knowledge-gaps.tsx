"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, RefreshCw, TriangleAlert } from "lucide-react";
import {
  fetchKnowledgeGaps,
  type KnowledgeGap,
  updateKnowledgeGap,
} from "@/lib/platform-api";

const statusLabels: Record<KnowledgeGap["status"], string> = {
  new: "新建",
  triaged: "已分诊",
  content_needed: "待补充",
  published: "已发布",
  resolved: "已解决",
  rejected: "已拒绝",
};

export function KnowledgeGaps() {
  const [gaps, setGaps] = useState<KnowledgeGap[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setGaps(await fetchKnowledgeGaps());
    } catch (err) {
      setError(err instanceof Error ? err.message : "知识缺口加载失败");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const changeStatus = async (gap: KnowledgeGap, status: KnowledgeGap["status"]) => {
    setBusyId(gap.id);
    setError(null);
    try {
      const updated = await updateKnowledgeGap(gap.id, status);
      setGaps((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "知识缺口更新失败");
    } finally {
      setBusyId(null);
    }
  };

  const openCount = gaps.filter(
    (gap) => !["resolved", "rejected"].includes(gap.status),
  ).length;

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-50">
      <div className="flex h-16 shrink-0 items-center border-b border-zinc-200 bg-white px-4 sm:px-6">
        <div>
          <h1 className="text-base font-semibold text-zinc-900">知识缺口</h1>
          <p className="text-xs text-zinc-500">{openCount} 项待处理</p>
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
      {error && (
        <div className="border-b border-red-200 bg-red-50 px-6 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-6xl overflow-hidden border border-zinc-200 bg-white">
          <div className="hidden h-11 grid-cols-[minmax(240px,1fr)_140px_150px_190px] items-center border-b border-zinc-200 bg-zinc-100 px-4 text-xs font-semibold text-zinc-600 md:grid">
            <span>问题</span>
            <span>来源</span>
            <span>状态</span>
            <span className="text-right">处理</span>
          </div>
          {gaps.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center text-zinc-500">
              <TriangleAlert className="h-7 w-7" />
              <p className="mt-3 text-sm">暂无知识缺口</p>
            </div>
          ) : (
            gaps.map((gap) => (
              <div
                key={gap.id}
                className="grid gap-3 border-b border-zinc-100 px-4 py-4 last:border-b-0 md:grid-cols-[minmax(240px,1fr)_140px_150px_190px] md:items-center"
              >
                <div className="min-w-0">
                  <p className="break-words text-sm font-medium text-zinc-900">{gap.question}</p>
                  <p className="mt-1 text-xs text-zinc-500">
                    {new Date(gap.created_at).toLocaleString("zh-CN")}
                  </p>
                </div>
                <span className="text-xs text-zinc-600">{gap.source}</span>
                <select
                  value={gap.status}
                  disabled={busyId === gap.id}
                  onChange={(event) =>
                    void changeStatus(gap, event.target.value as KnowledgeGap["status"])
                  }
                  className="h-9 border border-zinc-300 bg-white px-2 text-sm outline-none focus:border-teal-700 disabled:opacity-50"
                >
                  {Object.entries(statusLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
                <div className="flex justify-start gap-2 md:justify-end">
                  <button
                    type="button"
                    disabled={busyId === gap.id || gap.status === "resolved"}
                    onClick={() => void changeStatus(gap, "resolved")}
                    className="flex h-9 items-center gap-2 bg-teal-700 px-3 text-sm font-medium text-white disabled:opacity-40"
                  >
                    <Check className="h-4 w-4" /> 解决
                  </button>
                  <button
                    type="button"
                    disabled={busyId === gap.id || gap.status === "rejected"}
                    onClick={() => void changeStatus(gap, "rejected")}
                    className="h-9 border border-zinc-300 px-3 text-sm text-zinc-700 disabled:opacity-40"
                  >
                    拒绝
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
