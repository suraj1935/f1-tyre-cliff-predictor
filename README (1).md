# F1 Tyre Cliff Predictor

Predicts whether a Formula 1 tyre is about to fall off a cliff, meaning a sudden and lasting loss of pace, within the next 5 laps. The app shows the predicted risk lap by lap for a stint and marks the lap where an alert would have fired against the lap where the cliff really arrived.

**Problem.** Tyre wear is usually judged by feel and by tyre age alone. Tyre age is a weak signal: it scores PR-AUC 0.182 here, barely above random guessing at 0.165. The question is how much earlier warning recent pace gives.

**For whom.** Strategy analysts who want to see the warning lap by lap, and reviewers who want an honest model card and a pipeline they can rerun.

## Results

Out-of-fold PR-AUC from 5-fold cross-validation grouped by race, so every race is scored by a model that never saw it. The target is positive on about 16.5% of laps.

| Model | PR-AUC |
|---|---|
| Random guessing | 0.165 |
| Tyre age only | 0.182 |
| XGBoost without pace features | 0.277 |
| Logistic regression | 0.305 |
| **XGBoost, all features** | **0.412** |

**How to read this.** PR-AUC is the primary metric because the cliff is the rare class. Without the pace features, the model (tyre age, compound, race progress, position, weather and pit activity) reaches 0.277. Adding three features built from recent lap times (`DeltaSoFar`, `Delta3`, `Slope3`) lifts the score to 0.412, so most of the signal is in how the car's pace has been changing, not in how old the tyre is. The scores are printed by `train_model.py` and copied into `api.py` for the `/api/model-card` route, so rerun the training script after any change and update them.

## Data

Lap data comes from [FastF1](https://docs.fastf1.dev/) through `extract_data.py`. The modelling table has 35,113 laps from 60 dry races.

`prepare_data.py` cleans the laps and logs how many each step drops:

1. Wet races (any rainfall) are dropped.
2. Only SOFT, MEDIUM and HARD compounds are kept.
3. Laps with a missing lap time or tyre age are dropped.
4. Lap 1 and pit in and out laps are dropped.
5. Only green-flag laps are kept (track status 1), so safety car and yellow flag laps are out.
6. Laps flagged inaccurate are dropped, except for driver-races where the flag failed for every lap.
7. Lap times are fuel corrected.

## How the cliff is defined

`build_features.py` holds the decisions in one place:

| Setting | Value | Meaning |
|---|---|---|
| `CLIFF_THRESHOLD` | 1.0 s | Pace this much slower than the stint's best smoothed pace |
| `SUSTAIN` | 2 laps | The loss must hold for this many laps in a row |
| `SMOOTH` | 3 laps | Rolling median that stops one bad lap (traffic, lock-up) from counting |
| `MIN_STINT_LAPS` | 10 | Shorter stints are dropped |
| `HORIZON` | 5 laps | The target is 1 if the cliff arrives within the next 5 laps |

The script prints how many stints reach a cliff at 0.7 s, 1.0 s and 1.5 s, so the effect of the threshold choice can be checked.

## Features

Every feature uses only information available at that lap: tyre age and compound, fresh or used tyre, race progress, laps remaining, position, air and track temperature, humidity, wind speed, the three pace features above, and pit stops by other cars in the last 5 laps. `FuelCorrected` is left out on purpose because absolute lap time identifies the track, not the tyre. `LapNumber` is left out because race progress and laps remaining already cover it.

## Model

XGBoost (300 trees, depth 4, learning rate 0.05, class weighting for the rare cliff laps), compared with a logistic regression and the baselines above. `train_model.py` also runs two ablations (without pit-stop features and without pace features) and reports PR-AUC by compound.

## App and API

A FastAPI service with a plain HTML and JavaScript front end.

| Route | What it does |
|---|---|
| `GET /api/races`, `/api/races/{race}/drivers`, `/api/races/{race}/drivers/{driver}/stints` | Browse the 60 stored races |
| `GET /api/predict` | Risk lap by lap for one stint, with `alert_age`, `cliff_age` and `lead_laps` for a chosen threshold |
| `POST /api/whatif` | Risk for a situation you set up by hand |
| `POST /api/score-laps` | Send raw lap times and get risk back |
| `GET /api/live/...` | Score a stint from any 2023 to 2025 race through [OpenF1](https://openf1.org/) |
| `GET /api/model-card` | The scores table above |
| `GET /api/health` | Health check |

## Run it

```bash
pip install -r requirements.txt
uvicorn api:app --reload          # UI at http://127.0.0.1:8000
```

The cleaned table and the trained model are committed, so the app runs without the pipeline. To rebuild everything:

```bash
pip install -r requirements-pipeline.txt
python extract_data.py --years 2023      # add more years for more races
python prepare_data.py
python build_features.py
python train_model.py                    # prints the scores, writes model/ and feature_importance.png
```

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium
pytest -m "not live"      # everything that works offline
pytest -m live            # one real OpenF1 call, needs internet
```

The tests cover the routes, data and model sanity checks (no leakage columns, no rows at or after the cliff), parity between features rebuilt from raw lap times and the training table, the OpenF1 routes with the outside API mocked, and browser tests with Playwright. User stories are in [docs/stories.md](docs/stories.md), tickets are in [docs/tickets.md](docs/tickets.md), and [TESTING.md](TESTING.md) maps tests to stories.

## Known limits

- **What-if risk can fall at high tyre age (BUG-01).** Rows at or after the cliff are removed from training, so the model rarely sees very worn tyres with a positive label. The test for it is marked `xfail` until it is fixed, and the page tells users the panel is a probe, not a forecast.
- **Fuel effect is an assumption.** `prepare_data.py` uses 0.03 s per lap as a placeholder and does not estimate it from the data.
- **`/api/score-laps` only sees lap times.** Weather, position and nearby pit stops fall back to training medians. The OpenF1 route fills them from real data.
- **OpenF1 is an outside dependency.** If it is slow or down, the app returns a readable 502 message instead of crashing.
- **The cliff is a definition, not a measurement.** A different threshold or smoothing window gives different labels, which is why the sensitivity check is printed.
- **Model-card scores are copied by hand** from the last training run into `api.py`.
- **Free hosting sleeps.** On a free Render instance the first request after idle can take about a minute.
