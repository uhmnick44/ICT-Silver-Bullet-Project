"""Layer 2: config schema constraints, FVG detection, confirmation timing, mitigation and full fill."""
import pandas as pd
import pytest

from ict_lab.features.config import (FORBIDDEN_LIQUIDITY, FVGConfig, ATRConfig, Layer2Config, LiquidityConfig, BiasConfig,
                                     load_layer2_config)
from ict_lab.features.fvg import detect_fvg
from ict_lab.features.timeframes import resample
from .l2_fixtures import make_bars, flat


def test_default_config_loads_and_validates():
    cfg = load_layer2_config()
    assert cfg.liquidity.swing_timeframe == "15m" and "swing_15m" in cfg.liquidity.universe
    assert cfg.config_hash


@pytest.mark.parametrize("bad", ["swing_1m", "swing_5m", "mss_swing", "anything_else"])
def test_liquidity_universe_rejects_non_approved_types(bad):
    with pytest.raises(ValueError):
        Layer2Config(series_id="x", liquidity=LiquidityConfig(universe=("prev_session", bad))).validate()


def test_liquidity_swing_timeframe_must_be_15m():
    for tf in ("1m", "5m", "1h"):
        with pytest.raises(ValueError):
            Layer2Config(series_id="x", liquidity=LiquidityConfig(swing_timeframe=tf)).validate()


def test_lookahead_bias_requires_explicit_flag():
    with pytest.raises(ValueError):
        Layer2Config(series_id="x", bias=BiasConfig(detector="perfect_window")).validate()
    Layer2Config(series_id="x", bias=BiasConfig(detector="perfect_window", allow_lookahead_diagnostic=True)).validate()


def _fvg_bars(sessions, gap=True, bearish=False):
    # c1, c2, c3 at 10:00, 10:01, 10:02; then bars that come back to mitigate / fill
    if not bearish:
        ohlc = [(100, 101, 99, 100.5), (101, 106, 100.5, 105.5), (105.5, 107, 103 if gap else 100.5, 106),
                (106, 106.5, 105.5, 106), (106, 106.2, 102.9, 103), (103, 106, 101, 101), (101, 103, 99.5, 100)]
    else:
        ohlc = [(100, 101, 99, 99.5), (99, 99.5, 94, 94.5), (94.5, 97 if gap else 99.5, 93, 94),
                (94, 94.5, 93.5, 94), (94, 97.1, 93.9, 97), (97, 99, 94, 99), (99, 100.5, 97, 100.5)]
    return make_bars(sessions, "2024-05-15 10:00", ohlc)


def test_bullish_fvg_strict_gap_boundaries_and_timing(sessions, spec):
    bars = _fvg_bars(sessions)
    f = detect_fvg(resample(bars, "1m"), bars, "1m", FVGConfig(), ATRConfig(), "test", spec.tick_size)
    assert len(f) == 1 and f["direction"].iat[0] == "bullish"
    r = f.iloc[0]
    assert r["lower"] == 101 and r["upper"] == 103 and r["gap_points"] == 2 and r["midpoint"] == 102 and r["gap_ticks"] == 8
    assert r["formation_ts_utc"] == pd.Timestamp("2024-05-15 10:00", tz="America/New_York")
    assert r["confirmation_ts_utc"] == pd.Timestamp("2024-05-15 10:03", tz="America/New_York")   # after candle 3 closes
    assert r["first_mitigation_ts_utc"] == pd.Timestamp("2024-05-15 10:04", tz="America/New_York")  # low 102.9 < 103
    assert r["full_fill_ts_utc"] == pd.Timestamp("2024-05-15 10:05", tz="America/New_York")        # low 101 <= 101
    assert pd.isna(r["atr"]) and pd.isna(r["gap_atr"])  # ATR warm-up: unavailable, never fabricated


def test_bearish_fvg(sessions, spec):
    bars = _fvg_bars(sessions, bearish=True)
    f = detect_fvg(resample(bars, "1m"), bars, "1m", FVGConfig(), ATRConfig(), "test", spec.tick_size)
    assert len(f) == 1 and f["direction"].iat[0] == "bearish"
    r = f.iloc[0]
    assert r["upper"] == 99 and r["lower"] == 97
    assert r["first_mitigation_ts_utc"] == pd.Timestamp("2024-05-15 10:04", tz="America/New_York")  # high 97.1 > 97
    assert r["full_fill_ts_utc"] == pd.Timestamp("2024-05-15 10:05", tz="America/New_York")        # high 99 >= 99


def test_touching_candles_are_not_an_fvg(sessions, spec):
    for bearish in (False, True):
        bars = _fvg_bars(sessions, gap=False, bearish=bearish)
        f = detect_fvg(resample(bars, "1m"), bars, "1m", FVGConfig(), ATRConfig(), "test", spec.tick_size)
        assert len(f) == 0


def test_mitigation_cannot_precede_confirmation(sessions, spec):
    # candle 3 itself trades back into the gap; mitigation must still be at/after confirmation (next bar)
    ohlc = [(100, 101, 99, 100.5), (101, 106, 100.5, 105.5), (105.5, 107, 103, 106), (106, 106.5, 102.5, 103)]
    bars = make_bars(sessions, "2024-05-15 10:00", ohlc)
    f = detect_fvg(resample(bars, "1m"), bars, "1m", FVGConfig(), ATRConfig(), "test", spec.tick_size)
    assert f["first_mitigation_ts_utc"].iat[0] >= f["confirmation_ts_utc"].iat[0]


def test_missing_bar_breaks_three_candle_pattern(sessions, spec):
    ohlc = [(100, 101, 99, 100.5), (101, 106, 100.5, 105.5), (105.5, 107, 103, 106), (106, 106.5, 105.5, 106)]
    bars = make_bars(sessions, "2024-05-15 10:00", ohlc, drop_minutes=("2024-05-15 10:01",))
    f = detect_fvg(resample(bars, "1m"), bars, "1m", FVGConfig(), ATRConfig(), "test", spec.tick_size)
    assert len(f) == 0


def test_min_gap_filters(sessions, spec):
    bars = _fvg_bars(sessions)
    c = resample(bars, "1m")
    assert len(detect_fvg(c, bars, "1m", FVGConfig(min_gap_points=2.0), ATRConfig(), "t", spec.tick_size)) == 1
    assert len(detect_fvg(c, bars, "1m", FVGConfig(min_gap_points=2.25), ATRConfig(), "t", spec.tick_size)) == 0
    assert len(detect_fvg(c, bars, "1m", FVGConfig(min_gap_atr=0.5), ATRConfig(), "t", spec.tick_size)) == 0  # ATR NaN -> excluded


def test_htf_fvg_confirmation_waits_for_bucket_end(sessions, spec):
    # 5m: three candles 10:00, 10:05, 10:10 with a bullish gap; confirmation at 10:15
    rows = flat(5, 100, 0.5) + [(100.5, 110, 100.4, 109.5)] * 5 + [(109.5, 112, 108, 111)] * 5 + flat(5, 110, 0.5)
    bars = make_bars(sessions, "2024-05-15 10:00", rows)
    f = detect_fvg(resample(bars, "5m"), bars, "5m", FVGConfig(), ATRConfig(), "t", spec.tick_size)
    assert len(f) == 1 and f["confirmation_ts_utc"].iat[0] == pd.Timestamp("2024-05-15 10:15", tz="America/New_York")
    assert f["lower"].iat[0] == 100.5 and f["upper"].iat[0] == 108
