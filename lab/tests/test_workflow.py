"""The lab workflow's safety properties, pinned. They live in YAML, where nothing else would
catch them being edited away. Same idea as trader/tests/test_workflow.py."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / ".github" / "workflows" / "lab.yml"
SCAN = ROOT / ".github" / "workflows" / "scan.yml"


def load(path):
    doc = yaml.safe_load(path.read_text())
    doc["on"] = doc.pop(True, doc.get("on"))
    return doc


def steps(doc):
    return [s for job in doc["jobs"].values() for s in job["steps"]]


def test_an_experiment_never_runs_by_accident():
    """Each backtest spends a trial. No schedule, no push: only a person starts one."""
    assert set(load(LAB)["on"]) == {"workflow_dispatch"}


def test_it_cannot_deploy_and_cannot_touch_issues():
    perms = load(LAB)["permissions"]
    assert "pages" not in perms and "issues" not in perms
    assert perms == {"contents": "write", "actions": "write"}


def test_runs_cannot_overlap_because_the_ledger_is_append_only():
    c = load(LAB)["concurrency"]
    assert c["group"] == "lab" and c["cancel-in-progress"] is False


def test_tests_gate_the_run_and_precede_it():
    names = [s.get("name", "") for s in steps(load(LAB))]
    test_at = names.index("Test before running")
    assert test_at < names.index("Run")
    gate = steps(load(LAB))[test_at]
    assert "continue-on-error" not in gate


def test_the_ledger_is_saved_even_when_a_later_step_fails():
    save = next(s for s in steps(load(LAB)) if s.get("name") == "Save the ledgers")
    assert save["if"] == "always()"


def test_user_input_reaches_the_shell_only_through_env():
    """`${{ inputs.* }}` inside a run: script is shell injection; it has to come via env."""
    for s in steps(load(LAB)):
        assert "inputs." not in s.get("run", "")


def test_secrets_are_only_given_to_steps_that_call_alpaca():
    holders = [s["name"] for s in steps(load(LAB)) if "ALPACA_KEY_ID" in s.get("env", {})]
    assert holders == ["Run"]


def test_scan_publishes_lab_json_but_the_lab_never_deploys():
    text = SCAN.read_text()
    assert "history/lab/lab.json" in text and "web/public/data/lab.json" in text
    assert "upload-pages-artifact" not in LAB.read_text()
