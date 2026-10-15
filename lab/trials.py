"""The trial ledger: every strategy ever evaluated, pass or fail. Append-only; the count is
what raises the gate's bar, so an unrecorded trial would be a free look."""
import json
from pathlib import Path

DEFAULT = Path(__file__).parent / "trials.jsonl"


class LedgerError(RuntimeError):
    pass


class Ledger:
    def __init__(self, path: "Path | None" = None):
        self.path = Path(path or DEFAULT)  # looked up at call time so a data dir can be set

    def read(self) -> "list[dict]":
        if not self.path.exists():
            return []
        rows = []
        for n, line in enumerate(self.path.read_text().splitlines(), 1):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                raise LedgerError(f"{self.path}:{n} is not valid JSON; refusing to count trials") from None
        return rows

    def count(self) -> int:
        return len(self.read())

    def has(self, fingerprint: str) -> bool:
        return any(r.get("fingerprint") == fingerprint for r in self.read())

    def holdout_looks(self, window: "str | None" = None) -> int:
        """Looks at the sealed holdout; with `window`, only those at that window."""
        return sum(1 for r in self.read() if r.get("holdout_look")
                   and (window is None or r.get("holdout_window") == window))

    def append(self, rec: dict) -> None:
        self.read()  # validates; a ledger we cannot read is never extended
        with self.path.open("a") as f:
            f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
            f.flush()
