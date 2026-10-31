"""Deterministic order, fill and exit simulation on 1-minute bars (Layer 3 §3-§9).

Price basis: the back-adjusted series for all levels and point distances; unadjusted prices are
recovered with the bar's `adjustment` for reporting and for the roll check. Every rule below is
either FIXED by the specification or listed in docs/execution_assumptions.md.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..features.timeframes import naive_utc
from .exec_config import Layer3Config
from .instrument import InstrumentSpec
from .signals import Setup


@dataclass
class BarArrays:
    ts: np.ndarray            # datetime64[ns] naive UTC
    o: np.ndarray; h: np.ndarray; l: np.ndarray; c: np.ndarray
    adj: np.ndarray
    trading_date: np.ndarray  # datetime64[D]
    consecutive: np.ndarray
    symbol: np.ndarray
    minute_of_day: np.ndarray

    @classmethod
    def from_bars(cls, bars: pd.DataFrame) -> "BarArrays":
        b = bars.sort_values("ts_utc").reset_index(drop=True)
        return cls(ts=naive_utc(b["ts_utc"]), o=b["open"].to_numpy(float), h=b["high"].to_numpy(float), l=b["low"].to_numpy(float),
                   c=b["close"].to_numpy(float), adj=b["adjustment"].to_numpy(float),
                   trading_date=pd.DatetimeIndex(b["trading_date"]).to_numpy().astype("datetime64[D]"),
                   consecutive=b["consecutive_prev"].to_numpy(bool), symbol=b["symbol"].to_numpy(dtype=object),
                   minute_of_day=b["minute_of_day_ny"].to_numpy(int))

    def index_at_or_after(self, ts) -> int:
        return int(np.searchsorted(self.ts, naive_utc(ts), side="left"))


# ----------------------------------------------------------------------------- tick helpers
def round_to_tick(price: float, tick: float, mode: str) -> float:
    q = price / tick
    if mode == "down":
        r = np.floor(q + 1e-9)
    elif mode == "up":
        r = np.ceil(q - 1e-9)
    else:
        r = np.round(q)
    return float(r * tick)


def entry_limit_price(setup: Setup, cfg: Layer3Config, spec: InstrumentSpec) -> float:
    bull = setup.direction == "bullish"
    proximal, distal = (setup.fvg_upper, setup.fvg_lower) if bull else (setup.fvg_lower, setup.fvg_upper)
    loc = cfg.entry.location
    if loc == "proximal":
        return proximal
    if loc == "distal":
        return distal
    mid = (proximal + distal) / 2.0
    return round_to_tick(mid, spec.tick_size, "down" if bull else "up")   # away from proximal = deeper into the gap


TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}


def displacement_candle_extreme(setup: Setup, bars: BarArrays) -> tuple[float | None, str]:
    """Low (bullish) / high (bearish) of the frozen stop-reference displacement candle, aggregated from the
    1m bars inside its bucket [ts, ts + timeframe). Returns (price, status)."""
    if setup.stop_ref_displacement_ts_utc is None:
        return None, "no_displacement_candle_between_sweep_and_fvg"
    t0 = naive_utc(setup.stop_ref_displacement_ts_utc)
    t1 = t0 + np.timedelta64(TF_MINUTES[setup.stop_ref_displacement_timeframe], "m")
    a = int(np.searchsorted(bars.ts, t0, side="left")); b = int(np.searchsorted(bars.ts, t1, side="left"))
    if b <= a:
        return None, "displacement_candle_bars_missing"
    if setup.stop_ref_displacement_confirmation_ts_utc > setup.setup_ts_utc:
        return None, "displacement_candle_not_completed_at_setup"
    return (float(bars.l[a:b].min()) if setup.direction == "bullish" else float(bars.h[a:b].max())), "ok"


def stop_price(setup: Setup, entry: float, cfg: Layer3Config, spec: InstrumentSpec, bars: BarArrays | None = None) -> tuple[float | None, str]:
    bull = setup.direction == "bullish"
    buf = cfg.stop.buffer_ticks * spec.tick_size
    if cfg.stop.type == "fvg_distal":
        raw = setup.fvg_lower - buf if bull else setup.fvg_upper + buf
    elif cfg.stop.type == "fixed_points":
        raw = entry - cfg.stop.fixed_points if bull else entry + cfg.stop.fixed_points
    elif cfg.stop.type == "displacement_candle_extreme":
        if bars is None:
            return None, "displacement_candle_extreme requires bars"
        ext, status = displacement_candle_extreme(setup, bars)
        if ext is None:
            return None, status
        raw = ext - buf if bull else ext + buf
    else:
        return None, f"stop type {cfg.stop.type} awaiting definition"
    stop = round_to_tick(raw, spec.tick_size, "down" if bull else "up")
    dist = (entry - stop) if bull else (stop - entry)
    if dist <= 0:
        return None, f"stop_invalid(distance={dist:.2f})"
    return stop, "ok"


def target_price(setup: Setup, entry: float, risk: float, cfg: Layer3Config, spec: InstrumentSpec, levels: pd.DataFrame | None) -> tuple[float | None, str, bool]:
    """Returns (target, source, used_fallback). Opposing liquidity is restricted to levels known and
    active at setup_ts (activated, not expired, not consumed) from the approved universe."""
    bull = setup.direction == "bullish"
    def fixed(r):
        raw = entry + r * risk if bull else entry - r * risk
        return round_to_tick(raw, spec.tick_size, "up" if bull else "down")
    if cfg.target.type == "fixed_r":
        return fixed(cfg.target.r_multiple), f"fixed_{cfg.target.r_multiple}R", False
    if cfg.target.type == "time_only":
        return None, "time_only", False
    at = naive_utc(setup.setup_ts_utc)
    lv = levels
    side = "buyside" if bull else "sellside"
    base = lv["level_type"].str.replace(r"_(high|low)$", "", regex=True)
    m = (lv["side"] == side) & base.isin(cfg.target.opposing_liquidity_types) & (naive_utc(lv["activation_ts_utc"]) <= at)
    exp = naive_utc(lv["expiry_ts_utc"]); con = naive_utc(lv["consumed_ts_utc"])
    m &= np.isnat(exp) | (exp > at)
    m &= np.isnat(con) | (con > at)
    px = lv.loc[m, "price"].to_numpy(float)
    px = px[px > entry + spec.tick_size] if bull else px[px < entry - spec.tick_size]
    if len(px) == 0:
        return fixed(cfg.target.fallback_r_multiple), f"fallback_fixed_{cfg.target.fallback_r_multiple}R", True
    tgt = float(px.min()) if bull else float(px.max())
    return tgt, "opposing_liquidity", False


# ----------------------------------------------------------------------------- simulation
def simulate(setup: Setup, bars: BarArrays, cfg: Layer3Config, spec: InstrumentSpec, levels: pd.DataFrame | None,
             rth_end_utc, roll_ts: np.ndarray) -> tuple[dict | None, dict | None]:
    """Simulate one setup. Returns (trade, None) on a fill or (None, no_trade_diag) otherwise."""
    bull = setup.direction == "bullish"; sgn = 1.0 if bull else -1.0
    tick = spec.tick_size; qty = cfg.sizing.contracts
    limit = entry_limit_price(setup, cfg, spec)
    stop, why = stop_price(setup, limit, cfg, spec, bars)
    base = {"trading_date": setup.trading_date, "window": setup.window, "direction": setup.direction, "setup_ts_utc": setup.setup_ts_utc,
            "entry_limit": limit}
    if stop is None:
        return None, {**base, "gate_failed": "stop", "reason": why}
    risk = (limit - stop) if bull else (stop - limit)
    target, tsrc, fallback = target_price(setup, limit, risk, cfg, spec, levels)
    if target is not None and ((bull and target <= limit) or (not bull and target >= limit)):
        return None, {**base, "gate_failed": "target", "reason": f"target_invalid({target})"}
    i0 = bars.index_at_or_after(setup.setup_ts_utc)
    iE = bars.index_at_or_after(setup.window_end_utc)
    if i0 >= iE:
        return None, {**base, "gate_failed": "entry_fill", "reason": "no_bars_between_setup_and_window_end"}
    # ---- entry
    marketable = (bars.o[i0] < limit) if bull else (bars.o[i0] > limit)
    if marketable:
        if cfg.entry.marketable_at_activation == "cancel":
            return None, {**base, "gate_failed": "entry_fill", "reason": "marketable_at_activation_cancelled"}
        k = i0
    else:
        seg = (bars.l[i0:iE] < limit) if bull else (bars.h[i0:iE] > limit)
        if not seg.any():
            return None, {**base, "gate_failed": "entry_fill", "reason": "order_expired_unfilled_at_window_end", "stop": stop, "target": target}
        k = i0 + int(np.argmax(seg))
    entry_theo = limit
    entry_slip = cfg.costs.entry_slippage_ticks * tick
    entry_price = entry_theo + sgn * entry_slip
    # ---- exit horizon
    if cfg.exit.policy == "window_end":
        iT = iE
    elif cfg.exit.policy == "rth_end":
        iT = bars.index_at_or_after(rth_end_utc)
    else:
        iT = len(bars.ts)
    iT = max(iT, k + 1)
    exit_after_break = bool(iT < len(bars.ts) and cfg.exit.policy != "hold" and bars.trading_date[iT] != bars.trading_date[k])
    lo, hi, op = bars.l[k:iT], bars.h[k:iT], bars.o[k:iT]
    stop_hit = (lo <= stop) if bull else (hi >= stop)
    if target is None:
        tgt_hit = np.zeros(len(lo), dtype=bool)
    elif cfg.target.fill_rule == "touch":
        tgt_hit = (hi >= target) if bull else (lo <= target)
    else:
        tgt_hit = (hi > target) if bull else (lo < target)
    s_idx = int(np.argmax(stop_hit)) if stop_hit.any() else None
    t_idx = int(np.argmax(tgt_hit)) if tgt_hit.any() else None
    ambiguous = False
    if s_idx is not None and (t_idx is None or s_idx <= t_idx):
        j = k + s_idx; reason = "stop"
        ambiguous = t_idx is not None and t_idx == s_idx
        gap_through = (bars.o[j] < stop) if bull else (bars.o[j] > stop)
        exit_theo = bars.o[j] if gap_through else stop
        exit_slip = cfg.costs.stop_slippage_ticks * tick
    elif t_idx is not None:
        j = k + t_idx; reason = "target"
        exit_theo = target
        exit_slip = cfg.costs.target_slippage_ticks * tick
    else:
        if iT >= len(bars.ts):
            j = len(bars.ts) - 1; reason = "end_of_data"; exit_theo = bars.c[j]; exit_slip = 0.0
        else:
            j = iT; reason = "time_exit_window" if cfg.exit.policy == "window_end" else "time_exit_rth"
            exit_theo = bars.o[j]; exit_slip = cfg.costs.time_exit_slippage_ticks * tick
    exit_price = exit_theo - sgn * exit_slip
    # ---- excursions over the holding period (entry bar through exit bar, inclusive)
    mfe = (bars.h[k:j + 1].max() - entry_theo) if bull else (entry_theo - bars.l[k:j + 1].min())
    mae = (entry_theo - bars.l[k:j + 1].min()) if bull else (bars.h[k:j + 1].max() - entry_theo)
    # ---- money
    gross_points = sgn * (exit_theo - entry_theo)
    gross_pnl = gross_points * spec.point_value * qty
    slip_ticks = (entry_slip + exit_slip) / tick
    slippage_cost = slip_ticks * spec.tick_value * qty
    commission = cfg.costs.per_side * 2 * qty
    net_pnl = gross_pnl - slippage_cost - commission
    risk_usd = risk * spec.point_value * qty
    # ---- roll / data flags
    spans_roll = bool(bars.adj[k] != bars.adj[j]) or bool(((roll_ts > bars.ts[k]) & (roll_ts <= bars.ts[j])).any())
    gap_during = bool((~bars.consecutive[k + 1:j + 1]).any())
    trade = {
        **base, "sweep_id": setup.sweep_id, "level_type": setup.level_type, "level_price": setup.level_price,
        "sweep_penetration_ts_utc": setup.sweep_penetration_ts_utc, "sweep_confirmation_ts_utc": setup.sweep_confirmation_ts_utc,
        "mss_id": setup.mss_id, "mss_break_ts_utc": setup.mss_break_ts_utc, "displacement_ts_utc": setup.displacement_ts_utc,
        "displacement_confirmation_ts_utc": setup.displacement_confirmation_ts_utc, "displacement_ratio": setup.displacement_ratio,
        "fvg_id": setup.fvg_id, "fvg_timeframe": setup.fvg_timeframe, "fvg_confirmation_ts_utc": setup.fvg_confirmation_ts_utc,
        "fvg_upper": setup.fvg_upper, "fvg_lower": setup.fvg_lower, "bias": setup.bias, "stop_type": cfg.stop.type,
        "stop_ref_displacement_ts_utc": setup.stop_ref_displacement_ts_utc, "stop_ref_displacement_timeframe": setup.stop_ref_displacement_timeframe,
        "stop_ref_displacement_ratio": setup.stop_ref_displacement_ratio,
        "order_submitted_ts_utc": setup.setup_ts_utc, "order_active_ts_utc": pd.Timestamp(bars.ts[i0], tz="UTC"),
        "marketable_at_activation": bool(marketable),
        "entry_fill_ts_utc": pd.Timestamp(bars.ts[k], tz="UTC"), "entry_price": entry_price, "entry_price_theoretical": entry_theo,
        "stop_price": stop, "target_price": target, "target_source": tsrc, "target_fallback_used": fallback,
        "exit_ts_utc": pd.Timestamp(bars.ts[j], tz="UTC"), "exit_price": exit_price, "exit_price_theoretical": exit_theo, "exit_reason": reason,
        "quantity": qty, "planned_risk_points": risk, "planned_risk_ticks": risk / tick, "planned_risk_usd": risk_usd,
        "planned_reward_points": (abs(target - limit) if target is not None else np.nan),
        "planned_reward_ticks": (abs(target - limit) / tick if target is not None else np.nan),
        "planned_reward_r": (abs(target - limit) / risk if target is not None else np.nan),
        "gross_points": gross_points, "gross_pnl_usd": gross_pnl, "commission_usd": commission, "slippage_ticks": slip_ticks,
        "slippage_cost_usd": slippage_cost, "net_pnl_usd": net_pnl, "gross_r": gross_points / risk, "net_r": net_pnl / risk_usd,
        "mfe_points": float(mfe), "mae_points": float(mae), "mfe_r": float(mfe) / risk, "mae_r": float(mae) / risk,
        "bars_held": int(j - k), "same_bar_ambiguous": bool(ambiguous), "exit_after_session_break": exit_after_break,
        "spans_roll": spans_roll, "excluded_by_roll_policy": bool(spans_roll and cfg.roll.policy == "flag_and_exclude"),
        "gap_during_trade": gap_during, "entry_symbol": bars.symbol[k], "exit_symbol": bars.symbol[j],
        "entry_adjustment": float(bars.adj[k]), "exit_adjustment": float(bars.adj[j]),
        "entry_price_unadjusted": entry_price - bars.adj[k], "exit_price_unadjusted": exit_price - bars.adj[j],
        "stop_price_unadjusted": stop - bars.adj[k], "target_price_unadjusted": (target - bars.adj[k]) if target is not None else np.nan,
        "entry_bar_index": int(k), "exit_bar_index": int(j),
    }
    return trade, None
