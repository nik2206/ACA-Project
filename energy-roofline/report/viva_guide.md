# Viva guide: energy roofline models (Choi et al. 2013, 2014) and our reproduction

## How to use this guide

This guide is for the night before the viva. It explains the two papers from first principles, maps them onto our measurements, and collects the questions an evaluator is likely to ask. Sections can be read on their own: every symbol is defined again at the start of each section. If you only have an hour, read §8 (cheat sheet), then §1.4–§1.8 (the derivations) and skim the question bank in §4.

Sources are given in brackets. **[P1 §II-B, eq. 5]** is paper 1 (Choi, Bedard, Fowler, Vuduc, "A roofline model of energy", IPDPS 2013, pp. 661–672), **[P2 Table I]** is paper 2 (Choi, Dukhan, Liu, Vuduc, "Algorithmic time, energy, and power on candidate HPC compute building blocks", IPDPS 2014, pp. 447–457). Page numbers are the journal pages printed on the papers. Our own files are cited by name: `[turbo_on/summary.txt]` means `report/figures/turbo_on/summary.txt`, `[viva_extras.md]` means `report/figures/viva/viva_extras.md`, `[report §4.6]` means section 4.6 of `report/report.md`. Figure paths are relative to `report/`.

Three kinds of statement are kept apart throughout: what a paper says, what we measured, and what we infer. Inference is marked "we think" or "this suggests".

**Contents**
1. Paper 1 explained
2. Paper 2 explained
3. The papers' figures and claims mapped to ours
4. Evaluator question bank (62 questions)
5. Experimental results summary
6. Pros and cons
7. Open-ended questions from the papers
8. Cheat sheet

---

## 1. Paper 1 explained

*Symbols used in this section.* W = number of flops, Q = bytes moved between slow and fast memory, I = W/Q (flop/byte). τ_flop, τ_mem = time per flop and per byte (inverse peak rates). ε_flop, ε_mem = energy per flop and per byte. π₀ = constant power (W). B_τ = τ_mem/τ_flop, B_ε = ε_mem/ε_flop. ε₀ = π₀·τ_flop, ε̂_flop = ε_flop + ε₀, η_flop = ε_flop/ε̂_flop. B̂_ε = effective energy balance. π_flop = ε_flop/τ_flop.

### 1.1 The abstract machine and the algorithm [P1 §II, Fig. 1, Table I, p. 662]

The machine is a processor ("xPU") attached to a fast memory of finite size Z, which is attached to an infinite slow memory. The processor can only compute on data in fast memory, so every algorithm must move data from slow to fast memory [P1 §II]. This picture covers anything from one functional unit with its registers to a manycore chip with its last-level cache.

An algorithm is reduced to two numbers. **W** is the number of *useful* operations (flops for matrix multiply; the paper notes one could count comparisons for sorting or edges for graph traversal). **Q** is the number of bytes moved between slow and fast memory; loads and stores are not distinguished [P1 §II-A]. Their ratio is the **arithmetic intensity I = W/Q**, in flop/byte.

