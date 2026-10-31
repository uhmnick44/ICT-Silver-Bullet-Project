# Layer 3 manual verification — 2024-07, baseline configuration (provisional FVG-distal stop)

Prices are back-adjusted (unadjusted close shown for basis). Bars listed from 3 minutes before order activation to 2 minutes after exit. Each trade is re-derived by an independent naive replay; `REPLAY OK` means fill time, exit time, exit reason and theoretical exit price agree.

**Summary:** trades 10 (stop 7, target 2, time 1, ambiguous 0), unfilled orders 6, replay discrepancies 0.


## baseline (rth_end exit, 2R) — config ba4e1a50ed49

5 trades, 3 unfilled orders in 2024-07

### T00029_2024-07-01_sb_ny_am — bullish (prewindow_low 22092.75) — REPLAY OK

- sweep penetration 10:12 ET, confirmed 10:13; displacement candle confirmed 10:19 (ratio 1.72); FVG 5m 22171.50–22172.25 confirmed 10:30
- order active 10:30, limit 22171.75 (midpoint), filled 10:30 @ 22171.75; stop 22153.00; target 22209.25 (fixed_2.0R); risk 18.75 pts
- exit 10:39 @ 22152.75 (stop; theoretical 22153.00); gross -18.75 pts = $-37.50; commission $1.88; slippage $0.50; net $-39.88 (-1.06R); MFE 1.60R MAE 1.00R; ambiguous=False; unadjusted entry 19920.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev        mark
10:27 22180.75 22182.25 22173.50 22180.25     19928.75              True            
10:28 22180.25 22196.50 22179.75 22186.00     19934.50              True            
10:29 22186.00 22188.25 22180.75 22187.75     19936.25              True            
10:30 22187.50 22192.00 22170.50 22181.25     19929.75              True ACTIVE,FILL
10:31 22181.50 22182.50 22173.25 22178.75     19927.25              True            
10:32 22178.50 22187.50 22174.00 22181.00     19929.50              True            
10:33 22180.25 22185.50 22176.50 22184.25     19932.75              True            
10:34 22184.25 22186.00 22164.25 22165.00     19913.50              True            
10:35 22165.00 22179.50 22156.50 22172.00     19920.50              True            
10:36 22172.50 22201.75 22171.00 22187.50     19936.00              True            
10:37 22187.25 22189.50 22167.50 22173.00     19921.50              True            
10:38 22172.50 22175.00 22162.75 22165.75     19914.25              True            
10:39 22165.50 22169.75 22153.00 22153.50     19902.00              True        EXIT
10:40 22153.50 22168.50 22149.75 22167.25     19915.75              True            
10:41 22167.75 22170.50 22128.50 22128.50     19877.00              True            
```

### T00030_2024-07-03_sb_ny_am — bearish (prewindow_high 22535.50) — REPLAY OK

- sweep penetration 10:00 ET, confirmed 10:01; displacement candle confirmed 10:01 (ratio 5.06); FVG 5m 22521.25–22528.00 confirmed 10:30
- order active 10:30, limit 22524.75 (midpoint), filled 10:37 @ 22524.75; stop 22548.25; target 22477.75 (fixed_2.0R); risk 23.50 pts
- exit 10:43 @ 22548.50 (stop; theoretical 22548.25); gross -23.50 pts = $-47.00; commission $1.88; slippage $0.50; net $-49.38 (-1.05R); MFE 0.29R MAE 1.28R; ambiguous=False; unadjusted entry 20273.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev   mark
10:27 22513.50 22515.50 22504.50 22508.75     20257.25              True       
10:28 22508.75 22513.50 22503.50 22513.50     20262.00              True       
10:29 22513.75 22517.00 22509.25 22512.25     20260.75              True       
10:30 22511.50 22515.00 22503.25 22513.50     20262.00              True ACTIVE
10:31 22513.75 22520.00 22508.00 22512.25     20260.75              True       
10:32 22512.25 22522.00 22511.25 22520.00     20268.50              True       
10:33 22520.00 22522.75 22515.25 22518.50     20267.00              True       
10:34 22518.25 22522.00 22514.50 22518.25     20266.75              True       
10:35 22517.75 22519.25 22509.75 22510.50     20259.00              True       
10:36 22510.50 22521.50 22508.25 22519.50     20268.00              True       
10:37 22519.25 22529.00 22518.00 22526.75     20275.25              True   FILL
10:38 22526.50 22533.00 22525.50 22532.50     20281.00              True       
10:39 22532.50 22533.50 22525.50 22527.50     20276.00              True       
10:40 22528.00 22535.25 22524.50 22531.25     20279.75              True       
10:41 22531.25 22536.25 22526.75 22535.00     20283.50              True       
10:42 22535.00 22541.50 22532.75 22541.50     20290.00              True       
10:43 22541.25 22554.75 22540.50 22554.00     20302.50              True   EXIT
10:44 22554.25 22560.75 22548.25 22551.00     20299.50              True       
10:45 22551.25 22557.00 22547.75 22556.50     20305.00              True       
```

