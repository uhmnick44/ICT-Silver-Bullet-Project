"""Layer 2 — ICT feature detection engine (FVG, liquidity, sweeps, displacement, MSS, bias, windows).

Every detector takes a `SeriesData` (any registered continuous series) and a typed config, and
returns tables whose rows carry `series_id`, a formation timestamp and a confirmation timestamp.
No detector may read bars after a feature's confirmation timestamp to decide that feature.
"""
