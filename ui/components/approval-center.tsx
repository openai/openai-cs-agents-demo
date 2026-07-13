"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Check,
  ClipboardCheck,
  FileCheck2,
  RefreshCw,
  Send,
  X,
} from "lucide-react";
import {
  completeActionDraft,
  decideApproval,
  fetchApprovals,
  submitActionDraft,
  type ApprovalRequest,
} from "@/lib/platform-api";

const actionLabels: Record<string, string> = {
  create_support_ticket: "支持工单草稿",
  create_sales_opportunity: "销售商机草稿",
  open_billing_case: "账单复核草稿",
};

const statusLabels: Record<ApprovalRequest["status"], string> = {
  draft: "草稿",
  pending_review: "待审核",
  approved_for_manual_execution: "待人工执行",
  rejected: "已拒绝",
  manually_completed: "人工已完成",
  expired: "已过期",
  cancelled: "已取消",
};

function statusStyle(status: ApprovalRequest["status"]) {
  if (status === "pending_review") return "bg-amber-50 text-amber-800";
  if (status === "approved_for_manual_execution") return "bg-blue-50 text-blue-800";
  if (status === "manually_completed") return "bg-emerald-50 text-emerald-800";
  return "bg-zinc-100 text-zinc-700";
}

export function ApprovalCenter() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [completionId, setCompletionId] = useState<string | null>(null);
  const [externalId, setExternalId] = useState("");
  const [completionNote, setCompletionNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setApprovals(await fetchApprovals());
    } catch (err) {
      setError(err instanceof Error ? err.message : "动作草稿加载失败");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const replace = (updated: ApprovalRequest) => {
    setApprovals((items) => items.map((item) => (item.id === updated.id ? updated : item)));
  };

  const submit = async (approval: ApprovalRequest) => {
    setBusyId(approval.id);
    setError(null);
    try {
      replace(await submitActionDraft(approval.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "草稿提交失败");
    } finally {
      setBusyId(null);
    }
  };

  const decide = async (approval: ApprovalRequest, decision: "approved" | "rejected") => {
    setBusyId(approval.id);
    setError(null);
    try {
      replace(await decideApproval(approval.id, decision));
    } catch (err) {
      setError(err instanceof Error ? err.message : "审核处理失败");
    } finally {
      setBusyId(null);
    }
  };

  const complete = async (approval: ApprovalRequest) => {
    if (!externalId.trim()) return;
    setBusyId(approval.id);
    setError(null);
    try {
      replace(await completeActionDraft(approval.id, externalId.trim(), completionNote.trim()));
      setCompletionId(null);
      setExternalId("");
      setCompletionNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "人工结果回填失败");
    } finally {
      setBusyId(null);
    }
  };

  const pendingCount = approvals.filter((item) =>
    ["draft", "pending_review", "approved_for_manual_execution"].includes(item.status),
  ).length;

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-50">
      <div className="flex min-h-16 shrink-0 items-center border-b border-zinc-200 bg-white px-4 py-3 sm:px-6">
        <div>
          <h1 className="text-base font-semibold text-zinc-900">动作草稿</h1>
          <p className="text-xs text-zinc-500">{pendingCount} 项待处理，所有外部操作均由人工执行</p>
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
        <div className="mx-auto max-w-6xl space-y-3">
          {approvals.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center border border-zinc-200 bg-white text-zinc-500">
              <ClipboardCheck className="h-7 w-7" />
              <p className="mt-3 text-sm">暂无动作草稿</p>
            </div>
          ) : (
            approvals.map((approval) => (
              <article key={approval.id} className="border border-zinc-200 bg-white p-4">
                <div className="grid gap-4 md:grid-cols-[minmax(220px,0.8fr)_minmax(260px,1.2fr)_auto] md:items-start">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-sm font-semibold text-zinc-900">
                        {actionLabels[approval.action] ?? approval.action}
                      </h2>
                      <span className={`shrink-0 px-2 py-1 text-xs ${statusStyle(approval.status)}`}>
                        {statusLabels[approval.status]}
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-zinc-500">
                      {new Date(approval.created_at).toLocaleString("zh-CN")}
                    </p>
                    <p className="mt-2 break-all font-mono text-[11px] text-zinc-400">
                      {approval.id}
                    </p>
                  </div>
                  <pre className="max-h-36 overflow-auto whitespace-pre-wrap break-all bg-zinc-50 p-3 text-xs leading-5 text-zinc-700">
                    {JSON.stringify(approval.payload_summary ?? approval.parameters, null, 2)}
                  </pre>
                  <div className="flex flex-wrap justify-start gap-2 md:justify-end">
                    {approval.status === "draft" && (
                      <button
                        type="button"
                        disabled={busyId === approval.id}
                        onClick={() => void submit(approval)}
                        className="flex h-9 items-center gap-2 bg-zinc-900 px-3 text-sm font-medium text-white disabled:opacity-40"
                      >
                        <Send className="h-4 w-4" /> 提交审核
                      </button>
                    )}
                    {approval.status === "pending_review" && (
                      <>
                        <button
                          type="button"
                          disabled={busyId === approval.id}
                          onClick={() => void decide(approval, "approved")}
                          className="flex h-9 items-center gap-2 bg-teal-700 px-3 text-sm font-medium text-white disabled:opacity-40"
                        >
                          <Check className="h-4 w-4" /> 批准待人工执行
                        </button>
                        <button
                          type="button"
                          disabled={busyId === approval.id}
                          onClick={() => void decide(approval, "rejected")}
                          className="flex h-9 items-center gap-2 border border-zinc-300 px-3 text-sm text-zinc-700 disabled:opacity-40"
                        >
                          <X className="h-4 w-4" /> 拒绝
                        </button>
                      </>
                    )}
                    {approval.status === "approved_for_manual_execution" && (
                      <button
                        type="button"
                        onClick={() => setCompletionId(approval.id)}
                        className="flex h-9 items-center gap-2 border border-blue-300 bg-blue-50 px-3 text-sm font-medium text-blue-800"
                      >
                        <FileCheck2 className="h-4 w-4" /> 回填人工结果
                      </button>
                    )}
                    {approval.status === "manually_completed" && (
                      <span className="text-xs text-zinc-600">外部记录：{approval.external_record_id}</span>
                    )}
                  </div>
                </div>
                {completionId === approval.id && (
                  <div className="mt-4 grid gap-3 border-t border-zinc-200 pt-4 sm:grid-cols-[minmax(180px,0.7fr)_minmax(220px,1fr)_auto]">
                    <input
                      value={externalId}
                      onChange={(event) => setExternalId(event.target.value)}
                      placeholder="外部记录 ID"
                      className="h-10 min-w-0 border border-zinc-300 px-3 text-sm outline-none focus:border-teal-700"
                    />
                    <input
                      value={completionNote}
                      onChange={(event) => setCompletionNote(event.target.value)}
                      placeholder="处理备注（可选）"
                      className="h-10 min-w-0 border border-zinc-300 px-3 text-sm outline-none focus:border-teal-700"
                    />
                    <button
                      type="button"
                      disabled={!externalId.trim() || busyId === approval.id}
                      onClick={() => void complete(approval)}
                      className="flex h-10 items-center justify-center gap-2 bg-zinc-900 px-4 text-sm font-medium text-white disabled:opacity-40"
                    >
                      <Check className="h-4 w-4" /> 确认回填
                    </button>
                  </div>
                )}
              </article>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
