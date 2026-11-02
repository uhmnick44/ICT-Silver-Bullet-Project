# Layer 3 — Execution and backtesting assumptions

Implements the execution methodology of the written Silver Bullet specification (§1–§12 of the
Layer 3 brief). Items marked FIXED come from the specification; APPROVED/ASSUMPTION items are this
lab's deterministic choices where the specification is silent, each exposed in
`configs/layer3_execution.toml` and hashed into every trade log.

## Signal sequence (`engine/signals.py`)

- FIXED order of gates: window eligibility → optional bias → confirmed sweep → optional MSS →
  optional displacement → first direction-matching FVG → executable setup. `setup_ts_utc` is the
  latest confirmation among the required features (always the FVG confirmation).
- FIXED: sellside sweep → bullish setup; buyside sweep → bearish setup; FVG direction must match.
- FIXED: one trade per window (first qualifying setup); no re-entries, no concurrent positions.
- Features come from the Layer 2 tables unchanged (no re-derivation). Timeframes: sweep 1m,
  displacement 1m, MSS 1m, FVG configurable 1m/5m/15m. Liquidity references restricted to the
  approved universe; `swing_1m` is rejected by the config schema.
- ASSUMPTION `require_penetration_in_window = false`: the sweep's *confirmation* must fall inside the
  window; its penetration bar may precede the window start (a sweep confirmed on the window's first
  bar counts).
