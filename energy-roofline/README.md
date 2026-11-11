# Energy Roofline on a Multicore CPU

Reproduces the method of Choi et al., "A Roofline Model of Energy" (IPDPS 2013), plus
the power cap and cache-level energy costs from Choi et al. (IPDPS 2014), on one CPU
(Intel Core i5-13420H laptop, turbo on and turbo off).

Authors: Sai Abhinav (measurements: `bench.c`, `kernels.c`, `rapl.h`, `run.sh`, `data/`) and
Nikhil (modelling, analysis, report and slides: `analyze.py`, `compare.py`,
`make_fake_data.py`, `report/`).

## Requirements
- **Linux running directly on the hardware** (not WSL, not a VM). An Ubuntu live USB works.
- Intel CPU, or AMD Ryzen/EPYC (kernel 5.8 or newer)
- `sudo apt install gcc python3-numpy python3-matplotlib` (scipy and pandas are not needed)
- `linux-tools` (`perf`) for measuring the real kernels' DRAM traffic (optional: without it the analytic Q is used)

## Steps
```bash
# 1. allow reading the energy counters (resets on reboot)
sudo chmod -R a+r /sys/class/powercap/intel-rapl*
ls /sys/class/powercap/          # should list intel-rapl:0 ...

# 2. prepare the machine: plug in the charger, set the power mode to Performance,
#    close browsers and other apps, don't touch the machine while it runs

# 3. quick test (a few minutes): check the energy columns are NOT -1
QUICK=1 OUTDIR=data/$(hostname) ./run.sh

# 4. full run (roughly 20-40 min: every run is followed by a cool-down and throttled
#    runs are retried, so a hot laptop takes longer)
OUTDIR=data/$(hostname) ./run.sh

# 5. fit the model and make the plots (writes them next to the CSV unless --out is given)
python3 analyze.py data/$(hostname)/results.csv
```

## Outputs
`run.sh` writes `results.csv`, `run_flags.csv`, `q_measured.csv`, `run_log.txt`,
`machine_info.txt` and `idle_power.txt` (details in the Workstream A section below).
`analyze.py` then writes:

| File | What it shows |
|---|---|
| `summary.txt`, `summary.json` | fitted ε_flop, ε_mem, π0, B_τ, B_ε, B̂_ε, race-to-halt verdict, model errors, per-level pJ/B, real kernels, energy breakdown, best thread counts |
| `fig1_roofline.png` | time roofline (GFLOP/s vs intensity) |
| `fig2_archline.png` | energy roofline / "arch line" (GFLOP/J vs intensity) |
| `fig3_powerline.png` | average power vs intensity |
| `fig4_data_reuse.png` | energy per byte and bandwidth for L1 / L2 / L3 / DRAM |
| `fig5_reuse_archlines.png` | GFLOP/J vs intensity for each data location |
| `fig6_threads.png` | time, energy, GFLOP/J and power vs thread count at 3 intensities |
| `fig7_matmul_reuse.png` | naive vs tiled matrix multiply (time, energy, GFLOP/J) |
| `fig8_energy_breakdown.png` | energy per flop split into flops, memory and constant energy |
| `fig9_model_fit.png` | model vs measured energy and time |
| `results_summary.csv` | one row per configuration (medians of the repeats) |

## What the benchmark does
`bench.c` loads each double from an array, applies K dependent FMAs (x = x·a + b), and
accumulates the result, so each element costs W = 2K flops and Q = 8 bytes, giving
I = K/4 flop/byte. Changing K sweeps the intensity; changing the array size picks which
cache level the data comes from; `OMP_NUM_THREADS` sets the thread count.

## Experiments (run.sh)
1. **Intensity:** K = 1 to 512 (I = 0.25 to 128), all physical cores, 512 MB array (in DRAM)
2. **Data reuse:** K = 1, 2, 4, 8, 16, 64 with the working set sized from the *total* cache
   capacity of all cores: half of the total L1d, half of the total L2, and for L3 a size
   larger than all L2 caches together but below L3 (on our CPU 160 KB, 3.5 MB, 9.1 MB),
   plus the 512 MB DRAM array
3. **Threads:** 1, 2, 4, 6, 8 and 12 threads (12 = with SMT), at I = 0.25, 4 and 64 flop/byte
4. **Real kernels** (`kernels.c`): triad and naive / tiled matrix multiply, with DRAM traffic
   measured by `perf` (see "Real kernels" below)

`ONLY=intensity,reuse,threads,real` runs a subset (see the options table below).

Each configuration runs for at least 1 s and is repeated 3 times; the analysis uses the median.

## Notes for the report
- RAPL measures the CPU package (and DRAM on some Intel chips), not the whole system,
  so π0 is much smaller than the paper's 122 W, which was measured for the full machine.
  Our CPU has no DRAM domain, so DRAM energy is missing (see `report/dram_sensitivity.py`).
