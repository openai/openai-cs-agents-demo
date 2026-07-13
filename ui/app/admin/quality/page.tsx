"use client";

import { AdminPageGuard } from "@/components/admin-shell";
import { QualityDashboard } from "@/components/quality-dashboard";

export default function QualityPage() {
  return (
    <AdminPageGuard roles={["tenant_admin", "support_agent"]}>
      <QualityDashboard />
    </AdminPageGuard>
  );
}
