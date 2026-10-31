# ICT Silver Bullet — Research Methodology (Layer 2 feature definitions)

Status: implemented in `ict_lab/features/`, configuration in `configs/layer2_features.toml`.
Source: the written Layer 2 specification supplied to this lab, which is the authoritative
extraction of the original research framework (the source screenshots were processed upstream and
are not re-interpreted here). Anything the specification leaves open is listed under
*Implementation assumptions* and in §12.

Legend used throughout:

- **FIXED** — methodology requirement; changing it is a different methodology.
- **PARAM** — configurable research parameter (exposed in the TOML config and hashed into every run).
- **APPROVED** — implementation choice not determined by the specification, approved in the Layer 2
  ambiguity resolution (2026-10-31); documented here as an explicit, deliberate choice.
- **ASSUMPTION** — implementation choice still awaiting a decision (listed in §12).
- **LOOKAHEAD** — diagnostic that uses future information; isolated from strategy testing.

## 1. Data, series and causality

- Instrument: MNQ, 1-minute bars from Layer 1 (`ict_lab/data/clean`). Tick 0.25, $0.50/tick, $2/point.
- Default series (PARAM `series.series_id`): `mnq_volcross_next_session_backadj_v1` — the Layer 1
  volume-crossover (effective next session) roll, additive back-adjustment. Detectors take any
  registered series (`features/series.py::SERIES_REGISTRY`); no roll convention appears in detector
  code; every feature row carries `series_id`; the roll log is passed through as `rolls` for
  sensitivity analysis. Alternative roll datasets are not generated in Layer 2.
- Development split only (trading dates 2022-10-03 … 2024-10-18). The series loader goes through the
  Layer 1 development loader, so holdout bars cannot be reached from Layer 2.
- Timestamp convention: every candle is stamped with its **open** time (`ts_utc`, `ts_ny`), and
  carries `close_ts_utc` (last contained bar + 1 min) and `available_ts_utc` (bucket end on the NY
  wall clock = earliest moment the candle is known complete). A feature's `confirmation_ts_utc` is the
  `available_ts_utc` of the candle that confirms it. Any consumer must only use a feature at
  bar times `>= confirmation_ts_utc`.
- Higher timeframes (5m, 15m, 1h) are built from 1m bars on NY wall-clock buckets (DST-safe); 1d is
  the CME session. Candles carry `n_bars`, `expected_bars`, `complete` and `consecutive_prev`
  (previous candle is the immediately preceding bucket). Missing minutes are never forward-filled.
- Sessions/windows/holidays/missing-data flags come unchanged from Layer 1.

## 2. ATR(14)

- FIXED: period 14, measured on the same timeframe as the feature that uses it.
- APPROVED: Wilder smoothing (`atr.method = "wilder"`, alternative `"sma"`).
- APPROVED continuity rule: true range uses the previous close only when the candle is
  bucket-consecutive with its predecessor; across a session break or a data hole TR = high − low.
  A **data discontinuity** is a candle that is not bucket-consecutive with the previous candle of the
  same session (missing-bar hole) or that is itself incomplete. With `atr.reset_on_data_gap = true`
  (default) the recursion restarts at every discontinuity and ATR is unavailable (NaN) until 14 candles
  have accumulated since the restart. Session breaks (maintenance, weekends) are not data holes; ATR
  carries across them.
- Warm-up: the first 14 candles have no ATR (NaN). Features that need ATR record NaN and any
  ATR-based filter excludes them rather than inventing a value.

## 3. Fair Value Gaps (`features/fvg.py`)

| item | definition | status |
|---|---|---|
| bullish | candle-1 high **strictly below** candle-3 low; upper = c3.low, lower = c1.high | FIXED |
| bearish | candle-1 low **strictly above** candle-3 high; upper = c1.low, lower = c3.high | FIXED |
| timeframes | 1m, 5m, 15m | FIXED |
| availability | only after candle 3 closes: `confirmation_ts_utc = c3.available_ts_utc` | FIXED |
| formation_ts | candle-1 open time | APPROVED |
| candles | the three candles must be bucket-consecutive and complete (`fvg.require_complete_candles`); incomplete HTF candles never form an FVG | APPROVED/PARAM |
| midpoint, gap_points, gap_ticks | (upper+lower)/2, upper−lower, /0.25 | FIXED |
| gap_atr | gap_points / ATR(14) on the FVG timeframe at candle-3 close | FIXED |
| min filters | `fvg.min_gap_points`, `fvg.min_gap_atr` (NaN ATR fails the ATR filter) | PARAM |
| first mitigation | first 1m bar at/after confirmation that trades **strictly inside** the gap (bullish: low < upper; bearish: high > lower) | APPROVED |
| full fill | first 1m bar at/after confirmation that reaches the distal boundary (bullish: low ≤ lower; bearish: high ≥ upper) | APPROVED |

Mitigation and fill are evaluated on 1m bars regardless of the FVG timeframe and can never precede
confirmation (tested).