- Peaks are measured from the benchmark itself, not taken from vendor specs.
- Turbo boost changes the clock with load and temperature. Our data has both settings:
  turbo on (two runs) and turbo off (`results_turbo_off.csv`).

## run.sh options, real kernels and throttling handling (Workstream A)

### Environment variables
| Variable | Default | Meaning |
|---|---|---|
| `QUICK=1` | off | Smoke test: 1 repeat, 0.3 s runs, fewer K values, smaller arrays (a few minutes) |
| `ONLY=<list>` | all | Comma-separated experiments to run: `intensity`, `reuse`, `threads`, `real`. Example: `ONLY=intensity,real ./run.sh` |
| `OUTDIR=<dir>` | `.` | Where all outputs are written, e.g. `OUTDIR=data/$(hostname)` |
| `TAG=<name>` | none | Suffix for every output file: `TAG=run2` gives `results_run2.csv`, `run_flags_run2.csv`, ... |
| `COOLDOWN=<f>` | `1.5` | After each run, idle for f × that run's wall time, so the package's average power stays below the long-term limit PL1. `0` disables |
| `MAX_TRIES=<n>` | `3` | Attempts per measurement when throttling is detected (the last attempt is kept either way) |
| `MEASURE_Q=0` | on | Don't measure DRAM traffic of the real kernels with perf; use the analytic formulas |

A full run takes about 35-40 min on the i5-13420H laptop (cool-downs and retries included).

### Outputs (in `OUTDIR`, with `_TAG` suffix if set)
| File | Contents |
|---|---|
| `results.csv` | Section-5 format; the only file `analyze.py` needs |
| `run_flags.csv` | One line per `results.csv` data row, same order: `attempt`, `throttled` (0/1), `throttle_frac`, `pl1_min_W`, `temp_max_C`, `throttle_events`, `imbalance`. Use it to drop or down-weight throttled rows |
| `q_measured.csv` | Exp 4: analytic vs perf-measured DRAM bytes per rep |
| `machine_info.txt`, `idle_power.txt` | CPU details; idle package power (after a 20 s settle) |
| `run_log.txt` | Raw per-run diagnostics (also per-thread slice shares and psys energy) |

### Real kernels (Exp 4, `kernels.c`)
`./kernels <triad|matmul_naive|matmul_tiled|check> <n> [tile] [min_seconds]` prints the same CSV
tail as `bench.c`. `./kernels check 256` verifies that tiled and naive matmul agree.
If perf can read the memory-controller counters (`uncore_imc_free_running_*`, needs
`sudo sysctl -w kernel.perf_event_paranoid=-1`), run.sh measures Q per rep: it runs the
kernel once with 1 rep and once with R reps, takes the difference, and subtracts the idle
background traffic. It then passes the result to `kernels` through `Q_OVERRIDE` (bytes per
rep). `REPS=<r>` fixes the rep count, which the differencing needs.

### Hybrid CPUs (P-cores + E-cores)
`bench.c` gives each thread a fixed contiguous slice and calibrates the slice sizes to each
thread's measured speed before timing, so fast and slow cores finish together. All reps run
inside one parallel region, so there is no fork/join overhead per rep. The real kernels use
dynamic scheduling. Cache working sets are computed from the total capacity of each level
(`lscpu`), and the L3 set is larger than all L2 caches combined.

### Throttling handling
Laptops throttle during a run in two ways. thermald lowers the package power limit PL1
when the die gets hot, and the CPU's own thermal control (TCC) cuts clocks near Tjmax. Both
break the model's assumption of a constant cost per operation. Therefore:
- `rapl.h` runs a monitor thread during every timed region. It samples PL1 and the package
  temperature every 50 ms and diffs the kernel counters in
  `/sys/devices/system/cpu/cpu*/thermal_throttle/`. A run counts as **throttled** if PL1 dropped
  below its nominal value or the package was throttled for more than 2% of the timed region.
- Before every run, run.sh waits until PL1 is back at nominal and the package is below 65 °C.
  It retries a throttled run after a 15 s pause, up to `MAX_TRIES` times, and records the
  outcome in `run_flags.csv`.
- On the i5-13420H, roughly 20-30 of 171 rows remain throttled. They are the hottest
  configurations (74-85 W: L2/L3 reuse at low K, tiled matmul). See `data/<host>/notes.txt`.

## Analysis and report (Workstream B)

Requirements: Python 3 with numpy and matplotlib only (no scipy/pandas). The PDF build uses
google-chrome/chromium in headless mode (pandoc is not needed). If neither is installed,
`build_pdf.py` still writes `report.html`; print it to PDF from any Chromium-based browser, e.g.
`brave-browser --headless=new --no-pdf-header-footer --print-to-pdf=report/report.pdf report/report.html`.

