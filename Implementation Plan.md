# Implementation Plan: Exploring Performance–Energy Tradeoffs Using Energy Roofline Models

**Course:** Advanced Computer Architecture · **Team:** 2 people · **Deadline:** ~14 Nov 2026 (about 1 week)

**Project brief (from the instructors):**
> Study energy roofline modelling and construct performance and energy-efficiency models for one multicore CPU. Measure kernels with different arithmetic intensities, and investigate how data reuse and thread count affect execution time, total energy, and operations per joule.

**References**
1. Primary: Choi, Bedard, Fowler, Vuduc, "A Roofline Model of Energy," IPDPS 2013.
2. Supplementary: Choi, Dukhan, Liu, Vuduc, "Algorithmic Time, Energy, and Power on Candidate HPC Compute Building Blocks," IPDPS 2014.

> **For Claude Code:** read sections 1–4 for context, then work **only** on the workstream assigned to you (Section 6 = Person A, Section 7 = Person B). Do not edit files owned by the other workstream. The only shared contract is the CSV format in Section 5.

---

## 1. What the project is about

**Question:** on a modern multicore CPU, does making code faster also make it more energy-efficient, or do time and energy have to be optimised separately?

### 1.1 Program parameters
- **W**: number of flops the program performs
- **Q**: bytes moved between DRAM and the CPU
- **I = W/Q**: arithmetic intensity (flop/byte). Every plot uses this as its x-axis.

### 1.2 Time model (classic roofline)
Computation and memory transfer **overlap**, so the slower one decides the time:

```
T = max(W·τ_flop, Q·τ_mem)        τ_flop = 1/peak_flops,  τ_mem = 1/peak_bandwidth
B_τ = τ_mem / τ_flop               (time balance, flop/byte)
```
- I < B_τ → memory-bound; I > B_τ → compute-bound. The roofline has a **sharp corner** at B_τ.

### 1.3 Energy model (Choi et al. 2013)
Energy **does not overlap**: every flop and every byte is paid for, and constant power π₀ is paid for the whole runtime.

```
E = W·ε_flop + Q·ε_mem + π₀·T
B_ε = ε_mem / ε_flop               (energy balance, flop/byte; Table I's "flops per Joule" unit is a typo)
ε₀ = π₀·τ_flop = π₀ / peak_flops   (constant energy per flop, paid only when running at peak)
η_flop = ε_flop / (ε_flop + ε₀)    (share of per-flop energy that is not constant power)
B̂_ε(I) = η_flop·B_ε + (1 − η_flop)·max(0, B_τ − I)    (effective energy balance)
P = E/T                             (average power: the "powerline")
```
- Energy efficiency (flop/J) against I is a **smooth arch line**, not a sharp roof. At I = B_ε it is half the maximum.
- **Balance gap:**
  - If **B̂_ε > B_τ**, kernels with B_τ < I < B̂_ε are compute-bound in time but memory-bound in energy, so speed and energy need separate optimisation.
  - If **B_τ > B̂_ε**, time-efficient code is already energy-efficient, so **race-to-halt** works.
- A large π₀ lowers B̂_ε and favours race-to-halt. Paper 1 found exactly this on an i7-950 (B_τ ≈ 2.1 vs B̂_ε ≈ 1.1; ε_flop ≈ 670 pJ in double precision, ε_mem ≈ 795 pJ/B, π₀ = 122 W, i.e. ε₀ ≈ 2.3 nJ per flop).
- Paper 1 fitted the constants with linear regression: `E/W = ε_flop + ε_mem·(Q/W) + π₀·(T/W)`.

### 1.4 Paper 2 extensions (Choi et al. 2014)
- **Power cap Δπ:** `T = max(W·τ_flop, Q·τ_mem, (W·ε_flop + Q·ε_mem)/Δπ)`
- **Cache-level energy:** separate inclusive costs ε_L1 < ε_L2 < ε_mem, measured by sizing the working set to fit each level. **This is the "data reuse" part of our brief.**
- Random-access (pointer-chase) energy is more than 10× the streaming energy.
- On 7 of 12 platforms, constant power is more than 50% of peak power. Within one platform, power varies only about 0.65–1.15× across intensities.

