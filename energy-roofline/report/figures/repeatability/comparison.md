# Comparison: run 1 vs run 2

| Parameter | run 1 | run 2 | run 2 / run 1 |
|---|---|---|---|
| Sustained peak (GFLOP/s) | 361.7 | 367.7 | 1.02 |
| Sustained bandwidth (GB/s) | 40.1 | 40.0 | 1.00 |
| ε_flop (pJ/flop) | 99.8 | 100.8 | 1.01 |
| ε_mem (pJ/B) | 641.0 | 627.2 | 0.98 |
| π₀ (W) | 23.24 | 23.60 | 1.02 |
| ε₀ = π₀·τ_flop (pJ/flop) | 64.3 | 64.2 | 1.00 |
| B_τ (flop/B) | 9.03 | 9.18 | 1.02 |
| B_ε (flop/B) | 6.43 | 6.22 | 0.97 |
| B̂_ε (flop/B) | 5.35 | 5.31 | 0.99 |
| η_flop | 0.608 | 0.611 | 1.00 |
| Peak energy efficiency (GFLOP/J) | 6.10 | 6.06 | 0.99 |
| Max measured power (W) | 67.2 | 70.7 | 1.05 |
| Δπ = P_max − π₀ (W) | 44.0 | 47.1 | 1.07 |
| Uncapped model peak power (W) | 85.0 | 85.7 | 1.01 |
| Idle package power (W) | 2.86 | 2.77 | |
| Energy model error, median / max (%) | 1.7 / 4.9 | 1.9 / 5.1 | |
| Time model error, median / max (%) | 1.3 / 15.3 | 3.8 / 10.9 | |
| Time error with power cap, median / max (%) | 0.9 / 11.1 | 2.2 / 9.6 | |
| Verdict | race-to-halt (B_τ > B̂_ε) | race-to-halt (B_τ > B̂_ε) | |
| Throttled rows dropped | 21 of 171 | 28 of 171 | |

**Data-movement energy by level (pJ/B, inclusive upper bounds)**

| Level | run 1 | run 2 | ratio |
|---|---|---|---|
| L1 | 195 | 198 | 1.01 |
| L2 | 275 | 276 | 1.00 |
| L3 | 284 | 285 | 1.00 |
| DRAM | 643 | 631 | 0.98 |

**Real kernels (GFLOP/s, GFLOP/J; * = all repeats throttled)**

| Kernel | run 1 GFLOP/s | run 1 GFLOP/J | run 2 GFLOP/s | run 2 GFLOP/J | GFLOP/J ratio | speed ratio |
|---|---|---|---|---|---|---|
| naive mm | 26.0 | 0.370 | 25.9 | 0.359 | 0.97 | 1.00 |
| tiled b=32 | 54.9 | 0.659 | 55.0 | 0.659 | 1.00 | 1.00 |
| tiled b=64 | 75.4* | 0.924* | 72.7* | 0.975* | 1.06 | 0.96 |
| tiled b=128 | 91.1* | 1.073* | 91.0* | 1.084* | 1.01 | 1.00 |
| triad | 2.4 | 0.053 | 2.4 | 0.053 | 1.00 | 1.00 |

**Exp 1, measured run 2 / run 1**

| I (flop/B) | GFLOP/J ratio | GFLOP/s ratio |
|---|---|---|
| 0.25 | 1.00 | 1.00 |
| 0.5 | 1.00 | 1.00 |
| 1 | 1.00 | 1.00 |
| 2 | 1.00 | 1.00 |
| 4 | 1.00 | 0.98 |
| 8 | 1.00 | 1.05 |
| 16 | 0.99 | 1.08 |
| 32 | 0.98 | 0.93 |
| 64 | 0.98 | 0.94 |
| 128 | 1.01 | 1.03 |
