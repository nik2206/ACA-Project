# Energy Roofline on a Multicore CPU

Reproduces the method of Choi et al., "A Roofline Model of Energy" (IPDPS 2013), plus
the cache-level energy costs from Choi et al. (IPDPS 2014), on one CPU.

## Requirements
- **Linux running directly on the hardware** (not WSL, not a VM). An Ubuntu live USB works.
- Intel CPU, or AMD Ryzen/EPYC (kernel 5.8 or newer)
- `sudo apt install gcc python3-numpy python3-scipy python3-pandas python3-matplotlib`

## Steps
```bash
# 1. allow reading the energy counters (resets on reboot)
sudo chmod -R a+r /sys/class/powercap/intel-rapl*
ls /sys/class/powercap/          # should list intel-rapl:0 ...

# 2. prepare the machine: plug in the charger, set the power mode to Performance,
#    close browsers and other apps, don't touch the machine while it runs

# 3. quick test (~2 min): check the energy columns are NOT -1
QUICK=1 ./run.sh

# 4. full run (~15-25 min)
./run.sh

# 5. fit the model and make the plots
python3 analyze.py
```

## Outputs
| File | What it shows |
|---|---|
| `summary.txt` | fitted ε_flop, ε_mem, π0, B_τ, B_ε, B̂_ε, race-to-halt verdict, per-level pJ/B, best thread counts |
| `fig1_roofline.png` | time roofline (GFLOP/s vs intensity) |
| `fig2_archline.png` | energy roofline / "arch line" (GFLOP/J vs intensity) |
| `fig3_powerline.png` | average power vs intensity |
| `fig4_data_reuse.png` | energy per byte and bandwidth for L1 / L2 / L3 / DRAM |
| `fig5_reuse_archlines.png` | GFLOP/J vs intensity for each data location |
| `fig6_threads.png` | time, energy, GFLOP/J and power vs thread count at 3 intensities |
| `machine_info.txt`, `idle_power.txt` | CPU details and idle package power |

## What the benchmark does
`bench.c` loads each double from an array, applies K dependent FMAs (x = x·a + b), and
accumulates the result, so each element costs W = 2K flops and Q = 8 bytes, giving
I = K/4 flop/byte. Changing K sweeps the intensity; changing the array size picks which
cache level the data comes from; `OMP_NUM_THREADS` sets the thread count.

## Experiments (run.sh)
1. **Intensity:** K = 1 to 512, all physical cores, 512 MB array (in DRAM)
2. **Data reuse:** same kernel with the array sized to half of L1, L2 or L3, or in DRAM
3. **Threads:** 1 up to all cores (plus SMT), at I = 0.25, 4 and 64 flop/byte

Each configuration runs for at least 1 s and is repeated 3 times; the analysis uses the median.

## Notes for the report
- RAPL measures the CPU package (and DRAM on some Intel chips), not the whole system,
  so π0 is much smaller than the paper's 122 W, which was measured for the full machine.
- Peaks are measured from the benchmark itself, not taken from vendor specs.
- Turbo boost changes the clock with load and temperature; mention it if it was on.

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
google-chrome/chromium in headless mode (pandoc is not needed).

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
# report PDF
python3 report/build_pdf.py
# regression test of the fitting code (planted parameters, corrupted+flagged rows)
python3 make_fake_data.py --out /tmp/fake --check
```

`analyze.py` figures: fig1 roofline, fig2 arch line, fig3 powerline (all with the power-capped
model and real kernels), fig4 per-level energy/bandwidth, fig5 arch lines by data location,
fig6 thread scaling, fig7 naive vs tiled matmul, fig8 energy breakdown, fig9 model vs measured.
