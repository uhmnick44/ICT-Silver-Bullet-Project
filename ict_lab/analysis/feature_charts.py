"""Visual verification of Layer 2 features on randomly selected development-period windows.

Prices are drawn from the UNADJUSTED series; feature levels (computed on the back-adjusted series)
are mapped back with the segment's additive adjustment (constant inside a window, since rolls
take effect at the session open). Holdout dates can never be selected because the series loader
only exposes the development split.

Usage: python -m ict_lab.analysis.feature_charts [--n 15] [--seed 20261031] [--out runs/feature_charts]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

from ..engine.config import load_config
from ..features.config import load_layer2_config
from ..features.series import load_series

NY = "America/New_York"
LEVEL_STYLE = {"prev_session": ("#1f77b4", "-"), "prev_rth": ("#9467bd", "--"), "prewindow": ("#2ca02c", ":"), "swing_15m": ("#8c564b", "-.")}


def _candles(ax, b: pd.DataFrame):
    x = b["ts_ny"]; up = b["close"] >= b["open"]
    ax.vlines(x, b["low"], b["high"], color="#555", lw=0.6)
    for mask, col in ((up, "#2a9d8f"), (~up, "#e76f51")):
        s = b[mask]
        ax.vlines(s["ts_ny"], s[["open", "close"]].min(axis=1), s[["open", "close"]].max(axis=1), color=col, lw=2.4)


def draw_window(unadj: pd.DataFrame, adj: pd.DataFrame, feats: dict, w: pd.Series, out: Path, pad_before=90, pad_after=30) -> Path:
    s, e = pd.Timestamp(w["start_ts_utc"]), pd.Timestamp(w["end_ts_utc"])
    lo, hi = s - pd.Timedelta(minutes=pad_before), e + pd.Timedelta(minutes=pad_after)
    u = unadj[(unadj["ts_utc"] >= lo) & (unadj["ts_utc"] < hi)]
    a = adj[(adj["ts_utc"] >= lo) & (adj["ts_utc"] < hi)]
    offs = (a["close"].to_numpy() - u["close"].to_numpy())
    assert np.allclose(offs, offs[0]), "window spans a roll; adjustment not constant"
    off = float(offs[0])                      # unadjusted = adjusted - off
    fig, ax = plt.subplots(figsize=(14, 7))
    _candles(ax, u)
    ax.axvspan(s.tz_convert(NY), e.tz_convert(NY), color="#ffd166", alpha=0.15, label=f"{w['window']} window")
    ymin, ymax = u["low"].min() - 10, u["high"].max() + 10
    # FVGs (1m and 5m) confirmed inside the drawn range
    f = feats["fvg"]; f = f[(f["confirmation_ts_utc"] >= lo) & (f["confirmation_ts_utc"] < hi) & (f["timeframe"].isin(["1m", "5m"]))]
    for _, r in f.iterrows():
        x0 = r["confirmation_ts_utc"].tz_convert(NY); x1 = (r["first_mitigation_ts_utc"] if pd.notna(r["first_mitigation_ts_utc"]) and r["first_mitigation_ts_utc"] < hi else hi).tz_convert(NY)
        col = "#06d6a0" if r["direction"] == "bullish" else "#ef476f"
        ax.add_patch(Rectangle((x0, r["lower"] - off), x1 - x0, r["gap_points"], color=col, alpha=0.25 if r["timeframe"] == "1m" else 0.45, lw=0))
    # liquidity levels active during the range (not consumed before it starts)
    lv = feats["liquidity_levels"]
    act = lv[(lv["activation_ts_utc"] < hi) & (lv["expiry_ts_utc"].isna() | (lv["expiry_ts_utc"] > lo)) & (lv["consumed_ts_utc"].isna() | (lv["consumed_ts_utc"] > lo))]
    for _, r in act.iterrows():
        p = r["price"] - off
        if not (ymin <= p <= ymax):
            continue
        base = r["level_type"].rsplit("_", 1)[0]; col, ls = LEVEL_STYLE[base]
        x0 = max(r["activation_ts_utc"], lo).tz_convert(NY); x1 = (min(r["expiry_ts_utc"], hi) if pd.notna(r["expiry_ts_utc"]) else hi).tz_convert(NY)
        ax.hlines(p, x0, x1, color=col, ls=ls, lw=1.0); ax.text(x1, p, r["level_type"], fontsize=6, color=col, va="center")
    # confirmed sweeps
    sw = feats["sweeps"]; sw = sw[(sw["status"] == "confirmed") & (sw["confirmation_ts_utc"] >= lo) & (sw["confirmation_ts_utc"] < hi)]
    for _, r in sw.iterrows():
        y = r["level_price"] - off
        ax.plot(r["penetration_ts_utc"].tz_convert(NY), y, marker="^" if r["sweep_direction"] == "bullish_reversal" else "v", color="k", ms=9, ls="")
    # displacement candles >= 2.0 ATR
    d = feats["displacement"]; d = d[(d["ts_utc"] >= lo) & (d["ts_utc"] < hi) & (d["range_atr_ratio"] >= 2.0)]
    for _, r in d.iterrows():
        ub = u[u["ts_utc"] == r["ts_utc"]]
        if len(ub):
            ax.plot(ub["ts_ny"].iloc[0], ub["high"].iloc[0] + 3, marker="*", color="#f77f00", ms=10, ls="")
    # MSS
    m = feats["mss"]; m = m[m["found"] & (m["break_ts_utc"] >= lo) & (m["break_ts_utc"] < hi)]
    for _, r in m.iterrows():
        y = r["swing_price"] - off
        ax.hlines(y, r["swing_ts_utc"].tz_convert(NY), r["break_ts_utc"].tz_convert(NY), color="#3a0ca3", lw=1.2)
        ax.plot(r["break_ts_utc"].tz_convert(NY), y, marker="x", color="#3a0ca3", ms=9, ls="")
    ax.set_ylim(ymin, ymax); ax.set_xlim(lo.tz_convert(NY), hi.tz_convert(NY))
    ax.set_title(f"{w['trading_date'].date()} {w['window']} ({u['symbol'].iloc[0]}, unadjusted prices; adj offset {off:+.2f}) — "
                 "boxes: FVG (1m light / 5m dark); lines: liquidity; ▲▼ confirmed sweep; ★ displacement ≥2 ATR; ✕ MSS break", fontsize=9)
    ax.legend(loc="upper left", fontsize=7); fig.autofmt_xdate(); fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{w['trading_date'].date()}_{w['window']}.png"
    fig.savefig(p, dpi=110); plt.close(fig)
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15); ap.add_argument("--seed", type=int, default=20261031); ap.add_argument("--out", default=None)
    a = ap.parse_args()
    l1 = load_config(); cfg = load_layer2_config()
    run_dir = l1.resolve("runs_dir") / "features" / cfg.series_id / cfg.config_hash[:12]
    feats = {k: pd.read_parquet(run_dir / f"{k}.parquet") for k in ("fvg", "liquidity_levels", "sweeps", "displacement", "mss", "windows")}
    win = feats["windows"]; elig = win[win["eligible"]].reset_index(drop=True)
    rng = np.random.default_rng(a.seed)
    pick = elig.iloc[np.sort(rng.choice(len(elig), size=a.n, replace=False))]
    unadj = load_series("mnq_volcross_next_session_unadj_v1", l1).bars
    adj = load_series(cfg.series_id, l1).bars
    assert pick["trading_date"].max() <= pd.Timestamp(l1["split"]["development_end"])
    out = Path(a.out) if a.out else l1.resolve("runs_dir") / "feature_charts"
    index = []
    for _, w in pick.iterrows():
        p = draw_window(unadj, adj, feats, w, out)
        index.append({"trading_date": str(w["trading_date"].date()), "window": w["window"], "file": p.name}); print("wrote", p)
    pd.DataFrame(index).to_csv(out / "chart_index.csv", index=False)
    (out / "selection.json").write_text(json.dumps({"seed": a.seed, "n": a.n, "eligible_windows": int(len(elig)), "series": cfg.series_id,
                                                    "config_hash": cfg.config_hash, "selection": index}, indent=2))


if __name__ == "__main__":
    main()
