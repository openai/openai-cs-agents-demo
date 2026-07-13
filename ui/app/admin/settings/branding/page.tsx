"use client";

import { AdminPageGuard } from "@/components/admin-shell";
import { BrandingSettings } from "@/components/branding-settings";

export default function BrandingPage() {
  return (
    <AdminPageGuard roles={["tenant_admin"]}>
      <BrandingSettings />
    </AdminPageGuard>
  );
}
