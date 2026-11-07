# Comparison: turbo on vs turbo off

| Parameter | turbo on | turbo off | turbo off / turbo on |
|---|---|---|---|
| Sustained peak (GFLOP/s) | 361.7 | 165.0 | 0.46 |
| Sustained bandwidth (GB/s) | 40.1 | 36.4 | 0.91 |
| ε_flop (pJ/flop) | 99.8 | 34.9 | 0.35 |
| ε_mem (pJ/B) | 641.0 | 219.1 | 0.34 |
| π₀ (W) | 23.24 | 7.89 | 0.34 |
| ε₀ = π₀·τ_flop (pJ/flop) | 64.3 | 47.8 | 0.74 |
| B_τ (flop/B) | 9.03 | 4.53 | 0.50 |
| B_ε (flop/B) | 6.43 | 6.28 | 0.98 |
| B̂_ε (flop/B) | 5.35 | 3.34 | 0.62 |
| η_flop | 0.608 | 0.422 | 0.69 |
| Peak energy efficiency (GFLOP/J) | 6.10 | 12.09 | 1.98 |
| Max measured power (W) | 67.2 | 18.4 | 0.27 |
| Δπ = P_max − π₀ (W) | 44.0 | 10.5 | 0.24 |
| Uncapped model peak power (W) | 85.0 | 21.6 | 0.25 |
| Idle package power (W) | 2.86 | 2.71 | |
| Energy model error, median / max (%) | 1.7 / 4.9 | 1.6 / 7.2 | |
| Time model error, median / max (%) | 1.3 / 15.3 | 2.3 / 18.7 | |
| Time error with power cap, median / max (%) | 0.9 / 11.1 | 1.2 / 8.2 | |
| Verdict | race-to-halt (B_τ > B̂_ε) | race-to-halt (B_τ > B̂_ε) | |
| Throttled rows dropped | 21 of 171 | 0 of 117 | |

**Data-movement energy by level (pJ/B, inclusive upper bounds)**

| Level | turbo on | turbo off | ratio |
|---|---|---|---|
| L1 | 195 | 62 | 0.32 |
| L2 | 275 | 71 | 0.26 |
| L3 | 284 | 96 | 0.34 |
| DRAM | 643 | 219 | 0.34 |

**Real kernels (GFLOP/s, GFLOP/J; * = all repeats throttled)**

| Kernel | turbo on GFLOP/s | turbo on GFLOP/J | turbo off GFLOP/s | turbo off GFLOP/J | GFLOP/J ratio | speed ratio |
|---|---|---|---|---|---|---|
| naive mm | 26.0 | 0.370 | 19.2 | 1.089 | 2.94 | 0.74 |
| tiled b=32 | 54.9 | 0.659 | 26.3 | 1.375 | 2.09 | 0.48 |
| tiled b=64 | 75.4* | 0.924* | 35.3 | 1.960 | 2.12 | 0.47 |
| tiled b=128 | 91.1* | 1.073* | 42.9 | 2.363 | 2.20 | 0.47 |
| triad | 2.4 | 0.053 | 2.3 | 0.160 | 3.04 | 0.97 |

**Exp 1, measured turbo off / turbo on**

| I (flop/B) | GFLOP/J ratio | GFLOP/s ratio |
|---|---|---|
| 0.25 | 2.81 | 0.91 |
| 0.5 | 2.78 | 0.90 |
| 1 | 2.83 | 0.91 |
| 2 | 2.90 | 0.89 |
| 4 | 2.55 | 0.75 |
| 8 | 2.19 | 0.56 |
| 16 | 2.07 | 0.52 |
| 32 | 2.03 | 0.46 |
| 64 | 2.01 | 0.44 |
| 128 | 2.02 | 0.45 |
