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
    assert r["is_truncated_final"] and r["session_status"] == "truncated_final_session"
    assert not (r["eligible_rth"] or r["eligible_sb_london"] or r["eligible_sb_ny_am"] or r["eligible_sb_ny_pm"])
    assert r["split"] == "excluded"


def test_thanksgiving_2025_hole_makes_london_ineligible(session_table):
    r = row(session_table, "2025-11-28")
    assert r["vendor_degraded"] and r["internal_missing_minutes"] == 645
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
