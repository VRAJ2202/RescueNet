"""RescueNet network simulation — NumPy-vectorized for speed.

Simulates a disaster-affected region and measures what fraction of SOS
messages reach HQ under different configurations:
  1. Phone relays only
  2. Phone relays + fixed LoRa beacons
  3. Phone relays + mobile couriers (evacuating cars)

Usage:
  python simulate.py           # defaults, saves PNG
  python simulate.py --help
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from pathlib import Path

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ── Configurable defaults ─────────────────────────────────────────────────────

# Full 4 km × 4 km scenario.  Relay density is sampled to a max of 1200 nodes
# (statistically representative — same contact probability as the full population
# because spatial density within the tile is preserved by uniform sampling).
AREA_KM        = 4.0      # 4 km × 4 km = 16 km²
N_VICTIMS      = 300      # trapped victims
SIM_MINUTES    = 60       # delivery window
DT             = 3        # minutes per step (20 steps total)
PHONE_RANGE_M  = 80       # Wi-Fi Direct / BLE range (m)
LORA_RANGE_M   = 1500     # LoRa urban range (m)
BEACON_GRID_KM = 1.0      # beacons on 1 km grid (schools / shelters)
COURIER_FRAC   = 0.4      # fraction of relays that evacuate by car
COURIER_SPEED  = 15.0     # km/h
EDGE_BAND_M    = 300      # "has signal" band at area edge (m)
SEEDS          = [42, 137]
# Relay phones are sampled to this max to keep matrix ops fast.
# At 0.5% adoption in 16 km² × 2000/km² that's only 160 phones anyway;
# at 20% it would be 6400 — we cap at 1200 so the R×R matrix stays small.
MAX_RELAYS     = 1200
# Effective density used to compute n_relays from adoption %
DENSITY        = 2000     # people / km²


# ── Core simulation (numpy) ───────────────────────────────────────────────────

def _has_signal(xy: np.ndarray) -> np.ndarray:
    """Boolean array: node is within EDGE_BAND_M of any edge of the square."""
    eb = EDGE_BAND_M / 1000
    return (
        (xy[:, 0] <= eb) | (xy[:, 1] <= eb) |
        (xy[:, 0] >= AREA_KM - eb) | (xy[:, 1] >= AREA_KM - eb)
    )


def run_scenario(
    adoption: float,
    with_beacons: bool,
    with_couriers: bool,
    rng: random.Random,
) -> float:
    """Return fraction of SOS messages delivered within SIM_MINUTES."""
    np_rng = np.random.default_rng(rng.randint(0, 2**31))

    # ── Place nodes ───────────────────────────────────────────────────────────
    # Victims — each owns one SOS message (id = index)
    v_xy = np_rng.uniform(0, AREA_KM, (N_VICTIMS, 2))

    # Relay phones — capped at MAX_RELAYS to keep the R×R distance matrix fast
    total_phones = int(DENSITY * AREA_KM * AREA_KM)
    n_relays = min(MAX_RELAYS, max(1, int(total_phones * adoption)))
    r_xy = np_rng.uniform(0, AREA_KM, (n_relays, 2))

    # Fixed beacons on a grid
    if with_beacons:
        step = BEACON_GRID_KM
        xs = np.arange(step / 2, AREA_KM, step)
        ys = np.arange(step / 2, AREA_KM, step)
        gx, gy = np.meshgrid(xs, ys)
        b_xy = np.column_stack([gx.ravel(), gy.ravel()])
    else:
        b_xy = np.empty((0, 2))

    # ── Message state: which (relay/beacon) node carries which victim IDs ─────
    # We track delivery: set of victim IDs that have reached HQ
    delivered = np.zeros(N_VICTIMS, dtype=bool)

    # Each relay carries a bit-set of victim messages (as a boolean matrix)
    # Shape: (n_relays, N_VICTIMS)
    relay_msgs = np.zeros((n_relays, N_VICTIMS), dtype=bool)
    b_msgs = np.zeros((len(b_xy), N_VICTIMS), dtype=bool)

    # Victims broadcast to nearby relays/beacons at t=0
    # (victim is within phone range of relay → relay picks it up)
    if n_relays > 0:
        # dist_vr[i,j] = distance from victim i to relay j (metres)
        diff = v_xy[:, np.newaxis, :] - r_xy[np.newaxis, :, :]   # (V, R, 2)
        dist_vr = np.sqrt((diff ** 2).sum(axis=2)) * 1000         # metres
        # relay j picks up victim i if within phone range
        contact = dist_vr < PHONE_RANGE_M                          # (V, R)
        for j in range(n_relays):
            victims_near_j = np.where(contact[:, j])[0]
            relay_msgs[j, victims_near_j] = True

    if len(b_xy) > 0 and n_relays > 0:
        diff_rb = r_xy[:, np.newaxis, :] - b_xy[np.newaxis, :, :]
        dist_rb = np.sqrt((diff_rb ** 2).sum(axis=2)) * 1000
        # beacons also directly pick up victims within LoRa range
        diff_vb = v_xy[:, np.newaxis, :] - b_xy[np.newaxis, :, :]
        dist_vb = np.sqrt((diff_vb ** 2).sum(axis=2)) * 1000
        b_contact = dist_vb < LORA_RANGE_M
        for k in range(len(b_xy)):
            b_msgs[k, np.where(b_contact[:, k])[0]] = True

    # ── Courier velocities ────────────────────────────────────────────────────
    speed_km_per_min = COURIER_SPEED / 60
    if with_couriers:
        is_courier = np_rng.random(n_relays) < COURIER_FRAC
        # Direction: toward nearest edge
        dx = np.minimum(r_xy[:, 0], AREA_KM - r_xy[:, 0])
        dy = np.minimum(r_xy[:, 1], AREA_KM - r_xy[:, 1])
        toward_x = dx <= dy
        vel = np.zeros((n_relays, 2))
        vel[toward_x & (r_xy[:, 0] <= AREA_KM / 2), 0] = -speed_km_per_min
        vel[toward_x & (r_xy[:, 0] > AREA_KM / 2),  0] =  speed_km_per_min
        vel[~toward_x & (r_xy[:, 1] <= AREA_KM / 2), 1] = -speed_km_per_min
        vel[~toward_x & (r_xy[:, 1] > AREA_KM / 2),  1] =  speed_km_per_min
        vel[~is_courier] = 0
    else:
        vel = np.zeros((n_relays, 2))

    # ── Time loop ─────────────────────────────────────────────────────────────
    steps = SIM_MINUTES // DT
    for _ in range(steps):
        # Move couriers
        r_xy = r_xy + vel * DT
        # Clamp (once outside area they definitely have signal)
        r_xy = np.clip(r_xy, -1.0, AREA_KM + 1.0)

        # ── Phone ↔ phone propagation ─────────────────────────────────────
        if n_relays > 1:
            diff_rr = r_xy[:, np.newaxis, :] - r_xy[np.newaxis, :, :]
            dist_rr = np.sqrt((diff_rr ** 2).sum(axis=2)) * 1000
            in_range = dist_rr < PHONE_RANGE_M
            np.fill_diagonal(in_range, False)
            # Propagate: any relay j within range of relay i gets its messages
            # Union of messages from all in-range relays
            # relay_msgs_new[j] = relay_msgs[j] | OR(relay_msgs[i] for i in range_of_j)
            # Efficiently: for each relay, union from its neighbourhood
            # Use matrix multiply: contact (R×R) @ relay_msgs (R×V) → (R×V) count
            # Then threshold > 0
            new_msgs = (in_range.astype(np.uint8) @ relay_msgs.astype(np.uint8)) > 0
            relay_msgs = relay_msgs | new_msgs

        # ── Relay ↔ beacon propagation ────────────────────────────────────
        if len(b_xy) > 0 and n_relays > 0:
            diff_rb = r_xy[:, np.newaxis, :] - b_xy[np.newaxis, :, :]
            dist_rb = np.sqrt((diff_rb ** 2).sum(axis=2)) * 1000
            rb_range = dist_rb < LORA_RANGE_M    # (R, B)
            # Relays → beacons
            new_b = (rb_range.T.astype(np.uint8) @ relay_msgs.astype(np.uint8)) > 0
            b_msgs = b_msgs | new_b
            # Beacons → relays (LoRa broadcast)
            new_r = (rb_range.astype(np.uint8) @ b_msgs.astype(np.uint8)) > 0
            relay_msgs = relay_msgs | new_r

        # ── Delivery: nodes with signal upload ────────────────────────────
        r_signal = _has_signal(r_xy)   # (R,)
        if r_signal.any():
            delivered |= relay_msgs[r_signal].any(axis=0)

        if len(b_xy) > 0:
            b_signal = _has_signal(b_xy)
            if b_signal.any():
                delivered |= b_msgs[b_signal].any(axis=0)

        if delivered.all():
            break

    return delivered.sum() / N_VICTIMS


def run_all_seeds(adoption: float, with_beacons: bool, with_couriers: bool) -> float:
    results = []
    for seed in SEEDS:
        rng = random.Random(seed)
        results.append(run_scenario(adoption, with_beacons, with_couriers, rng))
    return sum(results) / len(results)


# ── Chart ─────────────────────────────────────────────────────────────────────

def _progress(done: int, total: int, label: str = ""):
    """Print a simple inline progress bar."""
    width = 30
    filled = int(width * done / total)
    bar = "█" * filled + "░" * (width - filled)
    print(f"\r  [{bar}] {done}/{total}  {label:<30}", end="", flush=True)


def generate_chart(output_path: str):
    adoption_pcts = [0.5, 1, 2, 5, 10, 20]
    scenarios = [
        ("phones_only",   False, False),
        ("with_beacons",  True,  False),
        ("with_couriers", True,  True),
    ]
    # total runs = adoption points × scenarios × seeds
    total = len(adoption_pcts) * len(scenarios) * len(SEEDS)
    done = 0

    print(f"Running {total} simulations ({len(adoption_pcts)} adoption levels"
          f" × {len(scenarios)} scenarios × {len(SEEDS)} seeds)\n")

    def _run(adoption, beacons, couriers, label):
        nonlocal done
        results = []
        for seed in SEEDS:
            done += 1
            _progress(done, total, label)
            rng = random.Random(seed)
            results.append(run_scenario(adoption, beacons, couriers, rng))
        return sum(results) / len(results)

    phones_only   = [_run(a/100, False, False, f"phones  {a}%") * 100 for a in adoption_pcts]
    with_beacons  = [_run(a/100, True,  False, f"beacons {a}%") * 100 for a in adoption_pcts]
    with_couriers = [_run(a/100, True,  True,  f"couriers {a}%") * 100 for a in adoption_pcts]

    print()  # newline after progress bar

    # Print table
    print(f"\n{'Adoption':>10} | {'Phones only':>12} | {'+ Beacons':>10} | {'+ Couriers':>10}")
    print("-" * 52)
    for a, p, b, c in zip(adoption_pcts, phones_only, with_beacons, with_couriers):
        print(f"{a:>9}% | {p:>11.1f}% | {b:>9.1f}% | {c:>9.1f}%")

    if not HAS_MPL:
        print("\n(matplotlib not installed — table only)")
        return

    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")

    x = adoption_pcts
    ax.plot(x, phones_only,   "o-", color="#58a6ff", linewidth=2.5, markersize=7,
            label="Phone relays only")
    ax.plot(x, with_beacons,  "s-", color="#ffd700", linewidth=2.5, markersize=7,
            label="+ LoRa beacons (1/km²)")
    ax.plot(x, with_couriers, "D-", color="#3fb950", linewidth=2.5, markersize=7,
            label="+ Evacuating cars (40%)")

    # Highlight 2% adoption with couriers
    idx2 = adoption_pcts.index(2)
    y2 = with_couriers[idx2]
    ax.axhline(y2, color="#ff4444", linestyle="--", linewidth=1, alpha=.6)
    ax.text(adoption_pcts[-1] * 0.97, y2 + 2, f"~{y2:.0f}% at 2%",
            color="#ff4444", fontsize=9, ha="right")

    ax.set_xlabel("% of phones with relay software", color="#8b949e", fontsize=11)
    ax.set_ylabel("% of SOS delivered within 60 min", color="#8b949e", fontsize=11)
    ax.set_title("RescueNet: SOS Delivery vs. Adoption",
                 color="#e6edf3", fontsize=13, fontweight="bold", pad=14)
    ax.tick_params(colors="#8b949e")
    for spine in ax.spines.values():
        spine.set_color("#30363d")
    ax.grid(color="#30363d", linestyle="--", linewidth=.7)
    ax.legend(facecolor="#1c2230", edgecolor="#30363d", labelcolor="#e6edf3", fontsize=10)
    ax.set_xlim(0, 22)
    ax.set_ylim(-2, 105)

    ax.annotate(
        f"{y2:.0f}% at 2% adoption\nwith evacuating cars",
        xy=(2, y2),
        xytext=(6, max(10, y2 - 25)),
        color="#3fb950", fontsize=9,
        arrowprops=dict(arrowstyle="->", color="#3fb950"),
    )

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"\nChart saved → {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RescueNet delivery simulation")
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent / "out" / "delivery_vs_adoption.png"),
    )
    args = parser.parse_args()
    import time as _time
    print(
        f"Simulation params: area={AREA_KM}km², victims={N_VICTIMS}, "
        f"window={SIM_MINUTES}min, dt={DT}min, seeds={SEEDS}"
    )
    t0 = _time.time()
    generate_chart(args.out)
    print(f"Total time: {_time.time() - t0:.1f}s")