### 1.5 What we must deliver (brief → deliverable)
| Brief phrase | Deliverable |
|---|---|
| Study energy roofline modelling | Theory section and a critique (strengths and weaknesses) |
| Construct performance and energy-efficiency models for one multicore CPU | Fitted ε_flop, ε_mem, π₀; roofline, arch line and powerline plots; B_τ vs B̂_ε verdict |
| Kernels with different arithmetic intensities | Synthetic intensity sweep plus 3 real kernels plotted on the same charts |
| Effect of data reuse | L1/L2/L3/DRAM energy per byte; naive vs tiled matmul |
| Effect of thread count | Time, energy, flop/J and power vs threads at low, medium and high intensity |

**Scope decision:** the full study runs on **one CPU** (the "main machine"). Running Experiment 1 on the second laptop is an **optional bonus section** (a mini cross-platform comparison in the spirit of paper 2).

---

## 2. Hardware and environment

- Both laptops run Linux: one Linux Mint, one Ubuntu. Both work the same way (Mint is Ubuntu-based).
- Energy comes from **RAPL** via `/sys/class/powercap/intel-rapl*` (Intel; AMD Zen with kernel ≥ 5.8).
- **Choosing the main machine:** it must list `intel-rapl:0` under `ls /sys/class/powercap/`. Prefer Intel (often exposes a DRAM domain), then the one with more cores.
- Setup:
  ```bash
  sudo apt install gcc python3-numpy python3-scipy python3-pandas python3-matplotlib
  sudo chmod -R a+r /sys/class/powercap/intel-rapl*    # resets on reboot
  ```
- Measurement procedure: charger plugged in, power profile set to Performance (`powerprofilesctl set performance` if available), browser and other apps closed, no interaction during runs. Record whether turbo is on.

---

## 3. Existing code (already written and tested)

All in `energy-roofline/`:

| File | Purpose | Owner from now on |
|---|---|---|
| `bench.c` | Synthetic tunable-intensity kernel plus RAPL reader. For each double: load, apply K dependent FMAs (`x = x*a + b`), accumulate. W = 2K flops and Q = 8 B per element, so I = K/4. 8 independent SIMD chains per thread (BLK=32 for AVX2, 64 for AVX-512). Auto-calibrates reps to at least `min_seconds`. Handles counter wrap-around. Prints one CSV line. | Person A |
| `run.sh` | Compiles, detects cores and cache sizes, runs Exp 1–3, records idle power, writes `results.csv`. `QUICK=1` gives a 2-minute smoke test. | Person A |
| `analyze.py` | Median of repeats; NNLS fit of ε_flop, ε_mem, π₀; B_τ, B_ε, B̂_ε, η; per-level ε (ε_flop and π₀ held fixed); 6 figures; `summary.txt`, `results_summary.csv`. Tested on synthetic data: recovers the planted parameters. | Person B |
| `README.md` | How to run | shared (append only) |

Existing experiments in `run.sh`:
1. **intensity**: K ∈ {1,2,4,…,512}, all physical cores, DRAM-sized array (≥ 512 MB and ≥ 4× L3)
2. **reuse**: K ∈ {1,2,4,8,16,64}, working set = ½ of L1 (per core × cores), ½ of L2 (same), ½ of L3, or DRAM
3. **threads**: thread counts {1,2,4,…,P} plus SMT, at K ∈ {1,16,256} (I = 0.25, 4, 64)

Each configuration runs for at least 1 s and is repeated 3×; the analysis uses the median.

---

## 4. Repository layout and file ownership

```
energy-roofline/
├── bench.c            A
├── kernels.c          A   (new: real kernels)
├── rapl.h             A   (new: RAPL code factored out of bench.c, shared by bench.c and kernels.c)
├── run.sh             A
├── analyze.py         B
├── compare.py         B   (new: optional two-machine comparison)
├── make_fake_data.py  B   (new: synthetic results.csv for developing without hardware)
├── report/            B   (report.md, figures/, slides outline)
├── data/<hostname>/   A writes raw results here (results.csv, machine_info.txt, idle_power.txt)
└── README.md          shared, append-only sections
```

---

## 5. Shared contract: `results.csv` format (DO NOT CHANGE without telling the other person)

