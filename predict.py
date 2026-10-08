# Load the saved model and score a race state.
import json
import pandas as pd
import xgboost as xgb

_booster = xgb.Booster()
_booster.load_model("model/cliff_model.json")
with open("model/meta.json") as f:
    _meta = json.load(f)

FEATURES = _meta["features"]
MEDIANS = _meta["medians"]
COMPOUNDS = ["HARD", "MEDIUM", "SOFT"]


def cliff_probability(state):
    # state is a dict with the same fields used in training:
    # TyreLife, Compound, FreshTyre, RaceProgress, LapsRemaining, Position,
    # AirTemp, TrackTemp, Humidity, WindSpeed, DeltaSoFar, Delta3, Slope3, PitsNearby
    # Any missing field falls back to its training median.
    row = {col: MEDIANS[col] for col in FEATURES}
    for key, value in state.items():
        if key != "Compound" and key in row and value is not None:
            row[key] = value
    for c in COMPOUNDS:
        col = "Compound_" + c
        if col in row:
            row[col] = 1 if state.get("Compound") == c else 0
    X = pd.DataFrame([row])[FEATURES].astype(float)
    return float(_booster.predict(xgb.DMatrix(X))[0])


if __name__ == "__main__":
    fresh = {"TyreLife": 5, "Compound": "MEDIUM", "FreshTyre": 1, "RaceProgress": 0.2,
             "DeltaSoFar": 0.1, "Delta3": 0.05, "Slope3": 0.0}
    worn = {"TyreLife": 22, "Compound": "MEDIUM", "FreshTyre": 0, "RaceProgress": 0.5,
            "DeltaSoFar": 1.1, "Delta3": 0.9, "Slope3": 0.3}
    print("fresh tyres:", round(cliff_probability(fresh), 3))
    print("worn tyres: ", round(cliff_probability(worn), 3))
