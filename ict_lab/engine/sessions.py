"""CME session calendar logic.

Trading date rule (wall-clock, DST-safe): a bar whose America/New_York wall-clock time is at
or after the session open (18:00) belongs to the NEXT calendar date; every other bar belongs
to its own calendar date. Because the Globex session never spans a Sunday 02:00 DST change
(the market is closed Friday 17:00 -> Sunday 18:00), the rule is unaffected by DST.

All windows are half-open [start, end) on NY wall-clock minutes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time

import numpy as np
import pandas as pd

NY_TZ = "America/New_York"


def _parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


@dataclass(frozen=True)
class SessionSpec:
    timezone: str
    open_minute: int          # minutes after midnight, wall clock
    close_minute: int
    maintenance_start: int
    maintenance_end: int
    full_session_minutes: int
    windows: dict[str, tuple[int, int]]

    @classmethod
    def from_config(cls, cfg) -> "SessionSpec":
        s = cfg["session"]
        return cls(timezone=s["timezone"], open_minute=_parse_hhmm(s["open_time"]),
                   close_minute=_parse_hhmm(s["close_time"]),
                   maintenance_start=_parse_hhmm(s["maintenance_start"]),
                   maintenance_end=_parse_hhmm(s["maintenance_end"]),
                   full_session_minutes=int(s["full_session_minutes"]),
                   windows={k: (_parse_hhmm(v[0]), _parse_hhmm(v[1])) for k, v in s["windows"].items()})

    # -- core ------------------------------------------------------------------------------
    def to_local(self, ts_utc: pd.Series | pd.DatetimeIndex) -> pd.Series | pd.DatetimeIndex:
        idx = ts_utc if isinstance(ts_utc, pd.DatetimeIndex) else pd.DatetimeIndex(ts_utc)
        if idx.tz is None:
            raise ValueError("timestamps must be tz-aware UTC")
        loc = idx.tz_convert(self.timezone)
        return loc if isinstance(ts_utc, pd.DatetimeIndex) else pd.Series(loc, index=ts_utc.index)

    def minute_of_day(self, ts_local: pd.DatetimeIndex) -> np.ndarray:
        return (ts_local.hour * 60 + ts_local.minute).to_numpy()

    def trading_date(self, ts_utc: pd.Series | pd.DatetimeIndex) -> np.ndarray:
        """CME trading date for each UTC timestamp, as numpy datetime64[D]."""
        loc = pd.DatetimeIndex(self.to_local(ts_utc))
        mod = self.minute_of_day(loc)
        cal = loc.tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
        return np.where(mod >= self.open_minute, cal + np.timedelta64(1, "D"), cal)

    def session_open_utc(self, trading_date) -> pd.Timestamp:
        """UTC timestamp of the nominal open (18:00 ET the day before the trading date)."""
        d = pd.Timestamp(trading_date)
        local = (d - pd.Timedelta(days=1)) + pd.Timedelta(minutes=self.open_minute)
        return local.tz_localize(self.timezone).tz_convert("UTC")

    def session_close_utc(self, trading_date) -> pd.Timestamp:
        """UTC timestamp of the nominal close (17:00 ET on the trading date; last bar is 16:59)."""
        d = pd.Timestamp(trading_date)
        local = d + pd.Timedelta(minutes=self.close_minute)
        return local.tz_localize(self.timezone).tz_convert("UTC")

    def expected_session_minutes(self, trading_date) -> pd.DatetimeIndex:
        """Every nominal 1-minute bar timestamp (UTC) of a full session for `trading_date`."""
        o = self.session_open_utc(trading_date)
        c = self.session_close_utc(trading_date)
        return pd.date_range(o, c, freq="1min", inclusive="left")

    def in_window(self, ts_local: pd.DatetimeIndex, name: str) -> np.ndarray:
        a, b = self.windows[name]
        mod = self.minute_of_day(ts_local)
        return (mod >= a) & (mod < b)

    def in_maintenance(self, ts_local: pd.DatetimeIndex) -> np.ndarray:
        mod = self.minute_of_day(ts_local)
        return (mod >= self.maintenance_start) & (mod < self.maintenance_end)

    def annotate(self, df: pd.DataFrame, ts_col: str = "ts_utc") -> pd.DataFrame:
        """Add ts_ny, trading_date, minute_of_day, weekday and window flags to a bar frame."""
        out = df.copy()
        loc = pd.DatetimeIndex(out[ts_col]).tz_convert(self.timezone)
        out["ts_ny"] = loc
        out["trading_date"] = pd.to_datetime(self.trading_date(pd.DatetimeIndex(out[ts_col])))
        out["minute_of_day_ny"] = self.minute_of_day(loc).astype("int16")
        out["weekday_ny"] = loc.weekday.astype("int8")
        for name in self.windows:
            out[f"in_{name}"] = self.in_window(loc, name)
        out["in_maintenance"] = self.in_maintenance(loc)
        return out

    def window_minutes(self, name: str) -> int:
        a, b = self.windows[name]
        return b - a
