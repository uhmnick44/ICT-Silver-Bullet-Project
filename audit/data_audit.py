#!/usr/bin/env python3
"""Phase 1 read-only data audit for Databento GLBX.MDP3 ohlcv-1m MNQ batch downloads.

Usage: python3 data_audit.py <raw_dir> <out_dir>
  raw_dir : directory tree containing extracted Databento batch folders (never written to)
  out_dir : where audit_report.md / audit_report.json / per-contract CSV tables are written

Nothing in raw_dir is modified. All conclusions are derived only from the files found.
"""
import sys, os, json, glob, collections
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from databento import DBNStore

NY = "America/New_York"
raw_dir, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
rep = {"generated_utc": datetime.now(timezone.utc).isoformat(), "raw_dir": raw_dir}
md = []
def H(s): md.append(f"\n## {s}\n")
def P(s=""): md.append(s)
def T(df, max_rows=None):
    d = df if max_rows is None else df.head(max_rows)
    md.append(d.to_markdown(index=False))
    md.append("")

# ---------------------------------------------------------------- 1. batch metadata
H("1. Batch jobs, files, formats, schemas")
batches = sorted(glob.glob(os.path.join(raw_dir, "*")))
batch_info = []
for b in batches:
    mp = os.path.join(b, "metadata.json")
    if not os.path.exists(mp):
        continue
    m = json.load(open(mp))
    q = m["query"]
    cond = json.load(open(os.path.join(b, "condition.json")))
    cc = collections.Counter(c["condition"] for c in cond)
    batch_info.append({
        "batch_dir": os.path.basename(b), "job_id": m["job_id"], "dataset": q["dataset"], "schema": q["schema"],
        "symbols": ",".join(q["symbols"]), "stype_in": q["stype_in"], "stype_out": q["stype_out"],
        "query_start_utc": pd.Timestamp(q["start"], unit="ns", tz="UTC").isoformat(),
        "query_end_utc": pd.Timestamp(q["end"], unit="ns", tz="UTC").isoformat(),
        "encoding": q["encoding"], "compression": q["compression"],
        "split_symbols": m["customizations"]["split_symbols"], "map_symbols": m["customizations"]["map_symbols"],
        "pretty_px": m["customizations"]["pretty_px"],
        "condition_days": len(cond), "condition_counts": dict(cc),
        "degraded_days": [c["date"] for c in cond if c["condition"] != "available"],
    })
rep["batches"] = batch_info
T(pd.DataFrame(batch_info).drop(columns=["condition_counts", "degraded_days"]))
for bi in batch_info:
    P(f"- `{bi['job_id']}` condition.json: {bi['condition_counts']}; non-available dates: {bi['degraded_days']}")

# ---------------------------------------------------------------- 2. per-file inventory
files = sorted(glob.glob(os.path.join(raw_dir, "*", "*.dbn.zst")))
inv = []
frames = []
for f in files:
    st = DBNStore.from_file(f)
    md_ = st.metadata
    sym = os.path.basename(f).split(".")[-3]  # ...ohlcv-1m.<SYM>.dbn.zst
    df = st.to_df(price_type="float", pretty_ts=True, map_symbols=True)
    n = len(df)
    is_spread = "-" in sym
    row = {
        "batch": os.path.basename(os.path.dirname(f)), "file": os.path.basename(f), "symbol": sym,
        "kind": "calendar_spread" if is_spread else "outright",
        "bytes_compressed": os.path.getsize(f), "dbn_version": md_.version, "dataset": md_.dataset,
        "schema": str(md_.schema), "stype_in": str(md_.stype_in), "stype_out": str(md_.stype_out),
        "meta_start_utc": pd.Timestamp(md_.start, unit="ns", tz="UTC").isoformat(),
        "meta_end_utc": pd.Timestamp(md_.end, unit="ns", tz="UTC").isoformat() if md_.end else None,
        "meta_symbols": ",".join(md_.symbols), "n_mappings": len(md_.mappings), "n_bars": n,
        "instrument_ids": ",".join(map(str, sorted(df["instrument_id"].unique()))) if n else "",
        "first_bar_ny": df.index.min().tz_convert(NY).isoformat() if n else None,
        "last_bar_ny": df.index.max().tz_convert(NY).isoformat() if n else None,
        "total_volume": int(df["volume"].sum()) if n else 0,
    }
    inv.append(row)
    if n and not is_spread:
        d = df.reset_index()[["ts_event", "instrument_id", "symbol", "open", "high", "low", "close", "volume"]].copy()
        d["file"] = os.path.basename(f); d["batch"] = row["batch"]
        frames.append(d)
