#!/usr/bin/env python3
"""make_fake_data.py - regression test for analyze.py's fitting code.

Writes a results.csv (plan Section 5 format, all four exp values) and a matching
run_flags.csv from PLANTED parameters, then (with --check) runs analyze.py on it and
verifies that the fitted values are within 5% of the planted ones.

  python3 make_fake_data.py --out /tmp/fake            # just write the files
  python3 make_fake_data.py --out /tmp/fake --check    # regression test (exit 1 on failure):
      noise-free data must be recovered exactly; with 2% noise the median over 9 seeds
      must be within 5% of the planted values

Times come from the roofline, energies from E = W*eps_flop + Q*eps_lvl + pi0*T, with 2%
multiplicative noise. A few rows are deliberately CORRUPTED (slow, low power, as a
thermally throttled run would be) and flagged throttled=1, so the test also checks that
analyze.py drops flagged rows before fitting.
"""
import argparse, csv, json, os, subprocess, sys
import numpy as np

PLANT = dict(eps_flop_pJ=300.0, eps_mem_pJ_per_B=600.0, pi0_W=8.0, peak_GFLOPs=100.0, peak_GBs=30.0,
             L1=20.0, L2=60.0, L3=150.0)
LEVEL_BW = dict(L1=400.0, L2=200.0, L3=100.0, DRAM=30.0)        # GB/s, all cores
SIZE = dict(L1=160 << 10, L2=3584 << 10, L3=9318 << 10, DRAM=512 << 20)
CORES = 8
HEADER = "exp,level,n,bytes,K,threads,reps,W,Q,time_s,E_pkg_J,E_dram_J,checksum".split(",")
FLAGS = "row,exp,level,K,threads,attempt,throttled,throttle_frac,pl1_min_W,temp_max_C,throttle_events,imbalance".split(",")


def run(rng, noise, exp, level, n, nbytes, K, thr, W, Q, eps_q, peak_f, peak_b, corrupt=False):
    T = max(W / peak_f, Q / peak_b)
    E = W * PLANT["eps_flop_pJ"] * 1e-12 + Q * eps_q * 1e-12 + PLANT["pi0_W"] * T
    T *= rng.normal(1, noise); E *= rng.normal(1, noise)
    if corrupt:                       # throttled: 40% slower, energy 35% lower
        T *= 1.4; E *= 0.65
    reps = max(1, int(round(W / max(n, 1))))
    return dict(exp=exp, level=level, n=n, bytes=nbytes, K=K, threads=thr, reps=reps, W=f"{W:.6e}",
                Q=f"{Q:.6e}", time_s=f"{T:.6f}", E_pkg_J=f"{E:.6f}", E_dram_J="-1.000000",
                checksum="0"), int(corrupt)


