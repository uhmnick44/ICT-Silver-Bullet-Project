"""Market Structure Shift after a confirmed liquidity sweep.

For a bullish reversal sweep (sellside taken) the MSS is a break of the most recent eligible
confirmed swing HIGH on the MSS timeframe; for a bearish sweep, of the most recent swing LOW.
Eligible = confirmed (right-side candles closed) at or before the sweep confirmation, and not already
broken between its candle and the sweep confirmation (ASSUMPTION: an already-broken swing is not a
structure level). Break confirmation: "close" (close through) or "wick" (high/low through), searched
in the candles that open at/after the sweep confirmation, within max_bars_after_sweep candles.
MSS swings are structure levels only; they are never used as liquidity-sweep references.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import MSSConfig
from .swings import fractal_swings
from .timeframes import naive_utc

MSS_COLS = ["mss_id", "series_id", "sweep_id", "direction", "mss_timeframe", "swing_kind", "swing_price", "swing_ts_utc",
            "swing_confirmation_ts_utc", "break_ts_utc", "break_candle_index", "bars_to_break", "confirmation_method", "found"]


def detect_mss(candles: pd.DataFrame, sweeps: pd.DataFrame, cfg: MSSConfig, series_id: str) -> pd.DataFrame:
    sw = fractal_swings(candles, cfg.swing_left, cfg.swing_right, cfg.equal_handling, series_id, cfg.timeframe)
    ts = naive_utc(candles["ts_utc"])
    hi, lo, cl = candles["high"].to_numpy(float), candles["low"].to_numpy(float), candles["close"].to_numpy(float)
    avail = naive_utc(candles["available_ts_utc"])
    pools = {}
    for kind in ("high", "low"):
        q = sw[sw["kind"] == kind].sort_values("candle_index").reset_index(drop=True)
        pools[kind] = (q["candle_index"].to_numpy(int), q["price"].to_numpy(float), naive_utc(q["confirmation_ts_utc"]), q)
    rows = []
    conf_sweeps = sweeps[sweeps["status"] == "confirmed"]
    for _, s in conf_sweeps.iterrows():
        bull = s["sweep_direction"] == "bullish_reversal"
        ci_arr, p_arr, conf_arr, q = pools["high" if bull else "low"]
        sweep_conf = naive_utc(s["confirmation_ts_utc"])
        start = int(np.searchsorted(ts, sweep_conf, side="left"))      # first candle opening at/after sweep confirmation
        n_elig = int(np.searchsorted(conf_arr, sweep_conf, side="right"))   # swings confirmed at/before the sweep (conf sorted with index)
        chosen = None
        arr = (cl if cfg.confirmation == "close" else (hi if bull else lo))
        run_max = -np.inf; run_min = np.inf; prev_ci = start   # incremental extreme of arr over (ci, start)
        for j in range(n_elig - 1, -1, -1):
            ci = int(ci_arr[j]); p = float(p_arr[j])
            seg = arr[ci + 1:prev_ci]
            if len(seg):
                if bull: run_max = max(run_max, float(seg.max()))
                else: run_min = min(run_min, float(seg.min()))
            prev_ci = ci + 1
            broken = (run_max > p) if bull else (run_min < p)
            if not broken:
                chosen = j; break
        row = {"series_id": series_id, "sweep_id": int(s["sweep_id"]), "direction": "bullish" if bull else "bearish",
               "mss_timeframe": cfg.timeframe, "swing_kind": "high" if bull else "low", "confirmation_method": cfg.confirmation,
               "swing_price": np.nan, "swing_ts_utc": pd.NaT, "swing_confirmation_ts_utc": pd.NaT, "break_ts_utc": pd.NaT,
               "break_candle_index": -1, "bars_to_break": -1, "found": False}
        if chosen is not None:
            p = float(p_arr[chosen])
            row.update({"swing_price": p, "swing_ts_utc": q["ts_utc"].iat[chosen], "swing_confirmation_ts_utc": q["confirmation_ts_utc"].iat[chosen]})
            end = min(start + cfg.max_bars_after_sweep, len(candles))
            seg = (arr[start:end] > p) if bull else (arr[start:end] < p)
            if seg.any():
                b = start + int(np.argmax(seg))
                row.update({"break_ts_utc": pd.Timestamp(avail[b], tz="UTC"), "break_candle_index": b, "bars_to_break": int(b - start), "found": True})
        rows.append(row)
    m = pd.DataFrame(rows, columns=[c for c in MSS_COLS if c != "mss_id"])
    m.insert(0, "mss_id", np.arange(len(m)))
    for c in ("swing_ts_utc", "swing_confirmation_ts_utc", "break_ts_utc"):
        m[c] = pd.to_datetime(m[c], utc=True)
    return m