inv_df = pd.DataFrame(inv)
inv_df.to_csv(os.path.join(out_dir, "file_inventory.csv"), index=False)
rep["file_inventory"] = inv
H("2. File inventory")
P(f"Total files: {len(inv_df)} (outrights: {(inv_df.kind=='outright').sum()}, calendar spreads: {(inv_df.kind=='calendar_spread').sum()}). "
  f"Total compressed bytes: {inv_df.bytes_compressed.sum():,}. DBN versions: {sorted(inv_df.dbn_version.unique())}. "
  f"Schemas: {sorted(inv_df.schema.unique())}. stype_in: {sorted(inv_df.stype_in.unique())}, stype_out: {sorted(inv_df.stype_out.unique())}.")
P("\nOutright contracts (one file per instrument_id per batch):\n")
T(inv_df[inv_df.kind == "outright"][["batch", "symbol", "instrument_ids", "n_bars", "total_volume", "first_bar_ny", "last_bar_ny", "bytes_compressed"]])
P("\nCalendar spread files (not needed for an outright continuous series):\n")
T(inv_df[inv_df.kind == "calendar_spread"][["batch", "symbol", "n_bars", "total_volume", "first_bar_ny", "last_bar_ny"]])

# ---------------------------------------------------------------- 3. combined outright dataset
all_ = pd.concat(frames, ignore_index=True)
all_["ts_ny"] = all_["ts_event"].dt.tz_convert(NY)
# CME trading date: Globex session opens 18:00 ET previous calendar day -> shift +6h
all_["trading_date"] = (all_["ts_ny"] + pd.Timedelta(hours=6)).dt.date
all_["cal_date_ny"] = all_["ts_ny"].dt.date
all_ = all_.sort_values(["symbol", "ts_event", "batch"]).reset_index(drop=True)

H("3. Coverage (all outright contracts combined)")
# cross-batch duplicates on (symbol, ts_event)
dup_mask = all_.duplicated(["symbol", "ts_event"], keep=False)
dups = all_[dup_mask]
xb = dups.groupby(["symbol", "ts_event"]).agg(n=("batch", "size"), nb=("batch", "nunique"),
      same=("close", lambda s: s.nunique() == 1), same_v=("volume", lambda s: s.nunique() == 1)).reset_index()
rep["cross_batch_overlap"] = {
    "duplicate_bar_rows": int(dup_mask.sum()), "duplicate_keys": int(len(xb)),
    "keys_spanning_two_batches": int((xb.nb == 2).sum()),
    "keys_same_batch": int((xb.nb == 1).sum()),
    "all_values_identical": bool(xb.same.all() and xb.same_v.all()) if len(xb) else True,
    "overlap_ny_range": [dups.ts_ny.min().isoformat(), dups.ts_ny.max().isoformat()] if len(dups) else None,
    "symbols": sorted(dups.symbol.unique().tolist()),
}
P(f"- Duplicate (symbol, ts_event) keys across the two batch jobs: {rep['cross_batch_overlap']['duplicate_keys']} "
  f"(rows {rep['cross_batch_overlap']['duplicate_bar_rows']}); spanning two batches: {rep['cross_batch_overlap']['keys_spanning_two_batches']}; "
  f"within one batch: {rep['cross_batch_overlap']['keys_same_batch']}; OHLCV identical on every duplicate: {rep['cross_batch_overlap']['all_values_identical']}; "
  f"overlap window (NY): {rep['cross_batch_overlap']['overlap_ny_range']}; symbols: {rep['cross_batch_overlap']['symbols']}")
