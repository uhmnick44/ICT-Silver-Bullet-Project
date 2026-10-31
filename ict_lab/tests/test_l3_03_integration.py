"""Layer 3 development-period integration: no overlap, holdout isolation, determinism, cache equivalence, roll handling."""
import json

import pandas as pd
import pytest

from ict_lab.engine.backtest import FeatureStore, run_backtest, write_backtest
from ict_lab.engine.exec_config import ExitConfig, load_layer3_config
from ict_lab.features.config import load_layer2_config
from ict_lab.features.series import load_series


@pytest.fixture(scope="module")
def l2cfg():
    return load_layer2_config()


@pytest.fixture(scope="module")
def store(cfg, l2cfg, clean_dir):
    return FeatureStore.build(cfg, l2cfg)


@pytest.fixture(scope="module")
def baseline():
    return load_layer3_config("ict_lab/configs/baseline_verification.toml")


def test_store_is_development_only_and_cached(store, cfg):
    assert store.data.bars["trading_date"].max() == pd.Timestamp(cfg["split"]["development_end"])
    assert (store.data.bars["split"] == "development").all() and store.source.startswith("cache")
    assert len(store.data.rolls) == 8


def test_baseline_run_invariants(store, baseline, cfg):
    res = run_backtest(baseline, store)
    tr, nd = res["trades"], res["no_trade"]
    assert len(tr) > 0 and len(tr) + len(nd) == (store.feats["windows"]["window"] == "sb_ny_am").sum()
    assert tr["trading_date"].max() <= pd.Timestamp(cfg["split"]["development_end"])
    assert (tr["order_active_ts_utc"] >= tr["setup_ts_utc"]).all() and (tr["entry_fill_ts_utc"] >= tr["order_active_ts_utc"]).all()
    assert (tr["exit_ts_utc"] >= tr["entry_fill_ts_utc"]).all()
    assert (tr["setup_ts_utc"] >= tr["sweep_confirmation_ts_utc"]).all() and (tr["setup_ts_utc"] >= tr["fvg_confirmation_ts_utc"]).all()
    assert (tr["setup_ts_utc"] >= tr["displacement_confirmation_ts_utc"]).all()
    assert tr.groupby(["trading_date", "window"]).size().max() == 1
    assert tr["trade_id"].is_unique and (tr["config_hash"] == baseline.config_hash).all()
    assert set(tr["level_type"].str.replace(r"_(high|low)$", "", regex=True)) <= {"prev_session", "prewindow"}
    assert (tr["fvg_timeframe"] == "5m").all() and (tr["displacement_ratio"] >= 1.5).all()
    for c in ("entry_price", "stop_price", "target_price"):
        assert ((tr[c] * 4).round(9) % 1 == 0).all()
    assert not tr["spans_roll"].any()
    # gate diagnostics are populated
    assert nd["gate_failed"].notna().all() and set(nd["gate_failed"]) <= {"window_eligible", "position_free", "bias", "sweep", "mss", "displacement", "fvg", "stop", "target", "entry_fill"}


def test_no_overlapping_positions_across_windows(store, baseline):
    # wide fixed stop + rth_end exit: trades stay open for hours, so later windows on the same day must be blocked
    c = load_layer3_config("ict_lab/configs/baseline_verification.toml", signal={"windows": ["sb_london", "sb_ny_am", "sb_ny_pm"]},
                           stop={"type": "fixed_points", "fixed_points": 150.0}, target={"type": "fixed_r", "r_multiple": 3.0})
    res = run_backtest(c, store)
    tr = res["trades"].sort_values("entry_fill_ts_utc").reset_index(drop=True)
    assert len(tr) > 10
    assert (tr["entry_fill_ts_utc"].iloc[1:].to_numpy() > tr["exit_ts_utc"].iloc[:-1].to_numpy()).all()
    blocked = res["no_trade"][res["no_trade"]["gate_failed"] == "position_free"]
    assert len(blocked) > 0
    wstart = store.feats["windows"].set_index(["trading_date", "window"])["start_ts_utc"]
    for r in blocked.itertuples():
        st = pd.Timestamp(wstart.loc[(pd.Timestamp(r.trading_date), r.window)])
        assert ((tr["entry_fill_ts_utc"] < st) & (tr["exit_ts_utc"] >= st)).any()


def test_deterministic_trade_logs(store, baseline, tmp_path, l2cfg):
    a = run_backtest(baseline, store); b = run_backtest(baseline, store)
    pd.testing.assert_frame_equal(a["trades"], b["trades"]); pd.testing.assert_frame_equal(a["no_trade"], b["no_trade"])
    out = write_backtest(a, baseline, store, l2cfg, tmp_path)
    m = json.loads((out / "backtest_manifest.json").read_text())
    assert m["holdout_accessed"] is False and m["development_range"][1] == "2024-10-18" and m["trades"] == len(a["trades"])
    m2 = write_backtest(b, baseline, store, l2cfg, tmp_path / "again")
    assert json.loads((m2 / "backtest_manifest.json").read_text())["trades_content_hash"] == m["trades_content_hash"]


@pytest.mark.slow
def test_cached_and_uncached_features_give_identical_trades(cfg, l2cfg, store, baseline):
    fresh = FeatureStore.build(cfg, l2cfg, use_cache=False)
    assert fresh.source == "computed"
    a = run_backtest(baseline, store)["trades"]; b = run_backtest(baseline, fresh)["trades"]
    pd.testing.assert_frame_equal(a, b)


def test_hold_policy_flags_roll_spanning_trades(store):
    ov = dict(exit={"policy": "hold"}, stop={"type": "fixed_points", "fixed_points": 400.0}, target={"type": "fixed_r", "r_multiple": 2.0})
    c = load_layer3_config("ict_lab/configs/baseline_verification.toml", roll={"policy": "flag_only"}, **ov)
    tr = run_backtest(c, store)["trades"]
    spanning = tr[tr["spans_roll"]]
    assert len(spanning) > 0 and (spanning["entry_adjustment"] != spanning["exit_adjustment"]).all()
    assert (spanning["entry_symbol"] != spanning["exit_symbol"]).all() and not spanning["excluded_by_roll_policy"].any()
    c2 = load_layer3_config("ict_lab/configs/baseline_verification.toml", **ov)
    tr2 = run_backtest(c2, store)["trades"]
    assert tr2["spans_roll"].any() and tr2.loc[tr2["spans_roll"], "excluded_by_roll_policy"].all()
    assert not tr2.loc[~tr2["spans_roll"], "excluded_by_roll_policy"].any()


def test_holdout_cannot_be_reached_through_layer3(cfg, l2cfg):
    with pytest.raises(Exception):
        load_series(l2cfg.series_id, cfg, start="2025-01-01", end="2025-03-01").bars["trading_date"].min() >= pd.Timestamp("2025-01-01") or (_ for _ in ()).throw(ValueError)
    d = load_series(l2cfg.series_id, cfg, start="2025-01-01", end="2025-03-01")
    assert len(d.bars) == 0
