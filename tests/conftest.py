import pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    import api
    return TestClient(api.app)


@pytest.fixture(scope="session")
def table():
    import pandas as pd
    return pd.read_csv(ROOT / "data" / "model_table.csv")


@pytest.fixture(scope="session")
def sample_stint(table):
    """A real stint (race, driver, stint number, rows) with at least 12 laps."""
    need = {"RaceId", "Driver", "Stint", "LapNumber"}
    if not need.issubset(table.columns):
        pytest.skip(f"model_table.csv is missing {need - set(table.columns)}")
    sizes = table.groupby(["RaceId", "Driver", "Stint"]).size()
    race, driver, stint = sizes[sizes >= 12].index[0]
    rows = table[(table.RaceId == race) & (table.Driver.astype(str) == str(driver)) & (table.Stint == stint)]
    return str(race), str(driver), int(stint), rows.sort_values("LapNumber")


def risks_in(obj):
    """Collect every number stored under a key that looks like a risk or probability."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and ("risk" in k.lower() or "prob" in k.lower()):
                out.append(float(v))
            else:
                out += risks_in(v)
    elif isinstance(obj, list):
        for v in obj:
            out += risks_in(v)
    return out
