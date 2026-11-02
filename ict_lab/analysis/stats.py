"""Layer 5 statistical utilities — only the parts fully specified by the Layer 5 brief.

Implemented here (specified): performance metrics after costs with an explicit insufficient-data
status; descriptive screens (>= 100 trades, net Sharpe >= 0.5, positive net P&L); Benjamini–Hochberg
FDR at 10% over the complete hypothesis family; stationary block bootstrap (Politis–Romano) with
1,000 resamples, a fixed seed and a one-sided test of mean net R > 0; qualification tiers.

NOT decided here (awaiting screenshot definitions): the bootstrap block length (a required argument,
no default), the raw p-value source fed into the FDR step (a required argument), grid values,
sampling, null-model procedures, walk-forward folds.

Annualization convention (documented choice, the brief allows one): `net_sharpe` is computed on the
daily net P&L series in dollars over every development trading date in the evaluation range (dates
without a trade contribute 0), annualized with sqrt(252). `per_trade_sharpe` (mean net R / std net R,
not annualized) is reported alongside for reference. Trade frequency is trades per year with the
calendar span of the evaluation range / 365.25.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_TRADES = 100
MIN_NET_SHARPE = 0.5
FDR_Q = 0.10
BOOTSTRAP_RESAMPLES = 1000
TRADING_DAYS_PER_YEAR = 252


# ----------------------------------------------------------------------------- metrics
def performance_metrics(trades: pd.DataFrame, trading_dates: pd.Series | list, min_trades: int = MIN_TRADES) -> dict:
    """All metrics reflect transaction costs (net_* columns from the Layer 3 engine). Roll-excluded trades are dropped.
    Returns status 'ok' or 'insufficient_data' (metrics that cannot be computed are None, never fabricated)."""
    t = trades[~trades["excluded_by_roll_policy"]] if len(trades) and "excluded_by_roll_policy" in trades else trades
    dates = pd.DatetimeIndex(pd.to_datetime(pd.Series(trading_dates))).unique().sort_values()
    span_years = ((dates.max() - dates.min()).days / 365.25) if len(dates) > 1 else np.nan
    n = int(len(t))
    out = {"n_trades": n, "n_ambiguous": int(t["same_bar_ambiguous"].sum()) if n else 0, "n_excluded_roll": int(len(trades) - n),
           "trading_dates_in_range": int(len(dates)), "span_years": span_years, "status": "ok" if n >= min_trades else "insufficient_data",
           "net_expectancy_r": None, "net_pnl_usd": None, "net_sharpe": None, "per_trade_sharpe": None, "profit_factor": None, "win_rate": None,
           "max_drawdown_usd": None, "max_drawdown_r": None, "avg_win_r": None, "avg_loss_r": None, "trades_per_year": None, "gross_expectancy_r": None}
    if n == 0:
        return out
    r = t["net_r"].to_numpy(float); pnl = t["net_pnl_usd"].to_numpy(float)
    out["net_expectancy_r"] = float(r.mean()); out["gross_expectancy_r"] = float(t["gross_r"].mean()); out["net_pnl_usd"] = float(pnl.sum())
    out["per_trade_sharpe"] = float(r.mean() / r.std(ddof=1)) if n > 1 and r.std(ddof=1) > 0 else None
    daily = pd.Series(pnl, index=pd.to_datetime(t["trading_date"])).groupby(level=0).sum().reindex(dates, fill_value=0.0)
    out["net_sharpe"] = float(daily.mean() / daily.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)) if len(daily) > 1 and daily.std(ddof=1) > 0 else None
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    out["profit_factor"] = float(wins.sum() / -losses.sum()) if losses.sum() < 0 else (float("inf") if wins.sum() > 0 else None)
    out["win_rate"] = float((pnl > 0).mean())
    eq = np.cumsum(pnl); out["max_drawdown_usd"] = float((np.maximum.accumulate(eq) - eq).max())
    eqr = np.cumsum(r); out["max_drawdown_r"] = float((np.maximum.accumulate(eqr) - eqr).max())
    rw, rl = r[r > 0], r[r < 0]
    out["avg_win_r"] = float(rw.mean()) if len(rw) else None; out["avg_loss_r"] = float(rl.mean()) if len(rl) else None
    out["trades_per_year"] = float(n / span_years) if span_years and span_years > 0 else None
    return out


def passes_descriptive_screen(m: dict) -> bool:
    return m["status"] == "ok" and m["n_trades"] >= MIN_TRADES and m["net_sharpe"] is not None and m["net_sharpe"] >= MIN_NET_SHARPE and m["net_pnl_usd"] > 0


# ----------------------------------------------------------------------------- multiple testing
def benjamini_hochberg(pvalues: np.ndarray | list, q: float = FDR_Q) -> tuple[np.ndarray, np.ndarray]:
    """BH step-up over the COMPLETE family. Returns (q_values, reject) aligned with the input order.
    NaN p-values (insufficient data) stay in the family count but can never be rejected."""
    p = np.asarray(pvalues, dtype=float); m = len(p)
    qv = np.full(m, np.nan); rej = np.zeros(m, dtype=bool)
    if m == 0:
        return qv, rej
    valid = ~np.isnan(p)
    pv = p.copy(); pv[~valid] = 1.0                       # treated as the weakest evidence; family size m is kept
    order = np.argsort(pv, kind="mergesort"); ranked = pv[order]
    adj = ranked * m / (np.arange(1, m + 1))
    adj = np.minimum.accumulate(adj[::-1])[::-1]; adj = np.minimum(adj, 1.0)
    qv[order] = adj; qv[~valid] = np.nan
    rej = (qv <= q) & valid
    return qv, rej


# ----------------------------------------------------------------------------- bootstrap
def stationary_block_bootstrap(x: np.ndarray, block_length: float, n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = 20261102,
                               alpha: float = 0.05) -> dict:
    """Politis–Romano stationary bootstrap of the mean of x (net R per trade in chronological order).
    Blocks have geometric lengths with mean `block_length` (p = 1/block_length), wrapping circularly, which
    preserves temporal dependence. One-sided p-value for H1: mean > 0 is the fraction of bootstrap means <= 0.
    The block length is a required input: the screenshot convention is not yet established."""
    x = np.asarray(x, dtype=float); n = len(x)
    if block_length is None or block_length <= 0:
        raise ValueError("block_length must be a positive number (screenshot convention not yet established)")
    if n < 2:
        return {"status": "insufficient_data", "n": n}
    rng = np.random.default_rng(seed); p = 1.0 / float(block_length)
    means = np.empty(n_resamples)
    for b in range(n_resamples):
        idx = np.empty(n, dtype=int); i = 0
        while i < n:
            start = int(rng.integers(0, n)); length = int(rng.geometric(p))
            k = min(length, n - i)
            idx[i:i + k] = (start + np.arange(k)) % n; i += k
        means[b] = x[idx].mean()
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"status": "ok", "n": n, "mean_net_r": float(x.mean()), "boot_mean": float(means.mean()), "ci_low": float(lo), "ci_high": float(hi),
            "p_one_sided": float((means <= 0).mean()), "ci_above_zero": bool(lo > 0), "block_length": float(block_length),
            "n_resamples": n_resamples, "seed": seed, "alpha": alpha, "bootstrap_means": means}


# ----------------------------------------------------------------------------- qualification
@dataclass
class Qualification:
    exploratory: bool = True
    descriptive_screen: bool = False
    fdr_pass: bool = False
    ci_above_zero: bool = False
    walk_forward_consistent: bool | None = None
    tier: str = "exploratory"
    reasons: list[str] = field(default_factory=list)


def qualify(metrics: dict, fdr_reject: bool, boot: dict | None, walk_forward_consistent: bool | None) -> Qualification:
    """Tiers: exploratory < descriptive_screen < fdr_pass < full_evidence_standard. The full standard needs positive
    net expectancy, a 95% bootstrap CI entirely above zero and supporting walk-forward consistency. No tier is a
    claim of profitability."""
    q = Qualification()
    q.descriptive_screen = passes_descriptive_screen(metrics)
    if not q.descriptive_screen:
        q.reasons.append("fails descriptive screen (>=100 trades, net Sharpe >= 0.5, positive net P&L)")
    q.fdr_pass = bool(q.descriptive_screen and fdr_reject)
    if q.descriptive_screen and not fdr_reject:
        q.reasons.append("not significant after BH FDR (q > 0.10)")
    q.ci_above_zero = bool(boot and boot.get("status") == "ok" and boot["ci_above_zero"] and metrics["net_expectancy_r"] > 0)
    q.walk_forward_consistent = walk_forward_consistent
    if q.fdr_pass and q.ci_above_zero and walk_forward_consistent:
        q.tier = "full_evidence_standard"
    elif q.fdr_pass:
        q.tier = "fdr_pass"
        if not q.ci_above_zero: q.reasons.append("95% CI for net expectancy not entirely above zero")
        if not walk_forward_consistent: q.reasons.append("walk-forward consistency not supported or not evaluated")
    elif q.descriptive_screen:
        q.tier = "descriptive_screen"
    return q
