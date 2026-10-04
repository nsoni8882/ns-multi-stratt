from dataclasses import asdict, dataclass

import pandas as pd

from scanner.indicators import (crossed_above, crossed_below, ema, macd, mfi, obv, rel_volume,
                                rsi)
from scanner.strategies.base import (HIGH, LOW, SIGNAL_WINDOW, STANDARD, Release, Signal,
                                     make_signal, thesis_negated)

HIST_WINDOW = 100  # trailing bars used to rank the histogram
HIST_QUANTILE = 0.10  # "deep" = bottom/top 10% of the trailing window
DEEP_LOOKBACK = 5  # bars before the signal bar in which the histogram was deep

# Two tiers on the BUY side. The edge falls off sharply as the level is raised -- over 165
# S&P names x 12y of daily bars the 20-bar mean return was +5.32% for a cross back above 20
# (n=86), +2.13% above 25 (n=368), +1.89% above 30 (n=1050) and -0.29% above 35 (n=2131),
# against a +1.35% buy-and-hold baseline. A cross above 20 alone fires about 7 times a year
# across the whole S&P 500, so 25 is carried as a second, standard-conviction tier; going to
# 30 would roughly triple the count for a third of the per-signal edge, so it is left out.
RSI_LOW = 20  # HIGH conviction
RSI_LOW_STANDARD = 25
RSI_HIGH = 80
# No matching second tier on the SELL side: loosening it to 75 added 504 signals whose
# short P&L was no better than the 262 at 80 (both indistinguishable from zero edge).
RSI_HIGH_STANDARD = RSI_HIGH
MIN_BARS = 150
RVOL_WINDOW = 20
DIVERGENCE_LOOKBACK = 40  # bars searched for the prior price low an OBV divergence is measured against
# Descriptive only: how far back the card's one-line explanation looks when it reports how
# deep the RSI trough and the histogram low were, and how far price is off its recent high.
# Deliberately NOT in `params` -- these numbers decide nothing, they only describe a signal
# that has already fired, so changing one cannot change which bars fire.
REASON_LOOKBACK = 20


@dataclass(frozen=True)
class ReversalConfig:
    """Tunable gates. The defaults reproduce the shipped rule exactly, so a variant is only
    ever active where it was asked for -- research/measure.py is the only caller that passes
    a non-default config. Every volume gate below is off until measured."""

    rsi_low: float = RSI_LOW
    rsi_low_standard: float = RSI_LOW_STANDARD
    rsi_high: float = RSI_HIGH
    # The short leg measures +0.05% over 20 bars (t = +0.09, n indep 239): indistinguishable
    # from doing nothing, and what little it has comes from one month of 2020. Off by default,
    # kept so the measurement can be reproduced.
    enable_short: bool = False
    # The exhaustion story this strategy tells predicts a volume climax at the low: the last
    # holders giving up is what ends the decline. It has never been tested here.
    min_capitulation_rvol: "float | None" = None  # loudest bar of the deep window, as a multiple
    min_trigger_rvol: "float | None" = None  # volume on the bar RSI crosses back
    require_obv_above_ema: bool = False
    require_obv_divergence: bool = False  # price made a lower low, OBV did not
    obv_ema_span: int = 20
    mfi_confluence: bool = False  # the volume-weighted RSI crosses the same level too
    mfi_length: int = 14
    rvol_window: int = RVOL_WINDOW


DEFAULT_CONFIG = ReversalConfig()


def recovery_bars(hist: pd.Series, i: int, max_lookback: int = REASON_LOOKBACK) -> int:
    """How many consecutive bars the histogram has risen, counting back from bar i.

    Descriptive. The rule only requires three ascending bars; this says whether this
    particular name has been turning for three bars or for ten.
    """
    n = 0
    for j in range(i, max(i - max_lookback, 0), -1):
        a, b = hist.iloc[j], hist.iloc[j - 1]
        if pd.isna(a) or pd.isna(b) or a <= b:
            break
        n += 1
    return n


