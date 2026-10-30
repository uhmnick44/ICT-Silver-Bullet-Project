"""Every continuous bar is a verbatim source bar; genuine holes stay holes; nothing outside sessions."""
import pandas as pd


def test_every_bar_exists_in_source_cache(clean_dir, unadj):
    parts = [pd.read_parquet(p) for p in sorted((clean_dir / "contracts").glob("*.parquet"))]
    src = pd.concat(parts, ignore_index=True).drop_duplicates(["symbol", "ts_utc"])
    m = unadj[["ts_utc", "symbol", "open", "high", "low", "close", "volume"]].merge(
        src, on=["ts_utc", "symbol"], how="left", suffixes=("", "_src"), indicator=True)
    assert (m["_merge"] == "both").all()
    for c in ["open", "high", "low", "close", "volume"]:
        assert (m[c] == m[f"{c}_src"]).all()


def test_bar_count_equals_selected_source_bars(clean_dir, unadj):
    parts = [pd.read_parquet(p) for p in sorted((clean_dir / "contracts").glob("*.parquet"))]
    src = pd.concat(parts, ignore_index=True).drop_duplicates(["symbol", "ts_utc"])
    sel = pd.read_csv(clean_dir / "MNQ_active_contract_by_date.csv", parse_dates=["trading_date"])
    from ict_lab.engine.sessions import SessionSpec
    from ict_lab.engine.config import load_config
    s = SessionSpec.from_config(load_config())
    src["trading_date"] = pd.to_datetime(s.trading_date(pd.DatetimeIndex(src["ts_utc"])))
    n = src.merge(sel, on="trading_date").pipe(lambda d: (d["symbol"] == d["active_symbol"]).sum())
    assert n == len(unadj)


def test_known_holes_are_still_holes(unadj):
    ny = unadj["ts_ny"]
    def has(s): return (ny == pd.Timestamp(s, tz="America/New_York")).any()
    assert not has("2025-11-28 03:00") and not has("2025-11-28 08:29") and has("2025-11-28 08:30") and has("2025-11-27 21:44")
    assert not has("2025-04-02 18:00") and not has("2025-04-02 18:01") and has("2025-04-02 18:02")
    assert not has("2022-12-13 08:31") and has("2022-12-13 08:30") and has("2022-12-13 08:32")
    assert not has("2025-04-02 16:31")
    assert not unadj.loc[ny == pd.Timestamp("2025-11-28 08:30", tz="America/New_York"), "consecutive_prev"].iloc[0]
    assert unadj.loc[ny == pd.Timestamp("2025-11-28 08:30", tz="America/New_York"), "gap_prev_min"].iloc[0] == 646


def test_no_bars_in_maintenance_or_weekend(unadj):
    assert not unadj["in_maintenance"].any()
    assert not ((unadj["weekday_ny"] == 5)).any()                       # no Saturday bars
    sunday = unadj[unadj["weekday_ny"] == 6]
    assert (sunday["minute_of_day_ny"] >= 18 * 60).all()                # Sunday bars only after 18:00 open


def test_consecutive_flag_matches_gap(unadj):
    assert (unadj["consecutive_prev"] == (unadj["gap_prev_min"] == 1.0)).all()
    assert not unadj["consecutive_prev"].iloc[0]
