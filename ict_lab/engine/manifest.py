"""Reproducibility manifest: source hashes, config hash, software versions, output hashes."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow


def content_hash(df: pd.DataFrame, columns: list[str] | None = None) -> str:
    """Order-sensitive hash of the frame's values (independent of Parquet encoding details)."""
    d = df if columns is None else df[columns]
    d = d.reset_index(drop=True)
    cols = []
    for c in d.columns:
        s = d[c]
        if isinstance(s.dtype, pd.DatetimeTZDtype):
            s = s.dt.tz_convert("UTC").astype("datetime64[ns, UTC]").astype("int64")
        elif pd.api.types.is_datetime64_any_dtype(s.dtype):
            s = s.astype("datetime64[ns]").astype("int64")
        elif pd.api.types.is_bool_dtype(s.dtype):
            s = s.astype("int8")
        elif pd.api.types.is_float_dtype(s.dtype):
            s = s.astype("float64")
        elif pd.api.types.is_integer_dtype(s.dtype):
            s = s.astype("int64")
        else:
            s = s.astype(str).astype(object)
        cols.append(s.rename(c))
    h = pd.util.hash_pandas_object(pd.concat(cols, axis=1), index=False).to_numpy()
    return hashlib.sha256(h.tobytes() + str(list(d.columns)).encode()).hexdigest()


def software_versions() -> dict:
    import databento
    return {"python": sys.version.split()[0], "platform": platform.platform(), "pandas": pd.__version__,
            "numpy": np.__version__, "pyarrow": pyarrow.__version__, "databento": databento.__version__}


def write_manifest(path: Path, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
