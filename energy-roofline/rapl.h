// rapl.h - Linux RAPL energy counters + wall-clock timer, shared by bench.c and kernels.c
//
// Energy is read from /sys/class/powercap (Linux RAPL; works on Intel and
// on AMD Zen with kernel >= 5.8). Reading energy_uj needs root:
//   sudo chmod -R a+r /sys/class/powercap/intel-rapl     (until reboot)
//
// Usage:
//   rapl_init();
//   double e0[64], e1[64]; rapl_read(e0); ...work... rapl_read(e1);
//   double Epkg, Edram; rapl_diff(e0, e1, &Epkg, &Edram);   // J, -1 if unavailable
//   double Epsys = rapl_psys(e0, e1);   // platform domain (Intel "psys"), J, -1 if absent;
//                                       // reported separately, never added to Epkg
#ifndef RAPL_H
#define RAPL_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <dirent.h>

typedef struct { char path[512]; double max_uj; int is_dram, is_psys; } dom_t;
static dom_t doms[64];
static int ndoms = 0;

static int read_str(const char *p, char *buf, int len) {
    FILE *f = fopen(p, "r"); if (!f) return -1;
    if (!fgets(buf, len, f)) { fclose(f); return -1; }
    fclose(f); buf[strcspn(buf, "\n")] = 0; return 0;
}
static double read_num(const char *p) {
    char b[64]; if (read_str(p, b, sizeof b)) return -1; return atof(b);
}
static void rapl_init(void) {
    const char *base = "/sys/class/powercap";
    DIR *d = opendir(base); if (!d) return;
    struct dirent *e;
    while ((e = readdir(d))) {
        // top-level packages: intel-rapl:0, intel-rapl:1 ; subdomains: intel-rapl:0:2
        if (strncmp(e->d_name, "intel-rapl:", 11)) continue;
        int colons = 0; for (char *c = e->d_name; *c; c++) colons += (*c == ':');
        char name[64], p[512];
        snprintf(p, sizeof p, "%s/%s/name", base, e->d_name);
        if (read_str(p, name, sizeof name)) continue;
        int is_pkg = (colons == 1 && !strncmp(name, "package", 7));
        int is_dram = !strcmp(name, "dram");
        int is_psys = (colons == 1 && !strcmp(name, "psys"));
        if (!is_pkg && !is_dram && !is_psys) continue;
        snprintf(doms[ndoms].path, 512, "%s/%s/energy_uj", base, e->d_name);
        if (read_num(doms[ndoms].path) < 0) {
            fprintf(stderr, "warning: cannot read %s (run: sudo chmod -R a+r %s/intel-rapl*)\n",
                    doms[ndoms].path, base);
            continue;
        }
        snprintf(p, sizeof p, "%s/%s/max_energy_range_uj", base, e->d_name);
        doms[ndoms].max_uj = read_num(p);
        doms[ndoms].is_dram = is_dram;
        doms[ndoms].is_psys = is_psys;
        ndoms++;
    }
    closedir(d);
    int npkg = 0; for (int i = 0; i < ndoms; i++) npkg += !doms[i].is_psys;
    if (!npkg) { ndoms = 0; fprintf(stderr, "warning: no readable RAPL domains, energy will be -1\n"); }
}
static void rapl_read(double *v) { for (int i = 0; i < ndoms; i++) v[i] = read_num(doms[i].path); }
static void rapl_diff(const double *a, const double *b, double *pkg, double *dram) {
    if (!ndoms) { *pkg = *dram = -1; return; }
    *pkg = 0; *dram = 0; int have_dram = 0;
    for (int i = 0; i < ndoms; i++) {
        double d = b[i] - a[i];
        if (d < 0) d += doms[i].max_uj;            // counter wrap-around
        if (doms[i].is_psys) continue;
        if (doms[i].is_dram) { *dram += d * 1e-6; have_dram = 1; }
        else *pkg += d * 1e-6;
    }
    if (!have_dram) *dram = -1;
}
static double rapl_psys(const double *a, const double *b) {
    for (int i = 0; i < ndoms; i++) if (doms[i].is_psys) {
        double d = b[i] - a[i];
        if (d < 0) d += doms[i].max_uj;
        return d * 1e-6;
    }
    return -1;
}

// ---------- timer ----------
static double now(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + 1e-9 * t.tv_nsec;
}

#endif
