"""Layer 4 frequency diagnostics for the named configurations (development data only).

Reports signal frequency (qualifying setups) separately from order and fill frequency. No profitability
or performance metric is computed here by design.

Usage: python -m ict_lab.analysis.frequency [--configs as_taught_5m,as_taught_1m,as_traded]
Outputs: analysis/frequency_report.csv, analysis/frequency_report.md, analysis/no_trade_reasons.csv, analysis/named_configs_manifest.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..engine.backtest import FeatureStore, run_backtest, write_backtest
from ..engine.config import load_config
from ..engine.exec_config import NAMED_CONFIGS, load_named_config
from ..engine.manifest import software_versions
from ..features.config import load_layer2_config

OUT = Path(__file__).resolve().parent
FORBIDDEN_METRICS = ("net_pnl", "win_rate", "sharpe", "profit_factor", "expectancy", "drawdown")


def frequency_rows(name: str, cfg, res: dict, store: FeatureStore) -> tuple[list[dict], pd.DataFrame]:
    ws = res["window_stats"]; tr = res["trades"]; nd = res["no_trade"]
    bars = store.data.bars
    dev_dates = sorted(bars["trading_date"].unique())
    years = (pd.Timestamp(dev_dates[-1]) - pd.Timestamp(dev_dates[0])).days / 365.25
    rows = []
    for scope in ("all", "sb_london", "sb_ny_am", "sb_ny_pm"):
        w = ws if scope == "all" else ws[ws["window"] == scope]
        t = tr if scope == "all" else tr[tr["window"] == scope]
        if scope != "all" and scope not in cfg.signal.windows:
            continue
        elig = w[w["eligible"]]
        dates_with_trade = t["trading_date"].nunique()
        dates_with_elig = elig["trading_date"].nunique()
        per_date = t.groupby("trading_date").size() if len(t) else pd.Series(dtype=int)
        dist = {f"dates_with_{k}_trades": int(v) for k, v in per_date.value_counts().sort_index().items()}
        dist["dates_with_0_trades"] = int(dates_with_elig - dates_with_trade)
        rows.append({
            "config": name, "scope": scope,
            "windows_registered": int(len(w)), "windows_eligible": int(len(elig)), "windows_ineligible_excluded": int((~w["eligible"]).sum()),
            "windows_with_qualifying_setup": int((elig["n_setups"] > 0).sum()),
            "pct_eligible_windows_with_setup": round(100 * (elig["n_setups"] > 0).mean(), 2) if len(elig) else 0.0,
            "windows_with_filled_trade": int((elig["n_filled"] > 0).sum()),
            "pct_eligible_windows_with_fill": round(100 * (elig["n_filled"] > 0).mean(), 2) if len(elig) else 0.0,
            "trading_dates_with_eligible_window": int(dates_with_elig), "trading_dates_with_filled_trade": int(dates_with_trade),
            "pct_trading_dates_with_filled_trade": round(100 * dates_with_trade / dates_with_elig, 2) if dates_with_elig else 0.0,
            "qualifying_setups": int(elig["n_setups"].sum()), "submitted_orders": int(elig["n_submitted"].sum()),
            "filled_trades": int(len(t)), "canceled_orders": int(elig["n_canceled"].sum()),
            "setups_rejected_at_execution_gate": int(elig["n_rejected_execution"].sum()),
            "setups_blocked_position_open": int(elig["n_blocked_position_open"].sum()),
            "setups_blocked_order_pending": int(elig["n_blocked_order_pending"].sum()),
            "setups_blocked_trade_cap": int(elig["n_blocked_trade_cap"].sum()), "setups_duplicate": int(elig["n_duplicate_setup"].sum()),
            "trades_excluded_roll": int(t["excluded_by_roll_policy"].sum()) if len(t) else 0,
            "development_years": round(years, 3), "trades_per_year": round(len(t) / years, 1) if years else 0.0,
            "setups_per_year": round(elig["n_setups"].sum() / years, 1) if years else 0.0,
            "avg_setups_per_eligible_window": round(elig["n_setups"].mean(), 4) if len(elig) else 0.0,
            "avg_trades_per_eligible_window": round(elig["n_filled"].mean(), 4) if len(elig) else 0.0,
            "max_trades_in_a_window": int(elig["n_filled"].max()) if len(elig) else 0,
            "trade_cap": cfg.signal.trade_cap, **dist,
        })
    reasons = nd.copy(); reasons["config"] = name
    reasons["reason_short"] = reasons["reason"].astype(str).str.replace(r"\(.*\)$", "", regex=True).str.replace(r"position_open_until_.*", "position_open", regex=True)
    rr = reasons.groupby(["config", "window", "gate_failed", "reason_short"]).size().reset_index(name="windows")
    return rows, rr


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--configs", default=",".join(NAMED_CONFIGS)); a = ap.parse_args()
    l1 = load_config(); l2 = load_layer2_config(); store = FeatureStore.build(l1, l2)
    l1m = json.loads((l1.resolve("clean_dir") / "manifest.json").read_text())
    all_rows, all_reasons, manifest_cfgs = [], [], {}
    for name in a.configs.split(","):
        cfg = load_named_config(name)
        res = run_backtest(cfg, store)
        out = write_backtest(res, cfg, store, l2, l1.resolve("runs_dir") / "backtests")
        rows, rr = frequency_rows(name, cfg, res, store)
        all_rows += rows; all_reasons.append(rr)
        manifest_cfgs[name] = {"execution_config_hash": cfg.config_hash, "description": cfg.meta.description,
                               "stop_substitution_note": cfg.meta.stop_substitution_note, "config": cfg.to_dict(), "backtest_dir": str(out),
                               "trades_content_hash": json.loads((out / "backtest_manifest.json").read_text())["trades_content_hash"]}
        print(f"{name}: setups {rows[0]['qualifying_setups']}, orders {rows[0]['submitted_orders']}, fills {rows[0]['filled_trades']}, canceled {rows[0]['canceled_orders']}")
    fr = pd.DataFrame(all_rows); nr = pd.concat(all_reasons, ignore_index=True)
    assert not any(any(f in c for f in FORBIDDEN_METRICS) for c in fr.columns)
    fr.to_csv(OUT / "frequency_report.csv", index=False); nr.to_csv(OUT / "no_trade_reasons.csv", index=False)
    man = {"generated_utc": datetime.now(timezone.utc).isoformat(), "purpose": "Layer 4 frequency diagnostics — research baselines, not recommended strategies; no performance metrics",
           "development_range": [str(store.data.bars["trading_date"].min().date()), str(store.data.bars["trading_date"].max().date())], "holdout_accessed": False,
           "series_id": store.data.series_id, "layer1_config_hash": l1m["config_hash"], "layer1_source_hashes": l1m["source_hashes"], "layer1_zip_hashes": l1m["zip_hashes"],
           "layer1_backadjusted_content_hash": l1m["outputs"]["MNQ_1m_backadjusted.parquet"]["content_hash"],
           "layer2_config_hash": l2.config_hash, "feature_source": store.source, "software": software_versions(), "configurations": manifest_cfgs}
    (OUT / "named_configs_manifest.json").write_text(json.dumps(man, indent=2, default=str))
    md = ["# Layer 4 frequency report — named configurations (development period only)\n",
          "Research baselines, **not** recommended strategies. Signal frequency (qualifying setups) is reported separately from order submissions and fills. "
          "No profitability or performance metrics are computed in this layer.\n",
          "Stop: user-authorized modification `liquidity_sweep_extreme` (one tick beyond the qualifying sweep's extreme wick) in place of the original, unresolved 'beyond displacement swing' stop.\n",
          f"Development range {man['development_range'][0]} → {man['development_range'][1]} ({fr['development_years'].iloc[0]} years). Ineligible windows (Layer 1 data-quality exclusions, truncated/non-causal sessions) are counted separately from eligible windows without a setup.\n"]
    key = ["config", "scope", "windows_registered", "windows_eligible", "windows_ineligible_excluded", "windows_with_qualifying_setup", "pct_eligible_windows_with_setup",
           "windows_with_filled_trade", "pct_eligible_windows_with_fill", "trading_dates_with_filled_trade", "pct_trading_dates_with_filled_trade",
           "qualifying_setups", "submitted_orders", "filled_trades", "canceled_orders", "trades_per_year", "avg_trades_per_eligible_window", "max_trades_in_a_window", "trade_cap"]
    md += ["## Frequency by configuration and window\n", fr[key].to_markdown(index=False), "\n",
           "## Why qualifying setups did not become filled trades\n",
           fr[fr["scope"] == "all"][["config", "qualifying_setups", "setups_rejected_at_execution_gate", "setups_blocked_position_open", "setups_blocked_order_pending", "setups_blocked_trade_cap", "setups_duplicate", "submitted_orders", "canceled_orders", "filled_trades", "trades_excluded_roll"]].to_markdown(index=False), "\n",
           "## Distribution of filled trades per trading date (dates with at least one eligible window)\n"]
    dcols = [c for c in fr.columns if c.startswith("dates_with_")]
    md += [fr[fr["scope"] == "all"][["config"] + sorted(dcols, key=lambda c: int(c.split("_")[2]))].fillna(0).astype({c: int for c in dcols}).to_markdown(index=False), "\n",
           "## No-trade reasons by eligibility gate (windows without a filled trade)\n",
           nr.pivot_table(index=["config", "gate_failed", "reason_short"], columns="window", values="windows", aggfunc="sum", fill_value=0).reset_index().to_markdown(index=False), "\n"]
    (OUT / "frequency_report.md").write_text("\n".join(md))
    print("wrote", OUT / "frequency_report.md")


if __name__ == "__main__":
    main()
