# Layer 4 manual verification — named configurations, development period

Each reviewed trade shows the chronological feature sequence and surrounding 1-minute bars, and is re-derived by an independent naive replay (`REPLAY OK`). Stop mode is the user-authorized modification `liquidity_sweep_extreme`. No trade is fabricated; categories absent from the data are reported as such.

**Summary:** 10 items reviewed, 0 discrepancies. Multi-trade windows present in as_traded: 23 trades with rank ≥ 2.


## [first qualifying FVG (setup rank 0, trade #1) — 5m FVG] as_taught_5m — T00001_2022-10-05_sb_london bullish — REPLAY OK

- bias bullish; sweep of swing_15m_low @ 15177.00: penetration 03:00 ET, confirmed 03:01
- displacement candle (gate) confirmed 03:02 (ratio 3.23); stop reference = sweep extreme wick 15176.25 (level 15177.00 - max penetration)
- FVG 5m 15173.25–15182.25 confirmed 03:40; setup rank in window 0, trade #1 in window
- order active 03:40, limit 15177.75; filled 03:55 @ 15177.75; stop 15176.00; target 15202.50 (opposing_liquidity, fallback=False); risk 1.75 pts, reward 14.14R planned
- exit 03:56 @ 15175.75 (stop); ambiguous=False; gap_during_trade=False; contract MNQZ2 (unadjusted entry 11571.50)

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
03:56 15177.25 15183.25 15173.50 15174.00     11567.75              True   EXIT
03:57 15174.00 15178.75 15171.25 15174.00     11567.75              True       
03:58 15173.50 15174.50 15170.00 15171.00     11564.75              True       
```

## [1-minute FVG] as_taught_1m — T00001_2022-10-05_sb_london bullish — REPLAY OK

- bias bullish; sweep of swing_15m_low @ 15177.00: penetration 03:00 ET, confirmed 03:01
- displacement candle (gate) confirmed 03:02 (ratio 3.23); stop reference = sweep extreme wick 15176.25 (level 15177.00 - max penetration)
- FVG 1m 15177.00–15181.50 confirmed 03:06; setup rank in window 0, trade #1 in window
- order active 03:06, limit 15179.25; filled 03:06 @ 15179.25; stop 15176.00; target 15204.50 (opposing_liquidity, fallback=False); risk 3.25 pts, reward 7.77R planned
- exit 03:06 @ 15175.75 (stop); ambiguous=False; gap_during_trade=False; contract MNQZ2 (unadjusted entry 11573.00)

```
   ny    open     high      low    close  unadj_close  consecutive_prev             mark
03:03 15177.0 15177.00 15165.50 15166.25     11560.00              True                 
03:04 15167.0 15185.00 15166.50 15184.00     11577.75              True                 
03:05 15183.5 15189.75 15181.50 15184.25     11578.00              True                 
03:06 15184.5 15185.00 15175.25 15178.50     11572.25              True ACTIVE,FILL,EXIT
03:07 15178.5 15181.50 15168.50 15170.50     11564.25              True                 
03:08 15170.0 15170.75 15164.00 15164.50     11558.25              True                 
```

## [15-minute liquidity swing sweep (bsl_ssl_15m universe)] as_taught_5m — T00002_2022-10-10_sb_ny_am bullish — REPLAY OK

- bias bullish; sweep of swing_15m_low @ 14601.25: penetration 10:04 ET, confirmed 10:05
- displacement candle (gate) confirmed 10:16 (ratio 1.66); stop reference = sweep extreme wick 14596.75 (level 14601.25 - max penetration)
- FVG 5m 14611.25–14622.00 confirmed 10:25; setup rank in window 0, trade #1 in window
- order active 10:25, limit 14616.50; filled 10:25 @ 14616.50; stop 14596.50; target 14742.75 (opposing_liquidity, fallback=False); risk 20.00 pts, reward 6.31R planned
- exit 10:37 @ 14596.25 (stop); ambiguous=False; gap_during_trade=False; contract MNQZ2 (unadjusted entry 11010.25)

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

## [multiple trades within one window (trade #2)] as_traded — T00054_2022-12-23_sb_london bullish — REPLAY OK

- bias none; sweep of swing_15m_low @ 14531.25: penetration 03:07 ET, confirmed 03:11
- displacement candle (gate) confirmed 03:50 (ratio 1.53); stop reference = sweep extreme wick 14526.00 (level 14531.25 - max penetration)
- FVG 1m 14528.25–14530.00 confirmed 03:51; setup rank in window 1, trade #2 in window
- order active 03:51, limit 14529.00; filled 03:51 @ 14529.00; stop 14525.75; target 14535.50 (fixed_2.0R, fallback=False); risk 3.25 pts, reward 2.00R planned
- exit 03:56 @ 14535.50 (target); ambiguous=False; gap_during_trade=False; contract MNQH3 (unadjusted entry 11039.25)

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

## [multiple trades within one window (trade #2)] as_traded — T00064_2023-01-10_sb_london bearish — REPLAY OK

- bias none; sweep of swing_15m_high @ 14669.00: penetration 03:23 ET, confirmed 03:24
- displacement candle (gate) confirmed 03:30 (ratio 1.85); stop reference = sweep extreme wick 14674.50 (level 14669.00 + max penetration)
- FVG 1m 14663.25–14670.00 confirmed 03:31; setup rank in window 1, trade #2 in window
- order active 03:31, limit 14666.75; filled 03:31 @ 14666.75; stop 14674.75; target 14650.75 (fixed_2.0R, fallback=False); risk 8.00 pts, reward 2.00R planned
- exit 03:31 @ 14675.00 (stop); ambiguous=False; gap_during_trade=False; contract MNQH3 (unadjusted entry 11177.00)

```
   ny     open     high      low    close  unadj_close  consecutive_prev             mark