```bash
H=data/sai-Victus-by-HP-Gaming-Laptop-15-fa1xxx
# fit + figures + summary.txt/summary.json for each dataset (throttled rows are dropped)
python3 analyze.py $H/results.csv           --flags $H/run_flags.csv           --out report/figures/turbo_on      --tag "turbo on"
python3 analyze.py $H/results_run2.csv      --flags $H/run_flags_run2.csv      --out report/figures/turbo_on_run2 --tag "turbo on, run 2"
python3 analyze.py $H/results_turbo_off.csv --flags $H/run_flags_turbo_off.csv --out report/figures/turbo_off     --tag "turbo off"
# comparisons (any two or more summary.json files; also works for a second machine)
python3 compare.py report/figures/turbo_on/summary.json report/figures/turbo_off/summary.json \
        --labels "turbo on" "turbo off" --out report/figures/comparison
python3 compare.py report/figures/turbo_on/summary.json report/figures/turbo_on_run2/summary.json \
        --labels "run 1" "run 2" --out report/figures/repeatability
# DRAM energy sensitivity figure + table (needs the two summary.json files above)
python3 report/dram_sensitivity.py
# viva what-ifs X1-X3 (pi0 sweep, power-cap what-if, greenup + EDP) -> report/figures/viva/
python3 report/viva_extras.py
# report PDF
python3 report/build_pdf.py
# regression test of the fitting code (planted parameters, corrupted+flagged rows)
python3 make_fake_data.py --out /tmp/fake --check
```

`analyze.py` figures: fig1 roofline, fig2 arch line, fig3 powerline (all with the power-capped
model and real kernels), fig4 per-level energy/bandwidth, fig5 arch lines by data location,
fig6 thread scaling, fig7 naive vs tiled matmul, fig8 energy breakdown, fig9 model vs measured.

`report/viva_guide.md` is the viva study guide: both papers derived from first principles, the papers'
figures mapped to ours, 62 evaluator questions with answers, pros and cons, the papers' open questions,
and a one-page cheat sheet.

### Open points and caveats in the analysis

These are judgement calls or uncertainties in the modelling. Check them before the viva.

- **Per-level (cache) energies use a relative-error-weighted fit.** With an unweighted fit, the
  high-K points dominate and a 1% error in eps_flop swamps the small cache cost. On the fake data
  that gave L1/L2 errors of 45-50%. The weighting changes our real-data values by less than 1%.
- **pi0 is only weakly determined by the regression.** T/W is proportional to Q/W when
  memory-bound and constant when compute-bound, so pi0 trades off against eps_mem and eps_flop.
  With 2% synthetic noise the fitted pi0 varies by about +-20% between seeds. Our real data
  (about 0.5-1% noise) reproduces within 2% between run 1 and run 2.
- **Turbo-on L2 energy (about 275 pJ/B) is unreliable.** Its K = 1, 2, 4 configurations were
  throttled in every repeat and are excluded, so L2 cannot be told apart from L3 (284). Quote the
  turbo-off values (62 / 71 / 96 / 219 pJ/B) for the data-reuse claim.
- **The power cap is fixed by a rule, not fitted.** Delta_pi = (max measured Exp 1 power) - pi0
  comes from a single reading (44.0 W in run 1, 47.1 W in run 2). Paper 2 fits it by regression.
  The capped model over-predicts the slowdown at I = 8, because the CPU lowers frequency and
  voltage at its limit instead of delaying operations at a fixed energy cost.
- **DRAM energy is missing (package-only RAPL).** `report/dram_sensitivity.py` shows the turbo-on
  race-to-halt verdict survives up to 840 pJ/B of extra DRAM energy, but the turbo-off verdict
  flips at 156-238 pJ/B. That is below the 253-389 pJ/B DRAM+interface estimate that paper 1
  quotes, though part of that estimate (controller, CPU-side PHY) is already in our eps_mem.
  The report (section 4.7) calls turbo on robust and turbo off fragile.
- **Two paper values were read off figures, not tables:** the i7-950's peak efficiency
  (about 0.34 GFLOP/J, from paper 1's Fig. 4) and its B_eps_hat (about 1.1).
- **Differences from notes.txt.** Max Exp 1 power is 67.2 W (notes: about 69 W). Points near the
  corner sit 14-15% below the roof in run 1, 8-11% in run 2 and 19% with turbo off (notes:
  14-27%). In run 2 the fastest thread count at I = 4 is 12, not 8 (a near-tie).

### Viewing the slide deck

`report/slides/index.html` is a single self-contained HTML file. It loads its fonts from Google
Fonts and its figures from `report/figures/`, so keep the folder structure intact.

```bash
xdg-open report/slides/index.html                  # default browser (Linux)
brave-browser report/slides/index.html             # or name a browser directly
```

Controls: Right/Left arrows, Space or Page Up/Down to move between slides, Home/End for the first
and last slide; mouse wheel and swipe also work. Press F11 for full screen. `#8` at the end of the
URL opens slide 8. Press **E** (or hover the top-left corner) to edit text in place. Edits are
saved in that browser's localStorage only, not in the file. To get a PDF, print from a Chromium-based
browser (Chrome, Brave) with landscape layout and no margins.
