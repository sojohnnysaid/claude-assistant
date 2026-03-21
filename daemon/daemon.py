#!/usr/bin/env python3
"""Claude Assistant Daemon — connects to backend, manages voice agent sessions."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys

import websockets
from websockets.exceptions import ConnectionClosed

from config import DaemonConfig
from session_manager import SessionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [daemon] %(message)s",
)
log = logging.getLogger(__name__)

config = DaemonConfig()
session_mgr = SessionManager(config)


async def run_daemon() -> None:
    backoff = config.reconnect_base

    while True:
        try:
            await _connect()
            backoff = config.reconnect_base  # reset on clean disconnect
        except Exception as e:
            log.warning(f"Connection error: {e}")

        log.info(f"Reconnecting in {backoff:.0f}s...")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, config.reconnect_max)


async def _connect() -> None:
    url = f"{config.backend_ws_url}?machine={config.machine_name}"
    log.info(f"Connecting to {url}")

    async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
        log.info(f"Connected as '{config.machine_name}'")

        # Register with current state
        active_session = None
        if session_mgr.is_active:
            active_session = {
                "session_id": session_mgr.session_id,
                "ngrok_url": session_mgr.ngrok_url,
            }

        await ws.send(json.dumps({
            "type": "register",
            "machine": config.machine_name,
            "active_session": active_session,
        }))

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(_heartbeat(ws))

        try:
            async for raw in ws:
                data = json.loads(raw)
                await _handle_message(data, ws)
        finally:
            heartbeat_task.cancel()


async def _heartbeat(ws: websockets.WebSocketClientProtocol) -> None:
    while True:
        await asyncio.sleep(config.heartbeat_interval)
        try:
            await ws.send(json.dumps({"type": "heartbeat"}))
        except ConnectionClosed:
            return


async def _handle_message(
    data: dict, ws: websockets.WebSocketClientProtocol
) -> None:
    msg_type = data.get("type")

    if msg_type == "start_session":
        session_id = data["session_id"]
        log.info(f"Received start_session: {session_id}")
        try:
            ngrok_url = await session_mgr.start(session_id)
            await ws.send(json.dumps({
                "type": "session_started",
                "ngrok_url": ngrok_url,
            }))
        except Exception as e:
            log.error(f"Failed to start session: {e}")
            await ws.send(json.dumps({
                "type": "session_error",
                "error": str(e),
            }))

    elif msg_type == "stop_session":
        log.info("Received stop_session")
        await session_mgr.stop()
        await ws.send(json.dumps({"type": "session_stopped"}))

    elif msg_type == "ping":
        pass

    else:
        log.warning(f"Unknown message type: {msg_type}")


async def main() -> None:
    loop = asyncio.get_event_loop()

    async def shutdown():
        log.info("Shutting down...")
        await session_mgr.stop()
        sys.exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    await run_daemon()


if __name__ == "__main__":
    asyncio.run(main())
