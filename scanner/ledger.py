"""Append one line per workflow run to a ledger on the `data` branch.

`health.json` is written from inside a scan, so it only exists for runs that got far enough to
publish. The runs that matter most -- the ones that failed, or that the calendar gate skipped
-- leave nothing behind but an Actions log, and GitHub deletes those after 90 days. This is the
durable record: every run, success or failure, in one append-only file next to `signals.db`.

Usage (from .github/workflows/scan.yml, with the GitHub env vars already set):
    python -m scanner.ledger history/runs.jsonl --gate success --gate-run true --scan failure
"""
import argparse
import json
import os
import sys
from pathlib import Path

KEEP = 500  # runs kept; enough to see a pattern, small enough to stay a readable file


def row(env: "dict[str, str]", gate: str, gate_run: str, scan: str) -> dict:
    run_id = env.get("GITHUB_RUN_ID", "")
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    repo = env.get("GITHUB_REPOSITORY", "")
    return {
        "run_id": run_id,
        "url": f"{server}/{repo}/actions/runs/{run_id}" if run_id else "",
        "event": env.get("GITHUB_EVENT_NAME", ""),
        "sha": env.get("GITHUB_SHA", "")[:12],
        "gate": gate,
        "gate_said_run": gate_run,
        "scan": scan,
    }


def append(path: Path, record: dict, keep: int = KEEP) -> int:
    """Add one row, trim to the last `keep`, and report how many rows the file now holds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text().splitlines() if path.exists() else []
    lines = [line for line in existing if line.strip()][-(keep - 1):]
    lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(lines) + "\n")
    return len(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("path", type=Path)
    p.add_argument("--gate", default="")
    p.add_argument("--gate-run", default="")
    p.add_argument("--scan", default="")
    p.add_argument("--keep", type=int, default=KEEP)
    args = p.parse_args()
    record = row(dict(os.environ), args.gate, args.gate_run, args.scan)
    total = append(args.path, record, args.keep)
    print(f"{json.dumps(record, sort_keys=True)} ({total} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
