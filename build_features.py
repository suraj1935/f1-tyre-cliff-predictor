"""
Build the modelling table: define the tyre cliff, create the target and the features.
Input:  data/clean_laps.csv, data/all_laps.csv
Output: data/model_table.csv
Run from the project folder:  python build_features.py
"""
import numpy as np
import pandas as pd

# ---- Decisions you own. Change them, rerun, and compare the printed summary. ----
CLIFF_THRESHOLD = 1.0   # seconds slower than the stint's best smoothed pace
SUSTAIN = 2             # laps in a row that must stay above the threshold
SMOOTH = 3              # rolling-median window that removes one-lap spikes
MIN_STINT_LAPS = 10     # stints shorter than this are dropped
HORIZON = 5             # target: does the cliff arrive within the next N laps?
PIT_WINDOW = 5          # nearby pit activity: other cars' stops in the last N laps
# ---------------------------------------------------------------------------------

KEYS = ["RaceId", "Driver", "Stint"]

clean = pd.read_csv("data/clean_laps.csv", dtype={"TrackStatus": str})
allp = pd.read_csv("data/all_laps.csv", dtype={"TrackStatus": str})

for c in ["LapNumber", "Stint", "TyreLife", "TotalLaps"]:
    clean[c] = clean[c].astype(int)

# The raw file can have missing stint or lap values (failed alignment), so drop those first
allp = allp.dropna(subset=["LapNumber", "Stint"]).copy()
allp["LapNumber"] = allp["LapNumber"].astype(int)
allp["Stint"] = allp["Stint"].astype(int)

clean = clean.sort_values(KEYS + ["TyreLife"]).reset_index(drop=True)

# 1. Drop short stints
clean["StintLaps"] = clean.groupby(KEYS)["TyreLife"].transform("size")
clean = clean[clean["StintLaps"] >= MIN_STINT_LAPS].reset_index(drop=True)
g = clean.groupby(KEYS, sort=False)

# 2. Smooth pace so one bad lap (traffic, lock-up) cannot trigger the cliff
clean["Smooth"] = g["FuelCorrected"].transform(
    lambda s: s.rolling(SMOOTH, center=True, min_periods=1).median())
clean["DeltaSmooth"] = clean["Smooth"] - g["Smooth"].transform("min")


# 3. Find the cliff: first lap, after the stint's best, where pace stays above threshold
def find_cliff(stint, threshold):
    d = stint["DeltaSmooth"].to_numpy()
    t = stint["TyreLife"].to_numpy()
    above = d >= threshold
    for i in range(int(d.argmin()), len(d) - SUSTAIN + 1):
        if above[i:i + SUSTAIN].all():
            return t[i]
    return np.nan


def cliff_table(threshold):
    rows = [(*k, find_cliff(s, threshold)) for k, s in clean.groupby(KEYS, sort=False)]
    return pd.DataFrame(rows, columns=KEYS + ["CliffTyreLife"])


# Sensitivity check: how much does the threshold choice matter?
print("Share of stints that reach a cliff, by threshold and compound:")
comp = clean.groupby(KEYS, sort=False)["Compound"].first().reset_index()
for th in [0.7, 1.0, 1.5]:
    ct = cliff_table(th).merge(comp, on=KEYS)
    print(f"  threshold {th}s ->", ct.groupby("Compound")["CliffTyreLife"]
          .apply(lambda s: round(s.notna().mean(), 2)).to_dict())

cliffs = cliff_table(CLIFF_THRESHOLD)
clean = clean.merge(cliffs, on=KEYS, how="left")
g = clean.groupby(KEYS, sort=False)

# 4. Features that only use the past (no leakage from future laps)
clean["BestSoFar"] = g["FuelCorrected"].cummin()
clean["DeltaSoFar"] = clean["FuelCorrected"] - clean["BestSoFar"]
g = clean.groupby(KEYS, sort=False)
clean["Delta3"] = g["DeltaSoFar"].transform(lambda s: s.rolling(3, min_periods=1).mean())
clean["Slope3"] = g["FuelCorrected"].transform(
    lambda s: s.diff().rolling(3, min_periods=1).mean()).fillna(0)
clean["RaceProgress"] = clean["LapNumber"] / clean["TotalLaps"]
clean["LapsRemaining"] = clean["TotalLaps"] - clean["LapNumber"]

# 5. Nearby pit activity: stops by OTHER cars in the last PIT_WINDOW laps.
#    A stop is the first lap of any stint after stint 1.
starts = allp.groupby(KEYS)["LapNumber"].min().reset_index()
events = starts[starts["Stint"] > 1]
pit_near = np.zeros(len(clean), dtype=int)
laps_arr = clean["LapNumber"].to_numpy()
drv_arr = clean["Driver"].to_numpy()
for race, idx in clean.groupby("RaceId").indices.items():
    ev = events[events["RaceId"] == race]
    ev_lap, ev_drv = ev["LapNumber"].to_numpy(), ev["Driver"].to_numpy()
    for j in idx:
        m = (ev_lap >= laps_arr[j] - PIT_WINDOW) & (ev_lap <= laps_arr[j] - 1) & (ev_drv != drv_arr[j])
        pit_near[j] = m.sum()
clean["PitsNearby"] = pit_near

# 6. Target. Predict whether the cliff arrives within the next HORIZON laps.
clean["LapsToCliff"] = clean["CliffTyreLife"] - clean["TyreLife"]
clean["CliffSoon"] = ((clean["LapsToCliff"] > 0) & (clean["LapsToCliff"] <= HORIZON)).astype(int)

# Drop laps at or after the cliff (the decision is made before it)
n0 = len(clean)
clean = clean[~(clean["LapsToCliff"] <= 0)]
# Censoring: if a stint never cliffed, its last HORIZON laps have an unknown label
# (the driver may have pitted just before the cliff). Drop them instead of calling them 0.
stint_max = clean.groupby(KEYS)["TyreLife"].transform("max")
unknown = clean["CliffTyreLife"].isna() & (clean["TyreLife"] > stint_max - HORIZON)
clean = clean[~unknown]
print(f"\nRows after label handling: {len(clean)} (dropped {n0 - len(clean)})")

cols = ["RaceId", "Event", "Driver", "Team", "Stint", "Compound", "LapNumber", "TyreLife",
        "FreshTyre", "TotalLaps", "RaceProgress", "LapsRemaining", "Position",
        "AirTemp", "TrackTemp", "Humidity", "WindSpeed", "FuelCorrected",
        "DeltaSoFar", "Delta3", "Slope3", "PitsNearby",
        "CliffTyreLife", "LapsToCliff", "CliffSoon"]
out = clean[cols].round(3)
out.to_csv("data/model_table.csv", index=False)

print(f"Positive rate (CliffSoon=1): {out['CliffSoon'].mean():.3f}")
print("\nStints reaching a cliff, by compound:")
st = out.groupby(["RaceId", "Driver", "Stint", "Compound"])["CliffTyreLife"].first().reset_index()
print(st.groupby("Compound")["CliffTyreLife"].agg(
    stints="size", reached=lambda s: s.notna().sum(), median_cliff_age="median"))
print("\nSaved data/model_table.csv")
