# ICT Quantitative Research Laboratory — Layer 1: Data Infrastructure (MNQ)

Independent replication of an ICT Silver Bullet quantitative backtesting *methodology* on
Micro E-mini Nasdaq-100 futures (MNQ). This layer builds the validated 1-minute datasets that
every later layer (feature detection, execution simulation, sweeps, statistics, holdout
validation) consumes. **No strategy logic lives here.**

## Layout

```
ict_lab/
├── configs/layer1_data.toml     # every pipeline parameter; hashed into the manifest
├── data/raw/                    # original Databento zips (read-only, git-ignored)
├── data/clean/                  # outputs (large files git-ignored; reports + manifest committed)
│   ├── MNQ_1m_unadjusted.parquet
│   ├── MNQ_1m_backadjusted.parquet
│   ├── MNQ_rolls.csv
│   ├── MNQ_sessions.parquet     # one row per CME trading date (status, eligibility, split)
│   ├── MNQ_daily_contract_volume.csv / MNQ_active_contract_by_date.csv
│   ├── partitioned/symbol_root=MNQ/series_type=<unadjusted|backadjusted>/year=<YYYY>/part-0.parquet
│   ├── contracts/               # per-contract decode cache keyed by source-file sha256
│   ├── manifest.json            # source/config/output hashes + software versions
│   └── reports/                 # contract_roll_report.md, data_quality_report.md/json,
│                                #   session_coverage_report.md/csv, gaps.csv, discontinuities.csv
├── engine/                      # config, instrument, sessions, ingest, rolls, continuous, quality, pipeline, loader, manifest
├── analysis/roll_chart.py       # chart verification around rolls;  analysis/layer1_summary.py
├── features/                    # Layer 2 (empty)
├── runs/                        # pipeline run logs, holdout_access.log, roll_charts/
└── tests/                       # pytest suite (50 tests)
```

## Reproduce

```bash
pip install pandas numpy pyarrow databento pytest matplotlib tabulate
# 1. put the two Databento batch zips in ict_lab/data/raw/
# 2. from the repository root:
python -m ict_lab.engine.pipeline            # ~35 s with the decode cache, ~2 min cold
python -m pytest ict_lab/tests               # 50 tests incl. a forced deterministic rebuild
python -m ict_lab.analysis.roll_chart --rolls 1,8,13,16   # PNGs in ict_lab/runs/roll_charts/
python -m ict_lab.analysis.layer1_summary "<pytest summary>"
```

The pipeline is idempotent: if `manifest.json` already matches the config hash and the source
hashes, it exits without rewriting (use `--force` to rebuild). Source files are verified against
Databento's own `manifest.json` sha256 values before anything is decoded.

## What the pipeline does

1. **Ingest** — extracts the zips once into `data/raw/_extracted/<job_id>/` (read-only), decodes
   each outright `ohlcv-1m` DBN file (calendar spreads are skipped), caches it as Parquet, and
   drops the bars duplicated across the two overlapping jobs after verifying they are identical.
   `ts_event` is the bar-open time and is stored as `ts_utc`; `ts_ny` is the tz-aware
   America/New_York conversion.
2. **Sessions** — CME trading date = NY calendar date, except bars at/after 18:00 ET belong to the
   next date. Session = 18:00 ET (previous day) → 17:00 ET; maintenance 17:00–18:00. Window flags
   (half-open, NY wall clock): `in_rth` 09:30–16:00, `in_sb_london` 03:00–04:00, `in_sb_ny_am`
   10:00–11:00, `in_sb_ny_pm` 14:00–15:00. Holidays and early closes are detected from the data
   (first/last bar vs nominal open/close, bar count) — no external calendar is assumed.
3. **Roll selection** — documented volume-crossover rule (see `engine/rolls.py` docstring and the
   roll report): a challenger with later expiry whose daily volume strictly exceeds the incumbent's
   on trading date D becomes the active contract on D+1. Ties keep the incumbent; never rolls
   backward; the first date uses its own volume (flagged).
4. **Continuous series** — unadjusted = the active contract's own bars (nothing interpolated).
   Back-adjusted = unadjusted + additive offset, anchored to the latest contract (adjustment 0);
   offset_k = close(new) − close(old) at the 16:59 ET bar of the crossover session. All offsets
   and cumulative adjustments are verified multiples of 0.25. Both files have identical rows,
   timestamps, volume and flags; only OHLC and `adjustment` differ.
