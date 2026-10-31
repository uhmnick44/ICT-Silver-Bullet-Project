"""Typed Layer 3 execution configuration with validation of the fixed methodology constraints."""
from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..features.config import LIQUIDITY_TYPES, LOOKAHEAD_BIAS, VALID_BIAS

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_L3_CONFIG = LAB_ROOT / "configs" / "layer3_execution.toml"
STOP_TYPES = ("displacement_swing", "fvg_distal", "fixed_points")
TARGET_TYPES = ("fixed_r", "opposing_liquidity", "time_only")
EXIT_POLICIES = ("window_end", "rth_end", "hold")
ENTRY_LOCATIONS = ("proximal", "midpoint", "distal")
# Stop types whose defining rule has not been approved. Selecting one fails validation with the reason.
STOP_TYPES_AWAITING_DEFINITION = {
    "displacement_swing": "the 'swing associated with displacement' is not defined by the Layer 2 feature metadata; "
                          "a swing-selection rule must be approved before this stop can be used (see docs/execution_assumptions.md §Open items)",
}


def _t(x):
    return tuple(x) if isinstance(x, list) else x


@dataclass(frozen=True)
class SignalConfig:
    windows: tuple[str, ...] = ("sb_london", "sb_ny_am", "sb_ny_pm")
    liquidity_types: tuple[str, ...] = LIQUIDITY_TYPES
    fvg_timeframe: str = "5m"
    min_fvg_points: float = 0.0
    min_fvg_atr: float = 0.0
    require_mss: bool = False
    require_displacement: bool = False
    displacement_threshold: float = 1.5
    bias_detector: str = "none"
    require_bias: bool = False
    require_penetration_in_window: bool = False
    max_trades_per_window: int = 1


@dataclass(frozen=True)
class EntryConfig:
    location: str = "midpoint"
    fill_rule: str = "trade_through"
    marketable_at_activation: str = "fill_at_limit"
    expiry: str = "window_end"
    round_midpoint: str = "away_from_proximal"


@dataclass(frozen=True)
class StopConfig:
    type: str = "fvg_distal"
    buffer_ticks: int = 1
    fixed_points: float = 20.0


@dataclass(frozen=True)
class TargetConfig:
    type: str = "fixed_r"
    r_multiple: float = 2.0
    opposing_liquidity_types: tuple[str, ...] = LIQUIDITY_TYPES
    fallback: str = "fixed_r"
    fallback_r_multiple: float = 2.0
    fill_rule: str = "trade_through"


@dataclass(frozen=True)
class ExitConfig:
    policy: str = "rth_end"
    same_bar_rule: str = "stop_first"
    time_exit_price: str = "next_bar_open"


@dataclass(frozen=True)
class CostConfig:
    commission_per_side: float = 0.39
    exchange_fee_per_side: float = 0.36
    clearing_fee_per_side: float = 0.19
    entry_slippage_ticks: int = 0
    target_slippage_ticks: int = 0
    stop_slippage_ticks: int = 1
    time_exit_slippage_ticks: int = 1

    @property
    def per_side(self) -> float:
        return self.commission_per_side + self.exchange_fee_per_side + self.clearing_fee_per_side


@dataclass(frozen=True)
class SizingConfig:
    contracts: int = 1


@dataclass(frozen=True)
class RollConfig:
    policy: str = "flag_and_exclude"


