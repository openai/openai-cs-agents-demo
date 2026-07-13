"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Save, UserRoundCheck, UserRoundX } from "lucide-react";
import { fetchMembers, updateMember, type TenantMember } from "@/lib/platform-api";

const availableRoles = [
  ["tenant_admin", "企业管理员"],
  ["support_agent", "客服人员"],
  ["knowledge_editor", "知识编辑"],
  ["knowledge_reviewer", "知识审核"],
  ["billing_reader", "账单只读"],
  ["legal_reader", "法务只读"],
  ["end_user", "终端用户"],
] as const;

export function MemberManagement() {
  const [members, setMembers] = useState<TenantMember[]>([]);
  const [drafts, setDrafts] = useState<Record<string, TenantMember>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchMembers();
      setMembers(data);
      setDrafts(Object.fromEntries(data.map((member) => [member.user_id, member])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "成员列表加载失败");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const changeRole = (userId: string, role: string, checked: boolean) => {
    setDrafts((current) => {
      const member = current[userId];
      const roles = checked
        ? Array.from(new Set([...member.roles, role]))
        : member.roles.filter((item) => item !== role);
      return { ...current, [userId]: { ...member, roles } };
    });
  };

  const save = async (userId: string) => {
    const draft = drafts[userId];
    if (!draft || draft.roles.length === 0) return;
    setBusyId(userId);
    setError(null);
    try {
      const updated = await updateMember(userId, draft.status, draft.roles);
      setMembers((items) => items.map((item) => (item.user_id === userId ? updated : item)));
      setDrafts((current) => ({ ...current, [userId]: updated }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "成员保存失败");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-50">
      <div className="flex min-h-16 shrink-0 items-center border-b border-zinc-200 bg-white px-4 py-3 sm:px-6">
        <div>
          <h1 className="text-base font-semibold text-zinc-900">成员与角色</h1>
          <p className="text-xs text-zinc-500">OIDC 成员状态和最小权限覆盖</p>
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
      <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-6xl space-y-3">
          {members.map((member) => {
            const draft = drafts[member.user_id] ?? member;
            return (
              <article key={member.user_id} className="border border-zinc-200 bg-white p-4">
                <div className="flex flex-wrap items-start gap-3">
                  <span className={`flex h-9 w-9 items-center justify-center ${draft.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-zinc-100 text-zinc-500"}`}>
                    {draft.status === "active" ? <UserRoundCheck className="h-4 w-4" /> : <UserRoundX className="h-4 w-4" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <h2 className="break-all text-sm font-semibold text-zinc-900">{member.user_id}</h2>
                    <p className="mt-1 text-xs text-zinc-500">
                      权限来源：{member.source === "oidc" ? "OIDC 映射" : "管理员覆盖"}
                      {member.last_login_at ? ` · 最近登录 ${new Date(member.last_login_at).toLocaleString("zh-CN")}` : ""}
                    </p>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-zinc-700">
                    <input
                      type="checkbox"
                      checked={draft.status === "active"}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [member.user_id]: { ...draft, status: event.target.checked ? "active" : "disabled" },
                        }))
                      }
                      className="h-4 w-4 accent-teal-700"
                    />
                    启用账户
                  </label>
                </div>
                <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 border-t border-zinc-100 pt-4">
                  {availableRoles.map(([role, label]) => (
                    <label key={role} className="flex items-center gap-2 text-sm text-zinc-700">
                      <input
                        type="checkbox"
                        checked={draft.roles.includes(role)}
                        onChange={(event) => changeRole(member.user_id, role, event.target.checked)}
                        className="h-4 w-4 accent-teal-700"
                      />
                      {label}
                    </label>
                  ))}
                  <button
                    type="button"
                    disabled={busyId === member.user_id || draft.roles.length === 0}
                    onClick={() => void save(member.user_id)}
                    className="ml-auto flex h-9 items-center gap-2 bg-zinc-900 px-3 text-sm font-medium text-white disabled:opacity-40"
                  >
                    <Save className="h-4 w-4" /> 保存
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
