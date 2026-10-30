# Raw Databento files

Place the original Databento batch-download zips here (they are git-ignored).
The pipeline extracts them into `_extracted/<job_id>/` (also git-ignored), makes
the extracted copies read-only, and never modifies or rewrites either.

Expected for this project (sha256 recorded in `data/clean/manifest.json`):

- `GLBX-20261021-SUW6SDRRS7` — GLBX.MDP3 ohlcv-1m MNQ.FUT, 2022-10-01 → 2025-10-02 UTC
- `GLBX-20261021-5QBR9J5GST` — GLBX.MDP3 ohlcv-1m MNQ.FUT, 2025-10-01 → 2026-10-21 UTC
