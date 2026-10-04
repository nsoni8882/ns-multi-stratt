from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from scanner.indicators import (adx, crossed_above, crossed_below, ema, mfi, obv, rel_volume,
                                rising, rsi)
from scanner.strategies.base import (HIGH, LOW, SIGNAL_WINDOW, STANDARD, Release, Signal,
                                     make_signal, thesis_negated)

# Cardwell's RSI range shift: RSI oscillates 40-80 in an uptrend (40 acts as support) and
# 20-60 in a downtrend (60 acts as resistance). The classic 30/70 and 20/80 bands were built
# for range-bound markets and barely fire inside a trend -- measured over 165 S&P names x 12y
# of daily bars, 20/80 produced 11 BUY and 6 SELL signals in total, against 7,198/2,890 here.
RSI_BUY_LEVEL = 40
RSI_SELL_LEVEL = 60

# EMA200 with adjust=False still carries ~8% of its weight on the seed bar after 250 bars,
# which left a 0.67% median error against a converged EMA200 and flipped the close-vs-EMA200
# verdict on 5 of 161 names. At 400 bars the error is 0.14% and nothing flipped. Both
# timeframes already fetch more than this (daily ~500 bars, 4H ~970), so the only tickers
# this excludes are recent listings whose trend could not be classified reliably anyway.
MIN_BARS = 400

DIP_LOOKBACK = 60  # how far back to trace a sub-level RSI run when measuring its depth
# Indicator periods. Not in TrendPullbackConfig because no variant has ever moved them, but
# they decide which bars fire just as much as the gates do, so they are in `params`.
EMA_FAST, EMA_SLOW, EMA_SHORT, RSI_LENGTH = 50, 200, 20, 14


@dataclass(frozen=True)
class TrendPullbackConfig:
    """Tunable gates for the setup. The defaults reproduce the shipped rule exactly, so a
    variant is only ever active where it was explicitly asked for -- see research/measure.py,
    which is the only caller that passes a non-default config.

    Every gate below has been measured over 163 S&P names x 12y and *none of them beat the
    defaults* -- full write-up in research/FINDINGS.md. Short version, 20-bar alpha on the
    non-overlapping sample, against the shipped rule's +0.11% (t=+0.74):

        RSI trigger 40 -> 35      -0.25%  (t=-1.18)
        ADX >= 20 gate            -0.08%  (t=-0.44)   ADX >= 25: -0.38% (t=-1.65)
        rising EMA200 gate        +0.11%  (t=+0.76)   i.e. no effect
        drop ema50 > ema200       +0.09%  (t=+0.65)   i.e. no effect
        close within 2% of EMA50  +0.15%  (t=+1.05)   best found; fails the t>=2.5 bar
        close below EMA20         +0.12%  (t=+0.82)
        close at/below EMA50      +0.10%  (t=+0.63)

    Grading conviction by pullback depth looked like the one real finding (deep dips -1.55%,
    t=-4.04) but it is the COVID crash: 70 signals in 2020 at -15.16% carry all of it, and
    every other year sits between -2.25% and +2.44%. Do not ship it. Do not re-propose these
    gates without reading FINDINGS.md first.
    """

    rsi_buy_level: float = RSI_BUY_LEVEL
    rsi_sell_level: float = RSI_SELL_LEVEL
    # The short leg does not just lack an edge, it is reliably wrong: shorting these returned
    # -2.08% over 20 bars (t = -8.14, n indep 1,487, win 43.5%) and was negative in 9 of 11
    # years. It is off by default and kept only so the measurement can be reproduced.
    enable_short: bool = False
    # Trend-quality gate: the dominant failure mode of "above the 200 EMA" is price chopping
    # just above the line, where an RSI dip is noise rather than a pullback into a trend.
    adx_min: "float | None" = None  # None leaves the gate off
    adx_length: int = 14
    require_rising_ema200: bool = False
    rising_lookback: int = 20
    # Conviction by pullback depth: (max_depth, tier) checked in order, so the deepest tier
    # must come first and the last entry should be open-ended. Empty means flat STANDARD.
    depth_tiers: "tuple[tuple[float, str], ...]" = ()
    # The 50-above-200 condition is near-collinear with close-above-200 and flips ~10-15%
    # after the actual turn; the flag exists so its contribution can be measured.
    require_ema50_above_ema200: bool = True
    # Structural pullback: is this a pullback at all? The shipped rule fires on an RSI dip
    # wherever it happens, so a name 25% above its EMA50 that ticked 39 -> 41 scores the same
    # as one sitting on the EMA50. These require price to have actually come back to a mean.
    max_ema50_distance: "float | None" = None  # e.g. 0.02 -> close must be within +2% of EMA50
    require_below_ema20: bool = False  # the dip reached the short-term mean
    # Volume confluence. The rule so far reads price alone, so a dip on heavy selling and a dip
    # on no selling at all score the same. Each gate below is one reading of "does the volume
    # agree with the story", and all are off by default until measured.
    rvol_window: int = 20  # bars in the rolling median that defines a "normal" bar
    max_dip_rvol: "float | None" = None  # dry-up: mean volume through the dip, as a multiple
    min_trigger_rvol: "float | None" = None  # expansion: volume on the bar that crosses back
    require_obv_above_ema: bool = False  # accumulation: OBV above its own EMA at the signal
    obv_ema_span: int = 20
    mfi_confluence: bool = False  # the volume-weighted RSI must cross the same level too
    mfi_length: int = 14


