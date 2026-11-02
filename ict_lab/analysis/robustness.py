"""Layer 5 robustness, subperiod, sample-size and walk-forward analyses (researcher-selected conventions 10-13).
All are ANALYTIC re-aggregations of the recorded development trade logs: no fill or exit can change under a
fee multiplier or a slippage change in this engine (slippage is applied after the exit price is determined and
entry/target slippage is zero), so no re-simulation is required and the trade set is identical across levels.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .stats import MIN_NET_SHARPE, MIN_TRADES, performance_metrics

FEE_MULTIPLIERS = (1.0, 1.5, 2.0)
STOP_SLIPPAGE_TICKS = (0, 1, 2, 3)
TIME_SLIPPAGE_TICKS = (0, 1, 2)


def recost(trades: pd.DataFrame, fee_mult: float, stop_ticks: int, time_ticks: int, tick_value: float = 0.5) -> pd.DataFrame:
    """Recompute net P&L / net R per trade under alternative fee and slippage assumptions (analytic)."""
    t = trades.copy()
    qty = t["quantity"].to_numpy(float)
    slip_ticks = np.where(t["exit_reason"] == "stop", stop_ticks, np.where(t["exit_reason"].str.startswith("time_exit"), time_ticks, 0)).astype(float)
    t["slippage_ticks"] = slip_ticks; t["slippage_cost_usd"] = slip_ticks * tick_value * qty
    t["commission_usd"] = t["commission_usd"] * fee_mult
    t["net_pnl_usd"] = t["gross_pnl_usd"] - t["slippage_cost_usd"] - t["commission_usd"]
    t["net_r"] = t["net_pnl_usd"] / t["planned_risk_usd"]
    return t


def cost_sensitivity(trades: pd.DataFrame, eligible_dates) -> pd.DataFrame:
    rows = []
    for fm in FEE_MULTIPLIERS:
        for st in STOP_SLIPPAGE_TICKS:
            for tt in TIME_SLIPPAGE_TICKS:
                m = performance_metrics(recost(trades, fm, st, tt), eligible_dates)
                rows.append({"fee_multiplier": fm, "stop_slippage_ticks": st, "time_exit_slippage_ticks": tt, "method": "analytic_recost",
                             **{k: m[k] for k in ("n_trades", "net_expectancy_r", "net_sharpe", "net_pnl_usd", "profit_factor", "max_drawdown_usd", "status")}})
    return pd.DataFrame(rows)


def subperiods(trades: pd.DataFrame, eligible_dates, dev_start: pd.Timestamp, dev_end: pd.Timestamp) -> pd.DataFrame:
    """Chronological annual and quarterly subperiods by trade entry date; partial periods flagged explicitly."""
    ed = pd.DatetimeIndex(pd.to_datetime(pd.Series(eligible_dates))).sort_values()
    rows = []
    for freq, label in (("Y", "annual"), ("Q", "quarterly")):
        for per, g in trades.groupby(pd.to_datetime(trades["trading_date"]).dt.to_period(freq)):
            ps, pe = per.start_time.normalize(), per.end_time.normalize()
            partial = ps < dev_start or pe > dev_end
            dates = ed[(ed >= ps) & (ed <= pe)]
            m = performance_metrics(g, dates)
            rows.append({"granularity": label, "period": str(per), "period_start": ps.date(), "period_end": pe.date(), "partial_period": bool(partial),
                         "eligible_days": int(len(dates)), **{k: m[k] for k in ("n_trades", "net_expectancy_r", "net_sharpe", "net_pnl_usd", "profit_factor", "max_drawdown_usd", "status")}})
    return pd.DataFrame(rows)


def sample_size_sensitivity(trades: pd.DataFrame, eligible_dates, fractions=(0.25, 0.5, 0.75, 1.0)) -> pd.DataFrame:
    """Metrics on the chronologically first 25/50/75/100% of a configuration's trades (no retrospective reselection)."""
    t = trades.sort_values("entry_fill_ts_utc").reset_index(drop=True)
    ed = pd.DatetimeIndex(pd.to_datetime(pd.Series(eligible_dates))).sort_values()
    rows = []
    for f in fractions:
        k = int(np.ceil(len(t) * f)); sub = t.iloc[:k]
        last = pd.Timestamp(sub["trading_date"].max()) if k else None
        dates = ed[ed <= last] if last is not None else ed[:0]
        m = performance_metrics(sub, dates)
        rows.append({"fraction": f, "n_trades": k, "through_date": last.date() if last is not None else None,
                     **{k2: m[k2] for k2 in ("net_expectancy_r", "net_sharpe", "net_pnl_usd", "profit_factor", "status")}})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- walk-forward (convention 11)