def trough(series: pd.Series, i: int, max_lookback: int = REASON_LOOKBACK) -> float:
    """Lowest value of `series` over the `max_lookback` bars ending at bar i."""
    window = series.iloc[max(i - max_lookback + 1, 0):i + 1].dropna()
    return float(window.min()) if not window.empty else float("nan")


def off_high(close: pd.Series, i: int, max_lookback: int = REASON_LOOKBACK) -> float:
    """Where bar i's close sits against the highest close of the window, as a fraction.

    -0.12 means the name is 12% below its 20-bar high: the size of the decline the
    histogram and RSI are now turning out of.
    """
    window = close.iloc[max(i - max_lookback + 1, 0):i + 1].dropna()
    if window.empty:
        return float("nan")
    peak = float(window.max())
    return float(close.iloc[i]) / peak - 1.0 if peak else float("nan")


def _obv_divergence(close: pd.Series, obv_series: pd.Series, i: int,
                    lookback: int = DIVERGENCE_LOOKBACK) -> bool:
    """True if price is at/below its low of the lookback while OBV is above its level there.

    The textbook bullish divergence: a lower low in price that the volume flow does not
    confirm, read as the selling having lost its force before the price did.
    """
    start = max(i - lookback, 0)
    window = close.iloc[start:i]
    if window.empty:
        return False
    j = int(window.to_numpy().argmin()) + start
    if j == i:
        return False
    if close.iloc[i] > window.iloc[j - start] * 1.01:  # price must still be near that low
        return False
    a, b = obv_series.iloc[j], obv_series.iloc[i]
    return bool(pd.notna(a) and pd.notna(b) and b > a)


def _volume_agrees(i: int, side: str, level: float, close: pd.Series, rvol: "pd.Series | None",
                   obv_series: "pd.Series | None", obv_dev: "pd.Series | None",
                   mfi_series: "pd.Series | None", cfg: ReversalConfig) -> bool:
    """Whether the volume behind the reversal supports it. A gate whose input is NaN rejects
    the bar: unmeasured is not the same as passing, and mixing the two would blur the cohort."""
    if cfg.min_capitulation_rvol is not None:
        if rvol is None:
            raise ValueError("min_capitulation_rvol is set but no volume series was supplied")
        window = rvol.iloc[max(i - DEEP_LOOKBACK, 0):i]
        peak = window.max() if not window.empty else float("nan")
        if pd.isna(peak) or peak < cfg.min_capitulation_rvol:
            return False
    if cfg.min_trigger_rvol is not None:
        if rvol is None:
            raise ValueError("min_trigger_rvol is set but no volume series was supplied")
        v = rvol.iloc[i]
        if pd.isna(v) or v < cfg.min_trigger_rvol:
            return False
    if cfg.require_obv_above_ema:
        if obv_dev is None:
            raise ValueError("require_obv_above_ema is set but no OBV series was supplied")
        d = obv_dev.iloc[i]
        if pd.isna(d) or (d <= 0 if side == "BUY" else d >= 0):
            return False
    if cfg.require_obv_divergence:
        if obv_series is None:
            raise ValueError("require_obv_divergence is set but no OBV series was supplied")
        if side == "BUY" and not _obv_divergence(close, obv_series, i):
            return False
        if side == "SELL" and not _obv_divergence(-close, -obv_series, i):
            return False
    if cfg.mfi_confluence:
        if mfi_series is None:
            raise ValueError("mfi_confluence is set but no MFI series was supplied")
        crossed = crossed_above if side == "BUY" else crossed_below
        if pd.isna(mfi_series.iloc[i]) or not crossed(mfi_series, i, level):
            return False
    return True


