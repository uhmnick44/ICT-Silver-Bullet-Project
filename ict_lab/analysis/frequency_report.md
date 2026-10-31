# Layer 4 frequency report — named configurations (development period only)

Research baselines, **not** recommended strategies. Signal frequency (qualifying setups) is reported separately from order submissions and fills. No profitability or performance metrics are computed in this layer.

Stop substitution: all three configurations use `displacement_candle_extreme` in place of the original, unresolved 'beyond displacement swing' stop.

Development range 2022-10-03 → 2024-10-18 (2.042 years). Ineligible windows (Layer 1 data-quality exclusions, truncated/non-causal sessions) are counted separately from eligible windows without a setup.

## Frequency by configuration and window

| config       | scope     |   windows_registered |   windows_eligible |   windows_ineligible_excluded |   windows_with_qualifying_setup |   pct_eligible_windows_with_setup |   windows_with_filled_trade |   pct_eligible_windows_with_fill |   trading_dates_with_filled_trade |   pct_trading_dates_with_filled_trade |   qualifying_setups |   submitted_orders |   filled_trades |   canceled_orders |   trades_per_year |   avg_trades_per_eligible_window |   max_trades_in_a_window |   trade_cap |
|:-------------|:----------|---------------------:|-------------------:|------------------------------:|--------------------------------:|----------------------------------:|----------------------------:|---------------------------------:|----------------------------------:|--------------------------------------:|--------------------:|-------------------:|----------------:|------------------:|------------------:|---------------------------------:|-------------------------:|------------:|
| as_taught_5m | all       |                 1590 |               1567 |                            23 |                             198 |                             12.64 |                          63 |                             4.02 |                                63 |                                 11.91 |                 286 |                126 |              63 |                63 |              30.8 |                           0.0402 |                        1 |           1 |
| as_taught_5m | sb_london |                  530 |                529 |                             1 |                              87 |                             16.45 |                          27 |                             5.1  |                                27 |                                  5.1  |                 121 |                 57 |              27 |                30 |              13.2 |                           0.051  |                        1 |           1 |
| as_taught_5m | sb_ny_am  |                  530 |                528 |                             2 |                              66 |                             12.5  |                          22 |                             4.17 |                                22 |                                  4.17 |                 101 |                 37 |              22 |                15 |              10.8 |                           0.0417 |                        1 |           1 |
| as_taught_5m | sb_ny_pm  |                  530 |                510 |                            20 |                              45 |                              8.82 |                          14 |                             2.75 |                                14 |                                  2.75 |                  64 |                 32 |              14 |                18 |               6.9 |                           0.0275 |                        1 |           1 |
| as_taught_1m | all       |                 1590 |               1567 |                            23 |                             438 |                             27.95 |                         248 |                            15.83 |                               210 |                                 39.7  |                 696 |                330 |             248 |                82 |             121.4 |                           0.1583 |                        1 |           1 |
| as_taught_1m | sb_london |                  530 |                529 |                             1 |                             187 |                             35.35 |                          92 |                            17.39 |                                92 |                                 17.39 |                 277 |                130 |              92 |                38 |              45   |                           0.1739 |                        1 |           1 |
| as_taught_1m | sb_ny_am  |                  530 |                528 |                             2 |                             124 |                             23.48 |                          77 |                            14.58 |                                77 |                                 14.58 |                 227 |                 96 |              77 |                19 |              37.7 |                           0.1458 |                        1 |           1 |
| as_taught_1m | sb_ny_pm  |                  530 |                510 |                            20 |                             127 |                             24.9  |                          79 |                            15.49 |                                79 |                                 15.49 |                 192 |                104 |              79 |                25 |              38.7 |                           0.1549 |                        1 |           1 |
| as_traded    | all       |                 1590 |               1567 |                            23 |                             786 |                             50.16 |                         438 |                            27.95 |                               322 |                                 60.87 |                1526 |                623 |             463 |               160 |             226.7 |                           0.2955 |                        2 |          10 |
| as_traded    | sb_london |                  530 |                529 |                             1 |                             316 |                             59.74 |                         166 |                            31.38 |                               166 |                                 31.38 |                 598 |                243 |             174 |                69 |              85.2 |                           0.3289 |                        2 |          10 |
| as_traded    | sb_ny_am  |                  530 |                528 |                             2 |                             237 |                             44.89 |                         130 |                            24.62 |                               130 |                                 24.62 |                 513 |                187 |             137 |                50 |              67.1 |                           0.2595 |                        2 |          10 |
| as_traded    | sb_ny_pm  |                  530 |                510 |                            20 |                             233 |                             45.69 |                         142 |                            27.84 |                               142 |                                 27.84 |                 415 |                193 |             152 |                41 |              74.4 |                           0.298  |                        2 |          10 |


