"use client";

import { AdminPageGuard } from "@/components/admin-shell";
import { KnowledgeGaps } from "@/components/knowledge-gaps";

export default function GapsPage() {
  return (
    <AdminPageGuard roles={["tenant_admin", "knowledge_editor", "knowledge_reviewer", "support_agent"]}>
      <KnowledgeGaps />
    </AdminPageGuard>
  );
}