def rule_side(hist: pd.Series, lo: pd.Series, hi: pd.Series, r: pd.Series, i: int,
              close: "pd.Series | None" = None, rvol: "pd.Series | None" = None,
              obv_series: "pd.Series | None" = None, obv_dev: "pd.Series | None" = None,
              mfi_series: "pd.Series | None" = None,
              *, cfg: ReversalConfig = DEFAULT_CONFIG) -> "tuple[str, str] | None":
    """Return (side, conviction) for bar i, or None. Pure function of the indicator series.

    The RSI "was beyond the level within the last 5 bars" condition is implied by
    the cross on bar i (bar i-1 was beyond the level), so only the cross is tested.
    The deeper tier is tested first, so a bar crossing from 19 to 26 is reported as HIGH.
    """
    window = slice(i - DEEP_LOOKBACK, i)
    h, h1, h2 = hist.iloc[i], hist.iloc[i - 1], hist.iloc[i - 2]

    deep_low = bool((hist.iloc[window] <= lo.iloc[window]).any())
    if deep_low and h > h1 > h2 and h <= 0:
        for level, tier in ((cfg.rsi_low, HIGH), (cfg.rsi_low_standard, STANDARD)):
            if crossed_above(r, i, level):
                if not _volume_agrees(i, "BUY", level, close, rvol, obv_series, obv_dev,
                                      mfi_series, cfg):
                    return None
                return "BUY", tier

    if not cfg.enable_short:
        return None
    deep_high = bool((hist.iloc[window] >= hi.iloc[window]).any())
    if deep_high and h < h1 < h2 and h >= 0 and crossed_below(r, i, cfg.rsi_high):
        if not _volume_agrees(i, "SELL", cfg.rsi_high, close, rvol, obv_series, obv_dev,
                              mfi_series, cfg):
            return None
        return "SELL", LOW  # see base.py: the short leg showed no measurable edge
    return None


VARIANTS = {
    "shipped": DEFAULT_CONFIG,
    "with-shorts": ReversalConfig(enable_short=True),  # the leg that was dropped
    # The exhaustion thesis, tested directly: was there a volume climax into the low?
    "capitulation-1.5x": ReversalConfig(min_capitulation_rvol=1.5),
    "capitulation-2x": ReversalConfig(min_capitulation_rvol=2.0),
    "trigger-rvol-1.2": ReversalConfig(min_trigger_rvol=1.2),
    "obv-above-ema": ReversalConfig(require_obv_above_ema=True),
    "obv-divergence": ReversalConfig(require_obv_divergence=True),
    "mfi-confluence": ReversalConfig(mfi_confluence=True),
    "capitulation+divergence": ReversalConfig(min_capitulation_rvol=1.5, require_obv_divergence=True),
}


