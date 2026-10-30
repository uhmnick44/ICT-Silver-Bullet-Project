"""Read the original Databento batch zips without modifying them, decode DBN -> per-contract
Parquet cache keyed by the source file hash, and expose sidecar information (condition.json).
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from databento import DBNStore

from .instrument import InstrumentSpec

BAR_COLUMNS = ["ts_utc", "symbol", "instrument_id", "open", "high", "low", "close", "volume"]


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


@dataclass
class SourceFile:
    job_id: str
    name: str
    path: Path
    sha256: str
    symbol: str
    is_outright: bool
    manifest_sha256: str | None = None
    manifest_ok: bool | None = None


@dataclass
class RawInventory:
    zips: dict[str, str]                      # zip name -> sha256
    jobs: dict[str, dict] = field(default_factory=dict)      # job_id -> metadata.json query
    files: list[SourceFile] = field(default_factory=list)
    degraded_dates: dict[str, list[str]] = field(default_factory=dict)  # job_id -> ['YYYY-MM-DD', ...]
    condition: dict[str, dict[str, str]] = field(default_factory=dict)  # job_id -> {date: condition}


def _make_readonly(root: Path) -> None:
    for p in root.rglob("*"):
        try:
            if p.is_dir():
                os.chmod(p, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            else:
                os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        except PermissionError:
            pass


def extract_zips(raw_dir: Path, spec: InstrumentSpec) -> RawInventory:
    """Extract every *.zip in raw_dir into raw_dir/_extracted/<job_id>/ (once), read-only.
    Returns an inventory with hashes verified against each job's manifest.json."""
    raw_dir = Path(raw_dir)
    zips = sorted(raw_dir.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"no Databento zips found in {raw_dir}")
    inv = RawInventory(zips={})
    ext_root = raw_dir / "_extracted"
    for z in zips:
        inv.zips[z.name] = sha256_file(z)
        with zipfile.ZipFile(z) as zf:
            meta = json.loads(zf.read("metadata.json"))
            job_id = meta["job_id"]
            dest = ext_root / job_id
            if not (dest / "metadata.json").exists():
                dest.mkdir(parents=True, exist_ok=True)
                zf.extractall(dest)
                _make_readonly(dest)
        inv.jobs[job_id] = {"zip": z.name, "query": meta["query"], "customizations": meta["customizations"]}
        manifest = {f["filename"]: f["hash"].split(":", 1)[1] for f in json.load(open(dest / "manifest.json"))["files"]}
        cond = json.load(open(dest / "condition.json"))
        inv.condition[job_id] = {c["date"]: c["condition"] for c in cond}
        inv.degraded_dates[job_id] = sorted(c["date"] for c in cond if c["condition"] != "available")
        for f in sorted(dest.glob("*.dbn.zst")):
            symbol = f.name.split(".")[-3]
            h = sha256_file(f)
            inv.files.append(SourceFile(job_id=job_id, name=f.name, path=f, sha256=h, symbol=symbol,
                                        is_outright=spec.is_outright(symbol),
                                        manifest_sha256=manifest.get(f.name),
                                        manifest_ok=(manifest.get(f.name) == h)))
    bad = [f.name for f in inv.files if f.manifest_ok is False]
    if bad:
        raise RuntimeError(f"source files fail Databento manifest sha256 check: {bad}")
    return inv


def decode_dbn(path: Path) -> pd.DataFrame:
    """Decode one ohlcv-1m DBN file to a plain frame. Prices are already float64 index points;
    ts_event (bar open) becomes tz-aware UTC `ts_utc`."""
    st = DBNStore.from_file(path)
    if str(st.schema) != "ohlcv-1m":
        raise ValueError(f"{path.name}: schema {st.schema} is not ohlcv-1m")
    df = st.to_df(price_type="float", pretty_ts=True, map_symbols=True)
    df = df.reset_index().rename(columns={"ts_event": "ts_utc"})
    df["ts_utc"] = pd.DatetimeIndex(df["ts_utc"]).tz_convert("UTC")
    df = df[["ts_utc", "symbol", "instrument_id", "open", "high", "low", "close", "volume"]]
    df["symbol"] = df["symbol"].astype(str)
    df["instrument_id"] = df["instrument_id"].astype("int64")
    df["volume"] = df["volume"].astype("int64")
    return df.sort_values("ts_utc", kind="mergesort").reset_index(drop=True)


def load_contract_bars(inv: RawInventory, cache_dir: Path, spec: InstrumentSpec) -> pd.DataFrame:
    """All outright bars from all jobs, decoded once per (file hash) and cached as Parquet.
    Rows duplicated across overlapping jobs are dropped after verifying they are identical."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for sf in inv.files:
        if not sf.is_outright:
            continue
        cp = cache_dir / f"{sf.symbol}.{sf.job_id}.{sf.sha256[:16]}.parquet"
        if cp.exists():
            df = pd.read_parquet(cp)
        else:
            df = decode_dbn(sf.path)
            df.to_parquet(cp, index=False)
        df = df.assign(job_id=sf.job_id, source_file=sf.name)
        parts.append(df)
    allbars = pd.concat(parts, ignore_index=True)
    allbars = allbars.sort_values(["symbol", "ts_utc", "job_id"], kind="mergesort").reset_index(drop=True)
    dup = allbars.duplicated(["symbol", "ts_utc"], keep=False)
    if dup.any():
        d = allbars[dup]
        chk = d.groupby(["symbol", "ts_utc"])[["open", "high", "low", "close", "volume"]].nunique()
        if (chk > 1).any().any():
            raise RuntimeError("overlapping jobs disagree on OHLCV for the same bar; refusing to continue")
    deduped = allbars.drop_duplicates(["symbol", "ts_utc"], keep="first").reset_index(drop=True)
    deduped.attrs["rows_before_dedup"] = int(len(allbars))
    deduped.attrs["cross_job_duplicates_dropped"] = int(len(allbars) - len(deduped))
    return deduped
