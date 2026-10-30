"""Print the Layer 1 final summary from the manifest, reports and (optionally) a pytest result file."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ..engine.config import load_config


def main(pytest_summary: str | None = None) -> None:
    cfg = load_config(); clean = cfg.resolve("clean_dir")
    m = json.loads((clean / "manifest.json").read_text())
    q = m["quality_summary"]
    lines = [
        "LAYER 1 SUMMARY — MNQ 1-minute data infrastructure",
        f"  total source bars (all outright files):        {m['source_rows']:,}  (after cross-job de-dup: {m['source_rows_dedup']:,})",
        f"  continuous-series bars (each series):          {m['continuous_rows']:,}",
        f"  date range (NY):                               {m['first_bar_ny']}  ->  {m['last_bar_ny']}",
        f"  trading sessions:                              {m['trading_sessions']}  (complete {m['sessions_complete']}; truncated final {q['truncated_final_session']})",
        f"  rolls:                                         {m['rolls']}",
        f"  missing-data findings:                         {q['total_missing_session_minutes']:,} nominal session minutes without a bar; "
        f"{len(q['missing_trading_dates'])} weekday dates with no session; {q['intra_session_gaps']} intra-session gaps; known anomalies reproduced: "
        f"{all(a['matches_expectation'] for a in q['known_anomalies'])}; vendor-degraded sessions: {q['sessions_vendor_degraded']}",
        f"  development:                                   {m['split']['development_start']} -> {m['split']['development_end']}  ({m['split_session_counts'].get('development')} sessions)",
        f"  holdout (untouched):                           {m['split']['holdout_start']} -> {m['split']['holdout_end']}  ({m['split_session_counts'].get('holdout')} sessions)",
        f"  excluded from both splits:                     {m['split_session_counts'].get('excluded', 0)} session(s)",
        f"  config hash:                                   {m['config_hash'][:16]}…   backadjusted content hash: {m['outputs']['MNQ_1m_backadjusted.parquet']['content_hash'][:16]}…",
        f"  software:                                      {m['software']}",
    ]
    if pytest_summary:
        lines.append(f"  test results:                                  {pytest_summary}")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