class MacdRsiReversal:
    id = "macd-rsi-reversal"
    name = "MACD + RSI Reversal"
    description = (
        "BUY when the MACD histogram climbs back from a deep low while RSI(14) crosses back "
        "above 20 (strongest) or 25. Long only: the mirror setup — histogram falling from a "
        "deep high with RSI crossing back below 80 — measured no edge at all over 12 years, "
        "so it is not published."
    )
    min_bars = MIN_BARS
    # The same levels are used on 1d and 4H. Checked, not assumed: on 4H a cross back above
    # 20 returned +3.57% over 20 bars against a +0.77% baseline (n=23), the same shape as daily.
    chart = {"rsi_levels": [RSI_LOW, RSI_LOW_STANDARD, RSI_HIGH], "macd_deep": True, "emas": False}
    # Newest first. See TrendPullback.history -- the top fingerprint is build-asserted.
    history = (
        Release("1.4.0", "2026-10-04",
                "The line explaining a signal now describes that stock: how far it fell, how "
                "deep RSI went, and how many bars the MACD histogram has been turning. It no "
                "longer says selling was exhausted — nothing in these rules looks at volume, "
                "and every volume test made the results worse.",
                fingerprint="12d3ca5cf02a"),
        Release("1.3.0", "2026-10-03",
                "SELL signals are gone. Over 12 years they were worth nothing measurable — "
                "a coin flip after costs, with what little they had coming from a single "
                "month of 2020. Only the side with evidence behind it is published now."),
        Release("1.2.0", "2026-10-03",
                "A signal that fired a day or two ago is now marked 'Setup changed' when RSI has "
                "since crossed back past the level that triggered it, so a card never describes "
                "a setup that no longer holds. They are still listed, not hidden: over 12 years "
                "these did no worse than signals still intact.",
                ),
        Release("1.1.0", "2026-10-03",
                "Signals now carry a conviction tier. An RSI cross below 20 beat the market "
                "by 3.97% over the next 20 days against 0.78% for a cross below 25, so the "
                "deeper ones are marked stronger and listed first."),
        Release("1.0.0", "2026-10-03",
                "First version. Looks for exhaustion: a deeply negative MACD histogram in "
                "the last 5 bars plus RSI(14) turning up out of oversold territory."),
    )
    def __init__(self, config: ReversalConfig = DEFAULT_CONFIG):
        self.config = config

    @property
    def params(self) -> dict:
        """Everything that can change which bars fire, for rules_version()."""
        return {
            "min_bars": MIN_BARS, "hist_window": HIST_WINDOW, "hist_quantile": HIST_QUANTILE,
            "deep_lookback": DEEP_LOOKBACK, "rsi_high_standard": RSI_HIGH_STANDARD,
            "divergence_lookback": DIVERGENCE_LOOKBACK,
            "macd": (12, 26, 9), "rsi_length": 14,  # indicator periods decide signals too
        } | asdict(self.config)

    def indicators(self, df: pd.DataFrame) -> dict:
        """Everything rule_side needs, computed once per frame. Volume series are built only
        when a gate asks for them -- OBV and MFI over 500 bars for every name is not free."""
        close = df["close"]
        hist = macd(close)["hist"]
        out = {
            "hist": hist,
            "lo": hist.rolling(HIST_WINDOW).quantile(HIST_QUANTILE),
            "hi": hist.rolling(HIST_WINDOW).quantile(1 - HIST_QUANTILE),
            "r": rsi(close),
            "close": close,
            "rvol": None,
            "obv_series": None,
            "obv_dev": None,
            "mfi_series": None,
        }
        cfg = self.config
        if cfg.min_capitulation_rvol is not None or cfg.min_trigger_rvol is not None:
            out["rvol"] = rel_volume(df["volume"], cfg.rvol_window)
        if cfg.require_obv_above_ema or cfg.require_obv_divergence:
            o = obv(close, df["volume"])
            out["obv_series"] = o
            out["obv_dev"] = o - ema(o, cfg.obv_ema_span)
        if cfg.mfi_confluence:
            out["mfi_series"] = mfi(df["high"], df["low"], close, df["volume"], cfg.mfi_length)
        return out
    def evaluate(self, df: pd.DataFrame) -> "Signal | None":
        if len(df) < self.min_bars:
            return None
        ind = self.indicators(df)
        hist, r, cfg = ind["hist"], ind["r"], self.config
        last = len(df) - 1
        for k in range(SIGNAL_WINDOW):
            i = last - k
            hit = rule_side(**ind, i=i, cfg=cfg)
            if hit:
                side, conviction = hit
                # The level that fired it: the deep tier for a HIGH buy, else the standard one.
                level = cfg.rsi_high if side == "SELL" else (
                    cfg.rsi_low if conviction == HIGH else cfg.rsi_low_standard)
                dead = thesis_negated(r, i, last, side, level)
                # Everything the card's explanation says about this name, measured on the
                # signal bar. Descriptive: no gate reads any of it, so none of it is in
                # `params` and adding one cannot move a signal.
                # A SELL is the mirror of a BUY throughout, so every extreme is measured on
                # the negated series and flipped back: the "trough" of a SELL is its peak.
                sgn = 1.0 if side == "BUY" else -1.0
                details = {
                    "macd_hist": hist.iloc[i], "rsi": r.iloc[i], "rsi_level": level,
                    "hist_trough": sgn * trough(sgn * hist, i),
                    "hist_deep_level": ind["lo"].iloc[i] if side == "BUY" else ind["hi"].iloc[i],
                    "recovery_bars": recovery_bars(sgn * hist, i),
                    "rsi_trough": sgn * trough(sgn * r, i),
                    "off_high": sgn * off_high(sgn * ind["close"], i),
                }
                return make_signal(df, i, side, details, conviction, invalidated=dead)
        return None
