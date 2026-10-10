"""The RSI(2) reversion rule. Pure functions over a list of closes -- no I/O, no broker.

Deliberately a second implementation of what research/ computes with pandas, because the
live path must stay dependency-free. trader/tests/test_rule_matches_backtest.py diffs the
two over real AMZN and AAPL history so they cannot drift apart unnoticed.
"""
from dataclasses import dataclass

from trader import params


@dataclass(frozen=True)
class Decision:
    action: str  # "buy" | "sell" | "hold" | "wait" | "skip"
    reason: str
    rsi2: "float | None" = None
    sma200: "float | None" = None
    price: "float | None" = None
    trend_gap_pct: "float | None" = None


def wilder_rsi(closes, n):
    """Wilder RSI, seeded the same way as pandas ewm(alpha=1/n, adjust=False)."""
    if len(closes) < n + 2:
        return None
    au = ad = 0.0
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        au += (max(d, 0.0) - au) / n
        ad += (max(-d, 0.0) - ad) / n
    if ad == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + au / ad)


def sma(closes, n):
    return sum(closes[-n:]) / n if len(closes) >= n else None


def decide(closes, *, held: bool, bars_held: int) -> Decision:
    """What to do with one symbol, given its closes (last element = today's partial bar).

    `skip` means the inputs cannot support a decision, which is not the same as `wait`:
    an undefined SMA(200) must never read as an open trend gate.
    """
    r = wilder_rsi(closes, params.RSI_LEN)
    trend = sma(closes, params.TREND_LEN)
    if r is None or trend is None:
        return Decision("skip", f"not enough history ({len(closes)} bars)", rsi2=r,
                        sma200=trend, price=closes[-1] if closes else None)
    price = closes[-1]
    gap = (price / trend - 1.0) * 100.0

    if held:
        if r > params.SELL_ABOVE:
            return Decision("sell", "rsi", r, trend, price, gap)
        if bars_held >= params.MAX_HOLD:
            return Decision("sell", "time_stop", r, trend, price, gap)
        return Decision("hold", f"{bars_held} of {params.MAX_HOLD} bars", r, trend, price, gap)

    if r >= params.BUY_BELOW:
        return Decision("wait", "not oversold", r, trend, price, gap)
    if price <= trend:
        return Decision("wait", "trend gate blocked", r, trend, price, gap)
    return Decision("buy", "oversold in uptrend", r, trend, price, gap)
