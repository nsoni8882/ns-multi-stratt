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


def crossed_above(series: pd.Series, i: int, level: float) -> bool:
    """True if series closed below `level` on bar i-1 and at/above it on bar i."""
    return bool(series.iloc[i - 1] < level <= series.iloc[i])


def crossed_below(series: pd.Series, i: int, level: float) -> bool:
    """True if series closed above `level` on bar i-1 and at/below it on bar i."""
    return bool(series.iloc[i - 1] > level >= series.iloc[i])
