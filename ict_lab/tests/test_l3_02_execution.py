"""Layer 3: fills, exits, costs, excursions, rounding, missing data, rolls (synthetic bars)."""
import numpy as np
import pandas as pd
import pytest

from ict_lab.engine.exec_config import CostConfig, EntryConfig, ExitConfig, Layer3Config, RollConfig, SizingConfig, StopConfig, TargetConfig
from ict_lab.engine.execution import BarArrays, entry_limit_price, round_to_tick, simulate, stop_price, target_price
from .l3_fixtures import arrays, bars_from, make_setup, ts

NY = "America/New_York"
NOROLL = np.zeros(0, dtype="datetime64[ns]")


def cfg(**kw) -> Layer3Config:
    base = dict(series_id="x", stop=StopConfig(type="fvg_distal", buffer_ticks=1), target=TargetConfig(type="fixed_r", r_multiple=2.0),
                exit=ExitConfig(policy="rth_end"), costs=CostConfig(), sizing=SizingConfig(contracts=1))
    base.update(kw)
    return Layer3Config(**base).validate()


def run(sessions, spec, bars_ohlc, c=None, setup=None, start="2024-05-15 10:00", levels=None, **bk):
    c = c or cfg()
    s = setup or make_setup()
    b = arrays(sessions, start, bars_ohlc, **bk)
    return simulate(s, b, c, spec, levels, ts("2024-05-15 16:00"), NOROLL)


# bullish setup: FVG 100-102, midpoint entry 101.0, distal stop 100 - 0.25 = 99.75, risk 1.25, 2R target 103.5
FLAT = (102.5, 103.0, 102.0, 102.5)      # filler bars: inside the stop/target band, above the limit
FILL = (103.0, 103.0, 100.75, 102.0)     # trades one tick through the limit; high below the target


def test_entry_activation_timing(sessions, spec):
    # a bar at 10:05 trades below the limit, but the order activates at 10:10 (setup ts) -> fill at 10:12
    ohlc = [FLAT] * 5 + [(103, 103, 100.5, 102)] + [FLAT] * 6 + [(103, 103, 100.5, 102)] + [FLAT] * 60
    tr, nd = run(sessions, spec, ohlc)
    assert tr is not None and tr["entry_fill_ts_utc"] == ts("2024-05-15 10:12") and tr["order_active_ts_utc"] == ts("2024-05-15 10:10")
    assert tr["entry_price"] == 101.0 and not tr["marketable_at_activation"]


def test_strict_trade_through_and_exact_touch_nonfill(sessions, spec):
    touch = [FLAT] * 12 + [(103, 103, 101.0, 102)] + [FLAT] * 60      # low == limit: no fill
    tr, nd = run(sessions, spec, touch)
    assert tr is None and nd["reason"] == "order_expired_unfilled_at_window_end"
    through = [FLAT] * 12 + [FILL] + [FLAT] * 60   # one tick through
    tr, _ = run(sessions, spec, through)
    assert tr is not None and tr["entry_price"] == 101.0


def test_order_expires_at_window_end(sessions, spec):
    # price only trades through the limit at 11:00 (first bar outside the window)
    ohlc = [FLAT] * 60 + [(103, 103, 100.5, 102)] + [FLAT] * 5
    tr, nd = run(sessions, spec, ohlc)
    assert tr is None and nd["gate_failed"] == "entry_fill" and nd["reason"] == "order_expired_unfilled_at_window_end"


def test_stop_execution_with_adverse_slippage(sessions, spec):
    ohlc = [FLAT] * 12 + [FILL] + [(102, 102.2, 101.5, 102)] + [(102, 102.1, 99.75, 100)] + [FLAT] * 60
    tr, _ = run(sessions, spec, ohlc)
    assert tr["exit_reason"] == "stop" and tr["exit_ts_utc"] == ts("2024-05-15 10:14")
    assert tr["exit_price_theoretical"] == 99.75 and tr["exit_price"] == 99.5          # 1 tick adverse
    assert tr["gross_points"] == -1.25 and tr["slippage_ticks"] == 1 and tr["slippage_cost_usd"] == 0.5
    assert abs(tr["gross_pnl_usd"] - (-2.5)) < 1e-9 and abs(tr["net_pnl_usd"] - (-2.5 - 0.5 - 1.88)) < 1e-9
    assert abs(tr["gross_r"] - (-1.0)) < 1e-9 and abs(tr["net_r"] - ((-2.5 - 0.5 - 1.88) / 2.5)) < 1e-9
    assert not tr["same_bar_ambiguous"]


