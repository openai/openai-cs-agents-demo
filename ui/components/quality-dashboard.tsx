"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  CircleAlert,
  RefreshCw,
  ShieldCheck,
  TestTube2,
} from "lucide-react";
import { fetchQualitySummary, type QualitySummary } from "@/lib/platform-api";

export function QualityDashboard() {
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setSummary(await fetchQualitySummary());
    } catch (err) {
      setError(err instanceof Error ? err.message : "质量数据加载失败");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!summary && !error) {
    return <div className="flex h-full items-center justify-center text-sm text-zinc-500">正在加载质量数据</div>;
  }

  const latest = summary?.evaluation.latest_report?.summary;
  const readinessDisplay = summary
    ? summary.readiness.status === "development"
      ? { icon: Activity, value: "开发环境", detail: "生产门禁仅作提示", tone: "neutral" as const }
      : summary.readiness.status === "ready"
        ? { icon: CheckCircle2, value: "就绪", detail: "生产启动门禁已通过", tone: "good" as const }
        : { icon: CircleAlert, value: "未就绪", detail: "生产启动门禁未通过", tone: "warning" as const }
    : null;

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-50">
      <div className="flex min-h-16 shrink-0 items-center border-b border-zinc-200 bg-white px-4 py-3 sm:px-6">
        <div>
          <h1 className="text-base font-semibold text-zinc-900">质量与上线门禁</h1>
          <p className="text-xs text-zinc-500">评测、红队、Trace 和生产配置状态</p>
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
      {summary && (
        <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
          <div className="mx-auto max-w-6xl space-y-6">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Metric
                icon={TestTube2}
                label="对话评测用例"
                value={String(summary.evaluation.conversation_case_count)}
                detail={summary.evaluation.status === "completed" ? "最近评测已运行" : "尚未运行评测"}
                tone={summary.evaluation.status === "completed" ? "good" : "warning"}
              />
              <Metric
                icon={ShieldCheck}
                label="红队用例"
                value={String(summary.evaluation.redteam_case_count)}
                detail={latest ? `${latest.critical_failures} 个关键失败` : "尚无执行结果"}
                tone={latest && latest.critical_failures === 0 ? "good" : "warning"}
              />
              <Metric
                icon={Activity}
                label="最近 Trace"
                value={String(summary.recent_traces.length)}
                detail="平台自有脱敏 Trace"
                tone="neutral"
              />
              <Metric
                icon={readinessDisplay!.icon}
                label="生产配置"
                value={readinessDisplay!.value}
                detail={readinessDisplay!.detail}
                tone={readinessDisplay!.tone}
              />
            </div>

            <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
              <section>
                <h2 className="text-sm font-semibold text-zinc-900">安全边界</h2>
                <div className="mt-3 border border-zinc-200 bg-white">
                  <StatusRow label="外部写入策略" value="仅生成草稿" passed />
                  <StatusRow label="自动外部写操作" value="已禁止" passed />
                  <StatusRow label="关键门禁" value="失败时阻断发布" passed />
                </div>

                <h2 className="mt-6 text-sm font-semibold text-zinc-900">生产配置检查</h2>
                <div className="mt-3 border border-zinc-200 bg-white">
                  {summary.readiness.checks.map((check) => (
                    <StatusRow
                      key={check.name}
                      label={check.name}
                      value={check.message}
                      passed={check.passed}
                    />
                  ))}
                </div>
              </section>

              <section>
                <h2 className="text-sm font-semibold text-zinc-900">最近 Trace</h2>
                <div className="mt-3 overflow-hidden border border-zinc-200 bg-white">
                  {summary.recent_traces.length === 0 ? (
                    <div className="flex min-h-48 items-center justify-center text-sm text-zinc-500">暂无 Trace</div>
                  ) : (
                    <div className="divide-y divide-zinc-100">
                      {summary.recent_traces.map((trace) => (
                        <div key={trace.id} className="grid gap-2 p-3 sm:grid-cols-[minmax(140px,0.8fr)_minmax(150px,1fr)_auto] sm:items-center">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-zinc-900">{trace.agent_name ?? "Unknown Agent"}</p>
                            <p className="mt-1 truncate font-mono text-[11px] text-zinc-400">{trace.request_id}</p>
                          </div>
                          <p className="truncate text-xs text-zinc-600">
                            {(trace.event_summary.tool_names ?? []).join(" · ") || "无工具调用"}
                          </p>
                          <div className="text-right">
                            <span className={`px-2 py-1 text-xs ${trace.status === "success" ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"}`}>
                              {trace.status}
                            </span>
                            <p className="mt-1 text-[11px] text-zinc-400">
                              {trace.duration_ms ? `${Math.round(trace.duration_ms)} ms` : "-"}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  detail: string;
  tone: "good" | "warning" | "neutral";
}) {
  const colors = tone === "good" ? "text-emerald-700" : tone === "warning" ? "text-amber-700" : "text-zinc-700";
  return (
    <article className="border border-zinc-200 bg-white p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-zinc-500">
        <Icon className={`h-4 w-4 ${colors}`} /> {label}
      </div>
      <p className="mt-3 text-2xl font-semibold text-zinc-900">{value}</p>
      <p className="mt-1 text-xs text-zinc-500">{detail}</p>
    </article>
  );
}

function StatusRow({ label, value, passed }: { label: string; value: string; passed: boolean }) {
  return (
    <div className="flex min-h-12 items-center gap-3 border-b border-zinc-100 px-3 py-2 last:border-b-0">
      {passed ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
      ) : (
        <CircleAlert className="h-4 w-4 shrink-0 text-amber-600" />
      )}
      <span className="min-w-0 flex-1 text-sm text-zinc-800">{label}</span>
      <span className="max-w-[55%] text-right text-xs text-zinc-500">{value}</span>
    </div>
  );
}
