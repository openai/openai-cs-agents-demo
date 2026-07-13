"use client";

import {
  Bot,
  BarChart3,
  ChevronRight,
  ClipboardCheck,
  Cable,
  ExternalLink,
  FileClock,
  LibraryBig,
  LogOut,
  Menu,
  Settings,
  ShieldCheck,
  Users,
  TriangleAlert,
  Workflow,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  fetchCurrentUser,
  fetchPortalConfig,
  type CurrentUser,
  type TenantBranding,
} from "@/lib/platform-api";
import { ApiError, adminLoginPageUrl, isOidcAuthMode, logoutFromSession } from "@/lib/auth";

const ADMIN_ROLES = [
  "tenant_admin",
  "knowledge_editor",
  "knowledge_reviewer",
  "support_agent",
] as const;

const navItems = [
  {
    href: "/admin/workspace",
    label: "Agent 工作台",
    icon: Workflow,
    roles: ["tenant_admin", "support_agent"],
  },
  {
    href: "/admin/knowledge",
    label: "知识中心",
    icon: LibraryBig,
    roles: [
      "tenant_admin",
      "knowledge_editor",
      "knowledge_reviewer",
      "support_agent",
    ],
  },
  {
    href: "/admin/gaps",
    label: "知识缺口",
    icon: TriangleAlert,
    roles: [
      "tenant_admin",
      "knowledge_editor",
      "knowledge_reviewer",
      "support_agent",
    ],
  },
  {
    href: "/admin/approvals",
    label: "动作草稿",
    icon: ClipboardCheck,
    roles: ["tenant_admin", "support_agent"],
  },
  {
    href: "/admin/connectors",
    label: "连接器",
    icon: Cable,
    roles: ["tenant_admin"],
  },
  {
    href: "/admin/members",
    label: "成员与角色",
    icon: Users,
    roles: ["tenant_admin"],
  },
  {
    href: "/admin/quality",
    label: "质量与上线",
    icon: BarChart3,
    roles: ["tenant_admin", "support_agent"],
  },
  {
    href: "/admin/audit",
    label: "审计日志",
    icon: FileClock,
    roles: ["tenant_admin", "support_agent"],
  },
  {
    href: "/admin/settings/branding",
    label: "企业设置",
    icon: Settings,
    roles: ["tenant_admin"],
  },
];

type AdminContextValue = {
  user: CurrentUser;
  branding: TenantBranding;
};

const AdminContext = createContext<AdminContextValue | null>(null);

export function useAdminContext() {
  const context = useContext(AdminContext);
  if (!context) throw new Error("Admin context is not available");
  return context;
}

function hasAnyRole(user: CurrentUser, roles: readonly string[]) {
  return roles.some((role) => user.roles.includes(role));
}

type AuthState = "loading" | "authenticated" | "unauthenticated" | "forbidden" | "error";

function LoginRequired({ returnTo }: { returnTo: string }) {
  if (!isOidcAuthMode()) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-zinc-100 p-6">
        <section className="w-full max-w-md border border-amber-200 bg-white p-7">
          <div className="flex h-11 w-11 items-center justify-center bg-amber-50 text-amber-700">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <h1 className="mt-5 text-lg font-semibold text-zinc-900">开发认证失败</h1>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            当前处于开发认证模式，请检查前端 `NEXT_PUBLIC_DEV_AUTH_TOKEN` 与后端 `DEV_AUTH_TOKEN` 是否一致。
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-zinc-100 p-6">
      <section className="w-full max-w-md border border-zinc-200 bg-white p-7 text-center shadow-sm">
        <div className="mx-auto flex h-11 w-11 items-center justify-center bg-zinc-900 text-white">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <h1 className="mt-5 text-lg font-semibold text-zinc-900">请先登录管理后台</h1>
        <p className="mt-2 text-sm leading-6 text-zinc-600">
          使用企业 SSO 完成认证后，将返回当前后台页面。
        </p>
        <Link
          href={adminLoginPageUrl(returnTo)}
          className="mt-6 inline-flex h-10 items-center justify-center bg-zinc-900 px-4 text-sm font-medium text-white hover:bg-zinc-800"
        >
          前往登录页
        </Link>
        <Link
          href="/support"
          className="mt-3 block text-sm font-medium text-zinc-600 hover:text-zinc-900"
        >
          返回客户服务
        </Link>
      </section>
    </main>
  );
}

