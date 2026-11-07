# Slides outline: Performance–Energy Trade-offs with Energy Roofline Models

About 14 slides, roughly 12–15 minutes. Figure paths are relative to `report/`. An HTML version of this deck is in `report/slides/index.html` (15 slides: data reuse and tiling get one slide each, and the energy breakdown moves to the balance-gap slide; arrow keys / space to navigate, E to edit text).

---

### 1. Title
- Exploring Performance–Energy Trade-offs Using Energy Roofline Models
- Intel Core i5-13420H (hybrid 4P + 4E), HP Victus 15 laptop
- Team names, course, date

### 2. The question
- Energy is now a first-class cost (battery, heat, power limits)
- **Does faster code also mean more energy-efficient code on a modern multicore CPU?**
- Tool: the energy roofline model (Choi et al., IPDPS 2013; extensions IPDPS 2014)

### 3. Roofline in time
- W flops, Q bytes, intensity I = W/Q
- T = max(W·τ_flop, Q·τ_mem): flops and bytes overlap, the slower one wins
- Ridge point B_τ = τ_mem/τ_flop; memory-bound left, compute-bound right
- Figure: `figures/turbo_on/fig1_roofline.png`

### 4. Energy model
- E = W·ε_flop + Q·ε_mem + π₀·T: energy does **not** overlap; constant power π₀ is paid for the whole run
- B_ε = ε_mem/ε_flop (flop/B; paper 1's Table I gives the unit as "flops per Joule", a typo)
- ε₀ = π₀·τ_flop, η_flop = ε_flop/(ε_flop+ε₀), B̂_ε(I) = η·B_ε + (1−η)·max(0, B_τ−I)

### 5. Arch line and the balance gap
- Sum instead of max → smooth arch line; half of peak at I = B̂_ε
- B̂_ε > B_τ → balance gap: compute-bound in time but memory-bound in energy
- B_τ > B̂_ε → race-to-halt: fast code is already within 2× of the best efficiency
- Figure: `figures/turbo_on/fig2_archline.png`

### 6. Paper 2 extensions
- Power cap: T = max(Wτ_flop, Qτ_mem, (Wε_flop+Qε_mem)/Δπ)
- Inclusive cache-level energies ε_L1 < ε_L2 < ε_L3 < ε_mem
- Constant power dominates on most platforms (π₀ > 50% of peak power on 7 of 12)

### 7. Experimental setup
- RAPL package energy (no DRAM domain on this CPU); idle 2.8 W
- Synthetic kernel: K FMAs per loaded double → I = K/4 (0.25 … 128)
- Real kernels: triad, naive matmul, tiled matmul (b = 32/64/128), **Q measured with IMC counters**
- Exp 1 intensity, Exp 2 data reuse (L1/L2/L3/DRAM), Exp 3 threads (1–12), Exp 4 real kernels
- ≥ 1 s per run, 3 repeats, median; pinned threads; speed-weighted P/E load balancing
- Throttle detection + retry; flagged rows dropped before fitting; turbo-on ×2 runs, turbo-off ×1

### 8. Result: the machine model
- Table: ε_flop 99.8 pJ, ε_mem 641 pJ/B, π₀ 23.2 W, B_τ 9.03, B̂_ε 5.35 (run 2 within 3.3%)
- Energy error: median 1.7%, max 4.9%; time error: median 1.3%
- **Race-to-halt holds** (9.03 > 5.35)
- Figures: `figures/turbo_on/fig1_roofline.png`, `figures/turbo_on/fig2_archline.png`, `figures/turbo_on/fig9_model_fit.png`

### 9. The balance gap since 2013, and π₀
- i7-950 (2013): ε_flop 670 pJ, ε_mem 795 pJ/B, B_ε ≈ 1.2, B_τ ≈ 2.1
- Ours: flop energy 6.7× lower, byte energy almost unchanged → B_ε ≈ 6.4, approaching B_τ
- Turbo off: B_ε 6.28 > B_τ 4.53 → only π₀ keeps race-to-halt valid
- π₀ = 23 W ≈ 8× idle power: "active baseline", not idle (paper: 122 W vs 40 W idle)

### 10. Power cap
- Uncapped model: 85 W at B_τ; laptop never above 67 W; corner points 14–15% under the roof
- Capped model (Δπ = 44 W): power error max 20% → 5.5%, but over-predicts the slowdown at I = 8
- Reason: the CPU lowers frequency and voltage at the limit, so each operation costs less energy
- Figures: `figures/turbo_on/fig3_powerline.png`, `figures/turbo_off/fig3_powerline.png`

### 11. Real kernels and data reuse
- Real kernels sit below roof and arch: triad energy within 3%, matmul 1.4–2.4× above the model (cache traffic not in Q)
- Inclusive energy per byte (turbo off): L1 62 < L2 71 < L3 96 < DRAM 219 pJ/B
- Tiled matmul b = 128: 2.9× (turbo on) / 2.2× (turbo off) more GFLOP/J than naive
- Naive matmul: real I = 1.28, not 0.25 (analytic Q 5× too high: B is shared through L3)
- Figures: `figures/turbo_off/fig4_data_reuse.png`, `figures/turbo_on/fig7_matmul_reuse.png`, `figures/turbo_off/fig5_reuse_archlines.png`

### 12. Threads and the energy breakdown
- I = 0.25: most efficient at **2** threads (fastest at 8); I = 4: at 4 (fastest at 8); I = 64: at 12 (fastest at 12)
- More threads help energy only when compute-bound; E-cores and SMT add power for little speed
- Constant energy is 35–47% of the total at every intensity (turbo off: 43–56%)
- Figures: `figures/turbo_on/fig6_threads.png`, `figures/turbo_on/fig8_energy_breakdown.png`

### 13. Main finding: turbo off
- **2.0–2.9× more energy-efficient at every intensity** (peak 12.1 vs 6.1 GFLOP/J)
- Memory-bound code loses only ~9% speed and gains the most (2.8–3×)
- All energy constants fall ~3× (π₀ 23 → 8 W, ε_flop 100 → 35 pJ); B_ε stays ≈ 6.3
- Race-to-halt holds **within** each setting but not **across** settings: the model has no frequency or voltage terms
- Figures: `figures/comparison/cmp_ratio.png`, `figures/comparison/cmp_archline.png`

### 14. Critique and conclusions
- Strengths: 5 numbers, < 2% energy error; algorithm-centred; explains race-to-halt; extensible
- Weaknesses (with our evidence): DVFS changes the constants 3×; power cap and throttling; best-case overlap; DRAM-only Q; π₀ catch-all and weakly identified; no heterogeneity or contention; package-only energy
- Answer: **faster ⇒ greener at a fixed clock, but the fastest clock is not the greenest**

---

## Viva Q&A appendix

**Q: Why is the arch line smooth while the roofline has a sharp corner?**
Time takes the *maximum* of the flop time and the byte time, because the two overlap, so the curve switches abruptly from one regime to the other at B_τ. Energy is the *sum* of the flop and byte energies, because both are always paid for. The sum changes gradually, so the efficiency curve bends smoothly and reaches half of its peak at the balance point. The arch is perfectly smooth only when π₀ = 0. The π₀·T term inherits the roofline's corner, so our fitted arch lines have a mild knee at B_τ (visible in the turbo-off curve).

**Q: What is B_ε?**
The ratio ε_mem/ε_flop: how many flops cost as much energy as moving one byte. Its unit is flop/byte, like I and B_τ. At I = B_ε, flops and data movement use equal energy (ignoring π₀). Ours is about 6.4 (turbo on) and 6.3 (turbo off). B̂_ε is the version that includes constant power.

**Q: When does race-to-halt fail?**
When B̂_ε > B_τ. That happens when constant power is small (η_flop → 1, so B̂_ε → B_ε) and data movement is expensive relative to flops (large B_ε). Then kernels with B_τ < I < B̂_ε are compute-bound in time but memory-bound in energy, and running faster does not make them efficient. Our turbo-off setting is close: B_ε (6.28) > B_τ (4.53), so without π₀ there would be a gap. Race-to-halt also fails *across* DVFS states, as the turbo experiment shows, which the model cannot express.

**Q: Why is your π₀ (23 W) so much smaller than the paper's 122 W, and yet so much larger than idle power (2.8 W)?**
Smaller than the paper's: RAPL measures only the processor package, while paper 1 measured the whole system at the power supply (motherboard, DRAM, fans, PSU losses), and on a 2009 desktop platform. Larger than idle: π₀ is the power of a chip that is *awake and running*. All cores and the uncore sit at full clock and voltage, caches and the ring stay powered, and leakage is higher at operating temperature. None of that is attributed to individual flops or bytes. Paper 1 saw the same on its GPU (122 W fitted vs about 40 W idle).

**Q: How did you get Q?**
For the synthetic kernel it is exact by construction: each element is loaded once per rep, so 8 bytes per element. For the real kernels we measured DRAM traffic with the memory-controller counters (`uncore_imc_free_running` data_read/data_write) using `perf`. We ran one rep and R reps, took the difference to cancel set-up and warm-up traffic, subtracted the idle background traffic (2.1–2.5 GB/s, mainly display scan-out), and divided by R − 1. The method reproduces the tiled analytic Q within about 1%. The naive matmul's analytic Q was 5× too high because the 8 threads share B through the 12 MB L3.

**Q: Why the median of 3 repeats, and why at least 1 s per run?**
The RAPL energy counter updates roughly every millisecond, so a run of 1 s or longer keeps the quantisation error below 0.1% and averages out turbo frequency changes and OS noise. Three repeats show whether a measurement is stable. The median ignores a single bad repeat (for example a background task or a throttling event) where the mean would not. Repeat spread was typically below 1–3%.

**Q: Why is the energy-optimal thread count low for memory-bound code?**
Once enough threads are running to saturate DRAM bandwidth (about 2–4 here), more threads cannot make the kernel faster, but each one still burns its own active power. The run time stays the same and the power rises (33 W at 2 threads → 53 W at 12 for I = 0.25), so energy grows from 21 J to 28 J. Extra threads pay off only when they shorten the run enough to save constant energy, which is the compute-bound case (I = 64: best at 12 threads).

**Q: What does the turbo-off experiment show about the model?**
That the model's constants are properties of one frequency and voltage, not of the chip. Turning turbo off cuts ε_flop, ε_mem and π₀ by about 3× (roughly the V² effect) and makes every kernel 2–3× more energy-efficient. Within each setting the model still fits well (energy error 1.6%) and still says race-to-halt. But it has no frequency or voltage term, so it cannot tell you that the slower setting is the more efficient one. The DVFS choice saved more energy than any code optimisation in our study.

**Q: Why does the capped model over-correct near B_τ?**
Paper 2's cap keeps ε_flop and ε_mem fixed and simply stretches the time until the power fits under Δπ. Our CPU instead lowers its clock and voltage when it reaches its power or thermal limit, which lowers the energy per operation as well. The real slowdown is therefore smaller than the capped model predicts (I = 8: the run takes 1.18× the roof time; the capped model predicts 1.31×). With turbo off there is no such frequency change, and the cap fits better.

**Q: Why is the L1 energy per byte (62–195 pJ/B) so much larger than the few pJ an L1 access costs?**
The per-level values are inclusive upper bounds. Our per-level fit assigns everything except W·ε_flop and π₀·T to the bytes, so the load instruction, address generation, the add into the accumulator and the loop overhead per element all land in ε_L1. Paper 2 defines its cache costs the same way.

**Q: Why do the real kernels fall below the roofline and arch line?**
The model is a best-case bound. Matmul needs registers, L1 and L2 traffic far beyond the DRAM bytes counted in Q, and its loops do not reach peak FMA throughput. Even with the measured run time, the energy model under-predicts matmul by 1.4–2.4×, the same missing cache term that paper 1 found for its fast multipole kernel. Triad, which only streams from DRAM, is predicted within 3%.

**Q: Why non-negative least squares on E/W?**
Dividing by W puts all configurations on the same per-flop scale, so the high-energy compute-bound runs don't dominate the fit (paper 1, eq. 9). Non-negativity keeps the constants physical. Without noise the fit recovers planted parameters exactly. A caveat: π₀ is weakly identified, because T/W is proportional to Q/W when memory-bound and constant when compute-bound. With 2% synthetic noise it varied ±20%, but our real data reproduced within 2%.
