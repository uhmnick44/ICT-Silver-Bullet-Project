"""Displacement: candle range relative to ATR(14) on the configured timeframe.

ratio = (high - low) / ATR_ref, where ATR_ref is the ATR at the previous candle's close
(atr_reference = "prior_candle", ASSUMPTION) or at the candle's own close ("same_candle").
Thresholds 1.0/1.5/2.0/3.0 x ATR are evaluated; `threshold_passed` is the highest one met.
Percentile definition: ratio >= the `percentile`-th percentile of the ratios of the previous
`percentile_lookback` candles (strictly prior candles only).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .atr import atr as atr_fn
from .config import ATRConfig, DisplacementConfig

DISP_COLS = ["series_id", "timeframe", "candle_index", "ts_utc", "ts_ny", "trading_date", "confirmation_ts_utc", "direction",
             "range_points", "atr", "range_atr_ratio", "threshold_passed", "percentile_threshold_value", "passes_percentile"]


def detect_displacement(candles: pd.DataFrame, timeframe: str, cfg: DisplacementConfig, atr_cfg: ATRConfig, series_id: str,
                        keep_all: bool = False) -> pd.DataFrame:
    a = atr_fn(candles, atr_cfg.period, atr_cfg.method, atr_cfg.reset_on_data_gap)
    ref = np.roll(a, 1) if cfg.atr_reference == "prior_candle" else a
    if cfg.atr_reference == "prior_candle":
        ref[0] = np.nan
    rng = (candles["high"] - candles["low"]).to_numpy(float)
    ratio = rng / ref
    o, c = candles["open"].to_numpy(float), candles["close"].to_numpy(float)
    direction = np.where(c > o, "bullish", np.where(c < o, "bearish", "none"))
    thr = sorted(cfg.thresholds)
    passed = np.full(len(ratio), np.nan)
    for t in thr:
        passed = np.where(ratio >= t, t, passed)
    s = pd.Series(ratio)
    pct_val = s.shift(1).rolling(cfg.percentile_lookback, min_periods=cfg.percentile_lookback).quantile(cfg.percentile / 100.0).to_numpy()
    passes_pct = ratio >= pct_val
    out = pd.DataFrame({"series_id": series_id, "timeframe": timeframe, "candle_index": np.arange(len(candles)), "ts_utc": candles["ts_utc"],
                        "ts_ny": candles["ts_ny"], "trading_date": candles["trading_date"], "confirmation_ts_utc": candles["available_ts_utc"],
                        "direction": direction, "range_points": rng, "atr": ref, "range_atr_ratio": ratio, "threshold_passed": passed,
                        "percentile_threshold_value": pct_val, "passes_percentile": passes_pct})
    for t in thr:
        out[f"ge_{str(t).replace('.', '_')}_atr"] = ratio >= t
    if not keep_all:
        out = out[(out["range_atr_ratio"] >= cfg.record_min_ratio) | out["passes_percentile"]]
    return out.reset_index(drop=True)
