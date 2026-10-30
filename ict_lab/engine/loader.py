"""Research data access with holdout protection.

Default loaders expose ONLY the development split. Holdout rows can be obtained solely through
`load_holdout`, which requires an explicit HoldoutAuthorization whose `confirm` string must match
HOLDOUT_CONFIRM_PHRASE exactly; every holdout access is appended to runs/holdout_access.log.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from .config import Config, load_config

HOLDOUT_CONFIRM_PHRASE = "I AM RUNNING THE FINAL HOLDOUT VALIDATION AND UNDERSTAND IT CAN ONLY BE DONE ONCE"
DEVELOPMENT = "development"
HOLDOUT = "holdout"


class HoldoutAccessError(PermissionError):
    pass


@dataclass(frozen=True)
class HoldoutAuthorization:
    authorized_by: str
    reason: str
    confirm: str

    def validate(self) -> None:
        if not self.authorized_by.strip() or not self.reason.strip():
            raise HoldoutAccessError("holdout authorization needs authorized_by and reason")
        if self.confirm != HOLDOUT_CONFIRM_PHRASE:
            raise HoldoutAccessError("holdout authorization confirm phrase does not match HOLDOUT_CONFIRM_PHRASE")


def _partition_root(cfg: Config) -> Path:
    return cfg.resolve("clean_dir") / "partitioned"


def _split_bounds(cfg: Config, split: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    s = cfg["split"]
    if split == DEVELOPMENT:
        return pd.Timestamp(s["development_start"]), pd.Timestamp(s["development_end"])
    if split == HOLDOUT:
        return pd.Timestamp(s["holdout_start"]), pd.Timestamp(s["holdout_end"])
    raise ValueError(split)


def _read(cfg: Config, series: str, split: str, columns: list[str] | None, symbol: str) -> pd.DataFrame:
    root = _partition_root(cfg)
    lo, hi = _split_bounds(cfg, split)
    part = ds.partitioning(pa.schema([("symbol_root", pa.string()), ("series_type", pa.string()), ("year", pa.int32())]), flavor="hive")
    dataset = ds.dataset(str(root), format="parquet", partitioning=part)
    lo_s, hi_s = pa.scalar(lo.to_pydatetime(), type=pa.timestamp("ms")), pa.scalar(hi.to_pydatetime(), type=pa.timestamp("ms"))
    filt = (ds.field("symbol_root") == symbol) & (ds.field("series_type") == series) & \
           (ds.field("year") >= lo.year) & (ds.field("year") <= hi.year) & \
           (ds.field("trading_date") >= lo_s) & (ds.field("trading_date") <= hi_s) & \
           (ds.field("split") == split)
    cols = None if columns is None else list(dict.fromkeys(list(columns) + ["trading_date", "split"]))
    tbl = dataset.to_table(filter=filt, columns=cols)
    df = tbl.to_pandas()
    df = df.drop(columns=[c for c in ("symbol_root", "series_type", "year") if c in df.columns])
    if "ts_utc" in df.columns:
        df = df.sort_values("ts_utc", kind="mergesort").reset_index(drop=True)
    if len(df) and (df["split"] != split).any():
        raise RuntimeError("loader returned rows outside the requested split")
    if len(df) and ((df["trading_date"] < lo) | (df["trading_date"] > hi)).any():
        raise RuntimeError("loader returned rows outside the split date bounds")
    return df


def load_development(series: str = "backadjusted", columns: list[str] | None = None,
                     cfg: Config | None = None, symbol: str = "MNQ") -> pd.DataFrame:
    """Default research loader: development-period bars only."""
    cfg = cfg or load_config()
    return _read(cfg, series, DEVELOPMENT, columns, symbol)


def load_bars(series: str = "backadjusted", columns: list[str] | None = None, cfg: Config | None = None,
              symbol: str = "MNQ") -> pd.DataFrame:
    """Alias of load_development; there is no 'scope' argument on purpose."""
    return load_development(series, columns, cfg, symbol)


def load_holdout(authorization: HoldoutAuthorization, series: str = "backadjusted",
                 columns: list[str] | None = None, cfg: Config | None = None, symbol: str = "MNQ") -> pd.DataFrame:
    """Holdout bars. Requires a validated authorization and writes an audit log entry."""
    if not isinstance(authorization, HoldoutAuthorization):
        raise HoldoutAccessError("load_holdout requires a HoldoutAuthorization")
    authorization.validate()
    cfg = cfg or load_config()
    runs_dir = cfg.resolve("runs_dir"); runs_dir.mkdir(parents=True, exist_ok=True)
    entry = {"ts_utc": datetime.now(timezone.utc).isoformat(), "authorized_by": authorization.authorized_by,
             "reason": authorization.reason, "series": series, "columns": columns, "config_hash": cfg.config_hash}
    with open(runs_dir / "holdout_access.log", "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return _read(cfg, series, HOLDOUT, columns, symbol)


def load_rolls(cfg: Config | None = None, authorization: HoldoutAuthorization | None = None) -> pd.DataFrame:
    """Roll log restricted to rolls whose effective date is in the development period, unless a
    valid holdout authorization is supplied (then the full log is returned and the access logged)."""
    cfg = cfg or load_config()
    rl = pd.read_csv(cfg.resolve("clean_dir") / "MNQ_rolls.csv", parse_dates=["crossover_trading_date", "effective_trading_date"])
    lo, hi = _split_bounds(cfg, DEVELOPMENT)
    if authorization is None:
        return rl[(rl["effective_trading_date"] >= lo) & (rl["effective_trading_date"] <= hi)].reset_index(drop=True)
    authorization.validate()
    runs_dir = cfg.resolve("runs_dir"); runs_dir.mkdir(parents=True, exist_ok=True)
    with open(runs_dir / "holdout_access.log", "a") as fh:
        fh.write(json.dumps({"ts_utc": datetime.now(timezone.utc).isoformat(), "authorized_by": authorization.authorized_by,
                             "reason": authorization.reason, "series": "rolls", "config_hash": cfg.config_hash}) + "\n")
    return rl


def load_sessions(cfg: Config | None = None, authorization: HoldoutAuthorization | None = None) -> pd.DataFrame:
    """Session table (development only by default)."""
    cfg = cfg or load_config()
    st = pd.read_parquet(cfg.resolve("clean_dir") / "MNQ_sessions.parquet")
    if authorization is None:
        return st[st["split"] == DEVELOPMENT].reset_index(drop=True)
    authorization.validate()
    return st
