"""FastAPI dashboard server."""
from __future__ import annotations
import os
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import state as _state

app = FastAPI(title="TradingAgents Dashboard")
_TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return _TEMPLATE.read_text()


@app.get("/api/status")
def api_status():
    return _state.get_state()


def start_in_background(host: str = "0.0.0.0", port: int = 8080) -> threading.Thread:
    _state.load_from_disk()

    def _run():
        uvicorn.run(app, host=host, port=port, log_level="warning")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
