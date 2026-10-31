"""Fair Value Gap detection (three-candle), with causal confirmation and post-confirmation
mitigation / full-fill tracking on 1-minute bars.

FIXED definitions:
  bullish FVG : candle-1 high  <  candle-3 low   (strict). upper = c3.low, lower = c1.high
  bearish FVG : candle-1 low   >  candle-3 high  (strict). upper = c1.low, lower = c3.high
  available only after candle 3 has closed (confirmation_ts = candle-3 available_ts)
ASSUMPTIONS (documented in docs/silver_bullet_methodology.md):
  formation_ts     = candle-1 open timestamp
  the three candles must be bucket-consecutive (no missing bar between them) and complete
  mitigation       = first 1m bar after confirmation that trades strictly inside the gap
                     (bullish: low < upper; bearish: high > lower)
  full fill        = first 1m bar after confirmation that reaches the distal boundary
                     (bullish: low <= lower; bearish: high >= upper)
  gap_atr          = gap_points / ATR(14) measured on the FVG timeframe at candle-3 close
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .atr import atr as atr_fn
from .config import ATRConfig, FVGConfig
from .timeframes import naive_utc

FVG_COLS = ["fvg_id", "series_id", "timeframe", "direction", "formation_ts_utc", "confirmation_ts_utc", "c1_ts_utc", "c2_ts_utc",
            "c3_ts_utc", "c3_index", "trading_date", "segment_id", "upper", "lower", "midpoint", "gap_points", "gap_ticks",
            "atr", "gap_atr", "first_mitigation_ts_utc", "full_fill_ts_utc"]


def first_index_where(values: np.ndarray, start: int, threshold: float, op: str) -> int:
    """First index >= start where values <op> threshold, or -1. Chunked doubling scan (numpy)."""
    n = len(values); size = 256
    while start < n:
        chunk = values[start:start + size]
        m = chunk < threshold if op == "lt" else chunk <= threshold if op == "le" else chunk > threshold if op == "gt" else chunk >= threshold
        if m.any():
            return start + int(np.argmax(m))
        start += size; size = min(size * 2, 1 << 18)
    return -1


def detect_fvg(candles: pd.DataFrame, bars_1m: pd.DataFrame, timeframe: str, cfg: FVGConfig, atr_cfg: ATRConfig,
               series_id: str, tick_size: float) -> pd.DataFrame:
    h, l = candles["high"].to_numpy(float), candles["low"].to_numpy(float)
    cons = candles["consecutive_prev"].to_numpy(bool)
    comp = candles["complete"].to_numpy(bool)
    a = atr_fn(candles, atr_cfg.period, atr_cfg.method)
    n = len(candles)
    if n < 3:
        return pd.DataFrame(columns=FVG_COLS)
    i3 = np.arange(2, n)
    ok = cons[i3] & cons[i3 - 1]
    if cfg.require_complete_candles:
        ok &= comp[i3] & comp[i3 - 1] & comp[i3 - 2]
    bull = ok & (h[i3 - 2] < l[i3])
    bear = ok & (l[i3 - 2] > h[i3])
    rows = []
    for mask, direction in ((bull, "bullish"), (bear, "bearish")):
        idx = i3[mask]
        if direction == "bullish":
            upper, lower = l[idx], h[idx - 2]
        else:
            upper, lower = l[idx - 2], h[idx]
        gap = upper - lower
        rows.append(pd.DataFrame({"direction": direction, "c3_index": idx, "upper": upper, "lower": lower, "gap_points": gap, "atr": a[idx]}))
    f = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["direction", "c3_index", "upper", "lower", "gap_points", "atr"])
    f = f.sort_values(["c3_index", "direction"]).reset_index(drop=True)
    f["gap_atr"] = f["gap_points"] / f["atr"]
    if cfg.min_gap_points > 0:
        f = f[f["gap_points"] >= cfg.min_gap_points]
    if cfg.min_gap_atr > 0:
        f = f[f["gap_atr"] >= cfg.min_gap_atr]   # NaN ATR (warm-up) fails the filter
    f = f.reset_index(drop=True)
    c3 = f["c3_index"].to_numpy(int)
    f["midpoint"] = (f["upper"] + f["lower"]) / 2.0
    f["gap_ticks"] = f["gap_points"] / tick_size
    f["c1_ts_utc"] = candles["ts_utc"].to_numpy()[c3 - 2]; f["c2_ts_utc"] = candles["ts_utc"].to_numpy()[c3 - 1]
    f["c3_ts_utc"] = candles["ts_utc"].to_numpy()[c3]
    f["formation_ts_utc"] = f["c1_ts_utc"]
    f["confirmation_ts_utc"] = candles["available_ts_utc"].to_numpy()[c3]
    f["trading_date"] = candles["trading_date"].to_numpy()[c3]
    f["segment_id"] = candles["segment_id"].to_numpy()[c3]
    # mitigation / full fill on 1m bars strictly after confirmation
    bts = naive_utc(bars_1m["ts_utc"])
    blo, bhi = bars_1m["low"].to_numpy(float), bars_1m["high"].to_numpy(float)
    conf = naive_utc(pd.to_datetime(f["confirmation_ts_utc"], utc=True))
    starts = np.searchsorted(bts, conf, side="left")
    mit, fill = np.full(len(f), np.datetime64("NaT", "ns")), np.full(len(f), np.datetime64("NaT", "ns"))
    for k in range(len(f)):
        s = int(starts[k])
        if f["direction"].iat[k] == "bullish":
            m = first_index_where(blo, s, float(f["upper"].iat[k]), "lt"); ff = first_index_where(blo, s, float(f["lower"].iat[k]), "le")
        else:
            m = first_index_where(bhi, s, float(f["lower"].iat[k]), "gt"); ff = first_index_where(bhi, s, float(f["upper"].iat[k]), "ge")
        if m >= 0: mit[k] = bts[m]
        if ff >= 0: fill[k] = bts[ff]
    f["first_mitigation_ts_utc"] = pd.to_datetime(mit, utc=True)
    f["full_fill_ts_utc"] = pd.to_datetime(fill, utc=True)
    f["series_id"] = series_id; f["timeframe"] = timeframe
    f.insert(0, "fvg_id", [f"{timeframe}:{int(i)}:{'bull' if d == 'bullish' else 'bear'}" for i, d in zip(f["c3_index"], f["direction"])])
    for c in ("c1_ts_utc", "c2_ts_utc", "c3_ts_utc", "formation_ts_utc", "confirmation_ts_utc"):
        f[c] = pd.to_datetime(f[c], utc=True)
    return f[FVG_COLS].reset_index(drop=True)
