from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from fastapi import WebSocket


@dataclass
class MachineInfo:
    name: str
    ws: WebSocket
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    active_session_id: str | None = None
    active_ngrok_url: str | None = None


class MachineRegistry:
    def __init__(self) -> None:
        self._machines: dict[str, MachineInfo] = {}
        self._ui_clients: list[WebSocket] = []

    def register(self, name: str, ws: WebSocket) -> MachineInfo:
        machine = MachineInfo(name=name, ws=ws)
        self._machines[name] = machine
        return machine

    def unregister(self, name: str) -> None:
        self._machines.pop(name, None)

    def get(self, name: str) -> MachineInfo | None:
        return self._machines.get(name)

    def list_online(self) -> list[dict]:
        return [
            {
                "name": m.name,
                "connected_at": m.connected_at,
                "last_heartbeat": m.last_heartbeat,
                "has_active_session": m.active_session_id is not None,
            }
            for m in self._machines.values()
        ]

    def add_ui_client(self, ws: WebSocket) -> None:
        self._ui_clients.append(ws)

    def remove_ui_client(self, ws: WebSocket) -> None:
        self._ui_clients = [c for c in self._ui_clients if c is not ws]

    async def broadcast_ui(self, event: dict) -> None:
        stale: list[WebSocket] = []
        for client in self._ui_clients:
            try:
                await client.send_json(event)
            except Exception:
                stale.append(client)
        for client in stale:
            self.remove_ui_client(client)
