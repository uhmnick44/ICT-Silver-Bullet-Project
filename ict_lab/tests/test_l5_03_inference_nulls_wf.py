"""Layer 5 conventions: null-centred bootstrap, population FDR, template simulation, null-model reproducibility,
analytic cost sensitivity, walk-forward chronological isolation, holdout isolation."""
import numpy as np
import pandas as pd
import pytest

from ict_lab.analysis import nulls as N, robustness as R
from ict_lab.analysis.stats import benjamini_hochberg, stationary_block_bootstrap, stationary_bootstrap_indices
from ict_lab.engine.exec_config import ExitConfig, Layer3Config, StopConfig, TargetConfig
from ict_lab.engine.execution import resolve_exit, simulate, simulate_template
from .l3_fixtures import arrays, make_setup, ts

NOROLL = np.zeros(0, dtype="datetime64[ns]")


def test_bootstrap_null_centred_and_block_structure():
    rng = np.random.default_rng(0)
    idx = stationary_bootstrap_indices(500, 10, 400, rng)
    assert idx.shape == (400, 500) and idx.min() >= 0 and idx.max() < 500
    runs = (np.diff(idx, axis=1) != 1).sum(axis=1) + 1
    assert 8 < 500 / runs.mean() < 12                                   # mean block length ~ 10
    x = rng.normal(0.0, 1.0, 300)
    b = stationary_block_bootstrap(x, 10, seed=3)
    assert 0 < b["p_one_sided"] <= 1 and b["ci_low"] < b["mean_net_r"] < b["ci_high"]
    # null-centred: a strongly positive series gets a tiny p; CI and p are separate objects
    strong = rng.normal(0.8, 0.5, 300); bs = stationary_block_bootstrap(strong, 10, seed=3)
    assert bs["p_one_sided"] < 0.01 and bs["ci_above_zero"]
    assert np.array_equal(stationary_block_bootstrap(x, 10, seed=3)["bootstrap_means"], b["bootstrap_means"])
    for bl in (5, 20):
        assert stationary_block_bootstrap(x, bl, seed=3)["status"] == "ok"


def test_fdr_population_includes_insufficient_configs():
    p = np.array([0.001, 0.5, np.nan, 0.004, np.nan])
    q, rej = benjamini_hochberg(p, 0.10)
    assert rej.tolist() == [True, False, False, True, False] and np.isnan(q[2]) and abs(q[0] - 0.005) < 1e-12 and abs(q[3] - 0.01) < 1e-12


def _cfg():
    return Layer3Config(series_id="x", stop=StopConfig(type="fvg_distal"), target=TargetConfig(type="fixed_r", r_multiple=1.0), exit=ExitConfig(policy="rth_end")).validate()


def test_resolve_exit_matches_simulate(sessions, spec):
    FLAT = (102.5, 103.0, 102.0, 102.5); FILL = (103.0, 103.0, 100.75, 102.0)
    ohlc = [FLAT] * 12 + [FILL] + [(102, 102.2, 101.5, 102)] + [(102, 102.1, 99.75, 100)] + [FLAT] * 60
    b = arrays(sessions, "2024-05-15 10:00", ohlc); s = make_setup(); c = _cfg()
    tr, _ = simulate(s, b, c, spec, None, ts("2024-05-15 16:00"), NOROLL)
    ex = resolve_exit(b, tr["entry_bar_index"], True, tr["entry_price_theoretical"], tr["stop_price"], tr["target_price"], c, spec, b.index_at_or_after(ts("2024-05-15 16:00")))
    assert ex["j"] == tr["exit_bar_index"] and ex["reason"] == tr["exit_reason"] and ex["exit_theo"] == tr["exit_price_theoretical"]


