# Layer 4 frequency report — named configurations (development period only)

Research baselines, **not** recommended strategies. Signal frequency (qualifying setups) is reported separately from order submissions and fills. No profitability or performance metrics are computed in this layer.

Stop: user-authorized modification `liquidity_sweep_extreme` (one tick beyond the qualifying sweep's extreme wick) in place of the original, unresolved 'beyond displacement swing' stop.

Development range 2022-10-03 → 2024-10-18 (2.042 years). Ineligible windows (Layer 1 data-quality exclusions, truncated/non-causal sessions) are counted separately from eligible windows without a setup.

## Frequency by configuration and window

| config       | scope     |   windows_registered |   windows_eligible |   windows_ineligible_excluded |   windows_with_qualifying_setup |   pct_eligible_windows_with_setup |   windows_with_filled_trade |   pct_eligible_windows_with_fill |   trading_dates_with_filled_trade |   pct_trading_dates_with_filled_trade |   qualifying_setups |   submitted_orders |   filled_trades |   canceled_orders |   trades_per_year |   avg_trades_per_eligible_window |   max_trades_in_a_window |   trade_cap |
|:-------------|:----------|---------------------:|-------------------:|------------------------------:|--------------------------------:|----------------------------------:|----------------------------:|---------------------------------:|----------------------------------:|--------------------------------------:|--------------------:|-------------------:|----------------:|------------------:|------------------:|---------------------------------:|-------------------------:|------------:|
| as_taught_5m | all       |                 1590 |               1567 |                            23 |                             198 |                             12.64 |                          86 |                             5.49 |                                85 |                                 16.07 |                 286 |                182 |              86 |                96 |              42.1 |                           0.0549 |                        1 |           1 |
| as_taught_5m | sb_london |                  530 |                529 |                             1 |                              87 |                             16.45 |                          36 |                             6.81 |                                36 |                                  6.81 |                 121 |                 75 |              36 |                39 |              17.6 |                           0.0681 |                        1 |           1 |
| as_taught_5m | sb_ny_am  |                  530 |                528 |                             2 |                              66 |                             12.5  |                          30 |                             5.68 |                                30 |                                  5.68 |                 101 |                 65 |              30 |                35 |              14.7 |                           0.0568 |                        1 |           1 |
| as_taught_5m | sb_ny_pm  |                  530 |                510 |                            20 |                              45 |                              8.82 |                          20 |                             3.92 |                                20 |                                  3.92 |                  64 |                 42 |              20 |                22 |               9.8 |                           0.0392 |                        1 |           1 |
| as_taught_1m | all       |                 1590 |               1567 |                            23 |                             438 |                             27.95 |                         257 |                            16.4  |                               228 |                                 43.1  |                 696 |                354 |             257 |                97 |             125.8 |                           0.164  |                        1 |           1 |
| as_taught_1m | sb_london |                  530 |                529 |                             1 |                             187 |                             35.35 |                          98 |                            18.53 |                                98 |                                 18.53 |                 277 |                143 |              98 |                45 |              48   |                           0.1853 |                        1 |           1 |
| as_taught_1m | sb_ny_am  |                  530 |                528 |                             2 |                             124 |                             23.48 |                          80 |                            15.15 |                                80 |                                 15.15 |                 227 |                109 |              80 |                29 |              39.2 |                           0.1515 |                        1 |           1 |
| as_taught_1m | sb_ny_pm  |                  530 |                510 |                            20 |                             127 |                             24.9  |                          79 |                            15.49 |                                79 |                                 15.49 |                 192 |                102 |              79 |                23 |              38.7 |                           0.1549 |                        1 |           1 |
| as_traded    | all       |                 1590 |               1567 |                            23 |                             786 |                             50.16 |                         446 |                            28.46 |                               330 |                                 62.38 |                1526 |                654 |             469 |               185 |             229.6 |                           0.2993 |                        2 |          10 |
| as_traded    | sb_london |                  530 |                529 |                             1 |                             316 |                             59.74 |                         169 |                            31.95 |                               169 |                                 31.95 |                 598 |                264 |             179 |                85 |              87.6 |                           0.3384 |                        2 |          10 |
| as_traded    | sb_ny_am  |                  530 |                528 |                             2 |                             237 |                             44.89 |                         138 |                            26.14 |                               138 |                                 26.14 |                 513 |                202 |             144 |                58 |              70.5 |                           0.2727 |                        2 |          10 |
| as_traded    | sb_ny_pm  |                  530 |                510 |                            20 |                             233 |                             45.69 |                         139 |                            27.25 |                               139 |                                 27.25 |                 415 |                188 |             146 |                42 |              71.5 |                           0.2863 |                        2 |          10 |


## Why qualifying setups did not become filled trades

| config       |   qualifying_setups |   setups_rejected_at_execution_gate |   setups_blocked_position_open |   setups_blocked_order_pending |   setups_blocked_trade_cap |   setups_duplicate |   submitted_orders |   canceled_orders |   filled_trades |   trades_excluded_roll |
|:-------------|--------------------:|------------------------------------:|-------------------------------:|-------------------------------:|---------------------------:|-------------------:|-------------------:|------------------:|----------------:|-----------------------:|
| as_taught_5m |                 286 |                                  33 |                              6 |                             33 |                         32 |                  0 |                182 |                96 |              86 |                      0 |
| as_taught_1m |                 696 |                                 193 |                              1 |                             28 |                        120 |                  0 |                354 |                97 |             257 |                      0 |
| as_traded    |                1526 |                                 404 |                            324 |                            144 |                          0 |                  0 |                654 |               185 |             469 |                      0 |


## Distribution of filled trades per trading date (dates with at least one eligible window)

| config       |   dates_with_0_trades |   dates_with_1_trades |   dates_with_2_trades |   dates_with_3_trades |   dates_with_4_trades |
|:-------------|----------------------:|----------------------:|----------------------:|----------------------:|----------------------:|
| as_taught_5m |                   444 |                    84 |                     1 |                     0 |                     0 |
| as_taught_1m |                   301 |                   202 |                    23 |                     3 |                     0 |
| as_traded    |                   199 |                   213 |                    97 |                    18 |                     2 |


## No-trade reasons by eligibility gate (windows without a filled trade)

| config       | gate_failed     | reason_short                                |   sb_london |   sb_ny_am |   sb_ny_pm |
|:-------------|:----------------|:--------------------------------------------|------------:|-----------:|-----------:|
| as_taught_1m | bias            | bias_conflict                               |          77 |         66 |         83 |
| as_taught_1m | displacement    | no_displacement_before_window_end           |          60 |         84 |         49 |
| as_taught_1m | entry_fill      | order_expired_unfilled_at_window_end        |          43 |         22 |         21 |
| as_taught_1m | fvg             | no_direction_matching_fvg_before_window_end |           9 |         14 |          7 |
| as_taught_1m | position_free   | position_open                               |           0 |          0 |          3 |
| as_taught_1m | stop            | stop_invalid                                |          46 |         22 |         26 |
| as_taught_1m | sweep           | no_confirmed_sweep_in_window                |         196 |        240 |        242 |
| as_taught_1m | window_eligible | incomplete_window_bars                      |           0 |          1 |         19 |
| as_taught_1m | window_eligible | noncausal_contract_selection                |           1 |          1 |          1 |
| as_taught_5m | bias            | bias_conflict                               |          77 |         66 |         83 |
| as_taught_5m | displacement    | no_displacement_before_window_end           |          60 |         84 |         49 |
| as_taught_5m | entry_fill      | order_expired_unfilled_at_window_end        |          38 |         32 |         19 |
| as_taught_5m | fvg             | no_direction_matching_fvg_before_window_end |         109 |         71 |         89 |
| as_taught_5m | position_free   | position_open                               |           0 |          1 |          2 |
| as_taught_5m | stop            | stop_invalid                                |          13 |          4 |          4 |
| as_taught_5m | sweep           | no_confirmed_sweep_in_window                |         196 |        240 |        244 |
| as_taught_5m | window_eligible | incomplete_window_bars                      |           0 |          1 |         19 |
| as_taught_5m | window_eligible | noncausal_contract_selection                |           1 |          1 |          1 |
| as_traded    | displacement    | no_displacement_before_window_end           |          54 |        104 |         65 |
| as_traded    | entry_fill      | order_expired_unfilled_at_window_end        |          73 |         47 |         33 |
| as_traded    | fvg             | no_direction_matching_fvg_before_window_end |          11 |         18 |         19 |
| as_traded    | position_free   | position_open                               |           0 |          0 |          6 |
| as_traded    | stop            | stop_invalid                                |          74 |         52 |         58 |
| as_traded    | sweep           | no_confirmed_sweep_in_window                |         148 |        169 |        190 |
| as_traded    | window_eligible | incomplete_window_bars                      |           0 |          1 |         19 |
| as_traded    | window_eligible | noncausal_contract_selection                |           1 |          1 |          1 |

