// kernels.c - real kernels for the energy roofline, measured like bench.c
//
// Usage: ./kernels <kernel> <n> [tile] [min_seconds]
//   triad         a[i] = b[i] + s*c[i], n doubles          W = 2n,   Q = 32n per rep
//                 (Q: read b, c; write a; write-allocate read of a)
//   matmul_naive  C += A*B, n x n, i-k-j loop order        W = 2n^3, Q = 8n^3 + 24n^2 per rep
//                 (B re-streamed from DRAM for every row i: upper bound)
//   matmul_tiled  same, blocked with tile b (default 64)   W = 2n^3, Q = 16n^3/b + 24n^2 per rep
//   check         correctness test: naive vs tiled (b = 32, 48, 64, 128) on n x n
// n accepts K/M suffixes (32M = 32*2^20). Thread count comes from OMP_NUM_THREADS.
//
// Environment:
//   Q_OVERRIDE=<bytes per rep>  use a measured DRAM traffic per rep instead of the formula
//   REPS=<r>                    skip calibration, time exactly r reps (used to measure Q
//                               with perf by differencing two rep counts; see run.sh)
//
// Prints one CSV line, same columns as bench.c:
//   n,bytes,K,threads,reps,W,Q,time_s,E_pkg_J,E_dram_J,checksum
// with K = tile for matmul_tiled, 0 otherwise; bytes = working set of all arrays.
//
// Work is handed out dynamically (rows / tiles / chunks) so the fast P-cores and slow
// E-cores of hybrid CPUs all stay busy until the end of each rep.

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <omp.h>
#include "rapl.h"

// ---------- kernels ----------
static void triad(double *restrict a, const double *restrict b, const double *restrict c, long n) {
    const double s = 1.000001;
    #pragma omp parallel for schedule(dynamic, 65536)
    for (long i = 0; i < n; i++) a[i] = b[i] + s * c[i];
}

static void matmul_naive(double *restrict C, const double *restrict A, const double *restrict B, long n) {
    #pragma omp parallel for schedule(dynamic, 4)
    for (long i = 0; i < n; i++)
        for (long k = 0; k < n; k++) {
            const double a = A[i * n + k];
            for (long j = 0; j < n; j++) C[i * n + j] += a * B[k * n + j];
        }
}

static void matmul_tiled(double *restrict C, const double *restrict A, const double *restrict B,
                         long n, long bs) {
    const long nb = (n + bs - 1) / bs;
    // each (ii, jj) tile of C belongs to one thread; kk runs in order, so every C[i][j]
    // sums over k in the same order as the naive loop
    #pragma omp parallel for collapse(2) schedule(dynamic, 1)
    for (long ib = 0; ib < nb; ib++)
        for (long jb = 0; jb < nb; jb++) {
            const long i0 = ib * bs, i1 = i0 + bs < n ? i0 + bs : n;
            const long j0 = jb * bs, j1 = j0 + bs < n ? j0 + bs : n;
            for (long k0 = 0; k0 < n; k0 += bs) {
                const long k1 = k0 + bs < n ? k0 + bs : n;
                for (long i = i0; i < i1; i++)
                    for (long k = k0; k < k1; k++) {
                        const double a = A[i * n + k];
                        double *restrict c = C + i * n;
                        const double *restrict b = B + k * n;
                        for (long j = j0; j < j1; j++) c[j] += a * b[j];
                    }
            }
        }
}

// ---------- helpers ----------
static double *alloc(long n) {
    double *p = aligned_alloc(64, ((n * sizeof(double) + 63) / 64) * 64);
    if (!p) { fprintf(stderr, "out of memory (%ld doubles)\n", n); exit(1); }
    return p;
}
static void fill(double *p, long n, double base) {
    #pragma omp parallel for schedule(static)
    for (long i = 0; i < n; i++) p[i] = base + (i % 7) * 1e-3;
}
static long parse_n(const char *s) {
    char *e; long v = strtol(s, &e, 10);
    if (*e == 'K' || *e == 'k') v <<= 10;
    else if (*e == 'M' || *e == 'm') v <<= 20;
    return v;
}