### T00031_2024-07-09_sb_ny_am — bearish (prewindow_high 23016.00) — REPLAY OK

- sweep penetration 10:12 ET, confirmed 10:13; displacement candle confirmed 10:23 (ratio 1.87); FVG 5m 22973.00–23003.25 confirmed 10:30
- order active 10:30, limit 22988.25 (midpoint), filled 10:45 @ 22988.25; stop 22996.25; target 22972.25 (fixed_2.0R); risk 8.00 pts
- exit 10:49 @ 22972.25 (target; theoretical 22972.25); gross +16.00 pts = $+32.00; commission $1.88; slippage $0.00; net $+30.12 (+1.88R); MFE 3.19R MAE 0.69R; ambiguous=False; unadjusted entry 20736.75 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev   mark
10:27 22947.75 22972.75 22944.75 22972.25     20720.75              True       
10:28 22972.50 22973.00 22961.25 22962.75     20711.25              True       
10:29 22962.25 22966.25 22953.25 22955.75     20704.25              True       
10:30 22956.00 22958.00 22939.50 22949.25     20697.75              True ACTIVE
10:31 22949.25 22952.25 22931.75 22939.75     20688.25              True       
10:32 22939.50 22950.75 22934.00 22945.50     20694.00              True       
10:33 22945.75 22954.75 22941.25 22952.50     20701.00              True       
10:34 22952.50 22962.75 22949.00 22960.00     20708.50              True       
10:35 22960.25 22970.00 22954.25 22958.75     20707.25              True       
10:36 22958.50 22967.75 22956.25 22966.00     20714.50              True       
10:37 22965.50 22976.25 22965.50 22975.25     20723.75              True       
10:38 22975.25 22976.75 22962.00 22966.75     20715.25              True       
10:39 22966.50 22973.50 22965.50 22972.00     20720.50              True       
10:40 22972.00 22973.75 22965.25 22969.00     20717.50              True       
10:41 22969.00 22977.25 22969.00 22977.00     20725.50              True       
10:42 22976.75 22982.00 22970.75 22979.75     20728.25              True       
10:43 22979.25 22980.00 22971.75 22976.00     20724.50              True       
10:44 22975.75 22981.25 22974.50 22980.00     20728.50              True       
10:45 22979.75 22991.00 22978.75 22986.75     20735.25              True   FILL
10:46 22986.75 22992.75 22981.50 22984.75     20733.25              True       
10:47 22984.00 22993.75 22977.75 22989.50     20738.00              True       
10:48 22989.25 22990.25 22977.00 22984.00     20732.50              True       
10:49 22983.75 22985.50 22962.75 22967.75     20716.25              True   EXIT
10:50 22967.75 22976.25 22958.75 22974.75     20723.25              True       
10:51 22974.50 22982.25 22973.75 22979.50     20728.00              True       
```

### T00032_2024-07-12_sb_ny_am — bearish (prewindow_high 22801.00) — REPLAY OK

- sweep penetration 10:00 ET, confirmed 10:04; displacement candle confirmed 10:13 (ratio 1.74); FVG 5m 22808.00–22809.25 confirmed 10:25
- order active 10:25, limit 22808.75 (midpoint), filled 10:25 @ 22808.75; stop 22838.50; target 22749.25 (fixed_2.0R); risk 29.75 pts
- exit 10:33 @ 22838.75 (stop; theoretical 22838.50); gross -29.75 pts = $-59.50; commission $1.88; slippage $0.50; net $-61.88 (-1.04R); MFE 0.41R MAE 1.21R; ambiguous=False; unadjusted entry 20557.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev        mark
10:22 22797.75 22801.25 22779.75 22781.75     20530.25              True            
10:23 22782.50 22788.50 22773.50 22788.25     20536.75              True            
10:24 22788.50 22805.25 22785.50 22804.50     20553.00              True            
10:25 22804.75 22811.50 22803.25 22810.25     20558.75              True ACTIVE,FILL
10:26 22810.00 22811.75 22800.00 22803.25     20551.75              True            
10:27 22803.50 22810.25 22796.75 22806.00     20554.50              True            
10:28 22806.50 22808.75 22797.25 22802.00     20550.50              True            
10:29 22802.00 22805.25 22799.25 22801.75     20550.25              True            
10:30 22802.00 22810.00 22796.50 22806.00     20554.50              True            
10:31 22806.50 22811.50 22806.25 22808.00     20556.50              True            
10:32 22808.25 22828.75 22806.00 22827.75     20576.25              True            
10:33 22828.00 22844.75 22826.25 22841.50     20590.00              True        EXIT
10:34 22841.75 22849.75 22840.50 22849.00     20597.50              True            
10:35 22849.25 22851.25 22837.75 22849.25     20597.75              True            
```

