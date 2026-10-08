"""Model and data sanity tests (US-05). These catch silent breakage after a retrain."""
import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.story("US-05")
def test_no_missing_values_in_label_or_core_features(table):
    for col in ("TyreLife", "DeltaSoFar", "Delta3", "Slope3", "CliffSoon"):
        if col in table.columns:
            assert table[col].notna().all(), col


@pytest.mark.story("US-05")
def test_label_is_binary_with_realistic_rate(table):
    assert set(table["CliffSoon"].unique()) <= {0, 1}
    rate = table["CliffSoon"].mean()
    assert 0.10 < rate < 0.25, f"positive rate {rate:.3f} is far from the expected 16.5%"


@pytest.mark.story("US-05")
def test_sixty_dry_races_and_stints_long_enough(table):
    assert table["RaceId"].nunique() == 60
    assert table.groupby(["RaceId", "Driver", "Stint"]).size().min() >= 1


@pytest.mark.story("US-05")
def test_no_post_cliff_rows_leaked_into_training(table):
    if "LapsToCliff" in table.columns:
        assert (table["LapsToCliff"].dropna() > 0).all()


@pytest.mark.story("US-05")
def test_model_meta_matches_predict_features():
    meta = json.loads((ROOT / "model" / "meta.json").read_text())
    feats = meta["features"]
    assert len(feats) == len(set(feats))
    for must in ("TyreLife", "DeltaSoFar", "Delta3", "Slope3"):
        assert must in feats
    for banned in ("FuelCorrected", "LapNumber", "CliffSoon", "LapsToCliff"):
        assert banned not in feats, f"{banned} would leak or identify the track"


@pytest.mark.story("US-05")
def test_cliff_probability_basic_behaviour():
    from predict import cliff_probability
    fresh = cliff_probability({"TyreLife": 3, "Compound": "MEDIUM", "DeltaSoFar": 0.0, "Delta3": 0.0, "Slope3": 0.0})
    worn = cliff_probability({"TyreLife": 22, "Compound": "MEDIUM", "DeltaSoFar": 0.6, "Delta3": 0.5, "Slope3": 0.1})
    assert 0 <= fresh <= 1 and 0 <= worn <= 1
    assert worn > fresh


@pytest.mark.story("US-05")
def test_missing_inputs_fall_back_to_medians():
    from predict import cliff_probability
    assert 0 <= cliff_probability({"TyreLife": 10, "Compound": "HARD"}) <= 1
