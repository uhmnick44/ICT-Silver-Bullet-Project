"""Higher-timeframe directional bias evaluated at a window start, using only data available then.

Valid detectors (causal):
  none                 : always "none"
  prev_day_oc          : previous CME session close vs open (bullish if close > open)
  swing_15m_structure  : last two confirmed 15m swing highs and lows — HH+HL bullish, LH+LL bearish, else none
  swing_1h_structure   : same on 1h candles
  daily_ma20_slope     : SMA(20) of completed-session closes rising -> bullish, falling -> bearish
Neutral / tie conditions (approved implementation choices):
  prev_day_oc          : no completed previous session -> none; close == open -> none
  swing structure      : fewer than two confirmed highs or two confirmed lows -> none; last high == previous high
                         or last low == previous low -> none; HH with LL or LH with HL (mixed) -> none
  daily_ma20_slope     : fewer than ma_period + 1 completed sessions -> none; slope == 0 -> none
LOOKAHEAD diagnostics (INVALID FOR LIVE TRADING, excluded from candidate selection, optimisation and holdout):
  perfect_window       : the window's own open-to-close direction
  perfect_session      : direction from the window open to the session close
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import LOOKAHEAD_BIAS, VALID_BIAS, BiasConfig
from .swings import fractal_swings
from .timeframes import naive_utc, resample

BIAS_COLS = ["series_id", "detector", "lookahead", "trading_date", "window", "eval_ts_utc", "bias"]


def _structure_bias(swings: pd.DataFrame, at: np.datetime64) -> str:
    e = swings[naive_utc(swings["confirmation_ts_utc"]) <= at]
    h = e[e["kind"] == "high"]["price"].to_numpy(); l = e[e["kind"] == "low"]["price"].to_numpy()
    if len(h) < 2 or len(l) < 2:
        return "none"
    hh, hl = h[-1] > h[-2], l[-1] > l[-2]
    lh, ll = h[-1] < h[-2], l[-1] < l[-2]
    return "bullish" if hh and hl else "bearish" if lh and ll else "none"


def compute_bias(bars: pd.DataFrame, sessions_spec, windows: tuple[str, ...], cfg: BiasConfig, series_id: str,
                 detector: str | None = None) -> pd.DataFrame:
    det = detector or cfg.detector
    lookahead = det in LOOKAHEAD_BIAS
    if lookahead and not cfg.allow_lookahead_diagnostic:
        raise PermissionError(f"{det} is a LOOKAHEAD diagnostic; set allow_lookahead_diagnostic=true (never for candidate selection)")
    if det not in VALID_BIAS + LOOKAHEAD_BIAS:
        raise ValueError(det)
    daily = resample(bars, "1d")
    if det in ("swing_15m_structure", "swing_1h_structure"):
        tf = "15m" if det == "swing_15m_structure" else "1h"
        sw = fractal_swings(resample(bars, tf), cfg.swing_left, cfg.swing_right, "first", series_id, tf)
    if det == "daily_ma20_slope":
        daily = daily.assign(sma=daily["close"].rolling(cfg.ma_period).mean())
    rows = []
    by_date = {d: g for d, g in bars.groupby("trading_date", sort=True)}
    dates = list(by_date)
    for i, d in enumerate(dates):
        for w in windows:
            a, b = sessions_spec.windows[w]
            w_start = sessions_spec.session_close_utc(d) - pd.Timedelta(minutes=sessions_spec.close_minute - a)
            w_end = w_start + pd.Timedelta(minutes=b - a)
            at = naive_utc(w_start)
            if det == "none":
                bias = "none"
            elif det == "prev_day_oc":
                prev = daily[naive_utc(daily["available_ts_utc"]) <= at]
                bias = "none" if len(prev) == 0 else ("bullish" if prev["close"].iat[-1] > prev["open"].iat[-1] else "bearish" if prev["close"].iat[-1] < prev["open"].iat[-1] else "none")
            elif det in ("swing_15m_structure", "swing_1h_structure"):
                bias = _structure_bias(sw, at)
            elif det == "daily_ma20_slope":
                prev = daily[naive_utc(daily["available_ts_utc"]) <= at]
                if len(prev) < cfg.ma_period + 1 or pd.isna(prev["sma"].iat[-1]) or pd.isna(prev["sma"].iat[-2]):
                    bias = "none"
                else:
                    slope = prev["sma"].iat[-1] - prev["sma"].iat[-2]
                    bias = "bullish" if slope > 0 else "bearish" if slope < 0 else "none"
            else:   # LOOKAHEAD diagnostics
                g = by_date[d]
                win = g[(g["ts_utc"] >= w_start) & (g["ts_utc"] < w_end)]
                if len(win) == 0:
                    bias = "none"
                else:
                    o = win["open"].iat[0]
                    c = win["close"].iat[-1] if det == "perfect_window" else g["close"].iat[-1]
                    bias = "bullish" if c > o else "bearish" if c < o else "none"
            rows.append({"series_id": series_id, "detector": det, "lookahead": lookahead, "trading_date": d, "window": w,
                         "eval_ts_utc": w_start, "bias": bias})
    out = pd.DataFrame(rows, columns=BIAS_COLS)
    out["eval_ts_utc"] = pd.to_datetime(out["eval_ts_utc"], utc=True)
    return out
