from __future__ import annotations as _annotations

import json
import os
import time
from typing import Annotated, Any, Dict, Literal
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OPENAI_TRACING_DISABLED", "1")

from chatkit.server import StreamingResult
from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from enterprise_support.agents import (
    account_billing_agent,
    product_knowledge_agent,
    security_compliance_agent,
    solution_architect_agent,
    technical_support_agent,
    triage_agent,
)
from enterprise_support.auth_api import router as auth_router
from enterprise_support.context import (
    EnterpriseAgentChatContext,
    EnterpriseAgentContext,
    create_initial_context,
    public_context,
)
from enterprise_support.connectors import ConnectorGateway
from enterprise_support.model_provider import ZAI_SETTINGS
from enterprise_support.observability import METRICS
from enterprise_support.object_storage import build_object_storage
from enterprise_support.production import assert_production_ready, production_readiness_checks
from enterprise_support.identity import (
    RequestIdentity,
    as_portal_identity,
    get_request_identity,
    require_roles,
)
from enterprise_support.platform_api import router as platform_router
from persistent_store import PersistentStore
from server import EnterpriseSupportServer

app = FastAPI(title="Enterprise AI Support Agent", version="1.0.0")
assert_production_ready()

# CORS configuration (adjust as needed for deployment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = PersistentStore()
connector_gateway = ConnectorGateway(store)
store.connector_gateway = connector_gateway
object_storage = build_object_storage()
chat_server = EnterpriseSupportServer(store=store)
app.state.store = store
app.state.connector_gateway = connector_gateway
app.state.object_storage = object_storage
app.include_router(platform_router)
app.include_router(auth_router)


@app.middleware("http")
async def observe_http_request(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or f"req_{uuid4().hex[:16]}"
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        METRICS.increment(
            "enterprise_agent_http_requests_total",
            method=request.method,
            path=request.url.path,
            status="500",
        )
        raise
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    METRICS.increment(
        "enterprise_agent_http_requests_total",
        method=request.method,
        path=path,
        status=str(response.status_code),
    )
    METRICS.observe(
        "enterprise_agent_http_request_duration_seconds",
        time.perf_counter() - started,
        method=request.method,
        path=path,
    )
    response.headers["X-Request-ID"] = request_id
    return response

AgentOperator = Annotated[
    RequestIdentity,
    Depends(require_roles("tenant_admin", "support_agent")),
]


class RoboAgeChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)

    @field_validator("content", mode="before")
    @classmethod
    def trim_content(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class RoboAgeChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    history: list[RoboAgeChatMessage] = Field(default_factory=list, max_length=24)
    thread_id: str | None = Field(default=None, max_length=200)
    surface: str = Field(default="roboage_workspace", max_length=80)

    @field_validator("message", mode="before")
    @classmethod
    def trim_message(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


def get_server() -> EnterpriseSupportServer:
    return chat_server


@app.post("/chatkit")
async def chatkit_endpoint(
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_request_identity)],
    server: EnterpriseSupportServer = Depends(get_server),
) -> Response:
    if not ZAI_SETTINGS.configured:
        return JSONResponse(
            status_code=503,
            content={
                "error": "model_provider_not_configured",
                "message": "Set ZAI_API_KEY in python-backend/.env and restart the server.",
            },
        )
    payload = await request.body()
    is_admin_surface = (
        request.headers.get("x-client-surface") == "admin"
        and identity.has_any_role("tenant_admin", "support_agent")
    )
    runtime_identity = identity if is_admin_surface else as_portal_identity(identity)
    result = await server.process(
        payload,
        {
            "request": request,
            "identity": runtime_identity,
            "client_surface": "admin" if is_admin_surface else "portal",
            "include_runner_events": is_admin_surface,
            "request_id": request.state.request_id,
        },
    )
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if hasattr(result, "json"):
        return Response(content=result.json, media_type="application/json")
    return Response(content=result)


@app.post("/v1/roboage/chat")
async def roboage_chat_endpoint(
    payload: RoboAgeChatRequest,
    request: Request,
    identity: AgentOperator,
    server: EnterpriseSupportServer = Depends(get_server),
) -> Dict[str, Any]:
    if not ZAI_SETTINGS.configured:
        return JSONResponse(
            status_code=503,
            content={
                "error": "model_provider_not_configured",
                "message": "Set ZAI_API_KEY in python-backend/.env and restart the server.",
            },
        )

    result = await server.respond_json(
        message=payload.message,
        thread_id=payload.thread_id,
        history=[item.model_dump() for item in payload.history],
        context={
            "request": request,
            "identity": identity,
            "client_surface": payload.surface,
            "include_runner_events": False,
            "request_id": request.state.request_id,
        },
    )
    return result


@app.get("/chatkit/state")
async def chatkit_state(
    thread_id: str = Query(...),
    identity: AgentOperator = None,
    server: EnterpriseSupportServer = Depends(get_server),
) -> Dict[str, Any]:
    return await server.snapshot(
        thread_id, {"request": None, "identity": identity}
    )


@app.get("/chatkit/bootstrap")
async def chatkit_bootstrap(
    identity: AgentOperator,
    server: EnterpriseSupportServer = Depends(get_server),
) -> Dict[str, Any]:
    request_context = {"request": None, "identity": identity}
    threads = await server.store.load_threads(
        limit=1,
        after=None,
        order="desc",
        context=request_context,
    )
    thread_id = threads.data[0].id if threads.data else None
    return await server.snapshot(thread_id, request_context)


@app.get("/chatkit/state/stream")
async def chatkit_state_stream(
    thread_id: str = Query(...),
    identity: AgentOperator = None,
    server: EnterpriseSupportServer = Depends(get_server),
):
    request_context = {"request": None, "identity": identity}
    thread = await server.ensure_thread(thread_id, request_context)
    queue = server.register_listener(thread.id)

    async def event_generator():
        try:
            initial = await server.snapshot(thread.id, request_context)
            yield f"data: {json.dumps(initial, default=str)}\n\n"
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        finally:
            server.unregister_listener(thread.id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy" if ZAI_SETTINGS.configured else "degraded",
        "service": "enterprise-ai-support-agent",
        "model_provider": "zhipu",
        "model": ZAI_SETTINGS.agent_model,
        "configured": ZAI_SETTINGS.configured,
    }


@app.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    checks = production_readiness_checks()
    return {
        "status": "ready" if all(check.passed for check in checks) else "not_ready",
        "checks": [check.__dict__ for check in checks],
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    return METRICS.render_prometheus()


__all__ = [
    "EnterpriseAgentChatContext",
    "EnterpriseAgentContext",
    "account_billing_agent",
    "app",
    "chat_server",
    "create_initial_context",
    "product_knowledge_agent",
    "public_context",
    "security_compliance_agent",
    "solution_architect_agent",
    "technical_support_agent",
    "triage_agent",
]
