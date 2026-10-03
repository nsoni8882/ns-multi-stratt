"""Signal history in SQLite. Rows are inserted once and never modified."""
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    side TEXT NOT NULL,
    fired_at TEXT NOT NULL,
    entry_price REAL NOT NULL,
    details TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE (strategy_id, ticker, timeframe, side, fired_at)
)
"""

# Added after the table shipped, so it is applied as a guarded ALTER rather than folded into
# SCHEMA. Stored so the history can later answer whether the conviction tiers held up live.
# `rules_version` fingerprints the thresholds in force when the row was written, so a change
# to a strategy does not silently blend rule generations in one history table.
MIGRATIONS = (
    "ALTER TABLE signals ADD COLUMN conviction TEXT NOT NULL DEFAULT 'standard'",
    "ALTER TABLE signals ADD COLUMN rules_version TEXT NOT NULL DEFAULT ''",
)


@dataclass(frozen=True)
class SignalRecord:
    strategy_id: str
    ticker: str
    timeframe: str
    side: str
    fired_at: str  # ISO-8601 UTC
    entry_price: float
    details: dict
    recorded_at: str  # ISO-8601 UTC
    conviction: str = "standard"
    rules_version: str = ""


class SignalStore:
    def __init__(self, path: "str | Path"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.execute(SCHEMA)
        for statement in MIGRATIONS:
            try:
                self.conn.execute(statement)
            except sqlite3.OperationalError:
                pass  # already applied
        self.conn.commit()

    def record_signals(self, records: "list[SignalRecord]") -> int:
        """Insert records, ignoring ones already stored. Returns the number inserted."""
        before = self.conn.total_changes
        self.conn.executemany(
            "INSERT OR IGNORE INTO signals "
            "(strategy_id, ticker, timeframe, side, fired_at, entry_price, details, recorded_at, "
            "conviction, rules_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (r.strategy_id, r.ticker, r.timeframe, r.side, r.fired_at, r.entry_price,
                 json.dumps(r.details, sort_keys=True), r.recorded_at, r.conviction, r.rules_version)
                for r in records
            ],
        )
        self.conn.commit()
        return self.conn.total_changes - before

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
