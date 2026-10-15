"""Where each strategy is in its life, and the rules it was told it would be judged by.

proposed -> backtested -> rejected | shadow -> paper -> kept -> retired
Rejected and retired are terminal for a fingerprint. Failure rules are attached on entry to
shadow and are never editable afterwards: the skill may propose a successor spec, not an excuse.
Moving to paper needs a named human; this module cannot approve for you.
"""
import json
import time
from pathlib import Path

DEFAULT = Path(__file__).parent / "registry.json"
ALLOWED = {
    "proposed": {"backtested"}, "backtested": {"rejected", "shadow"},
    "shadow": {"paper", "retired"}, "paper": {"kept", "retired"},
    "kept": {"retired"}, "rejected": set(), "retired": set(),
}
OPS = {"lt": lambda a, b: a < b, "gt": lambda a, b: a > b}


class LifecycleError(ValueError):
    pass


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Registry:
    def __init__(self, path: Path = DEFAULT):
        self.path = Path(path)

    def all(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def get(self, fp: str) -> dict:
        try:
            return self.all()[fp]
        except KeyError:
            raise LifecycleError(f"unknown strategy {fp}") from None

    def _save(self, d: dict) -> None:
        self.path.write_text(json.dumps(d, indent=2, sort_keys=True))

    def register(self, spec) -> str:
        d, fp = self.all(), spec.fingerprint()
        if fp in d:
            raise LifecycleError(f"{fp} is already {d[fp]['stage']}; a fingerprint is tried once")
        d[fp] = {"spec": spec.to_dict(), "stage": "proposed", "failure_rules": None,
                 "approved_by": None,
                 "history": [{"stage": "proposed", "when": _now(), "reason": "registered"}]}
        self._save(d)
        return fp

    def advance(self, fp, to, *, reason, approved_by=None, failure_rules=None) -> None:
        d = self.all()
        entry = d.get(fp)
        if entry is None:
            raise LifecycleError(f"unknown strategy {fp}")
        if to not in ALLOWED[entry["stage"]]:
            raise LifecycleError(f"{entry['stage']} -> {to} is not allowed")
        if failure_rules is not None and entry["failure_rules"] is not None:
            raise LifecycleError("failure rules are frozen")
        if to == "shadow":
            if not failure_rules:
                raise LifecycleError("entering shadow requires pre-registered failure rules")
            entry["failure_rules"] = failure_rules
        if to == "paper":
            if not approved_by:
                raise LifecycleError("moving to paper needs a named human approval")
            entry["approved_by"] = approved_by
        entry["stage"] = to
        entry["history"].append({"stage": to, "when": _now(), "reason": reason})
        self._save(d)

    def apply_failure_rules(self, fp: str, live: dict) -> "list[str]":
        entry = self.get(fp)
        tripped = [f"{r['metric']} {r['op']} {r['threshold']}" for r in entry["failure_rules"] or []
                   if live.get("n_trades", 0) >= r["after_trades"]
                   and OPS[r["op"]](live[r["metric"]], r["threshold"])]
        if tripped:
            self.advance(fp, "retired", reason="failure rule tripped: " + "; ".join(tripped))
        return tripped
