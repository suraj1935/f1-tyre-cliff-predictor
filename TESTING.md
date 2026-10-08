# Testing

## Run it

```
pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium
pytest -m "not live"          # everything that works offline
pytest -m live                # real OpenF1 call, needs internet
pytest tests/ui               # browser tests only
```

## What is covered

| Area | File | Stories |
|------|------|---------|
| Dataset routes (health, races, drivers, stints, predict, what-if, model card) | `tests/test_api.py` | US-01 to US-04 |
| Data and model sanity | `tests/test_model_data.py` | US-05 |
| Raw lap times to features (`/api/score-laps`), including parity with the training table | `tests/test_score_laps.py` | US-06 |
| OpenF1 routes with the outside API mocked | `tests/test_live_openf1.py` | US-07 |
| Browser tests (Playwright) with OpenF1 mocked | `tests/ui/test_ui.py` | US-01, US-02, US-07, US-08 |

User stories are in `docs/stories.md` and tickets in `docs/tickets.md`. To list the tests for one story: `pytest --collect-only -q -m "story"` and search the file for the story ID.

## Known failing test

`test_whatif_risk_does_not_fall_as_tyres_age` is marked `xfail`. It documents BUG-01: the what-if risk drops at high tyre age. It will start passing, and show as XPASS, once the bug is fixed.

## Notes

- The parity test rebuilds `DeltaSoFar` from raw lap times and compares it with the stored training column, so a change in the cleaning or feature code that breaks parity fails the build.
- Browser tests start their own server on a free port and never call OpenF1.
