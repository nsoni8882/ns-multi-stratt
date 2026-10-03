import json

from scanner.ledger import append, row

ENV = {
    "GITHUB_RUN_ID": "123", "GITHUB_SERVER_URL": "https://github.com",
    "GITHUB_REPOSITORY": "o/r", "GITHUB_EVENT_NAME": "schedule",
    "GITHUB_SHA": "0123456789abcdef0123",
}


def test_row_links_back_to_the_run_that_produced_it():
    r = row(ENV, gate="success", gate_run="true", scan="failure")
    assert r["url"] == "https://github.com/o/r/actions/runs/123"
    assert r["sha"] == "0123456789ab"  # short, like git log
    assert (r["gate"], r["gate_said_run"], r["scan"]) == ("success", "true", "failure")


def test_a_skipped_run_is_recorded_too(tmp_path):
    """The calendar gate deciding not to scan is a normal outcome, and the ledger should show
    it -- otherwise a quiet week is indistinguishable from a broken schedule."""
    path = tmp_path / "runs.jsonl"
    append(path, row(ENV, "success", "false", "skipped"))
    written = json.loads(path.read_text().strip())
    assert written["gate_said_run"] == "false" and written["scan"] == "skipped"


def test_rows_accumulate_newest_last(tmp_path):
    path = tmp_path / "runs.jsonl"
    for i in range(3):
        append(path, row(ENV | {"GITHUB_RUN_ID": str(i)}, "success", "true", "success"))
    ids = [json.loads(line)["run_id"] for line in path.read_text().splitlines()]
    assert ids == ["0", "1", "2"]


def test_the_ledger_is_trimmed_to_the_last_n(tmp_path):
    path = tmp_path / "runs.jsonl"
    for i in range(10):
        total = append(path, row(ENV | {"GITHUB_RUN_ID": str(i)}, "success", "true", "success"), keep=4)
    assert total == 4
    ids = [json.loads(line)["run_id"] for line in path.read_text().splitlines()]
    assert ids == ["6", "7", "8", "9"]


def test_a_blank_line_in_the_file_is_not_counted_as_a_run(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text("\n\n")
    assert append(path, row(ENV, "success", "true", "success")) == 1
