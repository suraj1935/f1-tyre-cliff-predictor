"""
Pull lap-level race data from FastF1, one CSV per race.
Run test first:  python extract_data.py --years 2023
Then everything: python extract_data.py --years 2022 2023 2024 2025
Safe to stop and re-run. Races already saved are skipped.
"""
import argparse
from pathlib import Path

import fastf1
import pandas as pd

RAW_DIR = Path("data/raw")
CACHE_DIR = Path("cache")

LAP_COLS = [
    "Driver", "Team", "LapNumber", "Stint", "Compound", "TyreLife",
    "FreshTyre", "LapTime", "PitInTime", "PitOutTime", "TrackStatus",
    "IsAccurate", "Position",
]
WEATHER_COLS = ["AirTemp", "TrackTemp", "Humidity", "Rainfall", "WindSpeed"]


def extract_race(year: int, rnd: int, event_name: str) -> pd.DataFrame:
    session = fastf1.get_session(year, rnd, "R")
    # We only need lap-level data, so skip telemetry. This keeps it fast.
    session.load(laps=True, weather=True, telemetry=False, messages=False)

    laps = session.laps
    keep = [c for c in LAP_COLS if c in laps.columns]
    df = laps[keep].copy().reset_index(drop=True)

    # Weather at the time of each lap
    weather = laps.get_weather_data().reset_index(drop=True)
    for col in WEATHER_COLS:
        if col in weather.columns:
            df[col] = weather[col]

    df["LapTimeSeconds"] = df["LapTime"].dt.total_seconds()
    df["IsPitLap"] = df["PitInTime"].notna() | df["PitOutTime"].notna()
    df["TotalLaps"] = int(df["LapNumber"].max())
    df["Year"] = year
    df["Round"] = rnd
    df["Event"] = event_name
    df["RaceId"] = f"{year}_{rnd:02d}"

    # Drop the raw timedelta columns, we have seconds now
    return df.drop(columns=["LapTime", "PitInTime", "PitOutTime"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, default=[2023])
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    for year in args.years:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        for _, ev in schedule.iterrows():
            rnd = int(ev["RoundNumber"])
            out = RAW_DIR / f"{year}_{rnd:02d}.csv"
            if out.exists():
                print(f"skip  {year} R{rnd:02d}")
                continue
            try:
                df = extract_race(year, rnd, ev["EventName"])
                df.to_csv(out, index=False)
                print(f"saved {year} R{rnd:02d} {ev['EventName']} ({len(df)} laps)")
            except Exception as e:
                # Future races or missing data will land here. Just move on.
                print(f"FAIL  {year} R{rnd:02d} {ev['EventName']}: {e}")

    files = sorted(RAW_DIR.glob("*.csv"))
    if files:
        all_laps = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
        all_laps.to_csv("data/all_laps.csv", index=False)
        print(f"\nCombined: {len(all_laps)} laps from {len(files)} races -> data/all_laps.csv")


if __name__ == "__main__":
    main()