Header (exactly):
```
exp,level,n,bytes,K,threads,reps,W,Q,time_s,E_pkg_J,E_dram_J,checksum
```
| Column | Meaning |
|---|---|
| `exp` | `intensity` · `reuse` · `threads` · `real` |
| `level` | for intensity/reuse/threads: `L1`/`L2`/`L3`/`DRAM`. For `real`: kernel name: `triad`, `matmul_naive`, `matmul_tiled` |
| `n` | elements (synthetic) or matrix dimension (matmul) or array length (triad) |
| `bytes` | working-set size in bytes |
| `K` | synthetic: FMAs per element. matmul_tiled: tile size. Otherwise 0 |
| `threads` | OpenMP threads used |
| `reps` | repetitions inside the timed region |
| `W`, `Q` | total flops and total DRAM bytes for the timed region (Q for real kernels = analytic estimate, see 6.2) |
| `time_s` | wall time of the timed region |
| `E_pkg_J`, `E_dram_J` | RAPL energy; `-1` if unavailable |
| `checksum` | anti-dead-code value; ignore |

Total energy used everywhere: `E = E_pkg_J + max(E_dram_J, 0)`.

---

## 6. Workstream A: Measurement and kernels (Person A + their Claude Code)

**Goal:** produce trustworthy `results.csv` files from the main machine (and optionally the second machine), including real kernels.

**Owns:** `bench.c`, `kernels.c`, `rapl.h`, `run.sh`, `data/`.

### A1. Validate the environment (Day 1)
- [ ] On both laptops: `lscpu | grep "Model name"`, `ls /sys/class/powercap/`. Pick the main machine (Section 2).
- [ ] Run `QUICK=1 ./run.sh`. **Acceptance:** `E_pkg_J` > 0 in every row; GFLOP/s at K=256 is plausible (≥ 30% of theoretical peak = cores × GHz × FMA units × SIMD lanes × 2).
- [ ] Check vectorisation: `gcc -O3 -march=native -fopenmp -fopt-info-vec-optimized bench.c 2>&1 | grep bench.c`

### A2. Factor out RAPL (Day 1)
- [ ] Move the RAPL code (`dom_t`, `rapl_init`, `rapl_read`, `rapl_diff`, helpers) and `now()` from `bench.c` into `rapl.h` as `static` functions. `bench.c` includes it. Output must be byte-identical in format.

### A3. Real kernels: `kernels.c` (Days 1–2)
CLI: `./kernels <kernel> <n> [tile] [min_seconds]` → prints the same CSV tail as `bench.c` (`n,bytes,K,threads,reps,W,Q,time_s,E_pkg_J,E_dram_J,checksum`). Same calibration loop (reps so the timed region ≥ min_seconds), same RAPL handling, OpenMP-parallel.

| Kernel | Code | W | Q (analytic DRAM bytes) | Expected I |
|---|---|---|---|---|
| `triad` | `a[i] = b[i] + s*c[i]`, n = 32M doubles | 2n per rep | 32n per rep (read b, c; write a; plus write-allocate read of a) | ≈ 0.0625 |
| `matmul_naive` | `C += A·B`, i-k-j loop order (inner loop vectorises), n = 2048 | 2n³ | ≈ 8n³ + 24n² (B is re-streamed from DRAM for every row i) | ≈ 0.25 |
| `matmul_tiled` | same, blocked with tile `b` ∈ {32, 64, 128} | 2n³ | ≈ 16n³/b + 24n² | ≈ b/8 |

**Note on Q for matmul:** the formulas above are analytic estimates (the naive one is an upper bound). Where possible, check them with hardware counters around one run: `perf stat -e uncore_imc/data_reads/,uncore_imc/data_writes/` (Intel client CPUs; counts × 64 B) or, failing that, `perf stat -e LLC-load-misses,LLC-store-misses` (× 64 B). If measured values are available, let `kernels.c` take them through an env var `Q_OVERRIDE` (bytes per rep) and use them instead of the formula. Record which method was used in `data/<host>/notes.txt`.

- [ ] Correctness check: tiled and naive give the same C (max abs diff < 1e-9) on n=256.
- [ ] Add to `run.sh` an Exp 4 block (all physical cores, 3 repeats):
  ```
  real triad 32M
  real matmul_naive 2048
  real matmul_tiled 2048 tile∈{32,64,128}
  ```
  written with `exp=real`, `level=<kernel>`, `K=<tile or 0>`.

### A4. Full runs (Days 2–3)
- [ ] Main machine: `./run.sh` → move outputs to `data/<hostname>/` (`results.csv`, `machine_info.txt`, `idle_power.txt`, `notes.txt` with turbo on/off, power profile, kernel version, date).
- [ ] Repeat the full run once more on another day or after a reboot → `data/<hostname>/results_run2.csv`. Check that the key fitted values agree within about 10% (ask B to run `analyze.py` on both).
- [ ] **Optional (bonus):** second laptop, Exp 1 + Exp 4 only (`ONLY=intensity,real ./run.sh`; add an `ONLY` env filter to `run.sh`) → `data/<hostname2>/`.
- [ ] **Optional:** turbo-off rerun of Exp 1 (`echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo`) for the critique section.

