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
├── engine/                      # Layer 1: config, instrument, sessions, ingest, rolls, continuous, quality, pipeline, loader, manifest
│                                # Layer 3: exec_config, signals, execution, backtest
├── analysis/roll_chart.py       # chart verification around rolls;  analysis/layer1_summary.py
├── analysis/feature_charts.py   # Layer 2: 15 seeded development-period feature verification charts
├── features/                    # Layer 2: series registry, timeframes, atr, swings, fvg, liquidity, sweeps,
│                                #   displacement, mss, bias, windows, config, run
├── docs/silver_bullet_methodology.md   # Layer 2 feature definitions, parameters, approved decisions
├── docs/execution_assumptions.md       # Layer 3 execution rules, costs, price basis, open items
├── docs/manual_verification_layer3.md  # Layer 3 one-month manual verification sample
├── runs/                        # pipeline run logs, holdout_access.log, roll_charts/
└── tests/                       # pytest suite (Layer 1 test_0*.py, Layer 2 test_l2_*.py)
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
   10:00–11:00, `in_sb_ny_pm` 14:00–15:00. Observed coverage (missing dates, early closes, late
   opens, internal gaps) is measured from the bars and reported as `observed_*`. It is **not**
   interpreted as a holiday classification: every date is `calendar_unverified` until it appears
   in `configs/cme_calendar_verified.csv` (date, classification, source) checked against an
   authoritative CME trading calendar.
3. **Roll selection** — the lab's own convention `lab_volume_crossover_next_session_v1` (see
   `engine/rolls.py` and the roll report), not the unknown vendor convention of the original
   research: a challenger with later expiry whose daily volume strictly exceeds the incumbent's
   on trading date D becomes the active contract on D+1. Ties keep the incumbent; never rolls
   backward. Alternative conventions are registered in `rolls.ROLL_METHODS` and selected via
   `[roll].method` so later layers can test roll-rule sensitivity. The first trading date has no
   prior session, so its contract comes from its own volume: that session is flagged
   `noncausal_contract_selection` and all its `eligible_<window>` flags are False.
4. **Continuous series** — unadjusted = the active contract's own bars (nothing interpolated).
   Back-adjusted = unadjusted + additive offset, anchored to the latest contract (adjustment 0);
   offset_k = close(new) − close(old) at the 16:59 ET bar of the crossover session. Both contracts
   must have a valid bar at exactly that minute; otherwise the roll is flagged `needs_review`,
   nothing is substituted, `MNQ_rolls_NEEDS_REVIEW.csv` is written and the pipeline aborts. All
   offsets and cumulative adjustments are verified multiples of 0.25. Both files have identical
   rows, timestamps, volume and flags; only OHLC and `adjustment` differ.
5. **Quality** — per-bar checks (duplicates, OHLC validity, tick grid, zero volume, NaN), per-session
   completeness, gap classification, abnormal discontinuity scan, and a hard check that the four
   audited anomalies are reproduced exactly. Databento `condition.json` flags are UTC-date vendor
   attributes and are reported independently of observed completeness:
   `vendor_degraded_utc_overlap` (session span touches a degraded UTC date),
   `missing_minutes_in_degraded_utc_window` (observed loss inside that overlap) and
   `vendor_degraded_with_observed_loss`. A vendor flag never changes eligibility by itself.
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
| `eligible_<window>` | bar is inside the window **and** the session's window has every minute present **and** the session is neither the truncated final session nor the non-causal first session |
| `bar_index`, `gap_prev_min`, `consecutive_prev` | `consecutive_prev` is False whenever the previous bar is not exactly one minute earlier — detectors must not treat such bars as consecutive |
| `segment_id`, `is_first_bar_of_contract` | roll segments |
| `session_complete`, `is_truncated_final` | observed session-level flags |
| `vendor_degraded_utc_overlap`, `vendor_degraded_with_observed_loss`, `in_vendor_degraded_utc_date` | Databento condition flags (UTC-date based), independent of observed completeness |
| `noncausal_contract_selection` | True only on the first session (contract chosen from its own volume) |
| `calendar_status` | `calendar_unverified` or `verified:<classification>` from the authoritative calendar file |
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