DEFAULT_CONFIG = TrendPullbackConfig()

# Variants wired up for measurement, keyed by the label the harness reports them under.
VARIANTS = {
    "shipped": DEFAULT_CONFIG,
    "with-shorts": TrendPullbackConfig(enable_short=True),  # the leg that was dropped
    "rsi35": TrendPullbackConfig(rsi_buy_level=35, rsi_sell_level=65),
    "adx20": TrendPullbackConfig(adx_min=20),
    "adx25": TrendPullbackConfig(adx_min=25),
    "rising200": TrendPullbackConfig(require_rising_ema200=True),
    "no-ema50": TrendPullbackConfig(require_ema50_above_ema200=False),
    "rsi35+adx20": TrendPullbackConfig(rsi_buy_level=35, rsi_sell_level=65, adx_min=20),
    # Two opposite readings of pullback depth. "deep-is-strong" extrapolates the Reversal
    # strategy's depth table (the deeper the RSI cross, the bigger the edge); measurement
    # falsified it here and supports "deep-is-weak" -- see research/results/trend_pullback.md.
    "tiered-deep-is-strong": TrendPullbackConfig(
        depth_tiers=((30, HIGH), (35, STANDARD), (float("inf"), LOW))),
    "tiered-deep-is-weak": TrendPullbackConfig(
        depth_tiers=((30, LOW), (35, STANDARD), (float("inf"), HIGH))),
    # Structural pullback: require price to have come back to a mean, rather than taking any
    # RSI dip wherever it happens. Measured against research/ACCEPTANCE.md.
    "near-ema50-2pct": TrendPullbackConfig(max_ema50_distance=0.02),
    "near-ema50-5pct": TrendPullbackConfig(max_ema50_distance=0.05),
    "at-ema50": TrendPullbackConfig(max_ema50_distance=0.0),  # close at or below the EMA50
    "below-ema20": TrendPullbackConfig(require_below_ema20=True),
    "below-ema20+near-ema50-5pct": TrendPullbackConfig(
        require_below_ema20=True, max_ema50_distance=0.05),
    # Volume confluence. The rule has only ever read price, so these ask whether the volume
    # behind a pullback says anything the price does not. Measured against ACCEPTANCE.md.
    "dryup-0.9": TrendPullbackConfig(max_dip_rvol=0.9),  # dip traded below its own normal
    "dryup-0.75": TrendPullbackConfig(max_dip_rvol=0.75),  # a strict reading of the same idea
    "trigger-rvol-1.2": TrendPullbackConfig(min_trigger_rvol=1.2),  # the recovery bar is real
    "obv-accumulation": TrendPullbackConfig(require_obv_above_ema=True),
    "mfi-confluence": TrendPullbackConfig(mfi_confluence=True),  # volume-weighted RSI agrees
    # The textbook setup in full: quiet pullback, loud recovery.
    "dryup+trigger": TrendPullbackConfig(max_dip_rvol=0.9, min_trigger_rvol=1.2),
}


