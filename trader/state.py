"""What the bot must remember between runs: the opening balance and each entry date.

Lives on the `data` branch, so a lost local file is not a disaster -- but it can still go
missing, and then `entry_date` recovers from filled order history. What it will not do is
default to today: that would reset the ten-session time stop on every run and a position
would never time out.
"""
import json
from pathlib import Path


def load(path) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def save(path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")


def opening_balance(state: dict, equity: float) -> float:
    """The account's equity the first time the bot ever ran. Written once, then frozen."""
    if "opening_balance" not in state:
        state["opening_balance"] = float(equity)
    return float(state["opening_balance"])


def entry_date(state: dict, symbol: str, api, today: str) -> "str | None":
    """State file first, then the broker's order history. None when neither knows."""
    known = (state.get("positions") or {}).get(symbol, {}).get("entry_date")
    if known:
        return known
    if api is None:
        return None
    order = api.last_filled_buy(symbol)
    return order["filled_at"][:10] if order and order.get("filled_at") else None