def test_simulate_template_market_and_limit(sessions, spec):
    FLAT = (102.5, 103.0, 102.0, 102.5)
    ohlc = [FLAT] * 12 + [(103.0, 103.0, 100.75, 102.0)] + [FLAT] * 5 + [(102.5, 104.75, 102.4, 104)] + [FLAT] * 400
    b = arrays(sessions, "2024-05-15 10:00", ohlc); c = _cfg(); iE = 60; iT = b.index_at_or_after(ts("2024-05-15 16:00"))
    m = simulate_template(b, c, spec, direction="bullish", k_activate=10, iE=iE, iT=iT, risk_points=2.0, target_r=1.0, entry_mode="market")
    assert m["entry_index"] == 10 and m["entry_price"] == 102.5 and m["stop_price"] == 100.5 and m["target_price"] == 104.5 and m["exit_reason"] == "target"
    assert m["exit_index"] == 18 and abs(m["net_pnl_usd"] - (2.0 * 2 - 1.88)) < 1e-9 and abs(m["net_r"] - (4 - 1.88) / 4) < 1e-9
    l = simulate_template(b, c, spec, direction="bullish", k_activate=10, iE=iE, iT=iT, risk_points=2.0, target_r=1.0, entry_mode="limit", limit=101.0)
    assert l["entry_index"] == 12 and l["entry_price"] == 101.0 and l["stop_price"] == 99.0 and l["target_price"] == 103.0 and l["exit_reason"] == "target"
    # inverted direction on the same limit: a sell limit below the market is marketable at activation -> fills at the limit
    sh = simulate_template(b, c, spec, direction="bearish", k_activate=10, iE=iE, iT=iT, risk_points=2.0, target_r=1.0, entry_mode="limit", limit=101.0)
    assert sh["entry_index"] == 10 and sh["entry_price"] == 101.0 and sh["stop_price"] == 103.0 and sh["exit_reason"] == "stop"
    assert simulate_template(b, c, spec, direction="bullish", k_activate=10, iE=12, iT=iT, risk_points=2.0, target_r=1.0, entry_mode="limit", limit=95.0) is None


def test_recost_is_analytic_and_consistent():
    t = pd.DataFrame({"exit_reason": ["stop", "target", "time_exit_rth"], "gross_pnl_usd": [-10.0, 20.0, 5.0], "commission_usd": [1.88] * 3, "quantity": [1] * 3,
                      "planned_risk_usd": [10.0] * 3, "trading_date": pd.to_datetime(["2023-01-03"] * 3), "entry_fill_ts_utc": pd.date_range("2023-01-03", periods=3, freq="h", tz="UTC"),
                      "same_bar_ambiguous": False, "excluded_by_roll_policy": False, "gross_r": [-1.0, 2.0, 0.5]})
    r = R.recost(t, 2.0, 3, 2)
    assert r["slippage_ticks"].tolist() == [3.0, 0.0, 2.0] and (r["commission_usd"] == 3.76).all()
    assert abs(r.loc[0, "net_pnl_usd"] - (-10 - 1.5 - 3.76)) < 1e-9 and abs(r.loc[2, "net_pnl_usd"] - (5 - 1.0 - 3.76)) < 1e-9
    cs = R.cost_sensitivity(t, pd.bdate_range("2023-01-02", periods=5))
    assert len(cs) == 3 * 4 * 3 and (cs["n_trades"] == 3).all() and (cs["method"] == "analytic_recost").all()


