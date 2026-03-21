from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from config import Config
from machines import MachineRegistry
from sessions import SessionManager
from twilio_config import TwilioConfigurator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger(__name__)

config = Config()
registry = MachineRegistry()
session_mgr = SessionManager()
twilio = TwilioConfigurator(
    config.twilio_account_sid,
    config.twilio_auth_token,
    config.twilio_phone_number,
)

app = FastAPI(title="Claude Assistant Backend")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# REST — Machines
# ---------------------------------------------------------------------------
@app.get("/api/machines")
async def list_machines():
    return registry.list_online()


# ---------------------------------------------------------------------------
# REST — Sessions
# ---------------------------------------------------------------------------
@app.get("/api/sessions")
async def get_session():
    return session_mgr.to_dict()


@app.post("/api/sessions")
async def start_session(request: Request):
    body = await request.json()
    machine_name = body.get("machine")
    if not machine_name:
        raise HTTPException(400, "machine is required")

    if session_mgr.active is not None:
        raise HTTPException(409, "A session is already active")

    machine = registry.get(machine_name)
    if machine is None:
        raise HTTPException(404, f"Machine '{machine_name}' is not online")

    session = session_mgr.start(machine_name)

    # Tell the daemon to start
    try:
        await machine.ws.send_json({
            "type": "start_session",
            "session_id": session.session_id,
        })
    except Exception as e:
        session_mgr.stop()
        raise HTTPException(502, f"Failed to reach daemon: {e}")

    await registry.broadcast_ui({
        "type": "session_starting",
        "machine": machine_name,
        "session_id": session.session_id,
    })

    return session_mgr.to_dict()


@app.delete("/api/sessions")
async def end_session():
    if session_mgr.active is None:
        raise HTTPException(404, "No active session")

    machine = registry.get(session_mgr.active.machine_name)
    if machine and machine.ws:
        try:
            await machine.ws.send_json({"type": "stop_session"})
        except Exception:
            pass

    session_mgr.stop()

    # Clear Twilio webhook
    fallback = _fallback_url()
    await twilio.clear_webhook(fallback)

    await registry.broadcast_ui({"type": "session_stopped"})
    return {"status": "stopped"}


# ---------------------------------------------------------------------------
# Twilio fallback
# ---------------------------------------------------------------------------
FALLBACK_TWIML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<Response>"
    "<Say>No assistant session is currently active. Please try again later.</Say>"
    "</Response>"
)


@app.post("/twilio/fallback")
async def twilio_fallback():
    return Response(content=FALLBACK_TWIML, media_type="application/xml")


def _fallback_url() -> str:
    return "https://assistant.sogos.io/twilio/fallback"


# ---------------------------------------------------------------------------
# WebSocket — Daemon connection
# ---------------------------------------------------------------------------
@app.websocket("/ws/daemon")
async def daemon_ws(ws: WebSocket):
    await ws.accept()
    machine_name: str | None = None

    try:
        # First message must be register
        raw = await asyncio.wait_for(ws.receive_json(), timeout=10)
        if raw.get("type") != "register":
            await ws.close(1008, "First message must be register")
            return

        machine_name = raw["machine"]
        machine = registry.register(machine_name, ws)
        log.info(f"Machine registered: {machine_name}")

        # Restore session state if daemon reports one
        existing = raw.get("active_session")
        if existing and session_mgr.active is None:
            session = session_mgr.start(machine_name)
            session.session_id = existing["session_id"]
            session.ngrok_url = existing.get("ngrok_url")
            session.status = "active"
            machine.active_session_id = session.session_id
            machine.active_ngrok_url = session.ngrok_url
            log.info(f"Restored session {session.session_id} from daemon")

        await registry.broadcast_ui({
            "type": "machine_online",
            "machine": machine_name,
        })

        # Message loop
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "heartbeat":
                import time
                machine.last_heartbeat = time.time()

            elif msg_type == "session_started":
                ngrok_url = data["ngrok_url"]
                session_mgr.activate(ngrok_url)
                machine.active_session_id = (
                    session_mgr.active.session_id if session_mgr.active else None
                )
                machine.active_ngrok_url = ngrok_url

                # Update Twilio webhook
                fallback = _fallback_url()
                await twilio.set_webhook(ngrok_url, fallback)

                await registry.broadcast_ui({
                    "type": "session_active",
                    "machine": machine_name,
                    "session_id": session_mgr.active.session_id if session_mgr.active else None,
                    "ngrok_url": ngrok_url,
                })
                log.info(f"Session active on {machine_name} via {ngrok_url}")

            elif msg_type == "session_stopped":
                session_mgr.stop()
                machine.active_session_id = None
                machine.active_ngrok_url = None
                fallback = _fallback_url()
                await twilio.clear_webhook(fallback)
                await registry.broadcast_ui({"type": "session_stopped"})
                log.info(f"Session stopped on {machine_name}")

            elif msg_type == "session_error":
                error = data.get("error", "unknown")
                session_mgr.stop()
                machine.active_session_id = None
                machine.active_ngrok_url = None
                await registry.broadcast_ui({
                    "type": "session_error",
                    "error": error,
                })
                log.error(f"Session error on {machine_name}: {error}")

    except WebSocketDisconnect:
        log.info(f"Machine disconnected: {machine_name}")
    except Exception as e:
        log.error(f"Daemon WS error: {e}")
    finally:
        if machine_name:
            registry.unregister(machine_name)
            await registry.broadcast_ui({
                "type": "machine_offline",
                "machine": machine_name,
            })


# ---------------------------------------------------------------------------
# WebSocket — UI updates
# ---------------------------------------------------------------------------
@app.websocket("/ws/ui")
async def ui_ws(ws: WebSocket):
    await ws.accept()
    registry.add_ui_client(ws)
    try:
        # Send initial state
        await ws.send_json({
            "type": "initial_state",
            "machines": registry.list_online(),
            "session": session_mgr.to_dict(),
        })
        # Keep alive — just wait for disconnect
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        registry.remove_ui_client(ws)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port)
