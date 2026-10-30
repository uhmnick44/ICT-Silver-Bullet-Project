"""Data-quality validation for the continuous series. Nothing here alters bars; it only
measures, flags and reports. Genuine missing data stays missing."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .instrument import InstrumentSpec
from .sessions import SessionSpec

PRICE_COLS = ["open", "high", "low", "close"]


# ----------------------------------------------------------------------------- sessions
def session_table(unadj: pd.DataFrame, sessions: SessionSpec, degraded_utc_dates: set[str]) -> pd.DataFrame:
    """One row per CME trading date present in the continuous series."""
    rows = []
    last_date = unadj["trading_date"].max()
    for d, g in unadj.groupby("trading_date", sort=True):
        g = g.sort_values("ts_utc")
        open_utc = sessions.session_open_utc(d); close_utc = sessions.session_close_utc(d)
        n = len(g)
        first, last = g["ts_utc"].iloc[0], g["ts_utc"].iloc[-1]
        in_sess = (g["ts_utc"] >= open_utc) & (g["ts_utc"] < close_utc)
        gaps = g["ts_utc"].diff().dt.total_seconds().div(60).iloc[1:]
        internal_gap_bars = int((gaps - 1).clip(lower=0).sum())
        span_days = pd.date_range(open_utc.floor("D"), (close_utc - pd.Timedelta(minutes=1)).floor("D"), freq="D")
        degraded = any(x.strftime("%Y-%m-%d") in degraded_utc_dates for x in span_days)
        row = {
            "trading_date": d, "active_symbol": g["symbol"].iloc[0], "n_bars": n,
            "expected_minutes": sessions.full_session_minutes,
            "missing_minutes": sessions.full_session_minutes - int(in_sess.sum()),
            "bars_outside_session": int((~in_sess).sum()),
            "first_bar_utc": first, "last_bar_utc": last,
            "first_bar_ny": first.tz_convert(sessions.timezone), "last_bar_ny": last.tz_convert(sessions.timezone),
            "opens_on_time": bool(first == open_utc),
            "closes_on_time": bool(last == close_utc - pd.Timedelta(minutes=1)),
            "internal_missing_minutes": internal_gap_bars,
            "late_open_minutes": int((first - open_utc).total_seconds() // 60) if first > open_utc else 0,
            "early_close_minutes": int((close_utc - pd.Timedelta(minutes=1) - last).total_seconds() // 60) if last < close_utc - pd.Timedelta(minutes=1) else 0,
            "vendor_degraded": degraded,
            "is_final_session": bool(d == last_date),
            "session_volume": int(g["volume"].sum()),
        }
        row["session_complete"] = bool(n == sessions.full_session_minutes and in_sess.all())
        row["is_truncated_final"] = bool(row["is_final_session"] and not row["session_complete"])
        if row["session_complete"]:
            status = "complete"
        elif row["is_truncated_final"]:
            status = "truncated_final_session"
        else:
            parts = []
            if row["late_open_minutes"]: parts.append("late_open")
            if row["early_close_minutes"]: parts.append("early_close")
            if row["internal_missing_minutes"]: parts.append("internal_gaps")
            status = "+".join(parts) if parts else "incomplete"
        row["session_status"] = status
        for w in sessions.windows:
            k = int(g[f"in_{w}"].sum())
            row[f"n_bars_{w}"] = k
            row[f"eligible_{w}"] = bool(k == sessions.window_minutes(w) and not row["is_truncated_final"])
        rows.append(row)
    return pd.DataFrame(rows)


def missing_trading_dates(st: pd.DataFrame) -> pd.DataFrame:
    """Weekdays between the first and last trading date with no bars at all."""
    present = set(pd.to_datetime(st["trading_date"]).dt.normalize())
    rng = pd.bdate_range(st["trading_date"].min(), st["trading_date"].max())
    miss = [d for d in rng if d not in present]
    return pd.DataFrame({"trading_date": miss, "weekday": [d.day_name() for d in miss]})


# ----------------------------------------------------------------------------- gaps
def gap_table(unadj: pd.DataFrame, sessions: SessionSpec) -> pd.DataFrame:
    """Every pair of consecutive bars more than one minute apart, with the number of
    nominal session minutes that fall strictly inside the gap (0 for pure breaks)."""
    ts = unadj["ts_utc"].reset_index(drop=True)
    sym = unadj["symbol"].reset_index(drop=True)
    td = unadj["trading_date"].reset_index(drop=True)
    diff = ts.diff().dt.total_seconds().div(60)
    idx = np.where(diff > 1)[0]
    rows = []
    for i in idx:
        a, b = ts[i - 1], ts[i]
        # nominal minutes expected between a and b (exclusive)
        d0, d1 = td[i - 1], td[i]
        expected = 0
        for d in pd.date_range(d0, d1, freq="D"):
            grid = sessions.expected_session_minutes(d)
            expected += int(((grid > a) & (grid < b)).sum())
        la, lb = a.tz_convert(sessions.timezone), b.tz_convert(sessions.timezone)
        if expected == 0:
            cls = "weekend_closure" if la.weekday() == 4 and lb.weekday() == 6 else "maintenance_break"
        elif d0 != d1 and expected >= sessions.full_session_minutes:
            cls = "exchange_closed_full_session"
        elif d0 != d1:
            cls = "early_close_or_late_open"
        else:
            cls = "intra_session_gap"
        rows.append({"gap_start_utc": a, "gap_end_utc": b, "gap_start_ny": la, "gap_end_ny": lb,
                     "gap_minutes": float(diff[i]), "missing_session_minutes": expected,
                     "class": cls, "symbol_before": sym[i - 1], "symbol_after": sym[i],
                     "trading_date_before": d0, "trading_date_after": d1})
    return pd.DataFrame(rows)


def verify_known_anomalies(gaps: pd.DataFrame, cfg, sessions: SessionSpec) -> pd.DataFrame:
    """Each configured anomaly must be present in the gap table with the expected size."""
    rows = []
    for a in cfg["quality"].get("known_anomalies", []):
        s = pd.Timestamp(a["gap_start_ny"]).tz_localize(sessions.timezone)
        e = pd.Timestamp(a["gap_end_ny"]).tz_localize(sessions.timezone)
        hit = gaps[(gaps["gap_start_ny"] == s) & (gaps["gap_end_ny"] == e)]
        found = len(hit) == 1
        got = int(hit["missing_session_minutes"].iloc[0]) if found else None
        ok = found and got == int(a["expected_missing_minutes"])
        rows.append({"anomaly_id": a["id"], "gap_start_ny": s, "gap_end_ny": e,
                     "expected_missing_minutes": int(a["expected_missing_minutes"]),
                     "observed_missing_minutes": got, "vendor_flag": a.get("vendor_flag", "none"),
                     "detected": found, "matches_expectation": ok})
    out = pd.DataFrame(rows)
    if len(out) and not out["matches_expectation"].all():
        bad = out[~out["matches_expectation"]]["anomaly_id"].tolist()
        raise RuntimeError(f"known anomalies not reproduced by the pipeline: {bad}")
    return out


# ----------------------------------------------------------------------------- bar checks
def bar_checks(df: pd.DataFrame, spec: InstrumentSpec) -> dict:
    inv_ohlc = (df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1)) | (df["high"] < df["low"])
    off = ~np.all([spec.on_tick_grid(df[c].to_numpy()) for c in PRICE_COLS], axis=0)
    return {
        "rows": int(len(df)),
        "duplicate_timestamps": int(df["ts_utc"].duplicated().sum()),
        "non_monotonic_timestamps": int((df["ts_utc"].diff().dt.total_seconds() < 0).sum()),
        "zero_volume_bars": int((df["volume"] <= 0).sum()),
        "invalid_ohlc_bars": int(inv_ohlc.sum()),
        "nonpositive_price_bars": int((df[PRICE_COLS] <= 0).any(axis=1).sum()),
        "off_tick_bars": int(off.sum()),
        "nan_fields": int(df[PRICE_COLS + ["volume"]].isna().sum().sum()),
        "minute_aligned": bool((pd.DatetimeIndex(df["ts_utc"]).second == 0).all()),
    }


def discontinuities(adj: pd.DataFrame, unadj: pd.DataFrame, threshold_points: float, sessions: SessionSpec) -> pd.DataFrame:
    """Consecutive-bar moves (prev close -> open) within the same trading date larger than the
    threshold, measured in the back-adjusted series; also reports the move at each roll boundary."""
    same_day = adj["trading_date"].to_numpy()[1:] == adj["trading_date"].to_numpy()[:-1]
    jump = adj["open"].to_numpy()[1:] - adj["close"].to_numpy()[:-1]
    ujump = unadj["open"].to_numpy()[1:] - unadj["close"].to_numpy()[:-1]
    i = np.where(same_day & (np.abs(jump) > threshold_points))[0] + 1
    rows = [{"ts_utc": adj["ts_utc"].iloc[k], "ts_ny": adj["ts_utc"].iloc[k].tz_convert(sessions.timezone),
             "symbol": adj["symbol"].iloc[k], "jump_points_adjusted": float(jump[k - 1]),
             "jump_points_unadjusted": float(ujump[k - 1]), "gap_prev_min": float(adj["gap_prev_min"].iloc[k]),
             "kind": "abnormal_intra_session_move"} for k in i]
    r = np.where(adj["is_first_bar_of_contract"].to_numpy()[1:])[0] + 1
    for k in r:
        rows.append({"ts_utc": adj["ts_utc"].iloc[k], "ts_ny": adj["ts_utc"].iloc[k].tz_convert(sessions.timezone),
                     "symbol": adj["symbol"].iloc[k], "jump_points_adjusted": float(jump[k - 1]),
                     "jump_points_unadjusted": float(ujump[k - 1]), "gap_prev_min": float(adj["gap_prev_min"].iloc[k]),
                     "kind": "roll_boundary"})
    return pd.DataFrame(rows).sort_values("ts_utc").reset_index(drop=True) if rows else pd.DataFrame(
        columns=["ts_utc", "ts_ny", "symbol", "jump_points_adjusted", "jump_points_unadjusted", "gap_prev_min", "kind"])


# ----------------------------------------------------------------------------- reports
def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    d = df if max_rows is None else df.head(max_rows)
    if len(d) == 0:
        return "_none_\n"
    return d.to_markdown(index=False) + "\n"


def write_quality_report(out_dir: Path, *, checks_unadj: dict, checks_adj: dict, st: pd.DataFrame,
                         gaps: pd.DataFrame, anomalies: pd.DataFrame, missing_dates: pd.DataFrame,
                         disc: pd.DataFrame, roll_log: pd.DataFrame, sessions: SessionSpec, split_counts: dict) -> dict:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    incomplete = st[~st["session_complete"]]
    summary = {
        "bar_checks_unadjusted": checks_unadj, "bar_checks_backadjusted": checks_adj,
        "sessions_total": int(len(st)), "sessions_complete": int(st["session_complete"].sum()),
        "sessions_incomplete": int((~st["session_complete"]).sum()),
        "sessions_vendor_degraded": int(st["vendor_degraded"].sum()),
        "truncated_final_session": st.loc[st["is_truncated_final"], "trading_date"].dt.strftime("%Y-%m-%d").tolist(),
        "missing_trading_dates": missing_dates["trading_date"].dt.strftime("%Y-%m-%d").tolist(),
        "total_missing_session_minutes": int(st["missing_minutes"].sum()),
        "gaps_total": int(len(gaps)), "gaps_by_class": gaps["class"].value_counts().to_dict() if len(gaps) else {},
        "intra_session_gaps": int((gaps["class"] == "intra_session_gap").sum()) if len(gaps) else 0,
        "known_anomalies": anomalies.assign(gap_start_ny=anomalies["gap_start_ny"].astype(str), gap_end_ny=anomalies["gap_end_ny"].astype(str)).to_dict("records"),
        "abnormal_discontinuities": int((disc["kind"] == "abnormal_intra_session_move").sum()) if len(disc) else 0,
        "roll_dates": roll_log["effective_trading_date"].dt.strftime("%Y-%m-%d").tolist() if len(roll_log) else [],
        "window_eligibility": {w: {"eligible_sessions": int(st[f"eligible_{w}"].sum()), "ineligible_sessions": int((~st[f"eligible_{w}"]).sum())} for w in sessions.windows},
        "split_session_counts": split_counts,
    }
    md = ["# Data-quality report — MNQ 1-minute continuous series\n",
          "## Bar-level checks (unadjusted / back-adjusted)\n",
          _md_table(pd.DataFrame([{"series": "unadjusted", **checks_unadj}, {"series": "backadjusted", **checks_adj}])),
          "## Sessions\n",
          f"- Trading sessions: {summary['sessions_total']} (complete {summary['sessions_complete']}, incomplete {summary['sessions_incomplete']}, vendor-degraded {summary['sessions_vendor_degraded']})",
          f"- Truncated final session (excluded from complete-session calculations): {summary['truncated_final_session']}",
          f"- Total nominal session minutes with no bar: {summary['total_missing_session_minutes']}",
          f"- Weekdays with no bars at all (exchange closed per data): {len(missing_dates)}\n",
          _md_table(missing_dates),
          "### Incomplete sessions\n", _md_table(incomplete[["trading_date", "active_symbol", "n_bars", "missing_minutes", "late_open_minutes", "early_close_minutes", "internal_missing_minutes", "first_bar_ny", "last_bar_ny", "vendor_degraded", "session_status"]]),
          "## Gaps between consecutive bars\n", f"- By class: {summary['gaps_by_class']}\n",
          "### Intra-session gaps (bars missing inside a session)\n",
          _md_table(gaps[gaps["class"] == "intra_session_gap"][["gap_start_ny", "gap_end_ny", "gap_minutes", "missing_session_minutes", "symbol_before", "trading_date_after"]]) if len(gaps) else "_none_\n",
          "### Known anomalies (must all be detected)\n", _md_table(anomalies),
          "## Vendor-degraded sessions (Databento condition.json)\n",
          _md_table(st[st["vendor_degraded"]][["trading_date", "active_symbol", "n_bars", "missing_minutes", "session_status"]]),
          "## Abnormal price discontinuities and roll boundaries\n",
          f"- Threshold for abnormal intra-session move: configured in [quality].abnormal_jump_points\n",
          _md_table(disc),
          "## Window eligibility rule\n",
          "A session's window (RTH, London SB, NY AM SB, NY PM SB) is eligible only if every minute of the half-open window has a bar "
          "and the session is not the truncated final session. Bars carry `eligible_<window>` so detectors can skip ineligible windows. "
          "`consecutive_prev` is False on any bar that does not follow its predecessor by exactly one minute.\n",
          _md_table(pd.DataFrame([{"window": w, **v} for w, v in summary["window_eligibility"].items()])),
          ]
    (out_dir / "data_quality_report.md").write_text("\n".join(md))
    (out_dir / "data_quality_report.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary


def write_session_coverage_report(out_dir: Path, st: pd.DataFrame, sessions: SessionSpec) -> None:
    out_dir = Path(out_dir)
    st.to_csv(out_dir / "session_coverage.csv", index=False)
    by_year = st.groupby(st["trading_date"].dt.year).agg(
        sessions=("trading_date", "size"), complete=("session_complete", "sum"),
        **{f"eligible_{w}": (f"eligible_{w}", "sum") for w in sessions.windows}).reset_index()
    status = st["session_status"].value_counts().reset_index(); status.columns = ["session_status", "sessions"]
    md = ["# Session coverage report\n",
          f"- Sessions: {len(st)}; complete: {int(st['session_complete'].sum())}; first: {st['trading_date'].min().date()}; last: {st['trading_date'].max().date()}\n",
          "## By year\n", _md_table(by_year), "## By status\n", _md_table(status),
          "## Sessions with at least one ineligible window\n",
          _md_table(st[~st[[f"eligible_{w}" for w in sessions.windows]].all(axis=1)][["trading_date", "active_symbol", "n_bars", "session_status"] + [f"eligible_{w}" for w in sessions.windows]])]
    (out_dir / "session_coverage_report.md").write_text("\n".join(md))
