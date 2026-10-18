"""SQLite persistence layer for HQ."""
import os
import sqlite3
import time
from contextlib import contextmanager


def _db_path() -> str:
    """Read DB path at call time so test env overrides work."""
    try:
        import importlib, sys
        # Prefer the hq-specific config if it's loaded
        hq_cfg = sys.modules.get("hq.config") or sys.modules.get("config")
        if hq_cfg and hasattr(hq_cfg, "DB_PATH") and "hq" in (hq_cfg.__file__ or ""):
            return hq_cfg.DB_PATH
    except Exception:
        pass
    return os.environ.get("HQ_DB", "hq.db")


@contextmanager
def get_db():
    conn = sqlite3.connect(_db_path(), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
                beacon_id TEXT NOT NULL,
                status TEXT NOT NULL,
                people INTEGER NOT NULL DEFAULT 1,
                injured INTEGER NOT NULL DEFAULT 0,
                special_needs TEXT DEFAULT '',
                victim_name TEXT DEFAULT '',
                victim_phone TEXT DEFAULT '',
                landmark TEXT NOT NULL,
                notes TEXT DEFAULT '',
                beacon_lat REAL,
                beacon_lon REAL,
                created_at INTEGER NOT NULL,
                received_at INTEGER NOT NULL,
                hops TEXT DEFAULT '[]',
                severity TEXT NOT NULL DEFAULT 'MEDIUM',
                summary TEXT DEFAULT '',
                translation TEXT DEFAULT '',
                dispatch_status TEXT NOT NULL DEFAULT 'pending',
                assigned_team TEXT,
                eta TEXT,
                rescue_status TEXT DEFAULT 'pending',
                call_initiated INTEGER DEFAULT 0,
                call_sid TEXT DEFAULT '',
                acked_at INTEGER
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_beacon ON incidents(beacon_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON incidents(dispatch_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_severity ON incidents(severity)")


def insert_incident(payload: dict, severity: str, summary: str, translation: str = "") -> dict:
    now = int(time.time())
    import json
    with get_db() as conn:
        conn.execute(
            """INSERT INTO incidents
               (message_id,beacon_id,status,people,injured,special_needs,
                victim_name,victim_phone,landmark,notes,beacon_lat,beacon_lon,
                created_at,received_at,hops,severity,summary,translation)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                payload["message_id"],
                payload["beacon_id"],
                payload["status"],
                payload["people"],
                payload["injured"],
                payload.get("special_needs", ""),
                payload.get("victim_name", ""),
                payload.get("victim_phone", ""),
                payload["landmark"],
                payload.get("notes", ""),
                payload.get("beacon_lat"),
                payload.get("beacon_lon"),
                payload["created_at"],
                now,
                json.dumps(payload.get("hops", [])),
                severity,
                summary,
                translation,
            ),
        )
    return get_by_message_id(payload["message_id"])


def get_by_message_id(message_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE message_id=?", (message_id,)
        ).fetchone()
    return dict(row) if row else None


def get_all(limit: int = 200) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY received_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_by_beacon(beacon_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM incidents WHERE beacon_id=?", (beacon_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def ack_incident(message_id: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE incidents SET dispatch_status='acknowledged', acked_at=? WHERE message_id=?",
            (int(time.time()), message_id),
        )


def assign_incident(message_id: str, team: str, eta: str):
    with get_db() as conn:
        conn.execute(
            """UPDATE incidents SET
               dispatch_status='assigned', assigned_team=?, eta=?, rescue_status='assigned'
               WHERE message_id=?""",
            (team, eta, message_id),
        )


def close_incident(message_id: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE incidents SET dispatch_status='closed', rescue_status='rescued' WHERE message_id=?",
            (message_id,),
        )


def set_call_initiated(message_id: str, call_sid: str = ""):
    with get_db() as conn:
        conn.execute(
            "UPDATE incidents SET call_initiated=1, call_sid=? WHERE message_id=?",
            (call_sid, message_id),
        )


def get_stats() -> dict:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        critical = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='CRITICAL'").fetchone()[0]
        high = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='HIGH'").fetchone()[0]
        people = conn.execute("SELECT COALESCE(SUM(people),0) FROM incidents WHERE dispatch_status!='closed'").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM incidents WHERE dispatch_status NOT IN ('closed')").fetchone()[0]
        assigned = conn.execute("SELECT COUNT(*) FROM incidents WHERE dispatch_status='assigned'").fetchone()[0]
        closed = conn.execute("SELECT COUNT(*) FROM incidents WHERE dispatch_status='closed'").fetchone()[0]
    return {
        "total": total, "critical": critical, "high": high,
        "people_needing_help": people, "active": active,
        "assigned": assigned, "closed": closed,
    }