### A5. Hand-off
- [ ] Commit `data/` and tell B the paths. Write `data/<host>/notes.txt` covering any anomalies (throttling, noisy points, missing DRAM domain).

**Pitfalls:** VMs/WSL have no RAPL; the compiler may remove unused results (keep checksums); unpinned threads (keep `OMP_PROC_BIND=close`, `OMP_PLACES=cores`); thermal throttling on long runs (keep `sleep 1` between runs if needed); RAPL resolution is ~1 ms, so runs must be ≥ 1 s.

---

## 7. Workstream B: Modelling, plots and report (Person B + their Claude Code)

**Goal:** turn `results.csv` into fitted models, figures and the written report. **B never waits for A**: develop against synthetic data first.

**Owns:** `analyze.py`, `compare.py`, `make_fake_data.py`, `report/`.

### B1. Synthetic data generator (Day 1)
- [ ] `make_fake_data.py`: writes a `results.csv` in the exact Section 5 format with all four `exp` values. Use planted parameters (ε_flop = 300 pJ, ε_mem = 600 pJ/B, ε_L1/L2/L3 = 20/60/150 pJ/B, π₀ = 8 W, peak 100 GFLOP/s, 30 GB/s, thread scaling: compute ∝ threads, bandwidth saturating at 3 threads, 2% noise). Times from the roofline; energy from the model.
- [ ] **Acceptance:** `analyze.py` on fake data recovers the planted parameters within 5%.

