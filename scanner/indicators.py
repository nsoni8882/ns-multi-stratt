"""Technical indicators. All functions take and return pandas Series/DataFrames."""
import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder's RSI, seeded with a simple average of the first `length` changes."""
    values = close.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) <= length:
        return pd.Series(out, index=close.index)
    delta = np.diff(values, prepend=np.nan)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain[1 : length + 1].mean()
    avg_loss = loss[1 : length + 1].mean()
    out[length] = _rsi_value(avg_gain, avg_loss)
    for i in range(length + 1, len(values)):
        avg_gain = (avg_gain * (length - 1) + gain[i]) / length
        avg_loss = (avg_loss * (length - 1) + loss[i]) / length
        out[i] = _rsi_value(avg_gain, avg_loss)
    return pd.Series(out, index=close.index)


def _wilder_smooth(values: np.ndarray, length: int) -> np.ndarray:
    """Wilder's accumulative smoothing, seeded with the sum of the first `length` values."""
    out = np.full(len(values), np.nan)
    if len(values) <= length:
        return out
    acc = values[1 : length + 1].sum()
    out[length] = acc
    for i in range(length + 1, len(values)):
        acc = acc - acc / length + values[i]
        out[i] = acc
    return out


def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder's ADX: how *strong* the trend is, regardless of direction.

    Below ~20 price is chopping rather than trending, which is where a pullback entry has
    nothing to pull back into. Returned on the same index as the inputs, NaN until enough
    bars exist (the first value lands at index 2*length-1).
    """
    h, l, c = (s.to_numpy(dtype=float) for s in (high, low, close))
    up, dn = np.diff(h, prepend=np.nan), -np.diff(l, prepend=np.nan)
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    prev_close = np.concatenate([[np.nan], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_close), np.abs(l - prev_close)))

    tr_s, plus_s, minus_s = (_wilder_smooth(x, length) for x in (tr, plus_dm, minus_dm))
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di, minus_di = 100.0 * plus_s / tr_s, 100.0 * minus_s / tr_s
        di_sum = plus_di + minus_di
        dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)
    dx = np.where(np.isnan(tr_s), np.nan, dx)

    out = np.full(len(c), np.nan)
    # Wilder seeds ADX with the mean of the first `length` DX values. DX is first defined at
    # index `length` (where the smoothed TR/DM are), so the seed spans dx[length : 2*length]
    # and is published at index 2*length-1 -- 27 for length 14, matching TradingView.
    first = 2 * length - 1
    if len(c) > first:
        avg = np.nanmean(dx[length : first + 1])
        out[first] = avg
        for i in range(first + 1, len(c)):
            avg = (avg * (length - 1) + dx[i]) / length
            out[i] = avg
    return pd.Series(out, index=close.index)


def rising(series: pd.Series, i: int, lookback: int) -> bool:
    """True if `series` is higher at bar i than it was `lookback` bars earlier."""
    j = i - lookback
    if j < 0:
        return False
    a, b = series.iloc[j], series.iloc[i]
    return bool(pd.notna(a) and pd.notna(b) and b > a)


def crossed_above(series: pd.Series, i: int, level: float) -> bool:
    """True if series closed below `level` on bar i-1 and at/above it on bar i."""
    return bool(series.iloc[i - 1] < level <= series.iloc[i])


def crossed_below(series: pd.Series, i: int, level: float) -> bool:
    """True if series closed above `level` on bar i-1 and at/below it on bar i."""
    return bool(series.iloc[i - 1] > level >= series.iloc[i])
