"""Layer 5 ablation — PARTIAL. Only the steps definable with established rules are executed:
  step 4: FVG + sweep + displacement + Silver Bullet window           (bias none)
  step 5: step 4 + 15-minute directional bias                          (bias swing_15m_structure)
  diagnostic: step 4 + perfect-future-bias (LOOKAHEAD, INVALID FOR TRADING; never a candidate)
Steps 1–3 (FVG only; FVG + sweep; FVG + sweep + displacement without a window) are NOT PERFORMED: the
FVG-only direction rule and the no-window search universe are not established (Layer 5 clarifications 15–16).

Shared base (implementation choice for consistency, from established parameters): 5m FVG, no min size,
bsl_ssl_15m universe, K=3, 1 tick, displacement 1.5 ATR, no MSS, midpoint entry, target 1R, all three
windows, 1 trade per window, liquidity_sweep_extreme stop + 1 tick, rth_end exit, default costs.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..engine.backtest import FeatureStore, run_backtest
from ..engine.config import load_config
from ..engine.exec_config import load_layer3_config
from ..features.bias import compute_bias
from ..features.config import BiasConfig, load_layer2_config
from .grid import BASE_CONFIG, OUT
from .stats import performance_metrics

BASE_SIGNAL = {"windows": ["sb_london", "sb_ny_am", "sb_ny_pm"], "liquidity_universe": "bsl_ssl_15m", "fvg_timeframe": "5m", "min_fvg_points": 0.0,
               "min_fvg_atr": 0.0, "require_mss": False, "require_displacement": True, "displacement_threshold": 1.5, "require_bias": False,
               "max_trades_per_window": 1}
STEPS = [
    ("1_fvg_only", "NOT PERFORMED: FVG-only direction rule not established"),
    ("2_fvg_sweep", "NOT PERFORMED: no-window search universe not established"),
    ("3_fvg_sweep_displacement", "NOT PERFORMED: no-window search universe not established"),
    ("4_fvg_sweep_displacement_window", "none"),
    ("5_plus_15m_bias", "swing_15m_structure"),
    ("diagnostic_perfect_future_bias_LOOKAHEAD", "perfect_window"),
]


def run_ablation(store: FeatureStore) -> pd.DataFrame:
    rows = []
    dates = store.data.bars["trading_date"].unique()
    for name, bias in STEPS:
        if bias.startswith("NOT PERFORMED"):
            rows.append({"step": name, "status": "not_performed", "note": bias, "lookahead": False}); continue
        lookahead = bias == "perfect_window"
        if lookahead:
            # the schema forbids lookahead detectors in a research config; the diagnostic injects the lookahead bias table directly
            cfg = load_layer3_config(BASE_CONFIG, meta={"name": "ablation_diag", "research_baseline": False}, signal={**BASE_SIGNAL, "bias_detector": "none"},
                                     entry={"location": "midpoint"}, stop={"type": "liquidity_sweep_extreme", "buffer_ticks": 1}, target={"type": "fixed_r", "r_multiple": 1.0}, exit={"policy": "rth_end"})
            diag_bias = compute_bias(store.data.bars, store.sessions, tuple(store.sessions.windows), BiasConfig(detector="perfect_window", allow_lookahead_diagnostic=True), store.data.series_id)
            res = _run_with_bias_table(cfg, store, diag_bias)
            cfg = load_layer3_config(BASE_CONFIG, meta={"name": "ablation_diag_perfect_window", "research_baseline": False}, signal={**BASE_SIGNAL, "bias_detector": "swing_15m_structure"},
                                     entry={"location": "midpoint"}, stop={"type": "liquidity_sweep_extreme", "buffer_ticks": 1}, target={"type": "fixed_r", "r_multiple": 1.0}, exit={"policy": "rth_end"})
        else:
            cfg = load_layer3_config(BASE_CONFIG, meta={"name": f"ablation_{name}", "research_baseline": True}, signal={**BASE_SIGNAL, "bias_detector": bias},
                                     entry={"location": "midpoint"}, stop={"type": "liquidity_sweep_extreme", "buffer_ticks": 1}, target={"type": "fixed_r", "r_multiple": 1.0}, exit={"policy": "rth_end"})
            res = run_backtest(cfg, store)
        m = performance_metrics(res["trades"], dates)
        rows.append({"step": name, "status": m["status"], "lookahead": lookahead, "note": "LOOKAHEAD / INVALID FOR LIVE TRADING — never a candidate" if lookahead else "",
                     "config_hash": cfg.config_hash, "n_trades": m["n_trades"], "net_expectancy_r": m["net_expectancy_r"], "net_sharpe": m["net_sharpe"],
                     "net_pnl_usd": m["net_pnl_usd"], "profit_factor": m["profit_factor"], "max_drawdown_usd": m["max_drawdown_usd"], "max_drawdown_r": m["max_drawdown_r"],
                     "win_rate": m["win_rate"], "n_ambiguous": m["n_ambiguous"]})
    return pd.DataFrame(rows)


def _run_with_bias_table(cfg, store, bias_table: pd.DataFrame):
    """Run the engine with an injected bias table (diagnostic only). The signal gate reads tables.bias, so the
    perfect-window direction filter is applied exactly like a valid detector would be."""
    from ..engine import backtest as bt
    # run_backtest reads store.bias_table(detector); the diagnostic temporarily swaps the cached table for a valid
    # detector name with the lookahead table, then restores it. Nothing is persisted.
    key = "swing_15m_structure"; saved = store._bias_cache.get(key)
    store._bias_cache[key] = bias_table
    try:
        cfg2 = load_layer3_config(BASE_CONFIG, meta={"name": "ablation_diag_perfect_window", "research_baseline": False}, signal={**BASE_SIGNAL, "bias_detector": key},
                                  entry={"location": "midpoint"}, stop={"type": "liquidity_sweep_extreme", "buffer_ticks": 1}, target={"type": "fixed_r", "r_multiple": 1.0}, exit={"policy": "rth_end"})
        return bt.run_backtest(cfg2, store)
    finally:
        if saved is None: store._bias_cache.pop(key, None)
        else: store._bias_cache[key] = saved


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    l1 = load_config(); store = FeatureStore.build(l1, load_layer2_config())
    df = run_ablation(store)
    df.to_csv(OUT / "ablation_partial.csv", index=False)
    (OUT / "ablation_manifest.json").write_text(json.dumps({"generated_utc": datetime.now(timezone.utc).isoformat(), "base_signal": BASE_SIGNAL,
        "steps": STEPS, "holdout_accessed": False, "note": "steps 1-3 not performed pending definitions; the perfect-future-bias row is a lookahead diagnostic only"}, indent=2, default=str))
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
