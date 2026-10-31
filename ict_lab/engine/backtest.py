"""Layer 3 backtest orchestration: chronological pass over trading windows, one position at a time.

Run: python -m ict_lab.engine.backtest --config configs/baseline_verification.toml [--start --end]
Outputs: runs/backtests/<config_hash[:12]>/trades.parquet, trades.csv, no_trade_log.csv, backtest_manifest.json
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ..features import run as l2run
from ..features.bias import compute_bias
from ..features.config import BiasConfig, load_layer2_config
from ..features.series import SeriesData, load_series
from ..features.timeframes import naive_utc
from .config import Config, load_config
from .exec_config import DEFAULT_L3_CONFIG, Layer3Config, load_layer3_config
from .execution import BarArrays, simulate
from .instrument import InstrumentSpec
from .manifest import content_hash, software_versions
from .sessions import SessionSpec
from .signals import build_setup, prepare_tables

TABLE_NAMES = ("windows", "fvg", "liquidity_levels", "sweeps", "displacement", "mss")


class FeatureStore:
    """Cached Layer 2 feature tables + bar arrays for one series/config. Built either from the Layer 2
    run directory (Parquet) or by recomputation; both give identical results (tested)."""

    def __init__(self, data: SeriesData, feats: dict, l1cfg: Config, l2_hash: str, source: str):
        self.data = data; self.feats = feats; self.l1cfg = l1cfg; self.l2_hash = l2_hash; self.source = source
        self.bars = BarArrays.from_bars(data.bars)
        self.spec = InstrumentSpec.from_config(l1cfg); self.sessions = SessionSpec.from_config(l1cfg)
        self.roll_ts = naive_utc(pd.to_datetime(data.rolls["roll_ts_utc"], utc=True)) if len(data.rolls) else np.zeros(0, dtype="datetime64[ns]")
        self._bias_cache: dict[str, pd.DataFrame] = {}

    @classmethod
    def build(cls, l1cfg: Config, l2cfg, data: SeriesData | None = None, use_cache: bool = True) -> "FeatureStore":
        data = data or load_series(l2cfg.series_id, l1cfg)
        run_dir = l1cfg.resolve("runs_dir") / "features" / l2cfg.series_id / l2cfg.config_hash[:12]
        full_range = data.bars["trading_date"].min() == load_series(l2cfg.series_id, l1cfg).bars["trading_date"].min() if use_cache else False
        if use_cache and (run_dir / "feature_manifest.json").exists() and full_range:
            feats = {k: pd.read_parquet(run_dir / f"{k}.parquet") for k in TABLE_NAMES}
            last = data.bars["trading_date"].max()
            feats = {k: v[v["trading_date"] <= last] if "trading_date" in v else v for k, v in feats.items()}
            return cls(data, feats, l1cfg, l2cfg.config_hash, f"cache:{run_dir}")
        feats = l2run.compute_all(data, l2cfg, l1cfg)
        return cls(data, {k: feats[k] for k in TABLE_NAMES}, l1cfg, l2cfg.config_hash, "computed")

    def bias_table(self, detector: str) -> pd.DataFrame:
        if detector not in self._bias_cache:
            self._bias_cache[detector] = compute_bias(self.data.bars, self.sessions, tuple(self.sessions.windows), BiasConfig(detector=detector), self.data.series_id) \
                if detector != "none" else pd.DataFrame(columns=["trading_date", "window", "bias"])
        return self._bias_cache[detector]


def run_backtest(cfg: Layer3Config, store: FeatureStore, log=lambda *_: None) -> dict:
    t0 = time.time()
    feats = dict(store.feats); feats["bias"] = store.bias_table(cfg.signal.bias_detector)
    tables = prepare_tables(feats, cfg.signal)
    levels = store.feats["liquidity_levels"]
    win = store.feats["windows"]; win = win[win["window"].isin(cfg.signal.windows)].sort_values(["start_ts_utc"]).reset_index(drop=True)
    ss = store.sessions
    trades, diags = [], []
    last_exit = None       # UTC timestamp of the last position exit
    for w in win.itertuples(index=False):
        w = pd.Series(w._asdict())
        start = pd.Timestamp(w["start_ts_utc"])
        if last_exit is not None and last_exit >= start:
            diags.append({"trading_date": w["trading_date"], "window": w["window"], "gate_failed": "position_free", "reason": f"position_open_until_{last_exit.isoformat()}", "sweeps_examined": 0}); continue
        setup, diag = build_setup(w, tables, cfg.signal)
        if setup is None:
            diags.append(diag); continue
        d = pd.Timestamp(w["trading_date"])
        rth_end = ss.session_close_utc(d) - pd.Timedelta(minutes=ss.close_minute - ss.windows["rth"][1])
        trade, nd = simulate(setup, store.bars, cfg, store.spec, levels, rth_end, store.roll_ts)
        if trade is None:
            diags.append({**nd, "sweeps_examined": diag["sweeps_examined"]}); continue
        trade["trade_id"] = f"T{len(trades) + 1:05d}_{d.date()}_{w['window']}"
        trade["config_hash"] = cfg.config_hash; trade["series_id"] = store.data.series_id
        trade["vendor_degraded_utc_overlap"] = bool(w["vendor_degraded_utc_overlap"]); trade["calendar_status"] = w["calendar_status"]
        trade["observed_session_status"] = w["observed_session_status"]; trade["sweeps_examined"] = diag["sweeps_examined"]
        trades.append(trade)
        last_exit = trade["exit_ts_utc"]
    tr = pd.DataFrame(trades)
    if len(tr):
        tr["included"] = ~tr["excluded_by_roll_policy"]
        tr["exclusion_reason"] = np.where(tr["excluded_by_roll_policy"], "spans_contract_roll", "")
        first = ["trade_id", "config_hash", "series_id", "trading_date", "window", "direction", "level_type", "level_price"]
        tr = tr[first + [c for c in tr.columns if c not in first]]
    nd = pd.DataFrame(diags)
    log(f"  {len(tr)} trades, {len(nd)} windows without a trade in {time.time()-t0:.1f}s")
    return {"trades": tr, "no_trade": nd, "elapsed": time.time() - t0}


def write_backtest(result: dict, cfg: Layer3Config, store: FeatureStore, l2cfg, out_root: Path) -> Path:
    out = out_root / cfg.config_hash[:12]; out.mkdir(parents=True, exist_ok=True)
    tr, nd = result["trades"], result["no_trade"]
    tr.to_parquet(out / "trades.parquet", index=False); tr.to_csv(out / "trades.csv", index=False)
    nd.to_csv(out / "no_trade_log.csv", index=False)
    if len(tr):
        tr[tr["excluded_by_roll_policy"]].to_csv(out / "excluded_trades.csv", index=False)   # reported separately, never stitched
    l1m = json.loads((store.l1cfg.resolve("clean_dir") / "manifest.json").read_text())
    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "layer3_config_hash": cfg.config_hash, "layer3_config": cfg.to_dict(),
                "layer2_config_hash": l2cfg.config_hash, "layer1_config_hash": l1m["config_hash"],
                "layer1_backadjusted_content_hash": l1m["outputs"]["MNQ_1m_backadjusted.parquet"]["content_hash"],
                "series_id": store.data.series_id, "feature_source": store.source, "holdout_accessed": False,
                "development_range": [str(store.data.bars["trading_date"].min().date()), str(store.data.bars["trading_date"].max().date())],
                "trades": int(len(tr)), "trades_content_hash": content_hash(tr) if len(tr) else None,
                "no_trade_windows": int(len(nd)), "no_trade_content_hash": content_hash(nd) if len(nd) else None,
                "gate_failure_counts": nd["gate_failed"].value_counts().to_dict() if len(nd) else {},
                "roll_exclusions": {"policy": cfg.roll.policy, "trades_spanning_roll": int(tr["spans_roll"].sum()) if len(tr) else 0,
                                     "trades_excluded": int(tr["excluded_by_roll_policy"].sum()) if len(tr) else 0,
                                     "reasons": tr.loc[tr["excluded_by_roll_policy"], "exclusion_reason"].value_counts().to_dict() if len(tr) else {}},
                "trades_included": int(tr["included"].sum()) if len(tr) else 0,
                "exit_reason_counts": tr["exit_reason"].value_counts().to_dict() if len(tr) else {},
                "software": software_versions(), "elapsed_seconds": round(result["elapsed"], 2)}
    (out / "backtest_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_L3_CONFIG)); ap.add_argument("--start", default=None); ap.add_argument("--end", default=None)
    a = ap.parse_args()
    cfg = load_layer3_config(a.config); l1 = load_config(); l2 = load_layer2_config(l1.lab_root / cfg.layer2_config)
    data = load_series(cfg.series_id, l1, a.start, a.end)
    store = FeatureStore.build(l1, l2, data)
    print(f"features from {store.source}; {len(data.bars):,} bars {data.bars['trading_date'].min().date()} -> {data.bars['trading_date'].max().date()}")
    res = run_backtest(cfg, store, log=print)
    out = write_backtest(res, cfg, store, l2, l1.resolve("runs_dir") / "backtests")
    print("wrote", out)
    tr = res["trades"]
    if len(tr):
        print(tr["exit_reason"].value_counts().to_dict()); print("ambiguous:", int(tr["same_bar_ambiguous"].sum()), "spans_roll:", int(tr["spans_roll"].sum()))
    print(res["no_trade"]["gate_failed"].value_counts().to_dict())


if __name__ == "__main__":
    main()
