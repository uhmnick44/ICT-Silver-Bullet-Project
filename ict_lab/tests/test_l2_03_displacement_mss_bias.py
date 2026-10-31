"""Layer 2: displacement thresholds, MSS detection, bias detectors, lookahead isolation, windows."""
import numpy as np
import pandas as pd
import pytest

from ict_lab.features.atr import atr
from ict_lab.features.bias import compute_bias
from ict_lab.features.config import ATRConfig, BiasConfig, DisplacementConfig, LiquidityConfig, MSSConfig, SweepConfig
from ict_lab.features.displacement import detect_displacement
from ict_lab.features.liquidity import build_liquidity_levels
from ict_lab.features.mss import detect_mss
from ict_lab.features.sweeps import detect_sweeps
from ict_lab.features.timeframes import resample
from .l2_fixtures import make_bars, flat, session_bars

NY = "America/New_York"
WINDOWS = ("sb_london", "sb_ny_am", "sb_ny_pm")


def test_atr_wilder_and_gap_handling(sessions):
    rows = flat(20, 100, 1.0)   # range 2 every bar (±1) -> ATR 2
    bars = make_bars(sessions, "2024-05-15 10:00", rows)
    a = atr(resample(bars, "1m"), 14, "wilder")
    assert np.isnan(a[12]) and a[13] == 2.0 and abs(a[-1] - 2.0) < 1e-12
    # a non-consecutive bar uses high-low only, not the previous close
    bars2 = make_bars(sessions, "2024-05-15 10:00", flat(20, 100, 1.0) + [(150, 151, 149, 150)] + flat(5, 150, 1.0), drop_minutes=("2024-05-15 10:19",))
    from ict_lab.features.atr import true_range
    tr = true_range(resample(bars2, "1m"))
    assert tr[19] == 2.0   # the 150 bar after the gap: high-low only (no 50-point jump counted)


def test_displacement_thresholds_and_direction(sessions):
    rows = flat(20, 100, 1.0) + [(100, 105.2, 100, 105)] + [(105, 105, 103.4, 103.5)]   # ATR baseline 2 -> ratio 2.6
    bars = make_bars(sessions, "2024-05-15 10:00", rows)
    d = detect_displacement(resample(bars, "1m"), "1m", DisplacementConfig(record_min_ratio=0.0, percentile_lookback=5), ATRConfig(), "t", keep_all=True)
    big = d.iloc[20]
    assert big["direction"] == "bullish" and abs(big["range_atr_ratio"] - 2.6) < 1e-9 and big["threshold_passed"] == 2.0
    assert big["ge_1_0_atr"] and big["ge_2_0_atr"] and not big["ge_3_0_atr"]
    assert big["confirmation_ts_utc"] == pd.Timestamp("2024-05-15 10:21", tz=NY)
    assert big["passes_percentile"]
    assert d.iloc[21]["direction"] == "bearish"
    # prior-candle ATR reference: the big candle's own range does not inflate its baseline
    assert big["atr"] == 2.0


def _sweep_then_break(sessions, break_close=True):
    # previous session with RTH low 90; current session: swing high at 09:40 (price 104), sweep of 90 at 10:05, break at 10:10
    a = session_bars(sessions, "2024-05-14", px=100, rng=1)
    a.loc[a["ts_ny"] == pd.Timestamp("2024-05-14 14:30", tz=NY), "low"] = 90
    b = session_bars(sessions, "2024-05-15", px=100, rng=1)
    def setbar(ts, o, h, l, c):
        i = b.index[b["ts_ny"] == pd.Timestamp(ts, tz=NY)][0]; b.loc[i, ["open", "high", "low", "close"]] = [o, h, l, c]
    setbar("2024-05-15 09:40", 100, 104, 99.5, 101)           # swing high 104 (confirmed at 09:43 with right=2)
    setbar("2024-05-15 10:05", 92, 92, 89.75, 91)              # sweep of 90, confirmed on close 10:06
    if break_close:
        setbar("2024-05-15 10:10", 101, 105, 100.5, 104.5)     # close through 104
    else:
        setbar("2024-05-15 10:10", 101, 105, 100.5, 103.5)     # wick through only
    return pd.concat([a, b], ignore_index=True)


