"""Layer 3 manual-verification sample: one development month under the baseline configuration.

For every trade and unfilled order in the month it prints the feature-event sequence and the
surrounding 1-minute bars (adjusted prices with the unadjusted basis), then re-derives the fill and
exit from those bars with an independent, deliberately naive re-implementation and reports any
discrepancy. A window_end exit variant of the same month is included so time exits are exercised.

Usage: python -m ict_lab.analysis.manual_verification --month 2024-07 [--out docs/manual_verification_layer3.md]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ..engine.backtest import FeatureStore, run_backtest
from ..engine.config import load_config
from ..engine.exec_config import load_layer3_config
from ..features.config import load_layer2_config

NY = "America/New_York"
BASELINE = "ict_lab/configs/baseline_verification.toml"


def naive_replay(bars: pd.DataFrame, t: pd.Series, policy: str) -> dict:
    """Independent re-derivation: scan the bars after order activation with plain Python."""
    bull = t["direction"] == "bullish"; lim, stop, tgt = t["entry_limit"], t["stop_price"], t["target_price"]
    rows = bars[(bars["ts_utc"] >= t["order_active_ts_utc"])]
    end = t["setup_ts_utc"].tz_convert(NY).normalize() + pd.Timedelta(hours=11)
    rth = t["setup_ts_utc"].tz_convert(NY).normalize() + pd.Timedelta(hours=16)
    fill = None
    for r in rows.itertuples():
        if r.ts_ny >= end:
            break
        if (bull and r.low < lim) or (not bull and r.high > lim) or (r.ts_utc == t["order_active_ts_utc"] and ((bull and r.open < lim) or (not bull and r.open > lim))):
            fill = r; break
    if fill is None:
        return {"filled": False}
    horizon = end if policy == "window_end" else rth
    out = {"filled": True, "fill_ts": fill.ts_utc}
    for r in rows[rows["ts_utc"] >= fill.ts_utc].itertuples():
        if r.ts_ny >= horizon:
            out.update(exit_ts=r.ts_utc, reason="time", exit_theo=r.open); return out
        s_hit = (r.low <= stop) if bull else (r.high >= stop)
        t_hit = (r.high > tgt) if bull else (r.low < tgt)
        if s_hit:
            gap = (r.open < stop) if bull else (r.open > stop)
            out.update(exit_ts=r.ts_utc, reason="stop", exit_theo=(r.open if gap else stop), ambiguous=bool(t_hit)); return out
        if t_hit:
            out.update(exit_ts=r.ts_utc, reason="target", exit_theo=tgt, ambiguous=False); return out
    out.update(exit_ts=None, reason="end_of_data"); return out


def bars_block(bars: pd.DataFrame, t: pd.Series, before: int = 3, after: int = 2) -> str:
    lo = t["setup_ts_utc"] - pd.Timedelta(minutes=before); hi = (t["exit_ts_utc"] if pd.notna(t.get("exit_ts_utc", pd.NaT)) else t["setup_ts_utc"] + pd.Timedelta(minutes=60)) + pd.Timedelta(minutes=after)
    b = bars[(bars["ts_utc"] >= lo) & (bars["ts_utc"] <= hi)].copy()
    if len(b) > 40:
        b = pd.concat([b.head(12), b.tail(12)])
    b["ny"] = b["ts_ny"].dt.strftime("%H:%M"); b["unadj_close"] = b["close"] - b["adjustment"]
    mark = []
    for r in b.itertuples():
        m = []
        if r.ts_utc == t["setup_ts_utc"]: m.append("ACTIVE")
        if pd.notna(t.get("entry_fill_ts_utc", pd.NaT)) and r.ts_utc == t["entry_fill_ts_utc"]: m.append("FILL")
        if pd.notna(t.get("exit_ts_utc", pd.NaT)) and r.ts_utc == t["exit_ts_utc"]: m.append("EXIT")
        mark.append(",".join(m))
    b["mark"] = mark
    return b[["ny", "open", "high", "low", "close", "unadj_close", "consecutive_prev", "mark"]].to_string(index=False)


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--month", default="2024-07"); ap.add_argument("--out", default="ict_lab/docs/manual_verification_layer3.md")
    a = ap.parse_args()
    l1 = load_config(); l2 = load_layer2_config(); store = FeatureStore.build(l1, l2)
    bars = store.data.bars
    base = load_layer3_config(BASELINE); variant = load_layer3_config(BASELINE, exit={"policy": "window_end"})
    md = [f"# Layer 3 manual verification — {a.month}, baseline configuration (provisional FVG-distal stop)\n",
          "Prices are back-adjusted (unadjusted close shown for basis). Bars listed from 3 minutes before order activation to 2 minutes after exit. "
          "Each trade is re-derived by an independent naive replay; `REPLAY OK` means fill time, exit time, exit reason and theoretical exit price agree.\n"]
    counts = {"trades": 0, "unfilled": 0, "stop": 0, "target": 0, "time": 0, "ambiguous": 0, "discrepancies": 0}
    for label, cfg in (("baseline (rth_end exit, 2R)", base), ("variant (window_end exit, 2R) — time-exit mechanics", variant)):
        res = run_backtest(cfg, store)
        tr = res["trades"]; tr = tr[tr["trading_date"].dt.strftime("%Y-%m") == a.month]
        nd = res["no_trade"]; nd = nd[(pd.to_datetime(nd["trading_date"]).dt.strftime("%Y-%m") == a.month) & (nd["gate_failed"] == "entry_fill")]
        md.append(f"\n## {label} — config {cfg.config_hash[:12]}\n\n{len(tr)} trades, {len(nd)} unfilled orders in {a.month}\n")
        for _, t in tr.iterrows():
            rep = naive_replay(bars, t, cfg.exit.policy)
            ok = rep["filled"] and rep["fill_ts"] == t["entry_fill_ts_utc"] and rep["exit_ts"] == t["exit_ts_utc"] and \
                 (rep["reason"] == t["exit_reason"] or (rep["reason"] == "time" and t["exit_reason"].startswith("time_exit"))) and abs(rep["exit_theo"] - t["exit_price_theoretical"]) < 1e-9 and \
                 (rep.get("ambiguous", False) == bool(t["same_bar_ambiguous"]))
            counts["trades"] += 1; counts[("time" if t["exit_reason"].startswith("time") else t["exit_reason"])] += 1
            counts["ambiguous"] += int(t["same_bar_ambiguous"]); counts["discrepancies"] += int(not ok)
            md += [f"### {t['trade_id']} — {t['direction']} ({t['level_type']} {t['level_price']:.2f}) — {'REPLAY OK' if ok else 'REPLAY DISCREPANCY'}\n",
                   f"- sweep penetration {t['sweep_penetration_ts_utc'].tz_convert(NY):%H:%M} ET, confirmed {t['sweep_confirmation_ts_utc'].tz_convert(NY):%H:%M}; displacement candle confirmed {t['displacement_confirmation_ts_utc'].tz_convert(NY):%H:%M} (ratio {t['displacement_ratio']:.2f}); "
                   f"FVG {t['fvg_timeframe']} {t['fvg_lower']:.2f}–{t['fvg_upper']:.2f} confirmed {t['fvg_confirmation_ts_utc'].tz_convert(NY):%H:%M}",
                   f"- order active {t['order_active_ts_utc'].tz_convert(NY):%H:%M}, limit {t['entry_limit']:.2f} (midpoint), filled {t['entry_fill_ts_utc'].tz_convert(NY):%H:%M} @ {t['entry_price']:.2f}; stop {t['stop_price']:.2f}; target {t['target_price']:.2f} ({t['target_source']}); risk {t['planned_risk_points']:.2f} pts",
                   f"- exit {t['exit_ts_utc'].tz_convert(NY):%H:%M} @ {t['exit_price']:.2f} ({t['exit_reason']}; theoretical {t['exit_price_theoretical']:.2f}); gross {t['gross_points']:+.2f} pts = ${t['gross_pnl_usd']:+.2f}; commission ${t['commission_usd']:.2f}; slippage ${t['slippage_cost_usd']:.2f}; net ${t['net_pnl_usd']:+.2f} ({t['net_r']:+.2f}R); MFE {t['mfe_r']:.2f}R MAE {t['mae_r']:.2f}R; ambiguous={t['same_bar_ambiguous']}; unadjusted entry {t['entry_price_unadjusted']:.2f} ({t['entry_symbol']})\n",
                   "```", bars_block(bars, t), "```\n"]
        for _, n in nd.iterrows():
            counts["unfilled"] += 1
            t = n.copy(); t["order_active_ts_utc"] = t["setup_ts_utc"]
            b = bars[(bars["ts_utc"] >= t["setup_ts_utc"]) & (bars["ts_ny"] < t["setup_ts_utc"].tz_convert(NY).normalize() + pd.Timedelta(hours=11))]
            lim = n["entry_limit"]; bull = n["direction"] == "bullish"
            touched = bool(((b["low"] < lim) if bull else (b["high"] > lim)).any())
            closest = (b["low"].min() - lim) if bull else (lim - b["high"].max())
            md += [f"### unfilled order — {n['trading_date'].date() if hasattr(n['trading_date'], 'date') else n['trading_date']} {n['direction']} limit {lim:.2f} active {t['setup_ts_utc'].tz_convert(NY):%H:%M} — {'VERIFIED (never traded through before 11:00)' if not touched else 'DISCREPANCY'}",
                   f"- bars until window end: {len(b)}; closest approach {closest:+.2f} pts from the limit; stop would have been {n.get('stop', float('nan'))}, target {n.get('target', float('nan'))}\n"]
            counts["discrepancies"] += int(touched)
    md.insert(2, f"**Summary:** trades {counts['trades']} (stop {counts['stop']}, target {counts['target']}, time {counts['time']}, ambiguous {counts['ambiguous']}), unfilled orders {counts['unfilled']}, replay discrepancies {counts['discrepancies']}.\n")
    Path(a.out).write_text("\n".join(md)); print("\n".join(md[:4])); print("wrote", a.out)


if __name__ == "__main__":
    main()
