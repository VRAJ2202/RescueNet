"""HQ configuration — all settings from environment variables."""
import os

# Server
HQ_HOST = os.environ.get("HQ_HOST", "0.0.0.0")
HQ_PORT = int(os.environ.get("HQ_PORT", "8000"))

# Database
DB_PATH = os.environ.get("HQ_DB", "hq.db")

# AI triage (optional)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-3-5-haiku-20241022")

# Retell (optional)
RETELL_API_KEY = os.environ.get("RETELL_API_KEY", "")
RETELL_AGENT_ID = os.environ.get("RETELL_AGENT_ID", "")
RETELL_FROM_NUMBER = os.environ.get("RETELL_FROM_NUMBER", "")
RETELL_NOTIFY_NUMBER = os.environ.get("RETELL_NOTIFY_NUMBER", "")
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"

# Auth token for dispatcher mutations (optional)
DISPATCHER_TOKEN = os.environ.get("DISPATCHER_TOKEN", "")
