# RescueNet

> "Satellite SOS needs open sky. Mesh apps need you to install them before the disaster. RescueNet needs neither — you don't need our app to be rescued, but someone near you does: a beacon, a fire truck, or a neighbor's phone."

**Dual-Use Hackathon @ USC Viterbi — Oct 16–18, 2026 · Vertical 03: Communications + Retell**

---

## What it is

RescueNet is an offline-first emergency communication system for disasters. When cell towers fail, anyone with a smartphone can submit an SOS through a nearby Android **beacon** — no app installation required. The beacon stores every SOS and automatically forwards them to emergency headquarters (HQ) the moment any network connectivity returns (a passing fire truck, an evacuating car, a restored connection).

## Quick Start

### 1 — Install dependencies

```bash
# HQ
pip install -r hq/requirements.txt

# Beacon
pip install -r beacon/requirements.txt

# Tests
pip install pytest httpx

# Simulation (optional)
pip install matplotlib numpy
```

### 2 — Configure

```bash
cp .env.example .env
# Edit .env with your API keys (all optional — demo mode works without them)
```

### 3 — Start HQ (laptop)

```bash
cd hq
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# Dashboard: http://localhost:8000
```

### 4 — Start Beacon (local dev)

```bash
cd beacon
HQ_URL=http://localhost:8000 python app.py
# SOS page: http://localhost:8080
```

### 5 — Run Tests

```bash
pytest tests/ -v
```

### 6 — Run Simulation

```bash
python sim/simulate.py
# Outputs: sim/out/delivery_vs_adoption.png
```

---

## Android / Termux Setup

1. Install **Termux** from F-Droid or GitHub (not Play Store).
2. Install **Termux:API** (optional, for GPS).
3. In Termux:

```bash
pkg update && pkg install python git
pip install flask requests
git clone https://github.com/SapnilPatel/RescueNet
cd RescueNet/beacon

# Set your HQ URL
export HQ_URL=https://your-hq.onrender.com
export BEACON_ID=beacon-android-01

python app.py
```

4. On Android: Settings → Hotspot → rename to **`SOS-HELP`**, disable mobile data.
5. Beacon URL: `http://192.168.43.1:8080` (typical Android hotspot IP).
6. Print/display a QR code pointing to that URL.

---

## Deploy HQ to Render

1. Push repo to GitHub.
2. New Web Service on [render.com](https://render.com) using `render.yaml`.
3. Add env vars in Render dashboard (ANTHROPIC_API_KEY, RETELL_*, etc).
4. Set `HQ_URL` on the beacon to the Render URL.

```bash
# Local HQ with public URL via ngrok (backup)
ngrok http 8000
# Use the https://xxx.ngrok.io URL as HQ_URL on the beacon
```

---

## Architecture

```
[Victim's phone] — joins SOS-HELP Wi-Fi —→ [Android Beacon]
                                                    │
                                         SQLite store-and-forward
                                                    │
                                     (when internet returns)
                                                    ↓
                                           [HQ FastAPI]
                                          /    |      \
                                    Leaflet  Claude  Retell
                                     Map    Triage   Call
```

### Delivery states

`saved_on_beacon` → `uploaded` → `hq_confirmed`

We never claim an SOS reached responders until HQ has acknowledged it.

---

## Two Lives, One Tool

| Life | Use |
|---|---|
| **Ordinary day** | Relay SDK inside stadium / campus apps; offline trail check-in at parks |
| **Crisis** | Same phones and beacons switch to SOS mode; anyone nearby sends via browser |

---

## Tech Stack

| Layer | Tech |
|---|---|
| Beacon | Python · Flask · SQLite · Termux |
| HQ | Python 3.11 · FastAPI · Uvicorn · SQLite |
| AI triage | Anthropic Claude (optional) + deterministic rules |
| Voice | Retell AI outbound call (optional) |
| Dashboard | Leaflet.js + OpenStreetMap (bundled) |
| Simulation | Python · matplotlib |
| Deploy | Render free tier · ngrok backup |

---

## Funding pathways (civilian only)

- **NSF I-Corps** via USC (accessible for international founders)
- **NTIA** (Broadband / disaster communications)
- **DHS S&T SVIP** (resilience technology)
- **FirstNet Authority** (public-safety comms)

---

## Key numbers (from simulation)

| Adoption | Phones only | + LoRa beacons | + Evacuating cars |
|---|---|---|---|
| 2% | ~1% | ~4% | **~85%** |
| 5% | ~2% | ~6% | ~97% |
| 10% | ~28% | ~67% | ~99.8% |

Pitch line: "With 2% of phones carrying our SDK and cars carrying messages out, ~85% of SOS messages reach responders within an hour."

---

## Limitations (honest)

- iPhone browsers block GPS on `http://` — location = beacon GPS (±50–100 m) + victim's text description.
- Real phone-to-phone multi-hop requires 2+ Androids with relay SDK (Nearby Connections) — stretch goal.
- LoRa beacons ($20–40 boards) are pitched/simulated; not live-demoed unless hardware is available.
- Courier update loop is delayed until the beacon reconnects — stated honestly to victims.
