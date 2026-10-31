"""Synthetic bar builders for Layer 2 tests. Bars are 1-minute, NY wall clock, back-adjusted-style prices."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ict_lab.engine.sessions import SessionSpec


def make_bars(sessions: SessionSpec, start_ny: str, ohlc: list[tuple[float, float, float, float]], volume: int = 10,
              drop_minutes: tuple[str, ...] = (), symbol: str = "MNQH4", segment_id: int = 0) -> pd.DataFrame:
    """Consecutive 1m bars starting at start_ny (America/New_York). `drop_minutes` removes bars (gaps)."""
    t0 = pd.Timestamp(start_ny, tz="America/New_York")
    ts = [t0 + pd.Timedelta(minutes=i) for i in range(len(ohlc))]
    df = pd.DataFrame({"ts_utc": [t.tz_convert("UTC") for t in ts], "open": [float(o) for o, _, _, _ in ohlc], "high": [float(h) for _, h, _, _ in ohlc],
                       "low": [float(l) for _, _, l, _ in ohlc], "close": [float(c) for _, _, _, c in ohlc], "volume": volume, "symbol": symbol,
                       "instrument_id": 1, "segment_id": segment_id})
    drop = {pd.Timestamp(x, tz="America/New_York").tz_convert("UTC") for x in drop_minutes}
    df = df[~df["ts_utc"].isin(drop)].reset_index(drop=True)
    df = sessions.annotate(df)
    gap = df["ts_utc"].diff().dt.total_seconds().div(60)
    df["gap_prev_min"] = gap; df["consecutive_prev"] = (gap.to_numpy() == 1.0)
    df["bar_index"] = np.arange(len(df))
    return df


def flat(n: int, px: float = 100.0, rng: float = 1.0) -> list[tuple[float, float, float, float]]:
    return [(float(px), float(px + rng), float(px - rng), float(px))] * n


def session_bars(sessions: SessionSpec, trading_date: str, px: float = 100.0, rng: float = 1.0, **kw) -> pd.DataFrame:
    """A full 1380-bar session (18:00 previous day -> 16:59) of flat bars."""
    d = pd.Timestamp(trading_date)
    start = (d - pd.Timedelta(days=1)).strftime("%Y-%m-%d") + " 18:00"
    return make_bars(sessions, start, flat(1380, px, rng), **kw)
