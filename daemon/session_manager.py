from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys

from config import DaemonConfig

log = logging.getLogger(__name__)


class SessionManager:
    """Manages ngrok, Temporal, and Val subprocesses for a session."""

    def __init__(self, config: DaemonConfig) -> None:
        self._config = config
        self._ngrok_proc: subprocess.Popen | None = None
        self._temporal_proc: subprocess.Popen | None = None
        self._val_proc: subprocess.Popen | None = None
        self._session_id: str | None = None

    @property
    def is_active(self) -> bool:
        return self._val_proc is not None and self._val_proc.poll() is None

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def ngrok_url(self) -> str | None:
        return self._config.ngrok_domain if self._ngrok_proc else None

    async def start(self, session_id: str) -> str:
        """Start a session. Returns the ngrok URL."""
        if self.is_active:
            raise RuntimeError("Session already active")

        self._session_id = session_id
        agent_dir = self._config.voice_agent_dir

        try:
            # 1. Start ngrok
            log.info("Starting ngrok...")
            self._ngrok_proc = subprocess.Popen(
                [
                    "ngrok", "http", "8765",
                    "--domain", self._config.ngrok_domain,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await asyncio.sleep(2)

            # 2. Start Temporal dev server
            log.info("Starting Temporal...")
            self._temporal_proc = subprocess.Popen(
                [
                    "temporal", "server", "start-dev",
                    "--port", "7533",
                    "--ui-port", "8533",
                    "--namespace", "codec-voice-agent",
                    "--db-filename", "/tmp/temporal-codec.db",
                    "--dynamic-config-value",
                    "frontend.WorkerHeartbeatsEnabled=true",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={**os.environ, "RUST_LOG": "error"},
            )
            await asyncio.sleep(3)

            # 3. Start Val (voice agent)
            log.info("Starting Val...")
            venv_python = os.path.join(agent_dir, "venv", "bin", "python")
            main_py = os.path.join(agent_dir, "main.py")

            # Build PATH that includes common CLI locations (claude, ngrok, temporal)
            home = os.path.expanduser("~")
            val_env = {
                **os.environ,
                "PATH": os.pathsep.join([
                    os.path.join(home, ".local", "bin"),  # claude CLI
                    "/usr/local/bin",
                    "/opt/homebrew/bin",
                    "/usr/bin",
                    "/bin",
                    os.environ.get("PATH", ""),
                ]),
            }

            self._val_proc = subprocess.Popen(
                [venv_python, main_py, "--mode", "phone"],
                cwd=agent_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=val_env,
            )

            log.info(
                f"Session {session_id} started — "
                f"ngrok={self._config.ngrok_domain}, "
                f"val_pid={self._val_proc.pid}"
            )
            return self._config.ngrok_domain

        except Exception as e:
            log.error(f"Failed to start session: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop all subprocesses."""
        log.info(f"Stopping session {self._session_id}...")

        for name, proc in [
            ("Val", self._val_proc),
            ("Temporal", self._temporal_proc),
            ("ngrok", self._ngrok_proc),
        ]:
            if proc and proc.poll() is None:
                log.info(f"Killing {name} (pid={proc.pid})")
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=3)
                except Exception as e:
                    log.warning(f"Error stopping {name}: {e}")

        self._val_proc = None
        self._temporal_proc = None
        self._ngrok_proc = None
        self._session_id = None
        log.info("Session stopped")
