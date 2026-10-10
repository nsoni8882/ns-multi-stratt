"""The trading workflow's safety properties, pinned.

These are the invariants from the spec that live in YAML rather than in Python, so nothing
else would catch them being edited away. The first is the one that matters most: scan.yml
re-runs on every push to main *by design*, and if this workflow ever gained the same trigger,
merging code would submit orders.
"""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TRADE = ROOT / ".github" / "workflows" / "trade.yml"
SCAN = ROOT / ".github" / "workflows" / "scan.yml"


def load(path):
    doc = yaml.safe_load(path.read_text())
    # PyYAML reads the bare `on:` key as the boolean True.
    doc["on"] = doc.pop(True, doc.get("on"))
    return doc


@pytest.fixture(scope="module")
def trade():
    return load(TRADE)


def test_the_trading_workflow_never_runs_on_push(trade):
    assert "push" not in trade["on"], (
        "trade.yml must not trigger on push: merging code would submit orders"
    )
    assert set(trade["on"]) == {"schedule", "workflow_dispatch"}


def test_it_wakes_up_in_both_daylight_offsets(trade):
    """Cron has no idea about DST, so 15:25 ET needs both. /v2/clock sorts out the rest."""
    assert sorted(c["cron"] for c in trade["on"]["schedule"]) == ["25 19 * * 1-5",
                                                                 "25 20 * * 1-5"]


def test_it_cannot_deploy(trade):
    """Pages belongs to scan.yml alone; two workflows deploying would race."""
    assert "pages" not in trade["permissions"]
    assert trade["permissions"] == {"contents": "write", "issues": "write"}


def test_tests_gate_the_trade_rather_than_being_recorded(trade):
    """scan.yml lets a scheduled run publish with failing tests, deliberately. This one must
    not: it places orders."""
    steps = trade["jobs"]["trade"]["steps"]
    testing = next(s for s in steps if s.get("name") == "Test before trading")
    assert "pytest" in testing["run"]
    assert "continue-on-error" not in testing
    ran = [s.get("name") for s in steps]
    assert ran.index("Test before trading") < ran.index("Decide and trade")


def test_runs_concurrently_with_nothing(trade):
    assert trade["concurrency"]["group"] == "paper-trade"
    assert trade["concurrency"]["cancel-in-progress"] is False


def test_a_failure_opens_an_issue(trade):
    failure = next(s for s in trade["jobs"]["trade"]["steps"]
                   if s.get("name") == "Say so, in an issue")
    assert failure["if"] == "failure()"
    assert "paper-trade-failure" in failure["run"]


def test_the_scan_publishes_the_dashboard_before_it_builds():
    """The trader writes paper-trading.json to the data branch; the scan is what deploys it."""
    steps = load(SCAN)["jobs"]["scan-and-deploy"]["steps"]
    names = [s.get("name", "") for s in steps]
    copy = names.index("Include the paper-trading dashboard, if the trader has written one")
    build = next(i for i, s in enumerate(steps) if s.get("run") == "npm run build")
    assert copy < build, "the file must be copied in before the site is built"
    assert "if [ -f history/paper-trading.json ]" in steps[copy]["run"], (
        "a missing file is normal before the first trading run and must not fail the scan"
    )