# de-duplicated set for all further stats
dd = all_.drop_duplicates(["symbol", "ts_event"], keep="first").reset_index(drop=True)
cov = {
    "earliest_bar_ny": dd.ts_ny.min().isoformat(), "latest_bar_ny": dd.ts_ny.max().isoformat(),
    "earliest_bar_utc": dd.ts_event.min().isoformat(), "latest_bar_utc": dd.ts_event.max().isoformat(),
    "span_days": (dd.ts_event.max() - dd.ts_event.min()).days,
    "n_bars_raw_rows": int(len(all_)), "n_bars_dedup_all_contracts": int(len(dd)),
    "n_unique_timestamps": int(dd.ts_event.nunique()),
    "n_trading_dates_cme": int(dd.trading_date.nunique()), "n_calendar_dates_ny": int(dd.cal_date_ny.nunique()),
    "n_outright_contracts": int(dd.symbol.nunique()), "contracts": sorted(dd.symbol.unique().tolist()),
}
# RTH trading days: days with any bar between 09:30 and 16:00 NY
rth = dd[(dd.ts_ny.dt.hour * 60 + dd.ts_ny.dt.minute >= 570) & (dd.ts_ny.dt.hour * 60 + dd.ts_ny.dt.minute < 960)]
cov["n_dates_with_rth_bars"] = int(rth.cal_date_ny.nunique())
cov["n_weekday_dates_with_rth_bars"] = int(rth[pd.to_datetime(rth.cal_date_ny).dt.weekday < 5].cal_date_ny.nunique())
rep["coverage"] = cov
for k, v in cov.items():
    if k != "contracts": P(f"- {k}: {v}")
P(f"- contracts: {', '.join(cov['contracts'])}")

# ---------------------------------------------------------------- 4. per-contract quality checks
H("4. Per-contract data-quality checks (de-duplicated)")
def session_gap_class(t0, t1):
    """Classify a gap between consecutive bars (NY tz) as expected or unexpected relative to CME Globex hours."""
    secs = (t1 - t0).total_seconds()
    if secs <= 60: return "none"
    # daily maintenance break 17:00-18:00 ET: previous bar at <=16:59, next at >=18:00 same day
    if t0.hour == 16 and t0.minute == 59 and t1.hour == 18 and t1.minute == 0 and t1.date() == t0.date(): return "daily_break"
    if t0.weekday() == 4 and t0.hour >= 16 and t1.weekday() == 6 and t1.hour >= 18: return "weekend"
    # gaps that touch the maintenance window or the weekend but are longer (illiquid edges)
    if t0.weekday() == 4 and t1.weekday() == 6: return "weekend_extended"
    if (t1 - t0) >= pd.Timedelta(hours=1) and (t0.hour <= 17 and t1.hour >= 18 and t1.date() == t0.date()): return "daily_break_extended"
    return "intraday_gap"

q_rows, gap_rows = [], []
for sym, g in dd.groupby("symbol", sort=False):
    g = g.sort_values("ts_event")
    ts = g.ts_event
    diff = ts.diff().dt.total_seconds().dropna()
    sub60 = int((diff < 60).sum()); not_multiple = int(((diff % 60) != 0).sum())
    offsec = int((ts.dt.second != 0).sum() + (ts.dt.nanosecond != 0).sum() + (ts.dt.microsecond != 0).sum())
    bad_ohlc = int(((g.high < g[["open", "close"]].max(axis=1)) | (g.low > g[["open", "close"]].min(axis=1)) | (g.high < g.low)).sum())
    nonpos = int(((g.open <= 0) | (g.high <= 0) | (g.low <= 0) | (g.close <= 0)).sum())
    zerov = int((g.volume <= 0).sum())
    nan_ = int(g[["open", "high", "low", "close", "volume"]].isna().sum().sum())
    # tick alignment: MNQ tick = 0.25
    px = g[["open", "high", "low", "close"]].to_numpy()
    offtick = int((np.abs(px * 4 - np.round(px * 4)) > 1e-6).sum())
    # gaps
    tny = g.ts_ny.reset_index(drop=True)
    cls = collections.Counter()
    for i in range(1, len(tny)):
        c = session_gap_class(tny[i - 1], tny[i])
        if c == "none": continue
        cls[c] += 1
        secs = (tny[i] - tny[i - 1]).total_seconds()
        if c in ("intraday_gap", "daily_break_extended", "weekend_extended") and secs >= 30 * 60:
            gap_rows.append({"symbol": sym, "gap_start_ny": tny[i - 1].isoformat(), "gap_end_ny": tny[i].isoformat(),
                             "minutes": secs / 60, "class": c,
                             "in_rth": bool((tny[i - 1].hour * 60 + tny[i - 1].minute < 960) and (tny[i].hour * 60 + tny[i].minute > 570) and tny[i].date() == tny[i - 1].date() and tny[i].weekday() < 5)})
    # bars per trading date while this contract is the volume leader are computed later
    q_rows.append({"symbol": sym, "n_bars": len(g), "first_ny": tny.iloc[0].isoformat(), "last_ny": tny.iloc[-1].isoformat(),
                   "n_trading_dates": g.trading_date.nunique(), "dup_ts": int(ts.duplicated().sum()),
                   "non_monotonic": int((diff < 0).sum()), "interval_lt_60s": sub60, "interval_not_60s_multiple": not_multiple,
                   "ts_not_minute_aligned": offsec, "ohlc_inconsistent": bad_ohlc, "nonpositive_px": nonpos, "off_tick_px": offtick,
                   "zero_volume_bars": zerov, "nan_fields": nan_, "px_min": float(g.low.min()), "px_max": float(g.high.max()),
                   "gaps_daily_break": cls["daily_break"], "gaps_weekend": cls["weekend"],
                   "gaps_unexpected_ge30m": cls["intraday_gap"] + cls["daily_break_extended"] + cls["weekend_extended"]})
