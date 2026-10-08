from typing import List, Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from live_features import build_stint_rows, score_rows
import openf1

router = APIRouter()


class LapIn(BaseModel):
    lap_number: int = Field(ge=1, le=100)
    lap_time_s: Optional[float] = Field(default=None, gt=30, lt=300)
    skip: Optional[str] = None  # set to any text to mark a pit, SC or yellow lap


class ScoreLaps(BaseModel):
    compound: Literal["SOFT", "MEDIUM", "HARD"]
    total_laps: Optional[int] = Field(default=None, ge=10, le=100)
    start_tyre_life: int = Field(default=1, ge=1, le=60)
    fresh_tyre: bool = True
    position: Optional[int] = Field(default=None, ge=1, le=20)
    laps: List[LapIn] = Field(min_length=4, max_length=100)


def _summarise(scored, dropped, threshold):
    alert = next((r["lap"] for r in scored if r["risk"] >= threshold), None)
    return {"threshold": threshold, "scored_laps": len(scored), "alert_lap": alert,
            "peak_risk": max((r["risk"] for r in scored), default=None),
            "dropped": [{"lap": n, "reason": why} for n, why in dropped], "laps": scored}


@router.post("/score-laps")
def score_laps(body: ScoreLaps, threshold: float = Query(0.5, ge=0, le=1)):
    pos = {l.lap_number: body.position for l in body.laps} if body.position else None
    rows, dropped = build_stint_rows([l.model_dump() for l in body.laps], body.compound, body.total_laps,
                                     body.start_tyre_life, body.fresh_tyre, position=pos)
    if len(rows) < 3:
        raise HTTPException(422, "Fewer than 3 usable laps after cleaning")
    return _summarise(score_rows(rows), dropped, threshold)


def _safe(fn, *a):
    try:
        return fn(*a)
    except openf1.OpenF1Error as e:
        raise HTTPException(502, str(e))


@router.get("/live/sessions")
def live_sessions(year: int = Query(2024, ge=2023, le=2030)):
    return _safe(openf1.sessions, year)


@router.get("/live/sessions/{session_key}/drivers")
def live_drivers(session_key: int):
    return _safe(openf1.drivers, session_key)


@router.get("/live/sessions/{session_key}/drivers/{driver_number}/stints")
def live_stints(session_key: int, driver_number: int):
    data = _safe(openf1.race_data, session_key)
    return [{"stint": s.get("stint_number"), "compound": s.get("compound"), "lap_start": s.get("lap_start"),
             "lap_end": s.get("lap_end")} for s in sorted(data["stints"], key=lambda s: s.get("stint_number") or 0)
            if s.get("driver_number") == driver_number]


@router.get("/live/score")
def live_score(session_key: int, driver_number: int, stint: int, threshold: float = Query(0.5, ge=0, le=1)):
    inp = _safe(openf1.build_inputs, session_key, driver_number, stint)
    rows, dropped = build_stint_rows(inp["laps"], inp["compound"], inp["total_laps"], inp["start_tyre_life"],
                                     inp["fresh_tyre"], inp["weather"], inp["position"], inp["pits_nearby"])
    if len(rows) < 3:
        raise HTTPException(422, "Fewer than 3 usable laps in this stint after cleaning")
    out = _summarise(score_rows(rows), dropped, threshold)
    out.update({"source": "OpenF1", "compound": inp["compound"], "stint_laps": inp["stint_laps"],
                "warnings": (["Rain was recorded in this session. The model was trained on dry races only."] if inp["wet"] else [])
                + (["Stint is shorter than 10 laps, outside the training range."] if inp["stint_laps"] < 10 else [])})
    return out
