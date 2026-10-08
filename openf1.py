"""Small OpenF1 client plus the cleaning rules that match training.

Field names follow the OpenF1 docs (laps: lap_number, lap_duration, is_pit_out_lap, date_start;
stints: stint_number, lap_start, lap_end, compound, tyre_age_at_start; weather; position;
race_control). I could not hit the live API while writing this, so every read is defensive.
"""
import time
from bisect import bisect_right
from datetime import datetime
from functools import lru_cache
import httpx

BASE = "https://api.openf1.org/v1"


class OpenF1Error(Exception):
    pass


def _get(path, **params):
    for attempt in range(4):
        try:
            r = httpx.get(f"{BASE}/{path}", params=params, timeout=20)
        except httpx.HTTPError as e:
            raise OpenF1Error(f"OpenF1 unreachable: {e}")
        if r.status_code == 429:
            time.sleep(1.5 * (attempt + 1)); continue
        if r.status_code == 404:
            return []  # OpenF1 answers 404 when a filter matches nothing
        if r.status_code != 200:
            raise OpenF1Error(f"OpenF1 returned {r.status_code} for {path}")
        data = r.json()
        return data if isinstance(data, list) else []
    raise OpenF1Error("OpenF1 rate limit, try again in a moment")


@lru_cache(maxsize=64)
def sessions(year):
    rows = _get("sessions", year=year, session_name="Race")
    return sorted(({"session_key": s["session_key"], "country": s.get("country_name"),
                    "circuit": s.get("circuit_short_name"), "date": (s.get("date_start") or "")[:10]}
                   for s in rows if "session_key" in s), key=lambda s: s["date"])


@lru_cache(maxsize=64)
def drivers(session_key):
    rows = _get("drivers", session_key=session_key)
    return sorted(({"number": d["driver_number"], "code": d.get("name_acronym"), "name": d.get("full_name"),
                    "team": d.get("team_name")} for d in rows if "driver_number" in d), key=lambda d: d["code"] or "")


@lru_cache(maxsize=32)
def race_data(session_key):
    """Everything shared by all drivers in a session, fetched once."""
    return {"stints": _get("stints", session_key=session_key),
            "weather": _get("weather", session_key=session_key),
            "control": _get("race_control", session_key=session_key)}


@lru_cache(maxsize=128)
def driver_laps(session_key, driver_number):
    return _get("laps", session_key=session_key, driver_number=driver_number)


@lru_cache(maxsize=128)
def driver_positions(session_key, driver_number):
    return _get("position", session_key=session_key, driver_number=driver_number)


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def flagged_laps(control, driver_number):
    """Laps under safety car, VSC or a yellow that touches this driver."""
    bad = {}
    sc_start = None
    for m in sorted(control, key=lambda m: m.get("date") or ""):
        lap, msg = m.get("lap_number"), (m.get("message") or "").upper()
        if lap is None:
            continue
        if m.get("category") == "SafetyCar":
            if "DEPLOYED" in msg:
                sc_start = lap
            if "IN THIS LAP" in msg and sc_start is not None:
                for n in range(sc_start, lap + 1):
                    bad[n] = "safety car"
                sc_start = None
        elif m.get("flag") in ("YELLOW", "DOUBLE YELLOW") and m.get("driver_number") in (None, driver_number):
            bad.setdefault(lap, "yellow flag")
    if sc_start is not None:  # SC never ended in the feed
        for n in range(sc_start, 999):
            bad.setdefault(n, "safety car")
    return bad


def pits_nearby_by_lap(stints, driver_number, window=5):
    """Stops by OTHER cars in the previous `window` laps, same rule as training."""
    events = [(s["lap_start"], s["driver_number"]) for s in stints
              if (s.get("stint_number") or 1) > 1 and s.get("lap_start") is not None]
    return lambda lap: sum(1 for l, d in events if lap - window <= l <= lap - 1 and d != driver_number)


def build_inputs(session_key, driver_number, stint_number):
    data = race_data(session_key)
    stints = [s for s in data["stints"] if s.get("driver_number") == driver_number]
    stints.sort(key=lambda s: s.get("stint_number") or 0)
    stint = next((s for s in stints if s.get("stint_number") == stint_number), None)
    if not stint or stint.get("lap_start") is None:
        raise OpenF1Error("stint not found")
    compound = (stint.get("compound") or "").upper()
    if compound not in ("SOFT", "MEDIUM", "HARD"):
        raise OpenF1Error(f"compound '{compound}' is outside what the model was trained on")
    lap_start = stint["lap_start"]
    lap_end = stint.get("lap_end") or max((l.get("lap_number") or 0) for l in driver_laps(session_key, driver_number))
    last_stint = stint is stints[-1]

    total_laps = max((s.get("lap_end") or 0) for s in data["stints"]) or None
    bad = flagged_laps(data["control"], driver_number)
    near = pits_nearby_by_lap(data["stints"], driver_number)

    wx = sorted(((_ts(w.get("date")), w) for w in data["weather"] if _ts(w.get("date"))), key=lambda x: x[0])
    wx_t = [t for t, _ in wx]
    pos = sorted(((_ts(p.get("date")), p.get("position")) for p in driver_positions(session_key, driver_number)
                  if _ts(p.get("date"))), key=lambda x: x[0])
    pos_t = [t for t, _ in pos]

    laps, weather, position, pits = [], {}, {}, {}
    for l in driver_laps(session_key, driver_number):
        n = l.get("lap_number")
        if n is None or n < lap_start or n > lap_end:
            continue
        skip = bad.get(n)
        if l.get("is_pit_out_lap"):
            skip = skip or "pit out lap"
        if n == lap_end and not last_stint:
            skip = skip or "pit in lap"
        laps.append({"lap_number": n, "lap_time_s": l.get("lap_duration"), "skip": skip})
        t = _ts(l.get("date_start"))
        if t is not None:
            if wx:
                w = wx[max(0, min(bisect_right(wx_t, t) - 1, len(wx) - 1))][1]
                weather[n] = {"AirTemp": w.get("air_temperature"), "TrackTemp": w.get("track_temperature"),
                              "Humidity": w.get("humidity"), "WindSpeed": w.get("wind_speed")}
            if pos:
                position[n] = pos[max(0, min(bisect_right(pos_t, t) - 1, len(pos) - 1))][1]
        pits[n] = near(n)

    wet = any((w.get("rainfall") or 0) for w in data["weather"])
    age0 = stint.get("tyre_age_at_start") or 0
    return {"laps": laps, "compound": compound, "total_laps": total_laps, "start_tyre_life": age0 + 1,
            "fresh_tyre": age0 == 0, "weather": weather, "position": position, "pits_nearby": pits,
            "wet": wet, "stint_laps": lap_end - lap_start + 1}
