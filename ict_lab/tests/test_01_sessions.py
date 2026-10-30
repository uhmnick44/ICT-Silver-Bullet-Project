"""Trading-date assignment and DST handling."""
import pandas as pd
import pytest


def utc(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def ny(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="America/New_York").tz_convert("UTC")


@pytest.mark.parametrize("local, expected", [
    ("2024-05-14 18:00", "2024-05-15"),   # session open -> next date
    ("2024-05-14 17:59", "2024-05-14"),   # maintenance minute -> own date
    ("2024-05-14 16:59", "2024-05-14"),   # last bar of the session
    ("2024-05-15 00:00", "2024-05-15"),   # midnight -> own date
    ("2024-05-15 09:30", "2024-05-15"),
    ("2024-05-12 18:00", "2024-05-13"),   # Sunday open -> Monday
])
def test_trading_date_rule(sessions, local, expected):
    td = sessions.trading_date(pd.DatetimeIndex([ny(local)]))
    assert str(td[0].astype("datetime64[D]")) == expected


def test_dst_spring_forward(sessions):
    # 2024-03-10 clocks jump 02:00 -> 03:00. Friday session before: EST; Monday session after: EDT.
    assert sessions.session_open_utc("2024-03-08") == utc("2024-03-07 23:00")  # 18:00 EST
    assert sessions.session_open_utc("2024-03-11") == utc("2024-03-10 22:00")  # 18:00 EDT
    assert sessions.session_close_utc("2024-03-08") == utc("2024-03-08 22:00")  # 17:00 EST
    assert sessions.session_close_utc("2024-03-11") == utc("2024-03-11 21:00")  # 17:00 EDT
    td = sessions.trading_date(pd.DatetimeIndex([utc("2024-03-10 22:00"), utc("2024-03-10 21:59")]))
    assert str(td[0].astype("datetime64[D]")) == "2024-03-11"
    assert str(td[1].astype("datetime64[D]")) == "2024-03-10"  # 17:59 EDT Sunday (no bar exists, but rule holds)


def test_dst_fall_back(sessions):
    # 2024-11-03 clocks go 02:00 -> 01:00.
    assert sessions.session_open_utc("2024-11-01") == utc("2024-10-31 22:00")  # EDT
    assert sessions.session_open_utc("2024-11-04") == utc("2024-11-03 23:00")  # EST
    grid = sessions.expected_session_minutes("2024-11-04")
    assert len(grid) == 1380 and grid[0] == utc("2024-11-03 23:00") and grid[-1] == utc("2024-11-04 21:59")


def test_window_flags_follow_wall_clock_across_dst(sessions):
    # 10:00 ET is 14:00 UTC in EDT and 15:00 UTC in EST
    idx = pd.DatetimeIndex([utc("2024-07-10 14:00"), utc("2024-07-10 15:00"), utc("2024-12-10 15:00"), utc("2024-12-10 14:00")])
    loc = idx.tz_convert(sessions.timezone)
    flags = sessions.in_window(loc, "sb_ny_am")
    assert list(flags) == [True, False, True, False]


@pytest.mark.parametrize("name, inside, outside", [
    ("rth", ["09:30", "15:59"], ["09:29", "16:00"]),
    ("sb_london", ["03:00", "03:59"], ["02:59", "04:00"]),
    ("sb_ny_am", ["10:00", "10:59"], ["09:59", "11:00"]),
    ("sb_ny_pm", ["14:00", "14:59"], ["13:59", "15:00"]),
])
def test_windows_are_half_open(sessions, name, inside, outside):
    mk = lambda hm: pd.Timestamp(f"2024-05-15 {hm}", tz="America/New_York")
    loc = pd.DatetimeIndex([mk(h) for h in inside + outside])
    f = sessions.in_window(loc, name)
    assert list(f) == [True, True, False, False]


def test_real_data_session_bounds(session_table, sessions):
    full = session_table[session_table["session_complete"]]
    assert len(full) > 900
    assert full["opens_on_time"].all() and full["closes_on_time"].all()
    # a full session's bars are exactly the nominal grid
    assert (full["n_bars"] == sessions.full_session_minutes).all()