### T00033_2024-07-23_sb_ny_am — bearish (prev_session_high 22295.75) — REPLAY OK

- sweep penetration 10:21 ET, confirmed 10:22; displacement candle confirmed 10:39 (ratio 1.81); FVG 5m 22211.50–22230.25 confirmed 10:55
- order active 10:55, limit 22221.00 (midpoint), filled 10:57 @ 22221.00; stop 22234.75; target 22193.50 (fixed_2.0R); risk 13.75 pts
- exit 11:00 @ 22235.00 (stop; theoretical 22234.75); gross -13.75 pts = $-27.50; commission $1.88; slippage $0.50; net $-29.88 (-1.09R); MFE 0.89R MAE 1.35R; ambiguous=False; unadjusted entry 19969.50 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev   mark
10:52 22182.50 22198.50 22180.75 22198.50     19947.00              True       
10:53 22198.25 22202.50 22190.25 22192.25     19940.75              True       
10:54 22192.50 22200.75 22190.50 22198.75     19947.25              True       
10:55 22199.25 22208.75 22193.25 22204.25     19952.75              True ACTIVE
10:56 22204.50 22214.50 22203.00 22212.75     19961.25              True       
10:57 22212.75 22226.25 22208.75 22222.75     19971.25              True   FILL
10:58 22222.75 22227.50 22216.50 22220.25     19968.75              True       
10:59 22220.50 22226.00 22217.00 22220.00     19968.50              True       
11:00 22220.25 22239.50 22217.50 22238.25     19986.75              True   EXIT
11:01 22238.00 22241.25 22231.50 22240.25     19988.75              True       
11:02 22240.25 22241.25 22231.25 22236.25     19984.75              True       
```

### unfilled order — 2024-07-25 bullish limit 21216.00 active 10:25 — VERIFIED (never traded through before 11:00)
- bars until window end: 35; closest approach +65.50 pts from the limit; stop would have been 21215.5, target 21217.0

### unfilled order — 2024-07-29 bearish limit 21574.25 active 10:15 — VERIFIED (never traded through before 11:00)
- bars until window end: 45; closest approach +0.50 pts from the limit; stop would have been 21601.0, target 21520.75

### unfilled order — 2024-07-31 bearish limit 21722.00 active 10:50 — VERIFIED (never traded through before 11:00)
- bars until window end: 10; closest approach +15.25 pts from the limit; stop would have been 21742.75, target 21680.5


## variant (window_end exit, 2R) — time-exit mechanics — config 0ef99cf07caa

5 trades, 3 unfilled orders in 2024-07

### T00029_2024-07-01_sb_ny_am — bullish (prewindow_low 22092.75) — REPLAY OK

- sweep penetration 10:12 ET, confirmed 10:13; displacement candle confirmed 10:19 (ratio 1.72); FVG 5m 22171.50–22172.25 confirmed 10:30
- order active 10:30, limit 22171.75 (midpoint), filled 10:30 @ 22171.75; stop 22153.00; target 22209.25 (fixed_2.0R); risk 18.75 pts
- exit 10:39 @ 22152.75 (stop; theoretical 22153.00); gross -18.75 pts = $-37.50; commission $1.88; slippage $0.50; net $-39.88 (-1.06R); MFE 1.60R MAE 1.00R; ambiguous=False; unadjusted entry 19920.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev        mark
10:27 22180.75 22182.25 22173.50 22180.25     19928.75              True            
10:28 22180.25 22196.50 22179.75 22186.00     19934.50              True            
10:29 22186.00 22188.25 22180.75 22187.75     19936.25              True            
10:30 22187.50 22192.00 22170.50 22181.25     19929.75              True ACTIVE,FILL
10:31 22181.50 22182.50 22173.25 22178.75     19927.25              True            
10:32 22178.50 22187.50 22174.00 22181.00     19929.50              True            
10:33 22180.25 22185.50 22176.50 22184.25     19932.75              True            
10:34 22184.25 22186.00 22164.25 22165.00     19913.50              True            
10:35 22165.00 22179.50 22156.50 22172.00     19920.50              True            
10:36 22172.50 22201.75 22171.00 22187.50     19936.00              True            
10:37 22187.25 22189.50 22167.50 22173.00     19921.50              True            
10:38 22172.50 22175.00 22162.75 22165.75     19914.25              True            
10:39 22165.50 22169.75 22153.00 22153.50     19902.00              True        EXIT
10:40 22153.50 22168.50 22149.75 22167.25     19915.75              True            
10:41 22167.75 22170.50 22128.50 22128.50     19877.00              True            
```

