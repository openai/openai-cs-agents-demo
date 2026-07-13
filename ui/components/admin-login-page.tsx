import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { authMode, loginUrl, safeReturnTo } from "@/lib/auth";

type AdminLoginPageProps = {
  returnTo?: string | null;
  reason?: string | null;
};

export function AdminLoginPage({ returnTo, reason }: AdminLoginPageProps) {
  const safePath = safeReturnTo(returnTo);
  const oidcMode = authMode() === "oidc";
  const reasonText =
    reason === "expired"
      ? "会话已过期，请重新登录。"
      : reason === "forbidden"
        ? "当前账户没有管理后台权限。"
        : reason === "logged_out"
          ? "已退出登录。"
          : null;

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-zinc-100 px-4 py-8">
      <section className="w-full max-w-md border border-zinc-200 bg-white p-7 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center bg-zinc-900 text-white">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-zinc-900">Enterprise AI Support Agent</p>
            <p className="text-xs text-zinc-500">企业管理后台</p>
          </div>
        </div>

        <h1 className="mt-8 text-2xl font-semibold text-zinc-950">登录企业管理后台</h1>
        <p className="mt-3 text-sm leading-6 text-zinc-600">
          {oidcMode
            ? "请使用企业身份提供方完成认证。登录成功后将返回刚才访问的后台页面。"
            : "当前是本地开发认证模式，前端会使用开发令牌访问后台接口。"}
        </p>

        {reasonText && (
          <p className="mt-5 border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {reasonText}
          </p>
        )}

        <div className="mt-7 flex flex-col gap-3">
          {oidcMode ? (
            <a
              href={loginUrl(safePath)}
              className="inline-flex h-11 items-center justify-center gap-2 bg-zinc-900 px-4 text-sm font-semibold text-white hover:bg-zinc-800"
            >
              使用企业 SSO 登录
              <ArrowRight className="h-4 w-4" />
            </a>
          ) : (
            <Link
              href={safePath}
              className="inline-flex h-11 items-center justify-center gap-2 bg-zinc-900 px-4 text-sm font-semibold text-white hover:bg-zinc-800"
            >
              进入开发后台
              <ArrowRight className="h-4 w-4" />
            </Link>
          )}
          <Link
            href="/support"
            className="inline-flex h-10 items-center justify-center border border-zinc-200 px-4 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
          >
            返回客户服务
          </Link>
        </div>
      </section>
    </main>
  );
}
