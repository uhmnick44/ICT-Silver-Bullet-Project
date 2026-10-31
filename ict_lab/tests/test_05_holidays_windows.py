"""Holiday / early-close handling and Silver Bullet window flags on real data."""
import pandas as pd


def row(st, d):
    r = st[st["trading_date"] == pd.Timestamp(d)]
    assert len(r) == 1, d
    return r.iloc[0]


def test_thanksgiving_and_day_after(session_table):
    r = row(session_table, "2024-11-28")
    assert r["n_bars"] == 1140 and r["early_close_minutes"] == 240 and r["last_bar_ny"].strftime("%H:%M") == "12:59"
    assert not r["eligible_rth"] and not r["eligible_sb_ny_pm"] and r["eligible_sb_ny_am"] and r["eligible_sb_london"]
    r2 = row(session_table, "2024-11-29")
    assert r2["last_bar_ny"].strftime("%H:%M") == "13:14" and not r2["eligible_sb_ny_pm"] and r2["eligible_sb_ny_am"]


def test_full_closures_absent(session_table):
    for d in ["2024-03-29", "2024-12-25", "2025-01-01", "2025-04-18"]:
        assert not (session_table["trading_date"] == pd.Timestamp(d)).any()


def test_partial_morning_sessions(session_table):
    r = row(session_table, "2025-01-09")
    assert r["last_bar_ny"].strftime("%H:%M") == "09:29" and not r["eligible_sb_ny_am"] and r["eligible_sb_london"]
    r = row(session_table, "2023-04-07")
    assert r["last_bar_ny"].strftime("%H:%M") == "09:14" and not r["eligible_rth"]


def test_truncated_final_session(session_table):
    r = row(session_table, "2026-10-21")
    assert r["is_truncated_final"] and r["observed_session_status"] == "truncated_final_session"
    assert not (r["eligible_rth"] or r["eligible_sb_london"] or r["eligible_sb_ny_am"] or r["eligible_sb_ny_pm"])
    assert r["split"] == "excluded"


def test_thanksgiving_2025_hole_makes_london_ineligible(session_table):
    r = row(session_table, "2025-11-28")
    assert r["vendor_degraded_utc_overlap"] and r["vendor_degraded_with_observed_loss"] and r["internal_missing_minutes"] == 645
    # degraded UTC date 2025-11-28 spans 19:00 ET 11/27 -> 19:00 ET 11/28, so the overlap holds the
    # 645-minute internal hole plus the 225 observed early-close minutes (13:15-16:59 ET)
    assert r["missing_minutes_in_degraded_utc_window"] == 645 + 225 and r["early_close_minutes"] == 225
    assert not r["eligible_sb_london"] and r["eligible_sb_ny_am"] and not r["eligible_sb_ny_pm"]


def test_window_flags_on_a_complete_session(unadj):
    day = unadj[unadj["trading_date"] == pd.Timestamp("2024-05-15")]
    assert len(day) == 1380
    for w, (a, b), n in [("sb_london", ("03:00", "03:59"), 60), ("sb_ny_am", ("10:00", "10:59"), 60),
                         ("sb_ny_pm", ("14:00", "14:59"), 60), ("rth", ("09:30", "15:59"), 390)]:
        sub = day[day[f"in_{w}"]]
        assert len(sub) == n
        assert sub["ts_ny"].min().strftime("%H:%M") == a and sub["ts_ny"].max().strftime("%H:%M") == b
        assert sub[f"eligible_{w}"].all()
        assert not day.loc[~day[f"in_{w}"], f"eligible_{w}"].any()


def test_bar_level_eligibility_matches_session(unadj, session_table):
    st = session_table.set_index("trading_date")
    for w in ["rth", "sb_london", "sb_ny_am", "sb_ny_pm"]:
        per_day = unadj[unadj[f"in_{w}"]].groupby("trading_date")[f"eligible_{w}"].all()
        assert (per_day == st.loc[per_day.index, f"eligible_{w}"]).all()


def test_shortened_sessions_are_calendar_unverified_not_holidays(session_table, clean_dir):
    import pandas as pd
    early = session_table[session_table["observed_session_status"].str.contains("observed_early_close")]
    assert len(early) > 30
    assert (early["calendar_status"] == "calendar_unverified").all()
    assert "holiday" not in " ".join(session_table["observed_session_status"].unique()).lower()
    import json
    q = json.loads((clean_dir / "reports" / "data_quality_report.json").read_text())
    assert q["missing_dates_calendar_unverified"] == len(q["missing_trading_dates"])


def test_vendor_flag_does_not_exclude_complete_sessions(session_table):
    deg = session_table[session_table["vendor_degraded_utc_overlap"]]
    assert len(deg) == 11
    complete_deg = deg[deg["session_complete"]]
    assert len(complete_deg) == 9
    for w in ["rth", "sb_london", "sb_ny_am", "sb_ny_pm"]:
        assert complete_deg[f"eligible_{w}"].all()
    assert (complete_deg["missing_minutes_in_degraded_utc_window"] == 0).all()
    assert deg["vendor_degraded_with_observed_loss"].sum() == 1
    # a complete session must never be flagged as having observed loss
    assert not (session_table["session_complete"] & session_table["vendor_degraded_with_observed_loss"]).any()


def test_first_session_is_flagged_noncausal_and_ineligible(session_table, unadj):
    r = row(session_table, "2022-10-03")
    assert r["noncausal_contract_selection"] and r["session_complete"]
    assert not (r["eligible_rth"] or r["eligible_sb_london"] or r["eligible_sb_ny_am"] or r["eligible_sb_ny_pm"])
    assert session_table["noncausal_contract_selection"].sum() == 1
    first = unadj[unadj["trading_date"] == r["trading_date"]]
    assert first["noncausal_contract_selection"].all() and not first[["eligible_rth", "eligible_sb_london", "eligible_sb_ny_am", "eligible_sb_ny_pm"]].any().any()
    assert not unadj.loc[unadj["trading_date"] != r["trading_date"], "noncausal_contract_selection"].any()


def test_bar_level_degraded_flag_is_utc_date_based(unadj):
    import pandas as pd
    d = unadj[pd.DatetimeIndex(unadj["ts_utc"]).strftime("%Y-%m-%d") == "2024-09-18"]
    assert d["in_vendor_degraded_utc_date"].all()
    assert not unadj.loc[pd.DatetimeIndex(unadj["ts_utc"]).strftime("%Y-%m-%d") == "2024-09-17", "in_vendor_degraded_utc_date"].any()
