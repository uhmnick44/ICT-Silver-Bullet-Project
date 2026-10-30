"""Build the continuous unadjusted and additive back-adjusted 1-minute series from per-contract
bars plus the contract selection table. Both series share exactly the same rows/timestamps."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .instrument import InstrumentSpec
from .sessions import SessionSpec

PRICE_COLS = ["open", "high", "low", "close"]


def build_unadjusted(bars: pd.DataFrame, sel: pd.DataFrame, sessions: SessionSpec) -> pd.DataFrame:
    """Select, for each trading date, the bars of the active contract. No bars are created."""
    active = sel["active_symbol"].rename("active_symbol")
    m = bars.merge(active, left_on="trading_date", right_index=True, how="inner")
    out = m[m["symbol"] == m["active_symbol"]].drop(columns=["active_symbol"]).copy()
    out = out.sort_values("ts_utc", kind="mergesort").reset_index(drop=True)
    if out["ts_utc"].duplicated().any():
        raise RuntimeError("duplicate timestamps in continuous series")
    out["bar_index"] = np.arange(len(out), dtype="int64")
    gap = out["ts_utc"].diff().dt.total_seconds().div(60.0)
    out["gap_prev_min"] = gap.fillna(np.nan).astype("float64")
    out["consecutive_prev"] = (gap.to_numpy() == 1.0)
    sym = out["symbol"].to_numpy(dtype=object)
    change = np.r_[True, sym[1:] != sym[:-1]] if len(sym) else np.zeros(0, dtype=bool)
    out["segment_id"] = (np.cumsum(change) - 1).astype("int32")
    out["is_first_bar_of_contract"] = change
    out["adjustment"] = 0.0
    out["series"] = "unadjusted"
    return out


def build_backadjusted(unadj: pd.DataFrame, roll_log: pd.DataFrame, spec: InstrumentSpec) -> pd.DataFrame:
    """Additive back-adjustment anchored to the latest contract: every bar of segment k gets
    + sum(offsets of rolls after segment k). Tick distances are preserved exactly."""
    adj = unadj.copy()
    n_seg = int(adj["segment_id"].max()) + 1
    if len(roll_log) != n_seg - 1:
        raise RuntimeError(f"segments ({n_seg}) and rolls ({len(roll_log)}) are inconsistent")
    cum = np.zeros(n_seg, dtype="float64")
    if len(roll_log):
        cum[:-1] = roll_log.sort_values("roll_id")["cumulative_adjustment_before_roll"].to_numpy()
        if not np.all(spec.on_tick_grid(cum)):
            raise RuntimeError("cumulative adjustment is not a multiple of the tick size")
    adj["adjustment"] = cum[adj["segment_id"].to_numpy()]
    for c in PRICE_COLS:
        adj[c] = unadj[c].to_numpy() + adj["adjustment"].to_numpy()
    adj["series"] = "backadjusted"
    if not (adj["ts_utc"].to_numpy() == unadj["ts_utc"].to_numpy()).all():
        raise RuntimeError("timestamps diverged between adjusted and unadjusted series")
    return adj