@dataclass(frozen=True)
class Layer3Config:
    series_id: str
    layer2_config: str = "configs/layer2_features.toml"
    signal: SignalConfig = SignalConfig()
    entry: EntryConfig = EntryConfig()
    stop: StopConfig = StopConfig()
    target: TargetConfig = TargetConfig()
    exit: ExitConfig = ExitConfig()
    costs: CostConfig = CostConfig()
    sizing: SizingConfig = SizingConfig()
    roll: RollConfig = RollConfig()

    def validate(self) -> "Layer3Config":
        s = self.signal
        for t in s.liquidity_types:
            if t not in LIQUIDITY_TYPES:
                raise ValueError(f"liquidity type {t!r} is not in the approved universe {LIQUIDITY_TYPES}")
        for t in self.target.opposing_liquidity_types:
            if t not in LIQUIDITY_TYPES:
                raise ValueError(f"opposing liquidity type {t!r} is not in the approved universe")
        if s.fvg_timeframe not in ("1m", "5m", "15m"):
            raise ValueError("fvg_timeframe must be 1m|5m|15m")
        if s.bias_detector in LOOKAHEAD_BIAS:
            raise ValueError(f"{s.bias_detector} is a LOOKAHEAD diagnostic and cannot drive signals")
        if s.bias_detector not in VALID_BIAS:
            raise ValueError(f"unknown bias detector {s.bias_detector}")
        if s.max_trades_per_window != 1:
            raise ValueError("Layer 3 supports exactly one trade per window (re-entries belong to Layer 4)")
        if self.entry.location not in ENTRY_LOCATIONS or self.entry.fill_rule != "trade_through":
            raise ValueError("entry.location must be proximal|midpoint|distal and fill_rule must be trade_through")
        if self.entry.marketable_at_activation not in ("fill_at_limit", "cancel"):
            raise ValueError("entry.marketable_at_activation must be fill_at_limit|cancel")
        if self.stop.type not in STOP_TYPES:
            raise ValueError(f"stop.type must be one of {STOP_TYPES}")
        if self.stop.type in STOP_TYPES_AWAITING_DEFINITION:
            raise ValueError(f"stop.type={self.stop.type!r} is not usable: {STOP_TYPES_AWAITING_DEFINITION[self.stop.type]}")
        if self.stop.buffer_ticks < 0 or (self.stop.type == "fixed_points" and self.stop.fixed_points <= 0):
            raise ValueError("stop buffer must be >= 0 and fixed_points > 0")
        if self.target.type not in TARGET_TYPES or self.target.r_multiple <= 0 or self.target.fallback_r_multiple <= 0:
            raise ValueError("target configuration invalid")
        if self.target.fill_rule not in ("trade_through", "touch"):
            raise ValueError("target.fill_rule must be trade_through|touch")
        if self.exit.policy not in EXIT_POLICIES or self.exit.same_bar_rule != "stop_first" or self.exit.time_exit_price != "next_bar_open":
            raise ValueError("exit configuration invalid (same_bar_rule must be stop_first; time_exit_price next_bar_open)")
        if self.target.type == "time_only" and self.exit.policy == "hold":
            raise ValueError("time_only target requires a time-based exit policy")
        c = self.costs
        if min(c.entry_slippage_ticks, c.target_slippage_ticks, c.stop_slippage_ticks, c.time_exit_slippage_ticks) < 0:
            raise ValueError("slippage ticks must be >= 0 (adverse only)")
        if self.sizing.contracts < 1:
            raise ValueError("contracts must be >= 1")
        if self.roll.policy not in ("flag_and_exclude", "flag_only"):
            raise ValueError("roll.policy must be flag_and_exclude|flag_only")
        return self

    @property
    def config_hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, default=str).encode()).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)


def load_layer3_config(path: Path | str | None = None, **overrides) -> Layer3Config:
    p = Path(path) if path else DEFAULT_L3_CONFIG
    with open(p, "rb") as fh:
        raw = tomllib.load(fh)
    for k, v in overrides.items():
        raw.setdefault(k, {}).update(v)
    cfg = Layer3Config(
        series_id=raw["series"]["series_id"], layer2_config=raw["series"].get("layer2_config", "configs/layer2_features.toml"),
        signal=SignalConfig(**{k: _t(v) for k, v in raw.get("signal", {}).items()}),
        entry=EntryConfig(**raw.get("entry", {})), stop=StopConfig(**raw.get("stop", {})),
        target=TargetConfig(**{k: _t(v) for k, v in raw.get("target", {}).items()}),
        exit=ExitConfig(**raw.get("exit", {})), costs=CostConfig(**raw.get("costs", {})),
        sizing=SizingConfig(**raw.get("sizing", {})), roll=RollConfig(**raw.get("roll", {})))
    return cfg.validate()
