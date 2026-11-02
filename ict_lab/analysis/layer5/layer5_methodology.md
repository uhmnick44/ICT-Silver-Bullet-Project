# Layer 5 methodology — researcher-selected conventions, assumptions and run plan

Status: CHECKPOINT. Infrastructure implemented and tested; the population inference, null models,
robustness, subperiod, sample-size and walk-forward experiments are NOT yet executed pending approval of
the run plan below. Development data only; the locked holdout is never loaded.

The original 24 screenshots remain the methodological authority. Where they do not establish an exact
parameter, the convention below is a **researcher-selected assumption** (Layer 5 review, 2026-11-02),
not a verified screenshot rule. Nothing in Layer 5 changes a Layer 1–4 definition.

## Fixed, carried from earlier layers

- MNQ only (tick 0.25, $0.50/tick, $2/pt, 1 contract); approved liquidity universes; no 1-minute swing
  liquidity (schema-rejected); stop = user-authorized `liquidity_sweep_extreme` + 1 tick in every
  configuration; `rth_end` exit at the 16:00 ET bar open; existing costs ($0.94/side) and slippage
  (stop 1 tick, time exit 1 tick, entry/target 0); strict limit fills; stop-first same-bar rule;
  roll-spanning trades flagged and excluded; series `mnq_volcross_next_session_backadj_v1`.
- The `displacement_swing` stop remains disabled and undefined. The named configurations and every grid
  point use the liquidity-sweep stop; this is the user-authorized modification, not a provisional stop.
  `displacement_candle_extreme` exists only for the Layer 3 verification baseline.

## Conventions (1–13)

1. **Grid.** Full canonical grid: 11,520 generated over the established dimensions, 8,640 after semantic
   deduplication (`swings_only` ≡ `bsl_ssl_15m`), all 8,640 evaluated (below the 25,000 cap; runtime
   66 min on 4 processes). No sampling was needed; `grid.csv` records generated index, config hash and
   semantic key, and `sample_grid(count, seed)` is available if a sample is ever required.
2. **Net Sharpe.** Annualized Sharpe of the daily net P&L (USD) over the configuration's *eligible*
   trading days (days with at least one eligible window among the configuration's windows), zero on days
   without a trade, factor √252, zero risk-free rate. Implemented in `stats.performance_metrics`
   (`inference.eligible_dates_for` supplies the eligible days). The earlier sweep used all development
   dates as the denominator; the inference step recomputes Sharpe under this convention.
3. **Bootstrap.** Politis–Romano stationary bootstrap, expected block length 10 trades (sensitivity 5 and
   20), 1,000 resamples, seed 20261102, vectorised restart construction (verified mean block ≈ 10).
4. **p-values and FDR.** One-sided p for H1: mean net R > 0 from the null-centred bootstrap (series shifted
   to mean zero, resampled with the same indices, p = P(centred mean ≥ observed) with add-one correction).
   The percentile 95% CI of the mean is reported separately. Benjamini–Hochberg at q = 0.10 over the
   complete population of 8,640 configurations: configurations with < 2 trades have no p-value, remain in
   the family count and can never be rejected. Dependence limitation: configurations share bars and
   trades, so p-values are positively dependent; BH is applied under a documented PRDS-type assumption
   (BY would be the conservative alternative) and is not a proof of independence.
5. **Null A.** Random bar inside the same eligible window and date, market entry at that bar's open,
   same direction, same planned risk distance and target R, production exits/costs; one position at a
   time (overlapping draws redrawn ≤ 20 times, else dropped and counted). 1,000 iterations, seed 20261105.
   Deviation to note: the actual strategy enters on a limit; the null enters at market (a limit has no
   meaning without an FVG).
6. **Null B.** 20 non-overlapping 60-minute off-hour windows starting at 18:00, 19:00, …, 02:00, 04:00, …,
   09:00, 11:00, 12:00, 13:00, 15:00, 16:00 ET (excludes the three Silver Bullet hours and the 17:00
   maintenance hour). Eligibility: all 60 minutes present and the session neither truncated nor
   non-causal. Pre-window levels and sweeps are recomputed with the unchanged Layer 2 detectors for the
   extended window set (`nulls.offhour_store`); the strategy logic is otherwise identical. Each
   off-hour window is run individually; results are compared with the actual windows.
7. **Null C.** Each setup's direction is independently flipped with p = 0.5 (seed 20261107, 1,000
   iterations) and the trade is re-simulated with the production limit-fill rule at the same limit price
   and activation bar, the same risk distance and target R, exits and costs. Inverted limits that are
   marketable at activation fill at the limit per the Layer 3 rule.
