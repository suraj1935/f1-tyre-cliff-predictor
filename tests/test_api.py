"""Backend API tests for the dataset routes (US-01 to US-04)."""
import pytest
from conftest import risks_in

pytestmark = []


@pytest.mark.story("US-01")
def test_health_reports_dataset_size(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["races"] == 60
    assert body["rows"] > 30000


@pytest.mark.story("US-01")
def test_v1_alias_matches_unversioned(client):
    a, b = client.get("/api/health"), client.get("/api/v1/health")
    assert a.json() == b.json()
    assert b.headers.get("X-API-Version") == "1"


@pytest.mark.story("US-01")
def test_races_lists_all_sixty(client):
    r = client.get("/api/races")
    assert r.status_code == 200
    assert len(r.json()) == 60


@pytest.mark.story("US-01")
def test_drivers_and_stints_for_a_real_race(client, sample_stint):
    race, driver, stint, _ = sample_stint
    drivers = client.get(f"/api/races/{race}/drivers")
    assert drivers.status_code == 200 and len(drivers.json()) >= 10
    stints = client.get(f"/api/races/{race}/drivers/{driver}/stints")
    assert stints.status_code == 200 and len(stints.json()) >= 1


@pytest.mark.story("US-01")
def test_unknown_race_is_404(client):
    assert client.get("/api/races/1999_99/drivers").status_code == 404


@pytest.mark.story("US-02")
def test_predict_returns_alert_fields_and_valid_risks(client, sample_stint):
    race, driver, stint, _ = sample_stint
    r = client.get("/api/predict", params={"race": race, "driver": driver, "stint": stint, "threshold": 0.5})
    assert r.status_code == 200
    body = r.json()
    for key in ("alert_age", "cliff_age", "lead_laps"):
        assert key in body
    risks = risks_in(body)
    assert risks, "no per-lap risk values found in the response"
    assert all(0.0 <= x <= 1.0 for x in risks)


@pytest.mark.story("US-02")
def test_lower_threshold_never_alerts_later(client, sample_stint):
    race, driver, stint, _ = sample_stint
    def alert(th):
        b = client.get("/api/predict", params={"race": race, "driver": driver, "stint": stint, "threshold": th}).json()
        return b["alert_age"]
    low, high = alert(0.2), alert(0.8)
    if low is not None and high is not None:
        assert low <= high
    if low is None:
        assert high is None


@pytest.mark.story("US-02")
@pytest.mark.parametrize("th", [-0.1, 1.5])
def test_predict_rejects_bad_threshold(client, sample_stint, th):
    race, driver, stint, _ = sample_stint
    r = client.get("/api/predict", params={"race": race, "driver": driver, "stint": stint, "threshold": th})
    assert r.status_code == 422


@pytest.mark.story("US-02")
def test_predict_unknown_stint_is_404(client, sample_stint):
    race, driver, _, _ = sample_stint
    assert client.get("/api/predict", params={"race": race, "driver": driver, "stint": 99}).status_code == 404


@pytest.mark.story("US-03")
def test_whatif_returns_probability(client):
    r = client.post("/api/whatif", json={"Compound": "SOFT", "TyreLife": 15})
    assert r.status_code == 200
    risks = risks_in(r.json())
    assert risks and 0.0 <= risks[0] <= 1.0


@pytest.mark.story("US-03")
@pytest.mark.parametrize("body", [
    {"Compound": "SOFT", "TyreLife": 0},
    {"Compound": "SOFT", "TyreLife": 200},
    {"Compound": "INTERMEDIATE", "TyreLife": 10},
])
def test_whatif_rejects_invalid_input(client, body):
    assert client.post("/api/whatif", json=body).status_code == 422


@pytest.mark.story("US-03")
def test_whatif_more_pace_loss_raises_risk(client):
    def p(delta):
        b = {"Compound": "MEDIUM", "TyreLife": 15, "DeltaSoFar": delta, "Delta3": delta, "Slope3": 0.05}
        return risks_in(client.post("/api/whatif", json=b).json())[0]
    assert p(0.8) > p(0.0)


@pytest.mark.story("US-03")
@pytest.mark.xfail(reason="BUG-01: risk falls at high tyre age and large pace loss (survivorship in training data)", strict=False)
def test_whatif_risk_does_not_fall_as_tyres_age(client):
    def p(age):
        b = {"Compound": "MEDIUM", "TyreLife": age, "DeltaSoFar": 0.3, "Delta3": 0.3, "Slope3": 0.05}
        return risks_in(client.post("/api/whatif", json=b).json())[0]
    assert p(30) >= p(10)


@pytest.mark.story("US-04")
def test_model_card_is_served(client):
    r = client.get("/api/model-card")
    assert r.status_code == 200 and isinstance(r.json(), dict) and r.json()


def test_frontend_is_served_from_root(client):
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


@pytest.mark.story("US-03")
def test_whatif_without_compound_uses_a_default(client):
    r = client.post("/api/whatif", json={"TyreLife": 10})
    assert r.status_code == 200
    assert 0.0 <= risks_in(r.json())[0] <= 1.0
