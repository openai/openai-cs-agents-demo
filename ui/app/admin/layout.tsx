import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AdminShell } from "@/components/admin-shell";

export const metadata: Metadata = {
  title: "企业 Agent 管理后台",
  description: "Agent、知识、审批与企业设置管理",
};

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}
