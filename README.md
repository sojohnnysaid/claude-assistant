# Claude Assistant

Remote voice agent orchestration — start/stop Val sessions on any machine from assistant.sogos.io.

## Architecture

- **Frontend** (SvelteKit) — Web UI at assistant.sogos.io
- **Backend** (FastAPI) — Thin coordinator in the cluster, manages machine registry and session state
- **Daemon** (Python) — Runs on local machines, connects to backend, spawns Val on command

## Daemon Setup (New Machine)

### Prerequisites

- Python 3.12+
- [ngrok](https://ngrok.com/) installed and authenticated (`ngrok config add-authtoken <token>`)
- [Temporal CLI](https://docs.temporal.io/cli) installed
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- The voice agent repo cloned with a working venv:
  ```bash
  git clone https://github.com/sojohnnysaid/claude-assistant-avatar-with-voice.git ~/claude-assistant-avatar-with-voice
  cd ~/claude-assistant-avatar-with-voice
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```
- A `.env` in the voice agent directory with API keys:
  ```
  GEMINI_API_KEY=<your-key>
  ELEVENLABS_API_KEY=<your-key>
  ELEVENLABS_VOICE_ID=<voice-id>
  TWILIO_ACCOUNT_SID=<sid>
  TWILIO_AUTH_TOKEN=<token>
  TWILIO_PHONE_NUMBER=<number>
  NGROK_DOMAIN=<your-ngrok-domain>
  ```

### Install the Daemon

1. Clone this repo:
   ```bash
   git clone https://github.com/sojohnnysaid/claude-assistant.git ~/claude-assistant
   ```

2. Set up the daemon venv:
   ```bash
   cd ~/claude-assistant/daemon
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Create `daemon/.env`:
   ```
   DAEMON_MACHINE_NAME=My-Machine-Name
   DAEMON_BACKEND_URL=wss://assistant.sogos.io/ws/daemon
   DAEMON_VOICE_AGENT_DIR=/path/to/claude-assistant-avatar-with-voice
   NGROK_DOMAIN=your-ngrok-domain.ngrok-free.app
   ```
   - `DAEMON_MACHINE_NAME` — Friendly name shown in the web UI
   - `DAEMON_VOICE_AGENT_DIR` — Absolute path to the voice agent repo (with working venv and .env)
   - `NGROK_DOMAIN` — Each machine needs its own ngrok domain (create at ngrok.com dashboard)

4. Install as a macOS background service:
   ```bash
   ./install.sh
   ```

5. Verify it's running:
   ```bash
   tail -f ~/Library/Logs/claude-daemon/stderr.log
   ```
   You should see: `Connected as 'My-Machine-Name'`

6. Check assistant.sogos.io — your machine should appear as online.

### Managing the Daemon

```bash
# Check status
launchctl list | grep claude

# Stop
launchctl unload ~/Library/LaunchAgents/com.sogos.claude-daemon.plist

# Start
launchctl load ~/Library/LaunchAgents/com.sogos.claude-daemon.plist

# View logs
tail -f ~/Library/Logs/claude-daemon/stderr.log
```

### Each Machine Needs

| Item | Unique per machine? |
|------|---------------------|
| ngrok domain | Yes — each machine needs its own |
| API keys (Gemini, ElevenLabs) | Can share the same keys |
| Twilio credentials | Same account, same phone number |
| DAEMON_MACHINE_NAME | Yes — unique friendly name |

## Development

```bash
# Frontend
cd frontend && npm install && npm run dev

# Backend
cd backend && pip install -r requirements.txt && python main.py

# Daemon (manual run, not as service)
cd daemon && source venv/bin/activate && python daemon.py
```

## Deployment

Push to `main` triggers GitHub Actions to build frontend + backend Docker images.
ArgoCD syncs k8s manifests to deploy at assistant.sogos.io.
