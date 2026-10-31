# Layer 4 verification

## Automated verification

- Full suite: 159 tests collected across Layers 1–4, 159 passed, 0 failed (includes the Layer 1 deterministic rebuild,
  Layer 2 truncation test, Layer 3 cached-vs-recomputed equivalence and the Layer 4 chronological truncation test).
- Layer 4 tests (`tests/test_l4_*.py`, 21 functions): named-config loading and deterministic hashes, liquidity universes
  (no 1m swings, universe controls sweeps and targets), schema rejections (disabled stop, lookahead bias, bad caps/windows),
  deterministic setup enumeration, multiple trades per window with count reconciliation, hard cap 10 and one-trade mode
  (first trade identical under any cap), no overlap / no simultaneous orders / no reuse of sweeps or FVGs, independent window
  allowances and window assignment, consumed-level and 15m-swing activation causality, chronological truncation consistency.
- Layer 3 baseline regression: 36 trades, identical content hash before and after the multi-trade extension.
- Holdout: never accessed (all stores built through the Layer 1 development loader; manifests record `holdout_accessed: false`).

## Manual verification — named configurations, development period

Each reviewed trade shows the chronological feature sequence and surrounding 1-minute bars, and is re-derived by an independent naive replay (`REPLAY OK`). Stop mode is the documented substitution `displacement_candle_extreme`. No trade is fabricated; categories absent from the data are reported as such.

**Summary:** 10 items reviewed, 0 discrepancies. Multi-trade windows present in as_traded: 25 trades with rank ≥ 2.


## [first qualifying FVG (setup rank 0, trade #1) — 5m FVG] as_taught_5m — T00001_2022-10-05_sb_london bullish — REPLAY OK

- bias bullish; sweep of swing_15m_low @ 15177.00: penetration 03:00 ET, confirmed 03:01
- displacement candle (gate) confirmed 03:02 (ratio 3.23); stop reference candle 03:30 extreme 15162.00
- FVG 5m 15173.25–15182.25 confirmed 03:40; setup rank in window 0, trade #1 in window
- order active 03:40, limit 15177.75; filled 03:55 @ 15177.75; stop 15161.75; target 15202.50 (opposing_liquidity, fallback=False); risk 16.00 pts, reward 1.55R planned
- exit 04:10 @ 15161.50 (stop); ambiguous=False; gap_during_trade=False; contract MNQZ2 (unadjusted entry 11571.50)

```
   ny     open     high      low    close  unadj_close  consecutive_prev   mark
03:37 15195.00 15197.50 15191.00 15197.00     11590.75              True       
03:38 15197.50 15200.00 15191.50 15193.00     11586.75              True       
03:39 15193.00 15195.75 15186.75 15188.00     11581.75              True       
03:40 15188.25 15193.50 15187.25 15193.00     11586.75              True ACTIVE
03:41 15193.00 15198.25 15189.75 15197.00     11590.75              True       
03:42 15196.50 15197.75 15186.75 15187.25     11581.00              True       
03:43 15187.50 15190.00 15184.75 15188.00     11581.75              True       
03:44 15188.25 15192.50 15184.25 15190.50     11584.25              True       
03:45 15191.25 15194.50 15186.00 15192.50     11586.25              True       
03:46 15192.50 15194.50 15185.75 15191.00     11584.75              True       
03:47 15191.00 15194.25 15187.25 15190.50     11584.25              True       
03:48 15190.50 15194.50 15187.25 15192.25     11586.00              True       
03:49 15192.25 15198.00 15190.50 15195.75     11589.50              True       
03:50 15195.50 15195.50 15188.25 15191.50     11585.25              True       
03:51 15192.25 15195.75 15189.00 15194.50     11588.25              True       
03:52 15194.50 15199.25 15191.50 15193.00     11586.75              True       
03:53 15193.00 15195.50 15188.50 15188.75     11582.50              True       
03:54 15189.25 15189.50 15181.75 15184.00     11577.75              True       
03:55 15184.50 15187.50 15177.25 15177.75     11571.50              True   FILL
03:56 15177.25 15183.25 15173.50 15174.00     11567.75              True       
03:57 15174.00 15178.75 15171.25 15174.00     11567.75              True       
03:58 15173.50 15174.50 15170.00 15171.00     11564.75              True       
03:59 15171.00 15173.75 15168.75 15172.00     11565.75              True       
04:00 15172.50 15175.75 15170.50 15172.25     11566.00              True       
04:01 15172.00 15178.00 15171.50 15175.00     11568.75              True       
04:02 15174.75 15183.00 15174.50 15175.25     11569.00              True       
04:03 15175.50 15178.00 15168.50 15171.50     11565.25              True       
04:04 15171.25 15177.75 15171.00 15175.00     11568.75              True       
04:05 15175.25 15176.25 15171.25 15173.00     11566.75              True       
04:06 15173.50 15175.50 15169.50 15170.25     11564.00              True       
04:07 15170.25 15171.50 15165.75 15166.50     11560.25              True       
04:08 15166.75 15169.00 15164.75 15167.25     11561.00              True       
04:09 15167.25 15170.00 15165.75 15167.00     11560.75              True       
04:10 15166.50 15167.00 15161.00 15163.00     11556.75              True   EXIT
04:11 15162.75 15163.75 15155.50 15156.25     11550.00              True       
04:12 15156.75 15159.00 15154.25 15157.00     11550.75              True       
```

