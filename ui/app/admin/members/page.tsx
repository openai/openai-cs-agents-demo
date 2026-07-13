"use client";

import { AdminPageGuard } from "@/components/admin-shell";
import { MemberManagement } from "@/components/member-management";

export default function MembersPage() {
  return (
    <AdminPageGuard roles={["tenant_admin"]}>
      <MemberManagement />
    </AdminPageGuard>
  );
}