def test_stop_gapped_through_fills_at_open(sessions, spec):
    ohlc = [FLAT] * 12 + [FILL] + [(99.0, 99.5, 98, 98.5)] + [FLAT] * 60
    tr, _ = run(sessions, spec, ohlc)
    assert tr["exit_reason"] == "stop" and tr["exit_price_theoretical"] == 99.0 and tr["exit_price"] == 98.75


def test_target_execution_strict_and_touch(sessions, spec):
    touch = [FLAT] * 12 + [FILL] + [(102, 103.5, 101.5, 102.5)] + [FLAT] * 400    # high == target: no fill
    tr, _ = run(sessions, spec, touch)
    assert tr["exit_reason"] == "time_exit_rth"
    tr2, _ = run(sessions, spec, touch, c=cfg(target=TargetConfig(type="fixed_r", r_multiple=2.0, fill_rule="touch")))
    assert tr2["exit_reason"] == "target" and tr2["exit_price"] == 103.5
    through = [FLAT] * 12 + [FILL] + [(102, 103.75, 101.5, 102.5)] + [FLAT] * 60
    tr3, _ = run(sessions, spec, through)
    assert tr3["exit_reason"] == "target" and tr3["exit_ts_utc"] == ts("2024-05-15 10:13") and tr3["exit_price"] == 103.5
    assert tr3["gross_points"] == 2.5 and abs(tr3["gross_r"] - 2.0) < 1e-9 and tr3["slippage_ticks"] == 0
    assert abs(tr3["net_pnl_usd"] - (5.0 - 1.88)) < 1e-9


def test_same_bar_stop_first_and_ambiguity_flag(sessions, spec):
    ohlc = [FLAT] * 12 + [FILL] + [(102, 104.0, 99.5, 102)] + [FLAT] * 60     # both stop and target in one bar
    tr, _ = run(sessions, spec, ohlc)
    assert tr["exit_reason"] == "stop" and tr["same_bar_ambiguous"]
    # entry bar itself reaching the stop also resolves stop-first
    ohlc = [FLAT] * 12 + [(103, 103, 99.0, 102)] + [FLAT] * 60
    tr, _ = run(sessions, spec, ohlc)
    assert tr["exit_reason"] == "stop" and tr["bars_held"] == 0 and tr["exit_ts_utc"] == tr["entry_fill_ts_utc"]


def test_time_exits_window_end_and_rth_end(sessions, spec):
    # fill at 10:12 then flat forever: window_end -> exit at the 11:00 bar open; rth_end -> 16:00 bar open
    ohlc = [FLAT] * 12 + [FILL] + [FLAT] * 400
    tr, _ = run(sessions, spec, ohlc, c=cfg(exit=ExitConfig(policy="window_end")))
    assert tr["exit_reason"] == "time_exit_window" and tr["exit_ts_utc"] == ts("2024-05-15 11:00")
    assert tr["exit_price_theoretical"] == 102.5 and tr["exit_price"] == 102.25      # next bar open, 1 tick adverse
    tr2, _ = run(sessions, spec, ohlc)
    assert tr2["exit_reason"] == "time_exit_rth" and tr2["exit_ts_utc"] == ts("2024-05-15 16:00")


def test_time_only_target(sessions, spec):
    ohlc = [FLAT] * 12 + [FILL] + [(102.5, 110, 102, 109)] * 50
    tr, _ = run(sessions, spec, ohlc, c=cfg(target=TargetConfig(type="time_only"), exit=ExitConfig(policy="window_end")))
    assert tr["target_price"] is None and tr["exit_reason"] == "time_exit_window" and np.isnan(tr["planned_reward_r"])


