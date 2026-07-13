from __future__ import annotations

from pathlib import Path
import json
import hashlib
import os
from typing import Annotated, Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field, field_validator

from persistent_store import PersistentStore

from .connectors import ConnectorError, ConnectorGateway, validate_read_only_scopes
from .documents import UnsupportedDocumentType, extract_document_text
from .identity import ALLOWED_ROLES, RequestIdentity, get_request_identity, require_roles
from .model_provider import ZAI_SETTINGS
from .production import production_readiness_checks
from .object_storage import ObjectStorage, document_object_key


router = APIRouter(prefix="/v1", tags=["enterprise-platform"])

KnowledgeManager = Annotated[
    RequestIdentity,
    Depends(
        require_roles(
            "tenant_admin", "knowledge_editor", "knowledge_reviewer", "support_agent"
        )
    ),
]
KnowledgeEditor = Annotated[
    RequestIdentity, Depends(require_roles("tenant_admin", "knowledge_editor"))
]
KnowledgeReviewer = Annotated[
    RequestIdentity, Depends(require_roles("tenant_admin", "knowledge_reviewer"))
]
SupportOperator = Annotated[
    RequestIdentity,
    Depends(
        require_roles(
            "tenant_admin", "knowledge_editor", "knowledge_reviewer", "support_agent"
        )
    ),
]
ActionReviewer = Annotated[
    RequestIdentity,
    Depends(require_roles("tenant_admin", "support_agent")),
]
TenantAdmin = Annotated[
    RequestIdentity,
    Depends(require_roles("tenant_admin")),
]


def get_store(request: Request) -> PersistentStore:
    store = getattr(request.app.state, "store", None)
    if not isinstance(store, PersistentStore):
        raise RuntimeError("Persistent store is not configured")
    return store


StoreDependency = Annotated[PersistentStore, Depends(get_store)]


def get_connector_gateway(store: StoreDependency) -> ConnectorGateway:
    return ConnectorGateway(store)


ConnectorDependency = Annotated[ConnectorGateway, Depends(get_connector_gateway)]


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=2_000_000)
    category: Literal["product", "compliance", "support", "sales"] = "product"
    language: str = Field(default="zh-CN", max_length=24)
    source: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=30)
    allowed_roles: list[str] = Field(default_factory=list, max_length=30)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    category: Literal["product", "compliance", "support", "sales"] | None = None
    limit: int = Field(default=5, ge=1, le=10)


class KnowledgeGapUpdate(BaseModel):
    status: Literal[
        "new", "triaged", "content_needed", "published", "resolved", "rejected"
    ]
    assignee: str | None = Field(default=None, max_length=200)
    resolution_document_id: str | None = None


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]


class ActionDraftCompletion(BaseModel):
    external_record_id: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)


class ConnectorConfiguration(BaseModel):
    connector_type: Literal["crm", "ticketing", "usage", "documents"]
    provider: Literal["hubspot", "jira", "usage_api", "confluence"]
    environment: Literal["sandbox", "staging", "production"] = "sandbox"
    status: Literal["disabled", "enabled"] = "disabled"
    credential_reference: str = Field(pattern=r"^env://[A-Z][A-Z0-9_]*$", max_length=200)
    granted_scopes: list[str] = Field(min_length=1, max_length=20)
    settings: dict[str, Any] = Field(default_factory=dict)

    @field_validator("settings")
    @classmethod
    def reject_inline_secrets(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden = ("api_key", "apikey", "authorization", "password", "secret", "token")
        for key in value:
            normalized = key.lower().replace("-", "_")
            if any(part in normalized for part in forbidden):
                raise ValueError("Connector settings cannot contain inline secrets")
        return value


class MemberUpdate(BaseModel):
    status: Literal["active", "disabled"]
    roles: list[str] = Field(min_length=1, max_length=10)

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, value: list[str]) -> list[str]:
        unknown = set(value).difference(ALLOWED_ROLES)
        if unknown:
            raise ValueError(f"Unsupported roles: {', '.join(sorted(unknown))}")
        return sorted(set(value))


class SuggestedPrompt(BaseModel):
    label: str = Field(min_length=1, max_length=24)
    prompt: str = Field(min_length=1, max_length=500)
    icon: Literal[
        "wrench",
        "network",
        "shield-check",
        "wallet-cards",
        "message-circle",
        "book-open",
    ] | None = None


class BrandingUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    assistant_name: str = Field(min_length=1, max_length=120)
    logo_url: str | None = Field(default=None, max_length=500)
    primary_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    welcome_message: str = Field(min_length=1, max_length=500)
    support_notice: str = Field(min_length=1, max_length=500)
    suggested_prompts: list[SuggestedPrompt] = Field(min_length=1, max_length=6)

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, value: str | None) -> str | None:
        if value in {None, ""}:
            return None
        if value.startswith("/") or value.startswith("https://") or value.startswith(
            "http://"
        ):
            return value
        raise ValueError("Logo URL must be an absolute HTTP URL or a local path")