- ASSUMPTION: a displacement candle qualifies if its confirmation is at/after the sweep confirmation
  (the sweep's confirming bar itself may be the displacement candle) and before the window end.
- ASSUMPTION (MSS): when required, the MSS break must occur before the window end; the setup time
  advances to the break.
- Bias: computed by the Layer 2 detectors at the window start; with a detector selected, a conflicting
  bias rejects the sweep, and `require_bias = true` makes a "none" reading block the window.
- No-trade diagnostics record the first failed gate of the sweep that progressed furthest.

## Orders and fills (`engine/execution.py`)

- FIXED: entry is an FVG limit at proximal / midpoint / distal; the order is active from the first
  bar opening at/after `setup_ts_utc`; nothing before activation can fill it.
- FIXED: strict trade-through — bullish fills need `low < limit`, bearish `high > limit`; an exact touch
  is not a fill. Fill price = limit (+ configurable entry slippage, default 0).
- APPROVED `marketable_at_activation = fill_at_limit`: if the activation bar *opens* beyond the limit,
  the fill is taken at the limit price (never better) on that bar and flagged; `cancel` is available.
- ASSUMPTION `round_midpoint = away_from_proximal`: an off-grid midpoint rounds deeper into the gap
  (down for bullish, up for bearish) — the harder-to-fill direction.
- FIXED: unfilled orders expire at the window end and are logged with the first failed gate
  `entry_fill` and reason `order_expired_unfilled_at_window_end`.

## Stops

- `fvg_distal`: distal FVG boundary ± `buffer_ticks`; `fixed_points`: entry ∓ points. Stops are
  rounded away from the entry onto the tick grid; a non-positive distance rejects the setup
  (`stop_invalid`) — nothing is substituted.
- `liquidity_sweep_extreme` (USER-AUTHORIZED MODIFICATION of the original screenshot methodology; used
  by the three named configurations): long = one tick below the lowest wick of the qualifying sweep
  event; short = one tick above its highest wick. The sweep event spans the penetration bar through the
  confirming bar inclusive — exactly the candles Layer 2 used to measure `max_penetration` at
  confirmation, so only candles available at confirmation are used (`extreme = level ∓ max_penetration`).
  The reference is frozen on the setup (`stop_ref_price`) and never adjusted; `buffer_ticks` (default 1)
  is the existing configurable buffer; a non-positive distance rejects the setup.
- `displacement_candle_extreme` (APPROVED, Layer 3 ambiguity resolution 1, used for the Layer 3 verification baseline):
  long = one tick below the low of the selected bullish displacement candle; short = one tick above the
  high of the selected bearish candle (`buffer_ticks`, default 1). The selected candle is the **latest**
  qualifying direction-matching displacement candle (ratio ≥ `displacement_threshold`) confirmed after
  the sweep confirmation and no later than the FVG confirmation; it is frozen on the setup
  (`stop_ref_displacement_*`). The extreme is aggregated from the 1m bars of the candle's bucket, so it
  works for any displacement timeframe. Missing candle, incomplete candle at setup time, or a
  non-positive stop distance rejects the setup at gate `stop` with the reason recorded — nothing is
  substituted. This extreme is **not** treated as a confirmed structural swing.
- `displacement_swing`: **separate, unresolved mode — blocked.** The Layer 2 metadata defines no
  structural swing associated with displacement; selecting this stop fails config validation.

## Targets

- `fixed_r` (1R/2R/3R or any positive multiple) rounded away from the entry; `time_only`.
- `opposing_liquidity`: nearest level on the opposite side from the approved universe that is active
  at `setup_ts_utc` (activated, not expired, not consumed) and at least one tick beyond the entry.
  Levels discovered later are never used. If none exists the configured fallback (default 2R) is used
  and recorded (`target_fallback_used`, `target_source`).
- ASSUMPTION `target.fill_rule = trade_through`: the profit-target limit also requires a strict
  trade-through (`touch` available for comparison).

## Exits and position management

- FIXED `same_bar_rule = stop_first`: when one bar reaches both stop and target the stop executes;
  the trade is flagged `same_bar_ambiguous`. The entry bar itself is included in this check.
- Stop-market: fills at the stop price (or at the bar's open when the bar gaps through the stop),
  minus `stop_slippage_ticks` adverse (default 1; 0/1/2/3 supported).
- Exit policies: `window_end` (exit at the open of the first bar at/after the window end),
  `rth_end` (open of the first bar at/after 16:00 ET), `hold` (stop/target only). Time exits use
  the first executable price after the condition is known (next bar open), never a completed close,
  minus `time_exit_slippage_ticks` adverse (APPROVED baseline assumption: 1 tick, configurable; included in
  net P&L and net R).
- If the session ends before a time exit can execute (early close), the exit happens at the first bar
  of the next session and is flagged `exit_after_session_break`.
- One position at a time: a window whose start falls while a position is open is skipped with gate
  `position_free`.

## Money, costs and price basis

- MNQ: tick 0.25, $0.50/tick, $2.00/point; `sizing.contracts` configurable (default 1, never assumed).
- Costs (modelling assumptions, not verified broker rates): $0.39 commission + $0.36 exchange + $0.19
  clearing = $0.94 per contract per side, $1.88 round trip. Slippage defaults: entry 0, target 0,
  stop 1 tick, time exit 1 tick — always adverse.
- `gross_pnl` uses theoretical prices (limit / stop / target / next-bar open); `slippage_cost` and
  `commission` are reported separately; `net_pnl = gross − slippage − commission`. `gross_r` =
  gross points / planned risk points; `net_r` = net $ / planned risk $.
- MFE/MAE are measured from the entry bar through the exit bar inclusive against the theoretical
  entry price, in points and R.
- Prices and distances are on the back-adjusted series; point differences are invariant under the
  additive adjustment inside a contract segment. Unadjusted entry/stop/target/exit prices and the
  contract symbols are recorded (`*_unadjusted`, `entry_symbol`, `exit_symbol`, `*_adjustment`).
- Rolls (APPROVED): a trade whose holding period crosses a roll timestamp or whose entry and exit
  adjustments differ is flagged `spans_roll`; with `roll.policy = flag_and_exclude` (default) it is also
  marked `excluded_by_roll_policy`, `included = False`, `exclusion_reason = spans_contract_roll`, and the
  manifest records `roll_exclusions` (counts and reasons). Positions are never stitched across two
  contracts. The `rth_end` and `window_end` policies cannot produce roll-spanning trades because rolls
  take effect at the 18:00 ET session open.

## Reproducibility

Every run writes `trades.parquet/csv`, `no_trade_log.csv` and `backtest_manifest.json` (Layer 3 config
and hash, Layer 2 config hash, Layer 1 config hash and data content hash, feature source
(cache/computed), development range, `holdout_accessed: false`, trade and no-trade content hashes,
software versions). Trades carry `trade_id`, `config_hash` and `series_id`.

## Final Layer 3 decisions (approved)

These are documented implementation decisions of this lab, not verified rules of the original research.

1. `displacement_swing` stays disabled: no structural definition is established by the available
   methodology; nothing is invented or substituted. `displacement_candle_extreme` is retained for the
   verification baseline and for explicitly labelled future experiments.
2. Roll-spanning trades are flagged and excluded; no synthetic rollover execution, no stitching across
   contracts. Excluded trades are written separately to `excluded_trades.csv` and counted in the manifest.
3. `displacement_candle_extreme`: most recent qualifying direction-matching displacement candle after the
   confirmed sweep and no later than FVG confirmation; long stop = candle low − 1 tick, short stop =
   candle high + 1 tick; confirmed features only; frozen at setup; setups without a qualifying candle or
   with a non-positive stop distance are rejected; the selected candle timestamp
   (`stop_ref_displacement_ts_utc`) and reference price (`stop_ref_price`) are recorded on every trade
   and on every stop-gate rejection.

## Resolved (Layer 3 ambiguity resolution)

1. Displacement-associated stop → `displacement_candle_extreme` for the verification baseline;
   `displacement_swing` kept as a separate unresolved mode.
2. Roll-spanning positions → flagged and excluded by default, with counts and reasons recorded.
3. Time-exit slippage → one adverse tick, configurable, included in net P&L and net R.

## Open items

1. `displacement_swing` stop: definition of a confirmed structural swing associated with displacement.
2. Rollover handling for positions held across a roll (only reachable with `exit.policy = hold`);
   such trades are excluded until a policy is approved.

## Layer 4 — multi-trade windows, multiple windows, named configurations

- Trade allowance per window: `signal.max_trades_per_window` is an integer in [1, 10] or `"unlimited"`,
  which applies the hard safety cap of 10 (`HARD_TRADE_CAP`). Each (trading date, window) has its own
  allowance; a position is never duplicated because several windows are registered.
- Setup enumeration (`signals.build_setups`): every confirmed sweep in the window yields at most one
  qualifying setup (its first eligible direction-matching FVG after the required gates). Setups are
  ordered by (setup timestamp, sweep confirmation, sweep id) — a deterministic tie-break that uses
  nothing after the setup's own confirmation.
- Submission rules, applied in setup order: trade allowance not exhausted → no open position (the new
  setup's activation bar must be strictly after the previous exit bar) → no pending order
  (`pending_order_policy = keep_first`: an unfilled order blocks newer setups until it fills or expires
  at the window end) → the sweep and the FVG have not already produced an order (no reuse of a consumed
  level or an executed setup). Rejections are logged per setup with their reason
  (`trade_cap_reached`, `position_open`, `order_pending`, `duplicate_setup`); execution-gate rejections
  (`stop`, `target`) are counted separately from submitted orders.
- Counters per window (`window_stats.csv`): qualifying setups, submitted orders, filled trades, canceled
  orders (expired unfilled; they do not consume a filled-trade allowance), execution-gate rejections and
  each blocking reason. `setup_log.csv` records every setup with a unique `setup_id`
  (`date:window:s<sweep_id>:<fvg_id>`) and its outcome. Setup ids are stable for a given feature run;
  Layer 2 sweep ids can renumber when features are recomputed on a prefix, so cross-run comparisons use
  feature content, not ids.
- Overlap across windows: one open position at any time; a position held past its window (e.g. a
  London trade under `rth_end`) blocks later windows that day (`position_free` gate).
- Named liquidity universes (`LIQUIDITY_UNIVERSES`): `session_refs`, `session_refs_plus_swings`,
  `bsl_ssl_15m`, `swings_only` (alias). A named universe sets both the sweep references and the
  opposing-liquidity target references; the schema rejects any mismatch and any 1m swing type.
- Named configurations (`configs/strategies/*.toml`, `load_named_config`): `as_taught_5m`,
  `as_taught_1m`, `as_traded` as specified in the Layer 4 brief, with the user-authorized stop
  modification `liquidity_sweep_extreme` (buffer 1 tick) in place of the original, unresolved "beyond
  displacement swing" stop. Entry (FVG midpoint), each configuration's target rule, sweep confirmation
  requirements, the `rth_end` exit (16:00 ET bar open with the existing market-exit slippage),
  roll-spanning exclusion and the approved liquidity references (no 1m swings) are unchanged. Each file
  carries `meta.stop_substitution_note` stating this.
- Frequency diagnostics (`analysis/frequency.py`) report signal, order and fill frequency only; the
  module asserts that no P&L, win-rate, Sharpe, profit-factor, expectancy or drawdown column exists.
