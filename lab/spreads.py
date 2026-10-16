"""Measure what crossing the spread really costs, so lab/config.py's cost model rests on a
number. Samples one-minute windows of SIP quotes for a stratified set of symbols at three times
of day on recent sessions, and reports the median half-spread in bps by liquidity tier.

COST_BPS_PER_SIDE is half-spread plus slippage; this measures only the half-spread, so it
bounds the model from below. It changes no verdict by itself: calibrating the model is a
separate, owner-approved edit to config.py with a HISTORY entry.
"""
import statistics
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from trader.alpaca import AlpacaError

ET = ZoneInfo("America/New_York")
TIMES = ((10, 0), (12, 30), (15, 0))  # ET, one-minute windows
MAX_SANE_BPS = 500  # a crossed or stale quote, not a spread


def half_spread_bps(quotes: "list[dict]") -> "list[float]":
    out = []
    for q in quotes:
        bid, ask = q.get("bp") or 0, q.get("ap") or 0
        if bid > 0 and ask > bid:
            spread = (ask - bid) / ((ask + bid) / 2) * 1e4
            if spread <= MAX_SANE_BPS:
                out.append(spread / 2)
    return out


def stratify(ranked: "list[str]", mega: int, others: int) -> "dict[str, list[str]]":
    """The top `mega` names, plus `others` spread evenly across the rest."""
    rest = ranked[mega:]
    step = max(1, len(rest) // max(others, 1))
    return {"mega": ranked[:mega], "large": rest[::step][:others]}


def sample(client, tiers: "dict[str, list[str]]", sessions: "list[str]") -> "list[dict]":
    rows, rejected = [], set()
    for tier, symbols in tiers.items():
        for symbol in symbols:
            for day in sessions:
                if symbol in rejected:
                    break
                for hour, minute in TIMES:
                    start = datetime.fromisoformat(f"{day}T{hour:02d}:{minute:02d}:00").replace(tzinfo=ET)
                    try:
                        q = client.quotes(symbol, start.astimezone(timezone.utc),
                                          (start + timedelta(minutes=1)).astimezone(timezone.utc))
                    except AlpacaError as e:
                        if e.status != 400:  # a symbol Alpaca will not quote is skipped, anything else is real
                            raise
                        rejected.add(symbol)
                        break
                    spreads = half_spread_bps(q)
                    if spreads:
                        rows.append({"tier": tier, "symbol": symbol, "day": day, "time": f"{hour}:{minute:02d}",
                                     "half_spread_bps": statistics.median(spreads), "quotes": len(spreads)})
    return rows


def summarize(rows: "list[dict]") -> dict:
    def stats(xs):
        xs = sorted(xs)
        return {"median": statistics.median(xs), "p25": xs[len(xs) // 4], "p75": xs[(3 * len(xs)) // 4],
                "samples": len(xs)}
    out = {"by_tier": {}, "by_time": {}}
    for tier in sorted({r["tier"] for r in rows}):
        out["by_tier"][tier] = stats([r["half_spread_bps"] for r in rows if r["tier"] == tier])
    for t in sorted({r["time"] for r in rows}, key=lambda s: tuple(map(int, s.split(":")))):
        out["by_time"][t] = stats([r["half_spread_bps"] for r in rows if r["time"] == t])
    return out
