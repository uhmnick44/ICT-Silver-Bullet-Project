"""Layer 5 null models (researcher-selected conventions 5-7; not screenshot-verified procedures).

Null A — randomized entry: for every actual trade of a configuration, a random bar inside the SAME eligible
          window on the SAME trading date, market entry at that bar's open (first executable price), the same
          direction (direction composition preserved exactly), the same planned risk distance and target R, the
          production exit rules (stop-first, strict target trade-through, rth_end time exit), costs and slippage.
          One position at a time: a draw that overlaps the previous null position is redrawn (up to 20 times) and
          otherwise dropped (counted). 1,000 iterations, fixed seed.
Null B — off-hour windows: the same strategy logic run in each eligible non-overlapping 60-minute window of the
          CME session outside the three Silver Bullet windows and the maintenance break (20 windows: 18:00 ... 16:00
          ET starts), with window eligibility = every minute present and the session neither truncated nor
          non-causal. Pre-window liquidity levels and sweeps are recomputed with the Layer 2 detectors for the
          extended window set; other levels are unchanged.
Null C — shuffled direction: each actual setup's direction is independently flipped with p = 0.5 (fixed seed), and
          the trade is RE-SIMULATED: same activation bar, same limit price, same risk distance and target R, with the
          production limit-fill rule for the (possibly inverted) direction, exits and costs. 1,000 iterations.
For every null the statistic is the mean net R of the iteration; the actual value's position in the null
distribution is reported as a one-sided exceedance probability P(null >= actual). Exceeding the null mean alone is
not treated as significance.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..engine.backtest import FeatureStore, run_backtest
from ..engine.exec_config import Layer3Config
from ..engine.execution import simulate_template
from ..engine.sessions import SessionSpec
from ..features.liquidity import build_liquidity_levels
from ..features.sweeps import detect_sweeps
from ..features.timeframes import naive_utc, resample
from ..features.windows import window_table

NULL_ITERATIONS = 1000
NULL_SEED_A = 20261105
NULL_SEED_C = 20261107
OFFHOUR_STARTS = [h for h in range(24) if h not in (3, 10, 14, 17)]          # 20 hourly windows; 17 = maintenance
OFFHOUR_WINDOWS = {f"oh_{h:02d}00": (h * 60, h * 60 + 60) for h in OFFHOUR_STARTS}


@dataclass
class Template:
    direction: str; k_activate: int; iE: int; iT: int; risk_points: float; target_r: float | None; limit: float; w_start: int; w_end: int


def trade_templates(trades: pd.DataFrame, store: FeatureStore) -> list[Template]:
    """Templates from a configuration's development trade log (chronological)."""
    bars = store.bars; ss = store.sessions
    win = store.feats["windows"].set_index(["trading_date", "window"])
    out = []
    for r in trades.sort_values("entry_fill_ts_utc").itertuples():
        ws, we = win.loc[(r.trading_date, r.window), ["start_ts_utc", "end_ts_utc"]]
        d = pd.Timestamp(r.trading_date)
        rth_end = ss.session_close_utc(d) - pd.Timedelta(minutes=ss.close_minute - ss.windows["rth"][1])
        out.append(Template(direction=r.direction, k_activate=bars.index_at_or_after(r.order_active_ts_utc), iE=bars.index_at_or_after(we),
                            iT=bars.index_at_or_after(rth_end), risk_points=float(r.planned_risk_points),
                            target_r=(float(r.planned_reward_r) if pd.notna(r.planned_reward_r) else None), limit=float(r.entry_limit),
                            w_start=bars.index_at_or_after(ws), w_end=bars.index_at_or_after(we)))
    return out


def _iteration_stats(results: list[dict]) -> dict:
    if not results:
        return {"n": 0, "mean_net_r": np.nan, "net_pnl_usd": np.nan}
    r = np.array([x["net_r"] for x in results]); p = np.array([x["net_pnl_usd"] for x in results])
    return {"n": len(r), "mean_net_r": float(r.mean()), "net_pnl_usd": float(p.sum())}