def walk_forward_folds(dev_start: pd.Timestamp, dev_end: pd.Timestamp, initial_months: int = 12, eval_months: int = 3) -> list[dict]:
    """Expanding chronological folds: training = dev_start .. fold_start-1, evaluation = next `eval_months` calendar months,
    non-overlapping; the first evaluation fold starts after `initial_months`. A trailing partial fold is kept and flagged."""
    first_eval = (pd.Timestamp(dev_start).normalize().replace(day=1) + pd.DateOffset(months=initial_months))
    folds = []; es = first_eval; k = 1
    while es <= dev_end:
        ee = min(es + pd.DateOffset(months=eval_months) - pd.Timedelta(days=1), dev_end)
        folds.append({"fold": k, "train_start": pd.Timestamp(dev_start), "train_end": es - pd.Timedelta(days=1), "eval_start": es, "eval_end": ee,
                      "partial_fold": bool(ee < es + pd.DateOffset(months=eval_months) - pd.Timedelta(days=1))})
        es = es + pd.DateOffset(months=eval_months); k += 1
    return folds


def walk_forward(sweep_trades: pd.DataFrame, eligible_dates_by_config: dict, dev_start, dev_end, min_train_trades: int = 100,
                 min_train_sharpe: float = MIN_NET_SHARPE, top_k: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """For each fold: rank every configuration on TRAINING trades only (positive training net P&L, >= min_train_trades,
    training net Sharpe >= min_train_sharpe, ranked by training net expectancy in R), freeze the top_k, then evaluate
    them on the evaluation fold. Selection never sees evaluation trades. Returns (per-fold selections, fold summary)."""
    ed_all = {h: pd.DatetimeIndex(pd.to_datetime(pd.Series(v))) for h, v in eligible_dates_by_config.items()}
    folds = walk_forward_folds(pd.Timestamp(dev_start), pd.Timestamp(dev_end))
    td = pd.to_datetime(sweep_trades["trading_date"])
    sel_rows, fold_rows = [], []
    for f in folds:
        train = sweep_trades[td <= f["train_end"]]; ev = sweep_trades[(td >= f["eval_start"]) & (td <= f["eval_end"])]
        cands = []
        for h, g in train.groupby("grid_config_hash"):
            ed = ed_all[h]; m = performance_metrics(g, ed[ed <= f["train_end"]], min_trades=min_train_trades)
            if m["status"] == "ok" and m["net_pnl_usd"] > 0 and m["net_sharpe"] is not None and m["net_sharpe"] >= min_train_sharpe:
                cands.append((h, m))
        cands.sort(key=lambda x: -x[1]["net_expectancy_r"])
        chosen = cands[:top_k]
        for rank, (h, m) in enumerate(chosen, start=1):
            g = ev[ev["grid_config_hash"] == h]; ed = ed_all[h]
            me = performance_metrics(g, ed[(ed >= f["eval_start"]) & (ed <= f["eval_end"])], min_trades=1)
            sel_rows.append({"fold": f["fold"], "rank": rank, "config_hash": h, "train_n": m["n_trades"], "train_net_r": m["net_expectancy_r"], "train_sharpe": m["net_sharpe"],
                             "eval_n": me["n_trades"], "eval_net_r": me["net_expectancy_r"], "eval_net_pnl": me["net_pnl_usd"], "eval_sharpe": me["net_sharpe"], "partial_fold": f["partial_fold"]})
        fold_rows.append({**{k: (v.date() if isinstance(v, pd.Timestamp) else v) for k, v in f.items()}, "n_candidates": len(cands), "n_selected": len(chosen),
                          "selected_top1": chosen[0][0] if chosen else None,
                          "eval_net_r_top1": next((r["eval_net_r"] for r in sel_rows if r["fold"] == f["fold"] and r["rank"] == 1), None)})
    return pd.DataFrame(sel_rows), pd.DataFrame(fold_rows)
