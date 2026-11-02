"""Layer 4: named configs, liquidity universes, schema rejections, deterministic hashes."""
import pytest

from ict_lab.engine.exec_config import (HARD_TRADE_CAP, LIQUIDITY_UNIVERSES, NAMED_CONFIGS, Layer3Config, SignalConfig, StopConfig, TargetConfig,
                                        load_layer3_config, load_named_config)


def test_three_named_configs_load_and_hash_deterministically():
    hashes = {}
    for n in NAMED_CONFIGS:
        c = load_named_config(n); c2 = load_named_config(n)
        assert c.meta.name == n and c.config_hash == c2.config_hash and "user-authorized modification" in c.meta.stop_substitution_note.lower()
        assert c.stop.type == "liquidity_sweep_extreme" and c.stop.buffer_ticks == 1 and c.signal.require_displacement and c.signal.displacement_threshold == 1.5
        assert c.exit.policy == "rth_end" and c.roll.policy == "flag_and_exclude" and "swing_1m" not in c.signal.liquidity_types
        assert c.signal.windows == ("sb_london", "sb_ny_am", "sb_ny_pm") and c.entry.location == "midpoint"
        hashes[n] = c.config_hash
    assert len(set(hashes.values())) == 3
    a, b, c = (load_named_config(n) for n in NAMED_CONFIGS)
    assert a.signal.fvg_timeframe == "5m" and b.signal.fvg_timeframe == "1m" and c.signal.fvg_timeframe == "1m"
    assert a.signal.liquidity_universe == "bsl_ssl_15m" and a.signal.liquidity_types == ("swing_15m",) and a.target.opposing_liquidity_types == ("swing_15m",)
    assert a.signal.bias_detector == "swing_15m_structure" and a.target.type == "opposing_liquidity" and a.target.fallback_r_multiple == 2.0
    assert c.signal.bias_detector == "none" and c.signal.liquidity_universe == "session_refs_plus_swings" and c.target.type == "fixed_r"
    assert c.signal.max_trades_per_window == "unlimited" and c.signal.trade_cap == HARD_TRADE_CAP == 10 and a.signal.trade_cap == 1


def test_liquidity_universes_contain_no_1m_swings():
    for name, types in LIQUIDITY_UNIVERSES.items():
        if types is not None:
            assert not any("1m" in t for t in types) and set(types) <= {"prev_session", "prev_rth", "prewindow", "swing_15m"}
    assert LIQUIDITY_UNIVERSES["swings_only"] == LIQUIDITY_UNIVERSES["bsl_ssl_15m"] == ("swing_15m",)
    assert LIQUIDITY_UNIVERSES["session_refs"] == ("prev_session", "prev_rth", "prewindow")


def test_universe_controls_sweeps_and_targets(tmp_path):
    cfg = load_layer3_config("ict_lab/configs/layer3_execution.toml", signal={"liquidity_universe": "session_refs", "liquidity_types": ["swing_15m"]})
    assert cfg.signal.liquidity_types == ("prev_session", "prev_rth", "prewindow") == cfg.target.opposing_liquidity_types
    with pytest.raises(ValueError):
        Layer3Config(series_id="x", signal=SignalConfig(liquidity_universe="bsl_ssl_15m", liquidity_types=("prev_session",)), target=TargetConfig(opposing_liquidity_types=("swing_15m",))).validate()
    with pytest.raises(ValueError):
        Layer3Config(series_id="x", signal=SignalConfig(liquidity_universe="swing_1m")).validate()


@pytest.mark.parametrize("bad", [
    dict(signal=SignalConfig(liquidity_types=("swing_1m",))),
    dict(signal=SignalConfig(bias_detector="perfect_window")),
    dict(signal=SignalConfig(bias_detector="perfect_session")),
    dict(stop=StopConfig(type="displacement_swing")),
    dict(signal=SignalConfig(max_trades_per_window=0)),
    dict(signal=SignalConfig(max_trades_per_window=11)),
    dict(signal=SignalConfig(max_trades_per_window="all")),
    dict(signal=SignalConfig(windows=("sb_ny_am", "sb_ny_am"))),
    dict(signal=SignalConfig(windows=("rth",))),
    dict(signal=SignalConfig(fvg_timeframe="1h")),
    dict(signal=SignalConfig(pending_order_policy="replace")),
])
def test_schema_rejects_invalid_configurations(bad):
    with pytest.raises(ValueError):
        Layer3Config(series_id="x", **bad).validate()


def test_hash_changes_with_any_field():
    base = load_named_config("as_traded")
    alt = load_layer3_config("ict_lab/configs/strategies/as_traded.toml", costs={"stop_slippage_ticks": 2})
    assert alt.config_hash != base.config_hash
    alt2 = load_layer3_config("ict_lab/configs/strategies/as_traded.toml", signal={"max_trades_per_window": 1})
    assert alt2.config_hash != base.config_hash and alt2.signal.trade_cap == 1
