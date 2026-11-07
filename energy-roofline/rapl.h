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

// ---------- throttle monitor ----------
// Laptops throttle during a run in ways that break the "constant cost per op" model:
// thermald lowers the package long-term limit PL1 when the die gets hot, and the CPU's
// own thermal control (TCC) cuts clocks near Tjmax. A background thread samples PL1 and
// the package temperature every 50 ms during the timed region; the kernel's
// thermal_throttle counters (events and total throttled time) are compared before/after.
//   mon_start(); ...timed region...; mon_stop();
//   then mon.throttled, mon.thr_frac, mon.pl1_min_w, mon.temp_max_c, mon.events
// throttled = PL1 was lowered, or the package was thermally throttled for more than 2%
// of the timed region (brief TCC blips below that are counted in events but tolerated).
// PL1_NOMINAL_UW (env) gives the unthrottled PL1; default: PL1 at mon_start().
#include <pthread.h>
#include <unistd.h>
#include <glob.h>

static struct {
    pthread_t th; volatile int stop, running;
    char temp_path[256];
    double pl1_nominal_w, pl1_min_w, temp_max_c, t0, thr_frac;
    long ev0, events, ms0; int throttled;
} mon;

static double pl1_w(void) {
    double v = read_num("/sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw");
    return v < 0 ? -1 : v * 1e-6;
}
static double pkg_temp_c(void) {
    if (!mon.temp_path[0]) return -1;
    double v = read_num(mon.temp_path); return v < 0 ? -1 : v * 1e-3;
}
static long throttle_events(void) {   // core + package thermal throttle events, all CPUs
    glob_t g; long s = 0;
    if (glob("/sys/devices/system/cpu/cpu[0-9]*/thermal_throttle/*_throttle_count", 0, NULL, &g)) return 0;
    for (size_t i = 0; i < g.gl_pathc; i++) { double v = read_num(g.gl_pathv[i]); if (v > 0) s += (long)v; }
    globfree(&g); return s;
}
static long pkg_throttle_ms(void) {
    double v = read_num("/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_total_time_ms");
    return v < 0 ? 0 : (long)v;
}
static void *mon_loop(void *arg) {
    (void)arg;
    while (!mon.stop) {
        double p = pl1_w(), t = pkg_temp_c();
        if (p >= 0 && p < mon.pl1_min_w) mon.pl1_min_w = p;
        if (t > mon.temp_max_c) mon.temp_max_c = t;
        usleep(50000);
    }
    return NULL;
}
static void mon_start(void) {
    if (!mon.temp_path[0]) {                       // find the package temperature sensor
        glob_t g; char ty[64];
        if (!glob("/sys/class/thermal/thermal_zone*/type", 0, NULL, &g)) {
            for (size_t i = 0; i < g.gl_pathc; i++)
                if (!read_str(g.gl_pathv[i], ty, sizeof ty) && !strcmp(ty, "x86_pkg_temp")) {
                    snprintf(mon.temp_path, sizeof mon.temp_path, "%.*stemp",
                             (int)(strlen(g.gl_pathv[i]) - 4), g.gl_pathv[i]);
                    break;
                }
            globfree(&g);
        }
    }
    const char *nom = getenv("PL1_NOMINAL_UW");
    mon.pl1_nominal_w = nom && atof(nom) > 0 ? atof(nom) * 1e-6 : pl1_w();
    mon.pl1_min_w = 1e30; mon.temp_max_c = -1; mon.stop = 0;
    mon.ev0 = throttle_events();
    mon.ms0 = pkg_throttle_ms();
    mon.t0 = now();
    mon.running = !pthread_create(&mon.th, NULL, mon_loop, NULL);
}
static void mon_stop(void) {
    double p = pl1_w();
    if (mon.running) { mon.stop = 1; pthread_join(mon.th, NULL); mon.running = 0; }
    if (p >= 0 && p < mon.pl1_min_w) mon.pl1_min_w = p;
    if (mon.pl1_min_w > 1e29) mon.pl1_min_w = -1;
    double dt = now() - mon.t0;
    mon.events = throttle_events() - mon.ev0;
    mon.thr_frac = dt > 0 ? (pkg_throttle_ms() - mon.ms0) * 1e-3 / dt : 0;
    mon.throttled = mon.thr_frac > 0.02 ||
        (mon.pl1_nominal_w > 0 && mon.pl1_min_w >= 0 && mon.pl1_min_w < mon.pl1_nominal_w - 0.5);
}
static void mon_report(FILE *f) {
    fprintf(f, "throttled=%d throttle_frac=%.3f pl1_min_W=%.1f pl1_nominal_W=%.1f temp_max_C=%.0f throttle_events=%ld ",
            mon.throttled, mon.thr_frac, mon.pl1_min_w, mon.pl1_nominal_w, mon.temp_max_c, mon.events);
}

#endif
