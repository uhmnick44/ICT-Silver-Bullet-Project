from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ict_lab.engine.config import Config, load_config
from ict_lab.engine.instrument import InstrumentSpec
from ict_lab.engine.sessions import SessionSpec

LAB = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def cfg() -> Config:
    return load_config()


@pytest.fixture(scope="session")
def spec(cfg) -> InstrumentSpec:
    return InstrumentSpec.from_config(cfg)


@pytest.fixture(scope="session")
def sessions(cfg) -> SessionSpec:
    return SessionSpec.from_config(cfg)


def _require_outputs(cfg: Config) -> Path:
    clean = cfg.resolve("clean_dir")
    if not (clean / "MNQ_1m_backadjusted.parquet").exists():
        pytest.skip("pipeline outputs not built; run `python -m ict_lab.engine.pipeline` first")
    return clean


@pytest.fixture(scope="session")
def clean_dir(cfg) -> Path:
    return _require_outputs(cfg)


@pytest.fixture(scope="session")
def unadj(clean_dir) -> pd.DataFrame:
    return pd.read_parquet(clean_dir / "MNQ_1m_unadjusted.parquet")


@pytest.fixture(scope="session")
def adj(clean_dir) -> pd.DataFrame:
    return pd.read_parquet(clean_dir / "MNQ_1m_backadjusted.parquet")


@pytest.fixture(scope="session")
def rolls_csv(clean_dir) -> pd.DataFrame:
    return pd.read_csv(clean_dir / "MNQ_rolls.csv", parse_dates=["crossover_trading_date", "effective_trading_date"])


@pytest.fixture(scope="session")
def session_table(clean_dir) -> pd.DataFrame:
    return pd.read_parquet(clean_dir / "MNQ_sessions.parquet")