def dip_depth(r: pd.Series, i: int, level: float, max_lookback: int = DIP_LOOKBACK) -> float:
    """Lowest RSI in the unbroken run of sub-`level` bars ending at bar i-1.

    Bar i-1 is below `level` whenever bar i crossed up through it, so this measures how deep
    the pullback that is now resolving actually went.
    """
    depth = float(r.iloc[i - 1])
    for j in range(i - 1, max(i - 1 - max_lookback, -1), -1):
        v = r.iloc[j]
        if pd.isna(v) or v >= level:
            break
        depth = min(depth, float(v))
    return depth


def dip_length(r: pd.Series, i: int, level: float, max_lookback: int = DIP_LOOKBACK) -> int:
    """How many bars the sub-`level` RSI run ending at bar i-1 lasted.

    Descriptive counterpart to `dip_depth`: the same window, reported as a duration. A
    two-bar dip and a three-week one are both "RSI crossed back above 40".
    """
    n = 0
    for j in range(i - 1, max(i - 1 - max_lookback, -1), -1):
        v = r.iloc[j]
        if pd.isna(v) or v >= level:
            break
        n += 1
    return n


def _tier(depth: float, tiers) -> str:
    """Map a pullback depth onto a conviction tier. Only the long leg is tiered: the short
    leg is pinned to LOW by its measured lack of edge, whatever its rally height."""
    for bound, tier in tiers:
        if depth <= bound:
            return tier
    return STANDARD


def dip_mean_rvol(rvol: pd.Series, r: pd.Series, i: int, level: float,
                  max_lookback: int = DIP_LOOKBACK) -> float:
    """Mean relative volume over the unbroken run of sub-`level` RSI bars ending at bar i-1.

    The same window `dip_depth` measures, asking a different question: how much volume the
    pullback traded on. A dip nobody sold into is the textbook healthy pullback; whether that
    textbook is right here is the thing being measured.
    """
    vals = []
    for j in range(i - 1, max(i - 1 - max_lookback, -1), -1):
        v = r.iloc[j]
        if pd.isna(v) or v >= level:
            break
        rv = rvol.iloc[j]
        if pd.notna(rv):
            vals.append(float(rv))
    return float(np.mean(vals)) if vals else float("nan")


def _volume_agrees(i: int, side: str, level: float, r: pd.Series, rvol: "pd.Series | None",
                   obv_dev: "pd.Series | None", mfi_series: "pd.Series | None",
                   cfg: TrendPullbackConfig) -> bool:
    """Whether the volume behind the setup supports it, per cfg. All gates default to off.

    A gate whose input is NaN rejects the signal rather than passing it: early bars and names
    with gaps in their volume history have not met the condition, they are simply unmeasured,
    and letting them through would quietly mix gated and ungated signals in one cohort.
    """
    if cfg.max_dip_rvol is not None:
        if rvol is None:
            raise ValueError("max_dip_rvol is set but no relative-volume series was supplied")
        mean_rvol = dip_mean_rvol(rvol, r, i, level)
        if pd.isna(mean_rvol) or mean_rvol > cfg.max_dip_rvol:
            return False
    if cfg.min_trigger_rvol is not None:
        if rvol is None:
            raise ValueError("min_trigger_rvol is set but no relative-volume series was supplied")
        v = rvol.iloc[i]
        if pd.isna(v) or v < cfg.min_trigger_rvol:
            return False
    if cfg.require_obv_above_ema:
        if obv_dev is None:
            raise ValueError("require_obv_above_ema is set but no OBV series was supplied")
        d = obv_dev.iloc[i]
        if pd.isna(d) or (d <= 0 if side == "BUY" else d >= 0):
            return False
    if cfg.mfi_confluence:
        if mfi_series is None:
            raise ValueError("mfi_confluence is set but no MFI series was supplied")
        crossed = crossed_above if side == "BUY" else crossed_below
        if pd.isna(mfi_series.iloc[i]) or not crossed(mfi_series, i, level):
            return False
    return True


