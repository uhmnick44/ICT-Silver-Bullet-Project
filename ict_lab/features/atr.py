"""ATR(period) on a candle table, using only candles up to and including each candle's close.

Continuity rules (approved Layer 2 decision 3):
  * true range uses the previous close only when the candle is bucket-consecutive with its predecessor;
    across a session break or a data hole TR = high - low (bars are never treated as adjacent when they are not)
  * a DATA DISCONTINUITY is a candle that is not bucket-consecutive with the previous candle of the SAME
    trading session (a missing-bar hole), or an incomplete candle (missing minutes inside its bucket).
    Session breaks (maintenance 17:00-18:00 ET, weekends) are not data holes.
  * with reset_on_data_gap=True (default) the ATR recursion restarts at every data discontinuity and the
    value is unavailable (NaN) until `period` candles have accumulated since the restart; with False the
    recursion carries across the hole (TR of the hole candle is still high-low only)
  * the first `period` candles of the series are NaN (warm-up); NaN is never replaced by a fabricated value
Smoothing: 'wilder' (recursive, standard ATR) or 'sma' (simple mean of the last `period` TRs).
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


def data_discontinuity(candles: pd.DataFrame) -> np.ndarray:
    """True for candles that follow a within-session missing-bar hole or are themselves incomplete."""
    cons = candles["consecutive_prev"].to_numpy(bool)
    td = pd.DatetimeIndex(candles["trading_date"]).to_numpy()
    same_session = np.r_[False, td[1:] == td[:-1]]
    comp = candles["complete"].to_numpy(bool) if "complete" in candles else np.ones(len(candles), dtype=bool)
    return (~cons & same_session) | ~comp


def _atr_segment(tr: np.ndarray, period: int, method: str) -> np.ndarray:
    n = len(tr); out = np.full(n, np.nan)
    if n < period:
        return out
    if method == "sma":
        return pd.Series(tr).rolling(period).mean().to_numpy()
    if method != "wilder":
        raise ValueError(method)
    out[period - 1] = tr[:period].mean()
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def atr(candles: pd.DataFrame, period: int = 14, method: str = "wilder", reset_on_data_gap: bool = True) -> np.ndarray:
    tr = true_range(candles)
    n = len(tr)
    if not reset_on_data_gap or n == 0:
        return _atr_segment(tr, period, method)
    disc = data_discontinuity(candles)
    starts = np.r_[0, np.where(disc)[0]]
    starts = np.unique(starts)
    out = np.full(n, np.nan)
    bounds = list(starts) + [n]
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b > a:
            out[a:b] = _atr_segment(tr[a:b], period, method)
    return out
