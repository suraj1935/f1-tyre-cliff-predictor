# User stories

Each test in `tests/` carries `@pytest.mark.story("US-xx")`, so every story can be traced to the tests that cover it (see `TESTING.md`).

| ID | As a... | I want to... | So that... | Acceptance criteria |
|----|---------|--------------|------------|---------------------|
| US-01 | strategy analyst | browse any of the 60 dry races, pick a driver and a stint | I can look at one tyre stint in detail | Race list has 60 entries. Drivers and stints load for a real race. An unknown race returns 404, not a crash. |
| US-02 | strategy analyst | see the predicted cliff risk lap by lap with an alert line | I can see how many laps of warning the model gave before the real cliff | Risks are between 0 and 1. The response has `alert_age`, `cliff_age` and `lead_laps`. A lower threshold never alerts later. A threshold outside 0 to 1 returns 422. |
| US-03 | curious visitor | set up a race situation and ask the model directly | I can probe how the model reacts | Valid input returns a probability between 0 and 1. Tyre age 0 or 200, or an unknown compound returns 422. A missing compound uses a default. More pace loss raises the risk. |
| US-04 | hiring manager or reviewer | read the model card and honest scores | I can judge the model without reading the code | `/api/model-card` returns the CV scores, including the baselines. |
| US-05 | maintainer | have data and model checks that fail loudly after a retrain | I never ship a model that quietly leaked or broke | Label is binary at about 16.5% positive. 60 races. No rows at or after the cliff. Feature list has no `FuelCorrected` or `LapNumber`. Missing inputs fall back to medians. |
| US-06 | developer using the API | send raw lap times and get risk back | I do not have to compute the features myself | Features rebuilt on the server match the training table. Lap 1 and flagged laps are dropped and reported. Fewer than 4 laps, an unknown compound or an impossible lap time returns 422. |
| US-07 | strategy analyst | score a stint from any 2023 to 2025 race through OpenF1 | I am not limited to the 60 stored races | Training cleaning rules are applied (lap 1, pit in and out laps, safety car and yellow laps). A wet session returns a warning. If OpenF1 is down, the user gets a clear message and a 502, not a 500. |
| US-08 | visitor on a phone | use the page on a small screen | I can open the link from a message | No horizontal scroll at 390 px wide. |