def get_object_storage(request: Request) -> ObjectStorage:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is None:
        raise RuntimeError("Object storage is not configured")
    return storage


ObjectStorageDependency = Annotated[ObjectStorage, Depends(get_object_storage)]


def _not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{resource} not found")


@router.get("/me")
async def current_user(
    identity: Annotated[RequestIdentity, Depends(get_request_identity)],
) -> dict[str, Any]:
    return identity.model_dump(mode="json")


@router.get("/portal/config")
async def portal_config(
    identity: Annotated[RequestIdentity, Depends(get_request_identity)],
    store: StoreDependency,
) -> dict[str, Any]:
    branding = store.get_tenant_branding(identity)
    branding.pop("updated_by", None)
    service_status = "online" if ZAI_SETTINGS.configured else "offline"
    return {
        "branding": branding,
        "service": {
            "status": service_status,
            "label": "服务在线" if service_status == "online" else "服务暂不可用",
        },
        "capabilities": {
            "history": True,
            "citations": True,
            "feedback": False,
            "human_escalation": True,
            "anonymous_access": False,
        },
    }


@router.get("/portal/threads")
async def portal_threads(
    identity: Annotated[RequestIdentity, Depends(get_request_identity)],
    store: StoreDependency,
    limit: Annotated[int, Query(ge=1, le=30)] = 30,
    after: str | None = None,
) -> dict[str, Any]:
    return store.list_portal_thread_summaries(
        identity,
        limit=limit,
        after=after,
    )


@router.get("/admin/settings/branding")
async def get_branding_settings(
    identity: TenantAdmin,
    store: StoreDependency,
) -> dict[str, Any]:
    return store.get_tenant_branding(identity)


@router.patch("/admin/settings/branding")
async def update_branding_settings(
    payload: BrandingUpdate,
    identity: TenantAdmin,
    store: StoreDependency,
) -> dict[str, Any]:
    return store.update_tenant_branding(identity, **payload.model_dump(mode="json"))


@router.get("/knowledge/documents")
async def list_documents(
    identity: KnowledgeManager, store: StoreDependency
) -> dict[str, Any]:
    return {"data": store.list_documents(identity)}


@router.post("/knowledge/documents", status_code=201)
async def create_document(
    payload: DocumentCreate,
    identity: KnowledgeEditor,
    store: StoreDependency,
) -> dict[str, Any]:
    return store.create_document(identity, **payload.model_dump())


@router.post("/knowledge/documents/upload", status_code=201)
async def upload_document(
    identity: KnowledgeEditor,
    store: StoreDependency,
    object_storage: ObjectStorageDependency,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    category: Annotated[str, Form()] = "product",
    language: Annotated[str, Form()] = "zh-CN",
) -> dict[str, Any]:
    data = await file.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MB limit")
    filename = file.filename or "upload.txt"
    if category not in {"product", "compliance", "support", "sales"}:
        raise HTTPException(status_code=422, detail="Unsupported document category")
    if os.getenv("DOCUMENT_PROCESSING_MODE", "sync") == "async":
        object_key = document_object_key(identity.tenant_id, filename)
        object_storage.put(object_key, data, content_type=file.content_type)
        try:
            document = store.create_document(
                identity,
                title=title or Path(filename).stem,
                content="Document processing is pending.",
                category=category,
                language=language,
                source=filename,
            )
            return store.enqueue_document_processing(
                identity,
                document_id=document["id"],
                object_key=object_key,
                filename=filename,
                content_type=file.content_type,
                content_hash=hashlib.sha256(data).hexdigest(),
            )
        except Exception:
            object_storage.delete(object_key)
            raise
    try:
        content = extract_document_text(filename, data)
    except UnsupportedDocumentType as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    if not content:
        raise HTTPException(status_code=422, detail="No readable text was extracted")
    return store.create_document(
        identity,
        title=title or Path(filename).stem,
        content=content,
        category=category,
        language=language,
        source=filename,
    )


@router.get("/knowledge/documents/{document_id}")
async def get_document(
    document_id: str,
    identity: Annotated[RequestIdentity, Depends(get_request_identity)],
    store: StoreDependency,
) -> dict[str, Any]:
    try:
        return store.get_document(identity, document_id)
    except (KeyError, PermissionError) as exc:
        raise _not_found("Document") from exc


