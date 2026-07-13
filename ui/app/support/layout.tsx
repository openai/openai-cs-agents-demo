import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "AI 客户服务",
  description: "企业智能客户服务",
};

export default function SupportLayout({ children }: { children: ReactNode }) {
  return children;
}