## [1-minute FVG] as_taught_1m — T00001_2022-10-05_sb_london bullish — REPLAY OK

- bias bullish; sweep of swing_15m_low @ 15177.00: penetration 03:00 ET, confirmed 03:01
- displacement candle (gate) confirmed 03:02 (ratio 3.23); stop reference candle 03:04 extreme 15166.50
- FVG 1m 15177.00–15181.50 confirmed 03:06; setup rank in window 0, trade #1 in window
- order active 03:06, limit 15179.25; filled 03:06 @ 15179.25; stop 15166.25; target 15204.50 (opposing_liquidity, fallback=False); risk 13.00 pts, reward 1.94R planned
- exit 03:08 @ 15166.00 (stop); ambiguous=False; gap_during_trade=False; contract MNQZ2 (unadjusted entry 11573.00)

```
   ny     open     high      low    close  unadj_close  consecutive_prev        mark
03:03 15177.00 15177.00 15165.50 15166.25     11560.00              True            
03:04 15167.00 15185.00 15166.50 15184.00     11577.75              True            
03:05 15183.50 15189.75 15181.50 15184.25     11578.00              True            
03:06 15184.50 15185.00 15175.25 15178.50     11572.25              True ACTIVE,FILL
03:07 15178.50 15181.50 15168.50 15170.50     11564.25              True            
03:08 15170.00 15170.75 15164.00 15164.50     11558.25              True        EXIT
03:09 15165.00 15170.00 15164.75 15165.75     11559.50              True            
03:10 15165.25 15176.50 15165.25 15175.50     11569.25              True            
```

## [15-minute liquidity swing sweep (bsl_ssl_15m universe)] as_taught_5m — T00002_2022-10-10_sb_ny_am bullish — REPLAY OK

- bias bullish; sweep of swing_15m_low @ 14601.25: penetration 10:04 ET, confirmed 10:05
- displacement candle (gate) confirmed 10:16 (ratio 1.66); stop reference candle 10:15 extreme 14594.75
- FVG 5m 14611.25–14622.00 confirmed 10:25; setup rank in window 0, trade #1 in window
- order active 10:25, limit 14616.50; filled 10:25 @ 14616.50; stop 14594.50; target 14742.75 (opposing_liquidity, fallback=False); risk 22.00 pts, reward 5.74R planned
- exit 10:37 @ 14594.25 (stop); ambiguous=False; gap_during_trade=False; contract MNQZ2 (unadjusted entry 11010.25)

