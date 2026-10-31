"""Registry of continuous series available to Layer 2 and the development-only data access.

A SeriesSpec names a Layer 1 continuous series (roll convention + adjustment). Detectors never
reference a roll convention directly; they receive a SeriesData whose `series_id` is stamped on
every feature row. Alternative roll conventions registered in Layer 1 become selectable here
without changing any detector.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..engine import loader
from ..engine.config import Config, load_config


@dataclass(frozen=True)
class SeriesSpec:
    series_id: str
    roll_convention: str
    adjustment: str          # "backadjusted" | "unadjusted"
    layer1_series: str       # name of the Layer 1 series_type partition
    description: str


SERIES_REGISTRY: dict[str, SeriesSpec] = {
    "mnq_volcross_next_session_backadj_v1": SeriesSpec(
        series_id="mnq_volcross_next_session_backadj_v1", roll_convention="lab_volume_crossover_next_session_v1",
        adjustment="backadjusted", layer1_series="backadjusted",
        description="MNQ 1m, lab volume-crossover roll effective next session, additive back-adjustment anchored to latest contract"),
    "mnq_volcross_next_session_unadj_v1": SeriesSpec(
        series_id="mnq_volcross_next_session_unadj_v1", roll_convention="lab_volume_crossover_next_session_v1",
        adjustment="unadjusted", layer1_series="unadjusted",
        description="Same roll convention, raw contract prices (chart verification only)"),
}
DEFAULT_SERIES_ID = "mnq_volcross_next_session_backadj_v1"


@dataclass
class SeriesData:
    spec: SeriesSpec
    bars: pd.DataFrame            # development-period 1m bars (Layer 1 columns)
    rolls: pd.DataFrame           # development-period roll log (effective dates inside the split)
    sessions: pd.DataFrame        # development-period session table

    @property
    def series_id(self) -> str:
        return self.spec.series_id


def register_series(spec: SeriesSpec) -> None:
    if spec.series_id in SERIES_REGISTRY:
        raise ValueError(f"series {spec.series_id} already registered")
    SERIES_REGISTRY[spec.series_id] = spec


def load_series(series_id: str = DEFAULT_SERIES_ID, cfg: Config | None = None,
                start: str | None = None, end: str | None = None) -> SeriesData:
    """Development split only (Layer 1 loader enforces the holdout lock). Optional trading-date bounds
    let tests and truncation checks work on prefixes."""
    cfg = cfg or load_config()
    spec = SERIES_REGISTRY[series_id]
    if spec.roll_convention != cfg["roll"]["convention_name"]:
        raise ValueError(f"series {series_id} expects roll convention {spec.roll_convention}, Layer 1 built {cfg['roll']['convention_name']}")
    bars = loader.load_development(series=spec.layer1_series, cfg=cfg)
    rolls = loader.load_rolls(cfg)
    sessions = loader.load_sessions(cfg)
    if start is not None:
        bars = bars[bars["trading_date"] >= pd.Timestamp(start)]; sessions = sessions[sessions["trading_date"] >= pd.Timestamp(start)]
    if end is not None:
        bars = bars[bars["trading_date"] <= pd.Timestamp(end)]; sessions = sessions[sessions["trading_date"] <= pd.Timestamp(end)]
    return SeriesData(spec=spec, bars=bars.reset_index(drop=True), rolls=rolls.reset_index(drop=True), sessions=sessions.reset_index(drop=True))


def truncate(data: SeriesData, end_ts_utc) -> SeriesData:
    """Prefix of a SeriesData: bars with ts_utc <= end (used by no-lookahead truncation tests)."""
    t = pd.Timestamp(end_ts_utc)
    bars = data.bars[data.bars["ts_utc"] <= t].reset_index(drop=True)
    last_date = bars["trading_date"].max() if len(bars) else None
    sess = data.sessions[data.sessions["trading_date"] <= last_date] if last_date is not None else data.sessions.iloc[0:0]
    return SeriesData(spec=data.spec, bars=bars, rolls=data.rolls, sessions=sess.reset_index(drop=True))
