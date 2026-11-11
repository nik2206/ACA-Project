# OPUS_TASK: viva preparation for the energy-roofline project

You are finishing a two-person Advanced Computer Architecture course project. The measurements, analysis, report and slides are done. Your job is to produce the material the team needs to **explain the two papers and defend the results in a viva**. The main output is one study guide, `energy-roofline/report/viva_guide.md`, plus one small analysis script and a few small additions to the report and slides.

The readers of the guide are the two team members, the night before the viva. They know the project but have not memorised the papers. Write in plain sentences, define every symbol where it first appears, and prefer a worked number over an abstract statement.

Everything in this file was checked against the repo and the two PDFs on 2026-11-11. Section 9 lists what I could not fully verify; check those items first.

---

## 0. Rules (binding)

- Work only on the `main` branch; never create branches. Commit and push only after the user approves.
- Do not modify `bench.c`, `kernels.c`, `rapl.h`, `run.sh`, `analyze.py`, `compare.py`, or anything under `data/`, and do not change the `results.csv` format.
- Anything needing sudo (turbo toggle, powercap chmod, apt): stop, print the exact command, and wait for the user.
- Before any benchmark run, tell the user how long it will take, and leave the machine alone while it runs.
- Never invent numbers. If something cannot be verified from the papers or our files, mark it "unverified" instead of guessing.

Two consequences of these rules that are easy to miss:

- The plan below needs **no benchmark run and no sudo**. Do not start one on your own initiative.
- New files go in `energy-roofline/report/` (and `report/figures/viva/`). Nothing new goes under `data/`.

---

## 1. Context summary

### 1.1 The project

"Exploring Performance–Energy Tradeoffs Using Energy Roofline Models". It reproduces the model of two papers on one laptop CPU:

- **Paper 1**: Choi, Bedard, Fowler, Vuduc, "A Roofline Model of Energy", IPDPS 2013, pp. 661–672. File: `References/A_Roofline_Model_of_Energy.pdf` (12 PDF pages; PDF page n = journal page 660 + n).
- **Paper 2**: Choi, Dukhan, Liu, Vuduc, "Algorithmic Time, Energy, and Power on Candidate HPC Compute Building Blocks", IPDPS 2014, pp. 447–457. File: `References/Algorithmic_Time_Energy_and_Power_on_Candidate_HPC_Compute_Building_Blocks.pdf` (11 PDF pages; PDF page n = journal page 446 + n).

`pdftotext` is installed and works on both. The equations and Table I of paper 2 come out garbled as text; render those pages to PNG (`pdftoppm -r 170 -f 5 -l 5 -png <pdf> <prefix>`) and read the image.

Measured machine: HP Victus 15-fa1xxx, Intel Core i5-13420H (4 P-cores with SMT + 4 E-cores, AVX2+FMA), Linux Mint 22. Energy is RAPL **package only**; there is no DRAM domain.

### 1.2 What exists (do not redo any of it)

All paths are relative to the repo root `/home/nikhil-v-atkuru/Desktop/ACA/ACA-Project/`.

| Item | Path | State |
|---|---|---|
| Original plan, formulas, deliverables | `Implementation Plan.md` (§1 formulas, §1.5 deliverables) | reference only |
| Benchmarks and runner | `energy-roofline/{bench.c,kernels.c,rapl.h,run.sh}` | frozen |
| Analysis | `energy-roofline/{analyze.py,compare.py,make_fake_data.py}`, `report/dram_sensitivity.py`, `report/build_pdf.py` | done; first three frozen |
| Raw data | `energy-roofline/data/sai-Victus-by-HP-Gaming-Laptop-15-fa1xxx/`: `results.csv` (turbo on, run 1, 171 rows), `results_run2.csv` (repeat), `results_turbo_off.csv` (117 rows, no Exp 3), matching `run_flags*.csv`, `q_measured*.csv`, `idle_power*.txt`, `notes.txt` | frozen |
| Fitted numbers | `energy-roofline/report/figures/{turbo_on,turbo_on_run2,turbo_off}/summary.txt` and `summary.json` (parameters are under the `"params"` key) | source of truth for every number |
| Comparisons | `report/figures/comparison/{comparison.md,dram_sensitivity.md,*.png}`, `report/figures/repeatability/comparison.md` | done |
| Report | `energy-roofline/report/report.md` (+ `.html`, `.pdf`) | done, 6 sections |
| Slides | `energy-roofline/report/slides/index.html` (16 slides), `report/slides_outline.md` (outline + 13 viva Q&As) | done |
| How to reproduce, open caveats | `energy-roofline/README.md` ("Analysis and report", "Open points and caveats in the analysis") | done |

### 1.3 Headline numbers (verified against `summary.txt` / `summary.json` / `notes.txt`)

| | Turbo on (run 1) | Turbo off |
|---|---|---|
| Peak GFLOP/s / GB/s | 361.7 / 40.1 | 165.0 / 36.4 |
| ε_flop (pJ/flop) | 99.8 | 34.9 |
| ε_mem (pJ/B) | 641.0 | 219.1 |
| π₀ (W); idle package power | 23.24; 2.86 | 7.89; 2.71 |
| ε₀ = π₀·τ_flop (pJ/flop) | 64.3 | 47.8 |
| η_flop | 0.608 | 0.422 |
| B_τ / B_ε / B̂_ε (flop/B) | 9.03 / 6.43 / 5.35 | 4.53 / 6.28 / 3.34 |
| Peak GFLOP/J | 6.10 | 12.09 |
| Max Exp 1 power; Δπ; uncapped model peak | 67.2 W; 44.0 W; 85.0 W | 18.4 W; 10.5 W; 21.6 W |
| Energy error median / max | 1.7% / 4.9% | 1.6% / 7.2% |
| Time error median / max | 1.3% / 15.3% | 2.3% / 18.7% |
| Throttled rows | 21 of 171 | 0 of 117 |

Race-to-halt holds in both settings (B_τ > B̂_ε). Turbo off is 2.0–2.9× more energy-efficient on the synthetic kernel and 2.1–3.0× on the real kernels. Run 2 reproduces every fitted parameter within 3.3%.

### 1.4 Which machine you are on

This checkout is on a **different laptop** from the one that produced the data: hostname `nikhil-v-atkuru-IdeaPad-Slim-5-14IAH8`, CPU i5-12450H. Here `python3` has numpy 2.5.1 and matplotlib 3.11.0 but **no scipy and no pandas** (the analysis scripts need neither), `google-chrome` is installed (used by `build_pdf.py`), and `/sys/class/powercap/intel-rapl:0/energy_uj` is **not readable without sudo**. Run `hostname` first to confirm. A benchmark run here would measure a different CPU and need a sudo `chmod`, which is one more reason the plan uses existing data only.

---

## 2. Gap analysis against the five outcomes