```
   ny     open     high      low    close  unadj_close  consecutive_prev        mark
10:22 14632.00 14641.25 14629.00 14636.00     11029.75              True            
10:23 14636.50 14640.00 14628.25 14637.50     11031.25              True            
10:24 14637.50 14638.25 14625.25 14626.75     11020.50              True            
10:25 14626.75 14629.25 14615.25 14628.50     11022.25              True ACTIVE,FILL
10:26 14628.50 14645.50 14620.25 14642.75     11036.50              True            
10:27 14643.00 14674.50 14642.75 14657.00     11050.75              True            
10:28 14656.75 14657.50 14646.75 14651.75     11045.50              True            
10:29 14651.00 14653.75 14633.75 14646.25     11040.00              True            
10:30 14647.00 14651.00 14627.25 14647.75     11041.50              True            
10:31 14647.50 14661.25 14639.50 14640.75     11034.50              True            
10:32 14641.00 14647.00 14618.00 14618.50     11012.25              True            
10:33 14618.75 14618.75 14604.25 14610.25     11004.00              True            
10:34 14610.50 14618.75 14603.75 14609.00     11002.75              True            
10:35 14609.00 14615.00 14600.50 14609.00     11002.75              True            
10:36 14609.00 14614.75 14598.25 14599.25     10993.00              True            
10:37 14599.50 14609.25 14581.75 14584.25     10978.00              True        EXIT
10:38 14584.00 14584.25 14567.50 14569.25     10963.00              True            
10:39 14569.50 14571.00 14558.50 14560.50     10954.25              True            
```

## [multiple trades within one window (trade #2)] as_traded — T00008_2022-10-14_sb_ny_am bullish — REPLAY OK

- bias none; sweep of swing_15m_low @ 14520.25: penetration 10:12 ET, confirmed 10:13
- displacement candle (gate) confirmed 10:29 (ratio 2.15); stop reference candle 10:28 extreme 14487.25
- FVG 1m 14502.00–14522.50 confirmed 10:30; setup rank in window 2, trade #2 in window
- order active 10:30, limit 14512.25; filled 10:39 @ 14512.25; stop 14487.00; target 14562.75 (fixed_2.0R, fallback=False); risk 25.25 pts, reward 2.00R planned
- exit 10:43 @ 14486.75 (stop); ambiguous=False; gap_during_trade=False; contract MNQZ2 (unadjusted entry 10906.00)

```
   ny     open     high      low    close  unadj_close  consecutive_prev   mark
10:27 14502.00 14502.00 14480.00 14491.00     10884.75              True       
10:28 14490.50 14545.25 14487.25 14543.00     10936.75              True       
10:29 14543.00 14544.25 14522.50 14526.50     10920.25              True       
10:30 14526.50 14536.25 14516.50 14533.00     10926.75              True ACTIVE
10:31 14533.25 14555.00 14518.75 14549.00     10942.75              True       
10:32 14548.75 14549.25 14535.75 14546.00     10939.75              True       
10:33 14546.00 14552.75 14529.75 14534.75     10928.50              True       
10:34 14534.75 14536.50 14514.50 14516.50     10910.25              True       
10:35 14515.75 14533.50 14514.75 14522.00     10915.75              True       
10:36 14522.25 14540.75 14520.25 14536.50     10930.25              True       
10:37 14536.00 14546.25 14526.25 14532.50     10926.25              True       
10:38 14532.25 14535.75 14519.75 14523.75     10917.50              True       
10:39 14523.25 14526.00 14502.00 14519.50     10913.25              True   FILL
10:40 14519.00 14540.75 14516.75 14526.75     10920.50              True       
10:41 14526.50 14528.75 14501.00 14507.00     10900.75              True       
10:42 14506.50 14517.00 14489.25 14493.00     10886.75              True       
10:43 14492.75 14494.50 14472.00 14482.25     10876.00              True   EXIT
10:44 14481.75 14486.50 14462.50 14466.00     10859.75              True       
10:45 14465.25 14473.50 14460.50 14465.25     10859.00              True       
```

## [multiple trades within one window (trade #2)] as_traded — T00052_2022-12-23_sb_london bullish — REPLAY OK

- bias none; sweep of swing_15m_low @ 14531.25: penetration 03:07 ET, confirmed 03:11
- displacement candle (gate) confirmed 03:50 (ratio 1.53); stop reference candle 03:49 extreme 14526.50
- FVG 1m 14528.25–14530.00 confirmed 03:51; setup rank in window 1, trade #2 in window
- order active 03:51, limit 14529.00; filled 03:51 @ 14529.00; stop 14526.25; target 14534.50 (fixed_2.0R, fallback=False); risk 2.75 pts, reward 2.00R planned
- exit 03:56 @ 14534.50 (target); ambiguous=False; gap_during_trade=False; contract MNQH3 (unadjusted entry 11039.25)