03:28 14671.25 14673.00 14670.00 14672.50     11182.75              True                 
03:29 14672.50 14672.75 14662.25 14663.25     11173.50              True                 
03:30 14663.25 14663.25 14657.75 14662.50     11172.75              True                 
03:31 14662.75 14681.75 14662.75 14680.75     11191.00              True ACTIVE,FILL,EXIT
03:32 14680.25 14682.50 14676.75 14678.50     11188.75              True                 
03:33 14678.25 14686.50 14678.00 14685.25     11195.50              True                 
```

## [liquidity-target selection (opposing 15m swing)] as_taught_5m — T00003_2022-10-20_sb_ny_am bearish — REPLAY OK

- bias none; sweep of swing_15m_high @ 14929.75: penetration 10:20 ET, confirmed 10:21
- displacement candle (gate) confirmed 10:31 (ratio 1.79); stop reference = sweep extreme wick 14931.25 (level 14929.75 + max penetration)
- FVG 5m 14899.25–14899.50 confirmed 10:40; setup rank in window 1, trade #1 in window
- order active 10:40, limit 14899.50; filled 10:40 @ 14899.50; stop 14931.50; target 14688.50 (opposing_liquidity, fallback=False); risk 32.00 pts, reward 6.59R planned
- exit 11:00 @ 14931.75 (stop); ambiguous=False; gap_during_trade=False; contract MNQZ2 (unadjusted entry 11293.25)

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
10:57 14897.75 14922.25 14897.75 14921.50     11315.25              True            
10:58 14921.25 14925.00 14915.25 14922.50     11316.25              True            
10:59 14922.50 14925.00 14915.25 14924.25     11318.00              True            
11:00 14924.25 14932.75 14922.75 14927.75     11321.50              True        EXIT
11:01 14927.50 14927.50 14904.50 14908.50     11302.25              True            
11:02 14908.75 14911.75 14902.00 14903.75     11297.50              True            
```

## [fixed 2R fallback (no eligible opposing liquidity)] as_taught_1m — T00039_2023-02-02_sb_ny_pm bullish — REPLAY OK

- bias none; sweep of swing_15m_low @ 16261.00: penetration 14:34 ET, confirmed 14:35
- displacement candle (gate) confirmed 14:38 (ratio 1.93); stop reference = sweep extreme wick 16259.00 (level 16261.00 - max penetration)
- FVG 1m 16259.25–16273.75 confirmed 14:39; setup rank in window 0, trade #1 in window
- order active 14:39, limit 16266.50; filled 14:39 @ 16266.50; stop 16258.75; target 16282.00 (fallback_fixed_2.0R, fallback=True); risk 7.75 pts, reward 2.00R planned
- exit 14:39 @ 16282.00 (target); ambiguous=False; gap_during_trade=False; contract MNQH3 (unadjusted entry 12776.75)

