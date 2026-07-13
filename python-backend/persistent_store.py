from __future__ import annotations

import json
import hashlib
import math
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, Thread, ThreadItem, ThreadMetadata
from pydantic import TypeAdapter

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - only used when PostgreSQL is configured
    psycopg = None
    dict_row = None

from enterprise_support.identity import RequestIdentity, identity_from_context
from enterprise_support.security import PayloadCipher, payload_hash, redact_data


_THREAD_ITEM_ADAPTER = TypeAdapter(ThreadItem)
PLATFORM_TENANT_ID = "__platform__"
EMBEDDING_DIMENSIONS = 96

DEFAULT_SUGGESTED_PROMPTS = [
    {
        "label": "技术故障",
        "prompt": "我们的 API 持续出现 429 和超时，请帮我诊断并给出下一步。",
        "icon": "wrench",
    },
    {
        "label": "方案咨询",
        "prompt": "我们想建设带权限控制的企业知识库 Agent，请给出初步架构。",
        "icon": "network",
    },
    {
        "label": "安全合规",
        "prompt": "请介绍私有化部署、数据留存和安全合规相关能力。",
        "icon": "shield-check",
    },
    {
        "label": "账户服务",
        "prompt": "请帮我查询当前套餐、用量和续费信息。",
        "icon": "wallet-cards",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_json(model: Any) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)


def _json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _token_sequence(text: str) -> list[str]:
    normalized = text.lower()
    tokens = list(re.findall(r"[a-z0-9][a-z0-9_.-]+", normalized))
    for segment in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(segment) == 1:
            tokens.append(segment)
        else:
            tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
    return tokens


def _tokens(text: str) -> set[str]:
    return set(_token_sequence(text))


def _embedding_features(text: str) -> list[str]:
    normalized = text.lower()
    features = _token_sequence(normalized)
    for word in re.findall(r"[a-z0-9][a-z0-9_.-]+", normalized):
        if len(word) >= 5:
            features.extend(word[index : index + 4] for index in range(len(word) - 3))
    for segment in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(segment) >= 3:
            features.extend(segment[index : index + 3] for index in range(len(segment) - 2))
    return features


def _text_embedding(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for feature in _embedding_features(text):
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return []
    return [round(value / norm, 6) for value in vector]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def _chunk_content(content: str, limit: int = 900) -> list[tuple[str, str]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not paragraphs:
        return []
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    current_size = 0
    section = "正文"
    for paragraph in paragraphs:
        if len(paragraph) <= 100 and re.match(r"^(#{1,6}\s+|第.+[章节]|\d+[.、])", paragraph):
            section = paragraph.lstrip("# ")
        if current and current_size + len(paragraph) > limit:
            chunks.append((section, "\n\n".join(current)))
            current = []
            current_size = 0
        if len(paragraph) > limit:
            if current:
                chunks.append((section, "\n\n".join(current)))
                current = []
                current_size = 0
            for start in range(0, len(paragraph), limit):
                chunks.append((section, paragraph[start : start + limit]))
            continue
        current.append(paragraph)
        current_size += len(paragraph)
    if current:
        chunks.append((section, "\n\n".join(current)))
    return chunks


class _DatabaseConnection:
    """Small DB-API adapter keeping the store compatible with SQLite and PostgreSQL."""

    def __init__(self, target: str) -> None:
        self.backend = "postgresql" if target.startswith(("postgresql://", "postgresql+psycopg://")) else "sqlite"
        if self.backend == "postgresql":
            if psycopg is None:
                raise RuntimeError("psycopg is required when DATABASE_URL uses PostgreSQL")
            dsn = target.replace("postgresql+psycopg://", "postgresql://", 1)
            self._connection = psycopg.connect(dsn, row_factory=dict_row)
        else:
            self._connection = sqlite3.connect(target, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row

    def _sql(self, statement: str) -> str:
        if self.backend == "sqlite":
            return statement
        converted = statement.replace("?", "%s")
        converted = converted.replace(
            "json_extract(data_json, '$.type')",
            "(data_json::jsonb ->> 'type')",
        )
        return converted

    def execute(self, statement: str, parameters: tuple[Any, ...] | list[Any] = ()):
        return self._connection.execute(self._sql(statement), parameters)

    def executescript(self, script: str) -> None:
        if self.backend == "sqlite":
            self._connection.executescript(script)
            return
        for statement in script.split(";"):
            if statement.strip():
                self._connection.execute(statement)

    def commit(self) -> None:
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()


class PersistentStore(Store[dict[str, Any]]):
    """Tenant-aware SQLite/PostgreSQL store for pilots and production deployments."""

    def __init__(self, database_path: str | None = None) -> None:
        path = database_path or os.getenv("DATABASE_URL") or os.getenv(
            "DATABASE_PATH", "./data/enterprise_agent.db"
        )
        is_postgresql = path.startswith(("postgresql://", "postgresql+psycopg://"))
        if path != ":memory:" and not is_postgresql:
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.database_path = path
        self._lock = RLock()
        self._cipher = PayloadCipher()
        self.connector_gateway: Any | None = None
        self._conn = _DatabaseConnection(path)
        self.backend = self._conn.backend
        if self.backend == "sqlite":
            self._conn.execute("PRAGMA foreign_keys = ON")
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL")
        self._create_schema()
        self._ensure_schema_migrations()
        self._migrate_legacy_approvals()
        self._seed_platform_documents()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _create_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    data_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_threads_tenant_created
                    ON threads(tenant_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS thread_items (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
                    tenant_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    data_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_thread_items_thread_created
                    ON thread_items(thread_id, created_at);

                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    data_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_states (
                    thread_id TEXT PRIMARY KEY REFERENCES threads(id) ON DELETE CASCADE,
                    tenant_id TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    language TEXT NOT NULL,
                    source TEXT,
                    tags_json TEXT NOT NULL,
                    allowed_roles_json TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    published_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_documents_tenant_status
                    ON knowledge_documents(tenant_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS knowledge_document_versions (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT,
                    content_hash TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(document_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_document_versions_tenant_document
                    ON knowledge_document_versions(tenant_id, document_id, version DESC);

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                    tenant_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    section TEXT NOT NULL,
                    content TEXT NOT NULL,
                    allowed_roles_json TEXT NOT NULL,
                    embedding_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_tenant_document
                    ON knowledge_chunks(tenant_id, document_id, sequence);

                CREATE TABLE IF NOT EXISTS document_assets (
                    document_id TEXT PRIMARY KEY REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                    tenant_id TEXT NOT NULL,
                    object_key TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content_type TEXT,
                    content_hash TEXT NOT NULL,
                    processing_status TEXT NOT NULL,
                    processing_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS document_tasks (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    document_id TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    next_attempt_at TEXT NOT NULL,
                    locked_by TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_document_tasks_status_next
                    ON document_tasks(status, next_attempt_at);

                CREATE TABLE IF NOT EXISTS knowledge_gaps (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    normalized_question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    thread_id TEXT,
                    highest_score REAL,
                    assignee TEXT,
                    resolution_document_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_gaps_tenant_status
                    ON knowledge_gaps(tenant_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS approval_requests (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    thread_id TEXT,
                    action TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_approvals_tenant_status
                    ON approval_requests(tenant_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS action_drafts (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    thread_id TEXT,
                    connector_id TEXT,
                    action_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_encrypted TEXT NOT NULL,
                    payload_summary_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    expires_at TEXT,
                    external_record_id TEXT,
                    manually_completed_by TEXT,
                    manually_completed_at TEXT,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS idx_action_drafts_tenant_status
                    ON action_drafts(tenant_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS connector_configs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    connector_type TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    status TEXT NOT NULL,
                    credential_reference TEXT NOT NULL,
                    granted_scopes_json TEXT NOT NULL,
                    settings_json TEXT NOT NULL,
                    last_health_status TEXT,
                    last_error_status TEXT,
                    last_health_check_at TEXT,
                    last_success_at TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, connector_type, environment)
                );
                CREATE INDEX IF NOT EXISTS idx_connectors_tenant_type
                    ON connector_configs(tenant_id, connector_type, status);

                CREATE TABLE IF NOT EXISTS trace_runs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    thread_id TEXT,
                    request_id TEXT NOT NULL,
                    model TEXT,
                    agent_name TEXT,
                    status TEXT NOT NULL,
                    duration_ms REAL,
                    event_summary_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_trace_runs_tenant_created
                    ON trace_runs(tenant_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    dataset_version TEXT NOT NULL,
                    model_config_version TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    tool_contract_version TEXT NOT NULL,
                    knowledge_snapshot TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    status TEXT NOT NULL,
                    aggregate_scores_json TEXT NOT NULL,
                    critical_failure_count INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS human_escalations (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    thread_id TEXT,
                    reason TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    actor_user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    result TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_tenant_created
                    ON audit_logs(tenant_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS tenant_members (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    roles_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    last_login_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id, user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_members_tenant_status
                    ON tenant_members(tenant_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS tenant_branding (
                    tenant_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    assistant_name TEXT NOT NULL,
                    logo_url TEXT,
                    primary_color TEXT NOT NULL,
                    welcome_message TEXT NOT NULL,
                    support_notice TEXT NOT NULL,
                    suggested_prompts_json TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    published_at TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def _table_columns(self, table_name: str) -> set[str]:
        if table_name not in {"knowledge_chunks"}:
            raise ValueError(f"Unsupported table for schema inspection: {table_name}")
        if self.backend == "sqlite":
            rows = self._conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            return {row["name"] for row in rows}
        rows = self._conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = ?
            """,
            (table_name,),
        ).fetchall()
        return {row["column_name"] for row in rows}

    def _ensure_schema_migrations(self) -> None:
        with self._lock:
            if "embedding_json" not in self._table_columns("knowledge_chunks"):
                self._conn.execute(
                    "ALTER TABLE knowledge_chunks ADD COLUMN embedding_json TEXT NOT NULL DEFAULT '[]'"
                )
            self._conn.commit()

    def _migrate_legacy_approvals(self) -> None:
        """Preserve old proposals without carrying simulated execution claims forward."""

        with self._lock:
            rows = self._conn.execute("SELECT * FROM approval_requests").fetchall()
            for row in rows:
                exists = self._conn.execute(
                    "SELECT 1 FROM action_drafts WHERE id = ?", (row["id"],)
                ).fetchone()
                if exists:
                    continue
                parameters = json.loads(row["parameters_json"])
                digest = payload_hash(parameters)
                status = {
                    "pending": "draft",
                    "approved": "approved_for_manual_execution",
                    "rejected": "rejected",
                }.get(row["status"], "cancelled")
                result = (
                    {
                        "executed": False,
                        "mode": "draft_only",
                        "manual_execution_required": status == "approved_for_manual_execution",
                        "legacy_simulated_result_discarded": row["status"] == "approved",
                    }
                    if row["status"] in {"approved", "rejected"}
                    else None
                )
                self._conn.execute(
                    """
                    INSERT INTO action_drafts(
                        id, tenant_id, user_id, thread_id, connector_id,
                        action_type, status, payload_encrypted, payload_summary_json,
                        payload_hash, idempotency_key, requested_by, reviewed_by,
                        reviewed_at, expires_at, external_record_id,
                        manually_completed_by, manually_completed_at, result_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL, NULL,
                              NULL, NULL, NULL, NULL, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        row["tenant_id"],
                        row["user_id"],
                        row["thread_id"],
                        row["action"],
                        status,
                        self._cipher.encrypt_json(parameters),
                        _json_value(redact_data(parameters, mask_personal_data=True)),
                        digest,
                        f"legacy:{row['id']}",
                        row["user_id"],
                        _json_value(result) if result else None,
                        row["created_at"],
                        row["updated_at"],
                    ),
                )
            self._conn.commit()

    @staticmethod
    def _thread_metadata(thread: ThreadMetadata | Thread) -> ThreadMetadata:
        has_items = isinstance(thread, Thread) or "items" in getattr(
            thread, "model_fields_set", set()
        )
        if not has_items:
            return thread.model_copy(deep=True)
        data = thread.model_dump()
        data.pop("items", None)
        return ThreadMetadata(**data)

    def _identity(self, context: dict[str, Any]) -> RequestIdentity:
        return identity_from_context(context)

    def _thread_row(
        self, thread_id: str, identity: RequestIdentity
    ) -> sqlite3.Row:
        row = self._conn.execute(
            "SELECT * FROM threads WHERE id = ? AND tenant_id = ?",
            (thread_id, identity.tenant_id),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Thread {thread_id} not found")
        if (
            row["owner_user_id"] != identity.user_id
            and not identity.has_any_role("tenant_admin", "support_agent")
        ):
            raise NotFoundError(f"Thread {thread_id} not found")
        return row

    async def load_thread(
        self, thread_id: str, context: dict[str, Any]
    ) -> ThreadMetadata:
        identity = self._identity(context)
        with self._lock:
            row = self._thread_row(thread_id, identity)
            return ThreadMetadata.model_validate_json(row["data_json"])

    async def save_thread(
        self, thread: ThreadMetadata, context: dict[str, Any]
    ) -> None:
        identity = self._identity(context)
        metadata = self._thread_metadata(thread)
        created_at = (metadata.created_at or datetime.now(timezone.utc)).isoformat()
        with self._lock:
            existing = self._conn.execute(
                "SELECT tenant_id FROM threads WHERE id = ?", (thread.id,)
            ).fetchone()
            if existing is not None and existing["tenant_id"] != identity.tenant_id:
                raise NotFoundError(f"Thread {thread.id} not found")
            self._conn.execute(
                """
                INSERT INTO threads(id, tenant_id, owner_user_id, created_at, data_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET data_json = excluded.data_json
                """,
                (
                    thread.id,
                    identity.tenant_id,
                    identity.user_id,
                    created_at,
                    _model_json(metadata),
                ),
            )
            self._conn.commit()

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadMetadata]:
        identity = self._identity(context)
        direction = "DESC" if order == "desc" else "ASC"
        with self._lock:
            if identity.has_any_role("tenant_admin", "support_agent"):
                rows = self._conn.execute(
                    f"SELECT id, data_json FROM threads WHERE tenant_id = ? ORDER BY created_at {direction}",
                    (identity.tenant_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    f"SELECT id, data_json FROM threads WHERE tenant_id = ? AND owner_user_id = ? ORDER BY created_at {direction}",
                    (identity.tenant_id, identity.user_id),
                ).fetchall()
        start = 0
        if after:
            ids = [row["id"] for row in rows]
            start = ids.index(after) + 1 if after in ids else 0
        page_rows = rows[start : start + limit + 1]
        has_more = len(page_rows) > limit
        page_rows = page_rows[:limit]
        data = [ThreadMetadata.model_validate_json(row["data_json"]) for row in page_rows]
        return Page(
            data=data,
            has_more=has_more,
            after=data[-1].id if has_more and data else None,
        )

    @staticmethod
    def _thread_item_text(data_json: str) -> str:
        try:
            item = json.loads(data_json)
        except (TypeError, json.JSONDecodeError):
            return ""
        parts = item.get("content", [])
        if not isinstance(parts, list):
            return ""
        text = " ".join(
            str(part.get("text", "")).strip()
            for part in parts
            if isinstance(part, dict) and part.get("text")
        )
        return " ".join(text.split())

    @staticmethod
    def _summary_text(text: str, limit: int) -> str:
        return text if len(text) <= limit else f"{text[:limit].rstrip()}..."

    def list_portal_thread_summaries(
        self,
        identity: RequestIdentity,
        *,
        limit: int = 30,
        after: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    t.id,
                    t.created_at,
                    t.data_json,
                    COALESCE(MAX(i.created_at), t.created_at) AS updated_at
                FROM threads t
                LEFT JOIN thread_items i
                    ON i.thread_id = t.id AND i.tenant_id = t.tenant_id
                WHERE t.tenant_id = ? AND t.owner_user_id = ?
                GROUP BY t.id, t.created_at, t.data_json
                HAVING COUNT(i.id) > 0
                ORDER BY updated_at DESC
                """,
                (identity.tenant_id, identity.user_id),
            ).fetchall()

            start = 0
            if after:
                ids = [row["id"] for row in rows]
                start = ids.index(after) + 1 if after in ids else 0
            page_rows = rows[start : start + limit + 1]
            has_more = len(page_rows) > limit
            page_rows = page_rows[:limit]

            summaries: list[dict[str, Any]] = []
            for row in page_rows:
                first_user = self._conn.execute(
                    """
                    SELECT data_json FROM thread_items
                    WHERE thread_id = ? AND tenant_id = ?
                      AND json_extract(data_json, '$.type') = 'user_message'
                    ORDER BY created_at ASC LIMIT 1
                    """,
                    (row["id"], identity.tenant_id),
                ).fetchone()
                latest_item = self._conn.execute(
                    """
                    SELECT data_json FROM thread_items
                    WHERE thread_id = ? AND tenant_id = ?
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (row["id"], identity.tenant_id),
                ).fetchone()
                metadata = json.loads(row["data_json"])
                first_text = (
                    self._thread_item_text(first_user["data_json"])
                    if first_user
                    else ""
                )
                latest_text = (
                    self._thread_item_text(latest_item["data_json"])
                    if latest_item
                    else ""
                )
                title = metadata.get("title") or first_text or "新会话"
                summaries.append(
                    {
                        "id": row["id"],
                        "title": self._summary_text(str(title), 36),
                        "preview": self._summary_text(latest_text or first_text, 72),
                        "updated_at": row["updated_at"],
                    }
                )

        return {
            "data": summaries,
            "has_more": has_more,
            "after": summaries[-1]["id"] if has_more and summaries else None,
        }

    async def delete_thread(self, thread_id: str, context: dict[str, Any]) -> None:
        identity = self._identity(context)
        with self._lock:
            self._thread_row(thread_id, identity)
            self._conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            self._conn.commit()

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadItem]:
        identity = self._identity(context)
        direction = "DESC" if order == "desc" else "ASC"
        with self._lock:
            self._thread_row(thread_id, identity)
            rows = self._conn.execute(
                f"SELECT id, data_json FROM thread_items WHERE thread_id = ? AND tenant_id = ? ORDER BY created_at {direction}",
                (thread_id, identity.tenant_id),
            ).fetchall()
        start = 0
        if after:
            ids = [row["id"] for row in rows]
            start = ids.index(after) + 1 if after in ids else 0
        page_rows = rows[start : start + limit + 1]
        has_more = len(page_rows) > limit
        page_rows = page_rows[:limit]
        data = [
            _THREAD_ITEM_ADAPTER.validate_json(row["data_json"]) for row in page_rows
        ]
        return Page(
            data=data,
            has_more=has_more,
            after=data[-1].id if has_more and data else None,
        )

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        await self.save_item(thread_id, item, context)

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        identity = self._identity(context)
        created_at = getattr(item, "created_at", None) or datetime.now(timezone.utc)
        with self._lock:
            self._thread_row(thread_id, identity)
            self._conn.execute(
                """
                INSERT INTO thread_items(id, thread_id, tenant_id, created_at, data_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET data_json = excluded.data_json
                """,
                (
                    item.id,
                    thread_id,
                    identity.tenant_id,
                    created_at.isoformat(),
                    _model_json(item),
                ),
            )
            self._conn.commit()

    async def load_item(
        self,
        thread_id: str,
        item_id: str,
        context: dict[str, Any],
    ) -> ThreadItem:
        identity = self._identity(context)
        with self._lock:
            self._thread_row(thread_id, identity)
            row = self._conn.execute(
                "SELECT data_json FROM thread_items WHERE id = ? AND thread_id = ? AND tenant_id = ?",
                (item_id, thread_id, identity.tenant_id),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Item {item_id} not found")
        return _THREAD_ITEM_ADAPTER.validate_json(row["data_json"])

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: dict[str, Any]
    ) -> None:
        identity = self._identity(context)
        with self._lock:
            self._thread_row(thread_id, identity)
            self._conn.execute(
                "DELETE FROM thread_items WHERE id = ? AND thread_id = ? AND tenant_id = ?",
                (item_id, thread_id, identity.tenant_id),
            )
            self._conn.commit()

    async def save_attachment(
        self, attachment: Attachment, context: dict[str, Any]
    ) -> None:
        identity = self._identity(context)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO attachments(id, tenant_id, data_json) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET data_json = excluded.data_json
                """,
                (attachment.id, identity.tenant_id, _model_json(attachment)),
            )
            self._conn.commit()

    async def load_attachment(
        self, attachment_id: str, context: dict[str, Any]
    ) -> Attachment:
        identity = self._identity(context)
        with self._lock:
            row = self._conn.execute(
                "SELECT data_json FROM attachments WHERE id = ? AND tenant_id = ?",
                (attachment_id, identity.tenant_id),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Attachment {attachment_id} not found")
        return Attachment.model_validate_json(row["data_json"])

    async def delete_attachment(
        self, attachment_id: str, context: dict[str, Any]
    ) -> None:
        identity = self._identity(context)
        with self._lock:
            self._conn.execute(
                "DELETE FROM attachments WHERE id = ? AND tenant_id = ?",
                (attachment_id, identity.tenant_id),
            )
            self._conn.commit()

    def load_conversation_state(
        self, thread_id: str, context: dict[str, Any]
    ) -> dict[str, Any] | None:
        identity = self._identity(context)
        with self._lock:
            self._thread_row(thread_id, identity)
            row = self._conn.execute(
                "SELECT data_json FROM conversation_states WHERE thread_id = ? AND tenant_id = ?",
                (thread_id, identity.tenant_id),
            ).fetchone()
        return json.loads(row["data_json"]) if row else None

    def save_conversation_state(
        self,
        thread_id: str,
        state: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        identity = self._identity(context)
        with self._lock:
            self._thread_row(thread_id, identity)
            self._conn.execute(
                """
                INSERT INTO conversation_states(thread_id, tenant_id, data_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    data_json = excluded.data_json,
                    updated_at = excluded.updated_at
                """,
                (thread_id, identity.tenant_id, _json_value(state), _now()),
            )
            self._conn.commit()

    def _seed_platform_documents(self) -> None:
        documents = [
            (
                "platform-agent-overview",
                "Agent Platform overview",
                "product",
                "The Agent Platform supports specialist handoffs, tool execution, streaming, and trace-based debugging.",
            ),
            (
                "platform-api-reliability",
                "Model API reliability guide",
                "product",
                "Use exponential backoff with jitter for transient 429 and 5xx responses. Persist request IDs for support diagnostics.",
            ),
            (
                "platform-rag",
                "Enterprise knowledge retrieval",
                "product",
                "Retrieval must preserve document-level permissions and return source identifiers with every grounded answer.",
            ),
            (
                "platform-security",
                "Security and data controls",
                "compliance",
                "Enterprise deployments support SSO, role-based access, audit logs, configurable retention, and private network patterns.",
            ),
            (
                "platform-soc2",
                "SOC 2 trust center policy",
                "compliance",
                "A current SOC 2 report can be shared through the controlled trust-center workflow under NDA.",
            ),
            (
                "platform-retention",
                "Data retention policy",
                "compliance",
                "Retention is configurable by product and contract. Confirm the tenant policy before stating a duration.",
            ),
        ]
        with self._lock:
            for slug, title, category, content in documents:
                document_id = f"doc_{slug}"
                exists = self._conn.execute(
                    "SELECT 1 FROM knowledge_documents WHERE id = ?", (document_id,)
                ).fetchone()
                if exists:
                    continue
                now = _now()
                cursor = self._conn.execute(
                    """
                    INSERT INTO knowledge_documents(
                        id, tenant_id, title, content, category, status, version,
                        language, source, tags_json, allowed_roles_json,
                        created_by, created_at, updated_at, published_at
                    ) VALUES (?, ?, ?, ?, ?, 'published', 1, 'en', 'platform', '[]', '[]',
                              'platform', ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        document_id,
                        PLATFORM_TENANT_ID,
                        title,
                        content,
                        category,
                        now,
                        now,
                        now,
                    ),
                )
                if cursor.rowcount:
                    self._rebuild_chunks(document_id)
            self._conn.commit()

    def _rebuild_chunks(self, document_id: str) -> None:
        document = self._conn.execute(
            "SELECT * FROM knowledge_documents WHERE id = ?", (document_id,)
        ).fetchone()
        if document is None:
            raise KeyError(document_id)
        self._conn.execute(
            "DELETE FROM knowledge_chunks WHERE document_id = ?", (document_id,)
        )
        chunks = _chunk_content(document["content"])
        for sequence, (section, content) in enumerate(chunks):
            self._conn.execute(
                """
                INSERT INTO knowledge_chunks(
                    id, document_id, tenant_id, sequence, section, content,
                    allowed_roles_json, embedding_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"chk_{uuid4().hex[:12]}",
                    document_id,
                    document["tenant_id"],
                    sequence,
                    section,
                    content,
                    document["allowed_roles_json"],
                    _json_value(_text_embedding(f"{document['title']} {section} {content}")),
                ),
            )

    @staticmethod
    def _document_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["tags"] = json.loads(data.pop("tags_json"))
        data["allowed_roles"] = json.loads(data.pop("allowed_roles_json"))
        data.pop("content", None)
        return data

    def list_documents(self, identity: RequestIdentity) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM knowledge_documents WHERE tenant_id = ? ORDER BY updated_at DESC",
                (identity.tenant_id,),
            ).fetchall()
        return [self._document_dict(row) for row in rows]

    def get_document(
        self, identity: RequestIdentity, document_id: str
    ) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM knowledge_documents WHERE id = ? AND tenant_id = ?",
                (document_id, identity.tenant_id),
            ).fetchone()
        if row is None:
            raise KeyError(document_id)
        data = self._document_dict(row)
        allowed_roles = set(data["allowed_roles"])
        if (
            allowed_roles
            and not allowed_roles.intersection(identity.roles)
            and "tenant_admin" not in identity.roles
        ):
            raise PermissionError(document_id)
        data["content"] = row["content"]
        return data

    def create_document(
        self,
        identity: RequestIdentity,
        *,
        title: str,
        content: str,
        category: str = "product",
        language: str = "zh-CN",
        source: str | None = None,
        tags: list[str] | None = None,
        allowed_roles: list[str] | None = None,
    ) -> dict[str, Any]:
        document_id = f"doc_{uuid4().hex[:12]}"
        now = _now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO knowledge_documents(
                    id, tenant_id, title, content, category, status, version,
                    language, source, tags_json, allowed_roles_json,
                    created_by, created_at, updated_at, published_at
                ) VALUES (?, ?, ?, ?, ?, 'draft', 1, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    document_id,
                    identity.tenant_id,
                    title,
                    content,
                    category,
                    language,
                    source,
                    _json_value(tags or []),
                    _json_value(allowed_roles or []),
                    identity.user_id,
                    now,
                    now,
                ),
            )
            self._conn.execute(
                """
                INSERT INTO knowledge_document_versions(
                    id, document_id, tenant_id, version, title, content, status,
                    source, content_hash, created_by, created_at
                ) VALUES (?, ?, ?, 1, ?, ?, 'draft', ?, ?, ?, ?)
                """,
                (
                    f"dver_{uuid4().hex[:12]}",
                    document_id,
                    identity.tenant_id,
                    title,
                    content,
                    source,
                    payload_hash(content),
                    identity.user_id,
                    now,
                ),
            )
            self._audit(
                identity,
                "knowledge.document.create",
                "knowledge_document",
                document_id,
                "success",
                {"title": title},
            )
            self._conn.commit()
        return self.get_document(identity, document_id)

    def sync_external_document(
        self,
        identity: RequestIdentity,
        *,
        title: str,
        content: str,
        source: str,
        category: str = "product",
        language: str = "zh-CN",
    ) -> dict[str, Any]:
        digest = payload_hash(content)
        now = _now()
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM knowledge_documents
                WHERE tenant_id = ? AND source = ?
                ORDER BY version DESC LIMIT 1
                """,
                (identity.tenant_id, source),
            ).fetchone()
            if row is not None and payload_hash(row["content"]) == digest:
                result = self._document_dict(row)
                result["content"] = row["content"]
                result["sync_status"] = "unchanged"
                return result
            if row is None:
                document_id = f"doc_{uuid4().hex[:12]}"
                version = 1
                self._conn.execute(
                    """
                    INSERT INTO knowledge_documents(
                        id, tenant_id, title, content, category, status, version,
                        language, source, tags_json, allowed_roles_json,
                        created_by, created_at, updated_at, published_at
                    ) VALUES (?, ?, ?, ?, ?, 'review_pending', 1, ?, ?, '[]', '[]', ?, ?, ?, NULL)
                    """,
                    (
                        document_id,
                        identity.tenant_id,
                        title,
                        content,
                        category,
                        language,
                        source,
                        identity.user_id,
                        now,
                        now,
                    ),
                )
            else:
                document_id = row["id"]
                version = int(row["version"]) + 1
                self._conn.execute(
                    """
                    UPDATE knowledge_documents
                    SET title = ?, content = ?, status = 'review_pending',
                        version = ?, updated_at = ?, published_at = NULL
                    WHERE id = ? AND tenant_id = ?
                    """,
                    (title, content, version, now, document_id, identity.tenant_id),
                )
                self._conn.execute(
                    "DELETE FROM knowledge_chunks WHERE document_id = ?", (document_id,)
                )
            self._conn.execute(
                """
                INSERT INTO knowledge_document_versions(
                    id, document_id, tenant_id, version, title, content, status,
                    source, content_hash, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'review_pending', ?, ?, ?, ?)
                ON CONFLICT(document_id, version) DO NOTHING
                """,
                (
                    f"dver_{uuid4().hex[:12]}",
                    document_id,
                    identity.tenant_id,
                    version,
                    title,
                    content,
                    source,
                    digest,
                    identity.user_id,
                    now,
                ),
            )
            self._audit(
                identity,
                "knowledge.document.external_sync",
                "knowledge_document",
                document_id,
                "success",
                {"source": source, "version": version, "status": "review_pending"},
            )
            self._conn.commit()
        result = self.get_document(identity, document_id)
        result["sync_status"] = "created" if row is None else "updated"
        return result

    def get_document_version(
        self,
        identity: RequestIdentity,
        document_id: str,
        version: int,
    ) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM knowledge_document_versions
                WHERE document_id = ? AND tenant_id = ? AND version = ?
                """,
                (document_id, identity.tenant_id, version),
            ).fetchone()
        if row is None:
            raise KeyError(document_id)
        return dict(row)

    def enqueue_document_processing(
        self,
        identity: RequestIdentity,
        *,
        document_id: str,
        object_key: str,
        filename: str,
        content_type: str | None,
        content_hash: str,
    ) -> dict[str, Any]:
        task_id = f"dtk_{uuid4().hex[:12]}"
        now = _now()
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM knowledge_documents WHERE id = ? AND tenant_id = ?",
                (document_id, identity.tenant_id),
            ).fetchone()
            if row is None:
                raise KeyError(document_id)
            self._conn.execute(
                "UPDATE knowledge_documents SET status = 'processing', updated_at = ? WHERE id = ?",
                (now, document_id),
            )
            self._conn.execute(
                """
                INSERT INTO document_assets(
                    document_id, tenant_id, object_key, filename, content_type,
                    content_hash, processing_status, processing_error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'queued', NULL, ?, ?)
                """,
                (
                    document_id,
                    identity.tenant_id,
                    object_key,
                    filename,
                    content_type,
                    content_hash,
                    now,
                    now,
                ),
            )
            self._conn.execute(
                """
                INSERT INTO document_tasks(
                    id, tenant_id, document_id, task_type, status, attempts,
                    max_attempts, next_attempt_at, locked_by, last_error,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'parse_and_index', 'queued', 0, 3, ?, NULL, NULL, ?, ?)
                """,
                (task_id, identity.tenant_id, document_id, now, now, now),
            )
            self._audit(
                identity,
                "knowledge.document.processing_queued",
                "knowledge_document",
                document_id,
                "success",
                {"task_id": task_id, "content_hash": content_hash},
            )
            self._conn.commit()
        document = self.get_document(identity, document_id)
        document.update({"processing_status": "queued", "processing_task_id": task_id})
        return document

    def claim_document_task(self, worker_id: str) -> dict[str, Any] | None:
        now = _now()
        with self._lock:
            query = """
                SELECT t.*, a.object_key, a.filename, a.content_type
                FROM document_tasks t
                JOIN document_assets a ON a.document_id = t.document_id
                WHERE t.status = 'queued' AND t.next_attempt_at <= ?
                  AND t.attempts < t.max_attempts
                ORDER BY t.created_at
                LIMIT 1
            """
            if self.backend == "postgresql":
                query = query.rstrip() + " FOR UPDATE SKIP LOCKED"
            row = self._conn.execute(query, (now,)).fetchone()
            if row is None:
                return None
            self._conn.execute(
                """
                UPDATE document_tasks
                SET status = 'processing', attempts = attempts + 1,
                    locked_by = ?, updated_at = ?
                WHERE id = ?
                """,
                (worker_id, now, row["id"]),
            )
            self._conn.execute(
                "UPDATE document_assets SET processing_status = 'processing', updated_at = ? WHERE document_id = ?",
                (now, row["document_id"]),
            )
            self._conn.commit()
        return dict(row)

    def complete_document_task(
        self,
        task: dict[str, Any],
        *,
        content: str,
    ) -> None:
        now = _now()
        identity = RequestIdentity(
            tenant_id=task["tenant_id"],
            user_id=str(task.get("locked_by") or "document-worker"),
            roles=frozenset({"knowledge_editor"}),
        )
        with self._lock:
            self._conn.execute(
                """
                UPDATE knowledge_documents
                SET content = ?, status = 'review_pending', updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (content, now, task["document_id"], task["tenant_id"]),
            )
            self._conn.execute(
                "UPDATE document_assets SET processing_status = 'review_pending', processing_error = NULL, updated_at = ? WHERE document_id = ?",
                (now, task["document_id"]),
            )
            self._conn.execute(
                "UPDATE document_tasks SET status = 'completed', locked_by = NULL, updated_at = ? WHERE id = ?",
                (now, task["id"]),
            )
            self._audit(
                identity,
                "knowledge.document.processing_complete",
                "knowledge_document",
                task["document_id"],
                "success",
                {"task_id": task["id"]},
            )
            self._conn.commit()

    def fail_document_task(self, task: dict[str, Any], error: str) -> None:
        now = datetime.now(timezone.utc)
        attempts = int(task.get("attempts", 0)) + 1
        max_attempts = int(task.get("max_attempts", 3))
        retry = attempts < max_attempts
        next_attempt = (now + timedelta(seconds=min(300, 2**attempts * 5))).isoformat()
        safe_error = str(redact_data(error, mask_personal_data=True))[:1000]
        with self._lock:
            self._conn.execute(
                """
                UPDATE document_tasks
                SET status = ?, next_attempt_at = ?, locked_by = NULL,
                    last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                ("queued" if retry else "failed", next_attempt, safe_error, now.isoformat(), task["id"]),
            )
            self._conn.execute(
                "UPDATE document_assets SET processing_status = ?, processing_error = ?, updated_at = ? WHERE document_id = ?",
                ("queued" if retry else "failed", safe_error, now.isoformat(), task["document_id"]),
            )
            if not retry:
                self._conn.execute(
                    "UPDATE knowledge_documents SET status = 'failed', updated_at = ? WHERE id = ?",
                    (now.isoformat(), task["document_id"]),
                )
            self._conn.commit()

    def publish_document(
        self, identity: RequestIdentity, document_id: str
    ) -> dict[str, Any]:
        now = _now()
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM knowledge_documents WHERE id = ? AND tenant_id = ?",
                (document_id, identity.tenant_id),
            ).fetchone()
            if row is None:
                raise KeyError(document_id)
            self._conn.execute(
                "UPDATE knowledge_documents SET status = 'published', published_at = ?, updated_at = ? WHERE id = ?",
                (now, now, document_id),
            )
            version_row = self._conn.execute(
                "SELECT version FROM knowledge_documents WHERE id = ?", (document_id,)
            ).fetchone()
            self._conn.execute(
                "UPDATE knowledge_document_versions SET status = 'published' WHERE document_id = ? AND version = ?",
                (document_id, version_row["version"]),
            )
            self._rebuild_chunks(document_id)
            self._audit(
                identity,
                "knowledge.document.publish",
                "knowledge_document",
                document_id,
                "success",
                {},
            )
            self._conn.commit()
        return self.get_document(identity, document_id)

    def deprecate_document(
        self, identity: RequestIdentity, document_id: str
    ) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM knowledge_documents WHERE id = ? AND tenant_id = ?",
                (document_id, identity.tenant_id),
            ).fetchone()
            if row is None:
                raise KeyError(document_id)
            self._conn.execute(
                "UPDATE knowledge_documents SET status = 'deprecated', updated_at = ? WHERE id = ?",
                (_now(), document_id),
            )
            version_row = self._conn.execute(
                "SELECT version FROM knowledge_documents WHERE id = ?", (document_id,)
            ).fetchone()
            self._conn.execute(
                "UPDATE knowledge_document_versions SET status = 'deprecated' WHERE document_id = ? AND version = ?",
                (document_id, version_row["version"]),
            )
            self._audit(
                identity,
                "knowledge.document.deprecate",
                "knowledge_document",
                document_id,
                "success",
                {},
            )
            self._conn.commit()
        return self.get_document(identity, document_id)

    def search_knowledge(
        self,
        identity: RequestIdentity,
        query: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        query_tokens = _tokens(query)
        query_features = set(_embedding_features(query))
        query_vector = _text_embedding(query)
        if not query_tokens and not query_vector:
            return []
        params: list[Any] = [identity.tenant_id, PLATFORM_TENANT_ID]
        category_filter = ""
        if category:
            category_filter = " AND d.category = ?"
            params.append(category)
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT c.*, d.title, d.version, d.status, d.category, d.source
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.id = c.document_id
                WHERE d.tenant_id IN (?, ?) AND d.status = 'published'{category_filter}
                """,
                params,
            ).fetchall()
        scored: list[tuple[float, dict[str, float], sqlite3.Row]] = []
        normalized_query = query.lower().strip()
        for row in rows:
            allowed_roles = set(json.loads(row["allowed_roles_json"]))
            if allowed_roles and not allowed_roles.intersection(identity.roles):
                continue
            haystack = f"{row['title']} {row['section']} {row['content']}"
            haystack_tokens = _tokens(haystack)
            overlap = query_tokens.intersection(haystack_tokens)
            lexical_score = len(overlap) / max(len(query_tokens), 1)
            try:
                row_vector = json.loads(row["embedding_json"] or "[]")
            except json.JSONDecodeError:
                row_vector = []
            if not row_vector:
                row_vector = _text_embedding(haystack)
            vector_score = max(_cosine_similarity(query_vector, row_vector), 0.0)
            phrase_score = 1.0 if normalized_query and normalized_query in haystack.lower() else 0.0
            if not overlap and phrase_score == 0:
                feature_overlap = query_features.intersection(_embedding_features(haystack))
                if vector_score < 0.28 or not feature_overlap:
                    continue
            score = (lexical_score * 0.55) + (vector_score * 0.35) + (phrase_score * 0.1)
            if score >= 0.08:
                scored.append(
                    (
                        score,
                        {
                            "lexical": round(lexical_score, 4),
                            "vector": round(vector_score, 4),
                            "phrase": round(phrase_score, 4),
                        },
                        row,
                    )
                )
        scored.sort(
            key=lambda item: (
                item[0],
                item[2]["tenant_id"] == identity.tenant_id,
            ),
            reverse=True,
        )
        return [
            {
                "document_id": row["document_id"],
                "version": row["version"],
                "title": row["title"],
                "section": row["section"],
                "content": row["content"],
                "score": round(score, 4),
                "retrieval": "hybrid",
                "score_components": components,
                "source_scope": "platform"
                if row["tenant_id"] == PLATFORM_TENANT_ID
                else "tenant",
                "citation_url": f"/v1/knowledge/documents/{row['document_id']}",
            }
            for score, components, row in scored[:limit]
        ]

    def create_knowledge_gap(
        self,
        identity: RequestIdentity,
        question: str,
        *,
        source: str = "agent",
        thread_id: str | None = None,
        highest_score: float | None = None,
    ) -> dict[str, Any]:
        normalized = " ".join(question.lower().split())
        now = _now()
        with self._lock:
            existing = self._conn.execute(
                """
                SELECT * FROM knowledge_gaps
                WHERE tenant_id = ? AND normalized_question = ?
                  AND status IN ('new', 'triaged', 'content_needed')
                ORDER BY created_at DESC LIMIT 1
                """,
                (identity.tenant_id, normalized),
            ).fetchone()
            if existing:
                return dict(existing)
            gap_id = f"gap_{uuid4().hex[:12]}"
            self._conn.execute(
                """
                INSERT INTO knowledge_gaps(
                    id, tenant_id, question, normalized_question, status, source,
                    thread_id, highest_score, assignee, resolution_document_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'new', ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    gap_id,
                    identity.tenant_id,
                    question,
                    normalized,
                    source,
                    thread_id,
                    highest_score,
                    now,
                    now,
                ),
            )
            self._audit(
                identity,
                "knowledge.gap.create",
                "knowledge_gap",
                gap_id,
                "success",
                {"source": source},
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM knowledge_gaps WHERE id = ?", (gap_id,)
            ).fetchone()
        return dict(row)

    def list_knowledge_gaps(self, identity: RequestIdentity) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM knowledge_gaps WHERE tenant_id = ? ORDER BY updated_at DESC",
                (identity.tenant_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_knowledge_gap(
        self,
        identity: RequestIdentity,
        gap_id: str,
        *,
        status: str,
        assignee: str | None = None,
        resolution_document_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM knowledge_gaps WHERE id = ? AND tenant_id = ?",
                (gap_id, identity.tenant_id),
            ).fetchone()
            if row is None:
                raise KeyError(gap_id)
            self._conn.execute(
                """
                UPDATE knowledge_gaps
                SET status = ?, assignee = ?, resolution_document_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, assignee, resolution_document_id, _now(), gap_id),
            )
            self._audit(
                identity,
                "knowledge.gap.update",
                "knowledge_gap",
                gap_id,
                "success",
                {"status": status},
            )
            self._conn.commit()
            updated = self._conn.execute(
                "SELECT * FROM knowledge_gaps WHERE id = ?", (gap_id,)
            ).fetchone()
        return dict(updated)

    @staticmethod
    def _connector_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["granted_scopes"] = json.loads(data.pop("granted_scopes_json"))
        data["settings"] = json.loads(data.pop("settings_json"))
        return data

    def configure_connector(
        self,
        identity: RequestIdentity,
        *,
        connector_type: str,
        provider: str,
        environment: str,
        status: str,
        credential_reference: str,
        granted_scopes: list[str],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        now = _now()
        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM connector_configs WHERE tenant_id = ? AND connector_type = ? AND environment = ?",
                (identity.tenant_id, connector_type, environment),
            ).fetchone()
            connector_id = existing["id"] if existing else f"con_{uuid4().hex[:12]}"
            self._conn.execute(
                """
                INSERT INTO connector_configs(
                    id, tenant_id, connector_type, provider, environment, status,
                    credential_reference, granted_scopes_json, settings_json,
                    last_health_status, last_error_status, last_health_check_at,
                    last_success_at, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?, ?)
                ON CONFLICT(tenant_id, connector_type, environment) DO UPDATE SET
                    provider = excluded.provider,
                    status = excluded.status,
                    credential_reference = excluded.credential_reference,
                    granted_scopes_json = excluded.granted_scopes_json,
                    settings_json = excluded.settings_json,
                    updated_at = excluded.updated_at
                """,
                (
                    connector_id,
                    identity.tenant_id,
                    connector_type,
                    provider,
                    environment,
                    status,
                    credential_reference,
                    _json_value(sorted(set(granted_scopes))),
                    _json_value(redact_data(settings)),
                    identity.user_id,
                    now,
                    now,
                ),
            )
            self._audit(
                identity,
                "connector.configure",
                "connector",
                connector_id,
                "success",
                {
                    "connector_type": connector_type,
                    "provider": provider,
                    "environment": environment,
                    "status": status,
                    "granted_scopes": sorted(set(granted_scopes)),
                },
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM connector_configs WHERE id = ?", (connector_id,)
            ).fetchone()
        return self._connector_dict(row)

    def list_connectors(self, identity: RequestIdentity) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM connector_configs WHERE tenant_id = ? ORDER BY connector_type, environment",
                (identity.tenant_id,),
            ).fetchall()
        return [self._connector_dict(row) for row in rows]

    def get_connector(self, identity: RequestIdentity, connector_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM connector_configs WHERE id = ? AND tenant_id = ?",
                (connector_id, identity.tenant_id),
            ).fetchone()
        if row is None:
            raise KeyError(connector_id)
        return self._connector_dict(row)

    def get_enabled_connector(
        self, identity: RequestIdentity, connector_type: str
    ) -> dict[str, Any] | None:
        target_environment = os.getenv(
            "CONNECTOR_ENV", "production" if os.getenv("APP_ENV") == "production" else "sandbox"
        )
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM connector_configs
                WHERE tenant_id = ? AND connector_type = ? AND environment = ? AND status = 'enabled'
                LIMIT 1
                """,
                (identity.tenant_id, connector_type, target_environment),
            ).fetchone()
        return self._connector_dict(row) if row else None

    def record_connector_health(
        self,
        identity: RequestIdentity,
        connector_id: str,
        *,
        status: str,
        error_status: str | None,
    ) -> None:
        now = _now()
        with self._lock:
            cursor = self._conn.execute(
                """
                UPDATE connector_configs
                SET last_health_status = ?, last_error_status = ?,
                    last_health_check_at = ?,
                    last_success_at = CASE WHEN ? = 'healthy' THEN ? ELSE last_success_at END,
                    updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (status, error_status, now, status, now, now, connector_id, identity.tenant_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(connector_id)
            self._audit(
                identity,
                "connector.health_check",
                "connector",
                connector_id,
                status,
                {"error_status": error_status},
            )
            self._conn.commit()

    def create_action_draft(
        self,
        identity: RequestIdentity,
        *,
        thread_id: str | None,
        action_type: str,
        parameters: dict[str, Any],
        connector_id: str | None = None,
        idempotency_key: str | None = None,
        expires_in_hours: int = 24,
    ) -> dict[str, Any]:
        digest = payload_hash(parameters)
        effective_key = idempotency_key or payload_hash(
            {
                "tenant_id": identity.tenant_id,
                "user_id": identity.user_id,
                "thread_id": thread_id,
                "action_type": action_type,
                "payload_hash": digest,
            }
        )
        now = _now()
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=max(1, min(expires_in_hours, 168)))).isoformat()
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM action_drafts WHERE tenant_id = ? AND idempotency_key = ?",
                (identity.tenant_id, effective_key),
            ).fetchone()
            if existing is not None:
                return self._action_draft_dict(existing)
            draft_id = f"drf_{uuid4().hex[:12]}"
            cursor = self._conn.execute(
                """
                INSERT INTO action_drafts(
                    id, tenant_id, user_id, thread_id, connector_id, action_type,
                    status, payload_encrypted, payload_summary_json, payload_hash,
                    idempotency_key, requested_by, reviewed_by, reviewed_at,
                    expires_at, external_record_id, manually_completed_by,
                    manually_completed_at, result_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, NULL, NULL,
                          ?, NULL, NULL, NULL, NULL, ?, ?)
                ON CONFLICT(tenant_id, idempotency_key) DO NOTHING
                """,
                (
                    draft_id,
                    identity.tenant_id,
                    identity.user_id,
                    thread_id,
                    connector_id,
                    action_type,
                    self._cipher.encrypt_json(parameters),
                    _json_value(redact_data(parameters, mask_personal_data=True)),
                    digest,
                    effective_key,
                    identity.user_id,
                    expires_at,
                    now,
                    now,
                ),
            )
            if cursor.rowcount:
                self._audit(
                    identity,
                    "action_draft.create",
                    "action_draft",
                    draft_id,
                    "success",
                    {"action_type": action_type, "mode": "draft_only", "payload_hash": digest},
                )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM action_drafts WHERE tenant_id = ? AND idempotency_key = ?",
                (identity.tenant_id, effective_key),
            ).fetchone()
        return self._action_draft_dict(row)

    def _action_draft_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["parameters"] = self._cipher.decrypt_json(data.pop("payload_encrypted"))
        data["payload_summary"] = json.loads(data.pop("payload_summary_json"))
        data["result"] = json.loads(data.pop("result_json")) if data["result_json"] else None
        data["action"] = data["action_type"]
        data["approval_id"] = data["id"]
        return data

    def list_action_drafts(self, identity: RequestIdentity) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM action_drafts WHERE tenant_id = ? ORDER BY updated_at DESC",
                (identity.tenant_id,),
            ).fetchall()
        return [self._action_draft_dict(row) for row in rows]

    def _action_draft_row(self, identity: RequestIdentity, draft_id: str) -> sqlite3.Row:
        row = self._conn.execute(
            "SELECT * FROM action_drafts WHERE id = ? AND tenant_id = ?",
            (draft_id, identity.tenant_id),
        ).fetchone()
        if row is None:
            raise KeyError(draft_id)
        if row["user_id"] != identity.user_id and not identity.has_any_role(
            "tenant_admin", "support_agent"
        ):
            raise KeyError(draft_id)
        return row

    def submit_action_draft(
        self, identity: RequestIdentity, draft_id: str
    ) -> dict[str, Any]:
        with self._lock:
            row = self._action_draft_row(identity, draft_id)
            if row["status"] != "draft":
                return self._action_draft_dict(row)
            if row["expires_at"] and row["expires_at"] <= _now():
                self._conn.execute(
                    "UPDATE action_drafts SET status = 'expired', updated_at = ? WHERE id = ?",
                    (_now(), draft_id),
                )
            else:
                self._conn.execute(
                    "UPDATE action_drafts SET status = 'pending_review', updated_at = ? WHERE id = ?",
                    (_now(), draft_id),
                )
            self._audit(
                identity,
                "action_draft.submit",
                "action_draft",
                draft_id,
                "success",
                {"payload_hash": row["payload_hash"]},
            )
            self._conn.commit()
            updated = self._conn.execute(
                "SELECT * FROM action_drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        return self._action_draft_dict(updated)

    def decide_action_draft(
        self, identity: RequestIdentity, draft_id: str, decision: str
    ) -> dict[str, Any]:
        if not identity.has_any_role("tenant_admin", "support_agent"):
            raise PermissionError("Only an authorized operator can review action drafts")
        with self._lock:
            row = self._action_draft_row(identity, draft_id)
            if row["status"] != "pending_review":
                if row["status"] in {"approved_for_manual_execution", "rejected"}:
                    return self._action_draft_dict(row)
                raise ValueError("Action draft must be pending review")
            status = "approved_for_manual_execution" if decision == "approved" else "rejected"
            result = {
                "executed": False,
                "mode": "draft_only",
                "manual_execution_required": decision == "approved",
            }
            now = _now()
            self._conn.execute(
                """
                UPDATE action_drafts
                SET status = ?, reviewed_by = ?, reviewed_at = ?, result_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, identity.user_id, now, _json_value(result), now, draft_id),
            )
            self._audit(
                identity,
                f"action_draft.{status}",
                "action_draft",
                draft_id,
                "success",
                {"action_type": row["action_type"], "mode": "draft_only"},
            )
            self._conn.commit()
            updated = self._conn.execute(
                "SELECT * FROM action_drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        return self._action_draft_dict(updated)

    def complete_action_draft(
        self,
        identity: RequestIdentity,
        draft_id: str,
        *,
        external_record_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        if not identity.has_any_role("tenant_admin", "support_agent"):
            raise PermissionError("Only an authorized operator can complete action drafts")
        with self._lock:
            row = self._action_draft_row(identity, draft_id)
            if row["status"] != "approved_for_manual_execution":
                raise ValueError("Action draft is not ready for manual completion")
            now = _now()
            result = {
                "executed": False,
                "mode": "manual_external_execution",
                "manual_execution_recorded": True,
                "note": redact_data(note, mask_personal_data=True) if note else None,
            }
            self._conn.execute(
                """
                UPDATE action_drafts
                SET status = 'manually_completed', external_record_id = ?,
                    manually_completed_by = ?, manually_completed_at = ?,
                    result_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (external_record_id, identity.user_id, now, _json_value(result), now, draft_id),
            )
            if row["thread_id"]:
                state_row = self._conn.execute(
                    "SELECT data_json FROM conversation_states WHERE thread_id = ? AND tenant_id = ?",
                    (row["thread_id"], identity.tenant_id),
                ).fetchone()
                if state_row:
                    state = json.loads(state_row["data_json"])
                    business_context = state.setdefault("context", {})
                    business_context["human_approval_required"] = False
                    if row["action_type"] == "create_support_ticket":
                        business_context["ticket_id"] = external_record_id
                        business_context["ticket_status"] = "Manually created"
                    elif row["action_type"] == "create_sales_opportunity":
                        business_context["opportunity_id"] = external_record_id
                    elif row["action_type"] == "open_billing_case":
                        business_context["billing_case_id"] = external_record_id
                    self._conn.execute(
                        "UPDATE conversation_states SET data_json = ?, updated_at = ? WHERE thread_id = ?",
                        (_json_value(state), now, row["thread_id"]),
                    )
            self._audit(
                identity,
                "action_draft.manually_completed",
                "action_draft",
                draft_id,
                "success",
                {"external_record_id": external_record_id, "mode": "manual_external_execution"},
            )
            self._conn.commit()
            updated = self._conn.execute(
                "SELECT * FROM action_drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        return self._action_draft_dict(updated)

    def create_approval(
        self,
        identity: RequestIdentity,
        *,
        thread_id: str | None,
        action: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        return self.create_action_draft(
            identity,
            thread_id=thread_id,
            action_type=action,
            parameters=parameters,
        )

    def list_approvals(self, identity: RequestIdentity) -> list[dict[str, Any]]:
        return self.list_action_drafts(identity)

    def decide_approval(
        self, identity: RequestIdentity, approval_id: str, decision: str
    ) -> dict[str, Any]:
        return self.decide_action_draft(identity, approval_id, decision)

    def create_escalation(
        self,
        identity: RequestIdentity,
        *,
        thread_id: str | None,
        reason: str,
        priority: str,
    ) -> dict[str, Any]:
        escalation_id = f"esc_{uuid4().hex[:12]}"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO human_escalations(
                    id, tenant_id, user_id, thread_id, reason, priority, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    escalation_id,
                    identity.tenant_id,
                    identity.user_id,
                    thread_id,
                    reason,
                    priority,
                    _now(),
                ),
            )
            self._audit(
                identity,
                "escalation.create",
                "human_escalation",
                escalation_id,
                "success",
                {"priority": priority},
            )
            self._conn.commit()
        return {
            "escalation_id": escalation_id,
            "priority": priority,
            "status": "open",
        }

    @staticmethod
    def _default_branding() -> dict[str, Any]:
        return {
            "display_name": os.getenv(
                "DEFAULT_TENANT_DISPLAY_NAME", "Acme Intelligence"
            ),
            "assistant_name": os.getenv(
                "DEFAULT_ASSISTANT_NAME", "Acme AI 服务助手"
            ),
            "logo_url": None,
            "primary_color": "#0f766e",
            "welcome_message": "您好，请问今天需要产品、技术、方案还是账户支持？",
            "support_notice": "回答基于企业已审核资料；重要业务信息请以正式合同和服务通知为准。",
            "suggested_prompts": DEFAULT_SUGGESTED_PROMPTS,
            "updated_by": "system",
            "updated_at": None,
            "published_at": None,
        }

    @staticmethod
    def _branding_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["suggested_prompts"] = json.loads(
            data.pop("suggested_prompts_json")
        )
        data.pop("tenant_id", None)
        return data

    def get_tenant_branding(self, identity: RequestIdentity) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tenant_branding WHERE tenant_id = ?",
                (identity.tenant_id,),
            ).fetchone()
        return self._branding_dict(row) if row else self._default_branding()

    def update_tenant_branding(
        self,
        identity: RequestIdentity,
        **changes: Any,
    ) -> dict[str, Any]:
        current = self.get_tenant_branding(identity)
        current.update(changes)
        now = _now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO tenant_branding(
                    tenant_id, display_name, assistant_name, logo_url,
                    primary_color, welcome_message, support_notice,
                    suggested_prompts_json, updated_by, updated_at, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    assistant_name = excluded.assistant_name,
                    logo_url = excluded.logo_url,
                    primary_color = excluded.primary_color,
                    welcome_message = excluded.welcome_message,
                    support_notice = excluded.support_notice,
                    suggested_prompts_json = excluded.suggested_prompts_json,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at,
                    published_at = excluded.published_at
                """,
                (
                    identity.tenant_id,
                    current["display_name"],
                    current["assistant_name"],
                    current.get("logo_url"),
                    current["primary_color"],
                    current["welcome_message"],
                    current["support_notice"],
                    _json_value(current["suggested_prompts"]),
                    identity.user_id,
                    now,
                    now,
                ),
            )
            self._audit(
                identity,
                "tenant.branding.update",
                "tenant_branding",
                identity.tenant_id,
                "success",
                {"fields": sorted(changes)},
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM tenant_branding WHERE tenant_id = ?",
                (identity.tenant_id,),
            ).fetchone()
        return self._branding_dict(row)

    def _audit(
        self,
        identity: RequestIdentity,
        action: str,
        resource_type: str,
        resource_id: str | None,
        result: str,
        metadata: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO audit_logs(
                id, tenant_id, actor_user_id, action, resource_type,
                resource_id, result, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"aud_{uuid4().hex[:12]}",
                identity.tenant_id,
                identity.user_id,
                action,
                resource_type,
                resource_id,
                result,
                _json_value(redact_data(metadata, mask_personal_data=True)),
                _now(),
            ),
        )

    def record_trace(
        self,
        identity: RequestIdentity,
        *,
        request_id: str,
        thread_id: str | None,
        model: str | None,
        agent_name: str | None,
        status: str,
        duration_ms: float | None,
        event_summary: dict[str, Any],
    ) -> dict[str, Any]:
        trace_id = f"trc_{uuid4().hex[:12]}"
        now = _now()
        safe_summary = redact_data(event_summary, mask_personal_data=True)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO trace_runs(
                    id, tenant_id, user_id, thread_id, request_id, model,
                    agent_name, status, duration_ms, event_summary_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    identity.tenant_id,
                    identity.user_id,
                    thread_id,
                    request_id,
                    model,
                    agent_name,
                    status,
                    duration_ms,
                    _json_value(safe_summary),
                    now,
                ),
            )
            self._conn.commit()
        return {
            "id": trace_id,
            "request_id": request_id,
            "thread_id": thread_id,
            "model": model,
            "agent_name": agent_name,
            "status": status,
            "duration_ms": duration_ms,
            "event_summary": safe_summary,
            "created_at": now,
        }

    def list_traces(
        self, identity: RequestIdentity, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM trace_runs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
                (identity.tenant_id, max(1, min(limit, 500))),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["event_summary"] = json.loads(item.pop("event_summary_json"))
            item.pop("tenant_id", None)
            result.append(item)
        return result

    @staticmethod
    def _member_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["roles"] = json.loads(data.pop("roles_json"))
        return data

    def authorize_identity(self, identity: RequestIdentity) -> RequestIdentity:
        """Provision OIDC users and enforce administrator-managed suspension/role overrides."""

        now = _now()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tenant_members WHERE tenant_id = ? AND user_id = ?",
                (identity.tenant_id, identity.user_id),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    """
                    INSERT INTO tenant_members(
                        tenant_id, user_id, status, roles_json, source,
                        last_login_at, created_at, updated_at
                    ) VALUES (?, ?, 'active', ?, 'oidc', ?, ?, ?)
                    """,
                    (
                        identity.tenant_id,
                        identity.user_id,
                        _json_value(sorted(identity.roles)),
                        now,
                        now,
                        now,
                    ),
                )
                self._conn.commit()
                return identity
            if row["status"] != "active":
                raise PermissionError("Member account is disabled")
            roles = frozenset(json.loads(row["roles_json"])) if row["source"] == "manual" else identity.roles
            self._conn.execute(
                """
                UPDATE tenant_members
                SET roles_json = ?, last_login_at = ?, updated_at = ?
                WHERE tenant_id = ? AND user_id = ?
                """,
                (
                    _json_value(sorted(roles)),
                    now,
                    now,
                    identity.tenant_id,
                    identity.user_id,
                ),
            )
            self._conn.commit()
        return identity.model_copy(update={"roles": roles})

    def list_members(self, identity: RequestIdentity) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM tenant_members WHERE tenant_id = ? ORDER BY updated_at DESC",
                (identity.tenant_id,),
            ).fetchall()
        return [self._member_dict(row) for row in rows]

    def update_member(
        self,
        identity: RequestIdentity,
        user_id: str,
        *,
        status: str,
        roles: list[str],
    ) -> dict[str, Any]:
        if user_id == identity.user_id and status != "active":
            raise ValueError("Administrators cannot disable their own current session")
        now = _now()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tenant_members WHERE tenant_id = ? AND user_id = ?",
                (identity.tenant_id, user_id),
            ).fetchone()
            if row is None:
                raise KeyError(user_id)
            self._conn.execute(
                """
                UPDATE tenant_members
                SET status = ?, roles_json = ?, source = 'manual', updated_at = ?
                WHERE tenant_id = ? AND user_id = ?
                """,
                (status, _json_value(sorted(set(roles))), now, identity.tenant_id, user_id),
            )
            self._audit(
                identity,
                "tenant.member.update",
                "tenant_member",
                user_id,
                "success",
                {"status": status, "roles": sorted(set(roles))},
            )
            self._conn.commit()
            updated = self._conn.execute(
                "SELECT * FROM tenant_members WHERE tenant_id = ? AND user_id = ?",
                (identity.tenant_id, user_id),
            ).fetchone()
        return self._member_dict(updated)

    def list_audit_logs(
        self, identity: RequestIdentity, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM audit_logs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
                (identity.tenant_id, limit),
            ).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["metadata"] = json.loads(data.pop("metadata_json"))
            result.append(data)
        return result
