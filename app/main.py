"""FastAPI server for Kotak Prime realtime voice agent."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent.graph import run_tool
from app.call_context import set_session_token
from app.config import get_settings
from app.services.auth import authenticate
from app.services.call_session import (
    begin_voice_call,
    end_session,
    get_session,
    reset_call_state,
    session_customer_context,
)
from app.services.tickets import log_support_ticket
from app.session_config import AGENT_NAME, build_session_config
from app.tools.kotak_tools import TOOL_BY_NAME, realtime_tool_schemas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kotak-prime-voice")

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"

app = FastAPI(
    title="Kotak Mahindra Prime Loans Voice Agent",
    description="Realtime speech-to-speech agent using gpt-realtime-2.1-mini + LangGraph tools",
    version="2.0.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ToolExecuteRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    session_token: str = ""


class LoginRequest(BaseModel):
    login: str
    password: str


class CallEndRequest(BaseModel):
    session_token: str
    transcript: list[dict[str, str]] = Field(default_factory=list)
    resolved: bool = False


def _token_from_request(request: Request, body_token: str = "") -> str | None:
    header = request.headers.get("X-Session-Token") or request.headers.get("x-session-token")
    return (body_token or header or "").strip() or None


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "model": settings.openai_realtime_model,
        "tools": str(len(TOOL_BY_NAME)),
        "agent_name": AGENT_NAME,
    }


@app.post("/api/login")
async def login(body: LoginRequest) -> JSONResponse:
    result = authenticate(body.login.strip(), body.password)
    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("error", "Login failed"))
    return JSONResponse(result)


@app.post("/api/logout")
async def logout(request: Request) -> JSONResponse:
    token = _token_from_request(request)
    if token:
        end_session(token)
    return JSONResponse({"ok": True})


@app.post("/api/call/end")
async def call_end(body: CallEndRequest) -> JSONResponse:
    session = get_session(body.session_token)
    if not session:
        return JSONResponse({"ok": True, "ticket_id": None, "message": "No active session"})

    for entry in body.transcript:
        session.add_transcript(entry.get("role", "unknown"), entry.get("text", ""))

    ticket_id = log_support_ticket(session, resolved=body.resolved)
    logger.info("Support ticket %s for customer %s", ticket_id, session.customer_id)
    reset_call_state(session)
    return JSONResponse({"ok": True, "ticket_id": ticket_id})


@app.get("/api/tools")
async def list_tools() -> JSONResponse:
    return JSONResponse({"tools": realtime_tool_schemas()})


@app.post("/api/tools/execute")
async def execute_tool(body: ToolExecuteRequest, request: Request) -> JSONResponse:
    token = _token_from_request(request, body.session_token)
    if not token or not get_session(token):
        raise HTTPException(status_code=401, detail="Valid session required")

    if body.name not in TOOL_BY_NAME:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {body.name}")

    set_session_token(token)
    try:
        logger.info("LangGraph tool call: %s args=%s", body.name, body.arguments)
        result = run_tool(body.name, body.arguments)
    finally:
        set_session_token(None)

    return JSONResponse({"name": body.name, "output": result})


@app.post("/session")
async def create_realtime_session(request: Request):
    """Browser POSTs SDP offer; we forward to OpenAI with logged-in customer context."""
    settings = get_settings()
    token = _token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Login required")

    customer_ctx = session_customer_context(token)
    if not customer_ctx or not get_session(token):
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    sdp_offer = (await request.body()).decode("utf-8")
    if not sdp_offer.strip():
        raise HTTPException(status_code=400, detail="Empty SDP offer")

    session_config = json.dumps(build_session_config(customer_ctx))
    form = {
        "sdp": (None, sdp_offer, "application/sdp"),
        "session": (None, session_config, "application/json"),
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/realtime/calls",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "OpenAI-Safety-Identifier": "kotak-prime-voice-demo",
                },
                files=form,
            )
    except httpx.HTTPError as exc:
        logger.exception("Failed to create realtime call")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if response.status_code >= 400:
        logger.error("OpenAI session error %s: %s", response.status_code, response.text)
        detail = response.text
        try:
            err = json.loads(response.text).get("error", {})
            if isinstance(err, dict) and err.get("message"):
                detail = err["message"]
        except json.JSONDecodeError:
            pass
        raise HTTPException(status_code=502, detail=f"OpenAI realtime error: {detail}")

    call_id = response.headers.get("Location") or response.headers.get("location")
    begin_voice_call(token)
    logger.info("Realtime call created for %s location=%s", customer_ctx.get("customer_id"), call_id)

    return Response(
        content=response.text,
        media_type="application/sdp",
        headers={"X-Realtime-Call-Id": call_id or ""},
    )


@app.post("/token")
async def create_ephemeral_token(request: Request) -> JSONResponse:
    settings = get_settings()
    token = _token_from_request(request)
    customer_ctx = session_customer_context(token) if token else None
    payload = {"session": build_session_config(customer_ctx)}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/realtime/client_secrets",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
                "OpenAI-Safety-Identifier": "kotak-prime-voice-demo",
            },
            json=payload,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return JSONResponse(response.json())


@app.websocket("/ws/events")
async def events_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "ready",
            "message": "Event socket connected.",
            "model": get_settings().openai_realtime_model,
        }
    )
    try:
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "tool_log":
                logger.info("Client tool log: %s", data)
                await websocket.send_json({"type": "tool_log_ack", "ok": True})
            elif msg_type == "client_status":
                await websocket.send_json({"type": "status_ack", "status": data.get("status")})
            else:
                await websocket.send_json(
                    {"type": "info", "message": f"Unhandled event type: {msg_type}"}
                )
    except WebSocketDisconnect:
        logger.info("Event socket disconnected")


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