def test_walk_forward_folds_and_isolation():
    folds = R.walk_forward_folds(pd.Timestamp("2022-10-03"), pd.Timestamp("2024-10-18"))
    assert folds[0]["eval_start"] == pd.Timestamp("2023-10-01") and folds[0]["train_end"] == pd.Timestamp("2023-09-30")
    assert [f["eval_start"].strftime("%Y-%m-%d") for f in folds] == ["2023-10-01", "2024-01-01", "2024-04-01", "2024-07-01", "2024-10-01"]
    assert folds[-1]["partial_fold"] and folds[-1]["eval_end"] == pd.Timestamp("2024-10-18") and not folds[0]["partial_fold"]
    for a, b in zip(folds[:-1], folds[1:]):
        assert b["train_end"] == a["eval_end"] and b["eval_start"] > a["eval_end"]        # expanding, non-overlapping
    # selection uses training only: a config that is great in evaluation but bad in training is never chosen
    dates = pd.bdate_range("2022-10-03", "2024-10-18")
    def mk(h, train_r, eval_r):
        d = dates[::3]
        r = np.where(d <= pd.Timestamp("2023-09-30"), train_r, eval_r)
        return pd.DataFrame({"grid_config_hash": h, "trading_date": d, "entry_fill_ts_utc": pd.DatetimeIndex(d).tz_localize("UTC"), "net_r": r, "gross_r": r,
                             "net_pnl_usd": r * 10, "same_bar_ambiguous": False, "excluded_by_roll_policy": False})
    sw = pd.concat([mk("good_train", 0.3, -1.0), mk("bad_train", -0.3, 2.0)], ignore_index=True)
    sel, fs = R.walk_forward(sw, {"good_train": dates, "bad_train": dates}, "2022-10-03", "2024-10-18", min_train_trades=50)
    assert set(sel.loc[sel["fold"] == 1, "config_hash"]) == {"good_train"} and sel.loc[sel["fold"] == 1, "eval_net_r"].iloc[0] < 0


def test_offhour_windows_definition():
    assert len(N.OFFHOUR_WINDOWS) == 20 and all(v[1] - v[0] == 60 for v in N.OFFHOUR_WINDOWS.values())
    starts = {v[0] // 60 for v in N.OFFHOUR_WINDOWS.values()}
    assert starts.isdisjoint({3, 10, 14, 17}) and Layer3Config(series_id="x", stop=StopConfig(type="fvg_distal")).validate()
    from ict_lab.engine.exec_config import SignalConfig
    Layer3Config(series_id="x", stop=StopConfig(type="fvg_distal"), signal=SignalConfig(windows=("oh_1800",))).validate()
    with pytest.raises(ValueError):
        Layer3Config(series_id="x", stop=StopConfig(type="fvg_distal"), signal=SignalConfig(windows=("rth",))).validate()


@pytest.fixture(scope="module")
def store(cfg, clean_dir):
    from ict_lab.engine.backtest import FeatureStore
    from ict_lab.features.config import load_layer2_config
    return FeatureStore.build(cfg, load_layer2_config())


def test_null_models_reproducible_and_development_only(store, cfg):
    from ict_lab.engine.backtest import run_backtest
    from ict_lab.engine.exec_config import load_named_config
    c = load_named_config("as_traded"); tr = run_backtest(c, store)["trades"].head(40)
    tpl = N.trade_templates(tr, store)
    assert len(tpl) == 40 and all(t.w_start <= t.k_activate < t.w_end <= t.iE and t.iT >= t.iE for t in tpl)
    a1 = N.null_a_random_entry(tpl, store, c, n_iter=5, seed=1); a2 = N.null_a_random_entry(tpl, store, c, n_iter=5, seed=1); a3 = N.null_a_random_entry(tpl, store, c, n_iter=5, seed=2)
    pd.testing.assert_frame_equal(a1, a2); assert not a1["mean_net_r"].equals(a3["mean_net_r"])
    c1 = N.null_c_shuffled_direction(tpl, store, c, n_iter=5, seed=1); c2 = N.null_c_shuffled_direction(tpl, store, c, n_iter=5, seed=1)
    pd.testing.assert_frame_equal(c1, c2) and (c1["flipped"] <= 40).all()
    ex = N.exceedance(a1["mean_net_r"].to_numpy(), tr["net_r"].mean())
    assert 0 < ex["p_null_ge_actual"] <= 1
    assert store.data.bars["trading_date"].max() <= pd.Timestamp(cfg["split"]["development_end"])
