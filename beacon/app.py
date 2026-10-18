"""Beacon Flask application — runs on Android via Termux.

Serves the offline SOS page on the SOS-HELP Wi-Fi hotspot.
"""
import datetime
import logging
import os
import subprocess
import sys

from flask import Flask, jsonify, redirect, render_template, request, url_for

import config
import storage
import uploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)

app = Flask(__name__)


@app.template_filter("timestamp")
def _ts_filter(value):
    try:
        return datetime.datetime.utcfromtimestamp(int(value)).strftime("%H:%M UTC")
    except Exception:
        return ""


def get_beacon_gps():
    """Try to get GPS from Termux:API; return (lat, lon) or (None, None)."""
    try:
        result = subprocess.run(
            ["termux-location", "-p", "gps", "-r", "once"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            return data.get("latitude"), data.get("longitude")
    except Exception:
        pass
    # Fallback: env-configured coords
    lat = os.environ.get("BEACON_LAT")
    lon = os.environ.get("BEACON_LON")
    if lat and lon:
        return float(lat), float(lon)
    return None, None


# ── Captive-portal probes (Android / iOS / Windows redirect to SOS page) ──
CAPTIVE_PATHS = [
    "/generate_204", "/gen_204",
    "/hotspot-detect.html", "/library/test/success.html",
    "/ncsi.txt", "/connecttest.txt",
    "/redirect", "/canonical.html",
]
for _path in CAPTIVE_PATHS:
    app.add_url_rule(
        _path,
        endpoint=f"captive_{_path.replace('/', '_').replace('.', '_')}",
        view_func=lambda: redirect(url_for("index")),
    )


@app.route("/")
def index():
    return render_template("sos.html", beacon_id=config.BEACON_ID)


@app.route("/sos", methods=["POST"])
def submit_sos():
    lat, lon = get_beacon_gps()
    inc = storage.save_incident(request.form, beacon_lat=lat, beacon_lon=lon)
    return redirect(url_for("confirmation", code=inc["tracking_code"]))


@app.route("/confirmation/<code>")
def confirmation(code: str):
    inc = storage.get_by_tracking(code)
    if not inc:
        return "Tracking code not found.", 404
    return render_template("status.html", inc=inc)


@app.route("/status/<code>")
def status(code: str):
    """Victim checks rescue status by re-entering their tracking code."""
    inc = storage.get_by_tracking(code)
    if not inc:
        return render_template("status.html", inc=None, code=code)
    return render_template("status.html", inc=inc)


@app.route("/status", methods=["GET", "POST"])
def status_lookup():
    code = None
    inc = None
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        if code:
            inc = storage.get_by_tracking(code)
    return render_template("status.html", inc=inc, code=code)


@app.route("/api/status/<code>")
def api_status(code: str):
    inc = storage.get_by_tracking(code)
    if not inc:
        return jsonify({"error": "not found"}), 404
    return jsonify(inc)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "beacon_id": config.BEACON_ID})


def _print_startup_info():
    """Print local IPs so the operator knows what URL to give victims."""
    import socket
    addrs = []
    try:
        # All network interfaces
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ip.startswith(("192.168.", "10.", "172.")) and ":" not in ip:
                addrs.append(ip)
    except Exception:
        pass
    if not addrs:
        addrs = ["192.168.43.1"]  # Samsung hotspot default fallback

    print("\n" + "=" * 52)
    print("  RescueNet Node — Phase 1 ready")
    print("=" * 52)
    for ip in set(addrs):
        print(f"  SOS page  → http://{ip}:{config.FLASK_PORT}/")
        print(f"  Status    → http://{ip}:{config.FLASK_PORT}/status")
    print(f"  Node ID   → {config.BEACON_ID}")
    print(f"  Database  → {config.DB_PATH}")
    hq = os.environ.get("HQ_URL", "")
    if hq and hq != "http://localhost:8000":
        print(f"  HQ sync   → {hq} (uploader active)")
    else:
        print("  HQ sync   → disabled (set HQ_URL to enable)")
    print("=" * 52 + "\n")


if __name__ == "__main__":
    storage.init_db()
    # Only start the HQ uploader when an explicit HQ_URL is configured.
    # In Phase 1 (offline-only test) leave it dormant so there are no
    # noisy connection errors in the logs.
    hq_url = os.environ.get("HQ_URL", "")
    if hq_url and hq_url != "http://localhost:8000":
        uploader.start_background()
    _print_startup_info()
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        use_reloader=False,
    )
