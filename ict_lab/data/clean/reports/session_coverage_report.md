# Session coverage report (observed from bars)

- Sessions: 1048; observed complete: 1004; first: 2022-10-03; last: 2026-10-21
- Observed coverage and official calendar classification are separate attributes; see 'By calendar status'.

## By year

|   trading_date |   sessions |   complete |   eligible_rth |   eligible_sb_london |   eligible_sb_ny_am |   eligible_sb_ny_pm |
|---------------:|-----------:|-----------:|---------------:|---------------------:|--------------------:|--------------------:|
|           2022 |         64 |         61 |             61 |                   63 |                  63 |                  61 |
|           2023 |        258 |        248 |            248 |                  258 |                 257 |                 248 |
|           2024 |        259 |        249 |            249 |                  259 |                 259 |                 249 |
|           2025 |        258 |        245 |            247 |                  257 |                 257 |                 247 |
|           2026 |        209 |        201 |            201 |                  208 |                 207 |                 201 |

## By observed status

| observed_session_status                     |   sessions |
|:--------------------------------------------|-----------:|
| complete                                    |       1004 |
| observed_early_close                        |         38 |
| observed_internal_gaps                      |          2 |
| observed_early_close+observed_internal_gaps |          2 |
| observed_late_open                          |          1 |
| truncated_final_session                     |          1 |

## By calendar status (official CME calendar; unverified until configs/cme_calendar_verified.csv is populated)

| calendar_status     |   sessions |
|:--------------------|-----------:|
| calendar_unverified |       1048 |

## Sessions with at least one ineligible window

| trading_date        | active_symbol   |   n_bars | observed_session_status                     | calendar_status     | noncausal_contract_selection   | eligible_rth   | eligible_sb_london   | eligible_sb_ny_am   | eligible_sb_ny_pm   |
|:--------------------|:----------------|---------:|:--------------------------------------------|:--------------------|:-------------------------------|:---------------|:---------------------|:--------------------|:--------------------|
| 2022-10-03 00:00:00 | MNQZ2           |     1380 | complete                                    | calendar_unverified | True                           | False          | False                | False               | False               |
| 2022-11-24 00:00:00 | MNQZ2           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2022-11-25 00:00:00 | MNQZ2           |     1155 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2023-01-16 00:00:00 | MNQH3           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2023-02-20 00:00:00 | MNQH3           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2023-04-07 00:00:00 | MNQM3           |      915 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | False               | False               |
| 2023-05-29 00:00:00 | MNQM3           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2023-06-19 00:00:00 | MNQU3           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2023-07-03 00:00:00 | MNQU3           |     1155 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2023-07-04 00:00:00 | MNQU3           |     1139 | observed_early_close+observed_internal_gaps | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2023-09-04 00:00:00 | MNQU3           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2023-11-23 00:00:00 | MNQZ3           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2023-11-24 00:00:00 | MNQZ3           |     1155 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2024-01-15 00:00:00 | MNQH4           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2024-02-19 00:00:00 | MNQH4           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2024-05-27 00:00:00 | MNQM4           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2024-06-19 00:00:00 | MNQU4           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2024-07-03 00:00:00 | MNQU4           |     1155 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2024-07-04 00:00:00 | MNQU4           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2024-09-02 00:00:00 | MNQU4           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2024-11-28 00:00:00 | MNQZ4           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2024-11-29 00:00:00 | MNQZ4           |     1155 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2024-12-24 00:00:00 | MNQH5           |     1155 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2025-01-09 00:00:00 | MNQH5           |      930 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | False               | False               |
| 2025-01-20 00:00:00 | MNQH5           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2025-02-17 00:00:00 | MNQH5           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2025-05-26 00:00:00 | MNQM5           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2025-06-19 00:00:00 | MNQU5           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2025-07-03 00:00:00 | MNQU5           |     1155 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2025-07-04 00:00:00 | MNQU5           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2025-09-01 00:00:00 | MNQU5           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2025-11-27 00:00:00 | MNQZ5           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2025-11-28 00:00:00 | MNQZ5           |      510 | observed_early_close+observed_internal_gaps | calendar_unverified | False                          | False          | False                | True                | False               |
| 2025-12-24 00:00:00 | MNQH6           |     1155 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2026-01-19 00:00:00 | MNQH6           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2026-02-16 00:00:00 | MNQH6           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2026-04-03 00:00:00 | MNQM6           |      915 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | False               | False               |
| 2026-05-25 00:00:00 | MNQM6           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2026-06-19 00:00:00 | MNQU6           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2026-07-03 00:00:00 | MNQU6           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2026-09-07 00:00:00 | MNQU6           |     1140 | observed_early_close                        | calendar_unverified | False                          | False          | True                 | True                | False               |
| 2026-10-21 00:00:00 | MNQZ6           |      120 | truncated_final_session                     | calendar_unverified | False                          | False          | False                | False               | False               |
