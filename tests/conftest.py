"""pytest configuration — ensures module paths and clean test DBs."""
import os
import sys
import tempfile

# Resolve paths relative to the tests/ directory
_BASE = os.path.dirname(os.path.abspath(__file__))
HQ_DIR = os.path.join(_BASE, "..", "hq")
BEACON_DIR = os.path.join(_BASE, "..", "beacon")

for _p in (HQ_DIR, BEACON_DIR):
    _ap = os.path.abspath(_p)
    if _ap not in sys.path:
        sys.path.insert(0, _ap)

# Set env vars BEFORE any module imports
_hq_tmp = tempfile.mkdtemp()
os.environ["HQ_DB"] = os.path.join(_hq_tmp, "test_hq.db")
os.environ["DEMO_MODE"] = "true"
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("RETELL_API_KEY", "")
os.environ.setdefault("BEACON_ID", "test-beacon-01")
os.environ.setdefault("BEACON_DB", os.path.join(tempfile.mkdtemp(), "test_beacon.db"))
os.environ.setdefault("HQ_URL", "http://localhost:9999")