def test_tick_grid_rounding(spec):
    assert round_to_tick(101.125, 0.25, "down") == 101.0 and round_to_tick(101.125, 0.25, "up") == 101.25
    s = make_setup(upper=102.25, lower=100.0)   # midpoint 101.125
    assert entry_limit_price(s, cfg(), spec) == 101.0                                   # bullish: away from proximal (down)
    sb = make_setup(direction="bearish", upper=102.25, lower=100.0)
    assert entry_limit_price(sb, cfg(), spec) == 101.25
    assert entry_limit_price(s, cfg(entry=EntryConfig(location="proximal")), spec) == 102.25
    assert entry_limit_price(s, cfg(entry=EntryConfig(location="distal")), spec) == 100.0
    st, why = stop_price(s, 101.0, cfg(stop=StopConfig(type="fvg_distal", buffer_ticks=3)), spec)
    assert st == 99.25 and why == "ok"
    st, why = stop_price(sb, 101.25, cfg(stop=StopConfig(type="fixed_points", fixed_points=4.0)), spec)
    assert st == 105.25
    for v in (st, 99.25, 101.0, 101.25):
        assert spec.is_tick_multiple(v)


def test_invalid_stop_rejected_not_substituted(sessions, spec):
    s = make_setup(upper=102.0, lower=100.0)
    c = cfg(entry=EntryConfig(location="distal"), stop=StopConfig(type="fvg_distal", buffer_ticks=0))   # entry 100, stop 100 -> distance 0
    tr, nd = run(sessions, spec, [FLAT] * 70, c=c, setup=s)
    assert tr is None and nd["gate_failed"] == "stop" and "stop_invalid" in nd["reason"]


def test_commission_and_slippage_scale_with_quantity(sessions, spec):
    ohlc = [FLAT] * 12 + [FILL] + [(102, 102.1, 99.75, 100)] + [FLAT] * 60
    c = cfg(sizing=SizingConfig(contracts=3), costs=CostConfig(stop_slippage_ticks=2))
    tr, _ = run(sessions, spec, ohlc, c=c)
    assert abs(tr["commission_usd"] - 0.94 * 2 * 3) < 1e-9 and tr["slippage_ticks"] == 2 and abs(tr["slippage_cost_usd"] - 2 * 0.5 * 3) < 1e-9
    assert tr["exit_price"] == 99.25 and abs(tr["gross_pnl_usd"] - (-1.25 * 2 * 3)) < 1e-9
    assert abs(tr["net_pnl_usd"] - (-7.5 - 3.0 - 5.64)) < 1e-9 and abs(tr["net_r"] - ((-7.5 - 3.0 - 5.64) / (1.25 * 2 * 3))) < 1e-9
    assert tr["planned_risk_usd"] == 1.25 * 2 * 3


def test_mfe_mae(sessions, spec):
    ohlc = [FLAT] * 12 + [FILL] + [(102, 102.0, 100.25, 101)] + [(101, 103.25, 100.5, 102.5)] + [(102.5, 103.75, 102.0, 103)] + [FLAT] * 60
    tr, _ = run(sessions, spec, ohlc)
    assert tr["exit_reason"] == "target"
    assert tr["mfe_points"] == 103.75 - 101.0 and tr["mae_points"] == 101.0 - 100.25
    assert abs(tr["mfe_r"] - 2.75 / 1.25) < 1e-9 and abs(tr["mae_r"] - 0.75 / 1.25) < 1e-9


def test_missing_bars_cannot_fill_and_are_flagged(sessions, spec):
    ohlc = [FLAT] * 12 + [FILL] + [(102, 102.2, 101.5, 102)] * 3 + [(102.5, 103.75, 102.4, 103)] + [FLAT] * 60
    # drop the fill bar: no fill until a later bar trades through; drop a bar during the trade -> gap flag
    tr, _ = run(sessions, spec, ohlc, drop_minutes=("2024-05-15 10:14",))
    assert tr["gap_during_trade"] and tr["exit_reason"] == "target"
    tr2, nd = run(sessions, spec, ohlc, drop_minutes=("2024-05-15 10:12",))
    assert tr2 is None and nd["reason"] == "order_expired_unfilled_at_window_end"


def test_marketable_at_activation_rules(sessions, spec):
    ohlc = [FLAT] * 10 + [(100.5, 100.6, 100.4, 100.5)] + [(102.5, 103.75, 102.0, 103)] + [FLAT] * 60   # 10:10 opens below the limit
    tr, _ = run(sessions, spec, ohlc)
    assert tr["marketable_at_activation"] and tr["entry_price"] == 101.0 and tr["entry_fill_ts_utc"] == ts("2024-05-15 10:10")
    tr2, nd = run(sessions, spec, ohlc, c=cfg(entry=EntryConfig(marketable_at_activation="cancel")))
    assert tr2 is None and nd["reason"] == "marketable_at_activation_cancelled"