### B2. Extend `analyze.py` (Days 1–3)
- [ ] CLI: `python3 analyze.py <results.csv> [--out <dir>]`; write all outputs into `--out` (default: alongside the CSV).
- [ ] Write `summary.json` (all fitted parameters and derived values) in addition to `summary.txt`.
- [ ] **Real kernels (`exp == real`):** overlay them as distinct labelled markers on fig1 (roofline) and fig2 (arch line); report model-predicted vs measured time and energy and their % error in `summary.txt`.
- [ ] **New fig7_matmul_reuse.png:** naive vs tiled (b = 32/64/128): time, energy and GFLOP/J bars (separate panels; never a dual axis). This is the "data reuse in a real kernel" figure.
- [ ] **Energy breakdown fig8_energy_breakdown.png:** stacked bars of E_flops = W·ε_flop, E_mem = Q·ε_mem and E₀ = π₀·T for selected intensities (I = 0.25, 1, 4, 16, 64). Shows how much of the energy is constant power, which supports the race-to-halt argument.
- [ ] Add the **power-capped** time model from paper 2 as an optional fit: estimate Δπ = max(P) − π₀ and plot the capped roofline as a dashed line on fig1 when it differs from the uncapped one by more than 5%.
- [ ] Residual check: a plot of model vs measured energy (log-log, y = x reference line) → fig9_model_fit.png, with the median/max error printed.
- [ ] Keep the existing style: Cove palette (#2a78d6, #eb6834, #1baf7a, #eda100), thin lines, legend when there are ≥ 2 series, one y-axis per chart.

### B3. Two-machine comparison (Day 3, only if A provides second-machine data)
- [ ] `compare.py data/<h1>/summary.json data/<h2>/summary.json` → a table (markdown) of peak GFLOP/s, GB/s, ε_flop, ε_mem, π₀, B_τ, B̂_ε, peak GFLOP/J and verdict, plus one figure overlaying both arch lines (normalised and absolute).

### B4. Report (Days 2–5), `report/report.md` (export to PDF at the end)
Target 6–8 pages. Write the theory and method sections first (no data needed), then fill in the results once A's data lands.

1. **Introduction**: motivation (energy as a first-class metric); the research question.
2. **Background and model**: roofline in time; energy model; B_ε, arch line, balance gap; constant power, η, B̂_ε; powerline; paper 2 extensions (power cap, cache levels, π₀ dominance). Include the symbol table (W, Q, I, τ, ε, π₀, ε₀ = π₀/peak_flops, η, B̂_ε) and point out the Table I unit typo.
3. **Experimental setup**: CPU details (from `machine_info.txt`), RAPL (package ± DRAM; what it does and doesn't measure), kernels (synthetic, triad, matmul), Exp 1–4, methodology (≥ 1 s, 3 repeats, median, pinning, power profile, turbo status), fitting method (NNLS on E/W).
4. **Results**
   - 4.1 Machine model: parameter table; fig1–3; B_τ vs B̂_ε → race-to-halt verdict; comparison with paper 1's i7-950 values.
   - 4.2 Real kernels on the model: where they sit; prediction error.
   - 4.3 Data reuse: fig4–5 (per-level pJ/B), fig7 (tiling).
   - 4.4 Thread count: fig6; energy-optimal vs time-optimal thread count per intensity; explanation via π₀ amortisation and bandwidth saturation.
   - 4.5 Energy breakdown: fig8; share of constant energy.
   - 4.6 (optional) Second CPU comparison.
5. **Critique of the model**
   - Strengths: few parameters; algorithm-centric (intensity); explains race-to-halt via π₀; validated on 2 and then 12 platforms; extensible (caches, caps).
   - Weaknesses (back each with our data where possible): assumes constant per-op cost (turbo/DVFS break this); best-case overlap (overpredicts near B_τ); no read/write or prefetch distinction; π₀ is a catch-all fitted term (paper's 122 W ≫ idle); measurement boundary (RAPL chip-only vs paper's wall-level); fitted on synthetic kernels (paper's FMM needed an extra cache term); **no explicit thread/contention modelling** (our Exp 3 tests this).
6. **Conclusion**: the 3–5 claims below, with our numbers.

**Claims the report should argue (fill in X/Y/Z):**
1. The time = max / energy = sum model describes our CPU (median energy error X%).
2. Our CPU: ε_flop = X pJ, ε_mem = Y pJ/B, π₀ = Z W, vs the i7-950's 670 pJ / 795 pJ/B / 122 W.
3. B_τ vs B̂_ε → race-to-halt does or does not hold.
4. Data reuse lowers energy per byte (L1 < L2 < L3 < DRAM); tiling improves GFLOP/J by X×.
5. More threads improve flop/J for compute-bound kernels; for memory-bound kernels the energy-optimal thread count is below the maximum.

### B5. Slides (Day 5)
`report/slides_outline.md`: about 12 slides: problem → roofline → energy model → arch line and balance gap → race-to-halt → setup → results (one slide per figure group) → critique → conclusions. Add a viva Q&A appendix:
- Why is the arch line smooth? (energy adds; time overlaps)
- What is B_ε? (ε_mem/ε_flop; flop/byte)
- When does race-to-halt fail? (B̂_ε > B_τ: small π₀, expensive data movement)
- Why is our π₀ ≪ 122 W? (RAPL measures only the package; the paper measured the whole system)
- How did you get Q? (analytic for the synthetic kernel: 8 B/element; perf counters or estimate for matmul)
- Why median of 3 and ≥ 1 s? (RAPL ~1 ms update; turbo/OS noise)

---

## 8. Timeline

| Day | Date | Person A (measurement) | Person B (modelling and report) |
|---|---|---|---|
| 1 | Sat 7 Nov | A1, A2: pick main machine, smoke test | B1 fake data; start B2; read §II–IV of paper 1 and §III of paper 2 |
| 2 | Sun 8 Nov | A3 real kernels + correctness | B2 new figures on fake data; report §1–2 |
| 3 | Mon 9 Nov | A4 full run on main machine → hand off `data/` | B2 on real data; report §3 |
| 4 | Tue 10 Nov | A4 second run (repeatability), optional second laptop / turbo-off | B3 (if data); report §4 |
| 5 | Wed 11 Nov | Review report results and critique for accuracy | Report §5–6; B5 slides |
| 6 | Thu 12 Nov | Both: proofread, rehearse, check figures match numbers | |
| 7 | Fri 13 Nov | Buffer | Buffer |

**Sync points:** end of Day 1 (main machine chosen; CSV contract frozen), end of Day 3 (real data handed over), Day 5 (draft review).

---

## 9. Definition of done
- [ ] `data/<main-host>/results.csv` with Exp 1–4, all energies > 0, plus a repeatability run
- [ ] `summary.txt` / `summary.json` with fitted parameters, B_τ, B̂_ε and verdict
- [ ] Figures fig1–fig9 generated from real data
- [ ] Report (PDF) with theory, setup, results, critique and conclusion; claims filled with our numbers
- [ ] Slides and viva Q&A
- [ ] README updated with exact reproduction steps