### T00030_2024-07-03_sb_ny_am — bearish (prewindow_high 22535.50) — REPLAY OK

- sweep penetration 10:00 ET, confirmed 10:01; displacement candle confirmed 10:01 (ratio 5.06); FVG 5m 22521.25–22528.00 confirmed 10:30
- order active 10:30, limit 22524.75 (midpoint), filled 10:37 @ 22524.75; stop 22548.25; target 22477.75 (fixed_2.0R); risk 23.50 pts
- exit 10:43 @ 22548.50 (stop; theoretical 22548.25); gross -23.50 pts = $-47.00; commission $1.88; slippage $0.50; net $-49.38 (-1.05R); MFE 0.29R MAE 1.28R; ambiguous=False; unadjusted entry 20273.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev   mark
10:27 22513.50 22515.50 22504.50 22508.75     20257.25              True       
10:28 22508.75 22513.50 22503.50 22513.50     20262.00              True       
10:29 22513.75 22517.00 22509.25 22512.25     20260.75              True       
10:30 22511.50 22515.00 22503.25 22513.50     20262.00              True ACTIVE
10:31 22513.75 22520.00 22508.00 22512.25     20260.75              True       
10:32 22512.25 22522.00 22511.25 22520.00     20268.50              True       
10:33 22520.00 22522.75 22515.25 22518.50     20267.00              True       
10:34 22518.25 22522.00 22514.50 22518.25     20266.75              True       
10:35 22517.75 22519.25 22509.75 22510.50     20259.00              True       
10:36 22510.50 22521.50 22508.25 22519.50     20268.00              True       
10:37 22519.25 22529.00 22518.00 22526.75     20275.25              True   FILL
10:38 22526.50 22533.00 22525.50 22532.50     20281.00              True       
10:39 22532.50 22533.50 22525.50 22527.50     20276.00              True       
10:40 22528.00 22535.25 22524.50 22531.25     20279.75              True       
10:41 22531.25 22536.25 22526.75 22535.00     20283.50              True       
10:42 22535.00 22541.50 22532.75 22541.50     20290.00              True       
10:43 22541.25 22554.75 22540.50 22554.00     20302.50              True   EXIT
10:44 22554.25 22560.75 22548.25 22551.00     20299.50              True       
10:45 22551.25 22557.00 22547.75 22556.50     20305.00              True       
```

### T00031_2024-07-09_sb_ny_am — bearish (prewindow_high 23016.00) — REPLAY OK

- sweep penetration 10:12 ET, confirmed 10:13; displacement candle confirmed 10:23 (ratio 1.87); FVG 5m 22973.00–23003.25 confirmed 10:30
- order active 10:30, limit 22988.25 (midpoint), filled 10:45 @ 22988.25; stop 22996.25; target 22972.25 (fixed_2.0R); risk 8.00 pts
- exit 10:49 @ 22972.25 (target; theoretical 22972.25); gross +16.00 pts = $+32.00; commission $1.88; slippage $0.00; net $+30.12 (+1.88R); MFE 3.19R MAE 0.69R; ambiguous=False; unadjusted entry 20736.75 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev   mark
10:27 22947.75 22972.75 22944.75 22972.25     20720.75              True       
10:28 22972.50 22973.00 22961.25 22962.75     20711.25              True       
10:29 22962.25 22966.25 22953.25 22955.75     20704.25              True       
10:30 22956.00 22958.00 22939.50 22949.25     20697.75              True ACTIVE
10:31 22949.25 22952.25 22931.75 22939.75     20688.25              True       
10:32 22939.50 22950.75 22934.00 22945.50     20694.00              True       
10:33 22945.75 22954.75 22941.25 22952.50     20701.00              True       
10:34 22952.50 22962.75 22949.00 22960.00     20708.50              True       
10:35 22960.25 22970.00 22954.25 22958.75     20707.25              True       
10:36 22958.50 22967.75 22956.25 22966.00     20714.50              True       
10:37 22965.50 22976.25 22965.50 22975.25     20723.75              True       
10:38 22975.25 22976.75 22962.00 22966.75     20715.25              True       
10:39 22966.50 22973.50 22965.50 22972.00     20720.50              True       
10:40 22972.00 22973.75 22965.25 22969.00     20717.50              True       
10:41 22969.00 22977.25 22969.00 22977.00     20725.50              True       
10:42 22976.75 22982.00 22970.75 22979.75     20728.25              True       
10:43 22979.25 22980.00 22971.75 22976.00     20724.50              True       
10:44 22975.75 22981.25 22974.50 22980.00     20728.50              True       
10:45 22979.75 22991.00 22978.75 22986.75     20735.25              True   FILL
10:46 22986.75 22992.75 22981.50 22984.75     20733.25              True       
10:47 22984.00 22993.75 22977.75 22989.50     20738.00              True       
10:48 22989.25 22990.25 22977.00 22984.00     20732.50              True       
10:49 22983.75 22985.50 22962.75 22967.75     20716.25              True   EXIT
10:50 22967.75 22976.25 22958.75 22974.75     20723.25              True       
10:51 22974.50 22982.25 22973.75 22979.50     20728.00              True       
```

