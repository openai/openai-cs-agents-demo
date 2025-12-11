from __future__ import annotations as _annotations

import json
import os
from typing import Any, Dict

from chatkit.server import StreamingResult
from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from airline.agents import (
    booking_cancellation_agent,
    faq_agent,
    flight_information_agent,
    refunds_compensation_agent,
    seat_special_services_agent,
    triage_agent,
)
from airline.context import (
    AirlineAgentChatContext,
    AirlineAgentContext,
    create_initial_context,
    public_context,
)
from server import AirlineServer

app = FastAPI()

# Disable tracing for zero data retention orgs
os.environ.setdefault("OPENAI_TRACING_DISABLED", "1")

# CORS configuration (adjust as needed for deployment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_server = AirlineServer()


def get_server() -> AirlineServer:
    return chat_server


@app.post("/chatkit")
async def chatkit_endpoint(
    request: Request, server: AirlineServer = Depends(get_server)
) -> Response:
    payload = await request.body()
    result = await server.process(payload, {"request": request})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if hasattr(result, "json"):
        return Response(content=result.json, media_type="application/json")
    return Response(content=result)


@app.get("/chatkit/state")
async def chatkit_state(
    thread_id: str = Query(...),
    server: AirlineServer = Depends(get_server),
) -> Dict[str, Any]:
    return await server.snapshot(thread_id, {"request": None})


@app.get("/chatkit/bootstrap")
async def chatkit_bootstrap(
    server: AirlineServer = Depends(get_server),
) -> Dict[str, Any]:
    return await server.snapshot(None, {"request": None})


@app.get("/chatkit/state/stream")
async def chatkit_state_stream(
    thread_id: str = Query(...),
    server: AirlineServer = Depends(get_server),
):
    thread = await server.ensure_thread(thread_id, {"request": None})
    queue = server.register_listener(thread.id)

    async def event_generator():
        try:
            initial = await server.snapshot(thread.id, {"request": None})
            yield f"data: {json.dumps(initial, default=str)}\n\n"
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        finally:
            server.unregister_listener(thread.id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy"}


__all__ = [
    "AirlineAgentChatContext",
    "AirlineAgentContext",
    "app",
    "booking_cancellation_agent",
    "chat_server",
    "create_initial_context",
    "faq_agent",
    "flight_information_agent",
    "public_context",
    "refunds_compensation_agent",
    "seat_special_services_agent",
    "triage_agent",
]