def _reached_the_mean(close: pd.Series, ema50: pd.Series, ema20: "pd.Series | None", i: int,
                      cfg: TrendPullbackConfig) -> bool:
    """Whether the dip actually pulled price back to a moving average, per cfg."""
    if cfg.max_ema50_distance is not None:
        if close.iloc[i] > ema50.iloc[i] * (1 + cfg.max_ema50_distance):
            return False
    if cfg.require_below_ema20:
        if ema20 is None:
            raise ValueError("require_below_ema20 is set but no EMA20 series was supplied")
        if pd.isna(ema20.iloc[i]) or close.iloc[i] >= ema20.iloc[i]:
            return False
    return True


def rule_side(close: pd.Series, ema50: pd.Series, ema200: pd.Series, r: pd.Series, i: int,
              adx_series: "pd.Series | None" = None, ema20: "pd.Series | None" = None,
              rvol: "pd.Series | None" = None, obv_dev: "pd.Series | None" = None,
              mfi_series: "pd.Series | None" = None,
              *, cfg: TrendPullbackConfig = DEFAULT_CONFIG) -> "tuple[str, str] | None":
    """Return (side, conviction) for bar i, or None. The 5-bar RSI lookback in the spec is
    implied by the cross on bar i (bar i-1 was beyond the level)."""
    if cfg.adx_min is not None:
        if adx_series is None:
            raise ValueError("adx_min is set but no ADX series was supplied")
        a = adx_series.iloc[i]
        if pd.isna(a) or a < cfg.adx_min:
            return None

    up_structure = ema50.iloc[i] > ema200.iloc[i] or not cfg.require_ema50_above_ema200
    dn_structure = ema50.iloc[i] < ema200.iloc[i] or not cfg.require_ema50_above_ema200

    if close.iloc[i] > ema200.iloc[i] and up_structure and crossed_above(r, i, cfg.rsi_buy_level):
        if cfg.require_rising_ema200 and not rising(ema200, i, cfg.rising_lookback):
            return None
        if not _reached_the_mean(close, ema50, ema20, i, cfg):
            return None
        if not _volume_agrees(i, "BUY", cfg.rsi_buy_level, r, rvol, obv_dev, mfi_series, cfg):
            return None
        if not cfg.depth_tiers:
            return "BUY", STANDARD
        return "BUY", _tier(dip_depth(r, i, cfg.rsi_buy_level), cfg.depth_tiers)
    if (cfg.enable_short and close.iloc[i] < ema200.iloc[i] and dn_structure
            and crossed_below(r, i, cfg.rsi_sell_level)):
        if cfg.require_rising_ema200 and rising(ema200, i, cfg.rising_lookback):
            return None
        if not _volume_agrees(i, "SELL", cfg.rsi_sell_level, r, rvol, obv_dev, mfi_series, cfg):
            return None
        return "SELL", LOW  # see base.py: the short leg showed no measurable edge
    return None