def test_mss_close_and_wick(sessions, spec):
    for close_break in (True, False):
        bars = _sweep_then_break(sessions, close_break)
        c = resample(bars, "1m")
        liq = LiquidityConfig(universe=("prev_rth",))
        lv = build_liquidity_levels(bars, sessions, liq, WINDOWS, "t")
        sw, _ = detect_sweeps(c, lv, SweepConfig(), liq, spec.tick_size, sessions, "t")
        # the 09:40 spike also sweeps the previous RTH high; keep only the MSS that follows the sellside sweep
        m_close = detect_mss(c, sw, MSSConfig(confirmation="close"), "t"); m_close = m_close[m_close["direction"] == "bullish"].reset_index(drop=True)
        m_wick = detect_mss(c, sw, MSSConfig(confirmation="wick"), "t"); m_wick = m_wick[m_wick["direction"] == "bullish"].reset_index(drop=True)
        assert len(m_close) == 1 and m_close["swing_price"].iat[0] == 104 and m_close["direction"].iat[0] == "bullish"
        assert m_close["swing_confirmation_ts_utc"].iat[0] == pd.Timestamp("2024-05-15 09:43", tz=NY)
        assert m_wick["found"].iat[0] and m_wick["break_ts_utc"].iat[0] == pd.Timestamp("2024-05-15 10:11", tz=NY)
        assert bool(m_close["found"].iat[0]) == close_break
        if close_break:
            assert m_close["break_ts_utc"].iat[0] == pd.Timestamp("2024-05-15 10:11", tz=NY)
            assert m_close["bars_to_break"].iat[0] == 4   # candles 10:06..10:10


def test_mss_search_horizon(sessions, spec):
    bars = _sweep_then_break(sessions, True)
    c = resample(bars, "1m")
    liq = LiquidityConfig(universe=("prev_rth",))
    lv = build_liquidity_levels(bars, sessions, liq, WINDOWS, "t")
    sw, _ = detect_sweeps(c, lv, SweepConfig(), liq, spec.tick_size, sessions, "t")
    m = detect_mss(c, sw, MSSConfig(max_bars_after_sweep=3), "t")
    assert not m[m["direction"] == "bullish"]["found"].iat[0]


def _bias_sessions(sessions, n=25, step=1.0):
    frames = []
    d0 = pd.Timestamp("2024-04-01")
    k = 0
    while len(frames) < n:
        d = d0 + pd.Timedelta(days=k); k += 1
        if d.weekday() >= 5:
            continue
        px = 100 + step * len(frames)
        s = session_bars(sessions, d.strftime("%Y-%m-%d"), px=px, rng=0.5)
        s.loc[s.index[-1], "close"] = px + 0.5 if step > 0 else px - 0.5   # session close vs open
        frames.append(s)
    return pd.concat(frames, ignore_index=True)


def test_prev_day_bias_and_ma_slope(sessions):
    bars = _bias_sessions(sessions, n=25, step=1.0)
    b = compute_bias(bars, sessions, WINDOWS, BiasConfig(detector="prev_day_oc"), "t")
    first_day = b["trading_date"].min()
    assert (b.loc[b["trading_date"] == first_day, "bias"] == "none").all()          # no previous session yet
    assert (b.loc[b["trading_date"] > first_day, "bias"] == "bullish").all()
    m = compute_bias(bars, sessions, WINDOWS, BiasConfig(detector="daily_ma20_slope"), "t")
    dates = sorted(m["trading_date"].unique())
    assert (m[m["trading_date"].isin(dates[:21])]["bias"] == "none").all()            # warm-up: 21 completed sessions needed
    assert (m[m["trading_date"].isin(dates[21:])]["bias"] == "bullish").all()
    assert not m["lookahead"].any()


