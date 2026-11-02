"""Layer 5 parameter grid over the ESTABLISHED dimensions only (Layer 5 clarifications), deduplication by
resolved content, fixed-seed uniform sampling with explicit (count, seed), and a development-only sweep
runner that records descriptive metrics after costs for every evaluated configuration.

Established dimensions: FVG timeframe {1m,5m,15m}; FVG min size none; K=3 bars; penetration 1 tick;
liquidity universe {session_refs, session_refs_plus_swings, bsl_ssl_15m, swings_only} (swings_only is
an alias of bsl_ssl_15m and is removed by deduplication); bias {none, prev_day_oc, swing_15m_structure,
swing_1h_structure, daily_ma20_slope}; displacement threshold {1, 1.5, 2, 3}; MSS {required, not};
entry {proximal, midpoint, distal}; target 1R; windows {London, NY AM, NY PM, all three};
max trades per window {1, unlimited(cap 10)}. Fixed: stop liquidity_sweep_extreme + 1 tick, rth_end exit,
default costs/slippage, 1 contract, roll flag_and_exclude, series mnq_volcross_next_session_backadj_v1.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ..engine.backtest import FeatureStore, run_backtest
from ..engine.config import load_config
from ..engine.exec_config import LIQUIDITY_UNIVERSES, Layer3Config, load_layer3_config
from ..engine.manifest import content_hash, software_versions
from ..features.config import load_layer2_config
from .stats import performance_metrics, passes_descriptive_screen

OUT = Path(__file__).resolve().parent / "layer5"
BASE_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "strategies" / "as_taught_5m.toml"   # fixed parts (stop, exit, costs, sizing, roll)

DIMENSIONS = {
    "fvg_timeframe": ["1m", "5m", "15m"],
    "liquidity_universe": ["session_refs", "session_refs_plus_swings", "bsl_ssl_15m", "swings_only"],
    "bias_detector": ["none", "prev_day_oc", "swing_15m_structure", "swing_1h_structure", "daily_ma20_slope"],
    "displacement_threshold": [1.0, 1.5, 2.0, 3.0],
    "require_mss": [False, True],
    "entry_location": ["proximal", "midpoint", "distal"],
    "target_r": [1.0],
    "windows": [("sb_london",), ("sb_ny_am",), ("sb_ny_pm",), ("sb_london", "sb_ny_am", "sb_ny_pm")],
    "max_trades_per_window": [1, "unlimited"],
}
FIXED = {"min_fvg_points": 0.0, "min_fvg_atr": 0.0, "max_confirmation_bars": 3, "min_penetration_ticks": 1,
         "stop_type": "liquidity_sweep_extreme", "stop_buffer_ticks": 1, "exit_policy": "rth_end", "target_type": "fixed_r"}


def make_config(p: dict) -> Layer3Config:
    """Build a validated execution config from one grid point, inheriting fixed parts from the base file."""
    return load_layer3_config(
        BASE_CONFIG,
        meta={"name": "grid", "description": "Layer 5 grid point", "stop_substitution_note": "user-authorized liquidity_sweep_extreme stop", "research_baseline": True},
        signal={"windows": list(p["windows"]), "liquidity_universe": p["liquidity_universe"], "fvg_timeframe": p["fvg_timeframe"],
                "min_fvg_points": FIXED["min_fvg_points"], "min_fvg_atr": FIXED["min_fvg_atr"], "require_mss": p["require_mss"],
                "require_displacement": True, "displacement_threshold": p["displacement_threshold"], "bias_detector": p["bias_detector"],
                "require_bias": False, "max_trades_per_window": p["max_trades_per_window"]},
        entry={"location": p["entry_location"]},
        stop={"type": FIXED["stop_type"], "buffer_ticks": FIXED["stop_buffer_ticks"]},
        target={"type": FIXED["target_type"], "r_multiple": p["target_r"]},
        exit={"policy": FIXED["exit_policy"]})


def semantic_key(cfg: Layer3Config) -> str:
    """Hash of the resolved execution content: universe names are replaced by their resolved level types so
    `swings_only` and `bsl_ssl_15m` collapse to one configuration."""
    d = asdict(cfg); d.pop("meta", None)
    d["signal"]["liquidity_universe"] = "resolved"; d["signal"]["liquidity_types"] = list(cfg.signal.liquidity_types)
    d["target"]["opposing_liquidity_types"] = list(cfg.target.opposing_liquidity_types)
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


def generate_grid() -> pd.DataFrame:
    keys = list(DIMENSIONS)
    rows = []
    for combo in itertools.product(*[DIMENSIONS[k] for k in keys]):
        p = dict(zip(keys, combo))
        cfg = make_config(p)
        rows.append({**{k: (";".join(v) if isinstance(v, tuple) else v) for k, v in p.items()}, "config_hash": cfg.config_hash, "semantic_key": semantic_key(cfg)})
    g = pd.DataFrame(rows)
    g["generated_index"] = np.arange(len(g))
    g["is_duplicate"] = g.duplicated("semantic_key", keep="first")
    return g


def sample_grid(unique: pd.DataFrame, count: int | None, seed: int | None) -> pd.DataFrame:
    """Fixed-seed uniform sampling without replacement from the deduplicated grid. count/seed are explicit inputs
    (the screenshot values are unverified); None evaluates the full deduplicated grid."""
    if count is None:
        return unique.assign(sampled=True)
    if seed is None:
        raise ValueError("a fixed seed is required for sampling")
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(len(unique), size=min(count, len(unique)), replace=False))
    return unique.iloc[idx].assign(sampled=True)


# ----------------------------------------------------------------------------- runner (multiprocessing)
_STORE = None
def _init():
    global _STORE
    l1 = load_config(); _STORE = FeatureStore.build(l1, load_layer2_config())


def _evaluate(p: dict) -> tuple[dict, pd.DataFrame]:
    cfg = make_config(p)
    res = run_backtest(cfg, _STORE)
    tr = res["trades"]; ws = res["window_stats"]
    dates = _STORE.data.bars["trading_date"].unique()
    m = performance_metrics(tr, dates)
    m["descriptive_screen_provisional"] = passes_descriptive_screen(m)
    m.update({"config_hash": cfg.config_hash, "qualifying_setups": int(ws["n_setups"].sum()), "submitted_orders": int(ws["n_submitted"].sum()),
              "canceled_orders": int(ws["n_canceled"].sum()), "eligible_windows": int(ws["eligible"].sum()), "trades_content_hash": content_hash(tr) if len(tr) else None})
    if len(tr):
        tr = tr.assign(grid_config_hash=cfg.config_hash)
    return m, tr


def run_sweep(points: pd.DataFrame, processes: int = 4, log=print) -> tuple[pd.DataFrame, pd.DataFrame]:
    from multiprocessing import Pool
    keys = list(DIMENSIONS)
    plist = []
    for r in points.itertuples(index=False):
        d = r._asdict(); p = {k: d[k] for k in keys}
        p["windows"] = tuple(p["windows"].split(";")); p["max_trades_per_window"] = "unlimited" if p["max_trades_per_window"] == "unlimited" else int(p["max_trades_per_window"])
        p["require_mss"] = bool(p["require_mss"]); p["displacement_threshold"] = float(p["displacement_threshold"]); p["target_r"] = float(p["target_r"])
        plist.append(p)
    t0 = time.time(); metrics, trades = [], []
    with Pool(processes, initializer=_init) as pool:
        for i, (m, tr) in enumerate(pool.imap(_evaluate, plist, chunksize=4), start=1):
            metrics.append(m)
            if len(tr): trades.append(tr)
            if i % 200 == 0: log(f"  {i}/{len(plist)} configurations evaluated ({time.time()-t0:.0f}s)")
    return pd.DataFrame(metrics), (pd.concat(trades, ignore_index=True) if trades else pd.DataFrame())


def main(count: int | None = None, seed: int | None = None, processes: int = 4) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    g = generate_grid(); unique = g[~g["is_duplicate"]].reset_index(drop=True)
    sel = sample_grid(unique, count, seed)
    g.to_csv(OUT / "grid.csv", index=False)
    print(f"grid generated {len(g)}, deduplicated {len(unique)}, selected {len(sel)}")
    metrics, trades = run_sweep(sel, processes)
    metrics = metrics.merge(g.drop(columns=["is_duplicate"]), on="config_hash", how="left")
    metrics.to_csv(OUT / "sweep_results.csv", index=False)
    (OUT / "sweep_trades.parquet").parent.mkdir(exist_ok=True)
    trades.to_parquet(OUT / "sweep_trades.parquet", index=False)
    l1 = load_config(); l1m = json.loads((l1.resolve("clean_dir") / "manifest.json").read_text()); l2 = load_layer2_config()
    man = {"generated_utc": datetime.now(timezone.utc).isoformat(), "dimensions": {k: [list(v) if isinstance(v, tuple) else v for v in vals] for k, vals in DIMENSIONS.items()},
           "fixed": FIXED, "counts": {"generated": int(len(g)), "deduplicated": int(len(unique)), "sampled": int(len(sel)), "evaluated": int(len(metrics))},
           "sampling": {"count": count, "seed": seed, "note": "screenshot sample count and seed unverified; full deduplicated grid evaluated" if count is None else "explicit user-supplied count/seed"},
           "series_id": l2.series_id, "roll_convention": l1m["roll_convention"], "layer1_config_hash": l1m["config_hash"], "layer1_source_hashes": l1m["source_hashes"],
           "layer1_backadjusted_content_hash": l1m["outputs"]["MNQ_1m_backadjusted.parquet"]["content_hash"], "layer2_config_hash": l2.config_hash,
           "costs": asdict(load_layer3_config(BASE_CONFIG).costs), "sizing": asdict(load_layer3_config(BASE_CONFIG).sizing), "holdout_accessed": False,
           "development_range": [str(pd.Timestamp(d).date()) for d in (trades["trading_date"].min(), trades["trading_date"].max())] if len(trades) else None,
           "total_trades": int(len(trades)), "ambiguous_trades": int(trades["same_bar_ambiguous"].sum()) if len(trades) else 0,
           "software": software_versions(), "sharpe_convention": "daily net $ P&L over all development trading dates (0 on no-trade days), annualized sqrt(252); provisional pending return-frequency clarification"}
    (OUT / "grid_manifest.json").write_text(json.dumps(man, indent=2, default=str))
    print("wrote", OUT)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--count", type=int, default=None); ap.add_argument("--seed", type=int, default=None); ap.add_argument("--processes", type=int, default=4)
    a = ap.parse_args(); main(a.count, a.seed, a.processes)
