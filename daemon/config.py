import os
import socket
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DaemonConfig:
    machine_name: str = field(
        default_factory=lambda: os.getenv(
            "DAEMON_MACHINE_NAME", socket.gethostname()
        )
    )
    backend_ws_url: str = field(
        default_factory=lambda: os.getenv(
            "DAEMON_BACKEND_URL", "wss://assistant.sogos.io/ws/daemon"
        )
    )
    voice_agent_dir: str = field(
        default_factory=lambda: os.getenv(
            "DAEMON_VOICE_AGENT_DIR",
            os.path.expanduser(
                "~/Desktop/experiments/claude-assistant-avatar-with-voice"
            ),
        )
    )
    ngrok_domain: str = field(
        default_factory=lambda: os.getenv("NGROK_DOMAIN", "")
    )
    heartbeat_interval: int = 15
    reconnect_base: float = 1.0
    reconnect_max: float = 30.0
