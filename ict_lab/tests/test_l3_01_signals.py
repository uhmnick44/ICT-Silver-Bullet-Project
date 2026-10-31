"""Layer 3: canonical sequence, direction matching, confirmation ordering, one trade per window, config constraints."""
import pandas as pd
import pytest

from ict_lab.engine.exec_config import Layer3Config, SignalConfig, StopConfig, load_layer3_config
from ict_lab.engine.signals import build_setup, prepare_tables
from .l3_fixtures import disp_row, feats, fvg_row, mss_row, sweep_row, ts, window_row

BASE = SignalConfig(liquidity_types=("prev_session", "prewindow"), fvg_timeframe="5m")


def test_baseline_config_loads_and_displacement_swing_stop_is_blocked():
    cfg = load_layer3_config("ict_lab/configs/baseline_verification.toml")
    assert cfg.signal.windows == ("sb_ny_am",) and cfg.entry.location == "midpoint" and cfg.target.r_multiple == 2.0
    with pytest.raises(ValueError, match="awaiting|not defined|swing-selection"):
        Layer3Config(series_id="x", stop=StopConfig(type="displacement_swing")).validate()


def test_config_rejects_non_approved_liquidity_and_lookahead_bias():
    with pytest.raises(ValueError):
        Layer3Config(series_id="x", signal=SignalConfig(liquidity_types=("swing_1m",))).validate()
    with pytest.raises(ValueError):
        Layer3Config(series_id="x", signal=SignalConfig(bias_detector="perfect_window")).validate()
    with pytest.raises(ValueError):
        Layer3Config(series_id="x", signal=SignalConfig(max_trades_per_window=2)).validate()


def test_canonical_sequence_minimal():
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row()])
    setup, diag = build_setup(window_row(), prepare_tables(f, BASE), BASE)
    assert setup is not None and setup.direction == "bullish" and setup.fvg_id == "5m:1:bull"
    assert setup.setup_ts_utc == ts("2024-05-15 10:10") and diag["gate_failed"] is None


def test_sellside_sweep_requires_bullish_fvg_and_vice_versa():
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row(direction="bearish", fid="5m:1:bear")])
    setup, diag = build_setup(window_row(), prepare_tables(f, BASE), BASE)
    assert setup is None and diag["gate_failed"] == "fvg"
    f = feats(sweeps=[sweep_row(direction="bearish_reversal", level_type="prev_session_high")], fvgs=[fvg_row(direction="bearish", fid="5m:1:bear", upper=102, lower=100)])
    setup, _ = build_setup(window_row(), prepare_tables(f, BASE), BASE)
    assert setup is not None and setup.direction == "bearish"


def test_fvg_confirmed_before_sweep_is_not_used():
    f = feats(sweeps=[sweep_row(conf="2024-05-15 10:20")], fvgs=[fvg_row(conf="2024-05-15 10:10")])
    setup, diag = build_setup(window_row(), prepare_tables(f, BASE), BASE)
    assert setup is None and diag["gate_failed"] == "fvg"
    f = feats(sweeps=[sweep_row(conf="2024-05-15 10:20")], fvgs=[fvg_row(conf="2024-05-15 10:10"), fvg_row(fid="5m:2:bull", conf="2024-05-15 10:25")])
    setup, _ = build_setup(window_row(), prepare_tables(f, BASE), BASE)
    assert setup.fvg_id == "5m:2:bull" and setup.setup_ts_utc == ts("2024-05-15 10:25")


def test_sweep_confirmed_outside_window_is_ignored():
    f = feats(sweeps=[sweep_row(conf="2024-05-15 09:59")], fvgs=[fvg_row()])
    setup, diag = build_setup(window_row(), prepare_tables(f, BASE), BASE)
    assert setup is None and diag["gate_failed"] == "sweep"


def test_displacement_and_mss_gates_and_setup_ts_is_latest_confirmation():
    cfg = SignalConfig(liquidity_types=("prev_session",), require_displacement=True, require_mss=True, displacement_threshold=1.5)
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row(conf="2024-05-15 10:15")], disps=[disp_row(conf="2024-05-15 10:06", ratio=1.2)], msss=[mss_row(brk="2024-05-15 10:08")])
    setup, diag = build_setup(window_row(), prepare_tables(f, cfg), cfg)
    assert setup is None and diag["gate_failed"] == "displacement"          # ratio below threshold
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row(conf="2024-05-15 10:15")], disps=[disp_row(conf="2024-05-15 10:06", ratio=2.0)], msss=[mss_row(found=False)])
    setup, diag = build_setup(window_row(), prepare_tables(f, cfg), cfg)
    assert setup is None and diag["gate_failed"] == "mss"
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row(conf="2024-05-15 10:15")], disps=[disp_row(conf="2024-05-15 10:12", ratio=2.0)], msss=[mss_row(brk="2024-05-15 10:08")])
    setup, _ = build_setup(window_row(), prepare_tables(f, cfg), cfg)
    assert setup is not None and setup.mss_break_ts_utc == ts("2024-05-15 10:08") and setup.setup_ts_utc == ts("2024-05-15 10:15")
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row(conf="2024-05-15 10:11"), fvg_row(fid="5m:2:bull", conf="2024-05-15 10:20")], disps=[disp_row(conf="2024-05-15 10:12", ratio=2.0)], msss=[mss_row(brk="2024-05-15 10:08")])
    setup, _ = build_setup(window_row(), prepare_tables(f, cfg), cfg)
    assert setup.fvg_id == "5m:2:bull" and setup.setup_ts_utc == ts("2024-05-15 10:20") and setup.displacement_confirmation_ts_utc == ts("2024-05-15 10:12")