## Why qualifying setups did not become filled trades

| config       |   qualifying_setups |   setups_rejected_at_execution_gate |   setups_blocked_position_open |   setups_blocked_order_pending |   setups_blocked_trade_cap |   setups_duplicate |   submitted_orders |   canceled_orders |   filled_trades |   trades_excluded_roll |
|:-------------|--------------------:|------------------------------------:|-------------------------------:|-------------------------------:|---------------------------:|-------------------:|-------------------:|------------------:|----------------:|-----------------------:|
| as_taught_5m |                 286 |                                  95 |                              6 |                             28 |                         31 |                  0 |                126 |                63 |              63 |                      0 |
| as_taught_1m |                 696 |                                 172 |                              0 |                             32 |                        162 |                  0 |                330 |                82 |             248 |                      0 |
| as_traded    |                1526 |                                 393 |                            361 |                            149 |                          0 |                  0 |                623 |               160 |             463 |                      0 |


## Distribution of filled trades per trading date (dates with at least one eligible window)

| config       |   dates_with_0_trades |   dates_with_1_trades |   dates_with_2_trades |   dates_with_3_trades |   dates_with_4_trades |
|:-------------|----------------------:|----------------------:|----------------------:|----------------------:|----------------------:|
| as_taught_5m |                   466 |                    63 |                     0 |                     0 |                     0 |
| as_taught_1m |                   319 |                   176 |                    30 |                     4 |                     0 |
| as_traded    |                   207 |                   204 |                    97 |                    19 |                     2 |


## No-trade reasons by eligibility gate (windows without a filled trade)

| config       | gate_failed     | reason_short                                |   sb_london |   sb_ny_am |   sb_ny_pm |
|:-------------|:----------------|:--------------------------------------------|------------:|-----------:|-----------:|
| as_taught_1m | bias            | bias_conflict                               |          77 |         66 |         82 |
| as_taught_1m | displacement    | no_displacement_before_window_end           |          60 |         84 |         49 |
| as_taught_1m | entry_fill      | order_expired_unfilled_at_window_end        |          36 |         19 |         22 |
| as_taught_1m | fvg             | no_direction_matching_fvg_before_window_end |           9 |         14 |          7 |
| as_taught_1m | position_free   | position_open                               |           0 |          0 |          5 |
| as_taught_1m | stop            | stop_invalid                                |          59 |         28 |         26 |
| as_taught_1m | sweep           | no_confirmed_sweep_in_window                |         196 |        240 |        240 |
| as_taught_1m | window_eligible | incomplete_window_bars                      |           0 |          1 |         19 |
| as_taught_1m | window_eligible | noncausal_contract_selection                |           1 |          1 |          1 |
| as_taught_5m | bias            | bias_conflict                               |          77 |         66 |         83 |
| as_taught_5m | displacement    | no_displacement_before_window_end           |          60 |         84 |         49 |
| as_taught_5m | entry_fill      | order_expired_unfilled_at_window_end        |          30 |         15 |         18 |
| as_taught_5m | fvg             | no_direction_matching_fvg_before_window_end |         109 |         71 |         88 |
| as_taught_5m | position_free   | position_open                               |           0 |          1 |          3 |
| as_taught_5m | stop            | stop_invalid                                |          30 |         29 |         11 |
| as_taught_5m | sweep           | no_confirmed_sweep_in_window                |         196 |        240 |        244 |
| as_taught_5m | window_eligible | incomplete_window_bars                      |           0 |          1 |         19 |
| as_taught_5m | window_eligible | noncausal_contract_selection                |           1 |          1 |          1 |
| as_traded    | displacement    | no_displacement_before_window_end           |          54 |        104 |         65 |
| as_traded    | entry_fill      | order_expired_unfilled_at_window_end        |          62 |         47 |         36 |
| as_traded    | fvg             | no_direction_matching_fvg_before_window_end |          11 |         18 |         19 |
| as_traded    | position_free   | position_open                               |           0 |          0 |          2 |
| as_traded    | stop            | stop_invalid                                |          88 |         60 |         55 |
| as_traded    | sweep           | no_confirmed_sweep_in_window                |         148 |        169 |        191 |
| as_traded    | window_eligible | incomplete_window_bars                      |           0 |          1 |         19 |
| as_traded    | window_eligible | noncausal_contract_selection                |           1 |          1 |          1 |

