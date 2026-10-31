"""Compute every Layer 2 feature table for a registered series and write them with a manifest.

Run: python -m ict_lab.features.run [--config path] [--series id] [--start YYYY-MM-DD --end YYYY-MM-DD]
Outputs: ict_lab/runs/features/<series_id>/<config_hash[:12]>/*.parquet + feature_manifest.json
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..engine.config import load_config
from ..engine.instrument import InstrumentSpec
from ..engine.manifest import content_hash, software_versions
from ..engine.sessions import SessionSpec
from .bias import compute_bias
from .config import DEFAULT_L2_CONFIG, Layer2Config, load_layer2_config
from .displacement import detect_displacement
from .fvg import detect_fvg
from .liquidity import build_liquidity_levels
from .mss import detect_mss
from .series import SeriesData, load_series
from .sweeps import detect_sweeps
from .timeframes import resample
from .windows import window_table


def compute_all(data: SeriesData, cfg: Layer2Config, l1cfg=None, log=lambda *_: None) -> dict[str, pd.DataFrame]:
    l1cfg = l1cfg or load_config()
    spec = InstrumentSpec.from_config(l1cfg); ss = SessionSpec.from_config(l1cfg)
    bars = data.bars; sid = data.series_id
    out: dict[str, pd.DataFrame] = {}
    t = time.time()
    candles = {tf: resample(bars, tf) for tf in sorted(set(cfg.fvg.timeframes) | {cfg.sweep.timeframe, cfg.displacement.timeframe, cfg.mss.timeframe})}
    log(f"  candles built {list(candles)} {time.time()-t:.1f}s")
    out["windows"] = window_table(data.sessions, ss, cfg.windows, sid)
    fv = [detect_fvg(candles[tf], bars, tf, cfg.fvg, cfg.atr, sid, spec.tick_size) for tf in cfg.fvg.timeframes]
    out["fvg"] = pd.concat(fv, ignore_index=True) if fv else pd.DataFrame()
    log(f"  fvg {len(out['fvg'])} {time.time()-t:.1f}s")
    levels = build_liquidity_levels(bars, ss, cfg.liquidity, cfg.windows, sid)
    sweeps, levels = detect_sweeps(candles[cfg.sweep.timeframe], levels, cfg.sweep, cfg.liquidity, spec.tick_size, ss, sid, cfg.windows)
    out["liquidity_levels"] = levels; out["sweeps"] = sweeps
    log(f"  levels {len(levels)} sweeps {len(sweeps)} (confirmed {(sweeps['status']=='confirmed').sum()}) {time.time()-t:.1f}s")
    out["displacement"] = detect_displacement(candles[cfg.displacement.timeframe], cfg.displacement.timeframe, cfg.displacement, cfg.atr, sid)
    out["mss"] = detect_mss(candles[cfg.mss.timeframe], sweeps, cfg.mss, sid)
    log(f"  displacement {len(out['displacement'])} mss {len(out['mss'])} (found {int(out['mss']['found'].sum())}) {time.time()-t:.1f}s")
    out["bias"] = compute_bias(bars, ss, cfg.windows, cfg.bias, sid)
    out["rolls"] = data.rolls.copy()
    return out


def write_outputs(tables: dict[str, pd.DataFrame], data: SeriesData, cfg: Layer2Config, out_root: Path, l1_manifest: dict) -> Path:
    out_dir = out_root / data.series_id / cfg.config_hash[:12]
    out_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, df in tables.items():
        p = out_dir / f"{name}.parquet"
        df.to_parquet(p, index=False)
        hashes[name] = {"rows": int(len(df)), "content_hash": content_hash(df) if len(df) else None}
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "series_id": data.series_id, "series_spec": data.spec.__dict__,
        "layer2_config_hash": cfg.config_hash, "layer2_config": cfg.to_dict(),
        "layer1_config_hash": l1_manifest.get("config_hash"), "layer1_backadjusted_content_hash": l1_manifest["outputs"]["MNQ_1m_backadjusted.parquet"]["content_hash"],
        "development_bars": int(len(data.bars)), "development_range": [str(data.bars["trading_date"].min().date()), str(data.bars["trading_date"].max().date())],
        "holdout_accessed": False, "software": software_versions(), "tables": hashes,
    }
    (out_dir / "feature_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return out_dir


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_L2_CONFIG)); ap.add_argument("--series", default=None)
    ap.add_argument("--start", default=None); ap.add_argument("--end", default=None)
    a = ap.parse_args()
    cfg = load_layer2_config(a.config)
    if a.series:
        cfg = Layer2Config(**{**cfg.to_dict(), "series_id": a.series}).validate()
    l1 = load_config()
    data = load_series(cfg.series_id, l1, a.start, a.end)
    print(f"series {data.series_id}: {len(data.bars):,} development bars {data.bars['trading_date'].min().date()} -> {data.bars['trading_date'].max().date()}")
    tables = compute_all(data, cfg, l1, log=print)
    l1_manifest = json.loads((l1.resolve("clean_dir") / "manifest.json").read_text())
    out = write_outputs(tables, data, cfg, l1.resolve("runs_dir") / "features", l1_manifest)
    print("wrote", out)
    for k, v in tables.items():
        print(f"  {k:18s} {len(v):>9,} rows")


if __name__ == "__main__":
    main()