5. **Quality** — per-bar checks (duplicates, OHLC validity, tick grid, zero volume, NaN), per-session
   completeness, gap classification, vendor-degraded flag (Databento `condition.json`), abnormal
   discontinuity scan, and a hard check that the four audited anomalies are reproduced exactly.
6. **Split** — `split` column: `development` (trading dates 2022-10-03 … 2024-10-18), `holdout`
   (2024-10-21 … 2026-10-20), `excluded` (the truncated 2026-10-21 session).

## Columns in the bar datasets

| column | meaning |
|---|---|
| `ts_utc`, `ts_ny` | bar open, UTC and America/New_York (tz-aware) |
| `trading_date` | CME trading date |
| `symbol`, `instrument_id` | source contract of this bar |
| `open high low close volume` | raw (unadjusted file) or raw + `adjustment` (back-adjusted file) |
| `adjustment` | additive offset applied to this bar (0 in the unadjusted file and for the latest contract) |
| `minute_of_day_ny`, `weekday_ny` | wall-clock helpers |
| `in_rth`, `in_sb_london`, `in_sb_ny_am`, `in_sb_ny_pm`, `in_maintenance` | window membership |
| `eligible_<window>` | bar is inside the window **and** the session's window has every minute present and is not the truncated final session |
| `bar_index`, `gap_prev_min`, `consecutive_prev` | `consecutive_prev` is False whenever the previous bar is not exactly one minute earlier — detectors must not treat such bars as consecutive |
| `segment_id`, `is_first_bar_of_contract` | roll segments |
| `session_complete`, `is_truncated_final`, `vendor_degraded` | session-level flags |
| `split` | development / holdout / excluded |

## Research access and holdout protection

```python
from ict_lab.engine.loader import load_development, load_rolls, load_sessions
bars = load_development(series="backadjusted")        # development split only — the default
```

`load_holdout` is the only way to read holdout rows. It requires a `HoldoutAuthorization`
whose `confirm` string equals `HOLDOUT_CONFIRM_PHRASE` exactly, and it appends an entry to
`runs/holdout_access.log`. `load_rolls` / `load_sessions` also hide holdout rows by default.
Nothing in Layer 1 computes signals or performance on any split.

## Price-handling rules enforced

- Strategy calculations use the **back-adjusted** series; charts and historical price audits use
  the **unadjusted** series.
- Distances are kept in index points, ticks (`InstrumentSpec.points_to_ticks`) and later R-multiples.
  Percentage returns or ratios of adjusted OHLC levels are prohibited; the static test
  `tests/test_08_static_price_division.py` fails the build if any module divides by a price column
  or calls `pct_change` (opt out of a single justified line with `# price-division-ok`).
- MNQ spec in config: tick 0.25 pt, $0.50/tick, $2.00/pt. No NQ/ES multipliers anywhere.

## Reports

- `data/clean/reports/contract_roll_report.md` — rule, 16-row roll log with offsets, cumulative
  adjustments, volumes, flags, and the comparison with the Phase 1 audit dates.
- `data/clean/reports/data_quality_report.md` — bar checks, incomplete sessions, gaps, known
  anomalies, vendor-degraded sessions, discontinuities, window-eligibility counts.
- `data/clean/reports/session_coverage_report.md` — sessions by year/status and the list of
  sessions with an ineligible window.
- `runs/roll_charts/` — adjusted vs unadjusted closes around selected rolls + `roll_boundary_jumps.csv`.

## Known assumptions (not resolvable from the files alone)

1. The original research's vendor roll convention is unknown; this rule is volume crossover
   effective next session. Later layers must test sensitivity to the roll rule.
2. The offset reference minute (16:59 ET close of the crossover session) is a documented choice,
   not the vendor's.
3. Holidays/early closes are inferred from the data, not from an official CME calendar.
4. Databento's `condition.json` dates are treated as UTC dates; a session is flagged degraded if
   its UTC span touches such a date (conservative; next-day sessions may be flagged).
5. Single-digit year codes in raw symbols are mapped to the 2020s (valid for 2022–2029 data).