| # | Outcome | Status | Evidence | What is missing |
|---|---|---|---|---|
| 1 | Paper understanding from first principles | **Partial** | `report.md` §2.1–2.3 state the time and energy models, B_τ, B_ε, B̂_ε, η_flop, arch line, powerline, race-to-halt; §2.4 lists four paper-2 items in one line each. Slides 3–6 repeat this. | No derivations (how eq. 5–6 follow from eq. 3–4; why half-peak is at I = B_ε; the fixed-point form of B̂_ε appears only in §4.7). The powerline formula (paper 1 eq. 7–8) and π_flop are never written. Paper 2's capped powerline with B_τ⁺/B_τ⁻ (eq. 5–7) is absent. Paper 2's cross-platform content (Fig. 1 Titan vs Arndale, Table I, Fig. 5, the throttling scenarios of Fig. 6–7, power bounding) is one sentence. Paper 1's FMM_U refinement, Table II / Fig. 2 worked example, and the work–communication trade-off (eq. 10) are absent or one clause. Nothing says where each idea breaks down, in one place. |
| 2 | Answering evaluators' questions | **Partial** | `slides_outline.md` "Viva Q&A appendix": 13 answers, good quality, mostly method and results. | No derivation questions, almost no "what if" questions, nothing on paper 2's platforms or on power bounding, nothing on the papers' open questions. 13 is far below the ≥ 40 needed. |
| 3 | Small set of experimental results | **Covered** | `report.md` §4.1–4.7, all `summary.txt` files, `comparison.md`. | No single-page table with one takeaway per experiment. Comparison with the papers is limited to the i7-950; nothing against paper 2's Table I (for example the Ivy Bridge NUC, the closest relative of our CPU) or its "π₁ > 50% of peak power on 7 of 12" finding. |
| 4 | Pros and cons | **Mostly covered** | `report.md` §5: 5 strengths, 8 weaknesses with our evidence, a one-paragraph "Limitations of this study". | The papers' weaknesses and our reproduction's weaknesses are mixed. The **strengths of our reproduction** (measured Q, throttle detection, repeat run, synthetic-data test of the fit, DRAM sensitivity) are never listed as such. The papers' own stated limitations (paper 1 §VII, paper 2 §I-B and §VI) are not quoted. |
| 5 | Open-ended questions from the papers | **Missing** | Only `report.md` §2.3 last sentence and §4.1 "balance gap has narrowed" touch one of them. | No list of the papers' open questions, no "what the paper says / our view / our evidence" treatment. This is the largest gap. |

---

## 3. Deliverables

### 3.1 Primary: `energy-roofline/report/viva_guide.md` (new)

Target 7,000–10,000 words. Use the report's notation and Unicode style (ε_flop, B̂_ε, π₀; no LaTeX). Every claim carries a source in brackets: a paper location such as `[P1 §II-B, eq. 5]` or `[P2 Table I]`, or one of our files such as `[turbo_on/summary.txt]`, `[notes.txt]`, `[report §4.6]`. Figures are referenced by path relative to `report/`, as the report does.

Start with a short "How to use this guide" paragraph and a table of contents, then these eight sections, in this order and with these titles.

#### Section 1. Paper 1 explained

Subsections, each ending with a two-line "Where it breaks down" note:

1. **The abstract machine and the algorithm** [P1 §II, Fig. 1, Table I, p. 662]. xPU + fast memory of size Z + slow memory; W, Q, I = W/Q; Q depends on Z (matrix multiply cannot exceed I = O(√Z); summing an array is O(1)). Note the Table I unit typo for B_ε.
2. **Time model** [P1 eq. 1, 3, p. 663]. T = max(W·τ_flop, Q·τ_mem) = W·τ_flop·max(1, B_τ/I). Throughput (not latency) costs; best case; valid only with enough concurrency [P1 §II-B and footnote 2].
3. **Energy model** [P1 eq. 2, 4]. E = W·ε_flop + Q·ε_mem + π₀·T. State the two differences from time that the paper calls critical: energy cannot overlap, and constant energy is burned throughout [P1 §II-B].
4. **Derivation of ε₀, ε̂_flop, η_flop and B̂_ε(I)** [P1 eq. 5–6]. Write the steps: π₀·T = W·ε₀·max(1, B_τ/I) = W·ε₀·(1 + max(0, B_τ − I)/I); collect terms over ε̂_flop = ε_flop + ε₀; use ε_mem/ε̂_flop = η_flop·B_ε and ε₀/ε̂_flop = 1 − η_flop. Result: E = W·ε̂_flop·(1 + B̂_ε(I)/I) with B̂_ε(I) = η_flop·B_ε + (1 − η_flop)·max(0, B_τ − I).
5. **Roofline vs arch line** [P1 §II-C, Fig. 2a, p. 664]. Roofline W·τ_flop/T = min(1, I/B_τ). Arch line W·ε̂_flop/E = 1/(1 + B̂_ε(I)/I). Half of peak at I = B_ε when π₀ = 0 (footnote 3: a + b ≤ 2·max(a, b)). With π₀ > 0 the half-peak point is the fixed point I = B̂_ε(I): derive B̂_ε = (η·B_ε + (1 − η)·B_τ)/(2 − η) when that value is below B_τ, and η·B_ε otherwise. Check both of our values by hand (5.35 and 3.34). Then state exactly when B̂_ε < B_ε, from the formula and not as a slogan (see §9 item 10 of this file for the condition to verify), and give paper 1's own sentence: higher π₀ means lower η_flop, which lowers B̂_ε [P1 §II-D last paragraph].
6. **Worked example from the paper** [P1 Table II, Fig. 2]. Fermi-class GPU from Keckler et al.: τ_flop ≈ 1.9 ps (515 GFLOP/s), τ_mem ≈ 6.9 ps (144 GB/s), B_τ ≈ 3.6, ε_flop ≈ 25 pJ, ε_mem ≈ 360 pJ/B, B_ε ≈ 14.4, π₀ assumed 0. A kernel with 3.6 < I < 14.4 is compute-bound in time and memory-bound in energy.
7. **Balance gap and race-to-halt** [P1 §II-D, p. 664–665]. Both directions: B_τ < B̂_ε (energy efficiency implies time efficiency, not the converse; "energy is the nobler goal"; gap measured by B_ε/B_τ) and B_τ > B̂_ε (time efficiency implies energy efficiency; race-to-halt, footnote 4). State clearly that roofs and arches are bounds, so these are guidelines [P1 §II-D].
8. **Powerline** [P1 §III, eq. 7–8, Fig. 2b, p. 665]. π_flop = ε_flop/τ_flop; P = (π_flop/η_flop)·[min(I, B_τ)/B_τ + B̂_ε(I)/max(I, B_τ)]; with π₀ = 0: P → π_flop·B_ε/B_τ as I → 0, P → π_flop as I → ∞, maximum π_flop·(1 + B_ε/B_τ) at I = B_τ. Give the equivalent, easier form used in paper 2: limits π₀ + π_mem and π₀ + π_flop, peak π₀ + π_flop + π_mem.
9. **The experiment** [P1 §IV, Tables III–IV, Fig. 3–5, p. 665–668]. Platforms (i7-950, GTX 580), PowerMon 2 at the PSU rails plus a PCIe interposer, 100 runs, 128 Hz sampling; microbenchmarks (GPU FMA mix; CPU polynomial in assembly); achieved fractions of peak; regression eq. 9 (E/W on Q/W, T/W and the precision flag); Table IV coefficients; Fig. 4 balance values (see §8 of this file for the numbers).
10. **What the fitted constants mean** [P1 §V-A, p. 667]. ε_flop is ~8× the bare FMA energy from Keckler (≈ 187 pJ/flop of instruction and microarchitecture overhead); ε_mem vs the 253–389 pJ/B DRAM+interface estimate; π₀ = 122 W vs 39.6 W GPU idle.
11. **Power caps as the model's visible failure** [P1 §V-B, Fig. 5]. GTX 580 single precision: model asks for 387 W, card limit 244 W.
12. **FMM_U refinement** [P1 §V-C, p. 668–669]. ~390 implementations; eq. 2 with DRAM bytes only under-estimates energy by 33% on average; adding a cache-access cost of 187 pJ/B brings the median error to 4.1% on ~160 kernels.
13. **Work–communication trade-off** [P1 §VII, eq. 10, p. 670]. New algorithm (f·W, Q/m); greenup ΔE = E₁,₁/E_f,m > 1 iff f < 1 + ((m − 1)/m)·(B_ε/I); hard limit f < 1 + B_ε/I; for a baseline already compute-bound in time, f < 1 + B_ε/B_τ. Say that the printed condition is stated for π₀ = 0.
14. **The paper's own limitations** [P1 §VII "Limitations"]. Latency suppressed; two-level hierarchy only; no power caps; predictions are upper bounds on power and lower bounds on time.

