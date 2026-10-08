"""OpenF1 routes with the external API mocked, so they run offline (US-07)."""
import pytest
import openf1

SK, DRV = 9999, 1


@pytest.fixture
def fake_openf1(monkeypatch):
    monkeypatch.setattr(openf1, "sessions", lambda year: [{"session_key": SK, "country": "Testland", "circuit": "T", "date": "2024-03-02"}])
    monkeypatch.setattr(openf1, "drivers", lambda k: [{"number": DRV, "code": "TST", "name": "Test Driver", "team": "T"}])
    stints = [
        {"driver_number": DRV, "stint_number": 1, "lap_start": 1, "lap_end": 14, "compound": "SOFT", "tyre_age_at_start": 0},
        {"driver_number": DRV, "stint_number": 2, "lap_start": 15, "lap_end": 30, "compound": "HARD", "tyre_age_at_start": 0},
        {"driver_number": 2, "stint_number": 2, "lap_start": 8, "lap_end": 30, "compound": "HARD", "tyre_age_at_start": 0},
    ]
    state = {"control": [], "rain": 0}
    monkeypatch.setattr(openf1, "race_data", lambda k: {
        "stints": stints, "control": state["control"],
        "weather": [{"date": "2024-03-02T15:00:00", "air_temperature": 25, "track_temperature": 40,
                     "humidity": 50, "wind_speed": 1, "rainfall": state["rain"]}]})
    monkeypatch.setattr(openf1, "driver_laps", lambda k, d: [
        {"lap_number": n, "lap_duration": 90 + 0.05 * n + (0.6 if 9 <= n <= 14 else 0),
         "is_pit_out_lap": n == 15, "date_start": "2024-03-02T15:10:00"} for n in range(1, 31)])
    monkeypatch.setattr(openf1, "driver_positions", lambda k, d: [{"date": "2024-03-02T15:00:00", "position": 4}])
    return state


@pytest.mark.story("US-07")
def test_picker_endpoints(client, fake_openf1):
    assert client.get("/api/v1/live/sessions?year=2024").json()[0]["session_key"] == SK
    assert client.get(f"/api/v1/live/sessions/{SK}/drivers").json()[0]["code"] == "TST"
    st = client.get(f"/api/v1/live/sessions/{SK}/drivers/{DRV}/stints").json()
    assert [s["compound"] for s in st] == ["SOFT", "HARD"]


@pytest.mark.story("US-07")
def test_score_applies_training_cleaning_rules(client, fake_openf1):
    r = client.get("/api/v1/live/score", params={"session_key": SK, "driver_number": DRV, "stint": 1})
    assert r.status_code == 200
    out = r.json()
    reasons = {d["lap"]: d["reason"] for d in out["dropped"]}
    assert reasons[1] == "lap 1"
    assert reasons[14] == "pit in lap"
    assert out["source"] == "OpenF1" and out["compound"] == "SOFT"
    assert all(0 <= l["risk"] <= 1 for l in out["laps"])


@pytest.mark.story("US-07")
def test_pit_out_lap_dropped_on_second_stint(client, fake_openf1):
    out = client.get("/api/v1/live/score", params={"session_key": SK, "driver_number": DRV, "stint": 2}).json()
    assert {d["lap"]: d["reason"] for d in out["dropped"]}[15] == "pit out lap"


@pytest.mark.story("US-07")
def test_safety_car_laps_are_dropped(client, fake_openf1):
    fake_openf1["control"].extend([
        {"date": "1", "category": "SafetyCar", "lap_number": 5, "message": "SAFETY CAR DEPLOYED"},
        {"date": "2", "category": "SafetyCar", "lap_number": 7, "message": "SAFETY CAR IN THIS LAP"}])
    out = client.get("/api/v1/live/score", params={"session_key": SK, "driver_number": DRV, "stint": 1}).json()
    assert {5, 6, 7} <= {d["lap"] for d in out["dropped"]}


@pytest.mark.story("US-07")
def test_wet_session_returns_a_warning(client, fake_openf1):
    fake_openf1["rain"] = 1
    out = client.get("/api/v1/live/score", params={"session_key": SK, "driver_number": DRV, "stint": 1}).json()
    assert any("dry" in w.lower() for w in out["warnings"])


@pytest.mark.story("US-07")
def test_unknown_stint_is_a_clean_502(client, fake_openf1):
    r = client.get("/api/v1/live/score", params={"session_key": SK, "driver_number": DRV, "stint": 9})
    assert r.status_code == 502 and "detail" in r.json()


@pytest.mark.story("US-07")
def test_openf1_outage_becomes_502_not_500(client, monkeypatch):
    def boom(*a, **k):
        raise openf1.OpenF1Error("OpenF1 unreachable")
    monkeypatch.setattr(openf1, "sessions", boom)
    r = client.get("/api/v1/live/sessions?year=2024")
    assert r.status_code == 502 and "unreachable" in r.json()["detail"]


@pytest.mark.story("US-07")
@pytest.mark.parametrize("year", [2022, 2031])
def test_year_out_of_range_is_422(client, year):
    assert client.get(f"/api/v1/live/sessions?year={year}").status_code == 422


@pytest.mark.live
@pytest.mark.story("US-07")
def test_real_openf1_smoke(client):
    r = client.get("/api/v1/live/sessions?year=2024")
    assert r.status_code == 200 and len(r.json()) >= 20
