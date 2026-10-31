"""Timeframe identifiers and causal higher-timeframe candle construction.

A candle of timeframe T is identified by its bucket open time (NY wall clock aligned: 5m/15m/1h to
the clock, 1d to the CME trading session). Its `close_ts` is the open time of the last 1-minute
bar it contains plus one minute, and its `available_ts` is the bucket end (wall-clock) — the
earliest instant at which the candle is known to be complete. `n_bars` and `complete` record
whether every nominal minute of the bucket has a bar; `consecutive_prev` is True only when the
previous candle in the table is the immediately preceding bucket of the same session.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TIMEFRAME_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}
INTRADAY = tuple(TIMEFRAME_MINUTES)
ALL_TIMEFRAMES = INTRADAY + ("1d",)
CANDLE_COLS = ["ts_utc", "ts_ny", "trading_date", "open", "high", "low", "close", "volume", "n_bars",
               "expected_bars", "complete", "close_ts_utc", "available_ts_utc", "consecutive_prev", "segment_id", "symbol"]


def naive_utc(x) -> np.ndarray:
    """tz-aware UTC Series/Index/scalar -> numpy datetime64[ns] (naive, UTC) for fast comparisons."""
    if isinstance(x, (pd.Series, pd.DatetimeIndex)):
        idx = pd.DatetimeIndex(x)
        if idx.tz is not None:
            idx = idx.tz_convert("UTC").tz_localize(None)
        return idx.to_numpy().astype("datetime64[ns]")
    t = pd.Timestamp(x)
    if t.tzinfo is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return np.datetime64(t.to_datetime64(), "ns")


def validate_timeframe(tf: str) -> str:
    if tf not in ALL_TIMEFRAMES:
        raise ValueError(f"unsupported timeframe {tf!r}; supported: {ALL_TIMEFRAMES}")
    return tf


def _bucket_open_ny(ts_ny: pd.DatetimeIndex, minutes: int) -> pd.DatetimeIndex:
    """Floor NY wall-clock time to the bucket (DST-safe: works on naive local time)."""
    naive = ts_ny.tz_localize(None)
    floored = naive.floor(f"{minutes}min")
    return floored.tz_localize(ts_ny.tz, ambiguous="NaT", nonexistent="NaT")


def resample(bars: pd.DataFrame, tf: str, session_open_minute: int = 18 * 60, session_close_minute: int = 17 * 60) -> pd.DataFrame:
    """Build timeframe `tf` candles from 1-minute bars (columns as produced by Layer 1).
    1m returns the bars themselves in candle layout. 1d = one candle per CME trading date."""
    validate_timeframe(tf)
    b = bars.sort_values("ts_utc").reset_index(drop=True)
    ts_ny = pd.DatetimeIndex(b["ts_ny"])
    if tf == "1m":
        one = pd.Timedelta(minutes=1)
        cons = b["consecutive_prev"].to_numpy() if "consecutive_prev" in b else np.r_[False, (b["ts_utc"].diff().iloc[1:] == one).to_numpy()]
        out = pd.DataFrame({
            "ts_utc": b["ts_utc"], "ts_ny": ts_ny, "trading_date": b["trading_date"],
            "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"],
            "volume": b["volume"], "n_bars": 1, "expected_bars": 1, "complete": True,
            "close_ts_utc": b["ts_utc"] + one, "available_ts_utc": b["ts_utc"] + one,
            "consecutive_prev": cons,
            "segment_id": b["segment_id"] if "segment_id" in b else 0, "symbol": b["symbol"],
        })
        return out[CANDLE_COLS]
    if tf == "1d":
        key = pd.DatetimeIndex(b["trading_date"])
        bucket_open = key  # label = trading date midnight (NY), nominal session open is 18:00 the day before
        minutes = None
    else:
        minutes = TIMEFRAME_MINUTES[tf]
        bucket_open = _bucket_open_ny(ts_ny, minutes)
    g = b.assign(_bucket=bucket_open.tz_localize(None) if minutes else key).groupby(["trading_date", "_bucket"], sort=True)
    agg = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                volume=("volume", "sum"), n_bars=("ts_utc", "size"), first_ts=("ts_utc", "min"), last_ts=("ts_utc", "max"),
                segment_id=("segment_id", "first"), symbol=("symbol", "first")).reset_index()
    if minutes:
        open_ny = pd.DatetimeIndex(agg["_bucket"]).tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
        end_ny = open_ny + pd.Timedelta(minutes=minutes)
        # nominal session close caps the bucket end (e.g. 16:45 15m candle ends 17:00; early-close sessions end earlier
        # but by wall-clock the bucket is only known complete at bucket end)
        agg["ts_ny"] = open_ny
        agg["ts_utc"] = open_ny.tz_convert("UTC")
        agg["available_ts_utc"] = end_ny.tz_convert("UTC")
        agg["expected_bars"] = minutes
    else:
        td = pd.DatetimeIndex(agg["trading_date"])
        open_local = (td - pd.Timedelta(days=1) + pd.Timedelta(minutes=session_open_minute)).tz_localize("America/New_York")
        close_local = (td + pd.Timedelta(minutes=session_close_minute)).tz_localize("America/New_York")
        agg["ts_ny"] = open_local; agg["ts_utc"] = open_local.tz_convert("UTC")
        agg["available_ts_utc"] = close_local.tz_convert("UTC")
        agg["expected_bars"] = ((close_local - open_local).total_seconds() // 60).astype(int)
    agg["close_ts_utc"] = agg["last_ts"] + pd.Timedelta(minutes=1)
    agg["complete"] = agg["n_bars"] == agg["expected_bars"]
    agg = agg.sort_values("ts_utc").reset_index(drop=True)
    if minutes:
        prev_end = agg["ts_utc"].shift() + pd.Timedelta(minutes=minutes)
        agg["consecutive_prev"] = (prev_end == agg["ts_utc"]).fillna(False).to_numpy()
    else:
        agg["consecutive_prev"] = np.r_[False, np.ones(len(agg) - 1, dtype=bool)] if len(agg) else np.zeros(0, dtype=bool)
    return agg[CANDLE_COLS]


def available_mask(candles: pd.DataFrame, at_ts_utc) -> np.ndarray:
    """Candles whose available_ts_utc <= at_ts_utc (causal selection)."""
    return naive_utc(candles["available_ts_utc"]) <= naive_utc(at_ts_utc)
