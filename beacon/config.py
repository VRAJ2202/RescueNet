"""Beacon configuration — all tunables in one place."""
import os

BEACON_ID = os.environ.get("BEACON_ID", "beacon-android-01")
HQ_URL = os.environ.get("HQ_URL", "http://localhost:8000")
UPLOAD_INTERVAL = int(os.environ.get("UPLOAD_INTERVAL", "15"))   # seconds
DB_PATH = os.environ.get("BEACON_DB", "beacon.db")
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "8080"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

# Connectivity probe — lightweight endpoint
HQ_HEALTH = f"{HQ_URL}/health"
UPLOAD_ENDPOINT = f"{HQ_URL}/api/v1/incidents"
UPDATES_ENDPOINT = f"{HQ_URL}/api/v1/updates"

UPLOAD_TIMEOUT = int(os.environ.get("UPLOAD_TIMEOUT", "10"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "5"))
