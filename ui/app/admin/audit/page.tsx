"use client";

import { AdminPageGuard } from "@/components/admin-shell";
import { AuditLogViewer } from "@/components/audit-log-viewer";

export default function AuditPage() {
  return (
    <AdminPageGuard roles={["tenant_admin", "support_agent"]}>
      <AuditLogViewer />
    </AdminPageGuard>
  );
}
