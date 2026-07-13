"use client";

import { AdminPageGuard } from "@/components/admin-shell";
import { AdminWorkspace } from "@/components/admin-workspace";

export default function WorkspacePage() {
  return (
    <AdminPageGuard roles={["tenant_admin", "support_agent"]}>
      <AdminWorkspace />
    </AdminPageGuard>
  );
}