q_df = pd.DataFrame(q_rows)
q_df.to_csv(os.path.join(out_dir, "per_contract_quality.csv"), index=False)
gap_df = pd.DataFrame(gap_rows)
if len(gap_df): gap_df.to_csv(os.path.join(out_dir, "gaps_ge30min.csv"), index=False)
rep["per_contract_quality"] = q_rows
P("Columns: `gaps_unexpected_ge30m` counts gaps >= 30 min that are not the 17:00-18:00 ET daily break or the Friday-to-Sunday closure. "
  "Databento ohlcv bars are only emitted for minutes with at least one trade, so gaps in illiquid back-month contracts are expected and are not data loss.\n")
T(q_df)

# ---------------------------------------------------------------- 5. front-month determination and roll log (derived)
H("5. Volume-based front-month identification and derived roll log")
dv = dd.groupby(["trading_date", "symbol"]).agg(volume=("volume", "sum"), bars=("volume", "size")).reset_index()
piv = dv.pivot(index="trading_date", columns="symbol", values="volume").fillna(0)
lead = piv.idxmax(axis=1).rename("front_by_volume")
lead_vol = piv.max(axis=1).rename("front_volume")
tot = piv.sum(axis=1).rename("total_volume")
daily = pd.concat([lead, lead_vol, tot], axis=1)
daily["front_share"] = daily.front_volume / daily.total_volume.replace(0, np.nan)
daily["second"] = piv.apply(lambda r: r.drop(r.idxmax()).idxmax() if (r > 0).sum() > 1 else None, axis=1)
daily["second_volume"] = piv.apply(lambda r: r.drop(r.idxmax()).max() if (r > 0).sum() > 1 else 0, axis=1)
daily = daily.reset_index()
daily.to_csv(os.path.join(out_dir, "daily_volume_leader.csv"), index=False)
# roll events where the leader changes
rolls = []
prev = None
for _, r in daily.iterrows():
    if prev is not None and r.front_by_volume != prev.front_by_volume:
        rolls.append({"trading_date_first_day_new_front": str(r.trading_date), "from": prev.front_by_volume, "to": r.front_by_volume,
                      "from_vol_prev_day": int(prev.front_volume), "to_vol_prev_day": int(piv.loc[prev.trading_date, r.front_by_volume]),
                      "to_vol_new_day": int(r.front_volume), "from_vol_new_day": int(piv.loc[r.trading_date, prev.front_by_volume])})
    prev = r
roll_df = pd.DataFrame(rolls)
# flag flip-flops (leader reverts within 5 trading days)
if len(roll_df):
    roll_df["is_flipflop"] = False
    for i in range(1, len(roll_df)):
        if roll_df.loc[i, "to"] == roll_df.loc[i - 1, "from"]:
            roll_df.loc[i, "is_flipflop"] = True; roll_df.loc[i - 1, "is_flipflop"] = True
roll_df.to_csv(os.path.join(out_dir, "derived_roll_log_volume.csv"), index=False)
rep["derived_roll_log_volume"] = rolls
P("Roll log derived from daily volume leadership (CME trading date = NY calendar date with the 18:00 ET session open assigned to the next date). "
  "This is DERIVED from the data; the files contain no Databento continuous-contract mapping because the jobs used `MNQ.FUT` parent symbology.\n")
