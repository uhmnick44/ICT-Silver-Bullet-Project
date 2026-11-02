"""Layer 5 status report: what was executed, provisional screening counts, what is NOT PERFORMED and why,
and the remaining definitions that need screenshot verification or user authorization.
Usage: python -m ict_lab.analysis.layer5_report
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from .grid import OUT

REMAINING = [
    ("Sampling count and seed", "§3", "full deduplicated grid evaluated instead; a sample can be drawn later from grid.csv with sample_grid(count, seed)"),
    ("Return-frequency convention for the net Sharpe >= 0.5 screen", "§5/§6", "provisional: daily net $ P&L, sqrt(252)"),
    ("Bootstrap block-length convention", "§7", "bootstrap NOT RUN"),
    ("Raw p-value source for BH-FDR", "§6", "FDR NOT RUN"),
    ("Null A random-entry generation and stop anchoring", "§8", "NOT RUN"),
    ("Null B off-hour comparison windows", "§8", "NOT RUN"),
    ("Null C direction-shuffling procedure", "§8", "NOT RUN"),
    ("FVG-only ablation direction rule", "§9", "ablation steps 1-3 NOT PERFORMED"),
    ("No-window ablation search universe", "§9", "ablation steps 2-3 NOT PERFORMED"),
    ("Higher-cost / slippage sensitivity grid", "§10", "NOT RUN"),
    ("Walk-forward fold lengths and rolling/expanding structure", "§11", "walk-forward NOT RUN; candidate qualification cannot complete"),
    ("Chronological robustness subperiod boundaries", "§10", "NOT RUN"),
    ("Sample-size sensitivity procedure", "§10", "NOT RUN"),
]
NOT_PERFORMED_FIXED = [("Roll-convention sensitivity", "§10", "NOT PERFORMED: only one roll convention is available; Layer 1 not extended (authorized)"),
                       ("ES cross-market validation", "§10", "NOT PERFORMED: MNQ data only; MNQ-only testing does not establish cross-market robustness")]


def main() -> None:
    man = json.loads((OUT / "grid_manifest.json").read_text())
    res = pd.read_csv(OUT / "sweep_results.csv")
    abl = pd.read_csv(OUT / "ablation_partial.csv")
    ok = res[res["status"] == "ok"]; ins = res[res["status"] != "ok"]
    screen = res[res["descriptive_screen_provisional"] == True]
    md = [f"# Layer 5 status report — generated {datetime.now(timezone.utc).isoformat()}\n",
          "Development data only (holdout never accessed). All metrics are after transaction costs and slippage. "
          "Stop: user-authorized `liquidity_sweep_extreme` + 1 tick in every configuration. Nothing in this report is a claim of profitability.\n",
          "## Grid and sweep (§3)\n",
          f"- Configurations generated {man['counts']['generated']}, deduplicated {man['counts']['deduplicated']}, sampled {man['counts']['sampled']}, evaluated {man['counts']['evaluated']}. "
          f"Sampling: {man['sampling']['note']}.",
          f"- Total trades analysed: {man['total_trades']:,} (ambiguous same-bar stop/target: {man['ambiguous_trades']:,}, reported per configuration in `sweep_results.csv`).",
          f"- Configurations with >= 100 trades (status ok): {len(ok)}; insufficient data: {len(ins)}.",
          f"- Provisional descriptive screen (>= 100 trades, net Sharpe >= 0.5 under the {man['sharpe_convention'].split(';')[0]}, positive net P&L): {len(screen)} configurations. "
          "PROVISIONAL because the return-frequency convention for the 0.5 threshold is unverified.",
          "- Multiple-testing correction, bootstrap, null models, walk-forward and candidate qualification: NOT RUN (definitions pending, see below). "
          "No configuration is classified beyond 'exploratory' or 'descriptive screen (provisional)'.\n",
          "### Net expectancy (R) distribution across evaluated configurations with >= 100 trades\n",
          ok["net_expectancy_r"].describe().to_frame().T.to_markdown() if len(ok) else "_none_", "\n",
          "### Provisional descriptive-screen passers (exploratory; not statistically tested)\n",
          (screen.sort_values("net_expectancy_r", ascending=False)[["config_hash", "fvg_timeframe", "liquidity_universe", "bias_detector", "displacement_threshold", "require_mss", "entry_location",
                "windows", "max_trades_per_window", "n_trades", "net_expectancy_r", "net_sharpe", "net_pnl_usd", "profit_factor", "max_drawdown_usd", "n_ambiguous"]].head(50).to_markdown(index=False)) if len(screen) else "_none_", "\n",
          "## Ablation (§9) — partial\n", abl.to_markdown(index=False), "\n",
          "Steps 1–3 are not performed pending definitions; the perfect-future-bias row is a LOOKAHEAD diagnostic and is excluded from any candidate set. "
          "No ablation result is interpreted as causal proof.\n",
          "## Not performed by decision\n", *[f"- {a} ({b}): {c}" for a, b, c in NOT_PERFORMED_FIXED], "",
          "## Remaining definitions requiring screenshot verification or explicit authorization\n",
          *[f"{i}. {a} ({b}) — {c}" for i, (a, b, c) in enumerate(REMAINING, start=1)], "",
          "## Traceability\n",
          f"- series {man['series_id']}, roll convention {man['roll_convention']}, Layer 1 config {man['layer1_config_hash'][:12]}, back-adjusted data hash {man['layer1_backadjusted_content_hash'][:12]}, "
          f"Layer 2 config {man['layer2_config_hash'][:12]}; costs {man['costs']}; sizing {man['sizing']}; software {man['software']}; per-configuration execution hashes in `grid.csv` / `sweep_results.csv`.\n"]
    (OUT / "layer5_status.md").write_text("\n".join(md))
    print("\n".join(md[2:9]))


if __name__ == "__main__":
    main()