def generate(out, seed=1, noise=0.02, quiet=False):
    rng = np.random.default_rng(seed)
    pf, pb = PLANT["peak_GFLOPs"] * 1e9, PLANT["peak_GBs"] * 1e9
    rows = []
    n = SIZE["DRAM"] // 8
    for K in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]:                      # Exp 1
        for r in range(3):
            # one corrupted repeat at K=8 and K=64: the median would survive, so also
            # corrupt all three repeats at K=32 (only the flags can save the fit there)
            bad = (K in (8, 64) and r == 0) or K == 32
            Q = 8.0 * n * 10; W = 2.0 * K * n * 10
            rows.append(run(rng, noise, "intensity", "DRAM", n, SIZE["DRAM"], K, CORES, W, Q,
                            PLANT["eps_mem_pJ_per_B"], pf, pb, bad))
    for L in ["L1", "L2", "L3", "DRAM"]:                                    # Exp 2
        eps_q = PLANT[L] if L != "DRAM" else PLANT["eps_mem_pJ_per_B"]
        nn = SIZE[L] // 8
        for K in [1, 2, 4, 8, 16, 64]:
            for r in range(3):
                reps = int(4e10 / (8 * nn)) or 1
                Q = 8.0 * nn * reps; W = 2.0 * K * nn * reps
                rows.append(run(rng, noise, "reuse", L, nn, SIZE[L], K, CORES, W, Q, eps_q, pf,
                                LEVEL_BW[L] * 1e9, L == "L2" and K == 1))
    for t in [1, 2, 4, 6, 8, 12]:                                            # Exp 3
        f = pf * min(t, CORES) / CORES
        b = pb * min(t, 3) / 3                     # bandwidth saturates at 3 threads
        for K in [1, 16, 256]:
            for r in range(3):
                Q = 8.0 * n * 10; W = 2.0 * K * n * 10
                rows.append(run(rng, noise, "threads", "DRAM", n, SIZE["DRAM"], K, t, W, Q,
                                PLANT["eps_mem_pJ_per_B"], f, b))
    for name, tile, I in [("triad", 0, 0.08), ("matmul_naive", 0, 1.3), ("matmul_tiled", 32, 4.3),
                          ("matmul_tiled", 64, 9.3), ("matmul_tiled", 128, 19.0)]:   # Exp 4
        for r in range(3):
            W = 5e10; Q = W / I
            rows.append(run(rng, noise, "real", name, 2048, 100663296, tile, CORES, W, Q,
                            PLANT["eps_mem_pJ_per_B"], pf, pb))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, HEADER); w.writeheader(); w.writerows(r for r, _ in rows)
    with open(os.path.join(out, "run_flags.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(FLAGS)
        for i, (r, bad) in enumerate(rows, 1):
            w.writerow([i, r["exp"], r["level"], r["K"], r["threads"], 1, bad, 0.4 if bad else 0.0,
                        45.0, 97 if bad else 70, 3 if bad else 0, 1.05])
    json.dump(PLANT, open(os.path.join(out, "planted.json"), "w"), indent=1)
    if not quiet:
        print(f"wrote {len(rows)} rows ({sum(b for _, b in rows)} flagged throttled) to {out}")


def fitted(out):
    here = os.path.dirname(os.path.abspath(__file__))
    subprocess.run([sys.executable, os.path.join(here, "analyze.py"), os.path.join(out, "results.csv"),
                    "--flags", os.path.join(out, "run_flags.csv"), "--out", out, "--tag", "fake"],
                   check=True, stdout=subprocess.DEVNULL)
    S = json.load(open(os.path.join(out, "summary.json")))
    p = S["params"]; lv = {x["level"]: x["pJ_per_B"] for x in S["levels"]}
    return {"eps_flop_pJ": p["eps_flop_pJ"], "eps_mem_pJ_per_B": p["eps_mem_pJ_per_B"], "pi0_W": p["pi0_W"],
            "peak_GFLOPs": p["peak_GFLOPs"], "peak_GBs": p["peak_GBs"], "L1": lv["L1"], "L2": lv["L2"], "L3": lv["L3"]}


def check(out, seeds):
    """1) noise-free data must be recovered exactly (< 0.5%): tests the fitting code itself.
    2) with 2% noise, the MEDIAN over several seeds must be within 5% (no bias); the
       per-seed spread is printed - it shows how well-conditioned each parameter is."""
    ok = True
    exact = fitted((generate(out + "/noise0", 1, 0.0, True), out + "/noise0")[1])
    runs = [fitted((generate(out + f"/seed{sd}", sd, 0.02, True), out + f"/seed{sd}")[1]) for sd in seeds]
    print(f"{'parameter':<17}{'planted':>9}{'no noise':>10}{'2% noise: median':>18}{'min..max (per seed)':>24}")
    for k, want in PLANT.items():
        e0 = 100 * (exact[k] - want) / want
        es = np.array([100 * (r[k] - want) / want for r in runs])
        med = float(np.median(es))
        good = abs(e0) < 0.5 and abs(med) <= 5
        ok &= good
        print(f"{k:<17}{want:9.1f}{e0:9.2f}%{med:17.1f}%{es.min():13.1f}% .. {es.max():5.1f}%"
              + ("" if good else "   FAIL"))
    print(f"{'PASS' if ok else 'FAIL'}: exact without noise; median over {len(seeds)} noisy seeds within 5%")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="fake_data")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--noise", type=float, default=0.02)
    ap.add_argument("--check", action="store_true", help="run analyze.py and compare with the planted values")
    ap.add_argument("--seeds", type=int, default=9, help="number of noisy seeds for --check")
    a = ap.parse_args()
    generate(a.out, a.seed, a.noise)
    if a.check:
        sys.exit(0 if check(a.out, range(1, a.seeds + 1)) else 1)
