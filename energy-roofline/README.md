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