```
   ny     open     high      low    close  unadj_close  consecutive_prev             mark
14:36 16252.50 16259.25 16245.00 16253.50     12763.75              True                 
14:37 16253.50 16278.50 16250.75 16276.75     12787.00              True                 
14:38 16276.50 16284.75 16273.75 16283.50     12793.75              True                 
14:39 16283.00 16283.25 16259.00 16264.25     12774.50              True ACTIVE,FILL,EXIT
14:40 16263.75 16270.50 16255.00 16255.75     12766.00              True                 
14:41 16255.25 16268.25 16254.75 16263.00     12773.25              True                 
```

## [time-based exit (RTH end)] as_taught_1m — T00023_2022-12-08_sb_ny_pm bullish — REPLAY OK

- bias none; sweep of swing_15m_low @ 15203.50: penetration 14:05 ET, confirmed 14:06
- displacement candle (gate) confirmed 14:10 (ratio 1.61); stop reference = sweep extreme wick 15198.50 (level 15203.50 - max penetration)
- FVG 1m 15211.00–15212.25 confirmed 14:18; setup rank in window 0, trade #1 in window
- order active 14:18, limit 15211.50; filled 14:29 @ 15211.50; stop 15198.25; target 15291.75 (opposing_liquidity, fallback=False); risk 13.25 pts, reward 6.06R planned
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

## [same-bar ambiguity (stop-first)] as_traded — T00047_2022-12-14_sb_ny_pm bullish — REPLAY OK

- bias none; sweep of swing_15m_low @ 15312.00: penetration 14:08 ET, confirmed 14:09
- displacement candle (gate) confirmed 14:42 (ratio 1.89); stop reference = sweep extreme wick 15307.00 (level 15312.00 - max penetration)
- FVG 1m 15302.75–15315.25 confirmed 14:45; setup rank in window 7, trade #1 in window
- order active 14:45, limit 15309.00; filled 14:45 @ 15309.00; stop 15306.75; target 15313.50 (fixed_2.0R, fallback=False); risk 2.25 pts, reward 2.00R planned
- exit 14:45 @ 15306.50 (stop); ambiguous=True; gap_during_trade=False; contract MNQH3 (unadjusted entry 11819.25)

```
   ny     open     high      low    close  unadj_close  consecutive_prev             mark
14:42 15296.75 15302.75 15256.75 15266.25     11776.50              True                 
14:43 15266.50 15343.75 15264.00 15339.00     11849.25              True                 
14:44 15338.00 15381.75 15315.25 15343.75     11854.00              True                 
14:45 15341.75 15348.25 15292.00 15319.75     11830.00              True ACTIVE,FILL,EXIT
14:46 15318.25 15325.50 15293.75 15307.75     11818.00              True                 
14:47 15306.00 15318.25 15291.50 15295.00     11805.25              True                 
```

## [overlapping setup rejection — position open] as_traded — 324 occurrences

- example setup `2022-10-05:sb_london:s54:1m:3305:bull` (bullish, swing_15m_low) at 2022-10-05 03:06 ET → outcome `rejected` / `position_open`
- blocking position: T00001_2022-10-05_sb_london filled 03:06 ET, exited 03:06 ET (stop) — the new setup's activation 03:06 is not after the exit bar

## [pending-order block — no simultaneous orders] as_traded — 144 occurrences

- example setup `2022-10-06:sb_london:s78:1m:4730:bull` (bullish, swing_15m_low) at 2022-10-06 03:51 ET → outcome `rejected` / `order_pending`
- pending order: setup `2022-10-06:sb_london:s75:1m:4730:bull` submitted 03:51 ET, never filled, canceled at window end

## [limit order expiration (canceled at window end)] as_taught_5m — 96 occurrences

- example setup `2022-10-06:sb_ny_am:s93:5m:1030:bull` (bullish, swing_15m_low) at 2022-10-06 10:55 ET → outcome `canceled` / `order_expired_unfilled_at_window_end`
- limit 15197.00, 5 bars until window end, traded through: False → VERIFIED never filled