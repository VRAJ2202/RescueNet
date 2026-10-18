# RescueNet — Demo Walkthrough

## Setup (do this before judges arrive)

### Laptop (HQ)
```bash
cd hq
uvicorn main:app --host 0.0.0.0 --port 8000
# OR with public URL:
ngrok http 8000   # keep this running; copy the https URL
```

Open **http://localhost:8000** (or the ngrok URL) in the browser. You should see the dark emergency dashboard.

### Android (Beacon)
1. Settings → Hotspot → rename to **SOS-HELP** → turn on.
2. In Termux:
```bash
cd RescueNet/beacon
export HQ_URL=https://xxxx.ngrok.io   # your ngrok/Render URL
export BEACON_ID=beacon-android-01
python app.py
```
3. **Disable mobile data** on Android (so it truly has no internet).
4. Note the beacon IP shown in Termux (usually `192.168.43.1:8080`).
5. Generate or display QR code to `http://192.168.43.1:8080`.

### iPhone 2 (Dispatcher)
- Make sure it can receive calls from the Retell number.

---

## Demo Script (~2 minutes)

### Step 1 — Set the scene
> "It's 2 AM. Hurricane has taken out 74% of cell towers in the county — exactly what happened during Helene 2024. There's no internet, no signal."

- Point to Android phone: *"This Android phone is running our beacon. It's broadcasting a local Wi-Fi called SOS-HELP. No internet."*

---

### Step 2 — Victim sends SOS (iPhone 1)

1. Ask a judge to connect their iPhone (or iPhone 1) to **SOS-HELP** Wi-Fi.
2. They open Safari and scan the QR code (or type `http://192.168.43.1:8080`).
3. They fill in:
   - **Status:** TRAPPED
   - **People:** 2
   - **Injured:** 1
   - **Location:** 2nd floor, blue house, back bedroom
4. Tap **SEND SOS**.
5. Page shows: **"SOS saved on nearby beacon. Not yet delivered to emergency headquarters."**
6. Tracking code (e.g. `A7K3`) is displayed prominently.

> "Their SOS is saved. But it hasn't reached anyone yet — we're honest about that."

---

### Step 3 — Courier moment (walk the Android)

> "Now watch. A fire truck drives through the neighborhood. It has a Starlink dish. Or just a driver with a working phone. We simulate that by..."

- **Turn off the Android's hotspot** (or move it).
- Connect the Android to the **venue Wi-Fi** (internet connection).
- The uploader thread auto-detects HQ and uploads in ~15 seconds.

---

### Step 4 — HQ dashboard

- New pin appears on the Leaflet map.
- Incident card shows **CRITICAL** severity badge.
- AI summary: *"2 people trapped on 2nd floor; 1 injured."*

> "Headquarters sees it. AI ranked it CRITICAL — the rules always run first, AI can only raise severity, never lower it."

---

### Step 5 — Retell notification call

- Click **📞 Notify Call** on the incident card.
- iPhone 2 rings with a Retell AI voice alert.
- If DEMO_MODE=true: confirmation modal shows "Simulated call."

---

### Step 6 — Dispatcher assigns team

1. Click **🚒 Assign Team** on the incident.
2. Enter: **Engine 23** / **15 minutes**.
3. Click Assign.
4. Card updates to "Team assigned."

---

### Step 7 — Victim checks their status

- Walk the Android back and reconnect to the beacon Wi-Fi.
- The uploader pulls updates from HQ (GET /api/v1/updates).
- On the victim's phone: open Safari → `http://192.168.43.1:8080/status` → enter `A7K3`.
- Page shows: **"Help is on the way — Engine 23, ETA: 15 minutes."**

> "The victim didn't need our app. They didn't need internet. Their SOS traveled from a phone to a beacon to a fire truck to HQ and back — store-and-forward, like email for emergencies."

---

## Fallback Plan (if demo fails)

1. **Pre-record a backup video** of the full end-to-end flow.
2. Keep the simulation chart ready: `sim/out/delivery_vs_adoption.png`.
3. Walk judges through the code on laptop if demo hardware fails.
4. Show the live dashboard with a manually injected incident:
```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{"message_id":"demo-001","beacon_id":"beacon-android-01","status":"trapped","people":2,"injured":1,"landmark":"2nd floor blue house","created_at":1792260000,"hops":["beacon-android-01"],"beacon_lat":34.021,"beacon_lon":-118.287}'
```

---

## Common Issues

| Issue | Fix |
|---|---|
| Android hotspot blocks Flask | Use `192.168.43.1:8080` — Android hotspot gateway is always that IP |
| "No internet — stay connected?" on victim phone | Tap **Yes** |
| Termux Flask won't start | `pkg install python` then `pip install flask requests` |
| Leaflet map blank | Check `/static/vendor/leaflet.js` is served |
| Retell not calling | Set `DEMO_MODE=true` — shows simulated call event instead |
| Beacon GPS unavailable | Set `BEACON_LAT` and `BEACON_LON` env vars manually |
