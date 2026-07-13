"use client";

import {
  Bot,
  ClipboardCheck,
  LibraryBig,
  MessagesSquare,
  TriangleAlert,
} from "lucide-react";
import type { CurrentUser } from "@/lib/platform-api";

export type AppView = "workspace" | "knowledge" | "gaps" | "approvals";

const navItems: Array<{
  id: AppView;
  label: string;
  icon: typeof MessagesSquare;
}> = [
  { id: "workspace", label: "Agent 工作台", icon: MessagesSquare },
  { id: "knowledge", label: "知识中心", icon: LibraryBig },
  { id: "gaps", label: "知识缺口", icon: TriangleAlert },
  { id: "approvals", label: "审批中心", icon: ClipboardCheck },
];

interface AppHeaderProps {
  activeView: AppView;
  onViewChange: (view: AppView) => void;
  user: CurrentUser | null;
}

export function AppHeader({
  activeView,
  onViewChange,
  user,
}: AppHeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center border-b border-zinc-200 bg-white px-3 sm:px-5">
      <div className="flex min-w-0 items-center gap-2">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center bg-teal-700 text-white">
          <Bot className="h-4 w-4" />
        </span>
        <div className="hidden min-w-0 lg:block">
          <p className="truncate text-sm font-semibold text-zinc-900">Enterprise Agent</p>
          <p className="truncate text-xs text-zinc-500">企业服务平台</p>
        </div>
      </div>

      <nav className="ml-3 flex min-w-0 flex-1 items-center gap-1 overflow-x-auto sm:ml-6">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activeView === item.id;
          return (
            <button
              key={item.id}
              type="button"
              aria-label={item.label}
              title={item.label}
              onClick={() => onViewChange(item.id)}
              className={`flex h-9 shrink-0 items-center gap-2 px-3 text-sm font-medium transition-colors ${
                active
                  ? "bg-zinc-900 text-white"
                  : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span className="hidden sm:inline">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {user && (
        <div className="ml-3 hidden min-w-0 text-right xl:block">
          <p className="max-w-48 truncate text-xs font-medium text-zinc-800">
            {user.tenant_id}
          </p>
          <p className="max-w-48 truncate text-xs text-zinc-500">{user.user_id}</p>
        </div>
      )}
    </header>
  );
}
