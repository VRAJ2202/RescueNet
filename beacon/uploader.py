"""Background uploader — runs in a daemon thread alongside Flask.

Periodically checks HQ reachability; when online, uploads pending SOS
messages and pulls dispatcher updates back.
"""
import logging
import threading
import time

import requests

import config
import storage

log = logging.getLogger("uploader")

_stop_event = threading.Event()


def _build_payload(inc: dict) -> dict:
    return {
        "message_id": inc["message_id"],
        "beacon_id": inc["beacon_id"],
        "status": inc["status"],
        "people": inc["people"],
        "injured": inc["injured"],
        "special_needs": inc.get("special_needs") or "",
        "victim_name": inc.get("victim_name") or "",
        "victim_phone": inc.get("victim_phone") or "",
        "landmark": inc["landmark"],
        "notes": inc.get("notes") or "",
        "beacon_lat": inc.get("beacon_lat"),
        "beacon_lon": inc.get("beacon_lon"),
        "created_at": inc["created_at"],
        "hops": [inc["beacon_id"]],
    }


def _is_hq_reachable() -> bool:
    try:
        r = requests.get(config.HQ_HEALTH, timeout=config.UPLOAD_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


def _upload_pending():
    pending = storage.get_pending_upload()
    if not pending:
        return
    for inc in pending:
        payload = _build_payload(inc)
        try:
            r = requests.post(
                config.UPLOAD_ENDPOINT,
                json=payload,
                timeout=config.UPLOAD_TIMEOUT,
            )
            if r.status_code in (200, 201):
                storage.mark_hq_confirmed(inc["message_id"])
                log.info("✓ Uploaded %s (tracking %s)", inc["message_id"][:8], inc["tracking_code"])
            elif r.status_code == 409:
                # Already exists at HQ — treat as confirmed
                storage.mark_hq_confirmed(inc["message_id"])
                log.info("= Duplicate ack %s", inc["message_id"][:8])
            else:
                storage.mark_uploaded(inc["message_id"])
                storage.increment_retry(inc["message_id"])
                log.warning("✗ HQ returned %s for %s", r.status_code, inc["message_id"][:8])
        except Exception as exc:
            storage.increment_retry(inc["message_id"])
            log.warning("✗ Upload error for %s: %s", inc["message_id"][:8], exc)


def _pull_updates():
    try:
        r = requests.get(
            config.UPDATES_ENDPOINT,
            params={"beacon_id": config.BEACON_ID},
            timeout=config.UPLOAD_TIMEOUT,
        )
        if r.status_code == 200:
            updates = r.json().get("updates", [])
            for upd in updates:
                storage.apply_hq_update(upd)
            if updates:
                log.info("↓ Pulled %d update(s) from HQ", len(updates))
    except Exception as exc:
        log.debug("Pull updates failed: %s", exc)


def run_loop():
    """Main uploader loop — call in a daemon thread."""
    log.info("Uploader started (interval=%ds)", config.UPLOAD_INTERVAL)
    while not _stop_event.is_set():
        try:
            if _is_hq_reachable():
                _upload_pending()
                _pull_updates()
        except Exception as exc:
            log.error("Uploader loop error: %s", exc)
        _stop_event.wait(config.UPLOAD_INTERVAL)


def start_background():
    t = threading.Thread(target=run_loop, daemon=True, name="uploader")
    t.start()
    return t


def stop():
    _stop_event.set()
