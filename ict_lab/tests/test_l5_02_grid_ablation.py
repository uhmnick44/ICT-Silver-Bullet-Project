"""Layer 5: grid deduplication, deterministic sampling, fixed stop and liquidity rules in every grid point,
holdout isolation of the sweep runner, ablation consistency and lookahead isolation."""
import pandas as pd
import pytest

from ict_lab.analysis import grid as G
from ict_lab.analysis.ablation import BASE_SIGNAL, STEPS, run_ablation
from ict_lab.engine.backtest import FeatureStore, run_backtest
from ict_lab.engine.exec_config import LIQUIDITY_UNIVERSES, load_layer3_config
from ict_lab.features.config import load_layer2_config


@pytest.fixture(scope="module")
def grid():
    return G.generate_grid()


def test_grid_counts_and_deduplication(grid):
    expected = 1
    for v in G.DIMENSIONS.values():
        expected *= len(v)
    assert len(grid) == expected == 11520
    unique = grid[~grid["is_duplicate"]]
    assert len(unique) == 8640 and unique["semantic_key"].is_unique and unique["config_hash"].is_unique
    # every swings_only point duplicates a bsl_ssl_15m point and nothing else is removed
    assert grid.loc[grid["is_duplicate"], "liquidity_universe"].eq("swings_only").all()
    assert (grid.groupby("liquidity_universe")["is_duplicate"].sum() == pd.Series({"bsl_ssl_15m": 0, "session_refs": 0, "session_refs_plus_swings": 0, "swings_only": 2880})).all()
    assert "swings_only" not in set(unique["liquidity_universe"])


def test_every_grid_point_keeps_fixed_rules(grid):
    sample = grid[~grid["is_duplicate"]].sample(40, random_state=3)
    keys = list(G.DIMENSIONS)
    for r in sample.itertuples(index=False):
        d = r._asdict(); p = {k: d[k] for k in keys}
        p["windows"] = tuple(p["windows"].split(";")); p["max_trades_per_window"] = "unlimited" if p["max_trades_per_window"] == "unlimited" else int(p["max_trades_per_window"])
        p["require_mss"] = bool(p["require_mss"])
        c = G.make_config(p)
        assert c.stop.type == "liquidity_sweep_extreme" and c.stop.buffer_ticks == 1 and c.exit.policy == "rth_end" and c.roll.policy == "flag_and_exclude"
        assert c.signal.min_fvg_points == 0 and c.signal.min_fvg_atr == 0 and c.sweep_k_ok if hasattr(c, "sweep_k_ok") else True
        assert "swing_1m" not in c.signal.liquidity_types and set(c.signal.liquidity_types) <= {"prev_session", "prev_rth", "prewindow", "swing_15m"}
        assert c.target.type == "fixed_r" and c.target.r_multiple == 1.0 and c.signal.require_displacement
        assert c.config_hash == r.config_hash


def test_sampling_deterministic_and_bounded(grid):
    u = grid[~grid["is_duplicate"]].reset_index(drop=True)
    a = G.sample_grid(u, 100, 42); b = G.sample_grid(u, 100, 42); c = G.sample_grid(u, 100, 43)
    assert a["config_hash"].tolist() == b["config_hash"].tolist() and a["config_hash"].tolist() != c["config_hash"].tolist()
    assert len(a) == 100 and a["config_hash"].is_unique and set(a["config_hash"]) <= set(u["config_hash"])
    assert len(G.sample_grid(u, None, None)) == len(u)
    with pytest.raises(ValueError):
        G.sample_grid(u, 10, None)


@pytest.fixture(scope="module")
def store(cfg, clean_dir):
    return FeatureStore.build(cfg, load_layer2_config())


def test_sweep_runner_is_development_only_and_matches_direct_run(store, cfg):
    G._STORE = store
    p = {"fvg_timeframe": "5m", "liquidity_universe": "bsl_ssl_15m", "bias_detector": "none", "displacement_threshold": 1.5, "require_mss": False,
         "entry_location": "midpoint", "target_r": 1.0, "windows": ("sb_london", "sb_ny_am", "sb_ny_pm"), "max_trades_per_window": 1}
    m, tr = G._evaluate(p)
    assert tr["trading_date"].max() <= pd.Timestamp(cfg["split"]["development_end"]) and (tr["grid_config_hash"] == m["config_hash"]).all()
    direct = run_backtest(G.make_config(p), store)["trades"]
    assert len(direct) == m["n_trades"] + m["n_excluded_roll"] and m["status"] in ("ok", "insufficient_data")


def test_ablation_consistency_and_lookahead_isolation(store):
    df = run_ablation(store).set_index("step")
    assert (df.loc[["1_fvg_only", "2_fvg_sweep", "3_fvg_sweep_displacement"], "status"] == "not_performed").all()
    step4 = df.loc["4_fvg_sweep_displacement_window"]
    base = load_layer3_config(G.BASE_CONFIG, signal={**BASE_SIGNAL, "bias_detector": "none"}, entry={"location": "midpoint"},
                              stop={"type": "liquidity_sweep_extreme", "buffer_ticks": 1}, target={"type": "fixed_r", "r_multiple": 1.0}, exit={"policy": "rth_end"})
    assert step4["n_trades"] == len(run_backtest(base, store)["trades"])            # step 4 == the shared base run directly
    diag = df.loc["diagnostic_perfect_future_bias_LOOKAHEAD"]
    assert diag["lookahead"] and "INVALID" in diag["note"]
    valid_candidates = df[(df["status"] != "not_performed") & (~df["lookahead"].astype(bool))]
    assert "diagnostic_perfect_future_bias_LOOKAHEAD" not in valid_candidates.index
    # the diagnostic's injected bias table is not left behind in the store cache
    assert "swing_15m_structure" not in store._bias_cache or len(store._bias_cache["swing_15m_structure"]) == len(store.bias_table("swing_15m_structure"))
