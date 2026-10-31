"""Configurable fractal swing detector on completed candles of any timeframe.

A candle i is a swing high when its high exceeds the highs of the `left` candles before it and
the highs of the `right` candles after it. Equal highs are resolved deterministically:
  first  : strictly greater than the left side, greater-or-equal on the right (earliest equal bar wins)
  last   : greater-or-equal on the left, strictly greater on the right (latest equal bar wins)
  strict : strictly greater on both sides (equal highs never form a swing)
Swing lows mirror this. A swing is confirmed (and becomes usable) at the `available_ts_utc` of the
`right`-th candle after it; nothing about it is knowable before that.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SWING_COLS = ["swing_id", "series_id", "timeframe", "kind", "price", "candle_index", "ts_utc", "ts_ny", "trading_date",
              "confirmation_ts_utc", "confirm_candle_index", "left", "right", "equal_handling"]


def _extreme_mask(vals: np.ndarray, left: int, right: int, mode: str) -> np.ndarray:
    """Vectorised fractal test for highs (pass -vals for lows)."""
    v = pd.Series(vals)
    left_max = v.shift(1).rolling(left, min_periods=left).max().to_numpy()
    right_max = v[::-1].shift(1).rolling(right, min_periods=right).max()[::-1].to_numpy()
    if mode == "first":
        m = (vals > left_max) & (vals >= right_max)
    elif mode == "last":
        m = (vals >= left_max) & (vals > right_max)
    else:
        m = (vals > left_max) & (vals > right_max)
    m &= ~np.isnan(left_max) & ~np.isnan(right_max)
    return m


def fractal_swings(candles: pd.DataFrame, left: int, right: int, equal_handling: str = "first",
                   series_id: str = "", timeframe: str = "") -> pd.DataFrame:
    highs, lows = candles["high"].to_numpy(float), candles["low"].to_numpy(float)
    avail = pd.DatetimeIndex(candles["available_ts_utc"])
    parts = []
    for kind, vals in (("high", highs), ("low", -lows)):
        m = _extreme_mask(vals, left, right, equal_handling)
        idx = np.where(m)[0]
        parts.append(pd.DataFrame({"kind": kind, "price": (vals[idx] if kind == "high" else -vals[idx]), "candle_index": idx,
                                   "ts_utc": candles["ts_utc"].to_numpy()[idx] if len(idx) else [], "ts_ny": candles["ts_ny"].to_numpy()[idx] if len(idx) else [],
                                   "trading_date": candles["trading_date"].to_numpy()[idx] if len(idx) else [],
                                   "confirmation_ts_utc": avail[idx + right] if len(idx) else [], "confirm_candle_index": idx + right}))
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["kind", "price", "candle_index", "ts_utc", "ts_ny", "trading_date", "confirmation_ts_utc", "confirm_candle_index"])
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    df["ts_ny"] = pd.to_datetime(df["ts_utc"]).dt.tz_convert("America/New_York")
    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df["confirmation_ts_utc"] = pd.to_datetime(df["confirmation_ts_utc"], utc=True)
    df = df.sort_values(["candle_index", "kind"]).reset_index(drop=True)
    df.insert(0, "swing_id", np.arange(len(df)))
    df.insert(1, "series_id", series_id); df.insert(2, "timeframe", timeframe)
    df["left"] = left; df["right"] = right; df["equal_handling"] = equal_handling
    return df[SWING_COLS]
