"""Typed Layer 2 configuration with validation of the fixed methodology constraints."""
from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .timeframes import INTRADAY, validate_timeframe

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_L2_CONFIG = LAB_ROOT / "configs" / "layer2_features.toml"

LIQUIDITY_TYPES = ("prev_session", "prev_rth", "prewindow", "swing_15m")   # FIXED universe
FORBIDDEN_LIQUIDITY = ("swing_1m", "swing_5m", "swing_1h", "mss_swing")
VALID_BIAS = ("none", "prev_day_oc", "swing_15m_structure", "swing_1h_structure", "daily_ma20_slope")
LOOKAHEAD_BIAS = ("perfect_window", "perfect_session")      # LOOKAHEAD / INVALID FOR LIVE TRADING


@dataclass(frozen=True)
class ATRConfig:
    period: int = 14
    method: str = "wilder"
    reset_on_data_gap: bool = True


@dataclass(frozen=True)
class FVGConfig:
    timeframes: tuple[str, ...] = ("1m", "5m", "15m")
    min_gap_points: float = 0.0
    min_gap_atr: float = 0.0
    require_complete_candles: bool = True
    mitigation_rule: str = "trade_inside"


@dataclass(frozen=True)
class LiquidityConfig:
    universe: tuple[str, ...] = LIQUIDITY_TYPES
    swing_timeframe: str = "15m"
    swing_left: int = 2
    swing_right: int = 2
    equal_handling: str = "first"
    prewindow_lookback: str = "session_open"
    consumption_rule: str = "sweep_or_no_reversal"
    allow_reuse: bool = False


@dataclass(frozen=True)
class SweepConfig:
    timeframe: str = "1m"
    min_penetration_ticks: int = 1
    max_confirmation_bars: int = 3


@dataclass(frozen=True)
class DisplacementConfig:
    timeframe: str = "1m"
    thresholds: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0)
    atr_reference: str = "prior_candle"
    percentile_lookback: int = 200
    percentile: float = 90.0
    record_min_ratio: float = 1.0


@dataclass(frozen=True)
class MSSConfig:
    timeframe: str = "1m"
    swing_left: int = 2
    swing_right: int = 2
    equal_handling: str = "first"
    confirmation: str = "close"
    max_bars_after_sweep: int = 60


@dataclass(frozen=True)
class BiasConfig:
    detector: str = "none"
    swing_left: int = 2
    swing_right: int = 2
    ma_period: int = 20
    allow_lookahead_diagnostic: bool = False


@dataclass(frozen=True)
class Layer2Config:
    series_id: str
    atr: ATRConfig = ATRConfig()
    fvg: FVGConfig = FVGConfig()
    liquidity: LiquidityConfig = LiquidityConfig()
    sweep: SweepConfig = SweepConfig()
    displacement: DisplacementConfig = DisplacementConfig()
    mss: MSSConfig = MSSConfig()
    bias: BiasConfig = BiasConfig()
    windows: tuple[str, ...] = ("sb_london", "sb_ny_am", "sb_ny_pm")

    def validate(self) -> "Layer2Config":
        for tf in self.fvg.timeframes:
            if tf not in ("1m", "5m", "15m"):
                raise ValueError(f"FVG timeframe {tf} not supported (1m/5m/15m)")
        for t in self.liquidity.universe:
            if t in FORBIDDEN_LIQUIDITY or t not in LIQUIDITY_TYPES:
                raise ValueError(f"liquidity type {t!r} is not in the approved universe {LIQUIDITY_TYPES}")
        if self.liquidity.swing_timeframe != "15m":
            raise ValueError("liquidity swing_timeframe must be '15m'; other swing timeframes are not permitted as liquidity")
        if self.liquidity.swing_left < 1 or self.liquidity.swing_right < 1:
            raise ValueError("swing_left/swing_right must be >= 1")
        if self.liquidity.equal_handling not in ("first", "last", "strict"):
            raise ValueError("equal_handling must be first|last|strict")
        if self.liquidity.prewindow_lookback != "session_open" and not str(self.liquidity.prewindow_lookback).endswith("m"):
            raise ValueError("prewindow_lookback must be 'session_open' or '<N>m'")
        if self.sweep.timeframe not in ("1m", "5m"):
            raise ValueError("sweep timeframe must be 1m or 5m")
        if self.sweep.min_penetration_ticks < 0 or self.sweep.max_confirmation_bars < 0:
            raise ValueError("sweep parameters must be non-negative")
        if self.mss.timeframe not in ("1m", "5m", "15m") or self.mss.confirmation not in ("close", "wick"):
            raise ValueError("mss timeframe must be 1m/5m/15m and confirmation close|wick")
        validate_timeframe(self.displacement.timeframe)
        if self.displacement.atr_reference not in ("prior_candle", "same_candle"):
            raise ValueError("displacement.atr_reference must be prior_candle|same_candle")
        if self.atr.method not in ("wilder", "sma"):
            raise ValueError("atr.method must be wilder|sma")
        if self.bias.detector in LOOKAHEAD_BIAS and not self.bias.allow_lookahead_diagnostic:
            raise ValueError(f"bias detector {self.bias.detector} is LOOKAHEAD and requires allow_lookahead_diagnostic=true (diagnostics only)")
        if self.bias.detector not in VALID_BIAS + LOOKAHEAD_BIAS:
            raise ValueError(f"unknown bias detector {self.bias.detector}")
        return self

    @property
    def config_hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, default=str).encode()).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)


def _tup(x):
    return tuple(x) if isinstance(x, list) else x


def load_layer2_config(path: Path | str | None = None, **overrides) -> Layer2Config:
    p = Path(path) if path else DEFAULT_L2_CONFIG
    with open(p, "rb") as fh:
        raw = tomllib.load(fh)
    for k, v in overrides.items():        # overrides: section -> dict
        raw.setdefault(k, {}).update(v)
    cfg = Layer2Config(
        series_id=raw["series"]["series_id"],
        atr=ATRConfig(**raw.get("atr", {})),
        fvg=FVGConfig(**{k: _tup(v) for k, v in raw.get("fvg", {}).items()}),
        liquidity=LiquidityConfig(**{k: _tup(v) for k, v in raw.get("liquidity", {}).items()}),
        sweep=SweepConfig(**raw.get("sweep", {})),
        displacement=DisplacementConfig(**{k: _tup(v) for k, v in raw.get("displacement", {}).items()}),
        mss=MSSConfig(**raw.get("mss", {})),
        bias=BiasConfig(**raw.get("bias", {})),
        windows=tuple(raw.get("windows", {}).get("names", ("sb_london", "sb_ny_am", "sb_ny_pm"))),
    )
    return cfg.validate()
