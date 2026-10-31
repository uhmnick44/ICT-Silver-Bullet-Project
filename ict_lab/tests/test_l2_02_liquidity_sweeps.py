"""Layer 2: liquidity references, 15m swing confirmation, sweep confirmation, penetration thresholds, consumption."""
import pandas as pd
import pytest

from ict_lab.features.config import LiquidityConfig, SweepConfig
from ict_lab.features.liquidity import build_liquidity_levels
from ict_lab.features.swings import fractal_swings
from ict_lab.features.sweeps import detect_sweeps
from ict_lab.features.timeframes import resample
from .l2_fixtures import make_bars, flat, session_bars

NY = "America/New_York"
WINDOWS = ("sb_london", "sb_ny_am", "sb_ny_pm")


def two_sessions(sessions):
    a = session_bars(sessions, "2024-05-14", px=100, rng=1)
    # put the session high/low at known minutes: high 120 at 03:30 ET, low 80 at 12:00 ET; RTH high 110 at 11:00, RTH low 90 at 14:30
    a.loc[a["ts_ny"] == pd.Timestamp("2024-05-14 03:30", tz=NY), ["high"]] = 120
    a.loc[a["ts_ny"] == pd.Timestamp("2024-05-14 05:00", tz=NY), ["low"]] = 80
    a.loc[a["ts_ny"] == pd.Timestamp("2024-05-14 11:00", tz=NY), ["high"]] = 110
    a.loc[a["ts_ny"] == pd.Timestamp("2024-05-14 14:30", tz=NY), ["low"]] = 90
    b = session_bars(sessions, "2024-05-15", px=100, rng=1)
    return pd.concat([a, b], ignore_index=True)


def test_previous_session_and_rth_references(sessions):
    bars = two_sessions(sessions)
    lv = build_liquidity_levels(bars, sessions, LiquidityConfig(universe=("prev_session", "prev_rth")), WINDOWS, "t")
    d = lv[lv["scope_trading_date"] == pd.Timestamp("2024-05-15")].set_index("level_type")
    assert d.loc["prev_session_high", "price"] == 120 and d.loc["prev_session_low", "price"] == 80
    assert d.loc["prev_rth_high", "price"] == 110 and d.loc["prev_rth_low", "price"] == 90
    assert d.loc["prev_session_high", "formation_ts_utc"] == pd.Timestamp("2024-05-14 03:30", tz=NY)
    assert d.loc["prev_session_high", "confirmation_ts_utc"] == pd.Timestamp("2024-05-14 17:00", tz=NY)
    assert d.loc["prev_rth_high", "confirmation_ts_utc"] == pd.Timestamp("2024-05-14 16:00", tz=NY)
    assert (d["activation_ts_utc"] == pd.Timestamp("2024-05-14 18:00", tz=NY)).all()
    assert (d["expiry_ts_utc"] == pd.Timestamp("2024-05-15 17:00", tz=NY)).all()
    assert d.loc["prev_session_high", "side"] == "buyside" and d.loc["prev_session_low", "side"] == "sellside"
    # the first session has no predecessor -> no levels scoped to it
    assert not (lv["scope_trading_date"] == pd.Timestamp("2024-05-14")).any()


def test_prewindow_references(sessions):
    bars = session_bars(sessions, "2024-05-15", px=100, rng=1)
    bars.loc[bars["ts_ny"] == pd.Timestamp("2024-05-15 09:59", tz=NY), "high"] = 130   # inside pre-window of NY AM
    bars.loc[bars["ts_ny"] == pd.Timestamp("2024-05-15 10:00", tz=NY), "high"] = 140   # inside the window: must not count
    lv = build_liquidity_levels(bars, sessions, LiquidityConfig(universe=("prewindow",)), WINDOWS, "t")
    am = lv[(lv["scope_window"] == "sb_ny_am")].set_index("level_type")
    assert am.loc["prewindow_high", "price"] == 130
    assert am.loc["prewindow_high", "activation_ts_utc"] == pd.Timestamp("2024-05-15 10:00", tz=NY)
    assert am.loc["prewindow_high", "expiry_ts_utc"] == pd.Timestamp("2024-05-15 11:00", tz=NY)
    ldn = lv[(lv["scope_window"] == "sb_london")].set_index("level_type")
    assert ldn.loc["prewindow_high", "price"] == 101   # 18:00 -> 02:59 flat bars


