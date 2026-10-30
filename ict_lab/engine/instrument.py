"""Instrument specification and tick-grid arithmetic (MNQ only; nothing is hardcoded for NQ/ES)."""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

MONTH_CODES = {"H": 3, "M": 6, "U": 9, "Z": 12}


@dataclass(frozen=True)
class InstrumentSpec:
    root: str
    tick_size: float
    tick_value: float
    point_value: float
    outright_symbol_regex: str

    @classmethod
    def from_config(cls, cfg) -> "InstrumentSpec":
        i = cfg["instrument"]
        return cls(root=i["root"], tick_size=float(i["tick_size"]), tick_value=float(i["tick_value"]),
                   point_value=float(i["point_value"]), outright_symbol_regex=i["outright_symbol_regex"])

    def is_outright(self, symbol: str) -> bool:
        return re.match(self.outright_symbol_regex, symbol) is not None

    def points_to_ticks(self, points: float | np.ndarray | pd.Series):
        return points / self.tick_size

    def ticks_to_points(self, ticks: float | np.ndarray | pd.Series):
        return ticks * self.tick_size

    def points_to_usd(self, points, contracts: int = 1):
        return points * self.point_value * contracts

    def on_tick_grid(self, prices, atol: float = 1e-9) -> np.ndarray:
        """Element-wise: is each price an integer multiple of tick_size?"""
        q = np.asarray(prices, dtype="float64") / self.tick_size
        return np.abs(q - np.round(q)) <= atol

    def is_tick_multiple(self, value: float, atol: float = 1e-9) -> bool:
        return bool(self.on_tick_grid(np.array([value]), atol)[0])


def contract_sort_key(symbol: str, root: str = "MNQ") -> tuple[int, int]:
    """(year, month) for an outright code like MNQH6 / MNQZ24. Two-digit years are assumed 20xx;
    one-digit years map to the 2020s, which covers every contract in the audited files."""
    body = symbol[len(root):]
    m = re.fullmatch(r"([HMUZ])(\d{1,2})", body)
    if not m:
        raise ValueError(f"not an outright quarterly symbol: {symbol}")
    month = MONTH_CODES[m.group(1)]
    y = m.group(2)
    year = 2000 + int(y) if len(y) == 2 else 2020 + int(y)
    return year, month


def expiry_order(symbols: list[str], root: str = "MNQ") -> list[str]:
    return sorted(symbols, key=lambda s: contract_sort_key(s, root))
