"""
Clean the raw lap data and look at first degradation curves.
Input:  data/all_laps.csv  (from extract_data.py)
Output: data/clean_laps.csv, degradation_curves.png
"""
import pandas as pd
import matplotlib.pyplot as plt

# ASSUMPTION: lap time gained per lap as fuel burns off (seconds).
# Placeholder value. Justify it or estimate it from the data before relying on it.
FUEL_EFFECT_S_PER_LAP = 0.03

df = pd.read_csv("data/all_laps.csv", dtype={"TrackStatus": str})
print(f"Start: {len(df)} laps, {df['RaceId'].nunique()} races")


def log(step, before):
    print(f"{step:<45} dropped {before - len(df):>6}  left {len(df)}")


# 1. Drop wet races. Rain changes everything about degradation.
rain_races = df.loc[df["Rainfall"] == True, "RaceId"].unique()
print("Races with rain (dropped):", sorted(rain_races))
n = len(df)
df = df[~df["RaceId"].isin(rain_races)]
log("wet races", n)

# 2. Dry compounds only
n = len(df)
df = df[df["Compound"].isin(["SOFT", "MEDIUM", "HARD"])]
log("non-dry or unknown compound", n)

# 3. Missing lap time or tyre age
n = len(df)
df = df.dropna(subset=["LapTimeSeconds", "TyreLife"])
log("missing lap time / tyre life", n)

# 4. Lap 1 (standing start) and pit in/out laps
n = len(df)
df = df[(df["LapNumber"] > 1) & (~df["IsPitLap"])]
log("lap 1 and pit laps", n)

# 5. Green-flag laps only. TrackStatus '1' means clear track.
n = len(df)
df = df[df["TrackStatus"] == "1"]
log("safety car / yellow flag laps", n)

# 6. IsAccurate, but ignore the flag where the check failed for a whole driver-race
share = df.groupby(["RaceId", "Driver"])["IsAccurate"].transform("mean")
n = len(df)
df = df[df["IsAccurate"] | (share == 0)]
log("inaccurate laps", n)

# 7. Fuel correction. Raw time = base + wear - fuel gain, so add the fuel gain back.
df["FuelCorrected"] = df["LapTimeSeconds"] + FUEL_EFFECT_S_PER_LAP * df["LapNumber"]

# 8. Pace delta against the best lap of the same driver stint (for eyeballing curves)
stint_best = df.groupby(["RaceId", "Driver", "Stint"])["FuelCorrected"].transform("min")
df["DeltaToStintBest"] = df["FuelCorrected"] - stint_best

df.to_csv("data/clean_laps.csv", index=False)

print("\nLaps per compound:")
print(df["Compound"].value_counts())
print("\nStint length (laps) per compound:")
print(df.groupby(["RaceId", "Driver", "Stint", "Compound"]).size()
        .groupby("Compound").describe()[["count", "mean", "50%", "max"]])

# Mean degradation curve by compound. Only show ages with enough laps behind them.
fig, ax = plt.subplots(figsize=(9, 5))
for comp, g in df.groupby("Compound"):
    curve = g.groupby("TyreLife")["DeltaToStintBest"].agg(["mean", "count"])
    curve = curve[curve["count"] >= 30]
    ax.plot(curve.index, curve["mean"], label=comp)
ax.set_xlabel("Tyre age (laps)")
ax.set_ylabel("Pace loss vs stint best (s)")
ax.set_title("Mean degradation by compound, 2023 dry races")
ax.legend()
ax.grid(alpha=0.3)
fig.savefig("degradation_curves.png", dpi=150, bbox_inches="tight")
print("\nSaved data/clean_laps.csv and degradation_curves.png")
