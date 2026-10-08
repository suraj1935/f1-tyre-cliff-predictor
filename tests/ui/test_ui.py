"""Browser tests. The OpenF1 panel is tested with mocked responses so it never depends on the network."""
import json
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.ui

SESSIONS = [{"session_key": 1, "country": "Testland", "circuit": "T", "date": "2024-03-02"}]
DRIVERS = [{"number": 7, "code": "TST", "name": "Test Driver", "team": "T"}]
STINTS = [{"stint": 1, "compound": "SOFT", "lap_start": 1, "lap_end": 12}]
SCORE = {"source": "OpenF1", "compound": "SOFT", "stint_laps": 12, "scored_laps": 3, "alert_lap": 4, "peak_risk": 0.9,
         "threshold": 0.5, "warnings": [], "dropped": [{"lap": 1, "reason": "lap 1"}],
         "laps": [{"lap": 2, "tyre_life": 2, "lap_time": 90.1, "delta": 0.0, "risk": 0.2},
                  {"lap": 3, "tyre_life": 3, "lap_time": 90.4, "delta": 0.3, "risk": 0.55},
                  {"lap": 4, "tyre_life": 4, "lap_time": 91.0, "delta": 0.9, "risk": 0.9}]}


def mock_openf1(page, score_status=200, score_body=None):
    def fulfil(route, body, status=200):
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body))
    page.route("**/api/v1/live/sessions?*", lambda r: fulfil(r, SESSIONS))
    page.route("**/api/v1/live/sessions/*/drivers", lambda r: fulfil(r, DRIVERS))
    page.route("**/api/v1/live/sessions/*/drivers/*/stints", lambda r: fulfil(r, STINTS))
    page.route("**/api/v1/live/score*", lambda r: fulfil(r, score_body or SCORE, score_status))


@pytest.mark.story("US-01")
def test_page_loads_without_console_errors(page, site):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    mock_openf1(page)
    page.goto(site)
    expect(page).to_have_title(__import__("re").compile("Tyre Cliff", __import__("re").I))
    page.wait_for_load_state("networkidle")
    assert errors == []


@pytest.mark.story("US-01")
def test_race_dropdown_lists_sixty_races(page, site):
    mock_openf1(page)
    page.goto(site)
    page.wait_for_function("[...document.querySelectorAll('select')].some(s => s.options.length === 60)")


@pytest.mark.story("US-02")
def test_changing_threshold_slider_does_not_break_page(page, site):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    mock_openf1(page)
    page.goto(site)
    page.wait_for_function("[...document.querySelectorAll('select')].some(s => s.options.length === 60)")
    slider = page.locator("input[type=range]").first
    slider.fill("0.3")
    page.wait_for_timeout(300)
    assert errors == []


@pytest.mark.story("US-07")
def test_live_panel_scores_a_stint(page, site):
    mock_openf1(page)
    page.goto(site)
    expect(page.locator("#lv-session option")).to_have_count(1)
    expect(page.locator("#lv-driver option")).to_have_count(1)
    expect(page.locator("#lv-stint option")).to_have_count(1)
    page.click("#lv-go")
    expect(page.locator("#lv-rows tr")).to_have_count(3)
    expect(page.locator("#lv-msg")).to_contain_text("First alert on lap 4")
    expect(page.locator("#lv-drop")).to_contain_text("lap 1")


@pytest.mark.story("US-07")
def test_live_panel_shows_openf1_failure_to_the_user(page, site):
    mock_openf1(page, score_status=502, score_body={"detail": "OpenF1 unreachable"})
    page.goto(site)
    expect(page.locator("#lv-stint option")).to_have_count(1)
    page.click("#lv-go")
    expect(page.locator("#lv-msg")).to_contain_text("Scoring failed")
    expect(page.locator("#lv-msg")).to_contain_text("unreachable")


@pytest.mark.story("US-07")
def test_live_panel_warns_about_wet_sessions(page, site):
    body = dict(SCORE, warnings=["Rain was recorded in this session. The model was trained on dry races only."])
    mock_openf1(page, score_body=body)
    page.goto(site)
    expect(page.locator("#lv-stint option")).to_have_count(1)
    page.click("#lv-go")
    expect(page.locator("#lv-msg")).to_contain_text("dry races only")


@pytest.mark.story("US-08")
def test_no_horizontal_scroll_on_a_phone(page, site):
    mock_openf1(page)
    page.set_viewport_size({"width": 390, "height": 800})
    page.goto(site)
    page.wait_for_load_state("networkidle")
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")
