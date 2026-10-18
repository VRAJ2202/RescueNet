"""Tests for HQ FastAPI (Tests 2, 3, 4, 5, 8)."""
import os
import sys

import pytest

# sys.path and env vars set in conftest.py

from fastapi.testclient import TestClient
import database
import main

database.init_db()
client = TestClient(main.app)


SAMPLE_PAYLOAD = {
    "message_id": "test-uuid-001",
    "beacon_id": "beacon-test-01",
    "status": "trapped",
    "people": 2,
    "injured": 1,
    "special_needs": "child",
    "victim_name": "Jane",
    "victim_phone": "",
    "landmark": "2nd floor, blue house, 123 Oak St",
    "notes": "building unstable",
    "beacon_lat": 34.021,
    "beacon_lon": -118.287,
    "created_at": 1792260000,
    "hops": ["beacon-test-01"],
}


# Test — health endpoint
def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# Test 2 — HQ receives SOS and creates incident
def test_create_incident():
    r = client.post("/api/v1/incidents", json=SAMPLE_PAYLOAD)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "created"
    assert data["message_id"] == "test-uuid-001"
    assert data["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")


# Test 3 — Duplicate message_id returns 200 (not 201) and no new incident
def test_duplicate_incident():
    payload = {**SAMPLE_PAYLOAD, "message_id": "test-uuid-dup"}
    r1 = client.post("/api/v1/incidents", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/v1/incidents", json=payload)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"
    # Only one record in DB
    all_incs = [i for i in database.get_all() if i["message_id"] == "test-uuid-dup"]
    assert len(all_incs) == 1


# Test 4 — AI failure: rule triage still works (no API key set)
def test_rule_triage_without_ai():
    import triage
    sev, summary, translation = triage.triage({
        "status": "trapped", "people": 3, "injured": 2,
        "landmark": "Basement", "notes": ""
    })
    assert sev == "CRITICAL"
    assert summary != ""
    assert translation == ""   # no AI key → no translation


# Test 5 — Dispatcher assigns rescue team
def test_assign_rescue_team():
    payload = {**SAMPLE_PAYLOAD, "message_id": "test-uuid-assign"}
    client.post("/api/v1/incidents", json=payload)
    r = client.post(
        "/api/v1/incidents/test-uuid-assign/assign",
        json={"team": "Engine 23", "eta": "15 minutes"},
    )
    assert r.status_code == 200
    assert r.json()["team"] == "Engine 23"
    inc = database.get_by_message_id("test-uuid-assign")
    assert inc["assigned_team"] == "Engine 23"
    assert inc["eta"] == "15 minutes"
    assert inc["dispatch_status"] == "assigned"


# Test — incident list
def test_list_incidents():
    r = client.get("/api/v1/incidents")
    assert r.status_code == 200
    assert "incidents" in r.json()


# Test — get updates for beacon
def test_get_updates():
    r = client.get("/api/v1/updates", params={"beacon_id": "beacon-test-01"})
    assert r.status_code == 200
    updates = r.json()["updates"]
    assert isinstance(updates, list)


# Test — close incident
def test_close_incident():
    payload = {**SAMPLE_PAYLOAD, "message_id": "test-uuid-close"}
    client.post("/api/v1/incidents", json=payload)
    r = client.post("/api/v1/incidents/test-uuid-close/close")
    assert r.status_code == 200
    inc = database.get_by_message_id("test-uuid-close")
    assert inc["dispatch_status"] == "closed"
    assert inc["rescue_status"] == "rescued"


# Test 8 — Retell missing credentials: incident delivery still succeeds
def test_retell_missing_creds():
    import retell_service
    result = retell_service.initiate_call({
        "message_id": "test-000",
        "status": "trapped",
        "people": 2, "injured": 1,
        "landmark": "Test location",
        "severity": "CRITICAL",
    })
    # Must succeed (demo/simulated) even without credentials
    assert result["success"] is True
    assert result["simulated"] is True


# Test — stats endpoint
def test_stats():
    r = client.get("/api/v1/stats")
    assert r.status_code == 200
    s = r.json()
    assert "total" in s
    assert "critical" in s


# Test 6 — Reverse sync: updates endpoint returns assignment
def test_reverse_sync():
    mid = "test-uuid-reverse"
    payload = {**SAMPLE_PAYLOAD, "message_id": mid}
    client.post("/api/v1/incidents", json=payload)
    client.post(f"/api/v1/incidents/{mid}/assign",
                json={"team": "Engine 23", "eta": "15 minutes"})
    r = client.get("/api/v1/updates", params={"beacon_id": "beacon-test-01"})
    updates = r.json()["updates"]
    my_upd = next((u for u in updates if u["message_id"] == mid), None)
    assert my_upd is not None
    assert my_upd["assigned_team"] == "Engine 23"
    assert my_upd["eta"] == "15 minutes"
    assert my_upd["rescue_status"] == "assigned"