@router.get("/knowledge/documents/{document_id}/versions/{version}")
async def get_document_version(
    document_id: str,
    version: int,
    identity: KnowledgeManager,
    store: StoreDependency,
) -> dict[str, Any]:
    try:
        return store.get_document_version(identity, document_id, version)
    except KeyError as exc:
        raise _not_found("Document version") from exc


@router.post("/knowledge/documents/{document_id}/publish")
async def publish_document(
    document_id: str,
    identity: KnowledgeReviewer,
    store: StoreDependency,
) -> dict[str, Any]:
    try:
        return store.publish_document(identity, document_id)
    except KeyError as exc:
        raise _not_found("Document") from exc


@router.post("/knowledge/documents/{document_id}/deprecate")
async def deprecate_document(
    document_id: str,
    identity: KnowledgeReviewer,
    store: StoreDependency,
) -> dict[str, Any]:
    try:
        return store.deprecate_document(identity, document_id)
    except KeyError as exc:
        raise _not_found("Document") from exc


@router.post("/knowledge/search/test")
async def test_knowledge_search(
    payload: KnowledgeSearchRequest,
    identity: KnowledgeManager,
    store: StoreDependency,
) -> dict[str, Any]:
    results = store.search_knowledge(
        identity, payload.query, category=payload.category, limit=payload.limit
    )
    return {
        "status": "grounded" if results else "insufficient_evidence",
        "results": results,
        "knowledge_gap": not results,
    }


@router.get("/knowledge/gaps")
async def list_knowledge_gaps(
    identity: SupportOperator, store: StoreDependency
) -> dict[str, Any]:
    return {"data": store.list_knowledge_gaps(identity)}


@router.patch("/knowledge/gaps/{gap_id}")
async def update_knowledge_gap(
    gap_id: str,
    payload: KnowledgeGapUpdate,
    identity: SupportOperator,
    store: StoreDependency,
) -> dict[str, Any]:
    try:
        return store.update_knowledge_gap(identity, gap_id, **payload.model_dump())
    except KeyError as exc:
        raise _not_found("Knowledge gap") from exc


@router.get("/approvals")
async def list_approvals(
    identity: Annotated[RequestIdentity, Depends(get_request_identity)],
    store: StoreDependency,
) -> dict[str, Any]:
    approvals = store.list_approvals(identity)
    if not identity.has_any_role("tenant_admin", "support_agent"):
        approvals = [item for item in approvals if item["user_id"] == identity.user_id]
    return {"data": approvals}


@router.get("/action-drafts")
async def list_action_drafts(
    identity: Annotated[RequestIdentity, Depends(get_request_identity)],
    store: StoreDependency,
) -> dict[str, Any]:
    drafts = store.list_action_drafts(identity)
    if not identity.has_any_role("tenant_admin", "support_agent"):
        drafts = [item for item in drafts if item["user_id"] == identity.user_id]
    return {"data": drafts}


@router.post("/action-drafts/{draft_id}/submit")
async def submit_action_draft(
    draft_id: str,
    identity: Annotated[RequestIdentity, Depends(get_request_identity)],
    store: StoreDependency,
) -> dict[str, Any]:
    try:
        return store.submit_action_draft(identity, draft_id)
    except KeyError as exc:
        raise _not_found("Action draft") from exc


@router.post("/action-drafts/{draft_id}/decision")
async def decide_action_draft(
    draft_id: str,
    payload: ApprovalDecision,
    identity: ActionReviewer,
    store: StoreDependency,
) -> dict[str, Any]:
    try:
        return store.decide_action_draft(identity, draft_id, payload.decision)
    except KeyError as exc:
        raise _not_found("Action draft") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/action-drafts/{draft_id}/complete")
async def complete_action_draft(
    draft_id: str,
    payload: ActionDraftCompletion,
    identity: ActionReviewer,
    store: StoreDependency,
) -> dict[str, Any]:
    try:
        return store.complete_action_draft(
            identity,
            draft_id,
            external_record_id=payload.external_record_id,
            note=payload.note,
        )
    except KeyError as exc:
        raise _not_found("Action draft") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/decision")
async def decide_approval(
    approval_id: str,
    payload: ApprovalDecision,
    identity: Annotated[RequestIdentity, Depends(get_request_identity)],
    store: StoreDependency,
) -> dict[str, Any]:
    approvals = {item["id"]: item for item in store.list_approvals(identity)}
    approval = approvals.get(approval_id)
    if approval is None:
        raise _not_found("Approval")
    if (
        approval["user_id"] != identity.user_id
        and not identity.has_any_role("tenant_admin", "support_agent")
    ):
        raise _not_found("Approval")
    try:
        return store.decide_approval(identity, approval_id, payload.decision)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/admin/connectors")
async def list_connectors(
    identity: TenantAdmin,
    store: StoreDependency,
) -> dict[str, Any]:
    data = store.list_connectors(identity)
    for item in data:
        item.pop("tenant_id", None)
        item.pop("created_by", None)
    return {"data": data}


