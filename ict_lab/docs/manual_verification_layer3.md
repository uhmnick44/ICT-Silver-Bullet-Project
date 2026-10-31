# Layer 3 manual verification — 2024-07, baseline configuration (provisional FVG-distal stop)

Prices are back-adjusted (unadjusted close shown for basis). Bars listed from 3 minutes before order activation to 2 minutes after exit. Each trade is re-derived by an independent naive replay; `REPLAY OK` means fill time, exit time, exit reason and theoretical exit price agree.

**Summary:** trades 10 (stop 7, target 2, time 1, ambiguous 4), unfilled orders 8, replay discrepancies 0.


## baseline (rth_end exit, 2R) — config 6510f655348c

5 trades, 4 unfilled orders in 2024-07

### T00047_2024-07-01_sb_ny_am — bullish (prewindow_low 22092.75) — REPLAY OK

- sweep penetration 10:12 ET, confirmed 10:13; displacement candle confirmed 10:19 (ratio 1.72); FVG 5m 22171.50–22172.25 confirmed 10:30
- order active 10:30, limit 22171.75 (midpoint), filled 10:30 @ 22171.75; stop 22171.25; target 22172.75 (fixed_2.0R); risk 0.50 pts
- exit 10:30 @ 22171.00 (stop; theoretical 22171.25); gross -0.50 pts = $-1.00; commission $1.88; slippage $0.50; net $-3.38 (-3.38R); MFE 40.50R MAE 2.50R; ambiguous=True; unadjusted entry 19920.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev             mark
10:27 22180.75 22182.25 22173.50 22180.25     19928.75              True                 
10:28 22180.25 22196.50 22179.75 22186.00     19934.50              True                 
10:29 22186.00 22188.25 22180.75 22187.75     19936.25              True                 
10:30 22187.50 22192.00 22170.50 22181.25     19929.75              True ACTIVE,FILL,EXIT
10:31 22181.50 22182.50 22173.25 22178.75     19927.25              True                 
10:32 22178.50 22187.50 22174.00 22181.00     19929.50              True                 
```

### T00048_2024-07-03_sb_ny_am — bearish (prewindow_high 22535.50) — REPLAY OK

- sweep penetration 10:00 ET, confirmed 10:01; displacement candle confirmed 10:01 (ratio 5.06); FVG 5m 22521.25–22528.00 confirmed 10:30
- order active 10:30, limit 22524.75 (midpoint), filled 10:37 @ 22524.75; stop 22528.25; target 22517.75 (fixed_2.0R); risk 3.50 pts
- exit 10:37 @ 22528.50 (stop; theoretical 22528.25); gross -3.50 pts = $-7.00; commission $1.88; slippage $0.50; net $-9.38 (-1.34R); MFE 1.93R MAE 1.21R; ambiguous=False; unadjusted entry 20273.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev      mark
10:27 22513.50 22515.50 22504.50 22508.75     20257.25              True          
10:28 22508.75 22513.50 22503.50 22513.50     20262.00              True          
10:29 22513.75 22517.00 22509.25 22512.25     20260.75              True          
10:30 22511.50 22515.00 22503.25 22513.50     20262.00              True    ACTIVE
10:31 22513.75 22520.00 22508.00 22512.25     20260.75              True          
10:32 22512.25 22522.00 22511.25 22520.00     20268.50              True          
10:33 22520.00 22522.75 22515.25 22518.50     20267.00              True          
10:34 22518.25 22522.00 22514.50 22518.25     20266.75              True          
10:35 22517.75 22519.25 22509.75 22510.50     20259.00              True          
10:36 22510.50 22521.50 22508.25 22519.50     20268.00              True          
10:37 22519.25 22529.00 22518.00 22526.75     20275.25              True FILL,EXIT
10:38 22526.50 22533.00 22525.50 22532.50     20281.00              True          
10:39 22532.50 22533.50 22525.50 22527.50     20276.00              True          
```

### T00049_2024-07-09_sb_ny_am — bearish (prewindow_high 23016.00) — REPLAY OK