def test_15m_swing_confirmation_timing(sessions):
    rows = flat(15 * 2, 100, 0.5) + [(100, 105, 99.5, 100.5)] * 15 + flat(15 * 2, 100, 0.5) + flat(15, 100, 0.5)
    bars = make_bars(sessions, "2024-05-15 09:00", rows)
    c15 = resample(bars, "15m")
    sw = fractal_swings(c15, 2, 2, "first", "t", "15m")
    hi = sw[sw["kind"] == "high"]
    assert len(hi) == 1 and hi["price"].iat[0] == 105
    assert hi["ts_utc"].iat[0] == pd.Timestamp("2024-05-15 09:30", tz=NY)
    assert hi["confirmation_ts_utc"].iat[0] == pd.Timestamp("2024-05-15 10:15", tz=NY)   # 2 right candles closed (09:45, 10:00)
    # with right=3 the confirmation moves one candle later
    sw3 = fractal_swings(c15, 2, 3, "first", "t", "15m")
    assert sw3[sw3["kind"] == "high"]["confirmation_ts_utc"].iat[0] == pd.Timestamp("2024-05-15 10:30", tz=NY)


def test_equal_highs_deterministic():
    import numpy as np
    c = pd.DataFrame({"high": [1, 2, 5, 5, 2, 1, 1.0], "low": [0] * 7, "available_ts_utc": pd.date_range("2024-01-01", periods=7, freq="15min", tz="UTC"),
                      "ts_utc": pd.date_range("2024-01-01", periods=7, freq="15min", tz="UTC"), "ts_ny": pd.date_range("2024-01-01", periods=7, freq="15min", tz="UTC"),
                      "trading_date": pd.Timestamp("2024-01-01")})
    first = fractal_swings(c, 2, 2, "first", "t", "15m"); last = fractal_swings(c, 2, 2, "last", "t", "15m"); strict = fractal_swings(c, 2, 2, "strict", "t", "15m")
    assert first[first.kind == "high"]["candle_index"].tolist() == [2]
    assert last[last.kind == "high"]["candle_index"].tolist() == [3]
    assert strict[strict.kind == "high"].empty


def _sweep_bars(sessions, pen_low=89.75, closes=(91, 91, 91)):
    bars = two_sessions(sessions)   # prev RTH low = 90 for 2024-05-15
    # on 2024-05-15 at 10:05 price dips to pen_low then bars close at `closes`
    t = pd.Timestamp("2024-05-15 10:05", tz=NY)
    i = bars.index[bars["ts_ny"] == t][0]
    bars.loc[i, ["open", "high", "low", "close"]] = [92, 92, pen_low, closes[0]]
    for k, c in enumerate(closes[1:], start=1):
        bars.loc[i + k, ["open", "high", "low", "close"]] = [closes[k - 1], max(closes[k - 1], c) + 0.25, min(closes[k - 1], c) - 0.25, c]
    return bars


def _run_sweeps(sessions, spec, bars, sweep_cfg=SweepConfig(), liq_cfg=LiquidityConfig(universe=("prev_rth",))):
    lv = build_liquidity_levels(bars, sessions, liq_cfg, WINDOWS, "t")
    return detect_sweeps(resample(bars, "1m"), lv, sweep_cfg, liq_cfg, spec.tick_size, sessions, "t")


def test_bullish_sweep_confirmed_same_bar(sessions, spec):
    sw, lv = _run_sweeps(sessions, spec, _sweep_bars(sessions, pen_low=89.75, closes=(91, 91, 91)))
    s = sw[sw["level_type"] == "prev_rth_low"]
    assert len(s) == 1 and s["status"].iat[0] == "confirmed" and s["sweep_direction"].iat[0] == "bullish_reversal"
    assert s["bars_to_confirmation"].iat[0] == 0 and s["max_penetration_points"].iat[0] == 0.25 and s["max_penetration_ticks"].iat[0] == 1
    assert s["penetration_ts_utc"].iat[0] == pd.Timestamp("2024-05-15 10:05", tz=NY)
    assert s["confirmation_ts_utc"].iat[0] == pd.Timestamp("2024-05-15 10:06", tz=NY)   # close of the penetration bar
    assert s["window"].iat[0] == "sb_ny_am"
    l = lv[lv["level_type"] == "prev_rth_low"].iloc[0]
    assert l["consumed"] and l["consumption_reason"] == "confirmed_sweep" and l["sweep_id"] == s["sweep_id"].iat[0]