```
   ny     open     high      low    close  unadj_close  consecutive_prev        mark
03:48 14528.00 14528.25 14526.00 14527.00     11037.25              True            
03:49 14526.50 14534.25 14526.50 14534.00     11044.25              True            
03:50 14534.00 14534.75 14530.00 14530.00     11040.25              True            
03:51 14530.50 14531.50 14528.75 14529.50     11039.75              True ACTIVE,FILL
03:52 14530.75 14531.50 14529.00 14529.25     11039.50              True            
03:53 14529.50 14532.50 14528.75 14528.75     11039.00              True            
03:54 14528.50 14531.75 14528.00 14530.50     11040.75              True            
03:55 14530.75 14533.75 14529.75 14533.00     11043.25              True            
03:56 14533.75 14541.50 14533.75 14537.50     11047.75              True        EXIT
03:57 14537.25 14541.25 14536.75 14539.50     11049.75              True            
03:58 14539.75 14540.25 14535.00 14535.00     11045.25              True            
```

## [liquidity-target selection (opposing 15m swing)] as_taught_5m — T00003_2022-10-20_sb_ny_am bearish — REPLAY OK

- bias none; sweep of swing_15m_high @ 14890.75: penetration 10:09 ET, confirmed 10:10
- displacement candle (gate) confirmed 10:31 (ratio 1.79); stop reference candle 10:31 extreme 14908.50
- FVG 5m 14899.25–14899.50 confirmed 10:40; setup rank in window 0, trade #1 in window
- order active 10:40, limit 14899.50; filled 10:40 @ 14899.50; stop 14908.75; target 14688.50 (opposing_liquidity, fallback=False); risk 9.25 pts, reward 22.81R planned
- exit 10:57 @ 14909.00 (stop); ambiguous=False; gap_during_trade=False; contract MNQZ2 (unadjusted entry 11293.25)

```
   ny     open     high      low    close  unadj_close  consecutive_prev        mark
10:37 14885.50 14890.50 14879.00 14888.00     11281.75              True            
10:38 14888.50 14899.25 14887.75 14896.75     11290.50              True            
10:39 14897.50 14898.50 14890.50 14898.25     11292.00              True            
10:40 14898.00 14902.00 14883.00 14886.75     11280.50              True ACTIVE,FILL
10:41 14887.25 14889.00 14868.50 14880.25     11274.00              True            
10:42 14880.50 14882.75 14871.25 14878.00     11271.75              True            
10:43 14877.75 14893.00 14877.50 14889.00     11282.75              True            
10:44 14889.00 14892.25 14882.25 14889.50     11283.25              True            
10:45 14888.75 14897.50 14885.75 14894.50     11288.25              True            
10:46 14894.50 14906.00 14894.25 14903.75     11297.50              True            
10:47 14903.00 14907.00 14898.75 14906.25     11300.00              True            
10:48 14906.00 14906.50 14895.75 14897.75     11291.50              True            
10:49 14897.75 14902.75 14893.25 14895.50     11289.25              True            
10:50 14895.50 14906.75 14887.00 14891.25     11285.00              True            
10:51 14891.00 14905.75 14888.50 14899.50     11293.25              True            
10:52 14899.75 14905.25 14893.25 14896.25     11290.00              True            
10:53 14895.25 14900.75 14891.00 14893.25     11287.00              True            
10:54 14893.00 14895.75 14884.00 14885.25     11279.00              True            
10:55 14885.25 14901.25 14884.50 14890.75     11284.50              True            
10:56 14890.75 14901.75 14888.50 14898.25     11292.00              True            
10:57 14897.75 14922.25 14897.75 14921.50     11315.25              True        EXIT
10:58 14921.25 14925.00 14915.25 14922.50     11316.25              True            
10:59 14922.50 14925.00 14915.25 14924.25     11318.00              True            
```

## [fixed 2R fallback (no eligible opposing liquidity)] as_taught_1m — T00035_2023-02-02_sb_ny_pm bullish — REPLAY OK

- bias none; sweep of swing_15m_low @ 16261.00: penetration 14:34 ET, confirmed 14:35
- displacement candle (gate) confirmed 14:38 (ratio 1.93); stop reference candle 14:37 extreme 16250.75
- FVG 1m 16259.25–16273.75 confirmed 14:39; setup rank in window 0, trade #1 in window
- order active 14:39, limit 16266.50; filled 14:39 @ 16266.50; stop 16250.50; target 16298.50 (fallback_fixed_2.0R, fallback=True); risk 16.00 pts, reward 2.00R planned
- exit 14:42 @ 16250.25 (stop); ambiguous=False; gap_during_trade=False; contract MNQH3 (unadjusted entry 12776.75)