T(roll_df)
# price gap at each roll using the last common timestamp before the roll date
H("6. Price offsets at derived rolls (needed for back-adjustment)")
offs = []
for r in rolls:
    d0 = pd.Timestamp(r["trading_date_first_day_new_front"]).date()
    a = dd[(dd.symbol == r["from"]) & (dd.trading_date == d0)].set_index("ts_event").close
    b = dd[(dd.symbol == r["to"]) & (dd.trading_date == d0)].set_index("ts_event").close
    common = a.index.intersection(b.index)
    if len(common):
        t = common.max()
        offs.append({"roll_date": str(d0), "from": r["from"], "to": r["to"], "common_minutes_on_roll_date": len(common),
                     "ref_ts_ny": t.tz_convert(NY).isoformat(), "from_close": float(a[t]), "to_close": float(b[t]), "offset_to_minus_from": float(b[t] - a[t])})
    else:
        offs.append({"roll_date": str(d0), "from": r["from"], "to": r["to"], "common_minutes_on_roll_date": 0,
                     "ref_ts_ny": None, "from_close": None, "to_close": None, "offset_to_minus_from": None})
off_df = pd.DataFrame(offs)
off_df.to_csv(os.path.join(out_dir, "roll_price_offsets.csv"), index=False)
rep["roll_price_offsets"] = offs
T(off_df)

# ---------------------------------------------------------------- 7. front-month-only series stats
H("7. Front-month-only (volume leader) series: bars per day and intraday gaps during RTH")
front = dd.merge(daily[["trading_date", "front_by_volume"]], on="trading_date")
front = front[front.symbol == front.front_by_volume].sort_values("ts_event")
front.to_csv(os.path.join(out_dir, "front_month_bars_preview.csv"), index=False, columns=["ts_event", "symbol"], chunksize=100000) if False else None
bpd = front.groupby("trading_date").size()
rep["front_series"] = {"n_bars": int(len(front)), "n_trading_dates": int(bpd.size), "bars_per_trading_date_describe": bpd.describe().to_dict()}
P(f"- Front-month bars: {len(front):,} over {bpd.size} CME trading dates. Bars/trading-date: min {bpd.min()}, 5th pct {int(bpd.quantile(.05))}, median {int(bpd.median())}, max {bpd.max()}.")
low_days = bpd[bpd < 1000]
P(f"- Trading dates with < 1000 front-month bars (likely holidays / early closes / partial sessions): {len(low_days)}")
ld = low_days.reset_index(); ld.columns = ["trading_date", "bars"]; ld["weekday"] = pd.to_datetime(ld.trading_date).dt.day_name()
ld.to_csv(os.path.join(out_dir, "front_low_bar_days.csv"), index=False)
T(ld, 60)
# RTH 09:30-16:00 ET completeness on weekdays for front month
fr = front[(front.ts_ny.dt.weekday < 5)]
mins = fr.ts_ny.dt.hour * 60 + fr.ts_ny.dt.minute
rth_f = fr[(mins >= 570) & (mins < 960)]
rth_cnt = rth_f.groupby("cal_date_ny").size()
rep["front_series"]["rth_weekdays"] = int(rth_cnt.size)
rep["front_series"]["rth_weekdays_full_390"] = int((rth_cnt == 390).sum())
rep["front_series"]["rth_weekdays_lt_380"] = int((rth_cnt < 380).sum())
P(f"- Weekdays with any RTH (09:30-16:00 ET) front-month bar: {rth_cnt.size}; with all 390 minutes: {(rth_cnt == 390).sum()}; with < 380: {(rth_cnt < 380).sum()}")
short = rth_cnt[rth_cnt < 380].reset_index(); short.columns = ["date", "rth_bars"]; short["weekday"] = pd.to_datetime(short.date).dt.day_name()
T(short, 60)
# Silver-bullet windows (NY): 03:00-04:00, 10:00-11:00, 14:00-15:00 completeness on weekdays
for name, (h0, h1) in {"london_0300_0400": (3, 4), "am_1000_1100": (10, 11), "pm_1400_1500": (14, 15)}.items():
    w = fr[(fr.ts_ny.dt.hour >= h0) & (fr.ts_ny.dt.hour < h1)].groupby("cal_date_ny").size()
    rep["front_series"][f"window_{name}"] = {"weekdays_with_bars": int(w.size), "full_60": int((w == 60).sum()), "lt_55": int((w < 55).sum())}
    P(f"- Window {name}: weekdays with bars {w.size}; with all 60 minutes {(w == 60).sum()}; with < 55 minutes {(w < 55).sum()}")

