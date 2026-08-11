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
from app.config import get_settings
from app.session_config import AGENT_NAME, build_session_config
from app.tools.kotak_tools import TOOL_BY_NAME, realtime_tool_schemas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kotak-prime-voice")

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"

app = FastAPI(
    title="Kotak Mahindra Prime Loans Voice Agent",
    description="Realtime speech-to-speech agent using gpt-realtime-2.1-mini + LangGraph tools",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ToolExecuteRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


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


@app.get("/api/tools")
async def list_tools() -> JSONResponse:
    return JSONResponse({"tools": realtime_tool_schemas()})


@app.post("/api/tools/execute")
async def execute_tool(body: ToolExecuteRequest) -> JSONResponse:
    if body.name not in TOOL_BY_NAME:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {body.name}")
    logger.info("LangGraph tool call: %s args=%s", body.name, body.arguments)
    result = run_tool(body.name, body.arguments)
    return JSONResponse({"name": body.name, "output": result})


@app.post("/session")
async def create_realtime_session(request: Request):
    """
    Unified WebRTC session bootstrap.
    Browser POSTs SDP offer; we forward to OpenAI /v1/realtime/calls with session config.
    """
    settings = get_settings()
    sdp_offer = (await request.body()).decode("utf-8")
    if not sdp_offer.strip():
        raise HTTPException(status_code=400, detail="Empty SDP offer")

    session_config = json.dumps(build_session_config())
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
        raise HTTPException(status_code=response.status_code, detail=response.text)

    call_id = response.headers.get("Location") or response.headers.get("location")
    logger.info("Realtime call created location=%s", call_id)

    return Response(
        content=response.text,
        media_type="application/sdp",
        headers={"X-Realtime-Call-Id": call_id or ""},
    )


@app.post("/token")
async def create_ephemeral_token() -> JSONResponse:
    """Optional ephemeral client secret path (alternative to unified /session)."""
    settings = get_settings()
    payload = {"session": build_session_config()}
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
    """
    Lightweight status socket for the HTML UI (connection lifecycle / tool logs).
    Audio itself uses WebRTC for near-zero latency.
    """
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "ready",
            "message": "Event socket connected. Start the call from the UI.",
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
