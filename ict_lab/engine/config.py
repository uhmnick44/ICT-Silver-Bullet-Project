"""Configuration loading and hashing."""
from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = LAB_ROOT / "configs" / "layer1_data.toml"


@dataclass(frozen=True)
class Config:
    raw: dict[str, Any]
    path: Path

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    @property
    def lab_root(self) -> Path:
        return LAB_ROOT

    def resolve(self, key: str) -> Path:
        """Resolve a [paths] entry relative to the lab root."""
        return (LAB_ROOT / self.raw["paths"][key]).resolve()

    @property
    def config_hash(self) -> str:
        return hash_config(self.raw)


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def hash_config(raw: dict[str, Any]) -> str:
    canon = json.dumps(_jsonable(raw), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def load_config(path: Path | str | None = None) -> Config:
    p = Path(path) if path else DEFAULT_CONFIG
    with open(p, "rb") as fh:
        raw = tomllib.load(fh)
    return Config(raw=raw, path=p.resolve())
