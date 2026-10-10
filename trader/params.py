"""Every threshold that can change which order is placed, in one place.

`rules_version()` fingerprints these onto every ledger row and into the published JSON, so a
threshold change splits the live record cleanly instead of blending two rule generations --
the same contract `scanner/strategies/base.py` enforces for the screener.

The fingerprint helpers are reimplemented here rather than imported from the scanner, because
`scanner/strategies/base.py` imports pandas and the live order path must not depend on it.
`trader/tests/test_params.py` cross-checks the two so the contract cannot diverge.
"""
import hashlib
import json
from dataclasses import dataclass

SYMBOLS = ["AMZN", "AAPL"]

RSI_LEN = 2
BUY_BELOW = 10.0
SELL_ABOVE = 65.0
TREND_LEN = 200
MAX_HOLD = 10  # trading sessions, counted off Alpaca's calendar

SLICE_PCT = 0.50  # fraction of *equity* per position; never of buying_power
MAX_CONCURRENT = 2

LOOKBACK_DAYS = 420  # calendar days requested; ~289 sessions, enough for SMA(200)

# When the run is allowed to submit, in minutes before the close. Both are gates -- they
# decide whether an order is placed -- so they live in params() and are fingerprinted, per
# the convention in CLAUDE.md.
#
# The lower bound: Alpaca rejects market-on-close orders after 15:50 ET.
# The upper bound is the one that cost a bug. Cron is in UTC, so 19:25 UTC is 15:25 EDT in
# summer but 14:25 EST in winter -- an open market with 95 minutes still to run. The rule is
# justified on a ~15:25 partial bar, so deciding an hour and a half earlier is a different
# strategy from the backtested one. The winter morning wake-up now stands down instead.
CUTOFF_MINUTES = 10
MAX_MINUTES_TO_CLOSE = 45


@dataclass(frozen=True)
class Release:
    """One entry in the visible change history. Mirrors scanner.strategies.base.Release."""

    version: str
    date: str  # ISO date, YYYY-MM-DD
    summary: str
    fingerprint: str = ""

    def as_dict(self) -> dict:
        return {"version": self.version, "date": self.date, "summary": self.summary}


def params() -> dict:
    """Everything that decides whether an order is placed."""
    return {
        "rsi_len": RSI_LEN,
        "buy_below": BUY_BELOW,
        "sell_above": SELL_ABOVE,
        "trend_len": TREND_LEN,
        "max_hold": MAX_HOLD,
        "slice_pct": SLICE_PCT,
        "max_concurrent": MAX_CONCURRENT,
        "symbols": SYMBOLS,
        "cutoff_minutes": CUTOFF_MINUTES,
        "max_minutes_to_close": MAX_MINUTES_TO_CLOSE,
    }


def rules_version() -> str:
    blob = json.dumps(params(), sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


def current_version(history: "tuple[Release, ...]") -> str:
    """History is newest-first, so the running version is the top entry."""
    return history[0].version if history else "0.0.0"


# Newest first, like the strategies. The top entry's fingerprint is build-asserted in
# trader/tests/test_params.py, so changing a threshold without adding an entry fails.
HISTORY = (
    Release("1.1.0", "2026-10-10",
            "The bot now stands down if it wakes up more than 45 minutes before the close. "
            "Its wake-up times are set in UTC, so through the winter one of them landed an "
            "hour and a half early, and a decision taken that far from the close is not the "
            "one this strategy was tested on.",
            fingerprint="f5e0af26ffd9"),
    Release("1.0.0", "2026-10-10",
            "First version. Buys AMZN or AAPL when RSI(2) falls under 10 while the price "
            "is still above its 200-day average, and sells when RSI(2) recovers past 65 or "
            "ten trading days pass. Half the account per name, no stop, paper money only.",
            fingerprint="512f04ab1a78"),
)