```
   ny     open     high      low    close  unadj_close  consecutive_prev        mark
14:36 16252.50 16259.25 16245.00 16253.50     12763.75              True            
14:37 16253.50 16278.50 16250.75 16276.75     12787.00              True            
14:38 16276.50 16284.75 16273.75 16283.50     12793.75              True            
14:39 16283.00 16283.25 16259.00 16264.25     12774.50              True ACTIVE,FILL
14:40 16263.75 16270.50 16255.00 16255.75     12766.00              True            
14:41 16255.25 16268.25 16254.75 16263.00     12773.25              True            
14:42 16262.75 16263.25 16244.50 16246.50     12756.75              True        EXIT
14:43 16246.50 16254.25 16244.00 16247.25     12757.50              True            
14:44 16248.00 16261.50 16246.00 16260.25     12770.50              True            
```

## [time-based exit (RTH end)] as_taught_1m — T00021_2022-12-08_sb_ny_pm bullish — REPLAY OK

- bias none; sweep of swing_15m_low @ 15203.50: penetration 14:05 ET, confirmed 14:06
- displacement candle (gate) confirmed 14:10 (ratio 1.61); stop reference candle 14:09 extreme 15195.00
- FVG 1m 15211.00–15212.25 confirmed 14:18; setup rank in window 0, trade #1 in window
- order active 14:18, limit 15211.50; filled 14:29 @ 15211.50; stop 15194.75; target 15291.75 (opposing_liquidity, fallback=False); risk 16.75 pts, reward 4.79R planned
- exit 16:00 @ 15251.50 (time_exit_rth); ambiguous=False; gap_during_trade=False; contract MNQZ2 (unadjusted entry 11605.25)

```
   ny     open     high      low    close  unadj_close  consecutive_prev   mark
14:15 15210.50 15211.00 15202.50 15203.50     11597.25              True       
14:16 15203.25 15213.00 15200.50 15212.50     11606.25              True       
14:17 15212.25 15222.75 15212.25 15219.75     11613.50              True       
14:18 15219.75 15223.00 15216.50 15219.50     11613.25              True ACTIVE
14:19 15219.50 15220.00 15214.75 15215.00     11608.75              True       
14:20 15215.00 15217.75 15212.00 15215.00     11608.75              True       
14:21 15215.25 15221.00 15214.25 15215.75     11609.50              True       
14:22 15215.75 15223.50 15215.50 15223.25     11617.00              True       
14:23 15222.75 15228.50 15222.25 15223.00     11616.75              True       
14:24 15223.00 15225.00 15219.00 15223.50     11617.25              True       
14:25 15223.25 15229.75 15222.00 15228.00     11621.75              True       
14:26 15228.00 15229.50 15225.25 15229.25     11623.00              True       
15:51 15222.50 15230.25 15216.25 15229.25     11623.00              True       
15:52 15229.50 15241.25 15228.00 15238.75     11632.50              True       
15:53 15238.50 15240.25 15228.50 15229.50     11623.25              True       
15:54 15230.00 15245.75 15229.25 15243.50     11637.25              True       
15:55 15243.50 15249.25 15235.50 15249.00     11642.75              True       
15:56 15249.00 15256.50 15248.00 15254.00     11647.75              True       
15:57 15253.75 15255.25 15244.00 15250.25     11644.00              True       
15:58 15249.75 15254.00 15247.75 15252.75     11646.50              True       
15:59 15253.00 15255.75 15246.50 15252.00     11645.75              True       
16:00 15251.75 15254.50 15248.50 15250.25     11644.00              True   EXIT
16:01 15250.50 15258.00 15250.25 15256.25     11650.00              True       
16:02 15256.25 15258.75 15251.00 15251.50     11645.25              True       
```

## [same-bar ambiguity (stop-first)] as_traded — T00072_2023-02-01_sb_ny_pm bullish — REPLAY OK

