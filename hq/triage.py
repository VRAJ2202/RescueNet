"""AI-assisted triage.

Deterministic rules are the safety baseline; Claude optionally enriches.
AI may raise severity, never lower it.  AI never blocks delivery.
"""
import logging
import os
from typing import Optional

import config

log = logging.getLogger("triage")


# ── Deterministic rules ───────────────────────────────────────────────────────

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _rule_severity(status: str, injured: int, people: int, notes: str) -> str:
    s = status.lower()
    n = (notes or "").lower()
    danger_words = {"fire", "flood", "collapse", "gas", "smoke", "explosion", "rubble", "trapped", "buried"}
    has_danger = any(w in n for w in danger_words)

    if s == "trapped":
        return "CRITICAL" if injured > 0 else "HIGH"
    if s == "injured":
        return "CRITICAL" if injured >= 3 else "HIGH"
    if s == "evacuation":
        return "HIGH" if (has_danger or people >= 5) else "MEDIUM"
    if s == "safe":
        return "LOW"
    return "MEDIUM"


def _rule_summary(inc: dict) -> str:
    parts = [f"{inc['people']} person(s) — {inc['status']}."]
    if inc.get("injured"):
        parts.append(f"{inc['injured']} injured.")
    if inc.get("special_needs"):
        parts.append(f"Special needs: {inc['special_needs']}.")
    parts.append(f"Location: {inc['landmark']}.")
    return " ".join(parts)


def _max_severity(a: str, b: str) -> str:
    return a if SEVERITY_ORDER.index(a) >= SEVERITY_ORDER.index(b) else b


# ── Optional Claude enrichment ────────────────────────────────────────────────

def _ai_enrich(inc: dict, rule_severity: str, rule_summary: str) -> tuple[str, str, str]:
    """Returns (severity, summary, translation). Falls back on any error."""
    # Read at call time so tests can override env vars after import
    api_key = os.environ.get("ANTHROPIC_API_KEY", "") or getattr(config, "ANTHROPIC_API_KEY", "")
    if not api_key:
        return rule_severity, rule_summary, ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = f"""You are a disaster dispatcher AI. Analyze this SOS report and respond with JSON only.

Report:
- Status: {inc['status']}
- People: {inc['people']} ({inc.get('injured', 0)} injured)
- Special needs: {inc.get('special_needs', 'none')}
- Location: {inc['landmark']}
- Notes: {inc.get('notes', '')}
- Current rule-based severity: {rule_severity}

Respond with ONLY valid JSON:
{{
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "summary": "One sentence dispatcher summary, max 100 chars",
  "translation": "English translation of notes if non-English, else empty string"
}}

Rules:
- severity may be >= {rule_severity} but NEVER lower than {rule_severity}
- summary must be factual, no invented details
- Do not invent medical facts"""

        msg = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        data = json.loads(msg.content[0].text)
        ai_sev = data.get("severity", rule_severity)
        final_sev = _max_severity(ai_sev, rule_severity)
        summary = data.get("summary") or rule_summary
        translation = data.get("translation", "")
        return final_sev, summary, translation
    except Exception as exc:
        log.warning("Claude enrichment failed (%s) — using rule triage", exc)
        return rule_severity, rule_summary, ""


def triage(inc: dict) -> tuple[str, str, str]:
    """Return (severity, summary, translation) — always succeeds."""
    rule_sev = _rule_severity(
        inc.get("status", "safe"),
        int(inc.get("injured", 0)),
        int(inc.get("people", 1)),
        inc.get("notes", ""),
    )
    rule_sum = _rule_summary(inc)
    return _ai_enrich(inc, rule_sev, rule_sum)
