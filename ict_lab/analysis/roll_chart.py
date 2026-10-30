"""Chart-verification utility: adjusted vs unadjusted 1-minute closes around contract rolls.

Usage: python -m ict_lab.analysis.roll_chart [--rolls 1,5,9] [--minutes 180] [--out runs/roll_charts]

This is an infrastructure/audit tool (no strategy logic). It reads the full roll log and both
series because roll verification is a data-pipeline concern; it does not compute research results.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from ..engine.config import load_config


def plot_roll(unadj: pd.DataFrame, adj: pd.DataFrame, roll: pd.Series, minutes: int, out: Path) -> Path:
    t = pd.Timestamp(roll["roll_ts_utc"])
    lo, hi = t - pd.Timedelta(minutes=minutes), t + pd.Timedelta(minutes=minutes)
    u = unadj[(unadj["ts_utc"] >= lo) & (unadj["ts_utc"] <= hi)]
    a = adj[(adj["ts_utc"] >= lo) & (adj["ts_utc"] <= hi)]
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for sym, g in u.groupby("symbol"):
        axes[0].plot(g["ts_ny"], g["close"], lw=0.8, label=f"unadjusted {sym}")
    axes[0].axvline(t.tz_convert("America/New_York"), color="k", ls="--", lw=0.8, label="roll ts")
    axes[0].set_title(f"Roll {int(roll['roll_id'])}: {roll['old_symbol']} -> {roll['new_symbol']}  offset {roll['offset_points']:+.2f} pts "
                      f"(ref {pd.Timestamp(roll['ref_ts_ny']).strftime('%Y-%m-%d %H:%M')} ET)")
    axes[0].legend(loc="best"); axes[0].set_ylabel("unadjusted close")
    for sym, g in a.groupby("symbol"):
        axes[1].plot(g["ts_ny"], g["close"], lw=0.8, label=f"back-adjusted {sym}")
    axes[1].axvline(t.tz_convert("America/New_York"), color="k", ls="--", lw=0.8)
    axes[1].legend(loc="best"); axes[1].set_ylabel("back-adjusted close"); axes[1].set_xlabel("America/New_York")
    fig.autofmt_xdate(); fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"roll_{int(roll['roll_id']):02d}_{roll['old_symbol']}_{roll['new_symbol']}.png"
    fig.savefig(p, dpi=110); plt.close(fig)
    return p


def roll_boundary_table(unadj: pd.DataFrame, adj: pd.DataFrame, rolls: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in rolls.iterrows():
        t = pd.Timestamp(r["roll_ts_utc"])
        i = int(adj.index[adj["ts_utc"] == t][0])
        rows.append({"roll_id": int(r["roll_id"]), "old": r["old_symbol"], "new": r["new_symbol"],
                     "last_old_close_unadj": unadj["close"].iloc[i - 1], "first_new_open_unadj": unadj["open"].iloc[i],
                     "jump_unadjusted": unadj["open"].iloc[i] - unadj["close"].iloc[i - 1],
                     "last_old_close_adj": adj["close"].iloc[i - 1], "first_new_open_adj": adj["open"].iloc[i],
                     "jump_backadjusted": adj["open"].iloc[i] - adj["close"].iloc[i - 1],
                     "offset_points": r["offset_points"]})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rolls", default="all"); ap.add_argument("--minutes", type=int, default=180)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cfg = load_config(); clean = cfg.resolve("clean_dir")
    out = Path(a.out) if a.out else cfg.resolve("runs_dir") / "roll_charts"
    cols = ["ts_utc", "ts_ny", "symbol", "open", "close"]
    unadj = pd.read_parquet(clean / "MNQ_1m_unadjusted.parquet", columns=cols)
    adj = pd.read_parquet(clean / "MNQ_1m_backadjusted.parquet", columns=cols)
    rolls = pd.read_csv(clean / "MNQ_rolls.csv", parse_dates=["roll_ts_utc", "ref_ts_ny"])
    rolls["roll_ts_utc"] = pd.DatetimeIndex(rolls["roll_ts_utc"]).tz_convert("UTC")
    if a.rolls != "all":
        rolls = rolls[rolls["roll_id"].isin([int(x) for x in a.rolls.split(",")])]
    for _, r in rolls.iterrows():
        print("wrote", plot_roll(unadj, adj, r, a.minutes, out))
    tbl = roll_boundary_table(unadj, adj, rolls)
    out.mkdir(parents=True, exist_ok=True)
    tbl.to_csv(out / "roll_boundary_jumps.csv", index=False)
    print(tbl.to_string(index=False))


if __name__ == "__main__":
    main()