I belongs to the algorithm, but it also depends on Z. No n×n matrix multiply can have intensity above O(√Z) (Hong and Kung's red-blue pebble bound), so doubling the fast memory improves matmul's intensity by at most √2. Summing an array has I = O(1) whatever Z is [P1 §II-A, p. 662]. In our project the same matmul has I = 1.28 (naive) to 19 (128-wide tiles) flop/B [turbo_on/summary.txt], which is exactly this dependence on how well the code uses the fast memory.

*Typo to know about.* P1 Table I and Table II give the unit of B_ε as "flops per Joule". B_ε is (J/byte)/(J/flop), so its unit is flop/byte, like I and B_τ [report §2.1].

*Where it breaks down.* Two levels only: real chips have L1, L2, L3 and DRAM, each with its own cost (paper 2 adds per-level costs). Q counts slow-memory traffic only, so cache traffic is invisible.

### 1.2 Time model [P1 eq. 1, 3, p. 663]

Each flop costs τ_flop seconds and each byte τ_mem seconds. These are **throughput** costs (inverse peak flop/s and inverse peak bandwidth), not latencies [P1 §II-B and footnote 2]. Assuming flops and memory transfers overlap perfectly:

> T = max(W·τ_flop, Q·τ_mem) = W·τ_flop · max(1, B_τ/I),  B_τ = τ_mem/τ_flop

B_τ, the **time balance**, is the intensity at which the flop time equals the memory time. A kernel with I < B_τ is memory-bound in time; with I > B_τ, compute-bound. W·τ_flop is the ideal time with no communication, and B_τ/I (when above 1) is the communication penalty. The "balance principle" is the design goal I > B_τ [P1 §II-B].

On our laptop with turbo on, peak 361.7 GFLOP/s and 40.1 GB/s give B_τ = 361.7/40.1 = 9.03 flop/B [turbo_on/summary.txt].

*Where it breaks down.* The max() assumes perfect overlap and enough concurrency to hide latency; the paper says this is a best case valid only with sufficient concurrency [P1 §II-B]. Our points nearest the corner sit 14–15% below the roof (turbo on) and 19% at I = 4 (turbo off) [turbo_on/summary.txt, turbo_off/summary.txt].

### 1.3 Energy model [P1 eq. 2, 4, p. 663]

> E = W·ε_flop + Q·ε_mem + π₀·T = W·ε_flop·(1 + B_ε/I + π₀·T/(ε_flop·W)),  B_ε = ε_mem/ε_flop

The paper stresses two differences from time, which it calls critical: **(i) time can overlap but energy cannot**, so energy is a sum where time is a max; and **(ii) constant energy is burned for the whole run**, so a slower run costs more even if it does the same operations [P1 §II-B, p. 663]. π₀ is assumed to be independent of which operations run [P1 eq. 2 discussion].

B_ε, the **energy balance**, is the intensity at which flop energy equals memory energy (ignoring π₀). Ours: 641.0/99.8 = 6.43 flop/B with turbo on [turbo_on/summary.txt].

*Where it breaks down.* "Fixed energy per operation" assumes one frequency and voltage. Our turbo-off run cut ε_flop, ε_mem and π₀ by about 3× each [comparison/comparison.md], so the constants belong to an operating point, not to the chip.

### 1.4 Derivation of ε₀, ε̂_flop, η_flop and B̂_ε(I) [P1 eq. 5–6, p. 663]

Start from the energy equation and substitute the time model:

1. π₀·T = π₀·W·τ_flop·max(1, B_τ/I) = W·ε₀·max(1, B_τ/I), where **ε₀ = π₀·τ_flop** is the constant energy burned during one flop at peak rate.
2. Rewrite the max: max(1, B_τ/I) = 1 + max(0, B_τ − I)/I. (If I ≥ B_τ both sides are 1; if I < B_τ, B_τ/I = 1 + (B_τ − I)/I.)
3. So E = W·[ε_flop + ε₀ + ε_mem/I + ε₀·max(0, B_τ − I)/I].
4. Factor out **ε̂_flop = ε_flop + ε₀**, the real cost of one flop including its share of constant power: E = W·ε̂_flop·[1 + (ε_mem/ε̂_flop + (ε₀/ε̂_flop)·max(0, B_τ − I))/I].
5. Define **η_flop = ε_flop/ε̂_flop**, the fraction of a flop's real cost that is the arithmetic itself. Then ε_mem/ε̂_flop = (ε_mem/ε_flop)·(ε_flop/ε̂_flop) = η_flop·B_ε, and ε₀/ε̂_flop = 1 − η_flop.

Result:

> E = W·ε̂_flop·(1 + B̂_ε(I)/I),  B̂_ε(I) = η_flop·B_ε + (1 − η_flop)·max(0, B_τ − I)

W·ε̂_flop is the ideal energy (flops only), and B̂_ε(I)/I is the energy communication penalty, just as B_τ/I was the time penalty. η_flop = 1 when π₀ = 0 [P1 §II-B].

Our numbers [turbo_on/summary.txt, turbo_off/summary.txt]:

| | ε_flop | ε₀ = π₀·τ_flop | ε̂_flop | η_flop |
|---|---|---|---|---|
| Turbo on | 99.8 pJ | 23.24 W / 361.7 GFLOP/s = 64.3 pJ | 164.1 pJ | 0.608 |
| Turbo off | 34.9 pJ | 7.89 W / 165.0 GFLOP/s = 47.8 pJ | 82.7 pJ | 0.422 |

*Where it breaks down.* ε₀ charges constant power at the *peak* flop rate. It is a bookkeeping device, and it inherits every weakness of π₀ (see §1.10).

### 1.5 Roofline vs arch line, and the half-peak point [P1 §II-C, Fig. 2a, p. 664]

Normalised to the best possible value:
- **Roofline (speed):** W·τ_flop/T = min(1, I/B_τ). A sharp corner at I = B_τ, because time is a max.
- **Arch line (energy efficiency):** W·ε̂_flop/E = 1/(1 + B̂_ε(I)/I). Smooth, because energy is a sum [P1 §II-C].

**Half-peak with π₀ = 0.** Then B̂_ε = B_ε and efficiency = 1/(1 + B_ε/I), which equals ½ exactly at I = B_ε. This is the paper's footnote 3: since a + b ≤ 2·max(a, b), the sum of flop and memory energy is at most twice the larger one, so at I = B_ε (where the two are equal) efficiency is half of peak. Equivalently, B_ε is where energy on flops equals energy on bytes [P1 §II-C, p. 664].

**Half-peak with π₀ > 0** (our derivation of what the report calls B̂_ε). Efficiency is ½ when B̂_ε(I) = I, a fixed point.
- If the solution lies below B_τ: η·B_ε + (1 − η)·(B_τ − I) = I, so **B̂_ε = (η·B_ε + (1 − η)·B_τ)/(2 − η)**. This is valid when the result is below B_τ, which reduces to η·B_ε < B_τ.
- Otherwise (η·B_ε ≥ B_τ): B̂_ε = η·B_ε.

Check by hand [turbo_on/summary.txt, turbo_off/summary.txt]:
- Turbo on: η·B_ε = 0.608 × 6.43 = 3.91 < 9.03, so B̂_ε = (3.91 + 0.392 × 9.03)/(2 − 0.608) = (3.91 + 3.54)/1.392 = **5.35**.
- Turbo off: η·B_ε = 0.422 × 6.28 = 2.65 < 4.53, so B̂_ε = (2.65 + 0.578 × 4.53)/1.578 = (2.65 + 2.62)/1.578 = **3.34**.

**When is B̂_ε < B_ε?** Not always. In the first case, B̂_ε < B_ε ⟺ η·B_ε + (1 − η)·B_τ < (2 − η)·B_ε ⟺ (1 − η)·B_τ < 2(1 − η)·B_ε ⟺ **B_τ < 2·B_ε** (for η < 1). In the second case B̂_ε = η·B_ε ≤ B_ε always. Both our settings satisfy B_τ < 2·B_ε (9.03 < 12.86; 4.53 < 12.56). Paper 1's own sentence is qualitative: "Higher constant power means lower η_flop; consequently ... it would cause B̂_ε(I) to be lower than B_ε" [P1 §II-D, last paragraph, p. 665]. The exact condition is our algebra.

**As π₀ grows**, η → 0 and B̂_ε → B_τ/2: energy then behaves like time, and on the roofline speed is half of peak at I = B_τ/2. **As π₀ → 0**, η → 1 and B̂_ε → B_ε. So B̂_ε always lies between the two, weighted by η.

The π₀·T term inherits the roofline corner, so a fitted arch line with π₀ > 0 has a mild knee at B_τ (visible in `figures/turbo_off/fig2_archline.png`) [slides_outline.md Q&A].

*Where it breaks down.* The "half-peak" definition of the energy ridge is a convention. With a large π₀ the arch line is not symmetric about B̂_ε.

### 1.6 Worked example from the paper [P1 Table II, Fig. 2, p. 664]

Paper 1 illustrates the model with a Fermi-class GPU, using Keckler et al.'s estimates:
- τ_flop = (515 GFLOP/s)⁻¹ ≈ 1.9 ps per flop; τ_mem = (144 GB/s)⁻¹ ≈ 6.9 ps per byte; **B_τ ≈ 3.6**.
- ε_flop ≈ 25 pJ (50 pJ per double FMA); ε_mem ≈ 360 pJ/B; **B_ε ≈ 14.4**.
- π₀ is unknown, so assumed 0.

A kernel with 3.6 < I < 14.4 is **compute-bound in time but memory-bound in energy**: it already runs at peak speed, but most of its energy still goes to moving data [P1 §II-C/D]. In Fig. 2b (powerline, normalised to π_flop) the memory-bound limit is B_ε/B_τ = 4.0 and the maximum is 1 + B_ε/B_τ = 5.0 [P1 Fig. 2b caption].

*Where it breaks down.* π₀ = 0 is not realistic; the paper's own measurements later found π₀ = 122 W on a GTX 580 [P1 Table IV].

### 1.7 Balance gap and race-to-halt [P1 §II-D, p. 664–665]

Compare the two ridges.

- **B_τ < B_ε (with π₀ = 0), a "balance gap".** The paper expects this "because both the time and energy of a mop tend to be relatively large compared to that of a flop". Kernels with B_τ < I < B_ε are compute-bound in time but memory-bound in energy. If raising intensity is the hard part of algorithm design, energy efficiency is harder to reach than time efficiency, and the gap ratio B_ε/B_τ measures how much harder. Corollary: I > B_ε implies I > B_τ, so **energy efficiency implies time efficiency, but not the converse**. "If we were to choose one metric for optimization, energy is the nobler goal" [P1 §II-D, p. 665].
- **B_τ > B_ε: time efficiency tends to imply energy efficiency.** This is when **race-to-halt** (run as fast as possible, then turn everything off; footnote 4) works [P1 §II-D].
- **With π₀ > 0** the same statements hold with B̂_ε(I) in place of B_ε [P1 §II-D, last paragraph].
- **B_τ = B̂_ε:** optimising for time and for energy are "most likely the same process" [P1 §II-B, p. 664].

The paper adds a caveat that matters in a viva: "roofs and arches are only bounds, so these high-level claims are only guidelines, rather than guaranteed relationships" [P1 §II-D].

Our verdict: B_τ = 9.03 > B̂_ε = 5.35 (turbo on) and 4.53 > 3.34 (turbo off), so **race-to-halt holds in both settings** [turbo_on/summary.txt, turbo_off/summary.txt]. A kernel that is fast is already within a factor of two of peak efficiency: at I = 16 (turbo on) we measured 4.91 of the 6.10 GFLOP/J asymptote [turbo_on/summary.json].

*Where it breaks down.* The verdict compares settings with *fixed* constants. Across DVFS settings the "slower" one can be more efficient (turbo off is 2–3× more efficient, §5), which the model cannot express.

### 1.8 Powerline [P1 §III, eq. 7–8, Fig. 2b, p. 665]

Average power P = E/T. With π_flop = ε_flop/τ_flop (flop power, excluding π₀), dividing eq. 5 by eq. 3 gives

> P = (π_flop/η_flop)·[min(I, B_τ)/B_τ + B̂_ε(I)/max(I, B_τ)]   [P1 eq. 7]

With π₀ = 0: as I → 0, P → π_flop·B_ε/B_τ; as I → ∞, P → π_flop; the maximum is at I = B_τ:

> P ≤ π_flop·(1 + B_ε/B_τ)   [P1 eq. 8]

The bigger the balance gap, the higher the peak power [P1 §III].

**The easier form, used in paper 2** [P2 eq. 7], with π_mem = ε_mem/τ_mem:
- I ≥ B_τ: P = π₀ + π_flop + π_mem·B_τ/I → π₀ + π_flop as I → ∞.
- I ≤ B_τ: P = π₀ + π_flop·I/B_τ + π_mem → π₀ + π_mem as I → 0.
- Peak at I = B_τ: **π₀ + π_flop + π_mem**, because both units run flat out at the same time.
(The two forms agree: π_flop·B_ε/B_τ = ε_mem/τ_mem = π_mem.)

Our numbers [viva_extras.md X2]: turbo on π_flop = 36.1 W, π_mem = 25.7 W, so limits π₀ + π_mem = 48.9 W (measured 49.8 W at I = 0.25) and π₀ + π_flop = 59.3 W (measured 61.6–65.8 W at I ≥ 32), and a predicted peak of 85.0 W against 67.2 W measured. Turbo off: 5.8 W and 8.0 W, limits 15.9 W and 13.6 W (measured 16.2 W and 13.6 W), peak 21.6 W vs 18.4 W measured.

*Where it breaks down.* The peak at B_τ is exactly where real chips hit power and thermal limits (§1.11).

### 1.9 The experiment [P1 §IV, Tables III–IV, Fig. 3–5, p. 665–668]

- **Platforms** [P1 Table III]: Intel Core i7-950 (Nehalem, 4 cores): 106.56 GFLOP/s single, 53.28 double, 25.6 GB/s, TDP 130 W. NVIDIA GTX 580 (Fermi): 1581.06 / 197.63 GFLOP/s, 192.4 GB/s.
- **Power measurement:** PowerMon 2 between the PSU and the devices (DC voltage and current on up to 8 channels, 1024 Hz per channel), plus a custom PCIe interposer for the GPU's motherboard supply. For CPU runs the GPU and unnecessary peripherals were removed. Each benchmark ran 100 times with samples every 7.8125 ms (128 Hz) [P1 §IV-A].
- **Microbenchmarks:** the GPU kernel mixes independent FMAs and loads, auto-tuned; the CPU kernel evaluates a polynomial, written in assembly; changing the polynomial degree changes I [P1 §IV-B]. Ours (`bench.c`) does the same thing with K dependent FMAs per loaded double, I = K/4.
- **Achieved:** GPU double 170 GB/s (88.3%) and 196 GFLOP/s (99.3%); CPU double 18.9 GB/s (73.8%) and 49.7 GFLOP/s (93.3%) [P1 §IV-B, p. 666].
- **Fit** [P1 eq. 9]: E/W = ε_s + ε_mem·(Q/W) + π₀·(T/W) + Δε_d·R, linear regression in R, where R = 1 for double precision. Time constants come from vendor peaks; energy constants from the regression. Normalising by W gave R² near 1 [P1 footnote 8].
- **Results** [P1 Table IV]: GTX 580 ε_s 99.7 pJ/flop, ε_d 212 pJ/flop, ε_mem 513 pJ/B, π₀ 122 W. i7-950 ε_s 371, ε_d 670 pJ/flop, ε_mem 795 pJ/B, π₀ 122 W. The identical π₀ "to three digits" is noted by the authors as a coincidence.
- **Balance points read from Fig. 4** (plot annotations, not a table) [P1 Fig. 4, p. 667]. Double: GPU B_τ 1.0, B̂_ε 0.79, B_ε(π₀ = 0) 2.4; CPU B_τ 2.1, B̂_ε 1.1, B_ε(π₀ = 0) 1.2. Single: GPU 8.2 / 4.5 / 5.1; CPU 4.2 / 2.1 / 2.1. Peak efficiencies: GPU 1.2 (double) and 5.7 (single) GFLOP/J; CPU 0.34 and 0.66 GFLOP/J.

*Where it breaks down.* Vendor peaks for τ (rather than measured peaks) make the time roofline optimistic, especially on the CPU (73.8% of peak bandwidth). We used measured peaks instead [report §3 "Fitting"].

### 1.10 What the fitted constants mean [P1 §V-A, p. 667]

- **ε_flop:** Keckler et al. give about 50 pJ per double FMA (25 pJ/flop). The fitted GPU value (212 pJ/flop) is about 8× larger because it includes instruction issue and microarchitectural overheads (registers, interconnect): about 187 pJ/flop of overhead.
- **ε_mem:** Keckler's DRAM + interface + wire estimate is 253–389 pJ/B. Adding ~47 pJ/B of instruction overhead gives 300–436, and ~7 pJ/B of L1/L2 read/write traffic gives 307–443 pJ/B. The fitted 513 pJ/B is higher, which "may reflect additional overheads for cache management, such as tag matching".
- **π₀:** no check is available, but GPU idle power was 39.6 W, so the fitted 122 W "accounts for much more than just idle power".
- CPU costs are higher than GPU costs: more complex cores, longer distance to memory, older process.

Ours: π₀ = 23.24 W against 2.86 W idle package power (8×) [turbo_on/summary.txt]. Same lesson as paper 1.

*Where it breaks down.* π₀ is a regression intercept, not a measured quantity. In our fit it trades off against ε_mem and ε_flop (±20% between seeds with 2% synthetic noise; run 1 and run 2 agree within 2%) [README "Open points"].

### 1.11 Power caps as the model's visible failure [P1 §V-B, Fig. 5, p. 667–668]

In all four cases of Fig. 4, B_τ exceeds B̂_ε, so time efficiency implies energy efficiency, "which explains why race-to-halt can be such an effective energy-saving strategy". "If architects could drive π₀ → 0, then the situation could reverse" (the GPU double-precision case: B_ε(π₀ = 0) = 2.4 > B_τ = 1.0). "However, for the Intel platform, even having π₀ = 0 does not invert the balance gap" [P1 §V-B].

The single-precision GPU does not track the roofline near B_τ. The model asks for 387 W there; the GTX 580's maximum power rating is 244 W. "Incorporating power caps will be an important extension for future work" [P1 §V-B, Fig. 5 caption].

Ours: the model asks for 85.0 W at B_τ; the laptop drew at most 67.2 W in Exp 1, and the points at I = 8 and 16 are 14–15% below the roof [turbo_on/summary.txt].

*Where it breaks down.* Exactly here. Paper 2's capped model is the fix (§2.3–2.4).

### 1.12 FMM_U refinement [P1 §V-C, p. 668–669]

The U-list phase of the fast multipole method: about 11 flops per point pair, O(q²) flops per O(q) points, typically compute-bound. About 390 GPU implementations existed from prior work. Using eq. 2 with DRAM bytes only (from L2-miss counters), energy was **under-estimated by 33% on average**. Measuring L1 and L2 bytes on a reference version and attributing the difference to them gave a cache-access cost of **187 pJ/B**. With that term, the ~160 variants that use only L1/L2 reuse were predicted with a **median error of 4.1%** [P1 §V-C]. The authors planned to derive separate L1, L2, texture and shared-memory costs.

Ours: matmul uses 1.4–2.4× more energy than the model predicts even when given its measured time [report §4.2], for the same reason.

*Where it breaks down.* One lumped cache cost for all levels; paper 2 splits it by level.

### 1.13 Work–communication trade-off [P1 §VII, eq. 10, p. 670]

Suppose a future machine has a real balance gap (B_ε > B_τ) and π₀ = 0. A "new" algorithm (f·W, Q/m) with f > 1 and m > 1 does more work to move less data. Greenup ΔE = E₁,₁/E_f,m (energy analogue of speedup). With π₀ = 0:
- E₁,₁ = W·ε_flop·(1 + B_ε/I); E_f,m = W·ε_flop·(f + B_ε/(m·I)).
- ΔE > 1 ⟺ **f < 1 + ((m − 1)/m)·(B_ε/I)** [P1 eq. 10].
- Even with no communication left (m → ∞), extra work is bounded by f < 1 + B_ε/I. If the baseline is already compute-bound in time (I ≥ B_τ), f < 1 + B_ε/B_τ.

The derivation is two lines and is ours; the paper says "one can easily show" and defers further analysis (speedup and greenup together) to tech report GT-CSE-12-01, which we do not have [P1 §VII, ref. 52]. The condition as printed is for π₀ = 0.

Our application: tiling is the f = 1, m > 1 case. With turbo on, m = 14.8 for b = 128 (from measured Q) and the allowance for extra work would be f < 5.7 at the naive kernel's intensity; for a compute-bound baseline f < 1.71 (turbo on) or 2.39 (turbo off) [viva_extras.md X3].

*Where it breaks down.* π₀ = 0; with constant power, extra flops also cost time and therefore constant energy.

### 1.14 The paper's own limitations [P1 §VII "Limitations", p. 670]

1. Latency is suppressed, assuming sufficient concurrency.
2. Only a two-level memory hierarchy.
3. No power caps, so the model can overestimate power and performance, though "at least the predictions appear empirically to give upper-bounds on power and lower-bounds on time".

The paper calls itself "just a first-cut at bridging algorithm and architecture analysis". It also notes it is an abridged version of a longer technical report [P1 Acknowledgements].

---

## 2. Paper 2 explained

*Symbols used in this section.* As in §1, plus π₁ = paper 2's name for constant power, Δπ = usable power above π₁ (the cap), π_mem = ε_mem/τ_mem, B_τ⁺ and B_τ⁻ = the edges of the power-capped region, ε_L1, ε_L2 = inclusive energy per byte from L1 and L2, ε_rand = energy per random access.

### 2.1 What is new [P2 abstract, §I-B, p. 447–448]

Two contributions. First, the model is extended with an explicit **power cap**, **cache energy costs**, and a measurement of **random memory access**. The cap matters because it predicts how much flops and memory operations must slow down to keep average power below a threshold. Second, the model is fitted to **twelve platforms** from nine systems: x86 (conventional and Xeon Phi), ARM, GPUs and hybrid APU/SoC processors [P2 §I-B]. All code is public (hpcgarage.org/archline). The authors present the approach as a way to make debates about future HPC building blocks "more quantitative, analytical, and insightful" [P2 abstract].

### 2.2 Notation difference: π₁ vs π₀

Paper 2 writes the constant power as **π₁**; paper 1 and our report write **π₀**. This guide keeps π₀ and writes "π₁ in paper 2" when quoting. Paper 2 adds that constant power "may include the power of other system components and peripherals, taken together", in contrast to "static power" in the literature [P2 §III-a, p. 449].

### 2.3 Model with a power cap [P2 §III, eq. 1–4, p. 449–450]

Energy is unchanged: E = W·ε_flop + Q·ε_mem + π₁·T [P2 eq. 1], or E = W·ε_flop·(1 + B_ε/I) + π₁·T [P2 eq. 2].

Time gains a third term. On top of π₁ the system has Δπ watts of usable power. Delivering the operation energy W·ε_flop + Q·ε_mem through Δπ watts takes at least (W·ε_flop + Q·ε_mem)/Δπ seconds, so

> T = max(W·τ_flop, Q·τ_mem, (W·ε_flop + Q·ε_mem)/Δπ) = W·τ_flop·max{1, B_τ/I, (π_flop/Δπ)·(1 + B_ε/I)}   [P2 eq. 3–4]

In words: if there is enough power to run at full speed, the old roofline applies; otherwise *all* operations are throttled, which the third term captures [P2 §III-c]. τ values are still throughput costs, "optimistic" by design [P2 §III-a].

*Where it breaks down.* The cap delays operations but keeps their energy per operation fixed. A real CPU at its limit lowers frequency and voltage, which also lowers energy per operation (§2.8, X2).

### 2.4 Capped powerline [P2 eq. 5–7, p. 450]

> B_τ⁺ = B_τ·max(1, π_mem/(Δπ − π_flop)),  B_τ⁻ = B_τ·min(1, (Δπ − π_mem)/π_flop)   [P2 eq. 5–6]

> P̄(I) = π₁ + { π_flop + π_mem·B_τ/I if I ≥ B_τ⁺;  π_flop·I/B_τ + π_mem if I ≤ B_τ⁻;  Δπ otherwise }   [P2 eq. 7]

Three regimes: memory-bound, cap-bound (power flat at π₁ + Δπ), compute-bound. If Δπ ≥ π_flop + π_mem, then B_τ⁻ = B_τ = B_τ⁺, the cap never binds, and the peak is π₁ + π_flop + π_mem at I = B_τ [P2 §III-d].

**Deriving B_τ⁺** (our two lines). For I > B_τ the cap term beats the flop term when ε_flop + ε_mem/I > τ_flop·Δπ, i.e. when I < ε_mem/(τ_flop·(Δπ − π_flop)). Since ε_mem/τ_flop = B_ε·π_flop = B_τ·π_mem, this is I < B_τ·π_mem/(Δπ − π_flop). The same argument on the memory side gives B_τ⁻.

**Our values** [viva_extras.md X2]:

| | π_flop | π_mem | Δπ | [B_τ⁻, B_τ⁺] |
|---|---|---|---|---|
| Turbo on | 36.1 W | 25.7 W | 44.0 W | [4.58, 29.4] flop/B |
| Turbo off | 5.8 W | 8.0 W | 10.5 W | [1.96, 7.7] flop/B |

Δπ is our choice: measured maximum Exp 1 power minus π₀ (67.2 − 23.2 = 44.0 W) [turbo_on/summary.txt]. Paper 2 fits Δπ by nonlinear regression [P2 §V-A]; this difference is listed in README "Open points".

### 2.5 Experimental setup [P2 §IV, Table I, Fig. 3, p. 450–452]

- Nine systems, twelve platforms: the hybrid NUC, APU and Arndale systems were measured as separate CPU and GPU platforms.
- Discrete coprocessors (GTX 580, 680, Titan, Xeon Phi) were measured **card only**, ignoring host power and transfers. Mobile boards were measured at **system level** (CPU, GPU, DRAM, peripherals). CPU systems were measured at the CPU input and the motherboard (which feeds DRAM) [P2 §IV-h].
- Hand-tuned microbenchmarks per platform: intensity (vary flops per loaded word; unrolling, FMAs, instruction selection, prefetching, assembly where needed), random access (pointer chasing), cache (data sets sized to each level; on GPUs L1/L2, shared memory or scratchpad depending on architecture) [P2 §IV-e,f,g].
- PowerMon 2 at 1024 Hz per channel, 3072 Hz aggregate; PCIe interposer for GPUs [P2 §IV-h].
- Single precision is the focus, since double is missing on several platforms [P2 §V].

### 2.6 Fitting and accuracy [P2 §V-A, Fig. 4, p. 452–453]

Nonlinear regression gives τ_flop, τ_mem, ε_flop, ε_mem, π₁ and Δπ (plus per-level costs) for each platform. Prediction errors (model − measured)/measured over all intensities form a distribution per platform. The capped model reduces the magnitude and spread of error on all platforms; the **bias is to over-predict**. A Kolmogorov–Smirnov test says the capped and uncapped error distributions differ (p < 0.05) on **7 of 12** platforms: Arndale GPU, NUC GPU, Arndale CPU, GTX 680, PandaBoard ES, Xeon Phi and APU GPU [P2 §V-A, Fig. 4].

### 2.7 Inclusive memory-hierarchy costs [P2 §V-B, p. 453]

Costs are **inclusive**: the cost of a memory-hierarchy operation is the additional energy to complete one more instance of it. ε_mem includes DRAM cells and wires, the memory controller, and the trip through L1 and L2. ε_L2 includes reading L2 cells plus writing and reading L1 on the way up, instruction overheads and coherence. Hence ε_L1 ≤ ε_L2 is expected and holds on every system (a sanity check). Reads and writes are not distinguished (ε_mem is an average). ε_rand reads a whole cache line plus overheads and is "at least an order of magnitude higher than ε_mem" [P2 §V-B].

Ours (turbo off, inclusive upper bounds): L1 62 < L2 71 < L3 96 < DRAM 219 pJ/B [turbo_off/summary.txt]. Our L1 value is large because it includes the load and add instructions per element [report §4.3].

### 2.8 Cross-platform findings [P2 §V-C, Fig. 5, Table I, p. 451–454]

**Table I (single-precision focus; values as printed, single precision ε_s and double ε_d in pJ/flop; parenthesised values are idle power or measured throughput):**

| Platform | π₁ (idle) W | Δπ W | ε_s pJ/flop (GFLOP/s) | ε_d (GFLOP/s) | ε_mem pJ/B (GB/s) | ε_L1 (GB/s) | ε_L2 (GB/s) | ε_rand nJ/acc (Macc/s) |
|---|---|---|---|---|---|---|---|---|
| Desktop CPU i7-950 (45 nm) | 122 (79.9) | 44.2 | 371 (99.4) | 670 (49.7) | 795 (19.1) | 135 (201) | 168 (120) | 108 (149) |
| NUC CPU i3-3217U (22 nm) | 16.5 (13.2) | 7.37 | 14.7 (55.6) | 24.3 (27.9) | 418 (17.9) | 8.75 (201) | 14.3 (103) | 54.6 (55.3) |
| NUC GPU HD 4000 | 10.1 (13.2)* | 17.7 | 76.1 (268) | – | 837 (15.4) | – | – | – |
| APU CPU E2-1800 (40 nm) | 20.1 (11.8) | 1.39 | 33.5 (13.4) | 119 (5.05) | 435 (3.32) | 84.0 (25.8) | 138 (11.6) | 75.6 (8.03) |
| APU GPU HD 7340 | 15.6 (11.8) | 3.23 | 5.82 (104) | – | 333 (8.70) | 6.47 (46.0) | – | 45.8 (115) |
| GTX 580 (40 nm) | 122 (148)* | 146 | 99.7 (1400) | 213 (196) | 513 (171) | 149 (761) | 257 (284) | 112 (977) |
| GTX 680 (28 nm) | 66.4 (100)* | 145 | 43.2 (3030) | 263 (147) | 437 (158) | 51 (1150) | 195 (297) | 184 (1420) |
| GTX Titan (28 nm) | 123 (72.9) | 164 | 30.4 (4020) | 93.9 (1600) | 267 (239) | 24.4 (1610) | 195 (297) | 48.0 (968) |
| Xeon Phi 5110P (22 nm) | 180 (90) | 36.1 | 6.05 (2020) | 12.4 (1010) | 136 (181) | 2.19 (2890) | 8.65 (591) | 5.11 (706) |
| PandaBoard ES OMAP 4460 (45 nm) | 3.48 (2.74) | 1.19 | 37.2 (9.47) | 302 (3.02) | 810 (1.28) | 79.5 (18.4) | 134 (4.12) | 60.9 (12.1) |
| Arndale CPU Exynos 5 (32 nm) | 5.50 (1.72) | 2.01 | 107 (15.8) | 275 (3.97) | 386 (3.94) | 76.3 (50.8) | 248 (15.2) | 138 (14.8) |
| Arndale GPU Mali T-604 | 1.28 (1.72)* | 4.83 | 84.2 (33.0) | – | 518 (8.39) | 71.4 (33.4) | – | 125 (33.6) |

\* fitted π₁ below the observed idle power (four platforms) [P2 Table I, note 1]. Transcribed from the text layer of the PDF; GTX 680 ε_L1 is printed as "51".

Findings [P2 §V-C]:
- Peak energy efficiency ranges from **16 GFLOP/J (GTX Titan) to 620 MFLOP/J (desktop Nehalem)** [P2 Fig. 5].
- Power within a platform varies only **0.65–1.15× of π₁ + Δπ** (under 2×), so there is "little room to reconfigure power". The obstacle is the large π₁.
- **π₁/(π₁ + Δπ) > 50% on 7 of 12 platforms**, and this fraction correlates with peak efficiency with a coefficient of about −0.6 (not shown in the paper). With the Table I values the seven are i7-950, NUC CPU, APU CPU, APU GPU, Xeon Phi, PandaBoard and Arndale CPU (our check).
- **π₁ can invert the ranking.** For a pure streaming workload, ε_mem alone ranks Xeon Phi best (136 pJ/B) ahead of GTX Titan (267) and Arndale GPU (518). Adding the constant-energy charge τ_mem·π₁ (994, 515 and 153 pJ/B) reverses the order: **Arndale GPU 671 pJ/B, GTX Titan 782 pJ/B, Xeon Phi 1.13 nJ/B**.
- The Arndale GPU reaches 8.1 GFLOP/J (half the Titan) but puts more power into memory, giving 1.5 GB/J vs 1.3 GB/J for the Titan.
- The cap model misfits on the NUC GPU (OS interference: OpenCL drivers only on Windows) and on the Arndale GPU, where the mid-range mismatch suggests "a different model of capping, perhaps one that [does] not assume constant time and energy costs per operation", with "active energy-efficiency scaling with respect to processor and memory utilization" even at fixed clock. Errors are always under 15% [P2 §V-C].

### 2.9 The Titan vs Arndale demonstration [P2 §I-A, Fig. 1, p. 447–448]

GTX Titan: 5 TFLOP/s single precision, 250 W TDP. Arndale GPU (Samsung Exynos 5): 72 GFLOP/s, developer board under 10 W. By flop/s per watt the Titan looks better. But the model says the two **match in flop/J for intensities up to about 4 flop/B** (sparse matrix-vector multiply is 0.25–0.5 flop/B single precision; a large FFT 2–4), and the Arndale is within 2× of the Titan even when compute-bound. A power-matched array of Arndale GPUs would have less than half the Titan's peak but up to **1.6× its bandwidth** for intensities up to about 4. Because this ignores the interconnect, the authors conclude the array would improve on the Titan "only marginally or not at all" [P2 §I-A].

*Inconsistency to know:* the text says matching the Titan's power "may require up to **42** Arndale GPUs"; the Fig. 1 caption and legend say **47** [P2 p. 447–448]. We quote both and do not pick one.

### 2.10 Throttling scenarios and power bounding [P2 §V-D, Fig. 6–7, p. 455–456]

- **Power throttling.** Set the cap to Δπ/k (k = 2, 4, 8), all else fixed including π₁. Because π₁ stays, cutting Δπ by k cuts total power by less than k. The Arndale GPU has the most room to cut system power this way; Xeon Phi, APU CPU and APU GPU the least. Memory-bound code on the Titan degrades least (power over-provisioned for compute); compute-bound code on the NUC CPU degrades least (over-provisioned for memory) [P2 §V-D-i].
- **Power bounding.** Halving a Titan node to 140 W corresponds to Δπ/8 and gives about **0.31×** the performance at I = 0.25. In the best case **23 Arndale GPUs** fit the same 140 W and are about **2.8× faster** at I = 0.25, better than the 1.6× of Fig. 1. "A lower power grainsize, combined with a compute building block having a lower π₁, may lead to more graceful degradation under a system power bound" [P2 §V-D-j].

Our version (X2): on the turbo-on constants, Δπ/8 (28.7 W total) gives 0.21× the speed at I = 0.25 and 0.14× at I = 64. The real turbo-off setting, at 18.4 W, beats every capped curve on efficiency, because it lowers the energy per operation instead of only delaying operations [viva_extras.md X2].

### 2.11 The paper's own limitations [P2 §I-B, §VI]

"The main limitation of our work is that, to permit parsimonious analysis, we have kept our model simple" [P2 §I-B]. "The main limitations of this work are its many simplifying assumptions and its microbenchmark-only evaluation. Consequently, there may be a considerable gap between the best-case abstract analysis of this paper and actual applications" [P2 §VI]. The authors list the Arndale GPU errors as something future models must explain.

---

## 3. The papers' figures and claims mapped to ours

| Paper item | What it shows | Our counterpart | Agree / differ, and why |
|---|---|---|---|
| P1 Fig. 2a roofline vs arch line | sharp roof, smooth arch, two balance points | `figures/turbo_on/fig1_roofline.png`, `fig2_archline.png` | Agree. Our arch has a mild knee at B_τ because π₀ > 0. |
| P1 Fig. 2b / Fig. 5 powerline | power peaks at B_τ | `figures/turbo_on/fig3_powerline.png`, `figures/turbo_off/fig3_powerline.png` | Shape agrees; turbo-on peak capped at 67.2 W vs 85.0 W predicted. |
| P1 Fig. 4 measured vs model with balance markers | model fits; B_τ > B̂_ε on both platforms | `figures/turbo_on/fig9_model_fit.png`; B_τ 9.03, B_ε 6.43, B̂_ε 5.35 | Agree: same verdict; energy error median 1.7% [turbo_on/summary.txt]. |
| P1 Table IV fitted coefficients | ε_flop, ε_mem, π₀ for i7-950 and GTX 580 | report §4.1 table | ε_flop 6.7× lower than the i7-950 (100 vs 670 pJ, double); ε_mem similar (641 vs 795, ours package-only). |
| P1 eq. 9 regression on E/W | linear fit, R² ≈ 1 | `analyze.py` NNLS on E/W (report §3 "Fitting") | Same form; we use non-negative least squares and measured peaks. |
| P1 §V-A π₀ ≫ idle | 122 W vs 39.6 W GPU idle | 23.2 W vs 2.86 W idle | Agree (8× vs 3×). |
| P1 §V-B power cap misfit | 387 W asked, 244 W limit | 85.0 W asked, 67.2 W drawn; I = 8, 16 sit 14–15% under the roof | Agree in kind. |
| P1 §V-C FMM_U needs a cache term | −33% energy without it | matmul energy 1.4–2.4× above the model even with measured T (report §4.2) | Agree in kind; we did not fit a cache term for matmul. |
| P1 §VII eq. 10 greenup | extra work allowed for less traffic | tiling: f = 1, m = 3.4–17.1 from `q_measured*.csv` [viva_extras.md X3] | Measured greenup 1.8–2.9× (turbo on), 1.3–2.2× (turbo off). |
| P2 eq. 3, eq. 7 capped time and power | cap flattens power, rounds the corner | green dashed curves in fig1/fig3; errors in `summary.txt` | Power error max 20.4% → 5.5% (turbo on); over-corrects at I = 8. |
| P2 Table I ε_L1 ≤ ε_L2 ≤ ε_mem | inclusive per-level costs ordered | `figures/turbo_off/fig4_data_reuse.png`: 62 / 71 / 96 / 219 pJ/B | Agree. Turbo-on L2 unreliable (throttled). |
| P2 π₁ > 50% of peak power on 7 of 12 | constant power dominates | π₀/(π₀ + Δπ) = 23.24/67.2 = 0.35 and 7.89/18.4 = 0.43 [viva_extras.md X2] | Lower than most of P2: package-only boundary excludes board, DRAM, PSU. Not directly comparable. |
| P2 power varies 0.65–1.15× within a platform | little room to reconfigure | Exp 1 power 49.8–67.2 W (0.74–1.00) and 13.6–18.4 W (0.74–1.00) [viva_extras.md X2] | Agree: under 1.4× across a 512× range of intensity. |
| P2 §V-C streaming cost ε_mem + π₁·τ_mem | constant power inverts rankings | ε_mem + π₀·τ_mem = 641 + 580 = 1221 pJ/B (turbo on); 219 + 217 = 436 pJ/B (turbo off) | Turbo off is 2.8× cheaper per streamed byte; constant power is half the cost in both. |
| P2 §V-C Arndale GPU cap misfit | constant per-op cost questioned | our over-correction at I = 8 (report §4.1 "Power cap") | Agree; we think the cause is DVFS at the limit. |
| P2 Fig. 6–7 throttling what-if | Δπ/k curves | `figures/viva/cap_whatif.png` [viva_extras.md X2] | Reproduced on our constants; real turbo off is far better than the model's throttle. |
| P2 ε_rand | random access ≥ 10× streaming | not measured | Say so. |
| P2 Fig. 1 cross-platform comparison | two building blocks cross over in efficiency | turbo on vs turbo off as two "building blocks" on one chip: `figures/comparison/cmp_archline.png`, `cmp_ratio.png` | Turbo off is slower everywhere but 2.0–2.9× more efficient at every I [comparison/comparison.md]. |

**Against the papers' platforms** (measurement boundary matters; numbers are not like-for-like):

| Platform | Boundary | Precision | Peak GFLOP/s | GB/s | ε_flop pJ | ε_mem pJ/B | π₀ / π₁ W | Peak GFLOP/J |
|---|---|---|---|---|---|---|---|---|
| Our i5-13420H, turbo on | CPU package (RAPL) | double | 361.7 | 40.1 | 99.8 | 641 | 23.2 | 6.10 |
| Our i5-13420H, turbo off | CPU package (RAPL) | double | 165.0 | 36.4 | 34.9 | 219 | 7.89 | 12.09 |
| i7-950, paper 1 | whole system at PSU | double | 49.7 | 18.9 | 670 | 795 | 122 | ≈ 0.34 |
| i7-950, paper 2 Table I | CPU input + motherboard | double (ε_d) | 49.7 | 19.1 | 670 | 795 | 122 | 0.62 (single, Fig. 5) |
| NUC CPU i3-3217U (Ivy Bridge), paper 2 | CPU input + motherboard | double (ε_d) | 27.9 | 17.9 | 24.3 | 418 | 16.5 | 3.2 (single, Fig. 5) |

The NUC's double-precision ε_d (24.3 pJ) is below our turbo-off ε_flop (34.9 pJ) even though its boundary is wider. We think this reflects how the regression splits energy between ε_flop and π₁ (its π₁ is 69% of its peak power), not a cheaper flop; this is inference.

---

## 4. Evaluator question bank

Answers start with the direct answer. Symbols: W flops, Q bytes, I = W/Q, B_τ time balance, B_ε energy balance, B̂_ε effective energy balance, π₀ constant power, η_flop = ε_flop/(ε_flop + ε₀), ε₀ = π₀·τ_flop.

### A. Conceptual

**Q1. What question does the energy roofline answer that the time roofline cannot?**
Whether optimising for speed also optimises for energy, and how much intensity is needed for a target energy efficiency. The time roofline only says whether a kernel is memory- or compute-bound in time. The energy model adds a second ridge (B̂_ε) and the comparison of the two tells you whether race-to-halt works [P1 §I, §II-D]. It also predicts average power (the powerline), which the time roofline says nothing about.

**Q2. What are W, Q and I, and why is I a property of the algorithm (and of Z)?**
W is the number of useful operations (flops), Q the bytes moved between slow and fast memory, and I = W/Q in flop/byte [P1 §II-A]. I is fixed by the algorithm and how it reuses data, not by the machine's speed. But Q depends on the fast-memory size Z: matmul's intensity is at most O(√Z), while an array sum is O(1) regardless of Z [P1 p. 662]. Our matmul goes from I = 1.28 (naive) to 19 (128-wide tiles) on the same machine [turbo_on/summary.txt].

**Q3. Why does time use max and energy use a sum?**
Flops and memory transfers can run at the same time, so the slower of the two sets the run time. Energy cannot overlap: every flop and every byte costs energy whether or not it happens in parallel with something else [P1 §II-B, "time costs may be overlapped whereas energy may not"]. Constant power adds a third term proportional to time.

**Q4. Why is the arch line smooth and the roofline cornered?**
The roofline is min(1, I/B_τ), a max of two straight lines, so it has a corner at B_τ. The arch line is 1/(1 + B̂_ε/I), a sum of two terms, so it bends gradually and reaches half of peak at the energy balance point [P1 §II-C]. With π₀ > 0 the π₀·T term inherits the roofline's corner, so fitted arch lines have a mild knee at B_τ (visible in `figures/turbo_off/fig2_archline.png`).

**Q5. What is B_τ physically? What is B_ε? Why do both have unit flop/byte?**
B_τ = τ_mem/τ_flop = peak flop/s ÷ peak byte/s: how many flops the machine can do in the time it moves one byte (ours 9.03). B_ε = ε_mem/ε_flop: how many flops cost the same energy as moving one byte (ours 6.43) [turbo_on/summary.txt]. Both are (cost per byte)/(cost per flop), so the cost units cancel and leave flop/byte. Paper 1's Table I writes "flops per Joule" for B_ε, which is a typo [report §2.1].

**Q6. What is π₀, and why is it neither idle power nor leakage alone?**
π₀ is the power drawn for as long as the program runs, whatever operations execute [P1 eq. 4]. Ours is 23.2 W against 2.86 W idle [turbo_on/summary.txt]. It is the power of a chip that is *awake*: cores and uncore at full clock and voltage, caches and ring powered, leakage at operating temperature. It is fitted as a regression intercept, so it also absorbs anything not proportional to flops or bytes. Paper 1 found the same: 122 W fitted vs 39.6 W GPU idle [P1 §V-A].

**Q7. What do ε₀ and η_flop mean? What does η_flop = 0.61 vs 0.42 tell you?**
ε₀ = π₀·τ_flop is the constant energy burned during one flop at peak rate; η_flop = ε_flop/(ε_flop + ε₀) is the fraction of a flop's real cost that is the arithmetic itself [P1 §II-B]. Turbo on: 99.8 pJ of arithmetic + 64.3 pJ of constant energy, so η = 0.61. Turbo off: 34.9 + 47.8 pJ, so η = 0.42 [turbo_on/summary.txt, turbo_off/summary.txt]. With turbo off the arithmetic got 3× cheaper but the constant energy per flop only 1.3× cheaper, so constant power dominates more.

**Q8. Why is B̂_ε a function of I, and which single number do you quote?**
B̂_ε(I) = η·B_ε + (1 − η)·max(0, B_τ − I) depends on I because constant energy depends on run time, and run time depends on whether the kernel is memory-bound (I < B_τ) [P1 eq. 6]. The single number we quote is the fixed point I = B̂_ε(I), where the arch line reaches half its peak: 5.35 (turbo on), 3.34 (turbo off) [report §2.2]. This is the same definition `analyze.py` uses.

**Q9. Why is B̂_ε < B_ε on our machine? Is it always?**
Ours: 5.35 < 6.43 and 3.34 < 6.28. It is not a theorem. When the half-peak point is below B_τ, B̂_ε = (η·B_ε + (1 − η)·B_τ)/(2 − η), and B̂_ε < B_ε exactly when B_τ < 2·B_ε (we check 9.03 < 12.86 and 4.53 < 12.56). When it is above B_τ, B̂_ε = η·B_ε ≤ B_ε always. Intuitively, constant power pulls B̂_ε towards B_τ/2: down if B_τ/2 < B_ε, up otherwise. Paper 1 says only that higher π₀ lowers η and "would cause B̂_ε(I) to be lower than B_ε" [P1 §II-D].

**Q10. What does B_τ > B̂_ε mean in practice? What would B̂_ε > B_τ mean?**
B_τ > B̂_ε: by the time a kernel is compute-bound in time (I > B_τ), it is already past the energy ridge, so within 2× of peak efficiency. Making code faster makes it greener; race-to-halt works [P1 §II-D, §V-B]. B̂_ε > B_τ: kernels with B_τ < I < B̂_ε are at full speed but still memory-bound in energy; cutting bytes would save energy without saving time, so energy must be optimised separately [P1 §II-D].

**Q11. What is race-to-halt, and why does a large π₀ favour it?**
Run as fast as possible, then turn everything off [P1 footnote 4]. Constant energy is π₀·T, so any speed-up removes part of it. A large π₀ makes that term a large share of the bill (35–47% of our energy with turbo on, 43–56% with turbo off [report §4.5]) and lowers η, pulling B̂_ε below B_τ.

**Q12. Why does the powerline peak at B_τ?**
At I = B_τ the flop units and the memory system are both running at full rate, so both dynamic powers are drawn at once: P = π₀ + π_flop + π_mem [P2 eq. 7]. Away from B_τ one of them idles part of the time. Ours predicts 85.0 W at B_τ (turbo on) and 21.6 W (turbo off) [turbo_on/summary.txt, turbo_off/summary.txt].

**Q13. "Energy is the nobler goal": what does paper 1 mean?**
If B_τ < B_ε, then I > B_ε implies I > B_τ: an energy-efficient algorithm is automatically time-efficient, but a time-efficient one need not be energy-efficient. So if you could pick only one metric, optimising energy gets you both [P1 §II-D, p. 665]. This holds only when the balance gap exists; on our machine (B_τ > B̂_ε) the reverse is true and time is the sufficient goal.

### B. Derivation

**Q14. Derive E = W·ε̂_flop·(1 + B̂_ε(I)/I) from eq. 3 and eq. 4.**
Substitute T = W·τ_flop·max(1, B_τ/I) into E = W·ε_flop + Q·ε_mem + π₀·T. The constant term becomes W·ε₀·max(1, B_τ/I) with ε₀ = π₀·τ_flop, and max(1, B_τ/I) = 1 + max(0, B_τ − I)/I. Collect over ε̂_flop = ε_flop + ε₀: E = W·ε̂_flop·[1 + (ε_mem/ε̂_flop + (ε₀/ε̂_flop)·max(0, B_τ − I))/I]. Finally ε_mem/ε̂_flop = η·B_ε and ε₀/ε̂_flop = 1 − η (guide §1.4) [P1 eq. 5–6].

**Q15. Show that efficiency is half its peak at I = B_ε when π₀ = 0.**
With π₀ = 0, E = W·ε_flop·(1 + B_ε/I), so normalised efficiency is 1/(1 + B_ε/I). At I = B_ε this is 1/2. Equivalently, flop energy W·ε_flop equals memory energy Q·ε_mem when W/Q = ε_mem/ε_flop, and a + b ≤ 2·max(a, b) [P1 footnote 3].

**Q16. Derive the closed form for the half-peak point with π₀ > 0 and check it with our numbers.**
Set B̂_ε(I) = I. For I < B_τ: η·B_ε + (1 − η)·(B_τ − I) = I, so I = (η·B_ε + (1 − η)·B_τ)/(2 − η), valid if η·B_ε < B_τ; otherwise I = η·B_ε. Turbo on: (0.608 × 6.43 + 0.392 × 9.03)/1.392 = 5.35. Turbo off: (0.422 × 6.28 + 0.578 × 4.53)/1.578 = 3.34 [turbo_on/summary.txt, turbo_off/summary.txt]. The derivation is ours; paper 1 gives eq. 6 and the half-peak interpretation.

**Q17. Derive the race-to-halt condition ε_mem < B_τ·(ε_flop + ε₀).**
From Q16, B̂_ε < B_τ in the first case iff η·B_ε + (1 − η)·B_τ < (2 − η)·B_τ iff η·B_ε < B_τ; in the second case B̂_ε = η·B_ε, so again iff η·B_ε < B_τ. And η·B_ε = ε_mem/(ε_flop + ε₀). So race-to-halt ⟺ ε_mem < B_τ·(ε_flop + ε₀) [report §4.7]. Turbo on: 641 < 9.03 × 164.1 = 1482 pJ/B. Turbo off: 219 < 4.53 × 82.7 = 375 pJ/B.

**Q18. Derive the powerline limits and the peak, and check them against 85.0 W and 21.6 W.**
For I ≥ B_τ, T = W·τ_flop, so P = π₀ + π_flop + ε_mem/(I·τ_flop) = π₀ + π_flop + π_mem·B_τ/I. For I ≤ B_τ, T = Q·τ_mem, so P = π₀ + π_flop·I/B_τ + π_mem. Limits: π₀ + π_mem (I → 0), π₀ + π_flop (I → ∞), peak π₀ + π_flop + π_mem at B_τ [P2 eq. 7]. Turbo on: 23.24 + 36.1 + 25.7 = 85.0 W. Turbo off: 7.89 + 5.8 + 8.0 = 21.6 W [viva_extras.md X2].

**Q19. Derive the capped time model and B_τ⁺, B_τ⁻.**
With only Δπ watts above π₀, the operation energy W·ε_flop + Q·ε_mem needs at least that divided by Δπ seconds, which becomes a third term in the max [P2 eq. 3]. For I > B_τ the cap binds when ε_flop + ε_mem/I > τ_flop·Δπ, i.e. I < B_τ·π_mem/(Δπ − π_flop) = B_τ⁺. For I < B_τ it binds when I·ε_flop + ε_mem > τ_mem·Δπ, i.e. I > B_τ·(Δπ − π_mem)/π_flop = B_τ⁻ [P2 eq. 5–6]. Ours: [4.58, 29.4] (turbo on), [1.96, 7.7] (turbo off) [viva_extras.md X2].

**Q20. Derive the greenup condition f < 1 + ((m − 1)/m)·(B_ε/I).**
With π₀ = 0, baseline energy is W·ε_flop·(1 + B_ε/I) and the new algorithm's is W·ε_flop·(f + B_ε/(m·I)). Greenup > 1 iff 1 + B_ε/I > f + B_ε/(m·I), which rearranges to the condition [P1 eq. 10]. As m → ∞ the bound becomes 1 + B_ε/I; for a compute-bound baseline, 1 + B_ε/B_τ (1.71 turbo on, 2.39 turbo off) [viva_extras.md X3]. The derivation is ours; the paper says "one can easily show".

**Q21. Why divide the regression by W (eq. 9), and why is π₀ weakly identified?**
Dividing by W puts every configuration on a per-flop scale, so the high-energy compute-bound runs do not dominate the fit; paper 1 reports R² near 1 this way [P1 footnote 8]. π₀ multiplies T/W, which equals τ_mem·(Q/W) when memory-bound and τ_flop when compute-bound. So in each regime π₀ is nearly collinear with ε_mem or with the constant ε_flop, and trades off against them. With 2% synthetic noise π₀ varied ±20% across seeds; our real data reproduced within 2% [README "Open points"].

### C. Method and measurement

**Q22. What does RAPL package energy include and exclude? Why no DRAM energy?**
It includes the cores, caches, ring interconnect, memory controller and CPU-side PHY. It excludes the DRAM devices (activation, refresh, DIMM I/O), the board, fans and PSU losses [report §4.7]. This CPU exposes no RAPL DRAM domain, so there was nothing to read [report §3]. The papers measured at the PSU or board, so our constants are not directly comparable with theirs.

**Q23. How accurate is RAPL, and why at least 1 s per run and the median of 3?**
RAPL updates about every 1 ms, so a run of 1 s or more keeps quantisation error below 0.1% [report §3]. Three repeats show stability; the median ignores one disturbed repeat where a mean would not. Repeat spread was typically 1–3% [slides_outline.md Q&A]. We did not calibrate RAPL against an external meter: say so if asked.

**Q24. How is the synthetic kernel built, and why is I = K/4 exact?**
For every double in a large array it loads the value, applies K dependent FMAs (x = x·a + b) and accumulates the result [`bench.c`]. Per element W = 2K flops (one FMA = 2 flops) and Q = 8 bytes (one load, nothing written back to the array), so I = 2K/8 = K/4. We used K = 1 … 512, i.e. I = 0.25 … 128 [`run.sh`, report §3]. Eight independent FMA chains per block hide FMA latency so high K reaches near-peak flop/s.

**Q25. How did you measure Q for the real kernels? Why was the analytic naive-matmul Q 5× too high?**
With perf on the memory-controller counters `uncore_imc_free_running_{0,1}/data_read,data_write/`. We ran 1 rep and R reps, took the difference to cancel setup traffic, subtracted idle background traffic (2.1–2.5 GB/s, mainly display scan-out), and divided by R − 1 [notes.txt "How Q was obtained"]. The method reproduces tiled analytic Q within about 1%. Naive matmul's analytic 8n³ assumes B is re-streamed from DRAM for every row; in reality the 8 threads share B through the 12 MB L3, so measured Q was 0.195× analytic and I = 1.28, not 0.25.

**Q26. How do you know runs were not throttled?**
A background thread in `rapl.h` samples PL1 and package temperature every 50 ms during the timed region, and the kernel's thermal_throttle counters (events and total throttled time) are compared before and after. A run is flagged if it was throttled for more than 2% of its time or if PL1 dropped below nominal. Flagged runs are retried up to three times after a cool-down; still-flagged rows are recorded in `run_flags.csv` [README "Throttling handling"]. No Exp 1 row was throttled in any dataset [turbo_on/summary.txt].

**Q27. What did you do with throttled rows, and which results rest on them?**
`analyze.py` drops them before every fit; configurations with all repeats throttled are plotted hollow or hatched [report §3]. Turbo on: 21 of 171 rows (reuse L2 K = 1, 2, 4; L3 K = 4; tiled matmul b = 64, 128). So turbo-on L2 energy (275 pJ/B) and the turbo-on tiled b = 64/128 numbers are unreliable; we quote turbo-off values for those (0 of 117 throttled) [turbo_on/summary.txt, report §4.3].

**Q28. Why did hybrid cores need load balancing?**
With an equal static split, 8 threads reached only 211 GFLOP/s, below the 4 P-cores alone (254), because the P-cores finished and waited for the E-cores [notes.txt change 1]. Each thread now owns a slice sized to its measured speed (P:E ≈ 1.43:0.58 when compute-bound), and all reps run in one parallel region. This raised 8-thread peak to about 362 GFLOP/s [report §3].

**Q29. How were the peaks obtained, and how do they compare with theory?**
The peaks are the highest measured flop/s and byte/s in Exp 1, not vendor numbers [report §3 "Fitting"]. Theoretical double-precision peak at maximum turbo is 4×4.6 GHz×16 + 4×3.4 GHz×8 ≈ 403 GFLOP/s; we reached 361.7 (90%). At base clocks theory is ≈ 182 GFLOP/s; turbo off reached 165.0 (91%) [report §3]. Paper 1 used vendor peaks for τ.

**Q30. How were the per-level energies fitted, and why are they "inclusive upper bounds"?**
For each working-set size (L1, L2, L3, DRAM) we held ε_flop and π₀ at their Exp 1 values and fitted the remaining energy against Q, with relative-error weights so the low-K points carry the fit [report §3, README "Open points"]. Everything not explained by flops and constant power is assigned to the bytes, so the load instruction, address arithmetic and loop overhead per element are included. That is why our L1 (62–195 pJ/B) is far above an SRAM access. Paper 2 defines its cache costs inclusively too [P2 §V-B].

**Q31. How was Δπ chosen, and how does that differ from paper 2?**
Δπ = highest measured Exp 1 power − fitted π₀: 67.2 − 23.2 = 44.0 W (turbo on), 18.4 − 7.9 = 10.5 W (turbo off) [turbo_on/summary.txt, turbo_off/summary.txt]. Paper 2 fits Δπ by nonlinear regression together with the other parameters [P2 §V-A]. Our rule guarantees the capped powerline passes through the measured maximum, but it is a judgement call [README "Open points"].

**Q32. How do you know the fitting code is right?**
`make_fake_data.py --check` generates synthetic data from planted parameters. Without noise the fit recovers them exactly and drops flagged rows; with 2% noise the medians over nine seeds stay within 5% of the planted values [report §3]. In addition, ε_flop and ε_mem from run 1 match an independent check in `notes.txt`.

**Q33. How repeatable is it?**
Run 2 reproduces every fitted parameter within 3.3% (e.g. ε_flop 99.8 vs 100.8 pJ, ε_mem 641 vs 627 pJ/B, B̂_ε 5.35 vs 5.31) [report §4.1, figures/repeatability/comparison.md]. Caveat: run 2 was on the same day, without a reboot [notes.txt anomaly 5].

**Q34. Why is psys unusable here?**
The psys (platform) RAPL domain on this laptop reads about 0.3 W regardless of load, so it does not track activity. We log it but never use it, and the idle measurement counts package domains only [notes.txt "RAPL domains", report §3].

### D. Results

**Q35. State the machine model in five numbers and the verdict.**
Turbo on: peak 361.7 GFLOP/s, 40.1 GB/s, ε_flop 99.8 pJ, ε_mem 641 pJ/B, π₀ 23.2 W. That gives B_τ 9.03, B_ε 6.43, B̂_ε 5.35, so B_τ > B̂_ε: race-to-halt holds. Peak efficiency 6.10 GFLOP/J; energy error median 1.7%, max 4.9% [turbo_on/summary.txt].

**Q36. How does our CPU compare with paper 1's i7-950 and paper 2's platforms?**
Against the i7-950 (double): 7× the flop rate, 2× the bandwidth, ε_flop 6.7× lower (100 vs 670 pJ), ε_mem slightly lower (641 vs 795 pJ/B, ours package-only), π₀ much lower (23 vs 122 W, ours package-only) [report §4.1, P1 Table IV]. So B_ε has risen from ≈ 1.2 to 6.4. Against paper 2, our peak efficiency (6.1 turbo on, 12.1 turbo off, double precision) would sit among their GPUs and the Xeon Phi, far above their CPUs (0.62–3.2 GFLOP/J single) [P2 Fig. 5]; the boundaries differ, so this is indicative only.

**Q37. Why is our π₀ far below 122 W and far above idle?**
Below 122 W: RAPL measures the package only, while paper 1 measured the whole desktop at the PSU (motherboard, DRAM, fans, PSU losses) on a 2009 platform [report §4.1]. Above idle: π₀ is the power of the chip awake at full clock while working, not of a chip in deep sleep states [Q6]. Ratio to idle: ours 8×, paper 1's GPU 3×.

**Q38. Where do the real kernels sit and why is matmul's energy under-predicted?**
All lie below the roofline and the arch line, as a bound expects [report §4.2]. Triad takes 1.3× the roof time and its energy is predicted within 3% (turbo on) and 2% (turbo off) once given its measured time. Matmul takes 2–5× the roof time and uses 1.4–2.4× the predicted energy even with measured time, because its heavy L1/L2 reuse is not in Q (DRAM bytes only). Paper 1 found the same with FMM_U and added a 187 pJ/B cache term [P1 §V-C].

**Q39. What does data reuse buy?**
Per level (turbo off): L1 62, L2 71, L3 96, DRAM 219 pJ/B, so an L1 byte costs 0.28× a DRAM byte [report §4.3]. At I = 0.25 efficiency differs 4× between L1 and DRAM (0.81 vs 0.20 GFLOP/J, turbo on). In a real kernel, 128-wide tiling raises matmul's DRAM intensity from 1.3 to 19, cuts time 3.5× and energy 2.9×; efficiency improves 2.9× (turbo on) and 2.2× (turbo off) [report §4.3].

**Q40. What is the energy-optimal thread count and why does it depend on I?**
I = 0.25: fastest at 8 threads but most efficient at 2 (0.25 vs 0.20 GFLOP/J). I = 4: best at 4. I = 64: best at 12 [turbo_on/summary.txt]. Memory-bound code saturates bandwidth at about 4 threads; more threads add 2–5 W each without speed, so energy rises (21 J → 28 J). Extra threads pay only when they cut time enough to save constant energy, which is the compute-bound case [report §4.4].

**Q41. Where does the energy go?**
Turbo on, constant energy is 35–47% of the total at every intensity; turbo off, 43–56% [report §4.5]. At I = 0.25 memory and constant energy split the bill evenly, flops are 2%. At I = 64 flops are 57% but more than a third is still constant energy [turbo_on/summary.txt]. This is why race-to-halt is attractive here, and why paper 2 says reducing π₁ matters most [P2 §VI].

**Q42. What is the main finding of turbo on vs off, and why do all three constants fall about 3×?**
Turbo off makes every kernel 2.0–2.9× more energy-efficient at every intensity (peak 6.1 → 12.1 GFLOP/J), at a speed cost of 9% (memory-bound) to 56% (compute-bound) [report §4.6]. ε_flop, ε_mem and π₀ each fall to 0.34–0.35× [comparison/comparison.md]. We think this is the voltage: dynamic energy per operation scales roughly with V², and both ε_flop and the on-chip part of ε_mem run on the core/uncore voltage. We did not measure voltage, so this is a hypothesis. B_ε stays near 6.3 because both energies scale together; B_τ halves because flops slow and bandwidth does not.

**Q43. Why does the capped model over-correct at I = 8 with turbo on but fit well with turbo off?**
Paper 2's cap keeps ε_flop and ε_mem fixed and stretches time until power fits under Δπ. Our CPU reaches its limit by lowering clock and voltage, which also lowers energy per operation, so the real slowdown is smaller: at I = 8 the run takes 1.18× the roof time, while the capped model predicts 1.31× [slides_outline.md Q&A]. With turbo off, power (≤ 18.4 W) is far below every limit and clocks stay at base, so the cap only shapes the corner and fits well (max energy error 7.2% → 2.5%) [turbo_off/summary.txt].

**Q44. With turbo off, why do compute-bound runs draw less power than memory-bound ones?**
Because π_mem (8.0 W) > π_flop (5.8 W) at base clocks: moving data at full bandwidth costs more power than computing at full flop rate [viva_extras.md X2]. So the powerline falls from 16.2 W at I = 0.25 to 13.6 W at I = 128, after peaking at 18.4 W near B_τ [turbo_off/summary.json]. With turbo on the order reverses (π_flop 36.1 W > π_mem 25.7 W).

### E. "What if"

**Q45. What if π₀ → 0?**
Turbo on: race-to-halt still holds, because B_ε (6.43) < B_τ (9.03); with π₀ = 0, B̂_ε = B_ε = 6.43, still below B_τ. This is the situation paper 1 described for its Intel CPU ("even having π₀ = 0 does not invert the balance gap") [P1 §V-B, viva_extras.md X1]. Turbo off: it flips once π₀ < π₀* = (ε_mem/B_τ − ε_flop)/τ_flop ≈ 2.2 W, which is below the idle package power (2.71 W). So in practice the turbo-off verdict also holds, but only because of constant power.

**Q46. What if π₀ were just the idle power?**
Then B̂_ε would be 6.16 (turbo on, still < 9.03) and 4.33 (turbo off, still < 4.53, barely) [viva_extras.md X1]. Race-to-halt would survive in both settings, with very little margin at turbo off. The model would also predict much lower energy for slow runs, which the measurements contradict: the fitted π₀ is what fits the data.

**Q47. What if you could measure DRAM energy?**
ε_mem would rise and so would B_ε and B̂_ε. With turbo on the verdict survives up to 840 pJ/B of extra DRAM energy, more than twice Keckler's whole 253–389 pJ/B estimate. With turbo off it flips at only 156 pJ/B (238 pJ/B if DRAM background adds 3 W to π₀), below the Keckler range [report §4.7]. The turbo-off efficiency advantage would shrink but not reverse, because DRAM device energy does not depend on core clock.

**Q48. What if a power cap of half the current power were imposed?**
Paper 2's model on our turbo-on constants: Δπ/2 (45.2 W total) gives 0.83× the speed at I = 0.25 and 0.55× at I = 64, with lower efficiency; Δπ/8 (28.7 W) gives 0.21× and 0.14× [viva_extras.md X2]. The real chip does better: turbo off draws at most 18.4 W, less than even the Δπ/8 bound, and is *more* efficient than uncapped turbo on (0.56 vs 0.20 GFLOP/J at I = 0.25). The turbo-on model cannot reach 18.4 W at all, because its π₀ alone is 23.2 W.

**Q49. What if the kernel used AVX-512, or single precision?**
Not measured; any numbers would be unverified. Qualitatively, twice the flops per instruction would halve τ_flop and roughly double B_τ, and ε_flop per flop would likely fall (one instruction's overhead spread over more flops), raising B_ε. Paper 1 saw single precision raise B_τ on both platforms (GPU 1.0 → 8.2, CPU 2.1 → 4.2) and lower ε (GPU 212 → 99.7 pJ/flop) [P1 Fig. 4, Table IV]. Our i5-13420H has no AVX-512 [report §3].

**Q50. What if memory bandwidth doubled? What if cores doubled at fixed bandwidth?**
Double bandwidth: τ_mem halves, B_τ halves (≈ 4.5), memory-bound kernels run 2× faster and save constant energy; if ε_mem stays the same, B_ε is unchanged, so B̂_ε moves towards B_τ and race-to-halt gets closer to failing. Double cores: τ_flop halves, B_τ doubles (≈ 18), more kernels become memory-bound; ε₀ = π₀·τ_flop halves if π₀ stays fixed, so η rises. These are model extrapolations, not measurements.

**Q51. What if the metric were energy-delay product instead of energy?**
EDP penalises slowness. Turbo off / turbo on EDP per flop is 0.39 for I ≤ 2, 0.52 at I = 4, 0.82 at I = 8, 0.93 at I = 16 and 1.07–1.13 for I ≥ 32 [viva_extras.md X3]. So under EDP turbo off still wins for memory-bound and balanced code and loses slightly for compute-bound code. Paper 1 lists EDP, flop/W and the Green Index as alternative metrics it does not study [P1 §VI "Metrics"].

**Q52. What if the run lasted minutes rather than 1 s?**
PL1 = 45 W applies after 56 s, and the package reaches 95–98 °C within 1–2 s at 60–85 W [report §3, notes.txt anomaly 1]. A preliminary run without throttle detection measured K = 512 at 250–260 GFLOP/s and 31 W instead of 356 GFLOP/s and 62 W [report §5 weakness 2, `data/.../prelim_throttled/`]. So sustained turbo-on constants would differ; turbo off, at 18.4 W, would barely change.

**Q53. What if the access pattern were random?**
Paper 2 measured pointer chasing: ε_rand is at least 10× ε_mem because each access fetches a whole cache line plus overheads [P2 §V-B]; e.g. i7-950 108 nJ/access [P2 Table I]. We did not measure it. In the model, random access means a much larger effective ε_mem and τ_mem per useful byte, which lowers the effective intensity.

**Q54. What if only E-cores or only P-cores were used?**
Our Exp 3 runs 1–4 threads on P-cores only (places fill in core-id order), so those points are P-only [report §3]. We have no E-only data; say so. Adding E-cores (6–8 threads) gave smaller gains per thread than adding P-cores [report §4.4]. The model has one chip-wide τ_flop and ε_flop, so it cannot represent the mix.

**Q55. Would you ship with turbo off?**
Depends on whether time has value. For energy alone, yes: 2–3× better at every intensity. Under EDP, turbo off is better for I ≤ 16 and slightly worse above [viva_extras.md X3]. For latency-critical compute-bound work, no: it is 2.2× slower. The model cannot make this decision because it has no frequency or voltage term [report §4.6].

### F. Critique

**Q56. What are the model's three most serious assumptions?**
(1) Fixed energy and time per operation, i.e. one DVFS state: turbo changes all energy constants by 3× [report §4.6]. (2) Perfect overlap and enough concurrency (the max()): points near B_τ sit 14–19% below the roof [summary.txt files]. (3) Only DRAM traffic costs energy: matmul is under-predicted 1.4–2.4× [report §4.2]. A fourth for this laptop: no power or thermal limits, fixed in part by paper 2's cap.

**Q57. Is "race-to-halt holds" a meaningful statement if turbo off is 2× better?**
Yes, but it is narrower than it sounds. It means: at a fixed frequency and voltage, a faster version of the code uses less energy. It does not mean the fastest hardware setting is the most efficient; across settings the slower one wins [report §4.6]. The model compares code at one operating point; choosing the operating point is outside it.

**Q58. Is π₀ a real physical quantity or a fitting artefact?**
Both. Physically it is the power of the awake chip that is not attributed to individual flops or bytes. Statistically it is a regression intercept that is weakly identified and absorbs whatever is time-proportional [README "Open points"]. Evidence it is meaningful: it reproduces within 2% across runs, scales with turbo like the other constants (0.34×), and explains why slow runs cost more. Evidence it is a catch-all: it is 8× idle, and paper 2 found four platforms where the fitted π₁ is *below* idle [P2 Table I note 1].

**Q59. Is a 1.7% median energy error impressive, given the model was fitted on the same kernel?**
Partly. It is an in-sample fit of 3 parameters (plus 2 measured peaks) to 10 points, so low error is expected; it shows the functional form is right, not that the model predicts. The out-of-sample tests are weaker: triad within 3%, matmul off by 1.4–2.4× [report §4.2]. Repeatability (run 2 within 3.3%) and the synthetic-data check show the fit is stable [report §3].

**Q60. Why trust ε_mem without DRAM energy?**
Trust it as what it is: the CPU-side cost of moving a byte from DRAM (loads, caches, ring, controller, PHY), a lower bound on the full cost [report §4.7]. Time and bandwidth are unaffected. The sensitivity analysis shows how much missing energy each conclusion can tolerate (840 pJ/B turbo on, 156 pJ/B turbo off) [report §4.7].

**Q61. What is the weakest part of your own study, and what would you do with one more week?**
Weakest: package-only energy, which makes the turbo-off verdict fragile, and one machine. With a week: measure wall power with an external meter to get system-level constants; run Exp 3 with turbo off; repeat after a reboot; fit a per-level cache term and test it on matmul; sweep fixed frequencies (not just turbo on/off) to model the constants as functions of frequency.

**Q62. How would you extend the model for DVFS and heterogeneous cores?**
DVFS: make the constants functions of the operating point, e.g. ε_flop(f, V) ≈ c·V², π₀(V) including leakage, τ_flop ∝ 1/f, τ_mem nearly constant, and minimise E (or EDP) over f as well as over the algorithm [report §5]. Heterogeneity: give each core type its own τ_flop and ε_flop, and treat thread placement as a choice of building block, as paper 2 does across platforms. Paper 1 notes DVFS gives "a different flavor of time-energy trade-off" that it does not model [P1 §VI].

---

## 5. Experimental results summary

*Symbols:* I = flop/byte, B_τ, B_ε, B̂_ε as above, π₀ constant power.

| Experiment | What was run | Key numbers | Takeaway | Source |
|---|---|---|---|---|
| Exp 1, turbo on (run 1) | synthetic kernel, I = 0.25–128, 8 threads, DRAM | 361.7 GFLOP/s, 40.1 GB/s; ε_flop 99.8 pJ, ε_mem 641 pJ/B, π₀ 23.2 W; B_τ 9.03 > B̂_ε 5.35; energy error 1.7% / 4.9% | Model fits; race-to-halt holds. | `turbo_on/summary.txt` |
| Exp 1, turbo on (run 2) | repeat, same day | all parameters within 3.3% of run 1 | Stable. | `repeatability/comparison.md` |
| Exp 1, turbo off | same sweep, no_turbo = 1 | 165.0 GFLOP/s, 36.4 GB/s; 34.9 pJ, 219 pJ/B, 7.89 W; B_τ 4.53 > B̂_ε 3.34 | Same verdict; every constant ~3× lower. | `turbo_off/summary.txt` |
| Exp 2, data reuse | working sets in L1, L2, L3, DRAM | turbo off 62 / 71 / 96 / 219 pJ/B | Closer data is cheaper; ordering as in paper 2. | `turbo_off/summary.txt` |
| Exp 3, threads (turbo on) | 1–12 threads at I = 0.25, 4, 64 | most efficient at 2, 4, 12 threads | Memory-bound code wants few threads. | `turbo_on/summary.txt` |
| Exp 4, real kernels | triad, naive and tiled matmul, measured Q | triad energy within 3%; matmul 1.4–2.4× above model; tiling 2.9× / 2.2× more efficient | Bound holds; cache traffic missing for matmul. | `turbo_on/summary.txt`, report §4.2–4.3 |
| Turbo on vs off | ratio of the two datasets | 2.0–2.9× more GFLOP/J; 0.44–0.91× speed | Biggest energy lever is the DVFS state. | `comparison/comparison.md` |
| DRAM sensitivity | add assumed DRAM energy to ε_mem | verdict flips at +840 pJ/B (on), +156 pJ/B (off) | Turbo-on verdict robust, turbo-off fragile. | `comparison/dram_sensitivity.md` |
| X1, π₀ sweep | lower π₀ with other constants fixed | no threshold (on); π₀* ≈ 2.2 W (off), below 2.71 W idle | Turbo off is race-to-halt only because of π₀. | `viva/viva_extras.md` |
| X2, power-cap what-if | paper 2 throttle model, Δπ/k | Δπ/8: 0.21× speed at I = 0.25; turbo off beats every capped curve on GFLOP/J | Real chips cap by DVFS, not by delay. | `viva/viva_extras.md` |
| X3, greenup and EDP | eq. 10 on tiling; EDP ratio | m up to 17.1; EDP ratio 0.39 (I ≤ 2) → 1.13 (I = 64) | Tiling is a free greenup; turbo off wins EDP up to I = 16 and loses from I = 32. | `viva/viva_extras.md` |

The papers' platforms side by side are in the "Against the papers' platforms" table at the end of §3.

---

## 6. Pros and cons

### 6.1 The papers' model: strengths
- **Very few parameters.** Five numbers (two peaks, three energies) predict energy within 2% median across a 512× range of intensity on a 2023 hybrid CPU the authors never saw [turbo_on/summary.txt].
- **Algorithm-centred.** Everything is in terms of W, Q and I, which a programmer can estimate before writing code [P1 §I].
- **Explains race-to-halt** through a measurable constant power, and predicts when it would stop working (B̂_ε > B_τ) [P1 §II-D, §V-B].
- **Extends cleanly.** The power cap and cache-level costs each add one term without changing the structure [P2 §III].
- **Supports what-if analysis.** Paper 2 uses it to reason about throttling and power bounding across building blocks [P2 §V-D]; we used it for X1–X3.
- **Validated widely.** Two platforms in paper 1, twelve in paper 2, and our laptop fits as well [P1 Fig. 4, P2 Fig. 4].

### 6.2 The papers' model: weaknesses
1. **Constant cost per operation assumes one frequency and voltage.** Turbo changes all energy constants by 3× [report §4.6]; paper 2 itself suspected non-constant costs on the Arndale GPU [P2 §V-C].
2. **Power and thermal limits.** The uncapped model over-predicts power (85 vs 67 W here; 387 vs 244 W in P1 §V-B); paper 2's cap over-predicts the slowdown on our chip [report §4.1].
3. **Best-case overlap.** Points near B_τ sit 14–19% below the roof [summary.txt files].
4. **Only DRAM traffic counts.** Matmul under-predicted 1.4–2.4× [report §4.2]; FMM_U 33% [P1 §V-C].
5. **π₀ is a catch-all and weakly identified** [README "Open points"]; four of paper 2's fits put it below idle [P2 Table I].
6. **No threads, heterogeneity or contention** [report §4.4].
7. **Reads, writes, prefetching and random access are not distinguished** [P1 §II-A, P2 §V-B]; triad's measured traffic is 0.83× the textbook count [notes.txt].
8. **The papers' own admissions:** latency suppressed, two-level hierarchy, no caps [P1 §VII]; simple model, microbenchmarks only, possible gap to real applications [P2 §I-B, §VI].

### 6.3 Our reproduction: strengths
- **Measured Q** for real kernels with memory-controller counters and a differencing method that cancels setup and background traffic [notes.txt].
- **Throttle detection** per run, with retry and row-level flags; the fit drops flagged rows [README "Throttling handling"].
- **A repeat run** (within 3.3%) and a **turbo-off dataset with zero throttling** [report §4.1].
- **A synthetic-data test** of the fitting code [report §3].
- **A DRAM sensitivity analysis** quantifying how much the missing DRAM energy could matter [report §4.7].
- **The model applied to real kernels and to a hybrid CPU** the papers never saw, with load balancing for P- and E-cores [report §3].

### 6.4 Our reproduction: limitations
- One machine.
- Package-only energy: ε_mem is a lower bound and the turbo-off verdict is sensitive to it [report §4.7].
- 1 s runs within the PL2 window, not sustained operation [report §4.1].
- Run 2 on the same day without a reboot [notes.txt].
- Δπ set by rule rather than fitted [README "Open points"].
- The model is fitted on the synthetic kernel only.
- No Exp 3 with turbo off.
- Turbo-on L2 energy unreliable (throttled) [turbo_on/summary.txt].
- No random-access or single-precision measurements.
- Paper 1's balance values are read from plot annotations, not a table [P1 Fig. 4].
- The V² explanation for the 3× drop is not backed by a voltage measurement.

---

## 7. Open-ended questions from the papers

*Symbols:* B_τ, B_ε, B̂_ε, π₀ (π₁ in paper 2), Δπ, η_flop as above.

### O1. Will a balance gap (B̂_ε > B_τ) appear in future hardware and break race-to-halt?
**What the paper says.** "If energy-balance will exceed time-balance in the future, race-to-halt will break" [P1 §I, fourth contribution]. "Today, B_τ > B_ε, due largely to constant power and other microarchitectural inefficiencies ... Will this change significantly in the future?" [P1 §VII].
**Our view.** The trend is towards a gap in B_ε, but constant power still hides it.
**Evidence.** B_ε rose from ≈ 1.2 (i7-950, 2013) to 6.43 (ours, turbo on) [report §4.1]. With turbo off B_ε (6.28) already exceeds B_τ (4.53); only π₀ keeps B̂_ε (3.34) below B_τ, and the threshold is π₀* ≈ 2.2 W [viva_extras.md X1].

### O2. How far will π₀ go towards 0, and how far will microarchitectural overheads shrink?
**What the paper says.** "An important question then is to what extent π₀ will go toward 0 and to what extent microarchitectural inefficiencies will reduce" [P1 §V-B].
**Our view.** Flop overheads have shrunk a lot; constant power has not shrunk relative to the work.
**Evidence.** ε_flop fell from 670 pJ (i7-950, double) to 99.8 pJ (ours), 6.7× [report §4.1]. π₀ is still 8× idle and 35–56% of our energy [report §4.5]. X1 shows the turbo-on verdict does not depend on π₀ at all; the turbo-off verdict does.

### O3. To what extent can π₁ be reduced, for instance by tighter integration?
**What the paper says.** "To what extent can π₁ be reduced, perhaps by more tightly integrating non-processor and non-memory components?" [P2 §VI]; π₁ > 50% of peak power on 7 of 12 [P2 §V-C].
**Our view.** A laptop SoC is already highly integrated, yet its active constant power is 8× idle, so integration alone does not remove it; voltage matters.
**Evidence.** π₀/(π₀ + Δπ) = 0.35 (turbo on), 0.43 (turbo off) at the package boundary [viva_extras.md X2]. Turbo off cut π₀ 3× (23.2 → 7.9 W) [comparison/comparison.md]. We cannot say what a system-level π₀ would be: no wall-power measurement.

### O4. Power caps as an extension
**What the paper says.** "Incorporating power caps will be an important extension for future work" [P1 §V-B]; limitation 3 [P1 §VII].
**Our view.** Paper 2 answers this, and the cap is necessary on a laptop.
**Evidence.** The capped model cuts our power error from 20.4% to 5.5% max (turbo on) and time error to 0.9% median, but over-corrects at I = 8 by 11% [turbo_on/summary.txt, report §4.1].

### O5. A capping model without constant per-operation cost
**What the paper says.** On the Arndale GPU "we would need a different model of capping, perhaps one that [does] not assume constant time and energy costs per operation" [P2 §V-C]; the authors are pursuing models "that can account for the observed errors (e.g., Arndale GPU)" [P2 §VI].
**Our view.** On a DVFS CPU the cap is met by changing the operating point, so per-operation costs fall when power is limited.
**Evidence.** Over-correction at I = 8 (1.31× predicted vs 1.18× measured roof time) [slides_outline.md Q&A]. Turbo off shows all constants moving together by 3× [comparison/comparison.md]. X2: the turbo-on cap model cannot reach the turbo-off power (π₀ alone is 23.2 W > 18.4 W) [viva_extras.md X2].

### O6. Dynamic power bounding: how to throttle with respect to intensity
**What the paper says.** The model "suggests how, with respect to intensity, operations should be throttled to meet a power cap" [P2 abstract]; power bounding as a required mechanism of future systems [P2 §V-D-j].
**Our view.** Throttling by delay (the model) is much worse than throttling by DVFS (the hardware).
**Evidence.** On our constants, Δπ/8 gives 0.07 GFLOP/J at I = 0.25 and 1.74 at I = 64; the real turbo-off setting at a lower power gives 0.56 and 11.39 [viva_extras.md X2].

### O7. Work–communication trade-offs: speedup, greenup, both or neither?
**What the paper says.** "Under what conditions on f and m should we expect a speedup, a 'greenup' ..., both, or neither?" Eq. 10 gives the greenup condition for π₀ = 0; joint conditions are left to ongoing work [P1 §VII].
**Our view.** Tiling (f = 1) is the easy case: it always gives both. The interesting case (f > 1, e.g. recomputation) has a tight budget when the baseline is fast.
**Evidence.** m = 3.4–17.1; measured greenup 1.8–2.9× (turbo on) and 1.3–2.2× (turbo off), with speedups too [viva_extras.md X3, report §4.3]. For a compute-bound baseline the extra-work budget is f < 1.71 (on) or 2.39 (off).

### O8. Per-level cache costs
**What the paper says.** "For future work, we plan to ... derive individual costs of loading data from L1, L2, texture and shared memory" [P1 §V-C].
**Our view.** Paper 2 did this; per-level costs are needed for any kernel with reuse.
**Evidence.** Ours: 62 / 71 / 96 / 219 pJ/B (turbo off) [turbo_off/summary.txt]. We did not plug them into the matmul prediction, so matmul remains under-predicted; that is a next step.

### O9. Latency and limited concurrency
**What the paper says.** "We have suppressed latency costs, under the assumption of sufficient concurrency; we have considered such costs in prior work and plan to extend it for energy" [P1 §VII].
**Our view.** Matters for thread counts and near the corner.
**Evidence.** Exp 3: bandwidth saturates at about 4 threads; 1 thread reaches about half of it [turbo_on/summary.json threads]. Points near B_τ sit 14–19% below the roof. We cannot quantify latency separately from these.

### O10. Loads vs stores
**What the paper says.** Loads and stores are not distinguished, "though one could do so in principle" [P1 §II-A]; ε_mem is an average of reads and writes [P2 §V-B].
**Our view.** It matters for write-heavy kernels.
**Evidence.** Triad's measured traffic is 0.83× the textbook count because the core avoids part of the write-allocate read [notes.txt]. We did not separate read and write energy.

### O11. Frequency scaling (DVFS) as a different kind of time–energy trade-off
**What the paper says.** DVFS research "suggests a different flavor of time-energy trade-off, which comes from the superlinear scaling of power and energy with frequency, than what we consider in this paper" [P1 §VI].
**Our view.** For a laptop CPU this is the trade-off that matters most.
**Evidence.** Turbo off: 2.0–2.9× more efficient at every intensity [report §4.6]. Extension: make τ and ε functions of frequency and voltage, and minimise over the operating point (Q62).

### O12. Which metric: energy, EDP, flop/J?
**What the paper says.** Other metrics "may be better suited" for trade-offs: EDP and generalisations, flop/s per W, the Green Index [P1 §VI "Metrics"].
**Our view.** The choice changes the turbo decision for compute-bound code.
**Evidence.** EDP ratio turbo off/on: 0.39 for I ≤ 2, 1.07–1.13 for I ≥ 32 [viva_extras.md X3].

### O13. Heterogeneous building blocks: which block for which intensity?
**What the paper says.** The model characterises "the range of algorithmic regimes where we might prefer one building block to others" and suggests "critical values of arithmetic intensity around which some systems may switch" [P2 abstract, §I-A].
**Our view.** Inside one chip, P-cores, E-cores and SMT are building blocks too; turbo on and off are two blocks that never cross in efficiency.
**Evidence.** Exp 3 qualitatively: E-cores add less per thread than P-cores, SMT adds power without speed [report §4.4]. Turbo off is slower at every I but more efficient at every I [comparison/comparison.md]. The model has one chip-wide constant set, so we cannot quantify per-core-type constants.

### O14. Aggregating low-power blocks ignores the interconnect
**What the paper says.** The Arndale array's best case "ignores the significant costs of an interconnection network" [P2 §I-A].
**Our view.** Agreed; this is a system-design question.
**Evidence.** We cannot answer from our data: one node, no network.

### O15. The gap between microbenchmarks and real applications
**What the paper says.** "There may be a considerable gap between the best-case abstract analysis of this paper and actual applications" [P2 §VI]; FMM_U needed a cache term [P1 §V-C].
**Our view.** The gap is small for DRAM-streaming code and large for cache-heavy code.
**Evidence.** Triad within 3%; matmul 1.4–2.4× off even with measured time [report §4.2].

### O16. What does constant power mean when the fit is below idle (four platforms) or far above it?
**What the paper says.** "In four cases ... our fitted constant power is less than observed idle power under no load" [P2 Table I note 1]; π₀ "accounts for much more than just idle power" [P1 §V-A].
**Our view.** π₀ is the intercept of a regression for "awake" power. Below-idle values suggest the regression shifts energy into ε terms on those platforms.
**Evidence.** Ours is 8× idle [turbo_on/summary.txt]. Note the GTX 580: paper 1 reports 39.6 W idle, paper 2 Table I lists 148 W idle beside π₁ = 122 W; the reason for the difference is unverified.

### O17. Simpler measurement via vendor counters
**What the paper says.** "In future studies, we expect to be able to use even simpler measurement methods based on vendor-provided hardware support", citing Intel's Sandy Bridge power counters and NVIDIA's NVML [P1 §VI "Tools"].
**Our view.** We did exactly this with RAPL. It is easy and fine-grained, but it moved the measurement boundary.
**Evidence.** No DRAM domain, psys unusable, package only [report §3]; the DRAM sensitivity analysis is the price [report §4.7].

### O18. Random access and irregular workloads
**What the paper says.** ε_rand ≥ 10× ε_mem; the Xeon Phi is at least 10× cheaper per random access than any other platform, "suggesting its utility on highly irregular data processing workloads" [P2 §V-B, §VI].
**Our view.** Important for sparse and graph codes.
**Evidence.** Not measured. A pointer-chasing benchmark over a DRAM-sized array, timed and measured like Exp 1, would give ε_rand for our chip.

### O19. Do CACTI, McPAT and GPUWattch agree with these measurements?
**What the paper says.** CACTI and McPAT are validated only against simulators or vendor TDP breakdowns; GPUWattch only on NVIDIA GPUs; "an interesting question may be to what extent these tools corroborate, complement, or contradict our experimental data" [P2 §II].
**Our view.** Open.
**Evidence.** We cannot answer it; the nearest thing is paper 1's comparison with Keckler et al.'s estimates (8× on ε_flop, 253–389 vs 513 pJ/B on ε_mem) [P1 §V-A].

---

## 8. Cheat sheet

**Symbols.** W flops · Q DRAM bytes · I = W/Q (flop/B) · τ_flop, τ_mem time per flop/byte (1/peak) · ε_flop, ε_mem energy per flop/byte · π₀ constant power (π₁ in paper 2) · Δπ usable power above π₀ · π_flop = ε_flop/τ_flop · π_mem = ε_mem/τ_mem.

**Formulas.**
1. T = max(W·τ_flop, Q·τ_mem) = W·τ_flop·max(1, B_τ/I)
2. E = W·ε_flop + Q·ε_mem + π₀·T
3. B_τ = τ_mem/τ_flop  B_ε = ε_mem/ε_flop  (both flop/byte)
4. ε₀ = π₀·τ_flop  ε̂_flop = ε_flop + ε₀  η_flop = ε_flop/ε̂_flop
5. E = W·ε̂_flop·(1 + B̂_ε(I)/I),  B̂_ε(I) = η·B_ε + (1 − η)·max(0, B_τ − I)
6. Half-peak point: B̂_ε = (η·B_ε + (1 − η)·B_τ)/(2 − η) if η·B_ε < B_τ, else η·B_ε
7. Race-to-halt ⟺ B̂_ε < B_τ ⟺ ε_mem < B_τ·(ε_flop + ε₀)
8. Powerline: limits π₀ + π_mem (I → 0), π₀ + π_flop (I → ∞); peak π₀ + π_flop + π_mem at B_τ
9. Capped time: T = max(W·τ_flop, Q·τ_mem, (W·ε_flop + Q·ε_mem)/Δπ); B_τ⁺ = B_τ·max(1, π_mem/(Δπ − π_flop)), B_τ⁻ = B_τ·min(1, (Δπ − π_mem)/π_flop)
10. Greenup (π₀ = 0): f < 1 + ((m − 1)/m)·B_ε/I; compute-bound baseline: f < 1 + B_ε/B_τ
11. B̂_ε < B_ε ⟺ B_τ < 2·B_ε (first case of 6)

**Our numbers.**

| | Turbo on | Turbo off |
|---|---|---|
| Peak GFLOP/s / GB/s | 361.7 / 40.1 | 165.0 / 36.4 |
| ε_flop / ε_mem / π₀ | 99.8 pJ / 641 pJ/B / 23.2 W | 34.9 pJ / 219 pJ/B / 7.89 W |
| ε₀ / η | 64.3 pJ / 0.61 | 47.8 pJ / 0.42 |
| B_τ / B_ε / B̂_ε | 9.03 / 6.43 / 5.35 | 4.53 / 6.28 / 3.34 |
| Peak GFLOP/J | 6.10 | 12.09 |
| P_max / Δπ / uncapped peak | 67.2 / 44.0 / 85.0 W | 18.4 / 10.5 / 21.6 W |
| Energy error median / max | 1.7% / 4.9% | 1.6% / 7.2% |
| Per-level pJ/B (L1/L2/L3/DRAM) | 195 / (275) / 284 / 643 | 62 / 71 / 96 / 219 |
| Idle package power | 2.86 W | 2.71 W |

**Paper 1 (Table IV, Fig. 4).** i7-950 (double): ε 670 pJ, ε_mem 795 pJ/B, π₀ 122 W, B_τ 2.1, B̂_ε 1.1, B_ε 1.2, 0.34 GFLOP/J. GTX 580 (double): 212 pJ, 513 pJ/B, 122 W, B_τ 1.0, B̂_ε 0.79, B_ε 2.4, 1.2 GFLOP/J. Power cap: 387 W predicted vs 244 W limit. FMM_U: −33% without a cache term; 187 pJ/B; 4.1% median error.

**Paper 2.** 12 platforms; 16 GFLOP/J (Titan) to 620 MFLOP/J (Nehalem); π₁ > 50% of peak power on 7 of 12; power varies 0.65–1.15× within a platform; ε_rand ≥ 10× ε_mem; Arndale vs Titan equal flop/J up to I ≈ 4; 42 (text) vs 47 (figure) Arndale GPUs.

**Five sentences if you remember nothing else.**
1. Time is a max and energy is a sum, so the time roofline has a corner at B_τ and the energy arch line is smooth with its half-peak at B̂_ε.
2. If B_τ > B̂_ε, faster code is greener code (race-to-halt); on our laptop 9.03 > 5.35 and 4.53 > 3.34.
3. Constant power is the hidden hero: it is 35–56% of our energy and is the only reason turbo off is still race-to-halt (threshold π₀* ≈ 2.2 W).
4. The model fits the synthetic kernel within 2% and bounds the real kernels, but misses cache traffic (matmul 1.4–2.4×) and power limits (85 vs 67 W).
5. Turning turbo off is 2–3× more energy-efficient at every intensity, which the model cannot predict because its constants belong to one frequency and voltage.
