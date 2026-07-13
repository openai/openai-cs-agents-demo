"use client";

import { AdminPageGuard } from "@/components/admin-shell";
import { ConnectorCenter } from "@/components/connector-center";

export default function ConnectorsPage() {
  return (
    <AdminPageGuard roles={["tenant_admin"]}>
      <ConnectorCenter />
    </AdminPageGuard>
  );
}