8. **FVG-only ablation.** CONFLICT — see below; not implemented.
9. **No-window ablation.** Not yet implemented — see open implementation question below.
10. **Cost sensitivity.** Fee multipliers 1.0/1.5/2.0 × stop slippage 0/1/2/3 ticks × time-exit slippage
    0/1/2 ticks, all **analytic re-costing** of the recorded trades: in this engine slippage is applied
    after the exit price is fixed and entry/target slippage is zero, so no fill or exit can change and
    re-simulation is unnecessary. The trade set is identical across every level.
11. **Walk-forward.** Expanding chronological folds; initial training period 2022-10-03 → 2023-09-30
    (12 months), then non-overlapping 3-month evaluation folds: 2023-10-01→12-31, 2024-01-01→03-31,
    2024-04-01→06-30, 2024-07-01→09-30, and a partial fold 2024-10-01→10-18 (16 days, flagged).
    Selection per fold uses training trades only (frozen before the fold): candidates with ≥ 100
    training trades, positive training net P&L and training net Sharpe ≥ 0.5, ranked by training net
    expectancy in R; the top 5 are evaluated on the fold. **Selection rule values (100 / 0.5 / top 5) are
    proposed and await approval.**
12. **Subperiods.** Annual and quarterly by trade entry date; partial periods (2022 Q4, 2024 Q4 to
    10-18) flagged.
13. **Sample size.** Chronologically first 25/50/75/100% of each configuration's trades; no reselection.

## Conflicts and open points (STOP items)

- **FVG-only ablation (convention 8) conflicts with the fixed stop rule.** With no sweep there is no
  qualifying sweep event, so the user-authorized `liquidity_sweep_extreme` stop is undefined, and the
  only alternatives are stop modes the instructions forbid adding or substituting. Options: (a) skip
  step 1 and report it not performed; (b) authorize `fvg_distal` for step 1 only, explicitly labelled
  as non-comparable. No action taken.
- **No-window ablation (convention 9).** The engine processes windows; a whole-session search needs a
  definition of the trade allowance over 23 hours (1 per session? per hour?) for comparability with the
  3-window base. Proposed: two half-session windows (18:00–00:00, 00:00–17:00) with the base allowance
  each, labelled. Awaiting approval.
- **Walk-forward selection values** (above).
- **Null-model population.** 1,000 iterations of Null A or C take ~10 s per configuration (measured on as_traded, 469 trades), so
  the full 8,640 population is ~24 h per null and is not proposed. Proposed population: the three named
  configurations + every configuration passing the descriptive screen under convention 2 + every FDR
  survivor (≈ 70–80 configurations, ≈ 10 min per null). Null B: ~1 min per configuration.

## Proposed run plan (awaiting approval)

| step | population | expected runtime |
|---|---|---|
| Population inference: Sharpe under convention 2, bootstrap at 10/5/20, BH-FDR | all 8,640 | ~2 min |
| Cost sensitivity, subperiods, sample-size (analytic) | all 8,640 | ~15 min |
| Walk-forward (5 folds, expanding) | all 8,640 as candidates | ~5 min |
| Null A, Null C (1,000 iterations each) | named configs + screen passers + FDR survivors | ~25 min |
| Null B (20 off-hour windows each) | same population | ~1.5 h |
| Ablation steps 4, 5, diagnostic | done; steps 1–3 per decisions above | — |

Statistical testing population: 8,640 (FDR family). Candidate qualification will combine: descriptive
screen → FDR survival → 95% CI above zero → walk-forward consistency (all evaluation folds with trades
show non-negative net expectancy for the frozen selection), reported as separate tiers.

## Limitations

Backtest evidence only; single instrument; one roll convention (sensitivity not performed); ES
cross-market validation not performed; bootstrap and FDR assume the dependence structure above;
window-level execution means Null A random entries do not inherit the limit-order mechanics.
