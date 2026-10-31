"""Liquidity-level universe (FIXED): previous CME session high/low, previous RTH high/low,
pre-window high/low, confirmed 15-minute fractal swing highs/lows. Nothing else — in particular
no 1-minute swings — can be a sweep reference.

Each level records formation (the extreme bar / swing candle), confirmation (when its value is
final and knowable), activation (when it may be swept) and expiry (scope end; None for swings).
Buyside liquidity = highs (resting buy stops), sellside = lows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import LiquidityConfig
from .swings import fractal_swings
from .timeframes import resample

LEVEL_COLS = ["level_id", "series_id", "level_type", "side", "price", "source_timeframe", "formation_ts_utc", "confirmation_ts_utc",
              "activation_ts_utc", "expiry_ts_utc", "scope_trading_date", "scope_window", "source_session_complete",
              "penetration_ts_utc", "max_penetration_points", "consumed", "consumed_ts_utc", "consumption_reason", "sweep_id"]


def _extreme_ts(sub: pd.DataFrame, col: str, kind: str):
    i = sub[col].idxmax() if kind == "high" else sub[col].idxmin()
    return sub.loc[i, "ts_utc"]


def _session_levels(bars: pd.DataFrame, sessions_spec, level_type: str, mask_col: str | None, series_id: str) -> list[dict]:
    rows = []
    dates = sorted(bars["trading_date"].unique())
    by_date = {d: g for d, g in bars.groupby("trading_date", sort=True)}
    for prev_d, d in zip(dates[:-1], dates[1:]):
        src = by_date[prev_d]
        if mask_col:
            src = src[src[mask_col]]
        if len(src) == 0:
            continue
        conf = src["ts_utc"].max() + pd.Timedelta(minutes=1)
        act = sessions_spec.session_open_utc(d); exp = sessions_spec.session_close_utc(d)
        complete = bool(len(src) == (1380 if mask_col is None else 390))
        for side, col, kind in (("buyside", "high", "high"), ("sellside", "low", "low")):
            rows.append({"series_id": series_id, "level_type": f"{level_type}_{kind}", "side": side, "price": float(src[col].max() if kind == "high" else src[col].min()),
                         "source_timeframe": "session" if mask_col is None else "rth", "formation_ts_utc": _extreme_ts(src, col, kind),
                         "confirmation_ts_utc": conf, "activation_ts_utc": act, "expiry_ts_utc": exp, "scope_trading_date": d,
                         "scope_window": None, "source_session_complete": complete})
    return rows


def _prewindow_levels(bars: pd.DataFrame, sessions_spec, windows: tuple[str, ...], cfg: LiquidityConfig, series_id: str) -> list[dict]:
    rows = []
    for d, g in bars.groupby("trading_date", sort=True):
        for w in windows:
            a, b = sessions_spec.windows[w]
            w_start = sessions_spec.session_close_utc(d) - pd.Timedelta(minutes=sessions_spec.close_minute - a)
            w_end = w_start + pd.Timedelta(minutes=b - a)
            if cfg.prewindow_lookback == "session_open":
                src = g[g["ts_utc"] < w_start]
            else:
                lb = int(str(cfg.prewindow_lookback)[:-1])
                src = g[(g["ts_utc"] < w_start) & (g["ts_utc"] >= w_start - pd.Timedelta(minutes=lb))]
            if len(src) == 0:
                continue
            for side, col, kind in (("buyside", "high", "high"), ("sellside", "low", "low")):
                rows.append({"series_id": series_id, "level_type": f"prewindow_{kind}", "side": side,
                             "price": float(src[col].max() if kind == "high" else src[col].min()), "source_timeframe": "1m",
                             "formation_ts_utc": _extreme_ts(src, col, kind), "confirmation_ts_utc": w_start, "activation_ts_utc": w_start,
                             "expiry_ts_utc": w_end, "scope_trading_date": d, "scope_window": w, "source_session_complete": None})
    return rows


def _swing15_levels(bars: pd.DataFrame, cfg: LiquidityConfig, series_id: str) -> list[dict]:
    c15 = resample(bars, cfg.swing_timeframe)
    sw = fractal_swings(c15, cfg.swing_left, cfg.swing_right, cfg.equal_handling, series_id, cfg.swing_timeframe)
    rows = []
    for _, r in sw.iterrows():
        rows.append({"series_id": series_id, "level_type": f"swing_15m_{r['kind']}", "side": "buyside" if r["kind"] == "high" else "sellside",
                     "price": float(r["price"]), "source_timeframe": cfg.swing_timeframe, "formation_ts_utc": r["ts_utc"],
                     "confirmation_ts_utc": r["confirmation_ts_utc"], "activation_ts_utc": r["confirmation_ts_utc"], "expiry_ts_utc": pd.NaT,
                     "scope_trading_date": r["trading_date"], "scope_window": None, "source_session_complete": None})
    return rows


def build_liquidity_levels(bars: pd.DataFrame, sessions_spec, cfg: LiquidityConfig, windows: tuple[str, ...], series_id: str) -> pd.DataFrame:
    rows: list[dict] = []
    if "prev_session" in cfg.universe:
        rows += _session_levels(bars, sessions_spec, "prev_session", None, series_id)
    if "prev_rth" in cfg.universe:
        rows += _session_levels(bars, sessions_spec, "prev_rth", "in_rth", series_id)
    if "prewindow" in cfg.universe:
        rows += _prewindow_levels(bars, sessions_spec, windows, cfg, series_id)
    if "swing_15m" in cfg.universe:
        rows += _swing15_levels(bars, cfg, series_id)
    lv = pd.DataFrame(rows)
    if len(lv) == 0:
        return pd.DataFrame(columns=LEVEL_COLS)
    for c in ("formation_ts_utc", "confirmation_ts_utc", "activation_ts_utc", "expiry_ts_utc"):
        lv[c] = pd.to_datetime(lv[c], utc=True)
    lv["scope_trading_date"] = pd.to_datetime(lv["scope_trading_date"])
    lv = lv.sort_values(["activation_ts_utc", "level_type", "price"], kind="mergesort").reset_index(drop=True)
    lv.insert(0, "level_id", np.arange(len(lv)))
    lv["penetration_ts_utc"] = pd.NaT; lv["max_penetration_points"] = np.nan; lv["consumed"] = False
    lv["consumed_ts_utc"] = pd.NaT; lv["consumption_reason"] = None; lv["sweep_id"] = -1
    for c in ("penetration_ts_utc", "consumed_ts_utc"):
        lv[c] = pd.to_datetime(lv[c], utc=True)
    assert not lv["level_type"].str.startswith("swing_1m").any()
    return lv[LEVEL_COLS]