def test_contract_roll_spanning_trade_is_flagged_and_excluded(sessions, spec):
    a = bars_from(sessions, "2024-05-15 10:00", [FLAT] * 12 + [FILL] + [FLAT] * 407, adjustment=100.0, symbol="MNQM4")
    b = bars_from(sessions, "2024-05-15 18:00", [FLAT] * 30, adjustment=50.0, symbol="MNQU4")
    bars = BarArrays.from_bars(pd.concat([a, b], ignore_index=True))
    roll_ts = np.array([np.datetime64(ts("2024-05-15 18:00").tz_localize(None).to_datetime64(), "ns")])
    s = make_setup()
    c = cfg(exit=ExitConfig(policy="hold"), target=TargetConfig(type="fixed_r", r_multiple=50.0))
    tr, _ = simulate(s, bars, c, spec, None, ts("2024-05-15 16:00"), roll_ts)
    assert tr["spans_roll"] and tr["excluded_by_roll_policy"] and tr["entry_symbol"] == "MNQM4" and tr["exit_symbol"] == "MNQU4"
    assert tr["entry_price_unadjusted"] == 101.0 - 100.0 and tr["exit_adjustment"] == 50.0
    c2 = cfg(exit=ExitConfig(policy="hold"), target=TargetConfig(type="fixed_r", r_multiple=50.0), roll=RollConfig(policy="flag_only"))
    tr2, _ = simulate(s, bars, c2, spec, None, ts("2024-05-15 16:00"), roll_ts)
    assert tr2["spans_roll"] and not tr2["excluded_by_roll_policy"]
    # rth_end exit never spans the 18:00 roll
    tr3, _ = simulate(s, bars, cfg(), spec, None, ts("2024-05-15 16:00"), roll_ts)
    assert not tr3["spans_roll"] and tr3["exit_reason"] == "time_exit_rth"


def test_opposing_liquidity_target_uses_only_known_active_levels(sessions, spec):
    s = make_setup()
    mk = lambda price, act, exp=pd.NaT, con=pd.NaT, ltype="prev_session_high", side="buyside": {
        "level_id": 1, "level_type": ltype, "side": side, "price": price, "activation_ts_utc": ts(act), "expiry_ts_utc": exp, "consumed_ts_utc": con}
    def lv(rows):
        d = pd.DataFrame(rows)
        for c in ("activation_ts_utc", "expiry_ts_utc", "consumed_ts_utc"):
            d[c] = pd.to_datetime(d[c], utc=True)
        return d
    c = cfg(target=TargetConfig(type="opposing_liquidity", fallback_r_multiple=2.0))
    t, src, fb = target_price(s, 101.0, 1.25, c, spec, lv([mk(110.0, "2024-05-15 09:00"), mk(106.0, "2024-05-15 09:30"), mk(104.0, "2024-05-15 10:30")]))
    assert t == 106.0 and src == "opposing_liquidity" and not fb               # 104 activates after setup -> unknown
    t, src, fb = target_price(s, 101.0, 1.25, c, spec, lv([mk(106.0, "2024-05-15 09:30", con="2024-05-15 10:05")]))
    assert t == 103.5 and fb and src.startswith("fallback")                      # consumed before setup -> fallback 2R
    t, _, _ = target_price(s, 101.0, 1.25, c, spec, lv([mk(106.0, "2024-05-15 09:30", exp="2024-05-15 10:00")]))
    assert t == 103.5                                                            # expired
    t, _, _ = target_price(s, 101.0, 1.25, c, spec, lv([mk(98.0, "2024-05-15 09:30", ltype="prev_session_low", side="sellside")]))
    assert t == 103.5                                                            # wrong side


