"""Silver Bullet window eligibility per (trading_date, window), inherited from Layer 1 session flags,
with explicit exclusion reasons."""
from __future__ import annotations

import pandas as pd

WINDOW_COLS = ["series_id", "trading_date", "window", "start_ts_utc", "end_ts_utc", "start_ny", "end_ny", "n_bars", "expected_bars",
               "eligible", "exclusion_reasons", "observed_session_status", "calendar_status", "vendor_degraded_utc_overlap"]


def window_table(sessions: pd.DataFrame, sessions_spec, windows: tuple[str, ...], series_id: str) -> pd.DataFrame:
    rows = []
    for _, s in sessions.iterrows():
        d = s["trading_date"]
        for w in windows:
            a, b = sessions_spec.windows[w]
            start = sessions_spec.session_close_utc(d) - pd.Timedelta(minutes=sessions_spec.close_minute - a)
            end = start + pd.Timedelta(minutes=b - a)
            n = int(s[f"n_bars_{w}"]); exp = b - a
            reasons = []
            if n != exp: reasons.append(f"incomplete_window_bars({n}/{exp})")
            if bool(s["is_truncated_final"]): reasons.append("truncated_final_session")
            if bool(s.get("noncausal_contract_selection", False)): reasons.append("noncausal_contract_selection")
            eligible = bool(s[f"eligible_{w}"])
            if eligible and reasons:
                raise RuntimeError(f"Layer 1 eligibility disagrees with reasons for {d} {w}")
            if not eligible and not reasons:
                reasons.append("layer1_ineligible")
            rows.append({"series_id": series_id, "trading_date": d, "window": w, "start_ts_utc": start, "end_ts_utc": end,
                         "start_ny": start.tz_convert(sessions_spec.timezone), "end_ny": end.tz_convert(sessions_spec.timezone),
                         "n_bars": n, "expected_bars": exp, "eligible": eligible, "exclusion_reasons": ";".join(reasons),
                         "observed_session_status": s["observed_session_status"], "calendar_status": s["calendar_status"],
                         "vendor_degraded_utc_overlap": bool(s["vendor_degraded_utc_overlap"])})
    return pd.DataFrame(rows, columns=WINDOW_COLS)