## 4. Liquidity levels (`features/liquidity.py`)

FIXED universe — nothing else can be a sweep reference, and the config schema rejects any other type:

| type | value | formation | confirmation | activation | expiry |
|---|---|---|---|---|---|
| prev_session_high/low | high/low of the previous CME session (18:00→17:00 ET) | bar of the extreme | previous session's last bar + 1 min | current session open (18:00 ET) | current session close |
| prev_rth_high/low | high/low of the previous session's RTH (09:30–16:00 ET) | bar of the extreme | 16:00 ET of that day | current session open | current session close |
| prewindow_high/low | high/low from the session open up to (excluding) the window start | bar of the extreme | window start | window start | window end |
| swing_15m_high/low | confirmed 15-minute fractal swing | swing candle open | `available_ts` of the `right`-th candle after the swing | = confirmation | none |

- FIXED exclusion: 1-minute swings are never liquidity. `LiquidityConfig.validate` rejects `swing_1m`,
  `swing_5m`, `swing_1h`, `mss_swing`; `swing_timeframe` must be `"15m"`.
- PARAM with APPROVED defaults: `swing_left` / `swing_right` = 2 / 2 (independently configurable from
  the MSS and bias fractals), `equal_handling = first` (strictly greater on the left, ≥ on the right;
  `last`: mirror; `strict`), `prewindow_lookback = session_open` (APPROVED: high/low from the current
  CME session open up to, excluding, the window start; frozen at the window start).
- APPROVED: previous session = previous *present* session in the data (a closed exchange day is
  skipped, not treated as a zero-range session). `source_session_complete` records whether that
  session had every minute.
- Buyside = highs, sellside = lows.
- Consumption (PARAM `consumption_rule`, `allow_reuse`): a level is consumed by a confirmed sweep or by
  a penetration that fails to reverse within the confirmation delay (`penetration_no_reversal`).
  Consumed levels are not reused unless `allow_reuse = true`.

## 5. Liquidity sweeps (`features/sweeps.py`)

| item | definition | status |
|---|---|---|
| bullish reversal sweep | bar low ≤ sellside level − min_penetration, and a bar within `max_confirmation_bars` (penetration bar = bar 0) **closes above** the level | FIXED |
| bearish reversal sweep | mirror on a buyside level, close below | FIXED |
| min_penetration | 1 tick (0.25) default | FIXED default, PARAM |
| max_confirmation_bars | 3 completed bars default | FIXED default, PARAM |
| execution timeframe | 1m default (5m allowed) | PARAM |
| eligibility | level active (`activation_ts ≤ bar open`), not expired, not consumed; evaluated strictly in time order | FIXED |
| recorded | level, direction, penetration ts/index, max penetration (points, ticks), confirmation ts (close of confirming bar) and index, bars to confirmation, status (`confirmed` / `no_reversal`), level type and source timeframe, Silver Bullet window of the confirming bar | FIXED |

States: activated → penetrated → confirmed sweep / no reversal → consumed.

## 6. Displacement (`features/displacement.py`)

- FIXED: candle range (high − low) relative to ATR(14); thresholds 1.0 / 1.5 / 2.0 / 3.0 × ATR all
  evaluated; `threshold_passed` = highest met.
- APPROVED/PARAM `atr_reference = prior_candle`: the baseline is the ATR(14) at the prior completed
  candle's close, so the candidate displacement candle is excluded from its own baseline
  (`same_candle` remains available for comparison only).
- Percentile definition (PARAM): ratio ≥ the `percentile`-th percentile of the ratios of the
  previous `percentile_lookback` candles (strictly prior candles).
- Direction: close > open bullish, close < open bearish, else none. Confirmation = candle close.
- Table size: only candles with ratio ≥ `record_min_ratio` or passing the percentile are written.

## 7. Market Structure Shift (`features/mss.py`)

- FIXED: after a confirmed sweep, break of the most recent eligible opposing confirmed swing
  (bullish sweep → swing high; bearish sweep → swing low) on the MSS timeframe (PARAM 1m/5m/15m),
  with `close` or `wick` confirmation (PARAM).
- MSS swings use their own fractal parameters (PARAM `mss.swing_left/right`) and are **never** used as
  liquidity references (separate table, separate config section).
- APPROVED "eligible": confirmed at or before the sweep confirmation, and not already broken (by the
  chosen confirmation method) between the swing candle and the sweep confirmation.
- PARAM `max_bars_after_sweep` (APPROVED default 60, explicitly *not* a methodology requirement):
  search horizon in MSS-timeframe candles starting at the first candle that opens at/after the sweep
  confirmation. Alternative horizons are a config change only. Rows with `found = False` record the
  swing used.

## 8. Higher-timeframe bias (`features/bias.py`)

Evaluated at each Silver Bullet window start with data available at that instant.

