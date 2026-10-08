# Tickets

Create these as GitHub Issues (Issues tab, New issue) and paste the text. Labels in brackets.

## BUG-01 What-if risk falls at high tyre age and large pace loss [bug, model]
**Seen:** In the What-if panel, moving tyre age up past about 25 laps, or pace loss to a very large value, lowers the risk.
**Expected:** Risk should not fall as tyres age with everything else fixed.
**Likely cause (unconfirmed):** Rows at or after the cliff are removed from training, so the model rarely sees very worn tyres or very large pace loss with a positive label. This is survivorship in the training data.
**Test:** `tests/test_api.py::test_whatif_risk_does_not_fall_as_tyres_age` (marked xfail until fixed).
**To do:** Run the risk-by-tyre-age bucket check on `data/model_table.csv`. If confirmed, either add a monotonic constraint on `TyreLife` in XGBoost or state the limit on the page.
**Status:** Hint text on the page already warns that the panel is a probe, not a forecast.

## TKT-02 Add tyre-age bucket check to the training script [task, model]
Print PR-AUC and mean risk by tyre-age bucket (1-10, 11-20, 21-30, 31+) so BUG-01 can be confirmed or ruled out.

## TKT-03 Score-laps uses medians for weather, position and nearby pit stops [limitation]
`POST /api/score-laps` only receives lap times, so `AirTemp`, `TrackTemp`, `Humidity`, `WindSpeed`, `Position` and `PitsNearby` fall back to training medians. The OpenF1 route fills them from real data. Document this in the README. Optional: accept these as optional fields.

## TKT-04 OpenF1 is an outside dependency [risk]
OpenF1 can be slow, rate-limited or down. The app returns 502 with a readable message and the UI shows it. Verified by `test_openf1_outage_becomes_502_not_500` and `test_live_panel_shows_openf1_failure_to_the_user`. Real-API smoke test: `pytest -m live`.

## TKT-05 Free Render instance sleeps when idle [ops]
First request after idle can take about a minute. Mention it in the README so visitors know to wait.

## Closed
- **TKT-00 OpenF1 vs FastF1 timing difference.** Checked on Bahrain 2024, Albon stint 1: mean absolute risk difference 0.018 between the live route and the stored data. Within expected range.

- **BUG-02 Page scrolled sideways on phones.** The one-column layout below 900 px used `1fr`, which grew to fit the lap table. Fixed with `minmax(0, 1fr)` and `min-width: 0` on the grid children. Covered by `test_no_horizontal_scroll_on_a_phone`.
