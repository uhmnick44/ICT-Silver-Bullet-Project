"""Liquidity-sweep detection on the execution timeframe.

bullish reversal sweep : price penetrates an eligible SELLSIDE level (low) by >= min_penetration and a
                         bar within max_confirmation_bars (counting the penetration bar as 0) CLOSES back above the level
bearish reversal sweep : mirror on a BUYSIDE level (high), close back below

State machine per level: activated (activation_ts <= bar open) -> penetrated (first bar through the
level) -> confirmed sweep (close back within the delay) or no_reversal (no close back within the delay).
Both outcomes consume the level unless allow_reuse=True (then only confirmed sweeps are recorded and the
level stays active). Eligibility is evaluated bar by bar in time order; nothing after the confirming bar is read.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import LiquidityConfig, SweepConfig
from .fvg import first_index_where
from .timeframes import naive_utc

SWEEP_COLS = ["sweep_id", "series_id", "level_id", "level_type", "source_timeframe", "level_price", "side_swept", "sweep_direction",
              "penetration_ts_utc", "penetration_index", "max_penetration_points", "max_penetration_ticks", "confirmation_ts_utc",
              "confirmation_index", "bars_to_confirmation", "status", "trading_date", "window", "exec_timeframe"]


def _window_of(minute_of_day: int, windows: dict[str, tuple[int, int]]) -> str | None:
    for name, (a, b) in windows.items():
        if a <= minute_of_day < b:
            return name
    return None


def detect_sweeps(candles: pd.DataFrame, levels: pd.DataFrame, cfg: SweepConfig, liq_cfg: LiquidityConfig, tick_size: float,
                  sessions_spec, series_id: str, windows: tuple[str, ...] = ("sb_london", "sb_ny_am", "sb_ny_pm")) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (sweeps, levels with penetration/consumption columns filled). `window` on each sweep is the
    Silver Bullet window containing the confirming bar (or None)."""
    sb_windows = {w: sessions_spec.windows[w] for w in windows}
    ts = naive_utc(candles["ts_utc"])
    lo, hi, cl = candles["low"].to_numpy(float), candles["high"].to_numpy(float), candles["close"].to_numpy(float)
    avail = naive_utc(candles["available_ts_utc"])
    mod = (pd.DatetimeIndex(candles["ts_ny"]).hour * 60 + pd.DatetimeIndex(candles["ts_ny"]).minute).to_numpy()
    tdates = candles["trading_date"].to_numpy()
    minpen = cfg.min_penetration_ticks * tick_size
    lv = levels.copy()
    rows = []
    sid = 0
    n = len(candles)
    act = naive_utc(lv["activation_ts_utc"]); expn = naive_utc(lv["expiry_ts_utc"])
    for k in range(len(lv)):
        price = float(lv["price"].iat[k]); side = lv["side"].iat[k]
        start = int(np.searchsorted(ts, act[k], side="left"))
        end = n if np.isnat(expn[k]) else int(np.searchsorted(ts, expn[k], side="left"))
        if start >= end:
            continue
        pos = start
        while pos < end:
            if side == "sellside":
                p = first_index_where(lo, pos, price - minpen, "le")
            else:
                p = first_index_where(hi, pos, price + minpen, "ge")
            if p < 0 or p >= end:
                break
            # confirmation window: bars p .. p+max (bounded by scope end)
            last = min(p + cfg.max_confirmation_bars, end - 1)
            seg_close = cl[p:last + 1]
            back = np.where(seg_close > price)[0] if side == "sellside" else np.where(seg_close < price)[0]
            if len(back):
                c = p + int(back[0])
                status = "confirmed"
            else:
                c = last
                status = "no_reversal"
            maxpen = (price - lo[p:c + 1].min()) if side == "sellside" else (hi[p:c + 1].max() - price)
            if pd.isna(lv["penetration_ts_utc"].iat[k]):
                lv.iat[k, lv.columns.get_loc("penetration_ts_utc")] = pd.Timestamp(ts[p], tz="UTC")
                lv.iat[k, lv.columns.get_loc("max_penetration_points")] = float(maxpen)
            rows.append({"sweep_id": sid, "series_id": series_id, "level_id": int(lv["level_id"].iat[k]), "level_type": lv["level_type"].iat[k],
                         "source_timeframe": lv["source_timeframe"].iat[k], "level_price": price, "side_swept": side,
                         "sweep_direction": "bullish_reversal" if side == "sellside" else "bearish_reversal",
                         "penetration_ts_utc": pd.Timestamp(ts[p], tz="UTC"), "penetration_index": p, "max_penetration_points": float(maxpen),
                         "max_penetration_ticks": float(maxpen / tick_size), "confirmation_ts_utc": pd.Timestamp(avail[c], tz="UTC"), "confirmation_index": c,
                         "bars_to_confirmation": int(c - p), "status": status, "trading_date": tdates[c],
                         "window": _window_of(int(mod[c]), sb_windows), "exec_timeframe": cfg.timeframe})
            sid += 1
            if status == "confirmed" and liq_cfg.allow_reuse:
                pos = c + 1
                continue
            lv.iat[k, lv.columns.get_loc("consumed")] = True
            lv.iat[k, lv.columns.get_loc("consumed_ts_utc")] = pd.Timestamp(avail[c], tz="UTC")
            lv.iat[k, lv.columns.get_loc("consumption_reason")] = "confirmed_sweep" if status == "confirmed" else "penetration_no_reversal"
            lv.iat[k, lv.columns.get_loc("sweep_id")] = sid - 1
            break
    sw = pd.DataFrame(rows, columns=SWEEP_COLS)
    for c in ("penetration_ts_utc", "confirmation_ts_utc"):
        sw[c] = pd.to_datetime(sw[c], utc=True)
    sw["trading_date"] = pd.to_datetime(sw["trading_date"])
    return sw.sort_values(["confirmation_ts_utc", "sweep_id"]).reset_index(drop=True), lv
