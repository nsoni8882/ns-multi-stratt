"""The live rule must make the same decisions as the TradingView strategy.

`research/rsi2/rsi2_reversion_strategy.pine` is the third implementation of this rule and the
one the user can check by eye in TradingView. Its semantics, from the Pine source:

    if position_size == 0 and r < buyLvl and upTrend        -> entry at this bar's close
    if position_size > 0:
        held = bar_index - entry_bar_index
        if r > sellLvl or held >= maxHold                   -> close at this bar's close

Three details of Pine that this test reproduces exactly, because getting any of them wrong
is how the live bot would quietly diverge from the chart the user is reading:

  * `ta.rsi` is Wilder-smoothed (ta.rma), which is what trader.rule.wilder_rsi computes.
  * The entry and exit blocks are mutually exclusive on a bar -- `strategy.position_size`
    reads the value at bar open, so a position opened on bar i is never closed on bar i.
  * `held` counts *bars* since the entry bar, so an entry on bar i first becomes eligible
    for the time stop on bar i+10. That is what trader.run counts with Alpaca's calendar.

Offline: the same cached closes the drift test uses.
"""
from pathlib import Path

import pandas as pd
import pytest

from trader import params
from trader.rule import decide, sma, wilder_rsi

FIXTURES = Path(__file__).parent / "fixtures"


def pine_trades(closes):
    """The Pine strategy's trade list, transcribed from the .pine source."""
    trades, pos, entry_bar = [], 0, None
    for i in range(len(closes)):
        prefix = closes[: i + 1]
        r, trend = wilder_rsi(prefix, params.RSI_LEN), sma(prefix, params.TREND_LEN)
        if r is None or trend is None:
            continue  # ta.sma is `na` here, and `close > na` is false in Pine
        price = prefix[-1]
        if pos == 0:
            if r < params.BUY_BELOW and price > trend:
                pos, entry_bar = 1, i
                trades.append({"entry_bar": i, "entry": price})
        else:
            held = i - entry_bar
            if r > params.SELL_ABOVE or held >= params.MAX_HOLD:
                pos = 0
                trades[-1] |= {"exit_bar": i, "exit": price, "held": held,
                               "reason": "rsi" if r > params.SELL_ABOVE else "time_stop"}
    return trades


def rule_trades(closes):
    """The same walk, but every decision taken by trader.rule.decide -- the live code."""
    trades, held_pos, entry_bar = [], False, None
    for i in range(len(closes)):
        prefix = closes[: i + 1]
        bars_held = (i - entry_bar) if held_pos else 0
        d = decide(prefix, held=held_pos, bars_held=bars_held)
        if d.action == "buy":
            held_pos, entry_bar = True, i
            trades.append({"entry_bar": i, "entry": d.price})
        elif d.action == "sell":
            held_pos = False
            trades[-1] |= {"exit_bar": i, "exit": d.price, "held": bars_held,
                           "reason": d.reason}
    return trades


@pytest.mark.parametrize("symbol", params.SYMBOLS)
def test_live_rule_reproduces_the_pine_strategy_trade_for_trade(symbol):
    close = pd.read_csv(FIXTURES / f"{symbol}.csv", index_col=0, parse_dates=True)["close"]
    closes = [float(x) for x in close.to_numpy()]
    want, got = pine_trades(closes), rule_trades(closes)
    assert len(got) == len(want), f"{symbol}: {len(got)} trades vs Pine's {len(want)}"
    for w, g in zip(want, got):
        assert g == w, f"{symbol}: diverged at bar {w['entry_bar']} ({close.index[w['entry_bar']].date()})"
    assert len(want) > 150, f"{symbol}: only {len(want)} trades, fixture too short to be a test"


@pytest.mark.parametrize("symbol", params.SYMBOLS)
def test_no_position_is_opened_and_closed_on_the_same_bar(symbol):
    """Pine reads position_size at bar open, so this cannot happen there. If the live rule
    allowed it, the bot would buy and sell into the same closing auction."""
    close = pd.read_csv(FIXTURES / f"{symbol}.csv", index_col=0, parse_dates=True)["close"]
    for t in rule_trades([float(x) for x in close.to_numpy()]):
        if "exit_bar" in t:
            assert t["exit_bar"] > t["entry_bar"], f"{symbol}: same-bar round trip at {t['entry_bar']}"


@pytest.mark.parametrize("symbol", params.SYMBOLS)
def test_the_time_stop_never_exceeds_max_hold(symbol):
    close = pd.read_csv(FIXTURES / f"{symbol}.csv", index_col=0, parse_dates=True)["close"]
    for t in rule_trades([float(x) for x in close.to_numpy()]):
        if "held" in t:
            assert t["held"] <= params.MAX_HOLD, f"{symbol}: held {t['held']} bars"