def null_a_random_entry(templates: list[Template], store: FeatureStore, cfg: Layer3Config, n_iter: int = NULL_ITERATIONS, seed: int = NULL_SEED_A) -> pd.DataFrame:
    rng = np.random.default_rng(seed); rows = []
    for it in range(n_iter):
        res = []; last_exit = -1; dropped = 0
        for t in templates:
            k = None
            for _ in range(20):
                cand = int(rng.integers(t.w_start, t.w_end))
                if cand > last_exit:
                    k = cand; break
            if k is None:
                dropped += 1; continue
            s = simulate_template(store.bars, cfg, store.spec, direction=t.direction, k_activate=k, iE=t.iE, iT=t.iT, risk_points=t.risk_points, target_r=t.target_r, entry_mode="market")
            if s is None:
                dropped += 1; continue
            res.append(s); last_exit = s["exit_index"]
        rows.append({"iteration": it, **_iteration_stats(res), "dropped": dropped})
    return pd.DataFrame(rows)


def null_c_shuffled_direction(templates: list[Template], store: FeatureStore, cfg: Layer3Config, n_iter: int = NULL_ITERATIONS, seed: int = NULL_SEED_C) -> pd.DataFrame:
    rng = np.random.default_rng(seed); rows = []
    for it in range(n_iter):
        flips = rng.random(len(templates)) < 0.5
        res = []; last_exit = -1; dropped = 0; unfilled = 0
        for t, f in zip(templates, flips):
            d = t.direction if not f else ("bearish" if t.direction == "bullish" else "bullish")
            if t.k_activate <= last_exit:
                dropped += 1; continue
            s = simulate_template(store.bars, cfg, store.spec, direction=d, k_activate=t.k_activate, iE=t.iE, iT=t.iT, risk_points=t.risk_points, target_r=t.target_r, entry_mode="limit", limit=t.limit)
            if s is None:
                unfilled += 1; continue
            res.append(s); last_exit = s["exit_index"]
        rows.append({"iteration": it, **_iteration_stats(res), "dropped": dropped, "unfilled": unfilled, "flipped": int(flips.sum())})
    return pd.DataFrame(rows)


def exceedance(null_values: np.ndarray, actual: float) -> dict:
    v = np.asarray(null_values, float); v = v[~np.isnan(v)]
    return {"null_mean": float(v.mean()), "null_sd": float(v.std(ddof=1)), "null_p5": float(np.percentile(v, 5)), "null_p95": float(np.percentile(v, 95)),
            "actual": float(actual), "p_null_ge_actual": float(((v >= actual).sum() + 1) / (len(v) + 1)), "percentile_of_actual": float((v < actual).mean() * 100)}


# ----------------------------------------------------------------------------- Null B infrastructure
def offhour_store(base: FeatureStore, liq_cfg, sweep_cfg) -> FeatureStore:
    """A FeatureStore whose window table, pre-window liquidity levels and sweeps cover the 20 off-hour windows."""
    ss = base.sessions
    ext = SessionSpec(timezone=ss.timezone, open_minute=ss.open_minute, close_minute=ss.close_minute, maintenance_start=ss.maintenance_start,
                      maintenance_end=ss.maintenance_end, full_session_minutes=ss.full_session_minutes, windows={**ss.windows, **OFFHOUR_WINDOWS})
    bars = base.data.bars
    sess = base.data.sessions.copy()
    for w, (a, b) in OFFHOUR_WINDOWS.items():
        mod = bars["minute_of_day_ny"]
        cnt = bars[(mod >= a) & (mod < b)].groupby("trading_date").size()
        sess[f"n_bars_{w}"] = sess["trading_date"].map(cnt).fillna(0).astype(int)
        sess[f"eligible_{w}"] = (sess[f"n_bars_{w}"] == b - a) & ~sess["is_truncated_final"] & ~sess["noncausal_contract_selection"]
    names = tuple(OFFHOUR_WINDOWS)
    wt = window_table(sess, ext, names, base.data.series_id)
    levels = build_liquidity_levels(bars, ext, liq_cfg, names, base.data.series_id)
    sweeps, levels = detect_sweeps(resample(bars, sweep_cfg.timeframe), levels, sweep_cfg, liq_cfg, base.spec.tick_size, ext, base.data.series_id, names)
    feats = dict(base.feats); feats["windows"] = wt; feats["liquidity_levels"] = levels; feats["sweeps"] = sweeps
    st = FeatureStore(base.data, feats, base.l1cfg, base.l2_hash, base.source + "+offhour")
    st.sessions = ext
    return st
