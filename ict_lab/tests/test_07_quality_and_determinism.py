"""Valid OHLC on both series, anomaly detection, deterministic rebuild."""
import json

import pytest

from ict_lab.engine import pipeline
from ict_lab.engine.manifest import content_hash
from ict_lab.engine.quality import bar_checks


def test_valid_ohlc_both_series(unadj, adj, spec):
    for df in (unadj, adj):
        c = bar_checks(df, spec)
        assert c["invalid_ohlc_bars"] == 0 and c["duplicate_timestamps"] == 0 and c["off_tick_bars"] == 0
        assert c["zero_volume_bars"] == 0 and c["nonpositive_price_bars"] == 0 and c["nan_fields"] == 0
        assert c["minute_aligned"] and c["non_monotonic_timestamps"] == 0


def test_known_anomalies_detected(clean_dir):
    q = json.loads((clean_dir / "reports" / "data_quality_report.json").read_text())
    ids = {a["anomaly_id"]: a for a in q["known_anomalies"]}
    assert set(ids) == {"thanksgiving_2025_overnight_hole", "2025-04-02_reopen_missing_1800_1801", "2022-12-13_cpi_missing_0831", "2025-04-02_missing_1631"}
    assert all(a["detected"] and a["matches_expectation"] for a in ids.values())
    assert ids["thanksgiving_2025_overnight_hole"]["observed_missing_minutes"] == 645


def test_manifest_records_provenance(clean_dir):
    m = json.loads((clean_dir / "manifest.json").read_text())
    assert len(m["source_hashes"]) == 66 and len(m["zip_hashes"]) == 2
    assert m["config_hash"] and m["software"]["pandas"] and m["outputs"]["MNQ_1m_backadjusted.parquet"]["content_hash"]
    assert m["rolls"] == 16 and m["trading_sessions"] == 1048


@pytest.mark.slow
def test_rebuild_is_deterministic(cfg, clean_dir, unadj, adj):
    before = json.loads((clean_dir / "manifest.json").read_text())["outputs"]
    pipeline.run(cfg, force=True, log=lambda *_: None)
    after = json.loads((clean_dir / "manifest.json").read_text())["outputs"]
    for k in ("MNQ_1m_unadjusted.parquet", "MNQ_1m_backadjusted.parquet"):
        assert before[k]["content_hash"] == after[k]["content_hash"]
        assert before[k]["sha256"] == after[k]["sha256"]
    assert before["MNQ_rolls.csv"]["sha256"] == after["MNQ_rolls.csv"]["sha256"]
    assert content_hash(unadj) == before["MNQ_1m_unadjusted.parquet"]["content_hash"]