def test_bias_gate():
    cfg = SignalConfig(liquidity_types=("prev_session",), bias_detector="prev_day_oc")
    bias = [{"trading_date": pd.Timestamp("2024-05-15"), "window": "sb_ny_am", "bias": "bearish"}]
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row()], bias=bias)
    setup, diag = build_setup(window_row(), prepare_tables(f, cfg), cfg)
    assert setup is None and diag["gate_failed"] == "bias" and "conflict" in diag["reason"]
    cfg2 = SignalConfig(liquidity_types=("prev_session",), bias_detector="prev_day_oc", require_bias=True)
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row()], bias=[{"trading_date": pd.Timestamp("2024-05-15"), "window": "sb_ny_am", "bias": "none"}])
    setup, diag = build_setup(window_row(), prepare_tables(f, cfg2), cfg2)
    assert setup is None and diag["reason"] == "no_bias"


def test_first_qualifying_setup_and_non_approved_liquidity_filtered():
    f = feats(sweeps=[sweep_row(sweep_id=0, level_type="swing_15m_low", conf="2024-05-15 10:03"), sweep_row(sweep_id=1, conf="2024-05-15 10:05")], fvgs=[fvg_row()])
    setup, _ = build_setup(window_row(), prepare_tables(f, BASE), BASE)   # BASE excludes swing_15m
    assert setup.sweep_id == 1
    cfg = SignalConfig(liquidity_types=("prev_session", "swing_15m"), fvg_timeframe="5m")
    setup, _ = build_setup(window_row(), prepare_tables(f, cfg), cfg)
    assert setup.sweep_id == 0 and setup.attempts == 1


def test_ineligible_window_is_first_gate():
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row()])
    setup, diag = build_setup(window_row(eligible=False, reasons="incomplete_window_bars(59/60)"), prepare_tables(f, BASE), BASE)
    assert setup is None and diag["gate_failed"] == "window_eligible" and "59/60" in diag["reason"]


def test_stop_reference_is_latest_displacement_no_later_than_fvg_confirmation():
    cfg = SignalConfig(liquidity_types=("prev_session",), require_displacement=True, displacement_threshold=1.5)
    disps = [disp_row(conf="2024-05-15 10:06", ratio=2.0), disp_row(conf="2024-05-15 10:09", ratio=1.8), disp_row(conf="2024-05-15 10:11", ratio=3.0),
             disp_row(conf="2024-05-15 10:08", ratio=2.5, direction="bearish")]
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row(conf="2024-05-15 10:10")], disps=disps)
    setup, _ = build_setup(window_row(), prepare_tables(f, cfg), cfg)
    assert setup.displacement_confirmation_ts_utc == ts("2024-05-15 10:06")           # gating: first qualifying candle
    assert setup.stop_ref_displacement_confirmation_ts_utc == ts("2024-05-15 10:09")  # stop: latest <= FVG confirmation, direction-matching
    assert setup.stop_ref_displacement_ratio == 1.8 and setup.stop_ref_displacement_timeframe == "1m"
    # a displacement candle confirmed at exactly the FVG confirmation qualifies; one confirmed later never does
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row(conf="2024-05-15 10:10")], disps=[disp_row(conf="2024-05-15 10:06"), disp_row(conf="2024-05-15 10:10", ratio=1.6)])
    setup, _ = build_setup(window_row(), prepare_tables(f, cfg), cfg)
    assert setup.stop_ref_displacement_confirmation_ts_utc == ts("2024-05-15 10:10")
    # without require_displacement the stop reference is still recorded when a candle exists, else None
    cfg2 = SignalConfig(liquidity_types=("prev_session",), displacement_threshold=1.5)
    f = feats(sweeps=[sweep_row()], fvgs=[fvg_row(conf="2024-05-15 10:10")])
    setup, _ = build_setup(window_row(), prepare_tables(f, cfg2), cfg2)
    assert setup is not None and setup.stop_ref_displacement_ts_utc is None