# ---------------------------------------------------------------- 7b. front-month gap scan, missing weekdays, degraded dates
H("7b. Front-month series: every gap >= 2 minutes outside the daily break / weekend closure")
ft = front.ts_ny.reset_index(drop=True); fs = front.symbol.reset_index(drop=True)
fg = []
for i in range(1, len(ft)):
    c = session_gap_class(ft[i - 1], ft[i])
    if c in ("none", "daily_break", "weekend"): continue
    secs = (ft[i] - ft[i - 1]).total_seconds()
    if secs < 120: continue
    fg.append({"gap_start_ny": ft[i - 1].isoformat(), "gap_end_ny": ft[i].isoformat(), "minutes": secs / 60, "class": c,
               "symbol_before": fs[i - 1], "symbol_after": fs[i], "weekday_start": ft[i - 1].day_name()})
fg_df = pd.DataFrame(fg)
fg_df.to_csv(os.path.join(out_dir, "front_month_gaps_ge2min.csv"), index=False)
rep["front_series"]["gaps_ge2min_outside_breaks"] = fg
P(f"- Gaps >= 2 min in the front-month series outside the 17:00-18:00 ET break and weekend closure: {len(fg_df)}. "
  "Interpretation: Databento emits no bar for a minute with zero trades, so a short gap in a liquid front month is possible but rare; long gaps on weekdays indicate holidays, early closes, exchange halts, or vendor outages.\n")
T(fg_df, 80)
H("7c. Weekdays inside the coverage span with NO front-month RTH bar (expected: exchange holidays only)")
all_wd = pd.bdate_range(pd.Timestamp(dd.cal_date_ny.min()), pd.Timestamp(dd.cal_date_ny.max()))
have = set(pd.to_datetime(rth_cnt.index))
missing_wd = [d for d in all_wd if d not in have]
mw = pd.DataFrame({"date": [d.date() for d in missing_wd], "weekday": [d.day_name() for d in missing_wd]})
mw["any_front_bar_that_calendar_day"] = [bool((front.cal_date_ny == d.date()).any()) for d in missing_wd]
rep["front_series"]["weekdays_without_rth_bars"] = mw.to_dict("records")
P(f"- Weekdays in span: {len(all_wd)}; with front-month RTH bars: {len(have)}; without: {len(mw)}\n")
T(mw)
H("7d. Databento condition.json 'degraded' dates vs what the front-month series shows")
deg = sorted({d for bi in batch_info for d in bi["degraded_days"]})
dr = []
for d in deg:
    dts = pd.Timestamp(d).date()
    sub = front[front.cal_date_ny == dts]
    gaps_d = fg_df[fg_df.gap_start_ny.str.startswith(d) | fg_df.gap_end_ny.str.startswith(d)] if len(fg_df) else fg_df
    dr.append({"date": d, "weekday": pd.Timestamp(d).day_name(), "front_bars_calendar_day": int(len(sub)),
               "rth_bars": int(rth_cnt.get(dts, 0)), "gaps_ge2min_touching_day": int(len(gaps_d)),
               "max_gap_min": float(gaps_d.minutes.max()) if len(gaps_d) else 0.0})
dr_df = pd.DataFrame(dr); rep["degraded_dates_check"] = dr
P("Databento marks a date 'degraded' when its own capture had a known issue on that date (not necessarily during the US session). "
  "`front_bars_calendar_day` counts bars whose NY calendar date equals the flagged date (a full weekday has up to 1380 bars; 1440 minus the 60-minute break).\n")
T(dr_df)

# ---------------------------------------------------------------- 8. holdout feasibility
H("8. Holdout feasibility")
last = pd.Timestamp(dd.ts_ny.max()); first = pd.Timestamp(dd.ts_ny.min())
hold_start = last - pd.DateOffset(years=2)
in_sample_days = (hold_start - first).days
rep["holdout"] = {"first_bar_ny": first.isoformat(), "last_bar_ny": last.isoformat(), "total_span_days": (last - first).days,
                  "two_year_holdout_start_ny": hold_start.isoformat(), "in_sample_span_days": in_sample_days,
                  "in_sample_trading_dates": int(dd[dd.ts_ny < hold_start].trading_date.nunique()),
                  "holdout_trading_dates": int(dd[dd.ts_ny >= hold_start].trading_date.nunique())}
for k, v in rep["holdout"].items(): P(f"- {k}: {v}")

json.dump(rep, open(os.path.join(out_dir, "audit_report.json"), "w"), indent=2, default=str)
open(os.path.join(out_dir, "audit_report.md"), "w").write("# Phase 1 Data Audit — Databento MNQ ohlcv-1m\n" + "\n".join(md))
print("done ->", out_dir)
