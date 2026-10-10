"""How many shares to buy, and the four reasons not to.

Slices come off `equity`. The paper account reports 4x that as `buying_power`; using it
would quietly lever a strategy whose backtest is unlevered. `cash` is the separate, harder
limit: equity rises with an appreciating holding while cash does not, so a 50% slice of
equity can exceed the money actually available and silently borrow the difference.
"""
import math

from trader import params


def shares_for(equity: float, price: float, buying_power: float, n_held: int,
               cash: "float | None" = None) -> "tuple[int, str | None]":
    """(qty, refusal). `refusal` is None when the order may proceed."""
    if n_held >= params.MAX_CONCURRENT:
        return 0, f"already holding {n_held} of {params.MAX_CONCURRENT}"
    slice_value = equity * params.SLICE_PCT
    qty = math.floor(slice_value / price) if price > 0 else 0
    if qty < 1:
        return 0, f"a slice of ${slice_value:,.0f} buys 0 whole shares at ${price:,.2f}"
    if cash is not None and qty * price > cash:
        return 0, f"needs ${qty * price:,.0f}, cash on hand is ${cash:,.0f}"
    if qty * price > buying_power:
        return 0, f"needs ${qty * price:,.0f}, buying power is ${buying_power:,.0f}"
    return qty, None
