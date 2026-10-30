# Phase 1 — Data Audit: Databento MNQ 1-minute files

Project: ICT Silver Bullet Replication — MNQ (independent of all prior MNQ research)
Audit date: 2026-10-30. Scope: read-only inspection. Original zips were not modified
(extracted copies were made read-only in the session scratch directory).

Source files (as uploaded):
- `1ea1621d-GLBX-20261021-SUW6SDRRS7.zip` — Databento batch job GLBX-20261021-SUW6SDRRS7, 29,093,082 bytes, sha256 15b03359…0395d5485
- `12d14ed2-GLBX-20261021-5QBR9J5GST.zip` — Databento batch job GLBX-20261021-5QBR9J5GST, 11,392,292 bytes, sha256 f397ecc9…e31174f9aa

Full machine-generated detail: `audit/reports/audit_report.md` (+ `.json` and CSV tables).
Script: `audit/data_audit.py` (read-only; rerunnable).

---

## 1. Files, formats, sizes, schemas

| | Job SUW6SDRRS7 | Job 5QBR9J5GST |
|---|---|---|
| Dataset | GLBX.MDP3 (CME Globex MDP 3.0) | GLBX.MDP3 |
| Schema | ohlcv-1m | ohlcv-1m |
| Requested symbol / stype_in | `MNQ.FUT` / parent | `MNQ.FUT` / parent |
| stype_out | instrument_id | instrument_id |
| Query range (UTC) | 2022-10-01 00:00 → 2025-10-02 00:00 | 2025-10-01 00:00 → 2026-10-21 00:00 |
| Encoding / compression | DBN v3 / zstd | DBN v3 / zstd |
| split_symbols | true (one file per instrument) | true |
| map_symbols / pretty_px / pretty_ts | false / false / false (raw fixed-point prices, ns timestamps; the client maps symbols from embedded metadata) | same |
| Data files | 44 `.dbn.zst` (17 outrights, 27 calendar spreads) | 22 `.dbn.zst` (8 outrights, 14 spreads) |
| Sidecar files | metadata.json, manifest.json (sha256 per file), condition.json | same |

Total: 66 DBN files, 40.3 MB compressed. Only the 25 outright files matter for a
continuous series; the 41 calendar-spread files (e.g. `MNQZ5-MNQH6`) are the exchange-listed
spread instruments that parent symbology sweeps in. They can be ignored or used later as
an independent check on roll offsets.

Because parent symbology was used, every outright file is a single raw contract
(stype_in in each file's own metadata = `raw_symbol`, exactly one instrument_id per file).

## 2. Earliest / latest timestamps (America/New_York)

- Earliest bar: **2022-10-02 18:00 ET** (Sunday Globex open; nothing lost at the start since the query began on a Saturday).
- Latest bar: **2026-10-20 19:59 ET** (query end was 2026-10-21 00:00 UTC = 20:00 ET, so the final evening session is truncated; the last complete CME trading date is 2026-10-20).
- Timestamps are bar-open times: every session starts at 18:00:00 and ends at 16:59:00 ET, all timestamps are minute-aligned (no second/sub-second components).
- The two jobs overlap on 2025-09-30 20:00 → 2025-10-01 19:59 ET. 2,025 duplicate (symbol, minute) keys, OHLCV identical on every one. Safe to de-duplicate by keeping either copy.

## 3. Trading days and bar counts

| Measure | Value |
|---|---|
| Span | 1,479 calendar days (~4.05 years) |
| Rows across all outright files (before de-dup) | 2,317,016 |
| Bars after de-dup, all 20 outright contracts | 2,314,991 |
| Unique minutes with at least one MNQ bar | 1,434,205 |
| CME trading dates (18:00 ET open assigned to next date) | 1,048 |
| Weekdays with any RTH (09:30–16:00 ET) bar | 1,044 |
| Weekdays with the full 390 RTH bars | 1,007 |
| Front-month (volume-leader) series bars | 1,434,204 |
| Front-month bars per trading date | median 1,380 (= full 23 h session), min 120 (the truncated last day) |

The 37 weekdays with fewer than 390 RTH bars are all exchange holidays / early closes
(210 bars = trading halted at 13:00 ET; 225 bars = halted at 13:15 ET). The 13 weekdays
with no RTH bar at all are Christmas, New Year's Day, Good Friday (2024, 2025 fully closed;
2023 and 2026 open until 09:14 ET) and 2025-01-09 (open until 09:29 ET). None of these are
data defects.