class TrendPullback:
    id = "trend-pullback"
    name = "Trend Pullback"
    description = (
        "BUY when price is in an uptrend (above the 200 EMA, with the 50 EMA above it) "
        "and RSI(14) dips below 40 then crosses back above it. Long only: the mirror setup "
        "in a downtrend was backtested over 12 years and lost money reliably, so it is not "
        "published."
    )
    min_bars = MIN_BARS
    # The same 40/60 levels are used on 1d and 4H. Checked, not assumed: on 4H the BUY leg
    # returned +0.36% over 20 bars against a +0.77% baseline (t=3.9, n=821), the same shape
    # as daily. Re-measure before changing them on one timeframe only.
    chart = {"rsi_levels": [RSI_BUY_LEVEL, RSI_SELL_LEVEL], "macd_deep": False, "emas": True}

    def __init__(self, config: TrendPullbackConfig = DEFAULT_CONFIG):
        self.config = config

    # Newest first. Add an entry at the top whenever `params` changes -- the fingerprint on
    # the top entry is asserted against the live one, so the build fails otherwise.
    history = (
        Release("1.5.0", "2026-10-04",
                "The line explaining a signal now describes that stock: how many bars RSI "
                "spent under the trigger level, how deep the dip went, and how far price "
                "sits above the 50 and 200 day averages.",
                fingerprint="0ea89a61ddfe"),
        Release("1.4.0", "2026-10-03",
                "SELL signals are gone. Over 12 years, shorting them lost 2.08% in the next "
                "20 days and won less than 44% of the time, in 9 years out of 11 — so the "
                "list only shows the side that measured positive. Fewer signals, each one "
                "with evidence behind it."),
        Release("1.3.0", "2026-10-03",
                "A signal that fired a day or two ago is now marked 'Setup changed' when RSI has "
                "since crossed back past the level that triggered it, so a card never describes "
                "a setup that no longer holds. They are still listed, not hidden: over 12 years "
                "these did no worse than signals still intact.",
                ),
        Release("1.2.0", "2026-10-03",
                "Tested a deeper RSI trigger, an ADX trend-strength filter and three "
                "versions of a 'price must come back to the 50 EMA' rule over 12 years. "
                "None of them beat the current rules, so nothing changed."),
        Release("1.1.0", "2026-10-03",
                "Raised the minimum history from 250 to 400 bars, because the 200 EMA is "
                "still distorted by its own starting value before then. Short signals are "
                "now shown as weaker than long ones: over 12 years they did not make money."),
        Release("1.0.0", "2026-10-03",
                "First version. Buys a pullback in an uptrend — price above the 200 EMA "
                "with the 50 EMA above it, and RSI(14) dipping under 40 then recovering."),
    )

    @property
    def params(self) -> dict:
        """Everything that can change which bars fire, for rules_version()."""
        return {
            "min_bars": self.min_bars,
            "ema_fast": EMA_FAST, "ema_slow": EMA_SLOW, "ema_short": EMA_SHORT,
            "rsi_length": RSI_LENGTH, "dip_lookback": DIP_LOOKBACK,
        } | asdict(self.config)

    def indicators(self, df: pd.DataFrame) -> dict:
        """Everything rule_side needs, computed once per frame."""
        close = df["close"]
        out = {
            "close": close,
            "ema50": ema(close, EMA_FAST),
            "ema200": ema(close, EMA_SLOW),
            "r": rsi(close, RSI_LENGTH),
            "adx_series": None,
            "ema20": None,
            "rvol": None,
            "obv_dev": None,
            "mfi_series": None,
        }
        cfg = self.config
        if cfg.adx_min is not None:
            out["adx_series"] = adx(df["high"], df["low"], close, cfg.adx_length)
        if cfg.require_below_ema20:
            out["ema20"] = ema(close, EMA_SHORT)
        if cfg.max_dip_rvol is not None or cfg.min_trigger_rvol is not None:
            out["rvol"] = rel_volume(df["volume"], cfg.rvol_window)
        if cfg.require_obv_above_ema:
            # The deviation, not the level: OBV's absolute value depends on where the series
            # happens to start, so only its position against its own average is meaningful.
            o = obv(close, df["volume"])
            out["obv_dev"] = o - ema(o, cfg.obv_ema_span)
        if cfg.mfi_confluence:
            out["mfi_series"] = mfi(df["high"], df["low"], close, df["volume"], cfg.mfi_length)
        return out

    def evaluate(self, df: pd.DataFrame) -> "Signal | None":
        if len(df) < self.min_bars:
            return None
        ind = self.indicators(df)
        last = len(df) - 1
        for k in range(SIGNAL_WINDOW):
            i = last - k
            hit = rule_side(**ind, i=i, cfg=self.config)
            if hit:
                side, conviction = hit
                level = self.config.rsi_sell_level if side == "SELL" else self.config.rsi_buy_level
                dead = thesis_negated(ind["r"], i, last, side, level)
                # The last four are descriptive only -- how deep this name's dip went, how
                # long it lasted, and how far price sits above each mean. No gate reads
                # them, so they are not in `params` and cannot move a signal.
                close, e50, e200 = ind["close"], ind["ema50"], ind["ema200"]
                details = {"rsi": ind["r"].iloc[i], "rsi_level": level,
                           "ema50": e50.iloc[i], "ema200": e200.iloc[i],
                           "rsi_trough": dip_depth(ind["r"], i, level),
                           "dip_bars": dip_length(ind["r"], i, level),
                           "above_ema50": close.iloc[i] / e50.iloc[i] - 1.0,
                           "above_ema200": close.iloc[i] / e200.iloc[i] - 1.0}
                if ind["adx_series"] is not None:
                    details["adx"] = ind["adx_series"].iloc[i]
                return make_signal(df, i, side, details, conviction, invalidated=dead)
        return None
