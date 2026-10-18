"""RescueNet HQ — FastAPI backend."""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
import database
import models
import retell_service
import triage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
log = logging.getLogger("hq")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    log.info("HQ started — DB: %s", database._db_path())
    yield


app = FastAPI(title="RescueNet HQ", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Auth helper ───────────────────────────────────────────────────────────────

def _check_dispatcher(request: Request):
    """Optional dispatcher token check. Skipped when DISPATCHER_TOKEN is unset."""
    expected = os.environ.get("DISPATCHER_TOKEN", "") or getattr(config, "DISPATCHER_TOKEN", "")
    if not expected:
        return
    token = request.headers.get("X-Dispatcher-Token", "")
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid dispatcher token")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "ts": int(time.time())}


# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/config")
def get_config():
    demo = os.environ.get("DEMO_MODE", "").lower() == "true" or getattr(config, "DEMO_MODE", False)
    ai = bool(os.environ.get("ANTHROPIC_API_KEY") or getattr(config, "ANTHROPIC_API_KEY", ""))
    retell = bool(
        (os.environ.get("RETELL_API_KEY") or getattr(config, "RETELL_API_KEY", ""))
        and (os.environ.get("RETELL_AGENT_ID") or getattr(config, "RETELL_AGENT_ID", ""))
    )
    return {"demo_mode": demo, "ai_enabled": ai, "retell_enabled": retell}


# ── POST /api/v1/incidents ────────────────────────────────────────────────────

@app.post("/api/v1/incidents", status_code=201)
def create_incident(payload: models.IncidentCreate):
    existing = database.get_by_message_id(payload.message_id)
    if existing:
        log.info("Duplicate message_id %s — returning existing", payload.message_id[:8])
        return JSONResponse(status_code=200, content={"status": "duplicate", "incident": existing})

    inc_dict = payload.model_dump()
    sev, summary, translation = triage.triage(inc_dict)
    inc = database.insert_incident(inc_dict, sev, summary, translation)
    log.info("New incident %s sev=%s beacon=%s", payload.message_id[:8], sev, payload.beacon_id)

    return {
        "status": "created",
        "message_id": inc["message_id"],
        "severity": inc["severity"],
        "summary": inc["summary"],
    }


# ── GET /api/v1/incidents ─────────────────────────────────────────────────────

@app.get("/api/v1/incidents")
def list_incidents():
    return {"incidents": database.get_all()}


# ── GET /api/v1/updates ───────────────────────────────────────────────────────

@app.get("/api/v1/updates")
def get_updates(beacon_id: str):
    """Return status updates for all incidents from this beacon."""
    rows = database.get_by_beacon(beacon_id)
    updates = [
        {
            "message_id": r["message_id"],
            "severity": r["severity"],
            "summary": r["summary"],
            "assigned_team": r["assigned_team"],
            "eta": r["eta"],
            "rescue_status": r["rescue_status"],
            "dispatch_status": r["dispatch_status"],
        }
        for r in rows
    ]
    return {"updates": updates}


# ── GET /api/v1/areas ─────────────────────────────────────────────────────────

@app.get("/api/v1/areas")
def get_areas():
    """Aggregate incidents by beacon for map cluster view."""
    rows = database.get_all()
    by_beacon: dict = {}
    for r in rows:
        bid = r["beacon_id"]
        if bid not in by_beacon:
            by_beacon[bid] = {
                "beacon_id": bid,
                "lat": r["beacon_lat"],
                "lon": r["beacon_lon"],
                "total": 0,
                "people": 0,
                "critical": 0,
            }
        by_beacon[bid]["total"] += 1
        by_beacon[bid]["people"] += r["people"]
        if r["severity"] == "CRITICAL":
            by_beacon[bid]["critical"] += 1
    return {"areas": list(by_beacon.values())}


# ── POST /api/v1/incidents/{id}/ack ──────────────────────────────────────────

@app.post("/api/v1/incidents/{message_id}/ack")
def ack_incident(message_id: str, _=Depends(_check_dispatcher)):
    inc = _get_or_404(message_id)
    database.ack_incident(message_id)
    return {"status": "acknowledged"}


# ── POST /api/v1/incidents/{id}/assign ───────────────────────────────────────

@app.post("/api/v1/incidents/{message_id}/assign")
def assign_incident(message_id: str, body: models.AssignRequest, _=Depends(_check_dispatcher)):
    _get_or_404(message_id)
    database.assign_incident(message_id, body.team, body.eta)
    log.info("Assigned %s → team=%s eta=%s", message_id[:8], body.team, body.eta)
    return {"status": "assigned", "team": body.team, "eta": body.eta}


# ── POST /api/v1/incidents/{id}/close ────────────────────────────────────────

@app.post("/api/v1/incidents/{message_id}/close")
def close_incident(message_id: str, _=Depends(_check_dispatcher)):
    _get_or_404(message_id)
    database.close_incident(message_id)
    return {"status": "closed"}


# ── POST /api/v1/incidents/{id}/call ─────────────────────────────────────────

@app.post("/api/v1/incidents/{message_id}/call")
def initiate_call(message_id: str, body: models.CallRequest = models.CallRequest(), _=Depends(_check_dispatcher)):
    inc = _get_or_404(message_id)
    demo = os.environ.get("DEMO_MODE", "").lower() == "true" or getattr(config, "DEMO_MODE", False)
    if inc.get("call_initiated") and not demo:
        return {"status": "already_called", "call_id": inc.get("call_sid", "")}
    result = retell_service.initiate_call(inc, override_phone=body.phone)
    if result["success"]:
        database.set_call_initiated(message_id, result.get("call_id", ""))
    return result


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/")
def dashboard():
    return FileResponse(str(STATIC_DIR / "dashboard.html"))


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/v1/stats")
def stats():
    return database.get_stats()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(message_id: str) -> dict:
    inc = database.get_by_message_id(message_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HQ_HOST") or getattr(config, "HQ_HOST", "0.0.0.0")
    port = int(os.environ.get("HQ_PORT", "") or getattr(config, "HQ_PORT", 8000))
    uvicorn.run("main:app", host=host, port=port, reload=False)