## 4. Individual contract vs continuous vs back-adjusted

**Individual contracts, raw exchange prices. Not continuous, not back-adjusted.** Evidence:
- One instrument_id per file; file-level stype_in = raw_symbol; no `MNQ.c.*`/`.n.*`/`.v.*` continuous symbols were requested.
- At the same minute, adjacent contracts differ by the carry spread (e.g. 2025-12-16 16:59 ET: MNQZ5 25,084.75 vs MNQH6 25,321.50). A stitched or adjusted series would not show two prices per minute.
- All 2.3 M bars are on the 0.25-point tick grid (0 off-tick prices); back-adjusted series usually are not.
- No contract's file contains prices from any other contract.

## 5. Contract symbols and rollover information

20 outright contracts: MNQZ2, H3, M3, U3, Z3, H4, M4, U4, Z4, H5, M5, U5, Z5, H6, M6, U6, Z6, H7, M7, U7.
Every quarterly contract from Z2 through Z6 has full life-cycle coverage ending at its 09:29 ET expiry-day
bar. H7/M7/U7 are thin back months still trading.

Instrument IDs are **not** stable identifiers across time (e.g. MNQM4 = 10, MNQH4 = 7101, MNQH5 = 42003617);
use the contract symbol, not instrument_id, as the key.

**No vendor roll information exists in these files.** Parent symbology carries no continuous-contract
mapping, so a roll log must be derived. The audit derived a volume-leadership roll log (first CME
trading date on which the next contract out-traded the current one):

| New front from | Roll | New front from | Roll |
|---|---|---|---|
| 2022-12-12 | Z2→H3 | 2024-12-17 | Z4→H5 |
| 2023-03-13 | H3→M3 | 2025-03-18 | H5→M5 |
| 2023-06-12 | M3→U3 | 2025-06-16 | M5→U5 |
| 2023-09-11 | U3→Z3 | 2025-09-16 | U5→Z5 |
| 2023-12-12 | Z3→H4 | 2025-12-16 | Z5→H6 |
| 2024-03-11 | H4→M4 | 2026-03-17 | H6→M6 |
| 2024-06-17 | M4→U4 | 2026-06-15 | M6→U6 |
| 2024-09-16 | U4→Z4 | 2026-09-15 | U6→Z6 |

Every transition is a clean single crossover (no flip-flops). Rolls land on the Monday or Tuesday
of expiry week, 3–4 sessions before the Friday 09:30 ET expiry. Several crossovers are near-ties the
day before (e.g. 2023-12-11: 493,930 vs 492,566), so a different roll rule (fixed calendar offset,
open-interest, Databento `.v.0` vs `.n.0`) would move some roll dates by a day or two. **The roll rule
must come from the methodology being replicated, not from this audit.**

Price offsets at each derived roll (new-contract close minus old-contract close at 16:59 ET on the
roll date) range from +116.50 (Dec 2022) to +299.75 (Jun 2026) points; the full table is in
`audit/reports/roll_price_offsets.csv`. Both contracts trade every one of the 1,380 session minutes on
every roll date, so any reference minute can be used for the adjustment.

## 6. Data-quality issues

Clean on every structural check, all contracts: 0 duplicate timestamps, 0 non-monotonic rows,
0 sub-minute or misaligned intervals, 0 OHLC inconsistencies (high < low, etc.), 0 non-positive
prices, 0 off-tick prices, 0 zero-volume bars, 0 NaN fields.

Databento emits a bar only for minutes with at least one trade. Consequently back-month files
are sparse (expected, not data loss) and the audit evaluates gaps on the front-month series only.
Front-month gaps ≥ 2 min outside the 17:00–18:00 ET break and weekend closure: 54, of which
50 are holidays / early closes. The four that are **not** explained by the exchange calendar:

| Window (ET) | Length | Contract | Other MNQ instruments in the window | Assessment |
|---|---|---|---|---|
| 2025-11-27 21:45 → 2025-11-28 08:29 | 645 min | MNQZ5 | none (whole MNQ complex silent) | Real hole, Thanksgiving night. Databento's condition.json flags 2025-11-28 as **degraded**. The 03:00–04:00 London window on 2025-11-28 is entirely absent. Must be excluded, not interpolated. |
| 2025-04-02 18:00 → 18:01 | 2 min | MNQM5 | none; first bar of every instrument is 18:02 | Reopen after the 2025-04-02 tariff announcement; cause (exchange-side vs vendor) not determinable from the data. |
| 2022-12-13 08:31 | 1 min | MNQH3 | MNQZ2 also lacks 08:31 | One missing minute at the CPI release; cause not determinable. |
| 2025-04-02 16:31 | 1 min | MNQM5 | MNQU5 also lacks it | One missing minute; cause not determinable. |

Two further 1-minute holes (2022-12-11 23:34 MNQH3, 2023-07-03 18:48 MNQU3) occur while another
contract or the same contract on a holiday evening is simply not trading; benign.

Databento condition.json flags 11 dates as degraded. Eight of them show complete front-month data
(2024-09-18, 2025-09-17, 2025-09-24, 2026-03-16, 2026-04-10 are full 1,380-bar weekdays; 2026-01-31,
2026-03-21, 2026-08-29 are Saturdays; 2026-03-15 and 2026-05-24 are full Sunday evenings). Only
2025-11-28 shows actual missing data. The degraded flag should still be carried as a per-day
attribute in the processed dataset.

## 7. Can we reconstruct the three required outputs from these files?

| Output | Feasible? | Basis |
|---|---|---|
| Unadjusted continuous series | **Yes** | Every front contract from Z2 to Z6 has complete coverage through expiry, and the next contract is always fully traded before the roll. Only a roll rule is needed. |
| Back-adjusted continuous series | **Yes** | At every roll both contracts have all 1,380 minutes, so an additive (or ratio) offset can be measured at any chosen reference minute. Which adjustment method and reference minute to use must match the methodology being replicated. |
| Accurate contract-roll log | **Yes, derived; no, vendor-supplied** | A roll log can be computed from the data under any stated rule (volume crossover shown above). The files contain no Databento/CME roll mapping, so "accurate" means "accurate under the chosen rule". If the source methodology used a vendor continuous symbol, that vendor's rule must be obtained. |

## 8. Two-year untouched chronological holdout

Coverage runs 2022-10-02 → 2026-10-20 (≈4.05 years, 1,048 trading dates).

| Split (last 2 years held out) | Dates | Trading dates |
|---|---|---|
| In-sample / development | 2022-10-02 → 2024-10-18 | 530 |
| Holdout (untouched) | 2024-10-21 → 2026-10-20 | 518 |

A two-year holdout is **supported, but it halves the usable history**: development gets ~2.0 years
(roughly 8 quarterly contracts, 2 Thanksgiving/Christmas seasons, 1 full annual cycle of each
macro-event type). Expect modest trade counts per session window; the holdout decision should be
locked before any rule is tested so the split is not re-drawn later. Earlier data could be
purchased to lengthen the in-sample without touching the holdout.

## Missing requirements before building the pipeline

1. **The source methodology document.** It is not in this repository. Needed to pin down: timeframe(s),
   session windows and timezone, roll rule, whether prices were adjusted, how holidays/early closes
   were handled, and the exact Silver Bullet definitions.
2. **Roll rule** (volume crossover as derived here vs fixed calendar day vs open interest vs vendor
   `.v.0`/`.n.0`). Changes several roll dates by 1–2 days and changes which contract's bars appear in
   those sessions.
3. **Adjustment method** for the back-adjusted series (additive vs ratio, reference minute,
   forward vs backward).
4. **Treatment rules** for: the 2025-11-28 hole, the 1–2 minute holes, early-close days, and the
   truncated final day 2026-10-21.
5. **Holdout boundary** confirmed and recorded before any research.
6. Optional: a Databento `definition` schema pull (expiry dates, tick size, contract multiplier per
   instrument) if the pipeline is to verify expiries rather than infer them from last-bar times.
   Network access to databento.com is blocked in this session, so vendor documentation could not be
   fetched here; the timestamp-convention conclusion above rests on the data itself.
