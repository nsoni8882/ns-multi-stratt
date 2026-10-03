"""Merge facts the scanner cannot know into the health record it just wrote.

`scanner.run` writes `health.json` from inside the scan, so it knows about fetch failures and
strategies that threw -- but not whether the test suites passed, which only the workflow can
see. Rather than let that live in the CI log alone, the workflow folds the outcomes in here
before the site is built, so a deploy carries the verdict on the code that produced it.

Usage (from .github/workflows/scan.yml):
    python -m scanner.health web/public/data/health.json --event schedule \\
        --test python=success --test web=failure
"""
import argparse
import json
import sys
from pathlib import Path

# What GitHub reports in `steps.<id>.outcome` when a step was not reached at all.
SKIPPED = {"skipped", ""}


def merge(path: Path, event: str, tests: "dict[str, str]") -> dict:
    """Fold test outcomes into an existing health.json. Returns the merged record.

    A missing file is not an error: the scan may have aborted before writing one, and the
    caller still wants the outcomes recorded rather than lost.
    """
    health = json.loads(path.read_text()) if path.exists() else {}
    health["event"] = event
    health["tests"] = {
        name: ("not run" if outcome in SKIPPED else outcome) for name, outcome in tests.items()
    }
    # The one combination worth naming: data published from code whose tests fail. Scheduled
    # runs do not block on tests, deliberately, so this is reachable and silent otherwise.
    health["published_with_failing_tests"] = any(
        outcome == "failure" for outcome in health["tests"].values()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(health, indent=1, sort_keys=True) + "\n")
    return health


def _pair(arg: str) -> "tuple[str, str]":
    name, _, outcome = arg.partition("=")
    if not name or not _:
        raise argparse.ArgumentTypeError(f"expected name=outcome, got {arg!r}")
    return name, outcome


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("path", type=Path)
    p.add_argument("--event", default="unknown", help="the GitHub event that triggered the run")
    p.add_argument("--test", type=_pair, action="append", default=[],
                   help="name=outcome, repeatable (outcome as GitHub reports it)")
    args = p.parse_args()
    health = merge(args.path, args.event, dict(args.test))
    print(json.dumps(health.get("tests", {}), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