@router.get("/admin/members")
async def list_members(
    identity: TenantAdmin,
    store: StoreDependency,
) -> dict[str, Any]:
    store.authorize_identity(identity)
    data = store.list_members(identity)
    for item in data:
        item.pop("tenant_id", None)
    return {"data": data}


@router.patch("/admin/members/{user_id}")
async def update_member(
    user_id: str,
    payload: MemberUpdate,
    identity: TenantAdmin,
    store: StoreDependency,
) -> dict[str, Any]:
    try:
        result = store.update_member(
            identity,
            user_id,
            status=payload.status,
            roles=payload.roles,
        )
    except KeyError as exc:
        raise _not_found("Member") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    result.pop("tenant_id", None)
    return result


@router.post("/admin/connectors", status_code=201)
async def configure_connector(
    payload: ConnectorConfiguration,
    identity: TenantAdmin,
    store: StoreDependency,
) -> dict[str, Any]:
    expected_provider = {
        "crm": "hubspot",
        "ticketing": "jira",
        "usage": "usage_api",
        "documents": "confluence",
    }[payload.connector_type]
    if payload.provider != expected_provider:
        raise HTTPException(
            status_code=422,
            detail=f"{payload.connector_type} connectors must use {expected_provider} in this release",
        )
    try:
        validate_read_only_scopes(payload.provider, payload.granted_scopes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record = store.configure_connector(identity, **payload.model_dump(mode="json"))
    record.pop("tenant_id", None)
    record.pop("created_by", None)
    return record


@router.post("/admin/connectors/{connector_id}/test")
async def test_connector(
    connector_id: str,
    identity: TenantAdmin,
    gateway: ConnectorDependency,
) -> dict[str, Any]:
    try:
        return await gateway.test_connector(identity, connector_id)
    except KeyError as exc:
        raise _not_found("Connector") from exc
    except ConnectorError as exc:
        raise HTTPException(status_code=503, detail=exc.as_dict()) from exc


@router.post("/admin/connectors/{connector_id}/sync")
async def sync_document_connector(
    connector_id: str,
    identity: TenantAdmin,
    gateway: ConnectorDependency,
    store: StoreDependency,
) -> dict[str, Any]:
    try:
        connector = store.get_connector(identity, connector_id)
        if connector["connector_type"] != "documents":
            raise HTTPException(status_code=422, detail="Only document connectors can be synchronized")
        return await gateway.sync_documents(identity)
    except KeyError as exc:
        raise _not_found("Connector") from exc
    except ConnectorError as exc:
        raise HTTPException(status_code=503, detail=exc.as_dict()) from exc


@router.get("/admin/traces")
async def list_traces(
    identity: SupportOperator,
    store: StoreDependency,
    limit: int = 100,
) -> dict[str, Any]:
    return {"data": store.list_traces(identity, limit)}


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


@router.get("/admin/quality/summary")
async def quality_summary(
    identity: ActionReviewer,
    store: StoreDependency,
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    dataset_dir = project_root / "evals" / "datasets"
    result_dir = project_root / "evals" / "results"
    report_files = sorted(result_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True) if result_dir.exists() else []
    latest_report = None
    if report_files:
        try:
            report = json.loads(report_files[0].read_text(encoding="utf-8"))
            latest_report = {
                "file": report_files[0].name,
                "summary": report.get("summary"),
            }
        except (OSError, json.JSONDecodeError):
            latest_report = {"status": "invalid_report"}
    readiness = production_readiness_checks()
    app_env = os.getenv("APP_ENV", "development").lower()
    readiness_status = (
        "development"
        if app_env != "production"
        else ("ready" if all(check.passed for check in readiness) else "not_ready")
    )
    traces = store.list_traces(identity, 20)
    return {
        "evaluation": {
            "status": "completed" if latest_report else "not_run",
            "conversation_case_count": _jsonl_count(dataset_dir / "conversation-v1.jsonl"),
            "redteam_case_count": _jsonl_count(dataset_dir / "redteam-v1.jsonl"),
            "latest_report": latest_report,
        },
        "safety": {
            "external_write_policy": "draft_only",
            "automatic_external_writes_allowed": False,
            "critical_gate_mode": "fail_closed",
        },
        "readiness": {
            "status": readiness_status,
            "checks": [check.__dict__ for check in readiness],
        },
        "recent_traces": traces,
    }


@router.get("/audit-logs")
async def list_audit_logs(
    identity: SupportOperator,
    store: StoreDependency,
    limit: int = 100,
) -> dict[str, Any]:
    return {"data": store.list_audit_logs(identity, min(max(limit, 1), 500))}