#### Section 2. Paper 2 explained

1. **What is new** [P2 abstract, §I-B, p. 447–448]. Power cap, cache-level and random-access costs, twelve platforms.
2. **Notation difference**: paper 2 calls constant power **π₁**; paper 1 and our report call it π₀. Say this once, then keep π₀ and write "π₁ in paper 2" where quoting.
3. **Model with a power cap** [P2 §III, eq. 1–4, p. 449–450]. π_flop = ε_flop/τ_flop, π_mem = ε_mem/τ_mem; constant power "may include the power of other system components and peripherals"; T = max(W·τ_flop, Q·τ_mem, (W·ε_flop + Q·ε_mem)/Δπ) = W·τ_flop·max{1, B_τ/I, (π_flop/Δπ)·(1 + B_ε/I)}. Explain the third term in words: if only Δπ watts are usable, the operation energy cannot be delivered faster than Δπ.
4. **Capped powerline** [P2 eq. 5–7, p. 450]. B_τ⁺ = B_τ·max(1, π_mem/(Δπ − π_flop)), B_τ⁻ = B_τ·min(1, (Δπ − π_mem)/π_flop); three regimes (memory-bound, cap-bound, compute-bound); P̄ = π₁ + Δπ on the plateau; if Δπ ≥ π_flop + π_mem the cap never binds and the peak is π₁ + π_flop + π_mem at I = B_τ. Derive B_τ⁺ in two lines (the cap term exceeds the flop term when I < B_ε·π_flop/(Δπ − π_flop), and B_ε·π_flop = B_τ·π_mem). Then compute B_τ⁻ and B_τ⁺ for our two settings from `summary.json` (planner's hand values to check against: turbo on π_flop ≈ 36.1 W, π_mem ≈ 25.7 W, interval ≈ [4.6, 29]; turbo off π_flop ≈ 5.8 W, π_mem ≈ 8.0 W, interval ≈ [2.0, 7.6]).
5. **Experimental setup** [P2 §IV, Table I, Fig. 3, p. 450–452]. Nine systems, twelve platforms; hand-tuned microbenchmarks (intensity, random access by pointer chasing, cache); PowerMon 2 at 1024 Hz per channel; mobile boards measured at system level; discrete cards measured card-only.
6. **Fitting and accuracy** [P2 §V-A, Fig. 4, p. 452–453]. Nonlinear regression for τ, ε, π₁, Δπ; capped vs uncapped error distributions; K-S test significant on 7 of 12 platforms; bias is to over-predict.
7. **Inclusive memory-hierarchy costs** [P2 §V-B, p. 453]. ε_mem includes cells, wires, controller and the pass through the caches; ε_L1 ≤ ε_L2 on every system; ε_rand at least 10× ε_mem; reads and writes not distinguished.
8. **Cross-platform findings** [P2 §V-C, Fig. 5, Table I, p. 453–454]. Include a compact copy of Table I (platform, π₁ and idle, Δπ, ε_s, ε_d, ε_mem, ε_L1, ε_L2, ε_rand; see §8 of this file) and these findings: peak efficiency from 16 GFLOP/J (GTX Titan) down to 620 MFLOP/J (desktop Nehalem); power within a platform varies only 0.65–1.15× of π₁ + Δπ; π₁/(π₁ + Δπ) > 50% on 7 of 12, correlation ≈ −0.6 with peak efficiency; the streaming example where π₁ inverts the ranking (Xeon Phi 136 + 994 = 1,130 pJ/B; GTX Titan 267 + 515 = 782; Arndale GPU 518 + 153 = 671); the cap model's misfit on the NUC GPU (OS interference) and Arndale GPU (suggests non-constant cost per operation).
9. **The Titan vs Arndale demonstration** [P2 §I-A, Fig. 1, p. 447–448]. 5 TFLOP/s and 250 W TDP vs 72 GFLOP/s and under 10 W; equal flop/J up to about I = 4; power-matched Arndale array has under half the peak but up to 1.6× the bandwidth; ignores interconnect, so the real gain is marginal or none.
10. **Throttling scenarios and power bounding** [P2 §V-D, Fig. 6–7, p. 455–456]. Cutting Δπ by k cuts total power by less than k because π₁ stays; which platforms degrade least and why; halving a Titan node to 140 W ≈ Δπ/8 gives ≈ 0.31× performance at I = 0.25, while 23 Arndale GPUs at the same 140 W are ≈ 2.8× faster there; lower π₁ and smaller power grain degrade more gracefully.
11. **The paper's own limitations** [P2 §I-B, §VI]. Simple model, microbenchmarks only, best-case analysis.

#### Section 3. Papers' figures and claims mapped to ours

One table, one row per item, columns: paper item | what it shows | our counterpart (figure path and numbers) | agree / differ and why. Rows required:

| Paper item | Our counterpart |
|---|---|
| P1 Fig. 2a roofline vs arch line | `figures/turbo_on/fig1_roofline.png`, `fig2_archline.png` |
| P1 Fig. 2b / Fig. 5 powerline | `figures/turbo_on/fig3_powerline.png`, `figures/turbo_off/fig3_powerline.png` |
| P1 Fig. 4 measured vs model, balance markers | `figures/turbo_on/fig9_model_fit.png`; B_τ 9.03 / B̂_ε 5.35 / B_ε 6.43 |
| P1 Table IV fitted coefficients | report §4.1 table |
| P1 eq. 9 regression | `analyze.py` NNLS on E/W (report §3 "Fitting") |
| P1 §V-A π₀ ≫ idle | 23.2 W vs 2.86 W |
| P1 §V-B power cap misfit (387 W vs 244 W) | 85.0 W asked vs 67.2 W drawn; corner points 14–15% under the roof |
| P1 §V-C FMM_U needs a cache term (−33%) | matmul energy 1.4–2.4× above the model even with measured T (report §4.2) |
| P1 §VII eq. 10 greenup condition | tiling: f = 1, m from `q_measured.csv`; result from `viva_extras.py` X3 |
| P2 eq. 3 capped time, eq. 7 capped powerline | green dashed curves in fig1/fig3; errors in `summary.txt` |
| P2 Table I ε_L1 ≤ ε_L2 ≤ ε_mem | `figures/turbo_off/fig4_data_reuse.png`: 62 / 71 / 96 / 219 pJ/B |
| P2 π₁ > 50% of peak power on 7 of 12 | ours: π₀/(π₀ + Δπ) = 23.24/67.2 and 7.89/18.4 (compute them; package-only, so not directly comparable) |
| P2 power varies 0.65–1.15× within a platform | our Exp 1 power range over P_max, both settings (from X2) |
| P2 §V-C streaming example ε_mem + π₁·τ_mem | ours: ε_mem + π₀·τ_mem for both settings (compute from `summary.json`) |
| P2 Arndale GPU cap misfit | our over-correction at I = 8 (report §4.1 "Power cap") |
| P2 Fig. 6–7 throttling what-if | `figures/viva/cap_whatif.png` from X2 |
| P2 ε_rand | not measured (say so) |
| P2 Fig. 1 cross-platform | turbo on vs turbo off treated as two "building blocks" on one chip: `figures/comparison/cmp_archline.png`, `cmp_ratio.png` |

#### Section 4. Evaluator question bank

At least **48** questions in six groups, numbered Q1…Qn. Each answer is 3–8 sentences, starts with the direct answer, and cites our numbers or a figure wherever one exists. Reuse and tighten the 13 answers already in `slides_outline.md` rather than rewriting them from nothing. Required questions (add more if useful; keep all of these):

**A. Conceptual (≥ 10)**
1. What question does the energy roofline answer that the time roofline cannot?
2. What are W, Q and I, and why is I a property of the algorithm (and of Z)?
3. Why does time use max and energy use a sum?
4. Why is the arch line smooth and the roofline cornered? (Include the knee the π₀·T term adds at B_τ.)
5. What is B_τ physically? What is B_ε? Why do both have unit flop/byte?
6. What is π₀, and why is it neither idle power nor leakage alone?
7. What do ε₀ and η_flop mean? What does η_flop = 0.61 vs 0.42 tell you?
8. Why is B̂_ε a function of I, and which single number do you quote?
9. Why is B̂_ε < B_ε on our machine with turbo on? Is it always? (Use the fixed-point formula: with B_ε < B_τ the (1 − η)·B_τ term pulls up and η pulls down; give the exact condition.)
10. What does B_τ > B̂_ε mean in practice? What would B̂_ε > B_τ mean?
11. What is race-to-halt, and why does a large π₀ favour it?
12. Why does the powerline peak at B_τ?
13. "Energy is the nobler goal": what does paper 1 mean?

**B. Derivation (≥ 7)**
14. Derive E = W·ε̂_flop·(1 + B̂_ε(I)/I) from eq. 3 and eq. 4.
15. Show that efficiency is half its peak at I = B_ε when π₀ = 0.
16. Derive the closed form for the half-peak point with π₀ > 0 and check it with our numbers.
17. Derive the race-to-halt condition ε_mem < B_τ·(ε_flop + ε₀) (report §4.7).
18. Derive the powerline limits and the peak π₀ + π_flop + π_mem; check against 85.0 W and 21.6 W.
19. Derive the capped time model and B_τ⁺, B_τ⁻.
20. Derive the greenup condition f < 1 + ((m − 1)/m)·(B_ε/I).
21. Why divide the regression by W (eq. 9), and why is π₀ weakly identified?

**C. Method and measurement (≥ 10)**
22. What does RAPL package energy include and exclude? Why no DRAM energy? [report §3, §4.7]
23. How accurate is RAPL, and why ≥ 1 s runs and the median of 3?
24. How is the synthetic kernel built, and why is I = K/4 exact? [`bench.c`, README]
25. How did you measure Q for the real kernels? Why was the analytic naive-matmul Q 5× too high? [`notes.txt` "How Q was obtained", `q_measured.csv`]
26. How do you know runs were not throttled? [`rapl.h` monitor, `run_flags.csv`, README "Throttling handling"]
27. What did you do with throttled rows, and which results rest on them? [L2 turbo on; tiled b = 64, 128]
28. Why did hybrid cores need load balancing? [`notes.txt` change 1: 211 vs 254 GFLOP/s]
29. How were the peaks obtained, and how do they compare with theory (403 and 182 GFLOP/s)?
30. How were the per-level energies fitted, and why are they "inclusive upper bounds"?
31. How was Δπ chosen, and how does that differ from paper 2? [README caveats]
32. How do you know the fitting code is right? [`make_fake_data.py --check`]
33. How repeatable is it? [run 2 within 3.3%; same day, no reboot]
34. Why is psys unusable here? [`notes.txt` "RAPL domains"]

**D. Results (≥ 8)**
35. State the machine model in five numbers and the verdict.
36. How does our CPU compare with paper 1's i7-950 and with paper 2's platforms?
37. Why is our π₀ far below 122 W and far above idle?
38. Where do the real kernels sit and why is matmul's energy under-predicted?
39. What does data reuse buy (per level, and tiling)?
40. What is the energy-optimal thread count and why does it depend on I?
41. Where does the energy go (constant share 35–47% turbo on, 43–56% turbo off)?
42. What is the main finding of turbo on vs off, and why do all three constants fall ~3×?
43. Why does the capped model over-correct at I = 8 with turbo on but fit well with turbo off?
44. With turbo off, why do compute-bound runs draw less power than memory-bound ones? (π_mem > π_flop there.)

**E. "What if" (≥ 8)**
45. What if π₀ → 0? (X1: turbo on, race-to-halt still holds because B_ε < B_τ, as on paper 1's Intel platform; turbo off, it flips.)
46. What if π₀ were just the idle power?
47. What if you could measure DRAM energy? [report §4.7: 840 vs 156–238 pJ/B]
48. What if a power cap of half the current power were imposed? (X2; contrast paper 2's throttle model with what turbo-off DVFS actually achieved.)
49. What if the kernel used AVX-512, or single precision? (Qualitative: τ_flop and ε_flop change, B_τ and B_ε shift; mark any number "unverified".)
50. What if memory bandwidth doubled? What if cores doubled at fixed bandwidth?
51. What if the metric were energy-delay product instead of energy? (X3.)
52. What if the run lasted minutes rather than 1 s? (PL1 = 45 W for 56 s, thermal limits, `prelim_throttled/` evidence.)
53. What if the access pattern were random? (P2 ε_rand ≥ 10× ε_mem; not measured.)
54. What if only E-cores or only P-cores were used? (Our Exp 3 gives P-only points at 1–4 threads; no E-only data: say so.)
55. Would you ship with turbo off? (Depends on I and on whether time has value; use X3.)

**F. Critique (≥ 6)**
56. What are the model's three most serious assumptions?
57. Is "race-to-halt holds" a meaningful statement if turbo off is 2× better?
58. Is π₀ a real physical quantity or a fitting artefact?
59. Is a 1.7% median energy error impressive, given the model was fitted on the same kernel?
60. Why trust ε_mem without DRAM energy?
61. What is the weakest part of your own study, and what would you do with one more week?
62. How would you extend the model for DVFS and heterogeneous cores?

#### Section 5. Experimental results summary

One table with a row per experiment: Exp 1 intensity (turbo on, run 2, turbo off), Exp 2 data reuse, Exp 3 threads, Exp 4 real kernels, turbo on vs off, DRAM sensitivity, repeatability, and the three analyses X1–X3. Columns: what was run | key numbers | one- or two-line takeaway | source file. Then a short "against the papers" table: our turbo-on and turbo-off rows beside the i7-950 (paper 1 Table IV, paper 2 Table I) and the Ivy Bridge NUC CPU (paper 2 Table I), with the measurement boundary stated for each (package-only vs wall/PSU).

#### Section 6. Pros and cons

Four separate lists, each item one or two sentences with evidence:
- **The papers' model: strengths** (from report §5 "Strengths", plus the what-if capability of P2 §V-D).
- **The papers' model: weaknesses** (report §5 items 1–8, plus the papers' own admissions: P1 §VII Limitations; P2 §I-B, §V-C Arndale, §VI).
- **Our reproduction: strengths.** Measured Q with IMC counters and a differencing method; throttle detection with retry and row-level flags; a repeat run; a turbo-off dataset with zero throttling; synthetic-data test of the fit; DRAM sensitivity analysis; the model applied to real kernels and to a hybrid CPU the papers never saw.
- **Our reproduction: limitations.** One machine; package-only energy (ε_mem a lower bound); 1 s runs under PL2, not sustained; same-day repeat; Δπ set by rule; fit on the synthetic kernel only; no Exp 3 with turbo off; turbo-on L2 unreliable; no random-access or single-precision measurement; Table/figure values of paper 1 read off plots; the V² explanation is not backed by a voltage measurement.

#### Section 7. Open-ended questions from the papers

One subsection per question, each with exactly three labelled parts: **What the paper says** (with location) · **Our view** · **Evidence from our data, or why our data cannot answer**. Cover all of these:

| # | Open question | Paper location | Our evidence to use |
|---|---|---|---|
| O1 | Will a balance gap (B̂_ε > B_τ) appear in future hardware, breaking race-to-halt? | P1 §I (fourth contribution), §VII first paragraph | B_ε rose from ≈ 1.2 (2013) to 6.4; turbo off B_ε 6.28 > B_τ 4.53; held only by π₀; X1 threshold |
| O2 | How far will π₀ go toward 0, and how far will microarchitectural overheads shrink? | P1 §V-B | ε_flop 670 → 100 pJ; π₀ 23 W vs 2.9 W idle; X1 |
| O3 | To what extent can π₁ be reduced, for instance by tighter integration? | P2 §VI, §V-C | constant share 35–56% of energy; π₀/(π₀ + Δπ) for our two settings; a laptop SoC is already highly integrated yet π₀ is 8× idle |
| O4 | Power caps as an extension | P1 §V-B, §VII | answered by P2; our capped fit and its over-correction |
| O5 | A capping model without constant per-operation cost | P2 §V-C (Arndale GPU), §VI | our I = 8 over-correction; turbo off shows all constants move with the operating point; X2 |
| O6 | Dynamic power bounding; how to throttle with respect to intensity | P2 §V-D, abstract | X2: paper-2 throttling vs measured turbo off |
| O7 | Work–communication trade-offs: when is there a speedup, a greenup, both, neither? | P1 §VII, eq. 10 | tiling as the f = 1, m ≫ 1 case; X3 |
| O8 | Per-level cache costs | P1 §V-C last sentence | answered in P2 §V-B; our 62 / 71 / 96 / 219 pJ/B; matmul still under-predicted |
| O9 | Latency and limited concurrency | P1 §VII Limitations, §II-B | Exp 3: bandwidth saturates at ≈ 4 threads; model has no thread term; cannot quantify latency |
| O10 | Loads vs stores | P1 §II-A; P2 §V-B | triad measured Q is 0.83× the textbook count (write-allocate partly avoided); we did not separate read and write energy |
| O11 | Frequency scaling (DVFS) as a different kind of time–energy trade-off | P1 §VI "Systems-focused frequency scaling" | our main finding (report §4.6); how to extend: constants as functions of the operating point |
| O12 | Which metric: energy, EDP, flop/J | P1 §VI "Metrics" | X3 EDP table |
| O13 | Heterogeneous building blocks; which block for which intensity | P2 §I-A, §V-C | P-cores vs E-cores vs SMT in Exp 3 (qualitative only); turbo on vs off as two blocks crossing in speed but not in efficiency |
| O14 | Aggregating low-power blocks ignores the interconnect | P2 §I-A | cannot answer from our data; explain why |
| O15 | Gap between microbenchmarks and real applications | P2 §VI; P1 §V-C | triad within 3%, matmul 1.4–2.4× off |
| O16 | What does constant power mean when the fit is below idle (4 platforms) or far above it? | P2 Table I note 1; P1 §V-A | ours is 8× idle; π₀ is a regression intercept for "awake" power |
| O17 | Simpler measurement via vendor counters | P1 §VI "Tools" (cites the Sandy Bridge RAPL paper) | we did exactly this; what RAPL cost us (no DRAM, package boundary) |
| O18 | Random access and irregular workloads | P2 §V-B, §VI | not measured; say what experiment would be needed |
| O19 | Do CACTI / McPAT / GPUWattch agree with these measurements? | P2 §II | cannot answer; note P1 §V-A's Keckler comparison as the nearest thing |

#### Section 8. Cheat sheet

At most about 60 lines, meant to be printed on one page: the symbol list; the ten formulas (T, E, B_τ, B_ε, ε₀, η_flop, B̂_ε(I), half-peak closed form, powerline peak and limits, capped T, race-to-halt condition, greenup condition); our key numbers for both settings; paper 1's i7-950 and GTX 580 numbers; five sentences to say if you remember nothing else.

### 3.2 New script: `energy-roofline/report/viva_extras.py`

Specified in §4. Outputs go to `energy-roofline/report/figures/viva/`.

### 3.3 Small additions to existing documents

Make exactly these; nothing else in these files changes.

1. `energy-roofline/report/report.md`
   - §2.4, first sentence: append "Paper 2 writes the constant power as π₁; we keep π₀ throughout."
   - §5, after the "Limitations of this study" paragraph: add a paragraph headed **Open questions.** of at most 6 sentences naming O1, O3, O5, O11 with the X1 and X2 numbers, ending "The full list is in `viva_guide.md`, section 7."
   - Do **not** change the byline "Person A / Person B" unless the user gives you the names; ask for them in your final message.
   - Then rebuild: `cd energy-roofline && python3 report/build_pdf.py`. If it fails, report the error and leave `report.pdf` as it was.
2. `energy-roofline/report/slides_outline.md`
   - After slide 6, add "### 6b. Paper 2 across twelve platforms" (4 bullets: Titan vs Arndale; π₁ > 50% on 7 of 12; power varies < 2× within a platform; throttling and power bounding).
   - Before slide 14, add "### 13b. Open questions" (4 bullets: O1/O2 with the X1 threshold, O5/O6 with the X2 result, O7 with the X3 result, O11).
   - At the top of the Q&A appendix add one line: "The full question bank (≥ 48 answers) is in `viva_guide.md`, section 4."
   - Update the slide count in the first paragraph.
3. `energy-roofline/report/slides/index.html`
   - Add the same two slides by copying the markup of an existing text slide (slide 6, `data-title="Paper 2"`, is the closest pattern) and placing them after slide 6 and before the conclusion slide. Keep the deck's classes and numbering scheme; if slides carry visible numbers or a total, update them. Open the file in headless Chrome or inspect the DOM to confirm there are 18 `<section class="slide…">` elements and no broken layout. If the deck's structure makes this risky, stop and report rather than restyle it.
4. `energy-roofline/README.md`
   - In "Analysis and report", add one command line for `python3 report/viva_extras.py` and one sentence pointing to `report/viva_guide.md`.

---

## 4. Small experiments

**No new benchmark run is needed.** The three additions below are analyses of files already in the repo. They live in one script, need only numpy and matplotlib, and run in seconds.

Script: `energy-roofline/report/viva_extras.py`. Model it on `report/dram_sensitivity.py` (same imports from `analyze.py` for colours; read `summary.json["params"]`; write a PNG and a markdown table). Inputs: `report/figures/{turbo_on,turbo_off}/summary.json`, and read-only `data/sai-Victus-by-HP-Gaming-Laptop-15-fa1xxx/{results.csv,results_turbo_off.csv,run_flags.csv,run_flags_turbo_off.csv,q_measured.csv,q_measured_turbo_off.csv}`. Outputs: `report/figures/viva/viva_extras.md` plus the PNGs named below. Follow the figure rules in `Implementation Plan.md` §7 B2 (palette, one y-axis per chart, legend when ≥ 2 series).

Command: `cd energy-roofline && python3 report/viva_extras.py`

### X1. Constant-power sweep: does race-to-halt survive as π₀ → 0?

- **Purpose.** Answers O1, O2, O3 and Q45–Q46 with a number instead of a guess.
- **Method.** For each setting, hold ε_flop, ε_mem and the peaks fixed, sweep π₀ from the fitted value to 0, recompute η_flop and the half-peak B̂_ε, and find the π₀ at which B̂_ε = B_τ (closed form: π₀* = (ε_mem/B_τ − ε_flop)/τ_flop). Mark the fitted π₀ and the idle power on the x-axis.
- **Output.** `figures/viva/pi0_sweep.png`; table rows: fitted π₀, idle power, π₀*, B̂_ε at π₀ = idle and at π₀ = 0.
- **Expected (planner's hand calculation; your script must reproduce it or you must find out why not).** Turbo on: no positive threshold (B_ε 6.43 < B_τ 9.03, so the verdict holds even at π₀ = 0, the situation paper 1 describes for its Intel platform in §V-B). Turbo off: π₀* ≈ 2.2 W, against a fitted 7.89 W and an idle power of 2.71 W.
- **Feeds.** Guide §4 Q45–Q46, §7 O1–O3, cheat sheet; report "Open questions" paragraph.

### X2. Power-bound what-if, and a test of paper 2's throttle model against turbo off

- **Purpose.** Answers O5, O6 and Q48; reproduces the idea of paper 2 Fig. 6–7 on our chip.
- **Method (a).** With the turbo-on constants, plot the capped model's GFLOP/s, GFLOP/J and power against I for Δπ, Δπ/2, Δπ/4, Δπ/8 (use `analyze.py`'s model class if importing it has no side effects; otherwise re-implement the three formulas). Also print B_τ⁻ and B_τ⁺ for the fitted Δπ in both settings, and the Exp 1 power range divided by P_max.
- **Method (b).** Treat turbo off as a real power bound: its measured maximum power is 18.4 W. Ask the turbo-on capped model for the same bound. Since the turbo-on π₀ (23.24 W) is already above 18.4 W, the model has **no** feasible Δπ: report exactly that, then show the nearest feasible comparison (for example Δπ/8) beside the measured turbo-off GFLOP/s and GFLOP/J at I = 0.25, 4 and 64.
- **Output.** `figures/viva/cap_whatif.png` (three panels in a row) and a table.
- **What it shows.** Paper 2's cap delays operations at a fixed energy cost and keeps π₁ fixed; a real CPU meets a bound by changing its operating point, which lowers ε_flop, ε_mem and π₀ together. The paper suspected this on the Arndale GPU [P2 §V-C].
- **Feeds.** Guide §2.4, §3, §4 Q43 and Q48, §7 O5–O6.

### X3. Greenup condition on tiling, and the turbo decision under EDP

- **Purpose.** Answers O7, O12 and Q51, Q55.
- **Method (a).** Tiling is a work–communication trade-off with f = 1 and m = Q_naive/Q_tiled from `q_measured*.csv` (turbo on, b = 128: 1.343761e10 / 9.052994e8 ≈ 14.8). Report m per tile size, the paper's π₀ = 0 bound on extra work f < 1 + ((m − 1)/m)·B_ε/I at the naive kernel's intensity, the model-predicted greenup (use the `"real"` entries of `summary.json`; state whether you used roofline time or measured time), and the measured greenup (2.90× turbo on, 2.17× turbo off). Also print 1 + B_ε/B_τ for both settings (hand values 1.71 and 2.39).
- **Method (b).** From the unthrottled Exp 1 medians, compute turbo-off / turbo-on ratios of time, energy and energy × time per flop at each I. Hand values to check against: EDP ratio ≈ 0.38–0.40 for I ≤ 2, 0.51 at I = 4, 0.84 at I = 8, 0.93 at I = 16, and 1.07–1.13 for I ≥ 32. So under EDP turbo off still wins for memory-bound and balanced code and loses slightly for compute-bound code.
- **Output.** `figures/viva/edp_ratio.png` and two tables.
- **Feeds.** Guide §3, §4 Q51 and Q55, §7 O7 and O12.

### Not planned: a second-CPU run

A sweep on the IdeaPad (`ONLY=intensity OUTDIR=<new folder outside data/> ./run.sh`) would give a second "building block" in the spirit of paper 2. It is **not** part of this task: it needs `sudo chmod -R a+r /sys/class/powercap/intel-rapl*`, its duration here is unverified (the turbo-off Exp 1 took about 4 minutes on the Victus; turbo on with cool-downs and retries is longer), and it does not strengthen any specific answer more than X1–X3 do. Mention it to the user as an option in your final message; run it only if they ask.

---

## 5. Execution order and acceptance checks

| Step | Do | Acceptance check |
|---|---|---|
| 1 | `git status`, `git branch --show-current`, `hostname`. Read this file, then the items in §9. | On `main`, clean tree apart from `OPUS_TASK.md`. Each §9 item resolved or carried into the guide as "unverified". |
| 2 | Read both PDFs in full (text, plus page images for P1 p. 663–668 and P2 p. 449–456). Read `report.md`, `slides_outline.md`, `notes.txt`, README caveats, the three `summary.txt` files, `comparison.md`, `dram_sensitivity.md`. | You can state, without looking, P1 eq. 3–8 and 10 and P2 eq. 1–7, and they match §3.1 above. Where they do not, the paper wins; note the correction in your final message. |
| 3 | Write `report/viva_extras.py`; run it. | Exits 0; writes `figures/viva/viva_extras.md` and three PNGs; reproduces the hand values in §4 within rounding (or the difference is explained); B̂_ε recomputed from `summary.json` equals 5.35 and 3.34. `git status` shows no change under `data/` and no change to the frozen files. Look at each PNG: readable labels, legend, one y-axis. |
| 4 | Write guide §1–§3. | Every formula matches the papers' notation and equation numbers. Every paper claim has a section, equation, figure or table reference. Both B̂_ε values are checked by hand in the text. The Table I copy matches the PDF image cell by cell. |
| 5 | Write guide §5–§6. | Every number matches `summary.txt`, `summary.json`, `comparison.md`, `dram_sensitivity.md`, `notes.txt` or `viva_extras.md`. Where `notes.txt` and `summary.txt` differ (see README "Differences from notes.txt"), `summary.txt` is used. |
| 6 | Write guide §7. | All of O1–O19 present, each with the three labelled parts and a paper location. Each "evidence" part either cites a file or says plainly why our data cannot answer. No open question is "answered" by speculation presented as a result. |
| 7 | Write guide §4, then §8. | ≥ 48 Q&As; group minimums in §3.1 met; every required question present; each answer 3–8 sentences and consistent with §1–§7 of the guide. The cheat sheet fits about one printed page. |
| 8 | Make the additions in §3.3. Rebuild the PDF. | `git diff --stat` touches only `report.md`, `report.html`/`report.pdf` (from the rebuild), `slides_outline.md`, `slides/index.html`, `README.md`. The deck has 18 slides and navigates end to end. |
| 9 | Self-review pass over the whole guide. | (a) Grep every number with a unit in the guide and trace it to a source; fix or mark "unverified". (b) No claim without a bracketed source. (c) Paper 2's constant power is called π₁ only in quotations. (d) The words "V²" and "voltage" always appear as an explanation, never as a measurement. (e) No figure path points to a missing file. |
| 10 | Final message to the user. Do not commit. | Lists the files created and changed, the X1–X3 results in three lines, every item marked "unverified", any correction to this plan, the two requests (author names for the byline; whether to commit), and the optional second-CPU run. |

---

## 6. Facts already extracted (to save you time; re-check anything you quote)

**Paper 1.**
- Table IV [p. 666]: GTX 580: ε_s 99.7 pJ/flop, ε_d 212 pJ/flop, ε_mem 513 pJ/B, π₀ 122 W. i7-950: ε_s 371, ε_d 670, ε_mem 795 pJ/B, π₀ 122 W (identical π₀ to three digits is a coincidence the paper remarks on).
- Table III [p. 665]: i7-950 peak 106.56 (single) / 53.28 (double) GFLOP/s, 25.6 GB/s, TDP 130 W. GTX 580: 1581.06 / 197.63 GFLOP/s, 192.4 GB/s.
- Achieved [p. 666]: CPU double 18.9 GB/s (73.8%) and 49.7 GFLOP/s (93.3%); GPU double 170 GB/s (88.3%) and 196 GFLOP/s (99.3%).
- Fig. 4 markers [p. 667], read from the plot: double precision, GPU B_τ 1.0, B̂_ε 0.79, B_ε(π₀ = 0) 2.4; CPU B_τ 2.1, B̂_ε 1.1, B_ε(π₀ = 0) 1.2. Single precision, GPU 8.2 / 4.5 / 5.1; CPU 4.2 / 2.1 / 2.1. Peak efficiencies: GPU 1.2 (double), 5.7 (single) GFLOP/J; CPU 0.34 (double), 0.66 (single) GFLOP/J.
- §V-A [p. 667]: Keckler FMA 50 pJ (25 pJ/flop); overhead ≈ 187 pJ/flop; DRAM + interface + wire 253–389 pJ/B; with instruction and cache overheads 307–443 pJ/B; GPU idle 39.6 W.
- §V-B [p. 668]: GPU single precision needs 387 W in the model; card limit 244 W. "If architects could drive π₀ → 0, then the situation could reverse" (GPU double); "for the Intel platform, even having π₀ = 0 does not invert the balance gap."
- §V-C [p. 668–669]: 33% average under-estimate; 187 pJ/B cache cost; median error 4.1% on about 160 kernels.

**Paper 2.**
- Table I [p. 451], transcribed from a rotated page image; **verify before use**. Format: π₁ (idle) W; Δπ W; ε_s pJ/flop (GFLOP/s); ε_d (GFLOP/s); ε_mem pJ/B (GB/s); ε_L1 (GB/s); ε_L2 (GB/s); ε_rand nJ/access (Macc/s). `*` = fitted π₁ below idle.
  - Desktop CPU i7-950 (45 nm): 122 (79.9); 44.2; 371 (99.4); 670 (49.7); 795 (19.1); 135 (201); 168 (120); 108 (149)
  - NUC CPU i3-3217U (22 nm): 16.5 (13.2); 7.37; 14.7 (55.6); 24.3 (27.9); 418 (17.9); 8.75 (201); 14.3 (103); 54.6 (55.3)
  - NUC GPU HD 4000: 10.1 (13.2)*; 17.7; 76.1 (268); –; 837 (15.4); –; –; –
  - APU CPU E2-1800 (40 nm): 20.1 (11.8); 1.39; 33.5 (13.4); 119 (5.05); 435 (3.32); 84.0 (25.8); 138 (11.6); 75.6 (8.03)
  - APU GPU HD 7340: 15.6 (11.8); 3.23; 5.82 (104); –; 333 (8.70); 6.47 (46.0); –; 45.8 (115)
  - GTX 580 (40 nm): 122 (148)*; 146; 99.7 (1400); 213 (196); 513 (171); 149 (761); 257 (284); 112 (977)
  - GTX 680 (28 nm): 66.4 (100)*; 145; 43.2 (3030); 263 (147); 437 (158); 51 (1150); 195 (297); 184 (1420)
  - GTX Titan (28 nm): 123 (72.9); 164; 30.4 (4020); 93.9 (1600); 267 (239); 24.4 (1610); 195 (297); 48.0 (968)
  - Xeon Phi 5110P (22 nm): 180 (90); 36.1; 6.05 (2020); 12.4 (1010); 136 (181); 2.19 (2890); 8.65 (591); 5.11 (706)
  - PandaBoard ES, OMAP 4460 (45 nm): 3.48 (2.74); 1.19; 37.2 (9.47); 302 (3.02); 810 (1.28); 79.5 (18.4); 134 (4.12); 60.9 (12.1)
  - Arndale CPU, Exynos 5 (32 nm): 5.50 (1.72); 2.01; 107 (15.8); 275 (3.97); 386 (3.94); 76.3 (50.8); 248 (15.2); 138 (14.8)
  - Arndale GPU, Mali T-604: 1.28 (1.72)*; 4.83; 84.2 (33.0); –; 518 (8.39); 71.4 (33.4); –; 125 (33.6)
- With these values π₁/(π₁ + Δπ) exceeds 50% on exactly seven platforms (i7-950, NUC CPU, APU CPU, APU GPU, Xeon Phi, PandaBoard, Arndale CPU), which matches the paper's count.
- The i7-950's Δπ (44.2 W) is almost the same as our turbo-on Δπ (44.0 W). Worth one sentence; it is a coincidence of two different measurement boundaries.

**Our data, hand-computed by the planner from `summary.json` (recompute in X2):** turbo on π_flop ≈ 36.1 W, π_mem ≈ 25.7 W, π₀ + π_mem ≈ 48.9 W (measured 49.8 W at I = 0.25), π₀ + π_flop ≈ 59.3 W (measured 61.6–63.7 W at high I). Turbo off π_flop ≈ 5.8 W, π_mem ≈ 8.0 W, limits ≈ 15.9 W and 13.7 W (measured 16.2 W and 13.6 W). Streaming cost per byte ε_mem + π₀·τ_mem ≈ 641 + 580 pJ/B turbo on and ≈ 219 + 217 pJ/B turbo off.

---

## 7. Style requirements for the guide

- Answer first, reasoning second. No preamble such as "Great question".
- Define a symbol at first use in each of the eight sections; a reader may open the guide at any section.
- Use the same rounding as the report (99.8 pJ, 641 pJ/B, 23.2 W, 9.03, 5.35, …).
- Distinguish three kinds of statement and never blur them: what a paper says, what we measured, and what we infer. Inference is introduced with "we think" or "this suggests".
- Tables for comparisons and lists of numbers; prose for explanations and derivations.

---

## 8. What not to do

- Do not rewrite or restructure `report.md` or the slide deck beyond §3.3.
- Do not re-run `analyze.py`, `compare.py` or `dram_sensitivity.py` to "refresh" outputs; their outputs are already committed and are the source of truth.
- Do not add scipy or pandas as a dependency.
- Do not present X1–X3 as measurements. They are model what-ifs on fitted constants (X1, X2a), or re-arrangements of measured data (X2b, X3b).

---

## 9. Things the planner was unsure about (check these first)

1. **Host mismatch.** The task brief speaks of "this laptop" as the measured Victus, but the checkout is on an IdeaPad (i5-12450H). Confirm with `hostname`. This is why §4 plans no run.
2. **π₁ vs π₀.** Paper 2 consistently writes π₁; our plan, report and slides write π₀ for both papers. Confirm on P2 p. 449–450 and apply §3.3 item 1.
3. **42 vs 47 Arndale GPUs.** P2 §I-A text says matching the Titan on power "may require up to 42 Arndale GPUs"; the Fig. 1 caption says 47. Quote both and say the paper is inconsistent; do not pick one.
4. **GTX 580 idle power.** P1 §V-A gives 39.6 W GPU idle; P2 Table I lists 148 W as the idle value beside π₁ = 122 W (with the asterisk). The two papers disagree or measure different things. The report's phrase "122 W fitted vs ≈ 40 W idle on its GPU" is correct for paper 1; when discussing O16, mention the paper-2 value and mark the reason for the difference "unverified".
5. **Paper 2 Table I transcription** (§6): read from a rotated scan at 170 dpi. Re-read every cell you use.
6. **Paper 1 Fig. 4 values** are read from plot annotations, not a table (the README already flags 0.34 GFLOP/J and B̂_ε ≈ 1.1).
7. **Paper 1 is the abridged version.** The derivation of eq. 10 and "some additional analysis" are in tech report GT-CSE-12-01, which is not in the repo. Derive eq. 10 yourself for π₀ = 0; mark anything about the π₀ > 0 case or about speedup-with-greenup conditions as our own derivation, not the paper's.
8. **"Constants fall ~3×, roughly V²."** The report and notes offer this as an explanation; no voltage was measured. Keep it as a hypothesis in the guide.
9. **Maximum Exp 1 power.** `summary.txt` says 67.2 W; `notes.txt` says about 69 W; the median of per-repeat powers gives 68.6 W at one K. Use 67.2 W (the value Δπ is built from) and do not mix definitions.
10. **Q7/Q9 wording on B̂_ε < B_ε.** The task brief asks "why is B̂_ε < B_ε?". That is true for our fitted values in both settings, but it is not a theorem: from B̂_ε = (η·B_ε + (1 − η)·B_τ)/(2 − η) (when below B_τ), B̂_ε < B_ε exactly when B_τ < 2·B_ε. Verify this algebra and state the condition; an evaluator may probe it.
11. **Slide deck edits.** I inspected only the text of `slides/index.html`, not its CSS/JS. If slide numbering is generated by script, adding sections may be enough; if it is hard-coded, update it. Stop if unsure.
12. **`analyze.py` import side effects.** `dram_sensitivity.py` imports colours from it without trouble; importing the model class should also be safe, but check that nothing runs at import time before relying on it.
13. **Duration of an optional second-CPU run** is unverified (see §4, last subsection).