| detector | rule | status |
|---|---|---|
| none | always "none" | FIXED option |
| prev_day_oc | previous completed session close vs open | FIXED |
| swing_15m_structure | last two confirmed 15m swing highs and lows: HH & HL → bullish, LH & LL → bearish, else none | APPROVED (structure rule) |
| swing_1h_structure | same on 1h candles | APPROVED |
| daily_ma20_slope | SMA(20) of completed session closes; last − previous > 0 bullish, < 0 bearish; none until 21 completed sessions | FIXED period, APPROVED slope rule |

Neutral and tie conditions (APPROVED, implemented in `features/bias.py`):

- prev_day_oc: no completed previous session → none; close == open → none.
- swing structure: fewer than two confirmed highs or two confirmed lows at the evaluation time → none;
  last high == previous high or last low == previous low → none; mixed (HH with LL, or LH with HL) → none.
- daily_ma20_slope: fewer than 21 completed sessions → none; slope exactly 0 → none.
| perfect_window | window's own open-to-close direction | **LOOKAHEAD / INVALID FOR LIVE TRADING** |
| perfect_session | direction from the window open to the session close | **LOOKAHEAD / INVALID FOR LIVE TRADING** |

Both lookahead variants are retained as diagnostics only (APPROVED). They raise `PermissionError`
unless `bias.allow_lookahead_diagnostic = true`; a validated research config rejects them as
`bias.detector`; every row they produce has `lookahead = True`. They are excluded from candidate
selection, optimisation and the holdout evaluation.

## 9. Silver Bullet windows (`features/windows.py`)

FIXED: America/New_York, half-open: London 03:00–04:00, NY AM 10:00–11:00, NY PM 14:00–15:00.
Eligibility and exclusion reasons are inherited from Layer 1 (every window minute present, not the
truncated final session, not the non-causal first session) and written per (trading_date, window)
together with the observed session status, calendar status and vendor-degraded flag.

## 10. Causality guarantees and tests

- No detector reads bars after a feature's confirmation to decide that feature; HTF features appear
  only after their bucket ends; missing bars break consecutiveness (`consecutive_prev`), so no FVG,
  ATR true range or MSS/sweep bar count ever treats non-adjacent bars as adjacent.
- Truncation test (`tests/test_l2_04_integration.py::test_no_lookahead_truncation`): features computed
  on a prefix of the development data are identical, for everything confirmed before the cut, to the
  same features computed on the full slice (FVG, liquidity, sweeps, displacement, MSS, bias).
- Series independence test: detectors run unchanged on a second registered series id and stamp it.

## 11. Execution methodology (documentation only — Layers 3 and 4)

Canonical setup sequence: (1) window eligibility → (2) optional bias → (3) qualifying liquidity sweep
→ (4) optional MSS confirmation → (5) optional displacement confirmation → (6) first eligible
direction-matching FVG.

Future execution configurations: entry at FVG proximal boundary / midpoint / distal boundary; limit
orders active only after setup confirmation; fills only when price trades through the limit; stops
beyond the displacement swing, FVG distal boundary or fixed points; targets at 1R/2R/3R, the next
opposing eligible liquidity (approved universe only, §4) or time-based exit; configurable trades per
window; no overlapping positions; commission and slippage; stop-first resolution when the intrabar
order is ambiguous. None of this is implemented in Layer 2.

## 12. Ambiguity resolution (2026-10-31) and remaining open items

Resolved and approved as explicit implementation choices (see APPROVED markers above):

1. Written specification is the authoritative source.
2. FVG formation = candle-1 open; confirmation/eligibility after candle-3 close; mitigation = strictly
   inside; full fill = distal boundary reached.
3. Wilder ATR(14); no true range across missing intervals; ATR unavailable after a within-session data
   hole until a fresh 14-candle warm-up (`atr.reset_on_data_gap`).
4. 2-left / 2-right confirmed fractals by default for 15m liquidity swings, MSS swings and structure
   bias, each independently configurable; 1-minute swings remain prohibited as liquidity references.
5. Pre-window liquidity = current session open → window start (exclusive), frozen at the window start.
6. Displacement baseline = prior completed candle's ATR(14).
7. MSS excludes swings already broken before the sweep; 60-candle horizon is a configurable default.
8. Structure bias from the two most recent confirmed swings; MA bias from the sign of the SMA(20)
   slope; neutral/tie conditions as documented in §8.
9. Window- and session-based perfect-bias diagnostics retained, labelled LOOKAHEAD, excluded from
   candidate selection, optimisation and holdout validation.
10. Incomplete higher-timeframe candles are excluded from FVG formation; missing-data flags are
    preserved; no bars are fabricated.

Remaining open items (none block Layer 3; each is a config parameter):

- `equal_handling` for fractal swings defaults to `first`; the specification only requires determinism.
- `liquidity.consumption_rule`: a penetration that never reverses within the delay consumes the level
  (`penetration_no_reversal`). An alternative rule (consume only on confirmed sweeps) is a one-line
  config change if Layer 3 needs it.
- The sweep execution timeframe (1m default, 5m allowed) and the displacement/MSS timeframes are
  research parameters whose sweep ranges will be set in Layer 4.
