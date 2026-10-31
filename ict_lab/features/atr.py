"""ATR(period) on a candle table, using only candles up to and including each candle's close.

True range of candle i = max(high-low, |high-prev_close|, |low-prev_close|) when candle i is
bucket-consecutive with candle i-1; otherwise high-low only (a missing bar is not a neighbour).
Smoothing: 'wilder' (recursive, standard ATR) or 'sma' (simple mean of the last `period` TRs).
The first `period` values are NaN (warm-up); detectors treat NaN ATR as "ATR unavailable".
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(candles: pd.DataFrame) -> np.ndarray:
    h, l, c = candles["high"].to_numpy(float), candles["low"].to_numpy(float), candles["close"].to_numpy(float)
    cons = candles["consecutive_prev"].to_numpy(bool)
    tr = h - l
    pc = np.roll(c, 1); pc[0] = np.nan
    alt = np.maximum(np.abs(h - pc), np.abs(l - pc))
    use = cons & ~np.isnan(pc)
    tr = np.where(use, np.maximum(tr, alt), tr)
    return tr


def atr(candles: pd.DataFrame, period: int = 14, method: str = "wilder") -> np.ndarray:
    tr = true_range(candles)
    n = len(tr)
    out = np.full(n, np.nan)
    if n < period:
        return out
    if method == "sma":
        s = pd.Series(tr).rolling(period).mean().to_numpy()
        return s
    if method != "wilder":
        raise ValueError(method)
    out[period - 1] = tr[:period].mean()
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out
