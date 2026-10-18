"""SQLite storage for the offline beacon."""
import sqlite3
import uuid
import random
import string
import time
from contextlib import contextmanager

import config


@contextmanager
def get_db():
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE NOT NULL,
                tracking_code TEXT NOT NULL,
                beacon_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'trapped',
                people INTEGER NOT NULL DEFAULT 1,
                injured INTEGER NOT NULL DEFAULT 0,
                special_needs TEXT,
                victim_name TEXT,
                victim_phone TEXT,
                landmark TEXT NOT NULL,
                notes TEXT,
                beacon_lat REAL,
                beacon_lon REAL,
                created_at INTEGER NOT NULL,
                delivery_status TEXT NOT NULL DEFAULT 'saved_on_beacon',
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_upload_attempt INTEGER,
                hq_confirmed_at INTEGER,
                assigned_team TEXT,
                eta TEXT,
                rescue_status TEXT DEFAULT 'pending',
                hq_severity TEXT,
                hq_summary TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_delivery ON incidents(delivery_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracking ON incidents(tracking_code)")


def _short_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=4))


def save_incident(form: dict, beacon_lat=None, beacon_lon=None) -> dict:
    """Persist a new SOS and return the stored record."""
    message_id = str(uuid.uuid4())
    tracking_code = _short_code()
    now = int(time.time())

    with get_db() as conn:
        conn.execute(
            """INSERT INTO incidents
               (message_id, tracking_code, beacon_id, status, people, injured,
                special_needs, victim_name, victim_phone, landmark, notes,
                beacon_lat, beacon_lon, created_at, delivery_status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                message_id,
                tracking_code,
                config.BEACON_ID,
                form.get("status", "trapped"),
                int(form.get("people", 1)),
                int(form.get("injured", 0)),
                ",".join(form.getlist("special_needs")) if hasattr(form, "getlist") else form.get("special_needs", ""),
                form.get("name", ""),
                form.get("phone", ""),
                form.get("landmark", ""),
                form.get("notes", ""),
                beacon_lat,
                beacon_lon,
                now,
                "saved_on_beacon",
            ),
        )
    return get_by_tracking(tracking_code)


def get_by_tracking(tracking_code: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE tracking_code = ?", (tracking_code,)
        ).fetchone()
    return dict(row) if row else None


def get_by_message_id(message_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE message_id = ?", (message_id,)
        ).fetchone()
    return dict(row) if row else None


def get_pending_upload(limit: int = 20) -> list[dict]:
    """Return messages not yet HQ-confirmed, ordered by urgency."""
    priority = {"trapped": 0, "injured": 1, "evacuation": 2, "safe": 3}
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM incidents
               WHERE delivery_status IN ('saved_on_beacon','uploaded')
               ORDER BY created_at ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    results = [dict(r) for r in rows]
    results.sort(key=lambda r: (priority.get(r["status"], 9), r["created_at"]))
    return results


def mark_uploaded(message_id: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE incidents SET delivery_status='uploaded', last_upload_attempt=? WHERE message_id=?",
            (int(time.time()), message_id),
        )


def mark_hq_confirmed(message_id: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE incidents SET delivery_status='hq_confirmed', hq_confirmed_at=? WHERE message_id=?",
            (int(time.time()), message_id),
        )


def increment_retry(message_id: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE incidents SET retry_count=retry_count+1, last_upload_attempt=? WHERE message_id=?",
            (int(time.time()), message_id),
        )


def apply_hq_update(update: dict):
    """Persist dispatcher assignment/status from HQ."""
    with get_db() as conn:
        conn.execute(
            """UPDATE incidents SET
               assigned_team=?, eta=?, rescue_status=?,
               hq_severity=?, hq_summary=?
               WHERE message_id=?""",
            (
                update.get("assigned_team"),
                update.get("eta"),
                update.get("rescue_status", "pending"),
                update.get("severity"),
                update.get("summary"),
                update["message_id"],
            ),
        )
