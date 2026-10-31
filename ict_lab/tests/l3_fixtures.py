"""Synthetic fixtures for Layer 3: bars + a hand-built Setup, feature tables for the signal gates."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ict_lab.engine.execution import BarArrays
from ict_lab.engine.signals import Setup
from .l2_fixtures import make_bars, flat

NY = "America/New_York"


def ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz=NY).tz_convert("UTC")


def bars_from(sessions, start_ny: str, ohlc, adjustment: float = 0.0, symbol: str = "MNQM4", drop_minutes=()) -> pd.DataFrame:
    b = make_bars(sessions, start_ny, ohlc, symbol=symbol, drop_minutes=drop_minutes)
    b["adjustment"] = adjustment
    return b


def arrays(sessions, start_ny: str, ohlc, **kw) -> BarArrays:
    return BarArrays.from_bars(bars_from(sessions, start_ny, ohlc, **kw))


def make_setup(direction="bullish", date="2024-05-15", window="sb_ny_am", upper=102.0, lower=100.0, setup_ny="2024-05-15 10:10",
               sweep_conf_ny="2024-05-15 10:05", level_price=95.0, level_type="prev_session_low", disp=None) -> Setup:
    return Setup(trading_date=pd.Timestamp(date), window=window, window_start_utc=ts(f"{date} 10:00"), window_end_utc=ts(f"{date} 11:00"),
                 direction=direction, bias="none", sweep_id=0, level_type=level_type, level_price=level_price,
                 sweep_penetration_ts_utc=ts(f"{date} 10:04"), sweep_confirmation_ts_utc=ts(sweep_conf_ny), sweep_max_penetration_points=0.5,
                 mss_id=None, mss_break_ts_utc=None, mss_swing_price=None, displacement_ts_utc=disp, displacement_confirmation_ts_utc=disp,
                 displacement_ratio=None, fvg_id="5m:1:bull", fvg_timeframe="5m", fvg_confirmation_ts_utc=ts(setup_ny), fvg_upper=upper,
                 fvg_lower=lower, fvg_midpoint=(upper + lower) / 2, setup_ts_utc=ts(setup_ny))


def window_row(date="2024-05-15", window="sb_ny_am", eligible=True, reasons="") -> pd.Series:
    return pd.Series({"trading_date": pd.Timestamp(date), "window": window, "start_ts_utc": ts(f"{date} 10:00"), "end_ts_utc": ts(f"{date} 11:00"),
                      "eligible": eligible, "exclusion_reasons": reasons, "vendor_degraded_utc_overlap": False, "calendar_status": "calendar_unverified",
                      "observed_session_status": "complete"})


def sweep_row(sweep_id=0, direction="bullish_reversal", level_type="prev_session_low", conf="2024-05-15 10:05", pen="2024-05-15 10:04", price=95.0, status="confirmed"):
    return {"sweep_id": sweep_id, "series_id": "t", "level_id": 0, "level_type": level_type, "source_timeframe": "session", "level_price": price,
            "side_swept": "sellside" if direction == "bullish_reversal" else "buyside", "sweep_direction": direction, "penetration_ts_utc": ts(pen),
            "penetration_index": 0, "max_penetration_points": 0.5, "max_penetration_ticks": 2, "confirmation_ts_utc": ts(conf), "confirmation_index": 1,
            "bars_to_confirmation": 1, "status": status, "trading_date": pd.Timestamp("2024-05-15"), "window": "sb_ny_am", "exec_timeframe": "1m"}


def fvg_row(fid="5m:1:bull", direction="bullish", conf="2024-05-15 10:10", upper=102.0, lower=100.0, tf="5m", gap_atr=1.0):
    return {"fvg_id": fid, "series_id": "t", "timeframe": tf, "direction": direction, "formation_ts_utc": ts("2024-05-15 09:55"), "confirmation_ts_utc": ts(conf),
            "c1_ts_utc": ts("2024-05-15 09:55"), "c2_ts_utc": ts("2024-05-15 10:00"), "c3_ts_utc": ts("2024-05-15 10:05"), "c3_index": 3,
            "trading_date": pd.Timestamp("2024-05-15"), "segment_id": 0, "upper": upper, "lower": lower, "midpoint": (upper + lower) / 2,
            "gap_points": upper - lower, "gap_ticks": (upper - lower) / 0.25, "atr": 2.0, "gap_atr": gap_atr, "first_mitigation_ts_utc": pd.NaT, "full_fill_ts_utc": pd.NaT}


def disp_row(conf="2024-05-15 10:06", direction="bullish", ratio=2.0):
    return {"series_id": "t", "timeframe": "1m", "candle_index": 5, "ts_utc": ts(conf) - pd.Timedelta(minutes=1), "ts_ny": ts(conf), "trading_date": pd.Timestamp("2024-05-15"),
            "confirmation_ts_utc": ts(conf), "direction": direction, "range_points": 4.0, "atr": 2.0, "range_atr_ratio": ratio, "threshold_passed": 1.5,
            "percentile_threshold_value": 1.0, "passes_percentile": True}


def mss_row(sweep_id=0, brk="2024-05-15 10:08", found=True, direction="bullish"):
    return {"mss_id": 0, "series_id": "t", "sweep_id": sweep_id, "direction": direction, "mss_timeframe": "1m", "swing_kind": "high", "swing_price": 101.0,
            "swing_ts_utc": ts("2024-05-15 09:50"), "swing_confirmation_ts_utc": ts("2024-05-15 09:53"), "break_ts_utc": ts(brk) if found else pd.NaT,
            "break_candle_index": 9, "bars_to_break": 3, "confirmation_method": "close", "found": found}


def feats(sweeps=(), fvgs=(), disps=(), msss=(), bias=None) -> dict:
    def df(rows, empty_cols):
        return pd.DataFrame(list(rows)) if rows else pd.DataFrame(columns=empty_cols)
    out = {"sweeps": df(sweeps, list(sweep_row().keys())), "fvg": df(fvgs, list(fvg_row().keys())), "displacement": df(disps, list(disp_row().keys())),
           "mss": df(msss, list(mss_row().keys()))}
    if bias is not None:
        out["bias"] = pd.DataFrame(bias)
    return out
