"""FastAPI HTTP + WebSocket API for shaper control."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from .state import VoiceParameterStore
from .logger import DatasetLogger

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


class HarmonicUpdate(BaseModel if HAS_FASTAPI else object):
    gain: Optional[float] = None
    pan: Optional[float] = None
    phase_deg: Optional[float] = None


class SessionStart(BaseModel if HAS_FASTAPI else object):
    experiment_id: str = "manual"
    metadata: Optional[dict] = None


def create_app(store: VoiceParameterStore, dataset_logger: DatasetLogger) -> "FastAPI":
    if not HAS_FASTAPI:
        raise ImportError("fastapi and uvicorn are required. pip install fastapi uvicorn[standard]")

    app = FastAPI(title="Harmonic Shaper", version="0.1.0")

    # ─── WebSocket connection manager ─────────────────────────────────────────

    class _WsManager:
        def __init__(self):
            self._connections: set[WebSocket] = set()

        async def connect(self, ws: WebSocket):
            await ws.accept()
            self._connections.add(ws)

        def disconnect(self, ws: WebSocket):
            self._connections.discard(ws)

        async def broadcast(self, data: dict):
            dead = set()
            for ws in self._connections:
                try:
                    await ws.send_json(data)
                except Exception:
                    dead.add(ws)
            self._connections -= dead

    ws_mgr = _WsManager()

    # Wire store changes → WebSocket broadcast
    _loop: Optional[asyncio.AbstractEventLoop] = None

    def _on_change():
        if _loop and _loop.is_running():
            data = store.to_dict()
            asyncio.run_coroutine_threadsafe(ws_mgr.broadcast(data), _loop)

    store._on_change = _on_change

    @app.on_event("startup")
    async def _startup():
        nonlocal _loop
        _loop = asyncio.get_event_loop()

    # ─── REST endpoints ───────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def root():
        index = STATIC_DIR / "index.html"
        return HTMLResponse(index.read_text())

    @app.get("/api/state")
    async def get_state():
        return store.to_dict()

    @app.put("/api/harmonic/{n}")
    async def update_harmonic(n: int, body: HarmonicUpdate):
        kwargs = {k: v for k, v in body.dict().items() if v is not None}
        if not kwargs:
            raise HTTPException(status_code=400, detail="No params provided")
        store.set_params(n, **kwargs)
        return {"ok": True, "harmonic_n": n, **kwargs}

    @app.post("/api/panic")
    async def panic():
        store.panic()
        return {"ok": True, "action": "panic"}

    @app.get("/api/midi-page")
    async def get_midi_page():
        # Exposes MIDI control page for UI display — filled by main.py injection
        page = getattr(app.state, "midi_page", "gain")
        return {"page": page}

    # ─── Dataset endpoints ────────────────────────────────────────────────────

    @app.post("/api/session/start")
    async def start_session(body: SessionStart):
        sid = dataset_logger.start_session(
            experiment_id=body.experiment_id,
            metadata=body.metadata,
        )
        return {"ok": True, "session_id": sid}

    @app.post("/api/session/stop")
    async def stop_session():
        if not dataset_logger.is_running:
            return {"ok": False, "detail": "No active session"}
        dataset_logger.stop_session()
        return {"ok": True}

    @app.get("/api/session/status")
    async def session_status():
        return {
            "running": dataset_logger.is_running,
            "session_id": dataset_logger.session_id,
        }

    # ─── WebSocket ────────────────────────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws_mgr.connect(ws)
        # Send initial state immediately
        await ws.send_json(store.to_dict())
        try:
            while True:
                # Keep connection alive; client sends nothing (one-way push)
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_mgr.disconnect(ws)

    return app


def run_server(
    store: VoiceParameterStore,
    dataset_logger: DatasetLogger,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    app = create_app(store, dataset_logger)
    uvicorn.run(app, host=host, port=port, log_level="warning")