- sweep penetration 10:12 ET, confirmed 10:13; displacement candle confirmed 10:23 (ratio 1.87); FVG 5m 22973.00–23003.25 confirmed 10:30
- order active 10:30, limit 22988.25 (midpoint), filled 10:45 @ 22988.25; stop 23003.50; target 22957.75 (fixed_2.0R); risk 15.25 pts
- exit 10:56 @ 22957.75 (target; theoretical 22957.75); gross +30.50 pts = $+61.00; commission $1.88; slippage $0.00; net $+59.12 (+1.94R); MFE 2.36R MAE 0.36R; ambiguous=False; unadjusted entry 20736.75 (MNQU4)

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
10:49 22983.75 22985.50 22962.75 22967.75     20716.25              True       
10:50 22967.75 22976.25 22958.75 22974.75     20723.25              True       
10:51 22974.50 22982.25 22973.75 22979.50     20728.00              True       
10:52 22979.50 22982.50 22976.00 22980.75     20729.25              True       
10:53 22980.50 22980.50 22970.50 22975.75     20724.25              True       
10:54 22975.50 22980.25 22974.25 22977.50     20726.00              True       
10:55 22977.50 22980.50 22963.75 22963.75     20712.25              True       
10:56 22963.75 22967.75 22952.25 22966.00     20714.50              True   EXIT
10:57 22966.00 22967.00 22957.25 22960.75     20709.25              True       
10:58 22961.00 22968.25 22958.25 22968.00     20716.50              True       
```

### T00050_2024-07-12_sb_ny_am — bearish (prewindow_high 22801.00) — REPLAY OK

- sweep penetration 10:00 ET, confirmed 10:04; displacement candle confirmed 10:13 (ratio 1.74); FVG 5m 22808.00–22809.25 confirmed 10:25
- order active 10:25, limit 22808.75 (midpoint), filled 10:25 @ 22808.75; stop 22809.50; target 22807.25 (fixed_2.0R); risk 0.75 pts
- exit 10:25 @ 22809.75 (stop; theoretical 22809.50); gross -0.75 pts = $-1.50; commission $1.88; slippage $0.50; net $-3.88 (-2.59R); MFE 7.33R MAE 3.67R; ambiguous=True; unadjusted entry 20557.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev             mark
10:22 22797.75 22801.25 22779.75 22781.75     20530.25              True                 
10:23 22782.50 22788.50 22773.50 22788.25     20536.75              True                 
10:24 22788.50 22805.25 22785.50 22804.50     20553.00              True                 
10:25 22804.75 22811.50 22803.25 22810.25     20558.75              True ACTIVE,FILL,EXIT
10:26 22810.00 22811.75 22800.00 22803.25     20551.75              True                 
10:27 22803.50 22810.25 22796.75 22806.00     20554.50              True                 
```

### T00051_2024-07-23_sb_ny_am — bearish (prev_session_high 22295.75) — REPLAY OK

- sweep penetration 10:21 ET, confirmed 10:22; displacement candle confirmed 10:39 (ratio 1.81); FVG 5m 22211.50–22230.25 confirmed 10:55
- order active 10:55, limit 22221.00 (midpoint), filled 10:57 @ 22221.00; stop 22230.50; target 22202.00 (fixed_2.0R); risk 9.50 pts
- exit 11:00 @ 22230.75 (stop; theoretical 22230.50); gross -9.50 pts = $-19.00; commission $1.88; slippage $0.50; net $-21.38 (-1.13R); MFE 1.29R MAE 1.95R; ambiguous=False; unadjusted entry 19969.50 (MNQU4)

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

### unfilled order — 2024-07-10 bearish limit 23030.00 active 10:25 — VERIFIED (never traded through before 11:00)
- bars until window end: 35; closest approach +3.75 pts from the limit; stop would have been 23034.0, target 23022.0

### unfilled order — 2024-07-25 bullish limit 21216.00 active 10:25 — VERIFIED (never traded through before 11:00)
- bars until window end: 35; closest approach +65.50 pts from the limit; stop would have been 21199.75, target 21248.5

### unfilled order — 2024-07-29 bearish limit 21574.25 active 10:15 — VERIFIED (never traded through before 11:00)
- bars until window end: 45; closest approach +0.50 pts from the limit; stop would have been 21586.0, target 21550.75

