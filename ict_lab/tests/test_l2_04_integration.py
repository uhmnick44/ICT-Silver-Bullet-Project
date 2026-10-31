"""Layer 2 development-period integration: DST, missing bars, no-lookahead truncation, series independence, holdout."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ict_lab.engine import loader
from ict_lab.features import run as l2run
from ict_lab.features.config import Layer2Config, load_layer2_config
from ict_lab.features.series import SERIES_REGISTRY, SeriesSpec, load_series, register_series, truncate
from ict_lab.features.timeframes import resample

NY = "America/New_York"


@pytest.fixture(scope="module")
def l2cfg():
    return load_layer2_config()


@pytest.fixture(scope="module")
def dev_slice(cfg, l2cfg, clean_dir):
    return load_series(l2cfg.series_id, cfg, start="2024-02-20", end="2024-04-05")


@pytest.fixture(scope="module")
def feats(dev_slice, l2cfg, cfg):
    return l2run.compute_all(dev_slice, l2cfg, cfg)


def test_series_loader_is_development_only(dev_slice, cfg):
    assert dev_slice.bars["trading_date"].max() <= pd.Timestamp(cfg["split"]["development_end"])
    assert (dev_slice.bars["split"] == "development").all()
    full = load_series(cfg=cfg)
    assert full.bars["trading_date"].max() == pd.Timestamp("2024-10-18") and len(full.rolls) == 8


def test_dst_boundary_candles_and_windows(dev_slice, feats):
    c15 = resample(dev_slice.bars, "15m")
    # Sunday 2024-03-10 DST start: first 15m candle of trading date 03-11 opens 18:00 EDT = 22:00 UTC
    first = c15[c15["trading_date"] == pd.Timestamp("2024-03-11")].iloc[0]
    assert first["ts_utc"] == pd.Timestamp("2024-03-10 22:00", tz="UTC") and first["available_ts_utc"] == pd.Timestamp("2024-03-10 22:15", tz="UTC")
    w = feats["windows"]
    before = w[(w["trading_date"] == pd.Timestamp("2024-03-08")) & (w["window"] == "sb_ny_am")].iloc[0]
    after = w[(w["trading_date"] == pd.Timestamp("2024-03-11")) & (w["window"] == "sb_ny_am")].iloc[0]
    assert before["start_ts_utc"] == pd.Timestamp("2024-03-08 15:00", tz="UTC") and after["start_ts_utc"] == pd.Timestamp("2024-03-11 14:00", tz="UTC")
    assert before["start_ny"].strftime("%H:%M") == "10:00" == after["start_ny"].strftime("%H:%M")


def test_good_friday_closure_and_window_exclusions(feats):
    w = feats["windows"]
    assert not (w["trading_date"] == pd.Timestamp("2024-03-29")).any()        # no session, no windows
    rows = w[w["trading_date"] == pd.Timestamp("2024-03-28")]
    assert rows["eligible"].all()
    assert (w.loc[~w["eligible"], "exclusion_reasons"] != "").all()


def test_no_fvg_or_sweep_spans_a_missing_bar(dev_slice, feats):
    bars = dev_slice.bars
    f = feats["fvg"]; f1 = f[f["timeframe"] == "1m"]
    idx = pd.DatetimeIndex(bars["ts_utc"]); cons = bars["consecutive_prev"].to_numpy()
    pos = idx.get_indexer(pd.DatetimeIndex(f1["c3_ts_utc"]))
    assert (pos >= 2).all() and cons[pos].all() and cons[pos - 1].all()
    # every feature timestamp maps to a real bar (nothing fabricated / forward-filled)
    for col in ("c1_ts_utc", "c2_ts_utc", "c3_ts_utc"):
        assert idx.get_indexer(pd.DatetimeIndex(f1[col])).min() >= 0
    assert idx.get_indexer(pd.DatetimeIndex(feats["sweeps"]["penetration_ts_utc"])).min() >= 0


def test_features_confirm_after_formation_and_in_order(feats):
    f = feats["fvg"]
    assert (f["confirmation_ts_utc"] > f["formation_ts_utc"]).all()
    assert (f["first_mitigation_ts_utc"].isna() | (f["first_mitigation_ts_utc"] >= f["confirmation_ts_utc"])).all()
    assert (f["full_fill_ts_utc"].isna() | (f["full_fill_ts_utc"] >= f["first_mitigation_ts_utc"])).all()
    lv = feats["liquidity_levels"]
    assert (lv["activation_ts_utc"] >= lv["confirmation_ts_utc"]).all() and (lv["confirmation_ts_utc"] >= lv["formation_ts_utc"]).all()
    assert (lv["penetration_ts_utc"].isna() | (lv["penetration_ts_utc"] >= lv["activation_ts_utc"])).all()
    sw = feats["sweeps"]
    assert (sw["confirmation_ts_utc"] > sw["penetration_ts_utc"]).all()
    assert (sw["bars_to_confirmation"] <= 3).all() and (sw.loc[sw["status"] == "confirmed", "max_penetration_ticks"] >= 1).all()
    m = feats["mss"]; mm = m[m["found"]]
    assert (mm["swing_confirmation_ts_utc"] <= mm["break_ts_utc"]).all()
    assert set(lv["level_type"].str.replace(r"_(high|low)$", "", regex=True)) <= {"prev_session", "prev_rth", "prewindow", "swing_15m"}


@pytest.mark.slow
def test_no_lookahead_truncation(dev_slice, feats, l2cfg, cfg):
    """Features confirmed before the cut must be identical when computed on the prefix only."""
    cut = pd.Timestamp("2024-03-20 11:00", tz=NY).tz_convert("UTC")
    pre = truncate(dev_slice, cut)
    pf = l2run.compute_all(pre, l2cfg, cfg)
    def cmp(name, conf_col, keys):
        a = feats[name]; b = pf[name]
        a = a[a[conf_col] <= cut].sort_values(keys).reset_index(drop=True)
        b = b[b[conf_col] <= cut].sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(a[keys], b[keys], check_dtype=False)
        return a, b
    a, b = cmp("fvg", "confirmation_ts_utc", ["timeframe", "c3_ts_utc", "direction", "upper", "lower", "gap_points", "atr", "gap_atr"])
    # mitigation that happened before the cut must agree; after the cut the prefix cannot know it (NaT allowed)
    known = a["first_mitigation_ts_utc"] <= cut
    assert (a.loc[known, "first_mitigation_ts_utc"].to_numpy() == b.loc[known, "first_mitigation_ts_utc"].to_numpy()).all()
    cmp("liquidity_levels", "activation_ts_utc", ["level_type", "price", "formation_ts_utc", "confirmation_ts_utc", "activation_ts_utc"])
    cmp("sweeps", "confirmation_ts_utc", ["level_type", "level_price", "penetration_ts_utc", "confirmation_ts_utc", "status", "max_penetration_points"])
    cmp("displacement", "confirmation_ts_utc", ["ts_utc", "range_atr_ratio", "threshold_passed", "passes_percentile"])
    m_full = feats["mss"]; m_pre = pf["mss"]
    done = m_full[m_full["found"] & (m_full["break_ts_utc"] <= cut)]
    s_full = feats["sweeps"].set_index("sweep_id"); s_pre = pf["sweeps"].set_index("sweep_id")
    key = lambda m, s: m.assign(pen=s.loc[m["sweep_id"], "penetration_ts_utc"].to_numpy())
    d1 = key(done, s_full).sort_values("pen")[["pen", "swing_price", "break_ts_utc"]].reset_index(drop=True)
    d2 = key(m_pre[m_pre["found"] & (m_pre["break_ts_utc"] <= cut)], s_pre).sort_values("pen")[["pen", "swing_price", "break_ts_utc"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(d1, d2, check_dtype=False)
    b_full = feats["bias"]; b_pre = pf["bias"]
    pd.testing.assert_frame_equal(b_full[b_full["eval_ts_utc"] <= cut].reset_index(drop=True), b_pre[b_pre["eval_ts_utc"] <= cut].reset_index(drop=True))


def test_roll_series_independence(dev_slice, feats, l2cfg, cfg):
    """Detectors run unchanged on another registered series; outputs carry that series id; roll dates stay available."""
    alt_id = "mnq_test_alt_series"
    if alt_id not in SERIES_REGISTRY:
        register_series(SeriesSpec(alt_id, cfg["roll"]["convention_name"], "backadjusted", "backadjusted", "test alias"))
    alt = load_series(alt_id, cfg, start="2024-03-18", end="2024-03-22")
    alt_feats = l2run.compute_all(alt, l2cfg, cfg)
    for name, df in alt_feats.items():
        if name != "rolls" and len(df):
            assert (df["series_id"] == alt_id).all()
    assert len(alt_feats["rolls"]) == 8 and "effective_trading_date" in alt_feats["rolls"]
    # same bars under a different id -> identical feature values
    same = feats["fvg"]; same = same[(same["trading_date"] >= pd.Timestamp("2024-03-18")) & (same["trading_date"] <= pd.Timestamp("2024-03-22"))]
    # (the slice starts earlier so ATR warm-up differs; compare gap boundaries only)
    a = same[["timeframe", "c3_ts_utc", "upper", "lower"]].sort_values(["timeframe", "c3_ts_utc"]).reset_index(drop=True)
    b = alt_feats["fvg"][["timeframe", "c3_ts_utc", "upper", "lower"]].sort_values(["timeframe", "c3_ts_utc"]).reset_index(drop=True)
    b = b[b["c3_ts_utc"].isin(a["c3_ts_utc"])].reset_index(drop=True); a = a[a["c3_ts_utc"].isin(b["c3_ts_utc"])].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b, check_dtype=False)
    assert "roll" not in json.dumps(l2cfg.to_dict()).lower().replace("series_id", "")   # no roll convention inside detector config


def test_full_run_manifest_if_present(cfg, l2cfg):
    root = cfg.resolve("runs_dir") / "features" / l2cfg.series_id / l2cfg.config_hash[:12]
    if not (root / "feature_manifest.json").exists():
        pytest.skip("full feature run not present")
    m = json.loads((root / "feature_manifest.json").read_text())
    assert m["holdout_accessed"] is False and m["development_range"][1] <= str(cfg["split"]["development_end"])
    assert m["layer2_config_hash"] == l2cfg.config_hash
    w = pd.read_parquet(root / "windows.parquet")
    assert w["trading_date"].max() <= pd.Timestamp(cfg["split"]["development_end"])
