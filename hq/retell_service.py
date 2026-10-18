"""Retell AI outbound call service.

Initiates a voice notification when a critical SOS arrives.
Gracefully degrades when credentials are missing.
"""
import logging
import os
import time

import config

log = logging.getLogger("retell")


def _build_dynamic_vars(inc: dict) -> dict:
    return {
        "tracking_code": inc.get("tracking_code") or inc.get("message_id", "")[:8],
        "severity": inc.get("severity", "UNKNOWN"),
        "status": inc.get("status", "unknown"),
        "people": str(inc.get("people", 0)),
        "injured": str(inc.get("injured", 0)),
        "landmark": inc.get("landmark", "unknown location"),
        "summary": inc.get("summary") or f"{inc.get('people',0)} person(s) at {inc.get('landmark','')}.",
    }


def initiate_call(inc: dict, override_phone: str | None = None) -> dict:
    """
    Initiate a Retell outbound call.
    Returns a result dict with keys: success (bool), call_id (str), simulated (bool).
    """
    # Read at call time so env overrides work in tests
    retell_key = os.environ.get("RETELL_API_KEY", "") or getattr(config, "RETELL_API_KEY", "")
    retell_agent = os.environ.get("RETELL_AGENT_ID", "") or getattr(config, "RETELL_AGENT_ID", "")
    retell_from = os.environ.get("RETELL_FROM_NUMBER", "") or getattr(config, "RETELL_FROM_NUMBER", "")
    notify_num = os.environ.get("RETELL_NOTIFY_NUMBER", "") or getattr(config, "RETELL_NOTIFY_NUMBER", "")
    demo = os.environ.get("DEMO_MODE", "").lower() == "true" or getattr(config, "DEMO_MODE", False)

    phone = override_phone or notify_num

    # Demo / no-credentials mode
    if demo or not all([retell_key, retell_agent, retell_from, phone]):
        log.info("[DEMO] Simulated Retell call for incident %s to %s",
                 inc.get("message_id", "")[:8], phone or "N/A")
        return {
            "success": True,
            "call_id": f"demo-{int(time.time())}",
            "simulated": True,
            "message": "Demo mode: no real call placed.",
        }

    try:
        import requests
        payload = {
            "from_number": config.RETELL_FROM_NUMBER,
            "to_number": phone,
            "agent_id": config.RETELL_AGENT_ID,
            "retell_llm_dynamic_variables": _build_dynamic_vars(inc),
        }
        r = requests.post(
            "https://api.retellai.com/v2/create-phone-call",
            headers={
                "Authorization": f"Bearer {config.RETELL_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 201):
            data = r.json()
            call_id = data.get("call_id", "")
            log.info("✓ Retell call initiated: %s", call_id)
            return {"success": True, "call_id": call_id, "simulated": False}
        else:
            log.error("Retell API error %s: %s", r.status_code, r.text[:200])
            return {"success": False, "call_id": "", "simulated": False, "error": r.text[:200]}
    except Exception as exc:
        log.error("Retell call exception: %s", exc)
        return {"success": False, "call_id": "", "simulated": False, "error": str(exc)}