## Approved conventions and open items

1. Roll convention `lab_volume_crossover_next_session_v1` is the lab's convention, approved for
   Layer 1; it is not claimed to match the original research's vendor series. Sensitivity to the
   roll rule is a Layer 2+ task via `ROLL_METHODS`.
2. Offset reference = 16:59 ET close of the crossover session, both bars required (no substitution).
3. Observed shortened/missing sessions remain `calendar_unverified` until an authoritative CME
   calendar is entered in `configs/cme_calendar_verified.csv` (currently empty).
4. Vendor condition flags are UTC-date attributes reported separately from observed loss.
5. The first session (2022-10-03) is flagged non-causal and is ineligible for strictly causal
   strategy testing; it stays in the development split for look-back context only.
6. Single-digit year codes in raw symbols are mapped to the 2020s (valid for 2022–2029 data).


## Layer 2 — ICT feature detection

Definitions, parameters and assumptions: `docs/silver_bullet_methodology.md`.
Configuration: `configs/layer2_features.toml` (hashed into every feature run manifest).

```bash
python -m ict_lab.features.run                      # all features on the development split (~45 s)
python -m ict_lab.analysis.feature_charts           # 15 seeded verification charts -> runs/feature_charts/
python -m pytest ict_lab/tests -k l2                # Layer 2 tests only
```

Outputs land in `runs/features/<series_id>/<config_hash[:12]>/`: `fvg`, `liquidity_levels`, `sweeps`,
`displacement`, `mss`, `bias`, `windows`, `rolls` (Parquet) and `feature_manifest.json` (series spec,
Layer 2 config + hash, Layer 1 config hash and back-adjusted content hash, software versions, row counts
and content hashes, `holdout_accessed: false`).

Rules enforced in code: approved liquidity universe only (no 1-minute swing liquidity, schema-rejected);
features confirm only after their candle closes; no forward-filling; `consecutive_prev` guards against
treating gaps as adjacent bars; lookahead "perfect bias" diagnostics are isolated behind an explicit flag
and rejected by validated research configs; detectors are series-agnostic (`features/series.py`).


## Layer 3 — deterministic execution and backtesting

Rules and assumptions: `docs/execution_assumptions.md`. Configuration: `configs/layer3_execution.toml`
(defaults) and `configs/baseline_verification.toml` (engine-verification baseline, not a strategy).

```bash
python -m ict_lab.engine.backtest --config ict_lab/configs/baseline_verification.toml
python -m ict_lab.analysis.manual_verification --month 2024-07
python -m pytest ict_lab/tests -k l3
```

Outputs land in `runs/backtests/<config_hash[:12]>/`: `trades.parquet/csv`, `no_trade_log.csv` (first failed
gate per window) and `backtest_manifest.json` (Layer 1/2/3 hashes, feature source, `holdout_accessed: false`,
content hashes). The signal sequence consumes Layer 2 tables unchanged; the engine uses NumPy arrays and
cached feature tables (cached and recomputed features give identical trades, tested).

The `displacement_swing` stop is blocked in the config schema until a swing-selection rule is approved;
the baseline runs with the FVG-distal stop as a labelled provisional stand-in.


## Layer 4 — named configurations, multi-trade windows, frequency diagnostics

```bash
python -m ict_lab.engine.backtest --config ict_lab/configs/strategies/as_traded.toml
python -m ict_lab.analysis.frequency            # analysis/frequency_report.{csv,md}, no_trade_reasons.csv, named_configs_manifest.json
python -m ict_lab.analysis.layer4_verification  # analysis/layer4_verification.md (hand-checked trades by category)
python -m pytest ict_lab/tests -k l4
```

Named configurations (`configs/strategies/`): `as_taught_5m`, `as_taught_1m`, `as_traded` — research
baselines, not recommended strategies; all use the documented `displacement_candle_extreme` stop
substitution. Multi-trade rules and counters are described in `docs/execution_assumptions.md`.