def test_minimum_penetration_threshold(sessions, spec):
    bars = _sweep_bars(sessions, pen_low=89.9, closes=(91, 91, 91))   # only 0.1 below: less than 1 tick
    sw, _ = _run_sweeps(sessions, spec, bars)
    assert sw[sw["level_type"] == "prev_rth_low"].empty
    sw2, _ = _run_sweeps(sessions, spec, bars, SweepConfig(min_penetration_ticks=0))
    assert len(sw2[sw2["level_type"] == "prev_rth_low"]) == 1
    sw3, _ = _run_sweeps(sessions, spec, _sweep_bars(sessions, pen_low=89.5), SweepConfig(min_penetration_ticks=2))
    assert len(sw3[sw3["level_type"] == "prev_rth_low"]) == 1


def test_confirmation_delay_limit(sessions, spec):
    # closes below the level for 3 bars, back above on the 4th: 3-bar limit fails, 4-bar limit succeeds
    bars = _sweep_bars(sessions, pen_low=89.5, closes=(89.75, 89.75, 89.75, 89.75, 91))
    sw, lv = _run_sweeps(sessions, spec, bars)
    s = sw[sw["level_type"] == "prev_rth_low"]
    assert s["status"].iat[0] == "no_reversal"
    assert lv[lv["level_type"] == "prev_rth_low"]["consumption_reason"].iat[0] == "penetration_no_reversal"
    sw4, _ = _run_sweeps(sessions, spec, bars, SweepConfig(max_confirmation_bars=4))
    s4 = sw4[sw4["level_type"] == "prev_rth_low"]
    assert s4["status"].iat[0] == "confirmed" and s4["bars_to_confirmation"].iat[0] == 4


def test_consumed_level_not_reused_unless_allowed(sessions, spec):
    bars = _sweep_bars(sessions, pen_low=89.75, closes=(91, 91, 91))
    # second dip 30 minutes later
    t = pd.Timestamp("2024-05-15 10:35", tz=NY); i = bars.index[bars["ts_ny"] == t][0]
    bars.loc[i, ["open", "high", "low", "close"]] = [92, 92, 89.5, 91]
    sw, _ = _run_sweeps(sessions, spec, bars)
    assert len(sw[sw["level_type"] == "prev_rth_low"]) == 1
    sw2, lv2 = _run_sweeps(sessions, spec, bars, liq_cfg=LiquidityConfig(universe=("prev_rth",), allow_reuse=True))
    assert len(sw2[sw2["level_type"] == "prev_rth_low"]) == 2 and not lv2[lv2["level_type"] == "prev_rth_low"]["consumed"].iat[0]


def test_bearish_sweep_on_buyside(sessions, spec):
    bars = two_sessions(sessions)   # prev RTH high 110
    t = pd.Timestamp("2024-05-15 14:10", tz=NY); i = bars.index[bars["ts_ny"] == t][0]
    bars.loc[i, ["open", "high", "low", "close"]] = [108, 110.5, 107.5, 109]
    sw, _ = _run_sweeps(sessions, spec, bars)
    s = sw[sw["level_type"] == "prev_rth_high"]
    assert len(s) == 1 and s["sweep_direction"].iat[0] == "bearish_reversal" and s["window"].iat[0] == "sb_ny_pm"


def test_level_not_sweepable_before_activation(sessions, spec):
    # a dip through 90 on 2024-05-14 at 15:00 (before the level is even confirmed) must not be a sweep of prev_rth_low scoped to 05-15
    bars = two_sessions(sessions)
    t = pd.Timestamp("2024-05-14 15:00", tz=NY); i = bars.index[bars["ts_ny"] == t][0]
    bars.loc[i, ["open", "high", "low", "close"]] = [92, 92, 89, 91]   # this bar also becomes the new RTH low (89)
    sw, lv = _run_sweeps(sessions, spec, bars)
    assert lv[lv["level_type"] == "prev_rth_low"]["price"].iat[0] == 89
    assert sw.empty


def test_one_minute_swings_never_appear_as_liquidity(sessions):
    bars = two_sessions(sessions)
    lv = build_liquidity_levels(bars, sessions, LiquidityConfig(), WINDOWS, "t")
    assert not lv["level_type"].str.contains("1m").any()
    assert set(lv["source_timeframe"].unique()) <= {"session", "rth", "1m", "15m"}
    assert set(lv.loc[lv["level_type"].str.startswith("swing"), "source_timeframe"]) <= {"15m"}
