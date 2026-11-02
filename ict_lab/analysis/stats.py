"""Layer 5 statistical utilities — only the parts fully specified by the Layer 5 brief.

Implemented here (specified): performance metrics after costs with an explicit insufficient-data
status; descriptive screens (>= 100 trades, net Sharpe >= 0.5, positive net P&L); Benjamini–Hochberg
FDR at 10% over the complete hypothesis family; stationary block bootstrap (Politis–Romano) with
1,000 resamples, a fixed seed and a one-sided test of mean net R > 0; qualification tiers.

NOT decided here (awaiting screenshot definitions): the bootstrap block length (a required argument,
no default), the raw p-value source fed into the FDR step (a required argument), grid values,
sampling, null-model procedures, walk-forward folds.

Annualization convention (researcher-selected, Layer 5 convention 2): `net_sharpe` is the annualized
Sharpe of the daily net P&L series in dollars over the ELIGIBLE trading days passed in (dates with an
eligible window for the configuration; days without a trade contribute 0), annualization factor
sqrt(252), zero risk-free rate. `per_trade_sharpe` (mean net R / std net R, not annualized) is reported
for reference. Trade frequency is trades per year with the calendar span of the eligible days / 365.25.

Bootstrap (conventions 3-4): stationary bootstrap (Politis-Romano) with expected block length 10 trades
(sensitivity 5 and 20), 1,000 resamples, fixed seed. The 95% CI for the mean is the percentile interval of
the bootstrap means. The one-sided p-value for H1: mean > 0 is NULL-CENTRED: the series is shifted to
mean zero, resampled, and p = P(bootstrap mean of the centred series >= observed mean). The CI and the
p-value are reported separately. Dependence limitation: trades of different configurations overlap on
the same bars, so the p-values across the population are positively dependent; BH is applied as a
documented assumption of PRDS-type dependence, not proven independence.
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
BLOCK_LENGTH = 10
BLOCK_LENGTH_SENSITIVITY = (5, 20)
BOOTSTRAP_SEED = 20261102


# ----------------------------------------------------------------------------- metrics
def performance_metrics(trades: pd.DataFrame, trading_dates: pd.Series | list, min_trades: int = MIN_TRADES) -> dict:
    """All metrics reflect transaction costs (net_* columns from the Layer 3 engine). Roll-excluded trades are dropped.
    `trading_dates` must be the ELIGIBLE trading days of the configuration's windows (convention 2).
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
def stationary_bootstrap_indices(n: int, block_length: float, n_resamples: int, rng: np.random.Generator) -> np.ndarray:
    """(n_resamples, n) index matrix of the Politis-Romano stationary bootstrap, vectorised: at every position a new
    block starts with probability 1/block_length at a uniformly random start; otherwise the index advances by one,
    wrapping circularly. Geometric block lengths with the requested mean follow from the per-position restart rule."""
    p = 1.0 / float(block_length)
    restart = rng.random((n_resamples, n)) < p
    restart[:, 0] = True
    starts = rng.integers(0, n, size=(n_resamples, n))
    pos = np.arange(n)
    last = np.maximum.accumulate(np.where(restart, pos, 0), axis=1)          # position of the most recent restart
    start_val = np.take_along_axis(starts, last, axis=1)
    return (start_val + (pos - last)) % n


def stationary_block_bootstrap(x: np.ndarray, block_length: float = BLOCK_LENGTH, n_resamples: int = BOOTSTRAP_RESAMPLES,
                               seed: int = BOOTSTRAP_SEED, alpha: float = 0.05) -> dict:
    """Stationary bootstrap of the mean of x (net R per trade in chronological order). Returns the percentile 95% CI of
    the mean (reported separately) and a NULL-CENTRED one-sided p-value for H1: mean > 0."""
    x = np.asarray(x, dtype=float); n = len(x)
    if block_length is None or block_length <= 0:
        raise ValueError("block_length must be a positive number")
    if n < 2:
        return {"status": "insufficient_data", "n": n, "mean_net_r": float(x.mean()) if n else None, "ci_low": None, "ci_high": None,
                "p_one_sided": None, "ci_above_zero": False, "block_length": float(block_length), "n_resamples": n_resamples, "seed": seed}
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(n, block_length, n_resamples, rng)
    means = x[idx].mean(axis=1)                                   # bootstrap distribution of the mean (for the CI)
    centred = (x - x.mean())[idx].mean(axis=1)                    # null distribution (same indices): mean-zero series
    obs = float(x.mean())
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    p = float(((centred >= obs).sum() + 1) / (n_resamples + 1))   # add-one correction keeps p in (0, 1]
    return {"status": "ok", "n": n, "mean_net_r": obs, "boot_mean": float(means.mean()), "ci_low": float(lo), "ci_high": float(hi),
            "p_one_sided": p, "ci_above_zero": bool(lo > 0), "block_length": float(block_length), "n_resamples": n_resamples, "seed": seed,
            "alpha": alpha, "bootstrap_means": means, "null_means": centred}


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
