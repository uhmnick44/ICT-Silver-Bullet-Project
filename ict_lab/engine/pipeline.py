"""Layer 1 pipeline: raw Databento zips -> validated continuous MNQ datasets + reports.

Run:  python -m ict_lab.engine.pipeline [--config path] [--force]
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import continuous, quality, rolls
from .config import Config, load_config
from .ingest import extract_zips, load_contract_bars, sha256_file
from .instrument import InstrumentSpec
from .manifest import content_hash, software_versions, write_manifest
from .sessions import SessionSpec

OUTPUT_COLUMNS = [
    "ts_utc", "ts_ny", "trading_date", "symbol", "instrument_id", "open", "high", "low", "close", "volume",
    "adjustment", "series", "minute_of_day_ny", "weekday_ny", "in_rth", "in_sb_london", "in_sb_ny_am", "in_sb_ny_pm",
    "in_maintenance", "bar_index", "gap_prev_min", "consecutive_prev", "segment_id", "is_first_bar_of_contract",
    "session_complete", "is_truncated_final", "vendor_degraded", "eligible_rth", "eligible_sb_london",
    "eligible_sb_ny_am", "eligible_sb_ny_pm", "split",
]


def assign_split(trading_date: pd.Series, cfg: Config) -> pd.Series:
    s = cfg["split"]
    td = pd.to_datetime(trading_date)
    dev = (td >= pd.Timestamp(s["development_start"])) & (td <= pd.Timestamp(s["development_end"]))
    hold = (td >= pd.Timestamp(s["holdout_start"])) & (td <= pd.Timestamp(s["holdout_end"]))
    out = pd.Series("excluded", index=trading_date.index, dtype="object")
    out[dev] = "development"; out[hold] = "holdout"
    return out


def _attach_session_flags(df: pd.DataFrame, st: pd.DataFrame, sessions: SessionSpec) -> pd.DataFrame:
    cols = ["trading_date", "session_complete", "is_truncated_final", "vendor_degraded"] + [f"eligible_{w}" for w in sessions.windows]
    m = df.merge(st[cols], on="trading_date", how="left")
    for w in sessions.windows:  # bar-level eligibility = session window eligible AND bar inside the window
        m[f"eligible_{w}"] = m[f"eligible_{w}"] & m[f"in_{w}"]
    return m


def _write_partitioned(df: pd.DataFrame, root: Path, symbol: str, series: str) -> list[dict]:
    """data/clean/partitioned/symbol_root=MNQ/series_type=<series>/year=<YYYY>/part-0.parquet (deterministic).
    Partition keys are named so they do not collide with the `symbol` / `series` data columns."""
    written = []
    years = pd.DatetimeIndex(df["trading_date"]).year
    for y in sorted(set(years)):
        part = df[years == y]
        d = root / f"symbol_root={symbol}" / f"series_type={series}" / f"year={y}"
        d.mkdir(parents=True, exist_ok=True)
        p = d / "part-0.parquet"
        _to_parquet(part, p)
        written.append({"path": str(p.relative_to(root.parent)), "rows": int(len(part)), "sha256": sha256_file(p)})
    return written


def _to_parquet(df: pd.DataFrame, path: Path) -> None:
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, path, compression="zstd", version="2.6", write_statistics=True)


def run(cfg: Config | None = None, force: bool = False, log=print) -> dict:
    t0 = time.time()
    cfg = cfg or load_config()
    spec = InstrumentSpec.from_config(cfg); sessions = SessionSpec.from_config(cfg); rule = rolls.RollRule.from_config(cfg)
    raw_dir, clean_dir, runs_dir = cfg.resolve("raw_dir"), cfg.resolve("clean_dir"), cfg.resolve("runs_dir")
    clean_dir.mkdir(parents=True, exist_ok=True); runs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = clean_dir / "reports"
    manifest_path = clean_dir / "manifest.json"

    log("[1/8] inventory + hashes of original Databento files")
    inv = extract_zips(raw_dir, spec)
    source_hashes = {f.name: f.sha256 for f in inv.files}
    identity = {"config_hash": cfg.config_hash, "zip_hashes": inv.zips, "source_hashes": source_hashes}
    if manifest_path.exists() and not force:
        old = json.loads(manifest_path.read_text())
        if all(old.get(k) == v for k, v in identity.items()) and (clean_dir / "MNQ_1m_backadjusted.parquet").exists():
            log("    outputs up to date for this config + sources (use --force to rebuild)")
            return old

    log("[2/8] decode outright contracts (cached per source hash)")
    bars = load_contract_bars(inv, clean_dir / "contracts", spec)
    bars = sessions.annotate(bars)
    n_source = int(len(bars)); rows_before = bars.attrs.get("rows_before_dedup", n_source)
    log(f"    {rows_before:,} source rows, {n_source:,} after cross-job de-dup, {bars['symbol'].nunique()} contracts")

    log("[3/8] contract selection (volume crossover) and roll log")
    dv = rolls.daily_volume(bars)
    sel, events = rolls.select_active_contracts(dv, rule, spec)
    roll_log = rolls.build_roll_log(bars, sel, events, sessions, rule, spec)
    if len(roll_log) and not roll_log["offset_is_tick_multiple"].all():
        raise RuntimeError("roll offset not on tick grid")
    log(f"    {len(roll_log)} rolls; contracts used: {sel['active_symbol'].unique().tolist()}")

    log("[4/8] continuous series")
    unadj = continuous.build_unadjusted(bars, sel, sessions)
    adj = continuous.build_backadjusted(unadj, roll_log, spec)

    log("[5/8] quality validation")
    degraded = {d for v in inv.degraded_dates.values() for d in v}
    st = quality.session_table(unadj, sessions, degraded)
    gaps = quality.gap_table(unadj, sessions)
    anomalies = quality.verify_known_anomalies(gaps, cfg, sessions)
    miss_dates = quality.missing_trading_dates(st)
    st["split"] = assign_split(st["trading_date"], cfg)
    unadj = _attach_session_flags(unadj, st, sessions); adj = _attach_session_flags(adj, st, sessions)
    unadj["split"] = assign_split(unadj["trading_date"], cfg); adj["split"] = adj["trading_date"].pipe(assign_split, cfg)
    unadj = unadj[OUTPUT_COLUMNS]; adj = adj[OUTPUT_COLUMNS]
    checks_u = quality.bar_checks(unadj, spec); checks_a = quality.bar_checks(adj, spec)
    disc = quality.discontinuities(adj, unadj, float(cfg["quality"]["abnormal_jump_points"]), sessions)
    for k in ("duplicate_timestamps", "invalid_ohlc_bars", "off_tick_bars", "nan_fields", "nonpositive_price_bars"):
        if checks_u[k] or checks_a[k]:
            raise RuntimeError(f"quality check failed: {k} = {checks_u[k]}/{checks_a[k]}")

    log("[6/8] write datasets")
    for p in [clean_dir / "partitioned"]:
        if p.exists(): shutil.rmtree(p)
    out_u = clean_dir / "MNQ_1m_unadjusted.parquet"; out_a = clean_dir / "MNQ_1m_backadjusted.parquet"
    _to_parquet(unadj, out_u); _to_parquet(adj, out_a)
    parts = _write_partitioned(unadj, clean_dir / "partitioned", spec.root, "unadjusted") + \
            _write_partitioned(adj, clean_dir / "partitioned", spec.root, "backadjusted")
    roll_cols = ["roll_id", "old_symbol", "new_symbol", "crossover_trading_date", "effective_trading_date",
                 "nominal_session_open_utc", "roll_ts_utc", "roll_ts_ny", "ref_ts_utc", "ref_ts_ny", "ref_minute_of_day_ny",
                 "ref_price_old", "ref_price_new", "offset_points", "offset_ticks", "offset_is_tick_multiple",
                 "cumulative_adjustment_before_roll", "cumulative_adjustment_after_roll", "reference_fallback_minutes",
                 "old_volume_crossover_date", "new_volume_crossover_date", "old_volume_effective_date",
                 "new_volume_effective_date", "crossover_volume_ratio", "near_tie_crossover", "n_candidates"]
    rl = roll_log[roll_cols].copy()
    # data-quality flags for each roll
    stx = st.set_index("trading_date")
    rl["crossover_session_complete"] = rl["crossover_trading_date"].map(stx["session_complete"]).astype(bool)
    rl["effective_session_complete"] = rl["effective_trading_date"].map(stx["session_complete"]).astype(bool)
    rl["crossover_vendor_degraded"] = rl["crossover_trading_date"].map(stx["vendor_degraded"]).astype(bool)
    rl["effective_vendor_degraded"] = rl["effective_trading_date"].map(stx["vendor_degraded"]).astype(bool)
    rl["roll_ts_is_nominal_open"] = rl["roll_ts_utc"] == rl["nominal_session_open_utc"]
    rl["flags"] = rl.apply(lambda r: ";".join([f for f, on in [
        ("reference_fallback", r.reference_fallback_minutes > 0), ("near_tie_crossover", bool(r.near_tie_crossover)),
        ("crossover_session_incomplete", not r.crossover_session_complete), ("effective_session_incomplete", not r.effective_session_complete),
        ("vendor_degraded", bool(r.crossover_vendor_degraded or r.effective_vendor_degraded)),
        ("roll_ts_not_nominal_open", not r.roll_ts_is_nominal_open), ("multiple_candidates", r.n_candidates > 1)] if on]) or "ok", axis=1)
    rl.to_csv(clean_dir / "MNQ_rolls.csv", index=False)
    st.to_parquet(clean_dir / "MNQ_sessions.parquet", index=False)
    dv.to_csv(clean_dir / "MNQ_daily_contract_volume.csv")
    sel.to_csv(clean_dir / "MNQ_active_contract_by_date.csv")

    log("[7/8] reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    gaps.to_csv(reports_dir / "gaps.csv", index=False); disc.to_csv(reports_dir / "discontinuities.csv", index=False)
    split_counts = st["split"].value_counts().to_dict()
    qsum = quality.write_quality_report(reports_dir, checks_unadj=checks_u, checks_adj=checks_a, st=st, gaps=gaps,
                                        anomalies=anomalies, missing_dates=miss_dates, disc=disc, roll_log=rl,
                                        sessions=sessions, split_counts=split_counts)
    quality.write_session_coverage_report(reports_dir, st, sessions)
    write_roll_report(reports_dir, rl, dv, cfg, sessions)

    log("[8/8] manifest")
    manifest = {
        **identity, "generated_utc": datetime.now(timezone.utc).isoformat(), "config_path": str(cfg.path),
        "config": cfg.raw, "jobs": inv.jobs, "degraded_dates": inv.degraded_dates, "software": software_versions(),
        "source_rows": rows_before, "source_rows_dedup": n_source, "cross_job_duplicates_dropped": bars.attrs.get("cross_job_duplicates_dropped"),
        "continuous_rows": int(len(unadj)), "first_bar_utc": str(unadj["ts_utc"].min()), "last_bar_utc": str(unadj["ts_utc"].max()),
        "first_bar_ny": str(unadj["ts_ny"].min()), "last_bar_ny": str(unadj["ts_ny"].max()),
        "trading_sessions": int(len(st)), "sessions_complete": int(st["session_complete"].sum()), "rolls": int(len(rl)),
        "split_session_counts": split_counts, "split": {k: str(v) for k, v in cfg["split"].items()},
        "outputs": {
            "MNQ_1m_unadjusted.parquet": {"sha256": sha256_file(out_u), "content_hash": content_hash(unadj), "rows": int(len(unadj))},
            "MNQ_1m_backadjusted.parquet": {"sha256": sha256_file(out_a), "content_hash": content_hash(adj), "rows": int(len(adj))},
            "MNQ_rolls.csv": {"sha256": sha256_file(clean_dir / "MNQ_rolls.csv"), "rows": int(len(rl))},
            "MNQ_sessions.parquet": {"sha256": sha256_file(clean_dir / "MNQ_sessions.parquet"), "rows": int(len(st))},
            "partitioned": parts,
        },
        "quality_summary": qsum, "elapsed_seconds": round(time.time() - t0, 1),
    }
    write_manifest(manifest_path, manifest)
    (runs_dir / f"pipeline_run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json").write_text(
        json.dumps({k: manifest[k] for k in ("generated_utc", "config_hash", "outputs", "elapsed_seconds", "software")}, indent=2, default=str))
    log(f"done in {manifest['elapsed_seconds']}s")
    return manifest


def write_roll_report(reports_dir: Path, rl: pd.DataFrame, dv: pd.DataFrame, cfg: Config, sessions: SessionSpec) -> None:
    """Roll report including a comparison with the Phase 1 audit's same-day volume-leader dates."""
    r = cfg["roll"]
    audit_same_day = _audit_same_day_leader_dates(dv)
    cmp = rl[["roll_id", "old_symbol", "new_symbol", "crossover_trading_date", "effective_trading_date"]].copy()
    cmp["audit_first_leader_date"] = cmp.apply(lambda x: audit_same_day.get((x.old_symbol, x.new_symbol)), axis=1)
    cmp["effective_minus_audit_days"] = (pd.to_datetime(cmp["effective_trading_date"]) - pd.to_datetime(cmp["audit_first_leader_date"])).dt.days
    cmp["same_transition_as_audit"] = cmp["audit_first_leader_date"].notna()
    md = ["# Contract-roll report — MNQ volume-crossover rule\n",
          "## Rule\n",
          f"- Method: {r['method']}; confirmation_days = {r['confirmation_days']}; forward_only = {r['forward_only']}; tie_break = {r['tie_break']}",
          f"- Crossover on trading date D (challenger daily volume strictly greater than incumbent) takes effect on the next trading date D+1 (no look-ahead).",
          f"- Roll timestamp = first bar of the new contract in the effective session (nominal open {cfg['session']['open_time']} ET of the preceding calendar day).",
          f"- Offset = {r['reference_price_field']}(new) − {r['reference_price_field']}(old) at the {r['reference_minute']} ET bar of the crossover session, stepping back one minute at a time within that session if either contract has no bar (flagged).",
          "- Back-adjustment: additive, anchored to the latest contract (its adjustment is 0); bars before roll k receive the sum of offsets k..n.",
          "- Initialisation: the first trading date uses its own session volume (only place same-day volume is used).\n",
          "## Roll log\n", rl.drop(columns=["nominal_session_open_utc", "ref_ts_utc", "roll_ts_utc"]).to_markdown(index=False), "\n",
          "## Comparison with the Phase 1 audit (audit = first date the new contract led volume, same-day)\n",
          "The audit's dates used each date's own full-session volume, which is not knowable at the session open. "
          "The pipeline's effective date is the next trading date after that crossover, so every pipeline roll is expected to be exactly one trading date later than the audit date for the same transition.\n",
          cmp.to_markdown(index=False), "\n",
          "## Caveat on vendor roll conventions\n",
          "The original Silver Bullet research used an unspecified vendor continuous contract. Vendor conventions (volume, open interest, fixed calendar day, Databento `.v.0`/`.n.0`/`.c.0`) differ from this rule by up to several trading days around each roll; several crossovers here are near-ties (see `near_tie_crossover`). "
          "Results from Layer 2+ must therefore be checked for sensitivity to the roll rule rather than assumed to match the vendor series.\n"]
    (reports_dir / "contract_roll_report.md").write_text("\n".join(md))
    cmp.to_csv(reports_dir / "roll_vs_audit_comparison.csv", index=False)


def _audit_same_day_leader_dates(dv: pd.DataFrame) -> dict:
    lead = dv.idxmax(axis=1)
    out = {}
    prev = None
    for d, s in lead.items():
        if prev is not None and s != prev and (prev, s) not in out:
            out[(prev, s)] = d
        prev = s
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Layer 1 MNQ data pipeline")
    ap.add_argument("--config", default=None); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    run(load_config(a.config) if a.config else None, force=a.force)


if __name__ == "__main__":
    main()
