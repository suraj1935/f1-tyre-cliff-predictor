"""POST /api/score-laps: the raw lap times to features route (US-06)."""
import pytest


def stint(n=12, base=90.0, wear=0.05, step_from=9, step=0.6):
    return [{"lap_number": i, "lap_time_s": base + wear * i + (step if i >= step_from else 0)} for i in range(2, 2 + n)]


def body(**kw):
    b = {"compound": "SOFT", "total_laps": 57, "laps": stint()}
    b.update(kw)
    return b


@pytest.mark.story("US-06")
def test_scores_a_clean_stint(client):
    r = client.post("/api/v1/score-laps", json=body())
    assert r.status_code == 200
    out = r.json()
    assert out["scored_laps"] == 12
    assert all(0 <= l["risk"] <= 1 for l in out["laps"])
    assert [l["tyre_life"] for l in out["laps"]] == list(range(1, 13))


@pytest.mark.story("US-06")
def test_risk_rises_when_pace_falls_off(client):
    laps = client.post("/api/v1/score-laps", json=body()).json()["laps"]
    assert laps[-1]["risk"] > laps[0]["risk"]


@pytest.mark.story("US-06")
def test_marked_and_lap_one_are_dropped_with_reasons(client):
    laps = stint()
    laps.insert(0, {"lap_number": 1, "lap_time_s": 99.0})
    laps[4]["skip"] = "yellow"
    out = client.post("/api/v1/score-laps", json=body(laps=laps)).json()
    reasons = {d["lap"]: d["reason"] for d in out["dropped"]}
    assert reasons[1] == "lap 1" and reasons[laps[4]["lap_number"]] == "yellow"
    assert out["scored_laps"] == len(laps) - 2


@pytest.mark.story("US-06")
def test_missing_lap_time_is_dropped_not_fatal(client):
    laps = stint()
    laps[3]["lap_time_s"] = None
    out = client.post("/api/v1/score-laps", json=body(laps=laps))
    assert out.status_code == 200 and out.json()["scored_laps"] == 11


@pytest.mark.story("US-06")
def test_delta_is_pace_loss_against_stint_best(client):
    out = client.post("/api/v1/score-laps", json=body()).json()["laps"]
    assert min(l["delta"] for l in out) == 0.0
    assert out[-1]["delta"] > 0.5


@pytest.mark.story("US-06")
def test_alert_lap_respects_threshold(client):
    lo = client.post("/api/v1/score-laps?threshold=0.05", json=body()).json()["alert_lap"]
    hi = client.post("/api/v1/score-laps?threshold=0.99", json=body()).json()["alert_lap"]
    assert lo is not None
    assert hi is None or hi >= lo


@pytest.mark.story("US-06")
@pytest.mark.parametrize("bad", [
    {"laps": stint(3)},
    {"compound": "WET"},
    {"laps": [{"lap_number": i, "lap_time_s": 10.0} for i in range(2, 8)]},
    {"laps": [{"lap_number": 0, "lap_time_s": 90.0}] * 5},
    {"total_laps": 3},
])
def test_invalid_bodies_are_422(client, bad):
    assert client.post("/api/v1/score-laps", json=body(**bad)).status_code == 422


@pytest.mark.story("US-06")
def test_threshold_out_of_range_is_422(client):
    assert client.post("/api/v1/score-laps?threshold=2", json=body()).status_code == 422


@pytest.mark.story("US-06")
def test_too_few_usable_laps_after_cleaning_is_422(client):
    laps = [{"lap_number": i, "lap_time_s": 90.0, "skip": "sc"} for i in range(2, 8)]
    assert client.post("/api/v1/score-laps", json=body(laps=laps)).status_code == 422


@pytest.mark.story("US-06")
def test_features_match_the_training_table(client, sample_stint):
    """The server must rebuild DeltaSoFar from raw lap times the way build_features.py did."""
    race, driver, stint_no, rows = sample_stint
    if "FuelCorrected" not in rows.columns:
        pytest.skip("FuelCorrected not in model_table.csv")
    laps = [{"lap_number": int(r.LapNumber), "lap_time_s": float(r.FuelCorrected) - 0.03 * int(r.LapNumber)}
            for r in rows.itertuples()]
    payload = {"compound": str(rows.Compound.iloc[0]), "start_tyre_life": int(rows.TyreLife.iloc[0]),
               "fresh_tyre": bool(rows.FreshTyre.iloc[0]), "laps": laps}
    out = client.post("/api/v1/score-laps", json=payload).json()["laps"]
    assert len(out) == len(rows)
    for got, want in zip(out, rows.DeltaSoFar):
        assert got["delta"] == pytest.approx(float(want), abs=0.01)
