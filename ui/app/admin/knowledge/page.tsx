"use client";

import { AdminPageGuard } from "@/components/admin-shell";
import { KnowledgeCenter } from "@/components/knowledge-center";

export default function KnowledgePage() {
  return (
    <AdminPageGuard roles={["tenant_admin", "knowledge_editor", "knowledge_reviewer", "support_agent"]}>
      <KnowledgeCenter />
    </AdminPageGuard>
  );
}
