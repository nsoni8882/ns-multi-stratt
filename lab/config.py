"""Every number that decides a verdict, in one place, fingerprinted.

Same contract as trader/params.py: `rules_version()` hashes `params()`, and the newest HISTORY
entry must carry that hash, so moving a threshold without saying so fails the build.
The values are written in lab/ACCEPTANCE.md before any result exists. The cost defaults are
conservative placeholders until quoted spreads are measured (see the spec's open items).
"""
import hashlib
import json

from trader.params import Release

TIMEFRAMES = ("5Min", "15Min")

# One-way cost in bps per side (half-spread + slippage) by liquidity tier.
COST_BPS_PER_SIDE = {"mega": 1.5, "large": 3.0}
MEGA_RANK = 10  # the top-N of the frozen universe are "mega"; the rest "large"
UNIVERSE_SIZE = 50

# The gate.
BASE_T = 2.5  # floor for the (day-level) t statistic; raised by the trial count
MIN_TRADES = 400
MIN_DAYS = 150
MIN_YEARS = 2
STRESS_MULT = 2.0  # costs x2 must still leave positive expectancy
# The holdout is a FIXED window, not "the latest six months": a moving window means every look
# sees a different slice, and last quarter's sealed data leaks into development. Rolling it
# forward is a deliberate act: change this date and add a Release entry. Looks are counted per
# window, so a roll starts a fresh allowance.
HOLDOUT_START = "2026-04-15"
MAX_HOLDOUT_LOOKS = 5  # after this many looks the holdout is burned; roll it forward
HOLDOUT_MIN_RATIO = 0.5  # holdout expectancy must be at least this share of development's
MIN_HOLDOUT_TRADES = 30

# The checks the gate runs, in order. A check added or removed changes the fingerprint, so the
# rules cannot change through gate.py alone; test_gate pins gate.py to this list.
GATE_CHECKS = ("min_trades", "min_days", "positive_expectancy", "positive_per_trade", "deflated_t",
               "both_halves", "drop_best_year", "cost_stress", "holdout")

START_EQUITY = 100_000.0


def params() -> dict:
    return {
        "timeframes": list(TIMEFRAMES),
        "cost_bps_per_side": COST_BPS_PER_SIDE,
        "mega_rank": MEGA_RANK,
        "universe_size": UNIVERSE_SIZE,
        "base_t": BASE_T,
        "min_trades": MIN_TRADES,
        "min_days": MIN_DAYS,
        "min_years": MIN_YEARS,
        "stress_mult": STRESS_MULT,
        "holdout_start": HOLDOUT_START,
        "max_holdout_looks": MAX_HOLDOUT_LOOKS,
        "holdout_min_ratio": HOLDOUT_MIN_RATIO,
        "min_holdout_trades": MIN_HOLDOUT_TRADES,
        "gate_checks": list(GATE_CHECKS),
    }


def rules_version() -> str:
    return hashlib.sha256(json.dumps(params(), sort_keys=True).encode()).hexdigest()[:12]


HISTORY = (
    Release("1.2.0", "2026-10-16",
            "A strategy now also has to make money per trade, not only on the average day. A "
            "strategy that won on quiet days and lost on crowded ones used to look positive.",
            fingerprint="4c51616de1d5"),
    Release("1.1.0", "2026-10-15",
            "The hidden recent period is now a fixed window instead of a sliding one, so every "
            "look at it is of the same data and a spent allowance can only be renewed on purpose.",
            fingerprint="c448bbf367b2"),
    Release("1.0.0", "2026-10-15",
            "First version of the lab's bar for a strategy: costs on every trade, a threshold "
            "that rises with every idea tried, and a hidden recent period it must also survive.",
            fingerprint="07cd38731b91"),
)
