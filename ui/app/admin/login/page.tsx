import type { Metadata } from "next";
import { AdminLoginPage } from "@/components/admin-login-page";

export const metadata: Metadata = {
  title: "登录企业管理后台",
  description: "使用企业 SSO 登录管理后台",
};

type AdminLoginRouteProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

function firstParam(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function AdminLoginRoute({ searchParams }: AdminLoginRouteProps) {
  const params = (await searchParams) ?? {};
  return (
    <AdminLoginPage
      returnTo={firstParam(params.return_to)}
      reason={firstParam(params.reason)}
    />
  );
}
