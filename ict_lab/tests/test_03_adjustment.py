"""Additive back-adjustment arithmetic, tick-grid alignment, identical timestamps."""
import numpy as np
import pandas as pd

from ict_lab.engine.continuous import build_backadjusted, build_unadjusted
from ict_lab.engine.instrument import InstrumentSpec


def test_synthetic_additive_adjustment(sessions):
    spec = InstrumentSpec("MNQ", 0.25, 0.5, 2.0, r"^MNQ[HMUZ][0-9]$")
    ts = pd.date_range("2024-01-02 15:00", periods=4, freq="1min", tz="UTC")
    bars = pd.DataFrame({"ts_utc": list(ts) * 2, "symbol": ["MNQH4"] * 4 + ["MNQM4"] * 4,
                         "instrument_id": [1] * 4 + [2] * 4,
                         "open": [100, 101, 102, 103] + [110, 111, 112, 113],
                         "high": [101, 102, 103, 104] + [111, 112, 113, 114],
                         "low": [99, 100, 101, 102] + [109, 110, 111, 112],
                         "close": [100.5, 101.5, 102.5, 103.5] + [110.5, 111.5, 112.5, 113.5], "volume": 1})
    bars = sessions.annotate(bars)
    # pretend the first two minutes are trading date A (H4 active), last two are date B (M4 active)
    bars["trading_date"] = pd.to_datetime(["2024-01-02"] * 2 + ["2024-01-03"] * 2 + ["2024-01-02"] * 2 + ["2024-01-03"] * 2)
    sel = pd.DataFrame({"active_symbol": ["MNQH4", "MNQM4"]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"]))
    un = build_unadjusted(bars, sel, sessions)
    roll_log = pd.DataFrame({"roll_id": [1], "offset_points": [10.0], "cumulative_adjustment_before_roll": [10.0]})
    ad = build_backadjusted(un, roll_log, spec)
    assert (ad["ts_utc"] == un["ts_utc"]).all()
    assert ad["adjustment"].tolist() == [10.0, 10.0, 0.0, 0.0]
    assert ad["close"].tolist() == [110.5, 111.5, 112.5, 113.5]
    assert ((ad["high"] - ad["low"]) == (un["high"] - un["low"])).all()


def test_real_adjustment_arithmetic(unadj, adj, rolls_csv, spec):
    for c in ["open", "high", "low", "close"]:
        assert np.allclose(adj[c] - unadj[c], adj["adjustment"])
        assert np.allclose(adj[c] - unadj[c], adj["adjustment"], atol=1e-9)
    # anchor: latest contract unadjusted
    last_seg = adj["segment_id"].max()
    assert (adj.loc[adj["segment_id"] == last_seg, "adjustment"] == 0).all()
    # cumulative adjustment for segment k equals sum of offsets of rolls after it
    offs = rolls_csv.sort_values("roll_id")["offset_points"].to_numpy()
    for k in range(last_seg + 1):
        expected = offs[k:].sum()
        got = adj.loc[adj["segment_id"] == k, "adjustment"].unique()
        assert len(got) == 1 and abs(got[0] - expected) < 1e-9
    # distances preserved exactly
    assert np.array_equal((adj["high"] - adj["low"]).to_numpy(), (unadj["high"] - unadj["low"]).to_numpy())


def test_real_tick_grid(unadj, adj, rolls_csv, spec):
    for df in (unadj, adj):
        for c in ["open", "high", "low", "close"]:
            assert spec.on_tick_grid(df[c].to_numpy()).all()
    assert spec.on_tick_grid(rolls_csv["offset_points"].to_numpy()).all()
    assert spec.on_tick_grid(rolls_csv["cumulative_adjustment_before_roll"].to_numpy()).all()
    assert (rolls_csv["offset_ticks"] == rolls_csv["offset_points"] / spec.tick_size).all()
    assert rolls_csv["offset_is_tick_multiple"].all()


def test_identical_timestamps_and_row_order(unadj, adj):
    assert len(unadj) == len(adj)
    assert np.array_equal(unadj["ts_utc"].to_numpy(), adj["ts_utc"].to_numpy())
    assert np.array_equal(unadj["bar_index"].to_numpy(), adj["bar_index"].to_numpy())
    assert np.array_equal(unadj["symbol"].to_numpy(), adj["symbol"].to_numpy())
    assert np.array_equal(unadj["volume"].to_numpy(), adj["volume"].to_numpy())
    assert unadj["ts_utc"].is_monotonic_increasing and not unadj["ts_utc"].duplicated().any()


def test_instrument_spec_values(spec):
    assert spec.tick_size == 0.25 and spec.tick_value == 0.5 and spec.point_value == 2.0
    assert spec.points_to_ticks(1.0) == 4 and spec.points_to_usd(10.0, 3) == 60.0
    assert spec.is_tick_multiple(116.5) and not spec.is_tick_multiple(116.6)
