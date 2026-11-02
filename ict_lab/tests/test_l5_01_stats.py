"""Layer 5 statistical utilities (fully specified parts only)."""
import numpy as np
import pandas as pd
import pytest

from ict_lab.analysis.stats import (FDR_Q, MIN_TRADES, benjamini_hochberg, passes_descriptive_screen, performance_metrics, qualify,
                                    stationary_block_bootstrap)


def trades_df(net_r, risk_usd=10.0, dates=None):
    n = len(net_r); net_r = np.asarray(net_r, float)
    d = pd.to_datetime(dates) if dates is not None else pd.bdate_range("2023-01-02", periods=n)
    return pd.DataFrame({"net_r": net_r, "gross_r": net_r + 0.1, "net_pnl_usd": net_r * risk_usd, "trading_date": d,
                         "same_bar_ambiguous": False, "excluded_by_roll_policy": False})


def test_metrics_net_r_costs_sharpe_and_insufficient_status():
    t = trades_df([2.0, -1.0, 2.0, -1.0] * 30)
    m = performance_metrics(t, pd.bdate_range("2023-01-02", periods=120))
    assert m["status"] == "ok" and m["n_trades"] == 120 and abs(m["net_expectancy_r"] - 0.5) < 1e-12 and abs(m["net_pnl_usd"] - 600) < 1e-9
    assert m["win_rate"] == 0.5 and abs(m["profit_factor"] - 2.0) < 1e-12 and abs(m["avg_win_r"] - 2.0) < 1e-12 and abs(m["avg_loss_r"] + 1.0) < 1e-12
    daily = np.array([20.0, -10.0] * 60); assert abs(m["net_sharpe"] - daily.mean() / daily.std(ddof=1) * np.sqrt(252)) < 1e-9
    assert m["max_drawdown_usd"] == 10.0 and m["max_drawdown_r"] == 1.0
    small = performance_metrics(trades_df([1.0] * 50), pd.bdate_range("2023-01-02", periods=50))
    assert small["status"] == "insufficient_data" and small["net_expectancy_r"] == 1.0 and not passes_descriptive_screen(small)
    empty = performance_metrics(trades_df([]), pd.bdate_range("2023-01-02", periods=10))
    assert empty["status"] == "insufficient_data" and empty["net_expectancy_r"] is None and empty["net_sharpe"] is None
    # roll-excluded trades are dropped and counted; costs are already inside net_r/net_pnl from the engine
    t2 = t.copy(); t2.loc[0, "excluded_by_roll_policy"] = True
    assert performance_metrics(t2, pd.bdate_range("2023-01-02", periods=120))["n_excluded_roll"] == 1


def test_descriptive_screen_thresholds():
    good = performance_metrics(trades_df([1.0, -0.5] * 60), pd.bdate_range("2023-01-02", periods=120))
    assert passes_descriptive_screen(good)
    bad_sharpe = performance_metrics(trades_df([3.0, -2.95] * 60), pd.bdate_range("2023-01-02", periods=120))
    assert bad_sharpe["net_pnl_usd"] > 0 and not passes_descriptive_screen(bad_sharpe)
    neg = performance_metrics(trades_df([1.0, -1.5] * 60), pd.bdate_range("2023-01-02", periods=120))
    assert not passes_descriptive_screen(neg)


def test_benjamini_hochberg_full_family():
    p = [0.001, 0.02, 0.03, 0.5, np.nan, 0.9]
    q, rej = benjamini_hochberg(p, 0.10)
    assert rej.tolist() == [True, True, True, False, False, False]
    assert abs(q[0] - 0.006) < 1e-12 and abs(q[1] - 0.06) < 1e-12 and abs(q[2] - 0.06) < 1e-12 and np.isnan(q[4])
    # correcting only the "profitable" subset would be wrong: family size changes the q-values
    q_sub, _ = benjamini_hochberg([0.001, 0.02, 0.03], 0.10)
    assert q_sub[1] < q[1]
    assert benjamini_hochberg([], 0.1)[0].size == 0


def test_bootstrap_reproducible_one_sided_and_requires_block_length():
    rng = np.random.default_rng(1); x = rng.normal(0.3, 1.0, 300)
    a = stationary_block_bootstrap(x, block_length=5, seed=7); b = stationary_block_bootstrap(x, block_length=5, seed=7)
    assert a["status"] == "ok" and np.array_equal(a["bootstrap_means"], b["bootstrap_means"]) and a["n_resamples"] == 1000
    assert a["ci_low"] < a["mean_net_r"] < a["ci_high"] and 0 <= a["p_one_sided"] <= 1
    c = stationary_block_bootstrap(x, block_length=5, seed=8)
    assert not np.array_equal(a["bootstrap_means"], c["bootstrap_means"])
    with pytest.raises(ValueError):
        stationary_block_bootstrap(x, block_length=None)
    assert stationary_block_bootstrap(np.array([1.0]), block_length=3)["status"] == "insufficient_data"
    # a clearly negative series never gets a CI above zero
    neg = stationary_block_bootstrap(rng.normal(-0.5, 0.2, 200), block_length=4, seed=1)
    assert not neg["ci_above_zero"] and neg["p_one_sided"] > 0.95


def test_qualification_tiers():
    good = performance_metrics(trades_df([1.0, -0.5] * 60), pd.bdate_range("2023-01-02", periods=120))
    boot_ok = {"status": "ok", "ci_above_zero": True}; boot_bad = {"status": "ok", "ci_above_zero": False}
    assert qualify(good, True, boot_ok, True).tier == "full_evidence_standard"
    assert qualify(good, True, boot_bad, True).tier == "fdr_pass"
    assert qualify(good, True, boot_ok, None).tier == "fdr_pass"
    assert qualify(good, False, boot_ok, True).tier == "descriptive_screen"
    small = performance_metrics(trades_df([1.0] * 20), pd.bdate_range("2023-01-02", periods=20))
    assert qualify(small, True, boot_ok, True).tier == "exploratory"