function LogoutButton({ compact = false }: { compact?: boolean }) {
  const [loggingOut, setLoggingOut] = useState(false);
  if (!isOidcAuthMode()) {
    return (
      <span className="inline-flex h-8 items-center px-3 text-xs font-medium text-zinc-500">
        开发模式
      </span>
    );
  }
  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logoutFromSession("/admin/login");
    } finally {
      window.location.assign(adminLoginPageUrl("/admin/workspace", "logged_out"));
    }
  };
  return (
    <button
      type="button"
      onClick={handleLogout}
      disabled={loggingOut}
      className={`inline-flex items-center gap-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 disabled:cursor-wait disabled:opacity-60 ${
        compact ? "h-9 px-2" : "h-10 px-3"
      }`}
    >
      <LogOut className="h-4 w-4" />
      {loggingOut ? "退出中" : "退出登录"}
    </button>
  );
}

function Forbidden() {
  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-zinc-100 p-6">
      <section className="w-full max-w-md border border-zinc-200 bg-white p-8 text-center">
        <div className="mx-auto flex h-11 w-11 items-center justify-center bg-red-50 text-red-700">
          <X className="h-5 w-5" />
        </div>
        <h1 className="mt-5 text-lg font-semibold text-zinc-900">无法访问管理后台</h1>
        <p className="mt-2 text-sm text-zinc-600">当前账户没有企业管理权限。</p>
        <div className="mt-6 flex flex-col items-center gap-2">
          <Link
            href="/support"
            className="inline-flex h-10 items-center bg-zinc-900 px-4 text-sm font-medium text-white"
          >
            返回客户服务
          </Link>
          <LogoutButton compact />
        </div>
      </section>
    </main>
  );
}

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [authState, setAuthState] = useState<AuthState>("loading");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [branding, setBranding] = useState<TenantBranding | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isAdminLoginPage = pathname === "/admin/login";

  const loadIdentity = async () => {
    try {
      const [nextUser, portal] = await Promise.all([
        fetchCurrentUser(),
        fetchPortalConfig(),
      ]);
      setUser(nextUser);
      setBranding(portal.branding);
      setAuthState(hasAnyRole(nextUser, ADMIN_ROLES) ? "authenticated" : "forbidden");
      setError(null);
    } catch (loadError) {
      setUser(null);
      setBranding(null);
      if (loadError instanceof ApiError && loadError.status === 401) {
        setAuthState(isOidcAuthMode() ? "unauthenticated" : "error");
        setError(isOidcAuthMode() ? null : "开发认证失败，请检查开发令牌配置。");
        return;
      }
      if (loadError instanceof ApiError && loadError.status === 403) {
        setAuthState("forbidden");
        setError(null);
        return;
      }
      setAuthState("error");
      setError(loadError instanceof Error ? loadError.message : "身份加载失败");
    }
  };

  useEffect(() => {
    if (isAdminLoginPage) return;
    void loadIdentity();
    const refreshBranding = () => void loadIdentity();
    window.addEventListener("tenant-branding-updated", refreshBranding);
    return () => window.removeEventListener("tenant-branding-updated", refreshBranding);
  }, [isAdminLoginPage]);

  useEffect(() => setMenuOpen(false), [pathname]);

  const visibleItems = useMemo(
    () => (user ? navItems.filter((item) => hasAnyRole(user, item.roles)) : []),
    [user],
  );

  if (isAdminLoginPage) {
    return <>{children}</>;
  }

  if (authState === "unauthenticated") {
    return <LoginRequired returnTo={pathname || "/admin/workspace"} />;
  }

  if (authState === "forbidden") return <Forbidden />;

  if (authState === "error" && error) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-zinc-100 p-6">
        <section className="border border-red-200 bg-white p-6 text-sm text-red-700">
          {error}
        </section>
      </main>
    );
  }

  if (authState === "loading" || !user || !branding) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-zinc-100 text-sm text-zinc-500">
        正在验证管理权限
      </main>
    );
  }

  const sidebar = (
    <div className="flex h-full flex-col bg-white">
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-zinc-200 px-4">
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center text-white"
          style={{ backgroundColor: branding.primary_color }}
        >
          <Bot className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-zinc-900">{branding.display_name}</p>
          <p className="truncate text-xs text-zinc-500">企业管理后台</p>
        </div>
        <button
          type="button"
          title="关闭导航"
          onClick={() => setMenuOpen(false)}
          className="ml-auto flex h-9 w-9 items-center justify-center text-zinc-500 hover:bg-zinc-100 lg:hidden"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
        <p className="px-3 pb-2 text-xs font-semibold text-zinc-400">管理</p>
        <div className="space-y-1">
          {visibleItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex h-10 items-center gap-3 px-3 text-sm font-medium ${
                  active
                    ? "bg-zinc-900 text-white"
                    : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
                {active && <ChevronRight className="h-4 w-4 shrink-0" />}
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="shrink-0 border-t border-zinc-200 p-3">
        <Link
          href="/support"
          target="_blank"
          className="flex h-10 items-center gap-3 px-3 text-sm font-medium text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
        >
          <ExternalLink className="h-4 w-4" />
          预览客户前台
        </Link>
        <div className="mt-2 border-t border-zinc-100 px-3 pt-3">
          <p className="truncate text-xs font-medium text-zinc-800">{user.user_id}</p>
          <p className="mt-1 truncate text-xs text-zinc-500">{user.roles.join(" · ")}</p>
          <div className="mt-3">
            <LogoutButton />
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <AdminContext.Provider value={{ user, branding }}>
      <main className="flex h-[100dvh] min-h-0 bg-zinc-100">
        <aside className="hidden h-full w-60 shrink-0 border-r border-zinc-200 lg:block">
          {sidebar}
        </aside>

        {menuOpen && (
          <>
            <button
              type="button"
              aria-label="关闭导航"
              onClick={() => setMenuOpen(false)}
              className="fixed inset-0 z-30 bg-black/30 lg:hidden"
            />
            <aside className="fixed inset-y-0 left-0 z-40 w-[min(86vw,300px)] border-r border-zinc-200 lg:hidden">
              {sidebar}
            </aside>
          </>
        )}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center border-b border-zinc-200 bg-white px-3 lg:hidden">
            <button
              type="button"
              title="打开导航"
              onClick={() => setMenuOpen(true)}
              className="flex h-9 w-9 items-center justify-center text-zinc-700 hover:bg-zinc-100"
            >
              <Menu className="h-5 w-5" />
            </button>
            <p className="ml-3 min-w-0 flex-1 truncate text-sm font-semibold text-zinc-900">
              {branding.display_name}
            </p>
            <span className="text-xs text-zinc-500">管理后台</span>
          </header>
          <div className="min-h-0 min-w-0 flex-1">{children}</div>
        </div>
      </main>
    </AdminContext.Provider>
  );
}

export function AdminPageGuard({
  roles,
  children,
}: {
  roles: readonly string[];
  children: ReactNode;
}) {
  const { user } = useAdminContext();
  if (!hasAnyRole(user, roles)) {
    return (
      <section className="flex h-full items-center justify-center p-6 text-sm text-zinc-600">
        当前角色无权访问此模块。
      </section>
    );
  }
  return <>{children}</>;
}
