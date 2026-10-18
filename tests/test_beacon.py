"""Tests for the beacon storage layer (Test 1, 7)."""
import os
import sys

import pytest

# sys.path and env vars set in conftest.py

import storage


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    import config
    config.DB_PATH = str(tmp_path / "beacon_test.db")
    storage.init_db()
    yield


class FakeForm(dict):
    def getlist(self, key):
        v = self.get(key, "")
        return v.split(",") if v else []


def make_form(**kwargs):
    defaults = dict(status="trapped", people="2", injured="1",
                    landmark="2nd floor blue house", notes="")
    defaults.update(kwargs)
    return FakeForm(defaults)


# Test 1 — Offline SOS stored on beacon
def test_save_incident_offline():
    form = make_form(status="trapped", people="3", injured="1",
                     landmark="Main St school gym")
    inc = storage.save_incident(form)
    assert inc is not None
    assert inc["delivery_status"] == "saved_on_beacon"
    assert inc["tracking_code"] != ""
    assert len(inc["tracking_code"]) == 4
    assert inc["status"] == "trapped"
    assert inc["people"] == 3


# Test — retrieval by tracking code
def test_get_by_tracking():
    form = make_form(landmark="Oak Ave bridge")
    inc = storage.save_incident(form)
    fetched = storage.get_by_tracking(inc["tracking_code"])
    assert fetched is not None
    assert fetched["message_id"] == inc["message_id"]


# Test — pending upload queue returns urgent first
def test_pending_order():
    storage.save_incident(make_form(status="safe", landmark="Park bench"))
    storage.save_incident(make_form(status="trapped", injured="2", landmark="Basement"))
    pending = storage.get_pending_upload()
    assert pending[0]["status"] == "trapped"


# Test — mark HQ confirmed
def test_mark_hq_confirmed():
    form = make_form(landmark="Fire station")
    inc = storage.save_incident(form)
    storage.mark_hq_confirmed(inc["message_id"])
    updated = storage.get_by_message_id(inc["message_id"])
    assert updated["delivery_status"] == "hq_confirmed"
    assert updated["hq_confirmed_at"] is not None


# Test 7 — Restart: messages persist in SQLite
def test_persistence_across_init():
    form = make_form(landmark="Hospital lobby")
    inc = storage.save_incident(form)
    mid = inc["message_id"]
    # Re-init DB (simulates restart — idempotent CREATE TABLE IF NOT EXISTS)
    storage.init_db()
    fetched = storage.get_by_message_id(mid)
    assert fetched is not None
    assert fetched["landmark"] == "Hospital lobby"


# Test — apply HQ update (rescue assignment)
def test_apply_hq_update():
    form = make_form(landmark="Green house corner")
    inc = storage.save_incident(form)
    storage.apply_hq_update({
        "message_id": inc["message_id"],
        "assigned_team": "Engine 23",
        "eta": "15 minutes",
        "rescue_status": "assigned",
        "severity": "CRITICAL",
        "summary": "Two trapped.",
    })
    updated = storage.get_by_message_id(inc["message_id"])
    assert updated["assigned_team"] == "Engine 23"
    assert updated["eta"] == "15 minutes"
    assert updated["rescue_status"] == "assigned"
