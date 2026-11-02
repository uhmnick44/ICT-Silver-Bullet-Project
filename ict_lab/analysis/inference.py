"""Layer 5 population inference: stationary bootstrap (CI + null-centred one-sided p) for every evaluated
configuration, Benjamini-Hochberg FDR at q = 0.10 across the COMPLETE canonical population, descriptive screens
and qualification tiers. Runs only on the recorded development sweep (no re-simulation).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .grid import OUT
from .stats import (BLOCK_LENGTH, BLOCK_LENGTH_SENSITIVITY, BOOTSTRAP_SEED, FDR_Q, benjamini_hochberg, passes_descriptive_screen,
                    performance_metrics, qualify, stationary_block_bootstrap)


def eligible_dates_for(windows_str: str, win: pd.DataFrame) -> np.ndarray:
    ws = windows_str.split(";")
    w = win[win["window"].isin(ws) & win["eligible"]]
    return np.sort(w["trading_date"].unique())


def run_inference(results: pd.DataFrame, trades: pd.DataFrame, win: pd.DataFrame, block_lengths=(BLOCK_LENGTH,) + tuple(BLOCK_LENGTH_SENSITIVITY)) -> pd.DataFrame:
    groups = {h: g.sort_values("entry_fill_ts_utc") for h, g in trades.groupby("grid_config_hash")}
    rows = []
    for r in results.itertuples(index=False):
        g = groups.get(r.config_hash, trades.iloc[0:0])
        ed = eligible_dates_for(r.windows, win)
        m = performance_metrics(g, ed)
        row = {"config_hash": r.config_hash, "n_trades": m["n_trades"], "net_expectancy_r": m["net_expectancy_r"], "net_sharpe": m["net_sharpe"],
               "net_pnl_usd": m["net_pnl_usd"], "profit_factor": m["profit_factor"], "max_drawdown_usd": m["max_drawdown_usd"], "n_ambiguous": m["n_ambiguous"],
               "eligible_days": int(len(ed)), "status": m["status"], "descriptive_screen": passes_descriptive_screen(m)}
        x = g["net_r"].to_numpy(float) if len(g) else np.zeros(0)
        for bl in block_lengths:
            b = stationary_block_bootstrap(x, bl, seed=BOOTSTRAP_SEED)
            tag = "" if bl == BLOCK_LENGTH else f"_bl{int(bl)}"
            row[f"ci_low{tag}"] = b["ci_low"]; row[f"ci_high{tag}"] = b["ci_high"]; row[f"p_one_sided{tag}"] = b["p_one_sided"]; row[f"ci_above_zero{tag}"] = b["ci_above_zero"]
        rows.append(row)
    df = pd.DataFrame(rows)
    q, rej = benjamini_hochberg(df["p_one_sided"].to_numpy(float), FDR_Q)
    df["q_value"] = q; df["fdr_reject"] = rej
    tiers = []
    for r in df.itertuples(index=False):
        m = {"status": r.status, "n_trades": r.n_trades, "net_sharpe": r.net_sharpe, "net_pnl_usd": r.net_pnl_usd, "net_expectancy_r": r.net_expectancy_r}
        boot = {"status": "ok" if r.p_one_sided is not None and not np.isnan(r.p_one_sided) else "insufficient_data", "ci_above_zero": bool(r.ci_above_zero)}
        tiers.append(qualify(m, bool(r.fdr_reject), boot, None).tier)   # walk-forward consistency filled in later
    df["tier_pre_walkforward"] = tiers
    return df


def main() -> None:
    results = pd.read_csv(OUT / "sweep_results.csv"); trades = pd.read_parquet(OUT / "sweep_trades.parquet")
    from ..engine.backtest import FeatureStore
    from ..engine.config import load_config
    from ..features.config import load_layer2_config
    store = FeatureStore.build(load_config(), load_layer2_config())
    df = run_inference(results, trades, store.feats["windows"])
    df.to_csv(OUT / "inference_results.csv", index=False)
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "population": int(len(df)), "with_p_value": int(df["p_one_sided"].notna().sum()),
               "descriptive_screen": int(df["descriptive_screen"].sum()), "fdr_reject_q10": int(df["fdr_reject"].sum()),
               "fdr_reject_and_screen": int((df["fdr_reject"] & df["descriptive_screen"]).sum()),
               "ci_above_zero": int(df["ci_above_zero"].sum()), "ci_above_zero_and_screen_and_fdr": int((df["ci_above_zero"] & df["descriptive_screen"] & df["fdr_reject"]).sum()),
               "block_length": BLOCK_LENGTH, "sensitivity": list(BLOCK_LENGTH_SENSITIVITY), "seed": BOOTSTRAP_SEED, "fdr_q": FDR_Q,
               "min_raw_p": float(np.nanmin(df["p_one_sided"])), "min_q": float(np.nanmin(df["q_value"]))}
    (OUT / "inference_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
