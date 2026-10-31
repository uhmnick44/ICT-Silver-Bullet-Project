"""Canonical Silver Bullet signal sequence (Layer 3 §1) on top of Layer 2 feature tables.

Order of gates per eligible trading window:
  1 window eligibility  2 optional bias  3 confirmed liquidity sweep  4 optional MSS
  5 optional displacement  6 first direction-matching FVG  7 executable setup
A setup's `setup_ts_utc` is the latest confirmation among its required features (always the FVG
confirmation, which cannot precede the others). Nothing after `setup_ts_utc` is read here.

Direction: sellside sweep -> bullish reversal; buyside sweep -> bearish reversal. The FVG must match.
Feature tables are consumed as produced by Layer 2 (no re-derivation).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..features.timeframes import naive_utc
from .exec_config import SignalConfig

GATES = ("window_eligible", "position_free", "bias", "sweep", "mss", "displacement", "fvg")


@dataclass
class Setup:
    trading_date: pd.Timestamp
    window: str
    window_start_utc: pd.Timestamp
    window_end_utc: pd.Timestamp
    direction: str                      # bullish | bearish
    bias: str
    sweep_id: int
    level_type: str
    level_price: float
    sweep_penetration_ts_utc: pd.Timestamp
    sweep_confirmation_ts_utc: pd.Timestamp
    sweep_max_penetration_points: float
    mss_id: int | None
    mss_break_ts_utc: pd.Timestamp | None
    mss_swing_price: float | None
    displacement_ts_utc: pd.Timestamp | None
    displacement_confirmation_ts_utc: pd.Timestamp | None
    displacement_ratio: float | None
    fvg_id: str
    fvg_timeframe: str
    fvg_confirmation_ts_utc: pd.Timestamp
    fvg_upper: float
    fvg_lower: float
    fvg_midpoint: float
    setup_ts_utc: pd.Timestamp
    attempts: int = 0                   # sweeps examined before this one qualified
    # stop reference (approved decision, Layer 3 ambiguity resolution 1): the LATEST qualifying direction-matching
    # displacement candle confirmed after the sweep confirmation and no later than the FVG confirmation; frozen here.
    stop_ref_displacement_ts_utc: pd.Timestamp | None = None
    stop_ref_displacement_confirmation_ts_utc: pd.Timestamp | None = None
    stop_ref_displacement_timeframe: str | None = None
    stop_ref_displacement_ratio: float | None = None


class SortedTable:
    """A feature table sorted by a timestamp column with a naive-UTC int array for searchsorted slicing."""
    def __init__(self, df: pd.DataFrame, ts_col: str):
        self.df = df.sort_values(ts_col, kind="mergesort").reset_index(drop=True) if len(df) else df.reset_index(drop=True)
        self.ts = naive_utc(self.df[ts_col]) if len(df) else np.zeros(0, dtype="datetime64[ns]")

    def between(self, lo, hi) -> pd.DataFrame:
        """rows with lo <= ts < hi"""
        a = int(np.searchsorted(self.ts, naive_utc(lo), side="left")); b = int(np.searchsorted(self.ts, naive_utc(hi), side="left"))
        return self.df.iloc[a:b]


@dataclass
class SignalTables:
    sweeps: SortedTable            # confirmed sweeps only, sorted by confirmation_ts_utc
    mss_by_sweep: dict             # sweep_id -> mss row (found only)
    displacement: SortedTable      # sorted by confirmation_ts_utc
    fvg: SortedTable               # one timeframe, sorted by confirmation_ts_utc
    bias: dict = field(default_factory=dict)   # (trading_date, window) -> bias string


def prepare_tables(feats: dict, cfg: SignalConfig) -> SignalTables:
    sw = feats["sweeps"]
    sw = sw[(sw["status"] == "confirmed") & (sw["level_type"].str.replace(r"_(high|low)$", "", regex=True).isin(cfg.liquidity_types))]
    mss = feats["mss"]; mss = mss[mss["found"]]
    mss_by = {int(r.sweep_id): r for r in mss.itertuples(index=False)}
    disp = feats["displacement"]; disp = disp[disp["range_atr_ratio"] >= cfg.displacement_threshold]
    fv = feats["fvg"]; fv = fv[fv["timeframe"] == cfg.fvg_timeframe]
    if cfg.min_fvg_points > 0:
        fv = fv[fv["gap_points"] >= cfg.min_fvg_points]
    if cfg.min_fvg_atr > 0:
        fv = fv[fv["gap_atr"] >= cfg.min_fvg_atr]
    bias = {}
    if "bias" in feats and len(feats["bias"]):
        b = feats["bias"]
        bias = {(pd.Timestamp(r.trading_date), r.window): r.bias for r in b.itertuples(index=False)}
    return SignalTables(SortedTable(sw, "confirmation_ts_utc"), mss_by, SortedTable(disp, "confirmation_ts_utc"), SortedTable(fv, "confirmation_ts_utc"), bias)


def build_setup(w: pd.Series, tables: SignalTables, cfg: SignalConfig) -> tuple[Setup | None, dict]:
    """First qualifying setup of the window (Layer 3 behaviour). See build_setups for the full list."""
    setups, diag = build_setups(w, tables, cfg)
    return (setups[0] if setups else None), diag


def build_setups(w: pd.Series, tables: SignalTables, cfg: SignalConfig) -> tuple[list[Setup], dict]:
    """All qualifying setups of the window, one per confirmed sweep (its first eligible direction-matching
    FVG), sorted deterministically by (setup_ts, sweep confirmation, sweep_id). Nothing after a setup's
    own setup_ts is used to rank it. The diagnostic names the first failed gate of the attempt that
    progressed furthest when no setup qualifies."""
    start, end = pd.Timestamp(w["start_ts_utc"]), pd.Timestamp(w["end_ts_utc"])
    diag = {"trading_date": w["trading_date"], "window": w["window"], "gate_failed": None, "reason": None, "sweeps_examined": 0}
    if not bool(w["eligible"]):
        diag.update(gate_failed="window_eligible", reason=w["exclusion_reasons"]); return [], diag
    bias = tables.bias.get((pd.Timestamp(w["trading_date"]), w["window"]), "none") if cfg.bias_detector != "none" else "none"
    if cfg.bias_detector != "none" and cfg.require_bias and bias == "none":
        diag.update(gate_failed="bias", reason="no_bias"); return [], diag
    sweeps = tables.sweeps.between(start, end)
    if cfg.require_penetration_in_window and len(sweeps):
        sweeps = sweeps[sweeps["penetration_ts_utc"] >= start]
    if len(sweeps) == 0:
        diag.update(gate_failed="sweep", reason="no_confirmed_sweep_in_window"); return [], diag
    setups: list[Setup] = []
    best_gate, best_reason = -1, None
    def fail(gate_idx, reason):
        nonlocal best_gate, best_reason
        if gate_idx > best_gate:
            best_gate, best_reason = gate_idx, reason
    for n, s in enumerate(sweeps.itertuples(index=False), start=1):
        direction = "bullish" if s.sweep_direction == "bullish_reversal" else "bearish"
        if cfg.bias_detector != "none" and bias != "none" and bias != direction:
            fail(0, f"bias_conflict({bias} vs {direction})"); continue
        t = pd.Timestamp(s.confirmation_ts_utc)
        mss_row = None
        if cfg.require_mss:
            mss_row = tables.mss_by_sweep.get(int(s.sweep_id))
            if mss_row is None or pd.Timestamp(mss_row.break_ts_utc) >= end:
                fail(1, "no_mss_before_window_end"); continue
            t = max(t, pd.Timestamp(mss_row.break_ts_utc))
        disp_row = None
        if cfg.require_displacement:
            d = tables.displacement.between(pd.Timestamp(s.confirmation_ts_utc), end)
            d = d[d["direction"] == direction]
            if len(d) == 0:
                fail(2, "no_displacement_before_window_end"); continue
            disp_row = d.iloc[0]
            t = max(t, pd.Timestamp(disp_row["confirmation_ts_utc"]))
        f = tables.fvg.between(t, end)
        f = f[f["direction"] == direction]
        if len(f) == 0:
            fail(3, "no_direction_matching_fvg_before_window_end"); continue
        fv = f.iloc[0]
        fv_conf = pd.Timestamp(fv["confirmation_ts_utc"])
        ref = tables.displacement.between(pd.Timestamp(s.confirmation_ts_utc), fv_conf + pd.Timedelta(nanoseconds=1))
        ref = ref[ref["direction"] == direction]
        ref_row = ref.iloc[-1] if len(ref) else None
        setup = Setup(trading_date=pd.Timestamp(w["trading_date"]), window=w["window"], window_start_utc=start, window_end_utc=end,
                      direction=direction, bias=bias, sweep_id=int(s.sweep_id), level_type=s.level_type, level_price=float(s.level_price),
                      sweep_penetration_ts_utc=pd.Timestamp(s.penetration_ts_utc), sweep_confirmation_ts_utc=pd.Timestamp(s.confirmation_ts_utc),
                      sweep_max_penetration_points=float(s.max_penetration_points),
                      mss_id=int(mss_row.mss_id) if mss_row is not None else None,
                      mss_break_ts_utc=pd.Timestamp(mss_row.break_ts_utc) if mss_row is not None else None,
                      mss_swing_price=float(mss_row.swing_price) if mss_row is not None else None,
                      displacement_ts_utc=pd.Timestamp(disp_row["ts_utc"]) if disp_row is not None else None,
                      displacement_confirmation_ts_utc=pd.Timestamp(disp_row["confirmation_ts_utc"]) if disp_row is not None else None,
                      displacement_ratio=float(disp_row["range_atr_ratio"]) if disp_row is not None else None,
                      fvg_id=fv["fvg_id"], fvg_timeframe=fv["timeframe"], fvg_confirmation_ts_utc=pd.Timestamp(fv["confirmation_ts_utc"]),
                      fvg_upper=float(fv["upper"]), fvg_lower=float(fv["lower"]), fvg_midpoint=float(fv["midpoint"]),
                      setup_ts_utc=max(t, fv_conf), attempts=n,
                      stop_ref_displacement_ts_utc=pd.Timestamp(ref_row["ts_utc"]) if ref_row is not None else None,
                      stop_ref_displacement_confirmation_ts_utc=pd.Timestamp(ref_row["confirmation_ts_utc"]) if ref_row is not None else None,
                      stop_ref_displacement_timeframe=str(ref_row["timeframe"]) if ref_row is not None else None,
                      stop_ref_displacement_ratio=float(ref_row["range_atr_ratio"]) if ref_row is not None else None)
        assert setup.setup_ts_utc >= setup.sweep_confirmation_ts_utc and setup.setup_ts_utc >= setup.fvg_confirmation_ts_utc
        setups.append(setup)
    diag.update(sweeps_examined=len(sweeps))
    if setups:
        setups.sort(key=lambda x: (x.setup_ts_utc, x.sweep_confirmation_ts_utc, x.sweep_id))
        return setups, diag
    gate = ("bias", "mss", "displacement", "fvg")[best_gate] if best_gate >= 0 else "sweep"
    diag.update(gate_failed=gate, reason=best_reason)
    return [], diag
