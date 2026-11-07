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
static double kernel(const double *restrict x, long n, int K) {
    const double a = 0.999999, b = 1e-7;
    double total = 0.0;
    #pragma omp parallel reduction(+:total)
    {
        double acc[BLK] = {0};
        #pragma omp for schedule(static)
        for (long i = 0; i < n; i += BLK) {
            double v[BLK];
            for (int j = 0; j < BLK; j++) v[j] = x[i + j];
            for (int k = 0; k < K; k++)
                for (int j = 0; j < BLK; j++) v[j] = v[j] * a + b;   // 1 FMA = 2 flops
            for (int j = 0; j < BLK; j++) acc[j] += v[j];
        }
        for (int j = 0; j < BLK; j++) total += acc[j];
    }
    return total;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s n_elements K [min_seconds]\n", argv[0]); return 1; }
    long n = atol(argv[1]); n = (n / BLK) * BLK; if (n < BLK) n = BLK;
    int K = atoi(argv[2]); if (K < 1) K = 1;
    double min_s = argc > 3 ? atof(argv[3]) : 1.0;
    int threads = omp_get_max_threads();

    double *x = aligned_alloc(64, ((n * sizeof(double) + 63) / 64) * 64);
    #pragma omp parallel for schedule(static)          // first-touch by the same threads
    for (long i = 0; i < n; i++) x[i] = 1.0 + (i % 7) * 1e-3;

    rapl_init();

    // warm-up + calibrate repetitions so the timed run lasts >= min_s
    double cs = kernel(x, n, K);
    double t0 = now(); long reps = 1;
    for (;;) {
        for (long r = 0; r < reps; r++) cs += kernel(x, n, K);
        double dt = now() - t0;
        if (dt > 0.2 * min_s) { reps = (long)(reps * min_s / dt) + 1; break; }
        reps *= 2; t0 = now();
    }

    double e0[64], e1[64];
    rapl_read(e0);
    t0 = now();
    for (long r = 0; r < reps; r++) cs += kernel(x, n, K);
    double T = now() - t0;
    rapl_read(e1);
    double Epkg, Edram; rapl_diff(e0, e1, &Epkg, &Edram);

    double W = 2.0 * K * (double)n * reps;
    double Q = 8.0 * (double)n * reps;
    printf("%ld,%ld,%d,%d,%ld,%.6e,%.6e,%.6f,%.6f,%.6f,%.6e\n",
           n, n * 8, K, threads, reps, W, Q, T, Epkg, Edram, cs);
    free(x);
    return 0;
}