def test_structure_bias_uses_only_confirmed_swings(sessions):
    # rising 15m structure: swing highs 110 < 114 < 118 and swing lows 104 < 108 < 113 (each 15m candle = 15 flat 1m bars)
    ranges = [(100, 101), (104, 106), (109, 110), (106, 107), (104, 105), (108, 110), (113, 114), (111, 112), (108, 109),
              (112, 114), (117, 118), (115, 116), (113, 114)]
    rows = []
    for lo, hi in ranges:
        rows += [(lo, hi, lo, hi)] * 15
    rows += flat(15 * 30, 115, 0.5)
    bars = make_bars(sessions, "2024-05-15 01:00", rows)
    b = compute_bias(bars, sessions, ("sb_ny_am",), BiasConfig(detector="swing_15m_structure"), "t")
    assert b["bias"].iat[0] == "bullish"
    # at 03:00 only one swing high (110) and one swing low (104) are confirmed -> no structure call yet
    b2 = compute_bias(bars, sessions, ("sb_london",), BiasConfig(detector="swing_15m_structure"), "t")
    assert b2["bias"].iat[0] == "none"


def test_lookahead_bias_isolated(sessions):
    bars = _bias_sessions(sessions, n=3, step=1.0)
    with pytest.raises(PermissionError):
        compute_bias(bars, sessions, WINDOWS, BiasConfig(detector="perfect_window"), "t")
    p = compute_bias(bars, sessions, WINDOWS, BiasConfig(detector="perfect_window", allow_lookahead_diagnostic=True), "t")
    assert p["lookahead"].all() and set(p["bias"]) <= {"bullish", "bearish", "none"}
    # a lookahead detector must never be accepted by a validated research config
    from ict_lab.features.config import Layer2Config
    with pytest.raises(ValueError):
        Layer2Config(series_id="x", bias=BiasConfig(detector="perfect_session")).validate()


def test_atr_resets_after_within_session_hole_but_not_across_session_break(sessions):
    from ict_lab.features.atr import atr, data_discontinuity
    # 40 flat bars with one missing minute at 10:20 -> hole; ATR NaN for 14 candles after the hole
    rows = flat(40, 100, 1.0)
    bars = make_bars(sessions, "2024-05-15 10:00", rows, drop_minutes=("2024-05-15 10:20",))
    c = resample(bars, "1m")
    disc = data_discontinuity(c)
    assert disc.sum() == 1 and c.loc[disc, "ts_ny"].iloc[0] == pd.Timestamp("2024-05-15 10:21", tz=NY)
    a = atr(c, 14, "wilder", reset_on_data_gap=True)
    i = int(np.where(disc)[0][0])
    assert not np.isnan(a[i - 1]) and np.isnan(a[i:i + 13]).all() and a[i + 13] == 2.0
    a2 = atr(c, 14, "wilder", reset_on_data_gap=False)
    assert not np.isnan(a2[i])
    # session break: last bar 16:59 then 18:00 next session -> not a data discontinuity, ATR carries
    rows = flat(20, 100, 1.0)
    b = pd.concat([make_bars(sessions, "2024-05-15 16:40", rows), make_bars(sessions, "2024-05-15 18:00", rows)], ignore_index=True)
    b["consecutive_prev"] = (b["ts_utc"].diff().dt.total_seconds().div(60).to_numpy() == 1.0)
    c2 = resample(b, "1m")
    assert data_discontinuity(c2).sum() == 0
    a3 = atr(c2, 14, "wilder")
    assert not np.isnan(a3[20]) and not np.isnan(a3[-1])


def test_incomplete_htf_candle_is_a_discontinuity_and_forms_no_fvg(sessions, spec):
    from ict_lab.features.atr import data_discontinuity
    from ict_lab.features.fvg import detect_fvg
    from ict_lab.features.config import FVGConfig, ATRConfig
    rows = flat(5, 100, 0.5) + [(100.5, 110, 100.4, 109.5)] * 5 + [(109.5, 112, 108, 111)] * 5 + flat(5, 110, 0.5)
    bars = make_bars(sessions, "2024-05-15 10:00", rows, drop_minutes=("2024-05-15 10:07",))   # hole inside candle 2
    c5 = resample(bars, "5m")
    assert not c5["complete"].iloc[1] and data_discontinuity(c5)[1]
    assert detect_fvg(c5, bars, "5m", FVGConfig(), ATRConfig(), "t", spec.tick_size).empty
    assert len(detect_fvg(c5, bars, "5m", FVGConfig(require_complete_candles=False), ATRConfig(), "t", spec.tick_size)) == 1
