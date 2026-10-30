"""Holdout isolation: the default loader cannot see holdout rows; access needs authorization + log."""
import inspect
import json

import pandas as pd
import pytest

from ict_lab.engine import loader
from ict_lab.engine.config import Config


@pytest.fixture
def tmp_cfg(cfg, tmp_path) -> Config:
    raw = json.loads(json.dumps(cfg.raw, default=str))
    raw["paths"]["runs_dir"] = str(tmp_path / "runs")
    return Config(raw=raw, path=cfg.path)


def test_default_loader_is_development_only(cfg, clean_dir):
    df = loader.load_development(columns=["ts_utc", "trading_date", "close"], cfg=cfg)
    assert len(df) > 0
    assert df["trading_date"].min() >= pd.Timestamp(cfg["split"]["development_start"])
    assert df["trading_date"].max() <= pd.Timestamp(cfg["split"]["development_end"])
    assert df["trading_date"].max() == pd.Timestamp("2024-10-18")
    assert (df["split"] == "development").all()
    assert "scope" not in inspect.signature(loader.load_bars).parameters


def test_holdout_requires_authorization(tmp_cfg, clean_dir):
    with pytest.raises(loader.HoldoutAccessError):
        loader.load_holdout(None, cfg=tmp_cfg)  # type: ignore[arg-type]
    bad = loader.HoldoutAuthorization("tester", "unit test", "wrong phrase")
    with pytest.raises(loader.HoldoutAccessError):
        loader.load_holdout(bad, cfg=tmp_cfg)
    assert not (tmp_cfg.resolve("runs_dir") / "holdout_access.log").exists()


def test_holdout_access_is_logged_and_bounded(tmp_cfg, clean_dir):
    auth = loader.HoldoutAuthorization("tester", "unit test of the access path", loader.HOLDOUT_CONFIRM_PHRASE)
    df = loader.load_holdout(auth, columns=["ts_utc", "trading_date"], cfg=tmp_cfg)
    assert df["trading_date"].min() == pd.Timestamp("2024-10-21") and df["trading_date"].max() == pd.Timestamp("2026-10-20")
    assert (df["split"] == "holdout").all()
    log = (tmp_cfg.resolve("runs_dir") / "holdout_access.log").read_text().strip().splitlines()
    assert len(log) == 1 and json.loads(log[0])["authorized_by"] == "tester"


def test_dev_and_holdout_are_disjoint_and_exclude_truncated_session(cfg, tmp_cfg, clean_dir, unadj):
    dev = loader.load_development(columns=["ts_utc"], cfg=cfg)
    hold = loader.load_holdout(loader.HoldoutAuthorization("t", "r", loader.HOLDOUT_CONFIRM_PHRASE), columns=["ts_utc"], cfg=tmp_cfg)
    assert not set(dev["ts_utc"]).intersection(set(hold["ts_utc"]))
    assert len(dev) + len(hold) == (unadj["split"] != "excluded").sum()
    assert not (hold["trading_date"] == pd.Timestamp("2026-10-21")).any()


def test_rolls_and_sessions_default_to_development(cfg, clean_dir):
    rl = loader.load_rolls(cfg)
    assert rl["effective_trading_date"].max() <= pd.Timestamp(cfg["split"]["development_end"])
    assert len(rl) == 8
    st = loader.load_sessions(cfg)
    assert (st["split"] == "development").all()