### unfilled order — 2024-07-31 bearish limit 21722.00 active 10:50 — VERIFIED (never traded through before 11:00)
- bars until window end: 10; closest approach +15.25 pts from the limit; stop would have been 21723.0, target 21720.0


## variant (window_end exit, 2R) — time-exit mechanics — config 7c05e32292ad

5 trades, 4 unfilled orders in 2024-07

### T00047_2024-07-01_sb_ny_am — bullish (prewindow_low 22092.75) — REPLAY OK

- sweep penetration 10:12 ET, confirmed 10:13; displacement candle confirmed 10:19 (ratio 1.72); FVG 5m 22171.50–22172.25 confirmed 10:30
- order active 10:30, limit 22171.75 (midpoint), filled 10:30 @ 22171.75; stop 22171.25; target 22172.75 (fixed_2.0R); risk 0.50 pts
- exit 10:30 @ 22171.00 (stop; theoretical 22171.25); gross -0.50 pts = $-1.00; commission $1.88; slippage $0.50; net $-3.38 (-3.38R); MFE 40.50R MAE 2.50R; ambiguous=True; unadjusted entry 19920.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev             mark
10:27 22180.75 22182.25 22173.50 22180.25     19928.75              True                 
10:28 22180.25 22196.50 22179.75 22186.00     19934.50              True                 
10:29 22186.00 22188.25 22180.75 22187.75     19936.25              True                 
10:30 22187.50 22192.00 22170.50 22181.25     19929.75              True ACTIVE,FILL,EXIT
10:31 22181.50 22182.50 22173.25 22178.75     19927.25              True                 
10:32 22178.50 22187.50 22174.00 22181.00     19929.50              True                 
```

### T00048_2024-07-03_sb_ny_am — bearish (prewindow_high 22535.50) — REPLAY OK

- sweep penetration 10:00 ET, confirmed 10:01; displacement candle confirmed 10:01 (ratio 5.06); FVG 5m 22521.25–22528.00 confirmed 10:30
- order active 10:30, limit 22524.75 (midpoint), filled 10:37 @ 22524.75; stop 22528.25; target 22517.75 (fixed_2.0R); risk 3.50 pts
- exit 10:37 @ 22528.50 (stop; theoretical 22528.25); gross -3.50 pts = $-7.00; commission $1.88; slippage $0.50; net $-9.38 (-1.34R); MFE 1.93R MAE 1.21R; ambiguous=False; unadjusted entry 20273.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev      mark
10:27 22513.50 22515.50 22504.50 22508.75     20257.25              True          
10:28 22508.75 22513.50 22503.50 22513.50     20262.00              True          
10:29 22513.75 22517.00 22509.25 22512.25     20260.75              True          
10:30 22511.50 22515.00 22503.25 22513.50     20262.00              True    ACTIVE
10:31 22513.75 22520.00 22508.00 22512.25     20260.75              True          
10:32 22512.25 22522.00 22511.25 22520.00     20268.50              True          
10:33 22520.00 22522.75 22515.25 22518.50     20267.00              True          
10:34 22518.25 22522.00 22514.50 22518.25     20266.75              True          
10:35 22517.75 22519.25 22509.75 22510.50     20259.00              True          
10:36 22510.50 22521.50 22508.25 22519.50     20268.00              True          
10:37 22519.25 22529.00 22518.00 22526.75     20275.25              True FILL,EXIT
10:38 22526.50 22533.00 22525.50 22532.50     20281.00              True          
10:39 22532.50 22533.50 22525.50 22527.50     20276.00              True          
```

### T00049_2024-07-09_sb_ny_am — bearish (prewindow_high 23016.00) — REPLAY OK

