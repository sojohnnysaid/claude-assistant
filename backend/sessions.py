from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class SessionInfo:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    machine_name: str = ""
    ngrok_url: str | None = None
    started_at: float = field(default_factory=time.time)
    status: str = "starting"  # starting | active | stopping


class SessionManager:
    def __init__(self) -> None:
        self.active: SessionInfo | None = None

    def start(self, machine_name: str) -> SessionInfo:
        if self.active is not None:
            raise RuntimeError("A session is already active")
        self.active = SessionInfo(machine_name=machine_name)
        return self.active

    def activate(self, ngrok_url: str) -> None:
        if self.active is None:
            return
        self.active.ngrok_url = ngrok_url
        self.active.status = "active"

    def stop(self) -> None:
        self.active = None

    def to_dict(self) -> dict | None:
        if self.active is None:
            return None
        return {
            "session_id": self.active.session_id,
            "machine_name": self.active.machine_name,
            "ngrok_url": self.active.ngrok_url,
            "started_at": self.active.started_at,
            "status": self.active.status,
        }
