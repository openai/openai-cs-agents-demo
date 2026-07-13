"use client";

import { AdminPageGuard } from "@/components/admin-shell";
import { ApprovalCenter } from "@/components/approval-center";

export default function ApprovalsPage() {
  return (
    <AdminPageGuard roles={["tenant_admin", "support_agent"]}>
      <ApprovalCenter />
    </AdminPageGuard>
  );
}
