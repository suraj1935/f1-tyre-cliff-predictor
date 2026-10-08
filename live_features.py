"""Build the training features from raw lap times, then score them.

Mirrors build_features.py: laps that training dropped are dropped here too, and the
rolling features are computed on the laps that remain.
"""
import numpy as np
from predict import cliff_probability

FUEL_EFFECT_S_PER_LAP = 0.03


def build_stint_rows(laps, compound, total_laps, start_tyre_life=1, fresh_tyre=True,
                     weather=None, position=None, pits_nearby=None):
    """laps: list of dicts with lap_number, lap_time_s, optional skip (bool).
    Returns (rows, dropped) where rows are dicts ready for scoring."""
    weather = weather or {}
    pits_nearby = pits_nearby or {}
    position = position or {}
    first = min((l["lap_number"] for l in laps), default=1)

    kept, dropped = [], []
    for l in sorted(laps, key=lambda x: x["lap_number"]):
        n, t = l["lap_number"], l.get("lap_time_s")
        if n == 1:
            dropped.append((n, "lap 1")); continue
        if t is None or not np.isfinite(t) or t <= 0:
            dropped.append((n, "no lap time")); continue
        if l.get("skip"):
            dropped.append((n, l["skip"] if isinstance(l["skip"], str) else "flagged")); continue
        kept.append(l)

    rows, best, prev_fc, diffs, deltas = [], None, None, [], []
    for l in kept:
        n = l["lap_number"]
        fc = l["lap_time_s"] + FUEL_EFFECT_S_PER_LAP * n
        best = fc if best is None else min(best, fc)
        delta = fc - best
        deltas.append(delta)
        diffs.append(0.0 if prev_fc is None else fc - prev_fc)
        prev_fc = fc
        rows.append({
            "LapNumber": n,
            "TyreLife": start_tyre_life + (n - first),
            "Compound": compound,
            "FreshTyre": int(bool(fresh_tyre)),
            "RaceProgress": n / total_laps if total_laps else None,
            "LapsRemaining": (total_laps - n) if total_laps else None,
            "Position": position.get(n),
            "AirTemp": weather.get(n, {}).get("AirTemp"),
            "TrackTemp": weather.get(n, {}).get("TrackTemp"),
            "Humidity": weather.get(n, {}).get("Humidity"),
            "WindSpeed": weather.get(n, {}).get("WindSpeed"),
            "DeltaSoFar": delta,
            "Delta3": float(np.mean(deltas[-3:])),
            "Slope3": float(np.mean(diffs[-3:])),
            "PitsNearby": pits_nearby.get(n),
            "LapTime": l["lap_time_s"],
        })
    return rows, dropped


def score_rows(rows):
    out = []
    for r in rows:
        state = {k: v for k, v in r.items() if v is not None and k not in ("LapNumber", "LapTime")}
        out.append({"lap": r["LapNumber"], "tyre_life": r["TyreLife"], "lap_time": round(r["LapTime"], 3),
                    "delta": round(r["DeltaSoFar"], 3), "risk": round(cliff_probability(state), 4)})
    return out