- sweep penetration 10:12 ET, confirmed 10:13; displacement candle confirmed 10:23 (ratio 1.87); FVG 5m 22973.00–23003.25 confirmed 10:30
- order active 10:30, limit 22988.25 (midpoint), filled 10:45 @ 22988.25; stop 23003.50; target 22957.75 (fixed_2.0R); risk 15.25 pts
- exit 10:56 @ 22957.75 (target; theoretical 22957.75); gross +30.50 pts = $+61.00; commission $1.88; slippage $0.00; net $+59.12 (+1.94R); MFE 2.36R MAE 0.36R; ambiguous=False; unadjusted entry 20736.75 (MNQU4)

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
10:49 22983.75 22985.50 22962.75 22967.75     20716.25              True       
10:50 22967.75 22976.25 22958.75 22974.75     20723.25              True       
10:51 22974.50 22982.25 22973.75 22979.50     20728.00              True       
10:52 22979.50 22982.50 22976.00 22980.75     20729.25              True       
10:53 22980.50 22980.50 22970.50 22975.75     20724.25              True       
10:54 22975.50 22980.25 22974.25 22977.50     20726.00              True       
10:55 22977.50 22980.50 22963.75 22963.75     20712.25              True       
10:56 22963.75 22967.75 22952.25 22966.00     20714.50              True   EXIT
10:57 22966.00 22967.00 22957.25 22960.75     20709.25              True       
10:58 22961.00 22968.25 22958.25 22968.00     20716.50              True       
```

### T00050_2024-07-12_sb_ny_am — bearish (prewindow_high 22801.00) — REPLAY OK

- sweep penetration 10:00 ET, confirmed 10:04; displacement candle confirmed 10:13 (ratio 1.74); FVG 5m 22808.00–22809.25 confirmed 10:25
- order active 10:25, limit 22808.75 (midpoint), filled 10:25 @ 22808.75; stop 22809.50; target 22807.25 (fixed_2.0R); risk 0.75 pts
- exit 10:25 @ 22809.75 (stop; theoretical 22809.50); gross -0.75 pts = $-1.50; commission $1.88; slippage $0.50; net $-3.88 (-2.59R); MFE 7.33R MAE 3.67R; ambiguous=True; unadjusted entry 20557.25 (MNQU4)

```
   ny     open     high      low    close  unadj_close  consecutive_prev             mark
10:22 22797.75 22801.25 22779.75 22781.75     20530.25              True                 
10:23 22782.50 22788.50 22773.50 22788.25     20536.75              True                 
10:24 22788.50 22805.25 22785.50 22804.50     20553.00              True                 
10:25 22804.75 22811.50 22803.25 22810.25     20558.75              True ACTIVE,FILL,EXIT
10:26 22810.00 22811.75 22800.00 22803.25     20551.75              True                 
10:27 22803.50 22810.25 22796.75 22806.00     20554.50              True                 
```

### T00051_2024-07-23_sb_ny_am — bearish (prev_session_high 22295.75) — REPLAY OK

- sweep penetration 10:21 ET, confirmed 10:22; displacement candle confirmed 10:39 (ratio 1.81); FVG 5m 22211.50–22230.25 confirmed 10:55
- order active 10:55, limit 22221.00 (midpoint), filled 10:57 @ 22221.00; stop 22230.50; target 22202.00 (fixed_2.0R); risk 9.50 pts
- exit 11:00 @ 22220.50 (time_exit_window; theoretical 22220.25); gross +0.75 pts = $+1.50; commission $1.88; slippage $0.50; net $-0.88 (-0.05R); MFE 1.29R MAE 1.95R; ambiguous=False; unadjusted entry 19969.50 (MNQU4)

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

### unfilled order — 2024-07-10 bearish limit 23030.00 active 10:25 — VERIFIED (never traded through before 11:00)
- bars until window end: 35; closest approach +3.75 pts from the limit; stop would have been 23034.0, target 23022.0

### unfilled order — 2024-07-25 bullish limit 21216.00 active 10:25 — VERIFIED (never traded through before 11:00)
- bars until window end: 35; closest approach +65.50 pts from the limit; stop would have been 21199.75, target 21248.5

### unfilled order — 2024-07-29 bearish limit 21574.25 active 10:15 — VERIFIED (never traded through before 11:00)
- bars until window end: 45; closest approach +0.50 pts from the limit; stop would have been 21586.0, target 21550.75

### unfilled order — 2024-07-31 bearish limit 21722.00 active 10:50 — VERIFIED (never traded through before 11:00)
- bars until window end: 10; closest approach +15.25 pts from the limit; stop would have been 21723.0, target 21720.0
