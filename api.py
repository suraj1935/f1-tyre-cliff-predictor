# FastAPI backend. Serves cliff predictions as JSON, plus the static frontend.
# Run from the project folder:  python -m uvicorn api:app --reload
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from live_routes import router as live_router
from predict import cliff_probability

BASE = Path(__file__).parent

STATE_COLS = ["TyreLife", "FreshTyre", "RaceProgress", "LapsRemaining", "Position",
              "AirTemp", "TrackTemp", "Humidity", "WindSpeed",
              "DeltaSoFar", "Delta3", "Slope3", "PitsNearby"]

df = pd.read_csv(BASE / "data" / "model_table.csv", dtype={"Driver": str})
df["FreshTyre"] = df["FreshTyre"].astype(int)
df["Stint"] = df["Stint"].astype(int)

app = FastAPI(title="F1 Tyre Cliff Predictor", version="1.0")


def num(x, nd=3):
    return None if pd.isna(x) else round(float(x), nd)


def text(x):
    return None if pd.isna(x) else str(x)


def stint_rows(race, driver, stint):
    sub = df[(df["RaceId"] == race) & (df["Driver"] == driver) & (df["Stint"] == stint)]
    if sub.empty:
        raise HTTPException(status_code=404, detail="No such stint")
    return sub.sort_values("TyreLife")


@lru_cache(maxsize=1024)
def score_stint(race, driver, stint):
    sub = stint_rows(race, driver, stint)
    probs = []
    for _, r in sub.iterrows():
        state = {c: num(r[c], 6) for c in STATE_COLS}
        state["Compound"] = r["Compound"]
        probs.append(cliff_probability(state))
    return tuple(probs)


@app.get("/api/health")
def health():
    return {"status": "ok", "rows": len(df), "races": int(df["RaceId"].nunique())}


@app.get("/api/races")
def races():
    r = df[["RaceId", "Event"]].drop_duplicates().sort_values("RaceId")
    return [{"id": x.RaceId, "year": int(x.RaceId[:4]), "name": x.Event} for x in r.itertuples()]


@app.get("/api/races/{race_id}/drivers")
def drivers(race_id: str):
    sub = df[df["RaceId"] == race_id]
    if sub.empty:
        raise HTTPException(status_code=404, detail="Unknown race")
    teams = sub.groupby("Driver")["Team"].first().sort_index()
    return [{"code": d, "team": text(t)} for d, t in teams.items()]


@app.get("/api/races/{race_id}/drivers/{driver}/stints")
def stints(race_id: str, driver: str):
    sub = df[(df["RaceId"] == race_id) & (df["Driver"] == driver)]
    if sub.empty:
        raise HTTPException(status_code=404, detail="Unknown driver")
    out = []
    for s, g in sub.groupby("Stint"):
        cliff = g["CliffTyreLife"].iloc[0]
        out.append({"stint": int(s), "compound": g["Compound"].iloc[0], "laps": int(len(g)),
                    "cliff_age": None if pd.isna(cliff) else int(cliff)})
    return out


@app.get("/api/predict")
def predict(race: str, driver: str, stint: int, threshold: float = Query(0.5, ge=0, le=1)):
    sub = stint_rows(race, driver, stint)
    probs = score_stint(race, driver, stint)
    laps, alert_age = [], None
    for r, p in zip(sub.itertuples(), probs):
        if alert_age is None and p >= threshold:
            alert_age = int(r.TyreLife)
        laps.append({"lap": int(r.LapNumber), "age": int(r.TyreLife), "risk": round(p, 4),
                     "delta": num(r.DeltaSoFar), "delta3": num(r.Delta3), "slope": num(r.Slope3)})
    cliff = sub["CliffTyreLife"].iloc[0]
    cliff_age = None if pd.isna(cliff) else int(cliff)
    lead = cliff_age - alert_age if (cliff_age is not None and alert_age is not None) else None
    return {"race": race, "driver": driver, "team": text(sub["Team"].iloc[0]),
            "compound": sub["Compound"].iloc[0], "stint": stint, "threshold": threshold,
            "alert_age": alert_age, "cliff_age": cliff_age, "lead_laps": lead, "laps": laps}


class WhatIf(BaseModel):
    Compound: Literal["SOFT", "MEDIUM", "HARD"] = "MEDIUM"
    TyreLife: float = Field(ge=1, le=80)
    DeltaSoFar: Optional[float] = None
    Delta3: Optional[float] = None
    Slope3: Optional[float] = None
    RaceProgress: Optional[float] = None
    TrackTemp: Optional[float] = None


@app.post("/api/whatif")
def whatif(body: WhatIf):
    # Fields left out fall back to their training medians inside cliff_probability.
    return {"risk": round(cliff_probability(body.model_dump()), 4)}


@app.get("/api/model-card")
def model_card():
    return {
        "rows": int(len(df)),
        "races": int(df["RaceId"].nunique()),
        "positive_rate": round(float(df["CliffSoon"].mean()), 3),
        "horizon_laps": 5,
        # PR-AUC from the last training run, 5-fold CV grouped by race
        "scores": [
            {"name": "Random guessing", "pr_auc": 0.165},
            {"name": "Tyre age only", "pr_auc": 0.182},
            {"name": "XGBoost without pace features", "pr_auc": 0.277},
            {"name": "Logistic regression", "pr_auc": 0.305},
            {"name": "XGBoost, all features", "pr_auc": 0.412},
        ],
    }


app.include_router(live_router, prefix="/api")


@app.middleware("http")
async def v1_alias(request, call_next):
    # /api/v1/x is the same as /api/x, so old and new URLs both work
    p = request.scope["path"]
    if p.startswith("/api/v1/"):
        request.scope["path"] = "/api/" + p[len("/api/v1/"):]
    resp = await call_next(request)
    if p.startswith("/api/"):
        resp.headers["X-API-Version"] = "1"
    return resp


# Must come last, so the /api routes above win.
app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
