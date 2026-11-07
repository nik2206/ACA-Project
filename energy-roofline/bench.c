// bench.c - tunable-intensity microbenchmark with RAPL energy measurement
// (modelled on Choi et al., IPDPS 2013/2014)
//
// For every double in an array: load it, apply K dependent FMAs
// (x = x*a + b), and accumulate the result. Per element:
//   W = 2*K flops, Q = 8 bytes  ->  intensity I = W/Q = K/4 flop/byte
//
// Usage: ./bench <n_elements> <K> [min_seconds]
// Thread count comes from OMP_NUM_THREADS.
// Prints one CSV line:
//   n,bytes,K,threads,reps,W,Q,time_s,E_pkg_J,E_dram_J,checksum
//
// Energy is read via RAPL (see rapl.h). Reading energy_uj needs root:
//   sudo chmod -R a+r /sys/class/powercap/intel-rapl     (until reboot)

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <omp.h>
#include "rapl.h"

#ifdef __AVX512F__
#define BLK 64   // 64 doubles = 8 independent AVX-512 FMA chains (hides FMA latency)
#else
#define BLK 32   // 32 doubles = 8 independent AVX2 FMA chains
#endif

// ---------- kernel ----------
// Each thread owns a fixed contiguous slice [blo[t], bhi[t]) of the array and runs all
// `reps` passes over it inside ONE parallel region: no fork/join or barrier per pass
// (that overhead dominated the tiny L1-sized runs), and a slice stays in its core's
// private caches. Slice sizes are balanced to measured per-thread speed (see balance()),
// because on hybrid CPUs (P-cores + E-cores) an equal split leaves the fast cores idle.
static long blo[1024], bhi[1024];   // per-thread slice, in elements (multiples of BLK)
static double tthr[1024];           // per-thread busy time of the last kernel() call

static double kernel(const double *restrict x, int K, long reps) {
    const double a = 0.999999, b = 1e-7;
    double total = 0.0;
    #pragma omp parallel reduction(+:total)
    {
        int t = omp_get_thread_num();
        const long lo = blo[t], hi = bhi[t];
        double acc[BLK] = {0};
        double t0 = now();
        for (long r = 0; r < reps; r++)
            for (long i = lo; i < hi; i += BLK) {
                double v[BLK];
                for (int j = 0; j < BLK; j++) v[j] = x[i + j];
                for (int k = 0; k < K; k++)
                    for (int j = 0; j < BLK; j++) v[j] = v[j] * a + b;   // 1 FMA = 2 flops
                for (int j = 0; j < BLK; j++) acc[j] += v[j];
            }
        tthr[t] = now() - t0;
        for (int j = 0; j < BLK; j++) total += acc[j];
    }
    return total;
}

// split n elements into slices proportional to weights w[0..nt-1]
static void set_slices(long n, int nt, const double *w) {
    long nblk = n / BLK; double sum = 0, c = 0;
    for (int t = 0; t < nt; t++) sum += w[t];
    for (int t = 0; t < nt; t++) {
        blo[t] = (long)(c / sum * nblk + 0.5) * BLK; c += w[t];
        bhi[t] = (long)(c / sum * nblk + 0.5) * BLK;
    }
    bhi[nt - 1] = n;
}
static double imbalance(int nt) {      // slowest / fastest thread busy time
    double mx = 0, mn = 1e30;
    for (int t = 0; t < nt; t++) if (bhi[t] > blo[t]) {
        if (tthr[t] > mx) mx = tthr[t];
        if (tthr[t] < mn) mn = tthr[t];
    }
    return mn > 0 && mn < 1e30 ? mx / mn : 1.0;
}
// Iteratively resize slices so that all threads finish at the same time
// (weight <- speed = elements / busy time, damped). Returns a checksum contribution.
static double balance(const double *x, long n, int K, int nt, double *w) {
    for (int t = 0; t < nt; t++) w[t] = 1.0;
    set_slices(n, nt, w);
    double cs = kernel(x, K, 1);                    // warm-up
    long r = 1;
    for (int it = 0; it < 8; ) {
        double t0 = now(); cs += kernel(x, K, r); double dt = now() - t0;
        if (dt < 0.02) { r *= 2; continue; }        // need >= 20 ms for a stable split
        if (imbalance(nt) < 1.02) break;
        for (int t = 0; t < nt; t++)
            if (bhi[t] > blo[t] && tthr[t] > 0)
                w[t] = 0.5 * w[t] + 0.5 * ((bhi[t] - blo[t]) / tthr[t]) / ((double)n / nt / dt);
        double m = 0; for (int t = 0; t < nt; t++) m += w[t] / nt;
        for (int t = 0; t < nt; t++) w[t] /= m;
        set_slices(n, nt, w);
        it++;
    }
    return cs;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s n_elements K [min_seconds]\n", argv[0]); return 1; }
    long n = atol(argv[1]); n = (n / BLK) * BLK; if (n < BLK) n = BLK;
    int K = atoi(argv[2]); if (K < 1) K = 1;
    double min_s = argc > 3 ? atof(argv[3]) : 1.0;
    int threads = omp_get_max_threads();
    if (threads > 1024) threads = 1024;
    omp_set_num_threads(threads);
    omp_set_dynamic(0);

    double *x = aligned_alloc(64, ((n * sizeof(double) + 63) / 64) * 64);
    #pragma omp parallel for schedule(static)
    for (long i = 0; i < n; i++) x[i] = 1.0 + (i % 7) * 1e-3;

    rapl_init();

    // balance slices across (possibly heterogeneous) cores, then
    // calibrate repetitions so the timed run lasts >= min_s
    double w[1024];
    double cs = balance(x, n, K, threads, w);
    double t0 = now(); long reps = 1;
    for (;;) {
        cs += kernel(x, K, reps);
        double dt = now() - t0;
        if (dt > 0.2 * min_s) { reps = (long)(reps * min_s / dt) + 1; break; }
        reps *= 2; t0 = now();
    }

    double e0[64], e1[64];
    rapl_read(e0);
    t0 = now();
    cs += kernel(x, K, reps);
    double T = now() - t0;
    rapl_read(e1);
    double Epkg, Edram; rapl_diff(e0, e1, &Epkg, &Edram);

    double W = 2.0 * K * (double)n * reps;
    double Q = 8.0 * (double)n * reps;
    printf("%ld,%ld,%d,%d,%ld,%.6e,%.6e,%.6f,%.6f,%.6f,%.6e\n",
           n, n * 8, K, threads, reps, W, Q, T, Epkg, Edram, cs);
    // diagnostics on stderr (not part of the CSV): load balance and platform (psys) energy
    fprintf(stderr, "info: imbalance=%.3f psys_J=%.6f shares=", imbalance(threads), rapl_psys(e0, e1));
    for (int t = 0; t < threads; t++)
        fprintf(stderr, "%s%.3f", t ? ":" : "", (double)(bhi[t] - blo[t]) / n * threads);
    fprintf(stderr, "\n");
    free(x);
    return 0;
}