# ----------------------------------------------------------------------------- displacement_candle_extreme (approved stop mode)
def test_displacement_candle_extreme_stop_long_and_short(sessions, spec):
    from ict_lab.engine.execution import displacement_candle_extreme
    # 1m displacement candle at 10:06 with low 97.5 (bullish setup) -> stop 97.25; FVG 100-102, entry 101, risk 3.75, 2R target 108.5
    ohlc = [FLAT] * 6 + [(98.0, 104.0, 97.5, 103.5)] + [FLAT] * 5 + [FILL] + [FLAT] * 400
    s = make_setup()
    s.stop_ref_displacement_ts_utc = ts("2024-05-15 10:06"); s.stop_ref_displacement_confirmation_ts_utc = ts("2024-05-15 10:07"); s.stop_ref_displacement_timeframe = "1m"
    b = arrays(sessions, "2024-05-15 10:00", ohlc)
    assert displacement_candle_extreme(s, b) == (97.5, "ok")
    c = cfg(stop=StopConfig(type="displacement_candle_extreme", buffer_ticks=1))
    tr, _ = simulate(s, b, c, spec, None, ts("2024-05-15 16:00"), NOROLL)
    assert tr["stop_price"] == 97.25 and tr["planned_risk_points"] == 3.75 and tr["target_price"] == 108.5 and tr["stop_type"] == "displacement_candle_extreme"
    assert tr["stop_ref_displacement_ts_utc"] == ts("2024-05-15 10:06") and tr["stop_ref_price"] == 97.5
    sb = make_setup(direction="bearish", upper=102.0, lower=100.0)   # entry = midpoint rounded up = 101.0
    sb.stop_ref_displacement_ts_utc = ts("2024-05-15 10:06"); sb.stop_ref_displacement_confirmation_ts_utc = ts("2024-05-15 10:07"); sb.stop_ref_displacement_timeframe = "1m"
    assert displacement_candle_extreme(sb, b) == (104.0, "ok")
    st, why = stop_price(sb, 101.0, c, spec, b)
    assert st == 104.25 and why == "ok"


def test_displacement_candle_extreme_uses_candle_bucket_for_htf(sessions, spec):
    from ict_lab.engine.execution import displacement_candle_extreme
    # 5m candle 10:05-10:09: lows 99, 97.5, 98, 99, 99 -> extreme 97.5
    ohlc = [FLAT] * 5 + [(100, 101, 99, 100), (100, 101, 97.5, 100), (100, 101, 98, 100), (100, 101, 99, 100), (100, 101, 99, 100)] + [FLAT] * 60
    s = make_setup(); s.stop_ref_displacement_ts_utc = ts("2024-05-15 10:05"); s.stop_ref_displacement_confirmation_ts_utc = ts("2024-05-15 10:10"); s.stop_ref_displacement_timeframe = "5m"
    assert displacement_candle_extreme(s, arrays(sessions, "2024-05-15 10:00", ohlc)) == (97.5, "ok")


def test_displacement_candle_extreme_rejects_without_substitution(sessions, spec):
    c = cfg(stop=StopConfig(type="displacement_candle_extreme", buffer_ticks=1))
    # no stop-reference candle between sweep and FVG confirmation
    s = make_setup()
    tr, nd = run(sessions, spec, [FLAT] * 70, c=c, setup=s)
    assert tr is None and nd["gate_failed"] == "stop" and nd["reason"] == "no_displacement_candle_between_sweep_and_fvg"
    # candle extreme on the wrong side of the entry -> non-positive distance -> rejected
    ohlc = [FLAT] * 6 + [(103.0, 106.0, 102.5, 105.5)] + [FLAT] * 60
    s2 = make_setup(); s2.stop_ref_displacement_ts_utc = ts("2024-05-15 10:06"); s2.stop_ref_displacement_confirmation_ts_utc = ts("2024-05-15 10:07"); s2.stop_ref_displacement_timeframe = "1m"
    tr, nd = run(sessions, spec, ohlc, c=c, setup=s2)
    assert tr is None and "stop_invalid" in nd["reason"] and nd["stop_ref_price"] == 102.5 and nd["stop_ref_displacement_ts_utc"] == ts("2024-05-15 10:06")
    # reference candle not completed at setup time -> rejected
    s3 = make_setup(); s3.stop_ref_displacement_ts_utc = ts("2024-05-15 10:10"); s3.stop_ref_displacement_confirmation_ts_utc = ts("2024-05-15 10:11"); s3.stop_ref_displacement_timeframe = "1m"
    tr, nd = run(sessions, spec, [FLAT] * 70, c=c, setup=s3)
    assert tr is None and nd["reason"] == "displacement_candle_not_completed_at_setup"


def test_displacement_swing_still_blocked():
    with pytest.raises(ValueError):
        cfg(stop=StopConfig(type="displacement_swing"))