static int check(long n) {
    double *A = alloc(n * n), *B = alloc(n * n), *C0 = alloc(n * n), *C1 = alloc(n * n);
    fill(A, n * n, 1.0); fill(B, n * n, 0.5);
    memset(C0, 0, n * n * sizeof(double));
    matmul_naive(C0, A, B, n);
    long tiles[] = {32, 48, 64, 128};
    int bad = 0;
    for (int t = 0; t < 4; t++) {
        memset(C1, 0, n * n * sizeof(double));
        matmul_tiled(C1, A, B, n, tiles[t]);
        double md = 0;
        for (long i = 0; i < n * n; i++) { double d = fabs(C0[i] - C1[i]); if (d > md) md = d; }
        printf("n=%ld tile=%ld max_abs_diff=%.3e %s\n", n, tiles[t], md, md < 1e-9 ? "OK" : "FAIL");
        bad |= !(md < 1e-9);
    }
    free(A); free(B); free(C0); free(C1);
    return bad;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s triad|matmul_naive|matmul_tiled|check n [tile] [min_seconds]\n", argv[0]);
        return 1;
    }
    const char *kname = argv[1];
    long n = parse_n(argv[2]);
    if (n < 1) { fprintf(stderr, "bad n\n"); return 1; }
    if (!strcmp(kname, "check")) return check(n);

    int kind = !strcmp(kname, "triad") ? 0 : !strcmp(kname, "matmul_naive") ? 1
             : !strcmp(kname, "matmul_tiled") ? 2 : -1;
    if (kind < 0) { fprintf(stderr, "unknown kernel %s\n", kname); return 1; }
    long tile = kind == 2 ? (argc > 3 ? atol(argv[3]) : 64) : 0;
    if (kind == 2 && tile < 1) tile = 64;
    double min_s = argc > 4 ? atof(argv[4]) : 1.0;
    int threads = omp_get_max_threads();

    double *x, *y, *z; long len, bytes;
    if (kind == 0) { len = n; bytes = 3 * n * 8; }
    else           { len = n * n; bytes = 3 * n * n * 8; }
    x = alloc(len); y = alloc(len); z = alloc(len);   // triad: a, b, c   matmul: C, A, B
    fill(y, len, 1.0); fill(z, len, 0.5);
    memset(x, 0, len * sizeof(double));

    #define RUN() do { if (kind == 0) triad(x, y, z, n); \
                       else if (kind == 1) matmul_naive(x, y, z, n); \
                       else matmul_tiled(x, y, z, n, tile); } while (0)

    rapl_init();

    // warm-up + calibrate repetitions so the timed run lasts >= min_s
    RUN();
    long reps = 1;
    const char *fixed = getenv("REPS");
    if (fixed && atol(fixed) > 0) reps = atol(fixed);
    else {
        double t0 = now();
        for (;;) {
            for (long r = 0; r < reps; r++) RUN();
            double dt = now() - t0;
            if (dt > 0.2 * min_s) { reps = (long)(reps * min_s / dt) + 1; break; }
            reps *= 2; t0 = now();
        }
    }

    double e0[64], e1[64];
    rapl_read(e0);
    double t0 = now();
    for (long r = 0; r < reps; r++) RUN();
    double T = now() - t0;
    rapl_read(e1);
    double Epkg, Edram; rapl_diff(e0, e1, &Epkg, &Edram);

    double nd = (double)n, Wrep, Qrep;
    if (kind == 0)      { Wrep = 2 * nd;          Qrep = 32 * nd; }
    else if (kind == 1) { Wrep = 2 * nd * nd * nd; Qrep = 8 * nd * nd * nd + 24 * nd * nd; }
    else                { Wrep = 2 * nd * nd * nd; Qrep = 16 * nd * nd * nd / tile + 24 * nd * nd; }
    const char *qo = getenv("Q_OVERRIDE");
    int q_measured = qo && atof(qo) > 0;
    if (q_measured) Qrep = atof(qo);

    double cs = 0;                                    // anti-dead-code checksum
    for (long i = 0; i < len; i += 4099) cs += x[i];

    printf("%ld,%ld,%ld,%d,%ld,%.6e,%.6e,%.6f,%.6f,%.6f,%.6e\n",
           n, bytes, tile, threads, reps, Wrep * reps, Qrep * reps, T, Epkg, Edram, cs);
    fprintf(stderr, "info: kernel=%s Q=%s psys_J=%.6f\n", kname,
            q_measured ? "measured" : "analytic", rapl_psys(e0, e1));
    free(x); free(y); free(z);
    return 0;
}
