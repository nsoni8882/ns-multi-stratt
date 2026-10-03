import json

import pytest

from scanner.health import merge


def test_merge_keeps_the_scan_facts_and_adds_the_test_outcomes(tmp_path):
    path = tmp_path / "health.json"
    path.write_text(json.dumps({"signals": {"found": 7}, "universe": 503}))
    out = merge(path, "schedule", {"python": "success", "web": "success"})
    assert out["signals"] == {"found": 7} and out["universe"] == 503
    assert out["tests"] == {"python": "success", "web": "success"}
    assert out["event"] == "schedule"
    assert out["published_with_failing_tests"] is False
    assert json.loads(path.read_text()) == out


def test_a_failing_suite_is_called_out(tmp_path):
    path = tmp_path / "health.json"
    path.write_text("{}")
    out = merge(path, "schedule", {"python": "failure", "web": "success"})
    assert out["published_with_failing_tests"] is True


@pytest.mark.parametrize("outcome", ["skipped", ""])
def test_a_step_that_never_ran_is_not_a_pass(tmp_path, outcome):
    path = tmp_path / "health.json"
    path.write_text("{}")
    out = merge(path, "push", {"python": outcome})
    assert out["tests"]["python"] == "not run"
    assert out["published_with_failing_tests"] is False


def test_a_missing_health_file_still_records_the_outcome(tmp_path):
    """The scan can abort before writing one; the verdict on the code should survive that."""
    path = tmp_path / "data" / "health.json"
    out = merge(path, "schedule", {"python": "failure"})
    assert path.exists() and out["published_with_failing_tests"] is True
