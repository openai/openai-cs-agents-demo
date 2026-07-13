import { ApiError, authenticatedFetch } from "./auth";

export type DocumentStatus =
  | "draft"
  | "processing"
  | "review_pending"
  | "published"
  | "failed"
  | "deprecated";

export interface KnowledgeDocument {
  id: string;
  title: string;
  category: "product" | "compliance" | "support" | "sales";
  status: DocumentStatus;
  version: number;
  language: string;
  source?: string | null;
  tags: string[];
  allowed_roles: string[];
  created_by: string;
  created_at: string;
  updated_at: string;
  published_at?: string | null;
  content?: string;
}

export interface KnowledgeSearchResult {
  document_id: string;
  version: number;
  title: string;
  section: string;
  content: string;
  score: number;
  source_scope: "tenant" | "platform";
  citation_url: string;
}

export interface KnowledgeGap {
  id: string;
  question: string;
  status: "new" | "triaged" | "content_needed" | "published" | "resolved" | "rejected";
  source: string;
  thread_id?: string | null;
  highest_score?: number | null;
  assignee?: string | null;
  resolution_document_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApprovalRequest {
  id: string;
  user_id: string;
  thread_id?: string | null;
  action: string;
  parameters: Record<string, unknown>;
  connector_id?: string | null;
  action_type: string;
  payload_summary: Record<string, unknown>;
  payload_hash: string;
  status:
    | "draft"
    | "pending_review"
    | "approved_for_manual_execution"
    | "rejected"
    | "manually_completed"
    | "expired"
    | "cancelled";
  external_record_id?: string | null;
  result?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectorConfiguration {
  id: string;
  connector_type: "crm" | "ticketing" | "usage" | "documents";
  provider: "hubspot" | "jira" | "usage_api" | "confluence";
  environment: "sandbox" | "staging" | "production";
  status: "disabled" | "enabled";
  credential_reference: string;
  granted_scopes: string[];
  settings: Record<string, unknown>;
  last_health_status?: "healthy" | "error" | null;
  last_error_status?: string | null;
  last_health_check_at?: string | null;
  last_success_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TraceRun {
  id: string;
  user_id: string;
  thread_id?: string | null;
  request_id: string;
  model?: string | null;
  agent_name?: string | null;
  status: string;
  duration_ms?: number | null;
  event_summary: {
    event_types?: string[];
    tool_names?: string[];
    guardrails?: { name: string; passed: boolean }[];
  };
  created_at: string;
}

export interface QualitySummary {
  evaluation: {
    status: "not_run" | "completed";
    conversation_case_count: number;
    redteam_case_count: number;
    latest_report?: {
      summary?: {
        total: number;
        passed: number;
        failed: number;
        critical_failures: number;
        average_score: number;
      };
    } | null;
  };
  safety: {
    external_write_policy: "draft_only";
    automatic_external_writes_allowed: false;
    critical_gate_mode: "fail_closed";
  };
  readiness: {
    status: "development" | "ready" | "not_ready";
    checks: { name: string; passed: boolean; message: string }[];
  };
  recent_traces: TraceRun[];
}

export interface TenantMember {
  user_id: string;
  status: "active" | "disabled";
  roles: string[];
  source: "oidc" | "manual";
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditLogEntry {
  id: string;
  actor_user_id: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  result: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface CurrentUser {
  tenant_id: string;
  user_id: string;
  roles: string[];
}

export interface SuggestedPrompt {
  label: string;
  prompt: string;
  icon?:
    | "wrench"
    | "network"
    | "shield-check"
    | "wallet-cards"
    | "message-circle"
    | "book-open"
    | null;
}

export interface TenantBranding {
  display_name: string;
  assistant_name: string;
  logo_url?: string | null;
  primary_color: string;
  welcome_message: string;
  support_notice: string;
  suggested_prompts: SuggestedPrompt[];
  updated_by?: string;
  updated_at?: string | null;
  published_at?: string | null;
}

export interface PortalConfig {
  branding: TenantBranding;
  service: {
    status: "online" | "degraded" | "offline";
    label: string;
  };
  capabilities: {
    history: boolean;
    citations: boolean;
    feedback: boolean;
    human_escalation: boolean;
    anonymous_access: boolean;
  };
}

export interface PortalThreadSummary {
  id: string;
  title: string;
  preview: string;
  updated_at: string;
}

export interface PortalThreadsPage {
  data: PortalThreadSummary[];
  has_more: boolean;
  after?: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authenticatedFetch(path, init);
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Keep the status-based message for non-JSON failures.
    }
    throw new ApiError(message, response.status);
  }
  return response.json();
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  return request<CurrentUser>("/v1/me");
}

export async function fetchPortalConfig(): Promise<PortalConfig> {
  return request<PortalConfig>("/v1/portal/config");
}

export async function fetchPortalThreads(
  after?: string | null,
): Promise<PortalThreadsPage> {
  const query = new URLSearchParams({ limit: "30" });
  if (after) query.set("after", after);
  return request<PortalThreadsPage>(`/v1/portal/threads?${query.toString()}`);
}

export async function fetchBrandingSettings(): Promise<TenantBranding> {
  return request<TenantBranding>("/v1/admin/settings/branding");
}

export async function updateBrandingSettings(
  payload: TenantBranding,
): Promise<TenantBranding> {
  return request<TenantBranding>("/v1/admin/settings/branding", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchDocuments(): Promise<KnowledgeDocument[]> {
  const response = await request<{ data: KnowledgeDocument[] }>(
    "/v1/knowledge/documents",
  );
  return response.data;
}

export async function fetchDocument(id: string): Promise<KnowledgeDocument> {
  return request<KnowledgeDocument>(`/v1/knowledge/documents/${id}`);
}

export async function createDocument(payload: {
  title: string;
  content: string;
  category: KnowledgeDocument["category"];
  language?: string;
}): Promise<KnowledgeDocument> {
  return request<KnowledgeDocument>("/v1/knowledge/documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function uploadDocument(
  file: File,
  category: KnowledgeDocument["category"],
): Promise<KnowledgeDocument> {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  return request<KnowledgeDocument>("/v1/knowledge/documents/upload", {
    method: "POST",
    body: form,
  });
}

export async function publishDocument(id: string): Promise<KnowledgeDocument> {
  return request<KnowledgeDocument>(
    `/v1/knowledge/documents/${id}/publish`,
    { method: "POST" },
  );
}

export async function deprecateDocument(id: string): Promise<KnowledgeDocument> {
  return request<KnowledgeDocument>(
    `/v1/knowledge/documents/${id}/deprecate`,
    { method: "POST" },
  );
}

export async function testKnowledgeSearch(query: string): Promise<{
  status: "grounded" | "insufficient_evidence";
  results: KnowledgeSearchResult[];
  knowledge_gap: boolean;
}> {
  return request("/v1/knowledge/search/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

export async function fetchKnowledgeGaps(): Promise<KnowledgeGap[]> {
  const response = await request<{ data: KnowledgeGap[] }>(
    "/v1/knowledge/gaps",
  );
  return response.data;
}

export async function updateKnowledgeGap(
  id: string,
  status: KnowledgeGap["status"],
): Promise<KnowledgeGap> {
  return request<KnowledgeGap>(`/v1/knowledge/gaps/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export async function fetchApprovals(): Promise<ApprovalRequest[]> {
  const response = await request<{ data: ApprovalRequest[] }>("/v1/approvals");
  return response.data;
}

export async function decideApproval(
  id: string,
  decision: "approved" | "rejected",
): Promise<ApprovalRequest> {
  return request<ApprovalRequest>(`/v1/approvals/${id}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
}

export async function submitActionDraft(id: string): Promise<ApprovalRequest> {
  return request<ApprovalRequest>(`/v1/action-drafts/${id}/submit`, {
    method: "POST",
  });
}

export async function completeActionDraft(
  id: string,
  externalRecordId: string,
  note?: string,
): Promise<ApprovalRequest> {
  return request<ApprovalRequest>(`/v1/action-drafts/${id}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ external_record_id: externalRecordId, note: note || null }),
  });
}

export async function fetchConnectors(): Promise<ConnectorConfiguration[]> {
  const response = await request<{ data: ConnectorConfiguration[] }>(
    "/v1/admin/connectors",
  );
  return response.data;
}

export async function configureConnector(payload: Omit<ConnectorConfiguration, "id" | "created_at" | "updated_at" | "last_health_status" | "last_error_status" | "last_health_check_at" | "last_success_at">): Promise<ConnectorConfiguration> {
  return request<ConnectorConfiguration>("/v1/admin/connectors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function testConnector(id: string): Promise<{
  status: "healthy";
  connector_id: string;
  sample: Record<string, unknown>;
}> {
  return request(`/v1/admin/connectors/${id}/test`, { method: "POST" });
}

export async function syncDocumentConnector(id: string): Promise<{
  status: "completed";
  synced: { document_id: string; version: number; status: string; sync_status: string }[];
  skipped: number;
}> {
  return request(`/v1/admin/connectors/${id}/sync`, { method: "POST" });
}

export async function fetchQualitySummary(): Promise<QualitySummary> {
  return request<QualitySummary>("/v1/admin/quality/summary");
}

export async function fetchMembers(): Promise<TenantMember[]> {
  const response = await request<{ data: TenantMember[] }>("/v1/admin/members");
  return response.data;
}

export async function updateMember(
  userId: string,
  status: TenantMember["status"],
  roles: string[],
): Promise<TenantMember> {
  return request<TenantMember>(`/v1/admin/members/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, roles }),
  });
}

export async function fetchAuditLogs(): Promise<AuditLogEntry[]> {
  const response = await request<{ data: AuditLogEntry[] }>("/v1/audit-logs?limit=200");
  return response.data;
}