- bias none; sweep of swing_15m_low @ 15561.50: penetration 14:00 ET, confirmed 14:01
- displacement candle (gate) confirmed 14:02 (ratio 4.83); stop reference candle 14:05 extreme 15595.25
- FVG 1m 15612.50–15612.75 confirmed 14:07; setup rank in window 0, trade #1 in window
- order active 14:07, limit 15612.50; filled 14:31 @ 15612.50; stop 15595.00; target 15647.50 (fixed_2.0R, fallback=False); risk 17.50 pts, reward 2.00R planned
- exit 14:31 @ 15594.75 (stop); ambiguous=True; gap_during_trade=False; contract MNQH3 (unadjusted entry 12122.75)

```
   ny     open     high      low    close  unadj_close  consecutive_prev      mark
14:04 15594.50 15612.50 15584.75 15599.25     12109.50              True          
14:05 15600.75 15633.75 15595.25 15626.75     12137.00              True          
14:06 15626.50 15630.50 15612.75 15618.25     12128.50              True          
14:07 15619.75 15677.75 15612.75 15662.50     12172.75              True    ACTIVE
14:08 15663.00 15688.50 15655.75 15686.25     12196.50              True          
14:09 15686.50 15687.50 15663.00 15668.75     12179.00              True          
14:10 15668.50 15694.50 15662.25 15674.00     12184.25              True          
14:11 15673.50 15689.00 15663.50 15688.50     12198.75              True          
14:12 15686.50 15693.75 15677.00 15682.50     12192.75              True          
14:13 15682.75 15686.00 15665.75 15678.75     12189.00              True          
14:14 15678.75 15685.25 15667.75 15674.25     12184.50              True          
14:15 15673.75 15680.25 15664.75 15670.00     12180.25              True          
14:16 15669.75 15678.50 15654.00 15657.50     12167.75              True          
14:17 15657.25 15664.75 15631.25 15636.00     12146.25              True          
14:18 15636.50 15649.50 15628.00 15640.00     12150.25              True          
14:19 15640.00 15656.50 15640.00 15652.75     12163.00              True          
14:20 15653.25 15660.25 15650.25 15655.50     12165.75              True          
14:21 15655.75 15669.25 15654.75 15666.50     12176.75              True          
14:22 15666.50 15670.00 15658.50 15661.25     12171.50              True          
14:23 15661.75 15663.50 15651.50 15653.75     12164.00              True          
14:24 15653.75 15659.00 15646.75 15652.50     12162.75              True          
14:25 15653.00 15653.75 15641.25 15646.25     12156.50              True          
14:26 15646.50 15653.50 15643.75 15648.75     12159.00              True          
14:27 15648.00 15655.75 15645.25 15646.75     12157.00              True          
14:28 15647.25 15656.50 15644.75 15655.50     12165.75              True          
14:29 15654.75 15657.50 15636.25 15638.50     12148.75              True          
14:30 15639.00 15660.75 15617.25 15632.00     12142.25              True          
14:31 15633.75 15653.50 15589.25 15590.25     12100.50              True FILL,EXIT
14:32 15591.00 15609.25 15565.50 15579.50     12089.75              True          
14:33 15578.50 15587.75 15549.75 15558.00     12068.25              True          
```

## [overlapping setup rejection — position open] as_traded — 361 occurrences

- example setup `2022-10-05:sb_london:s54:1m:3305:bull` (bullish, swing_15m_low) at 2022-10-05 03:06 ET → outcome `rejected` / `position_open`
- blocking position: T00002_2022-10-05_sb_london filled 03:06 ET, exited 03:08 ET (stop) — the new setup's activation 03:06 is not after the exit bar

## [pending-order block — no simultaneous orders] as_traded — 149 occurrences

- example setup `2022-10-06:sb_london:s78:1m:4730:bull` (bullish, swing_15m_low) at 2022-10-06 03:51 ET → outcome `rejected` / `order_pending`
- pending order: setup `2022-10-06:sb_london:s75:1m:4730:bull` submitted 03:51 ET, never filled, canceled at window end

## [limit order expiration (canceled at window end)] as_taught_5m — 63 occurrences

- example setup `2022-10-06:sb_ny_am:s93:5m:1030:bull` (bullish, swing_15m_low) at 2022-10-06 10:55 ET → outcome `canceled` / `order_expired_unfilled_at_window_end`
- limit 15197.00, 5 bars until window end, traded through: False → VERIFIED never filled