### T00032_2024-07-12_sb_ny_am — bearish (prewindow_high 22801.00) — REPLAY OK

- sweep penetration 10:00 ET, confirmed 10:04; displacement candle confirmed 10:13 (ratio 1.74); FVG 5m 22808.00–22809.25 confirmed 10:25
- order active 10:25, limit 22808.75 (midpoint), filled 10:25 @ 22808.75; stop 22838.50; target 22749.25 (fixed_2.0R); risk 29.75 pts
- exit 10:33 @ 22838.75 (stop; theoretical 22838.50); gross -29.75 pts = $-59.50; commission $1.88; slippage $0.50; net $-61.88 (-1.04R); MFE 0.41R MAE 1.21R; ambiguous=False; unadjusted entry 20557.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev        mark
10:22 22797.75 22801.25 22779.75 22781.75     20530.25              True            
10:23 22782.50 22788.50 22773.50 22788.25     20536.75              True            
10:24 22788.50 22805.25 22785.50 22804.50     20553.00              True            
10:25 22804.75 22811.50 22803.25 22810.25     20558.75              True ACTIVE,FILL
10:26 22810.00 22811.75 22800.00 22803.25     20551.75              True            
10:27 22803.50 22810.25 22796.75 22806.00     20554.50              True            
10:28 22806.50 22808.75 22797.25 22802.00     20550.50              True            
10:29 22802.00 22805.25 22799.25 22801.75     20550.25              True            
10:30 22802.00 22810.00 22796.50 22806.00     20554.50              True            
10:31 22806.50 22811.50 22806.25 22808.00     20556.50              True            
10:32 22808.25 22828.75 22806.00 22827.75     20576.25              True            
10:33 22828.00 22844.75 22826.25 22841.50     20590.00              True        EXIT
10:34 22841.75 22849.75 22840.50 22849.00     20597.50              True            
10:35 22849.25 22851.25 22837.75 22849.25     20597.75              True            
```

### T00033_2024-07-23_sb_ny_am — bearish (prev_session_high 22295.75) — REPLAY OK

- sweep penetration 10:21 ET, confirmed 10:22; displacement candle confirmed 10:39 (ratio 1.81); FVG 5m 22211.50–22230.25 confirmed 10:55
- order active 10:55, limit 22221.00 (midpoint), filled 10:57 @ 22221.00; stop 22234.75; target 22193.50 (fixed_2.0R); risk 13.75 pts
- exit 11:00 @ 22220.50 (time_exit_window; theoretical 22220.25); gross +0.75 pts = $+1.50; commission $1.88; slippage $0.50; net $-0.88 (-0.03R); MFE 0.89R MAE 1.35R; ambiguous=False; unadjusted entry 19969.50 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev   mark
10:52 22182.50 22198.50 22180.75 22198.50     19947.00              True       
10:53 22198.25 22202.50 22190.25 22192.25     19940.75              True       
10:54 22192.50 22200.75 22190.50 22198.75     19947.25              True       
10:55 22199.25 22208.75 22193.25 22204.25     19952.75              True ACTIVE
10:56 22204.50 22214.50 22203.00 22212.75     19961.25              True       
10:57 22212.75 22226.25 22208.75 22222.75     19971.25              True   FILL
10:58 22222.75 22227.50 22216.50 22220.25     19968.75              True       
10:59 22220.50 22226.00 22217.00 22220.00     19968.50              True       
11:00 22220.25 22239.50 22217.50 22238.25     19986.75              True   EXIT
11:01 22238.00 22241.25 22231.50 22240.25     19988.75              True       
11:02 22240.25 22241.25 22231.25 22236.25     19984.75              True       
```

### unfilled order — 2024-07-25 bullish limit 21216.00 active 10:25 — VERIFIED (never traded through before 11:00)
- bars until window end: 35; closest approach +65.50 pts from the limit; stop would have been 21215.5, target 21217.0

### unfilled order — 2024-07-29 bearish limit 21574.25 active 10:15 — VERIFIED (never traded through before 11:00)
- bars until window end: 45; closest approach +0.50 pts from the limit; stop would have been 21601.0, target 21520.75

### unfilled order — 2024-07-31 bearish limit 21722.00 active 10:50 — VERIFIED (never traded through before 11:00)
- bars until window end: 10; closest approach +15.25 pts from the limit; stop would have been 21742.75, target 21680.5
