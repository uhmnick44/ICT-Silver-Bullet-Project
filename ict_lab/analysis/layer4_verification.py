"""Layer 4 manual verification: hand-checked development-period trades across required categories.

Usage: python -m ict_lab.analysis.layer4_verification [--out analysis/layer4_verification.md]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ..engine.backtest import FeatureStore, run_backtest
from ..engine.config import load_config
from ..engine.exec_config import NAMED_CONFIGS, load_named_config
from ..features.config import load_layer2_config
from .manual_verification import bars_block, naive_replay

NY = "America/New_York"


def describe(t: pd.Series, cfg) -> list[str]:
    f = lambda x: x.tz_convert(NY).strftime("%H:%M") if pd.notna(x) else "-"
    return [f"- bias {t['bias']}; sweep of {t['level_type']} @ {t['level_price']:.2f}: penetration {f(t['sweep_penetration_ts_utc'])} ET, confirmed {f(t['sweep_confirmation_ts_utc'])}",
            f"- displacement candle (gate) confirmed {f(t['displacement_confirmation_ts_utc'])} (ratio {t['displacement_ratio']:.2f}); stop reference candle {f(t['stop_ref_displacement_ts_utc'])} extreme {t['stop_ref_price']:.2f}",
            f"- FVG {t['fvg_timeframe']} {t['fvg_lower']:.2f}–{t['fvg_upper']:.2f} confirmed {f(t['fvg_confirmation_ts_utc'])}; setup rank in window {t['setup_rank_in_window']}, trade #{t['trade_in_window']} in window",
            f"- order active {f(t['order_active_ts_utc'])}, limit {t['entry_limit']:.2f}; filled {f(t['entry_fill_ts_utc'])} @ {t['entry_price']:.2f}; stop {t['stop_price']:.2f}; target {t['target_price']:.2f} ({t['target_source']}, fallback={t['target_fallback_used']}); risk {t['planned_risk_points']:.2f} pts, reward {t['planned_reward_r']:.2f}R planned",
            f"- exit {f(t['exit_ts_utc'])} @ {t['exit_price']:.2f} ({t['exit_reason']}); ambiguous={t['same_bar_ambiguous']}; gap_during_trade={t['gap_during_trade']}; contract {t['entry_symbol']} (unadjusted entry {t['entry_price_unadjusted']:.2f})"]


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="ict_lab/analysis/layer4_verification.md"); a = ap.parse_args()
    l1 = load_config(); l2 = load_layer2_config(); store = FeatureStore.build(l1, l2); bars = store.data.bars
    results = {n: (load_named_config(n), run_backtest(load_named_config(n), store)) for n in NAMED_CONFIGS}
    md = ["# Layer 4 manual verification — named configurations, development period\n",
          "Each reviewed trade shows the chronological feature sequence and surrounding 1-minute bars, and is re-derived by an independent naive replay (`REPLAY OK`). "
          "Stop mode is the documented substitution `displacement_candle_extreme`. No trade is fabricated; categories absent from the data are reported as such.\n"]
    picks: list[tuple[str, str, pd.Series]] = []
    chosen: set[tuple[str, str]] = set()
    def take(cat, name, mask_fn, k=1):
        """Pick up to k trades matching the category, preferring trades not yet shown (dedup by config + trade id)."""
        cfg, res = results[name]; tr = res["trades"]
        sel = tr[mask_fn(tr)] if len(tr) else tr
        fresh = sel[~sel["trade_id"].map(lambda x: (name, x) in chosen)]
        for _, t in (fresh if len(fresh) else sel).head(k).iterrows():
            picks.append((cat, name, t)); chosen.add((name, t["trade_id"]))
        return len(sel)
    take("first qualifying FVG (setup rank 0, trade #1) — 5m FVG", "as_taught_5m", lambda t: (t.setup_rank_in_window == 0) & (t.trade_in_window == 1))
    take("1-minute FVG", "as_taught_1m", lambda t: t.fvg_timeframe == "1m")
    take("15-minute liquidity swing sweep (bsl_ssl_15m universe)", "as_taught_5m", lambda t: t.level_type.str.startswith("swing_15m"))
    take("previous-session liquidity sweep", "as_traded", lambda t: t.level_type.str.startswith("prev_session"))
    n_multi = take("multiple trades within one window (trade #2)", "as_traded", lambda t: t.trade_in_window >= 2, k=2)
    take("liquidity-target selection (opposing 15m swing)", "as_taught_5m", lambda t: t.target_source == "opposing_liquidity")
    take("fixed 2R fallback (no eligible opposing liquidity)", "as_taught_1m", lambda t: t.target_fallback_used)
    take("time-based exit (RTH end)", "as_taught_1m", lambda t: t.exit_reason.str.startswith("time_exit"))
    take("same-bar ambiguity (stop-first)", "as_traded", lambda t: t.same_bar_ambiguous)
    counts = {"reviewed": 0, "discrepancies": 0}
    seen = set()
    for cat, name, t in picks:
        cfg, res = results[name]
        dup = (name, t["trade_id"]) in seen; seen.add((name, t["trade_id"]))
        rep = naive_replay(bars, t, cfg.exit.policy)
        ok = rep["filled"] and rep["fill_ts"] == t["entry_fill_ts_utc"] and rep["exit_ts"] == t["exit_ts_utc"] and \
             (rep["reason"] == t["exit_reason"] or (rep["reason"] == "time" and t["exit_reason"].startswith("time_exit"))) and \
             abs(rep["exit_theo"] - t["exit_price_theoretical"]) < 1e-9 and (rep.get("ambiguous", False) == bool(t["same_bar_ambiguous"]))
        counts["reviewed"] += 1; counts["discrepancies"] += int(not ok)
        md += [f"\n## [{cat}] {name} — {t['trade_id']} {t['direction']} — {'REPLAY OK' if ok else 'REPLAY DISCREPANCY'}{' (also shown above)' if dup else ''}\n", *describe(t, cfg), "\n```", bars_block(bars, t), "```"]
    # overlapping-setup rejection and order expiration examples from the setup logs
    for cat, name, outcome, reason in (("overlapping setup rejection — position open", "as_traded", "rejected", "position_open"),
                                       ("pending-order block — no simultaneous orders", "as_traded", "rejected", "order_pending"),
                                       ("limit order expiration (canceled at window end)", "as_taught_5m", "canceled", "order_expired_unfilled_at_window_end")):
        cfg, res = results[name]; sl = res["setups"]
        ex = sl[(sl["outcome"] == outcome) & (sl["reason"] == reason)]
        md.append(f"\n## [{cat}] {name} — {len(ex)} occurrences\n")
        if len(ex):
            e = ex.iloc[0]
            md.append(f"- example setup `{e['setup_id']}` ({e['direction']}, {e['level_type']}) at {e['setup_ts_utc'].tz_convert(NY):%Y-%m-%d %H:%M} ET → outcome `{e['outcome']}` / `{e['reason']}`")
            if reason == "position_open":
                tr = res["trades"]; blocker = tr[(tr["entry_fill_ts_utc"] <= e["setup_ts_utc"]) & (tr["exit_ts_utc"] >= e["setup_ts_utc"])]
                if len(blocker):
                    b = blocker.iloc[0]; md.append(f"- blocking position: {b['trade_id']} filled {b['entry_fill_ts_utc'].tz_convert(NY):%H:%M} ET, exited {b['exit_ts_utc'].tz_convert(NY):%H:%M} ET ({b['exit_reason']}) — the new setup's activation {e['setup_ts_utc'].tz_convert(NY):%H:%M} is not after the exit bar")
            if reason == "order_pending":
                pend = sl[(sl["trading_date"] == e["trading_date"]) & (sl["window"] == e["window"]) & (sl["outcome"] == "canceled")]
                if len(pend):
                    p0 = pend.iloc[0]; md.append(f"- pending order: setup `{p0['setup_id']}` submitted {p0['setup_ts_utc'].tz_convert(NY):%H:%M} ET, never filled, canceled at window end")
            if reason == "order_expired_unfilled_at_window_end":
                nd = res["no_trade"]; row = nd[(nd["trading_date"] == e["trading_date"]) & (nd["window"] == e["window"])]
                if len(row):
                    r0 = row.iloc[0]; lim = r0["entry_limit"]; bull = r0["direction"] == "bullish"
                    end = pd.Timestamp(e["setup_ts_utc"]).tz_convert(NY).normalize() + pd.Timedelta(hours={"sb_london": 4, "sb_ny_am": 11, "sb_ny_pm": 15}[e["window"]])
                    b = bars[(bars["ts_utc"] >= e["setup_ts_utc"]) & (bars["ts_ny"] < end)]
                    through = bool(((b["low"] < lim) if bull else (b["high"] > lim)).any())
                    md.append(f"- limit {lim:.2f}, {len(b)} bars until window end, traded through: {through} → {'VERIFIED never filled' if not through else 'DISCREPANCY'}")
                    counts["reviewed"] += 1; counts["discrepancies"] += int(through)
    md.insert(2, f"**Summary:** {counts['reviewed']} items reviewed, {counts['discrepancies']} discrepancies. Multi-trade windows present in as_traded: {n_multi} trades with rank ≥ 2.\n")
    Path(a.out).write_text("\n".join(md)); print("\n".join(md[:4])); print("wrote", a.out)


if __name__ == "__main__":
    main()
