#!/usr/bin/env python3
"""analyze.py - fit the energy-roofline model (Choi et al., IPDPS 2013 / 2014) to a
results.csv and produce the figures, summary.txt and summary.json.

Usage:
  python3 analyze.py <results.csv> [--flags run_flags.csv] [--out DIR] [--tag NAME]
                                   [--idle idle_power.txt]

Model (paper 1):
  T = max(W*tau_flop, Q*tau_mem)                 time: flops and bytes overlap
  E = W*eps_flop + Q*eps_mem + pi0*T             energy: nothing overlaps
Power-capped time (paper 2):
  T = max(W*tau_flop, Q*tau_mem, (W*eps_flop + Q*eps_mem)/dpi),  dpi = max(P) - pi0
Fit (paper 1, eq. 9):  E/W = eps_flop + eps_mem*(Q/W) + pi0*(T/W)   (non-negative LSQ)

Throttled rows (run_flags.csv, throttled=1) are removed before every fit. A configuration
whose repeats are ALL throttled is kept only for plotting (hollow / hatched marks).
Only numpy and matplotlib are required.
"""
import argparse, csv, json, os, re, sys
from itertools import combinations
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mt

C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]          # categorical slots 1-4
INK, MUTED, FAINT = "#222222", "#888888", "#f1f1f1"
REAL_STYLE = {   # real kernels: distinct marker per kernel, shared ink colour
    ("triad", 0): ("triad", "s"), ("matmul_naive", 0): ("naive mm", "D"),
    ("matmul_tiled", 32): ("tiled b=32", "^"), ("matmul_tiled", 64): ("tiled b=64", "v"),
    ("matmul_tiled", 128): ("tiled b=128", "P")}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6,
                     "lines.linewidth": 1.6, "lines.markersize": 6, "legend.frameon": False,
                     "legend.fontsize": 8.5, "savefig.dpi": 160, "savefig.bbox": "tight",
                     "mathtext.fontset": "dejavusans"})
L_BTAU, L_BEPS = r"$B_\tau$", r"$\hat{B}_\epsilon$"


# ------------------------------------------------------------------ helpers
def nnls(A, b):
    """Exact non-negative least squares for a handful of columns (all active sets)."""
    n, best = A.shape[1], (np.inf, np.zeros(A.shape[1]))
    for k in range(1, n + 1):
        for cols in combinations(range(n), k):
            x, *_ = np.linalg.lstsq(A[:, cols], b, rcond=None)
            if (x < 0).any():
                continue
            full = np.zeros(n); full[list(cols)] = x
            r = np.sum((A @ full - b) ** 2)
            if r < best[0]:
                best = (r, full)
    return best[1]


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def guess_sibling(results, prefix):
    """results.csv -> <prefix>.csv; results_run2.csv -> <prefix>_run2.csv"""
    d, b = os.path.split(results)
    m = re.match(r"results(.*)\.csv$", b)
    if not m:
        return None
    for ext in (".csv", ".txt"):
        p = os.path.join(d, prefix + m.group(1) + ext)
        if os.path.exists(p):
            return p
    return None


def nice_log(ax, which="both"):
    """plain-number tick labels on log axes (0.2, 1, 5, 20 instead of 2x10^-1 ...)"""
    f = mt.FuncFormatter(lambda v, _: f"{v:g}")
    axes = [ax.xaxis, ax.yaxis] if which == "both" else [ax.xaxis if which == "x" else ax.yaxis]
    for a_ in axes:
        if a_.get_scale() == "log":
            a_.set_major_formatter(f)
            a_.set_minor_formatter(mt.FuncFormatter(
                lambda v, _: f"{v:g}" if v > 0 and round(v / 10 ** np.floor(np.log10(v))) in (2, 5) else ""))


def pct(x):
    return 100 * np.asarray(x, float)


# ------------------------------------------------------------------ load
def load(results_path, flags_path):
    rows = read_csv(results_path)
    for r in rows:
        for k in ("n", "bytes", "K", "threads", "reps", "W", "Q", "time_s", "E_pkg_J", "E_dram_J"):
            r[k] = float(r[k])
        r["K"], r["threads"] = int(r["K"]), int(r["threads"])
        r["E"] = r["E_pkg_J"] + max(r["E_dram_J"], 0.0)
        r["throttled"], r["tfrac"] = 0, 0.0
    if all(r["E_pkg_J"] < 0 for r in rows):
        sys.exit("No energy data (E_pkg_J = -1). RAPL was not readable - see README.")
    if flags_path:
        fl = read_csv(flags_path)
        if len(fl) != len(rows):
            sys.exit(f"{flags_path}: {len(fl)} rows but {results_path} has {len(rows)}")
        for r, f in zip(rows, fl):
            if (f["exp"], f["level"], int(f["K"]), int(f["threads"])) != \
               (r["exp"], r["level"], r["K"], r["threads"]):
                sys.exit(f"{flags_path}: row {f['row']} does not match results row")
            r["throttled"], r["tfrac"] = int(f["throttled"]), float(f["throttle_frac"])
    return rows


def aggregate(rows):
    """Median of repeats per (exp, level, K, threads). Throttled repeats are dropped when at
    least one clean repeat exists; otherwise the throttled ones are used and marked."""
    groups = {}
    for r in rows:
        groups.setdefault((r["exp"], r["level"], r["K"], r["threads"]), []).append(r)
    out = []
    for (exp, lvl, K, thr), rs in groups.items():
        clean = [r for r in rs if not r["throttled"]]
        use = clean or rs
        med = lambda k: float(np.median([r[k] for r in use]))
        g = dict(exp=exp, level=lvl, K=K, threads=thr, n=use[0]["n"], reps=med("reps"),
                 W=med("W"), Q=med("Q"), T=med("time_s"), E=med("E"),
                 n_rep=len(rs), n_thr=len(rs) - len(clean), all_thr=not clean)
        g["I"] = g["W"] / g["Q"]
        g["GFLOPs"], g["GBs"] = g["W"] / g["T"] / 1e9, g["Q"] / g["T"] / 1e9
        g["GFLOPJ"], g["P"] = g["W"] / g["E"] / 1e9, g["E"] / g["T"]
        out.append(g)
    return out


def sel(g, exp, **kw):
    return [x for x in g if x["exp"] == exp and all(x[k] == v for k, v in kw.items())]


def col(lst, k):
    return np.array([x[k] for x in lst], float)


# ------------------------------------------------------------------ model
class Model:
    def __init__(s, eps_f, eps_m, pi0, peak_f, peak_b, dpi=None):
        s.eps_f, s.eps_m, s.pi0, s.peak_f, s.peak_b, s.dpi = eps_f, eps_m, pi0, peak_f, peak_b, dpi
        s.tau_f, s.tau_m = 1 / peak_f, 1 / peak_b
        s.B_tau, s.B_eps = s.tau_m / s.tau_f, eps_m / eps_f
        s.eps0 = pi0 * s.tau_f                       # constant energy per flop at peak
        s.eta = eps_f / (eps_f + s.eps0)
        # effective energy balance: the fixed point I = B_eps_hat(I) (paper 1 eq. 6), i.e.
        # the intensity where the arch line reaches half of its peak
        a = s.eta * s.B_eps
        s.B_eps_hat = a if a >= s.B_tau else (a + (1 - s.eta) * s.B_tau) / (2 - s.eta)
        s.peak_fj = 1 / (eps_f + s.eps0)

    def T(s, W, Q, capped=False):
        W, Q = np.asarray(W, float), np.asarray(Q, float)
        t = np.maximum(W * s.tau_f, Q * s.tau_m)
        if capped and s.dpi:
            t = np.maximum(t, (W * s.eps_f + Q * s.eps_m) / s.dpi)
        return t

    def E(s, W, Q, capped=False):
        W, Q = np.asarray(W, float), np.asarray(Q, float)
        return W * s.eps_f + Q * s.eps_m + s.pi0 * s.T(W, Q, capped)

    def curves(s, I, capped=False):     # per unit work: flop/s, flop/J, W
        I = np.asarray(I, float)
        t, e = s.T(1.0, 1 / I, capped), s.E(1.0, 1 / I, capped)
        return 1 / t, 1 / e, e / t


def fit(g):
    s = [x for x in sel(g, "intensity") if not x["all_thr"]]
    s.sort(key=lambda x: x["I"])
    if len(s) < 3:
        sys.exit("Need at least 3 clean Exp 1 (intensity) configurations to fit.")
    W, Q, T, E = col(s, "W"), col(s, "Q"), col(s, "T"), col(s, "E")
    eps_f, eps_m, pi0 = nnls(np.c_[np.ones(len(s)), Q / W, T / W], E / W)
    m = Model(eps_f, eps_m, pi0, col(s, "GFLOPs").max() * 1e9, col(s, "GBs").max() * 1e9)
    m.dpi = max(col(s, "P").max() - pi0, 1e-9)
    m.P_max = col(s, "P").max()
    return m, s


def errs(pred, meas):
    e = (np.asarray(pred) - np.asarray(meas)) / np.asarray(meas)
    return dict(median=float(np.median(np.abs(e)) * 100), max=float(np.max(np.abs(e)) * 100),
                mean_signed=float(np.mean(e) * 100))


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results")
    ap.add_argument("--flags", help="run_flags.csv (default: sibling of results, if present)")
    ap.add_argument("--no-flags", action="store_true", help="ignore run_flags even if present")
    ap.add_argument("--idle", help="idle_power.txt (default: sibling of results, if present)")
    ap.add_argument("--out", help="output directory (default: alongside the CSV)")
    ap.add_argument("--tag", default="", help="short name used in titles and summary")
    a = ap.parse_args()

    flags = None if a.no_flags else (a.flags or guess_sibling(a.results, "run_flags"))
    idle_p = a.idle or guess_sibling(a.results, "idle_power")
    out = a.out or os.path.dirname(os.path.abspath(a.results))
    os.makedirs(out, exist_ok=True)
    P = lambda f: os.path.join(out, f)
    tag = a.tag
    tt = (lambda t: f"{t}  [{tag}]") if tag else (lambda t: t)

    rows = load(a.results, flags)
    idle_W = None
    if idle_p and os.path.exists(idle_p):
        m_ = re.search(r"idle_pkg_W\s*=\s*([\d.]+)", open(idle_p).read())
        idle_W = float(m_.group(1)) if m_ else None

    # ---- throttling report
    exps = ["intensity", "reuse", "threads", "real"]
    drop_lines = [f"flags file: {flags or '(none - no rows dropped)'}"]
    for e in exps:
        rs = [r for r in rows if r["exp"] == e]
        if rs:
            nt = sum(r["throttled"] for r in rs)
            drop_lines.append(f"  {e:<10}: {nt:3d} of {len(rs):3d} rows throttled and dropped")
    print("\n".join(drop_lines))

    g = aggregate(rows)
    m, s = fit(g)
    W, Q, T, E = col(s, "W"), col(s, "Q"), col(s, "T"), col(s, "E")
    err = dict(
        energy=errs(m.E(W, Q), E), time=errs(m.T(W, Q), T),
        power=errs(m.E(W, Q) / m.T(W, Q), E / T),
        energy_capped=errs(m.E(W, Q, True), E), time_capped=errs(m.T(W, Q, True), T),
        power_capped=errs(m.E(W, Q, True) / m.T(W, Q, True), E / T))
    # how far below the roof the points near the corner sit
    corner = [(x["I"], 100 * (1 - x["GFLOPs"] * 1e9 / m.curves(x["I"])[0]))
              for x in s if m.B_tau / 4 <= x["I"] <= m.B_tau * 4]

    # ---- Exp 2: per-level (inclusive) data-movement energy, eps_flop and pi0 held fixed
    lv = []
    for L in ["L1", "L2", "L3", "DRAM"]:
        d = sel(g, "reuse", level=L)
        if not d:
            continue
        dc = [x for x in d if not x["all_thr"]]
        if dc:
            resid = col(dc, "E") - m.eps_f * col(dc, "W") - m.pi0 * col(dc, "T")
            # least squares through the origin on RELATIVE residuals (weights 1/E^2): at high K
            # the flop and pi0 terms dwarf the data term, and a 1% error in eps_flop would
            # otherwise dominate the (small) cache energy
            q, w = col(dc, "Q"), 1 / col(dc, "E") ** 2
            e_lv = max(float((w * resid * q).sum() / (w * q ** 2).sum()), 0.0)
        else:
            e_lv = float("nan")
        lv.append(dict(level=L, pJ_per_B=e_lv * 1e12, max_GBs=float(col(d, "GBs").max()),
                       max_GBs_clean=float(col(dc, "GBs").max()) if dc else float("nan"),
                       n_configs=len(d), n_configs_used=len(dc),
                       excluded_K=[x["K"] for x in d if x["all_thr"]]))

    # ---- Exp 4: real kernels vs the model
    real = sorted(sel(g, "real"), key=lambda x: (x["level"], x["K"]))
    for x in real:
        x["name"], x["marker"] = REAL_STYLE.get((x["level"], x["K"]), (f"{x['level']} {x['K']}", "X"))
        x["T_model"], x["E_model"] = float(m.T(x["W"], x["Q"])), float(m.E(x["W"], x["Q"]))
        x["T_model_cap"], x["E_model_cap"] = float(m.T(x["W"], x["Q"], True)), float(m.E(x["W"], x["Q"], True))
        x["T_err"] = 100 * (x["T_model"] - x["T"]) / x["T"]
        x["E_err"] = 100 * (x["E_model"] - x["E"]) / x["E"]
        x["T_err_cap"] = 100 * (x["T_model_cap"] - x["T"]) / x["T"]
        x["E_err_cap"] = 100 * (x["E_model_cap"] - x["E"]) / x["E"]
        # energy model fed with the MEASURED time: isolates the energy terms from the time model
        x["E_model_Tmeas"] = m.eps_f * x["W"] + m.eps_m * x["Q"] + m.pi0 * x["T"]
        x["E_err_Tmeas"] = 100 * (x["E_model_Tmeas"] - x["E"]) / x["E"]

    # ---- Exp 3: threads
    th = sel(g, "threads")
    thr_res = []
    for K in sorted({x["K"] for x in th}):
        d = sorted(sel(g, "threads", K=K), key=lambda x: x["threads"])
        dc = [x for x in d if not x["all_thr"]] or d
        be, bt = max(dc, key=lambda x: x["GFLOPJ"]), max(dc, key=lambda x: x["GFLOPs"])
        thr_res.append(dict(I=K / 4, K=K, fastest=bt["threads"], most_efficient=be["threads"],
                            best_GFLOPJ=be["GFLOPJ"], GFLOPJ_at_fastest=bt["GFLOPJ"],
                            points=[dict(threads=x["threads"], GFLOPs=x["GFLOPs"], GFLOPJ=x["GFLOPJ"],
                                         P=x["P"], throttled=x["all_thr"]) for x in d]))

    # ================================================================= figures
    Imin = min([x["I"] for x in s] + [x["I"] for x in real]) / 2
    Imax = max(x["I"] for x in s) * 2
    Ip = np.logspace(np.log10(Imin), np.log10(Imax), 600)
    mf, mj, mp = m.curves(Ip)
    cf, cj, cp = m.curves(Ip, capped=True)
    cap_differs = np.max(np.abs(cf / mf - 1)) > 0.05

    def vlines(ax, where="top"):
        ax.axvline(m.B_tau, color=MUTED, ls="--", lw=1)
        ax.axvline(m.B_eps_hat, color=MUTED, ls=":", lw=1)
        tr = ax.get_xaxis_transform()
        lo, hi = sorted([m.B_tau, m.B_eps_hat])
        y = 0.97 if where == "top" else 0.03
        va = "top" if where == "top" else "bottom"
        for x, lab, ha in ((lo, None, "right"), (hi, None, "left")):
            name = L_BTAU if x == m.B_tau else L_BEPS
            pad = 0.94 if ha == "right" else 1.06
            ax.text(x * pad, y, f"{name}={x:.2f}", transform=tr, ha=ha, va=va, fontsize=8, color=INK)

    def real_marks(ax, ykey):
        for x in real:
            ax.plot(x["I"], x[ykey], x["marker"], ms=7, mfc="white" if x["all_thr"] else INK,
                    mec=INK, mew=1.1, ls="none",
                    label=x["name"] + (" (throttled)" if x["all_thr"] else ""))

    # fig1: roofline
    fig, ax = plt.subplots(figsize=(6.4, 4.3))
    ax.loglog(Ip, mf / 1e9, color=C[1], label="model (roofline)")
    if cap_differs:
        ax.loglog(Ip, cf / 1e9, color=C[2], ls="--", label=fr"power-capped model ($\Delta\pi$={m.dpi:.0f} W)")
    ax.loglog(col(s, "I"), col(s, "GFLOPs"), "o", color=C[0], label="synthetic kernel (Exp 1)")
    real_marks(ax, "GFLOPs")
    ax.set(xlabel="Arithmetic intensity I (flop/byte)", ylabel="Performance (GFLOP/s)", title=tt("Time roofline"))
    vlines(ax, "bottom"); ax.legend(loc="upper left", ncol=1)
    nice_log(ax); fig.savefig(P("fig1_roofline.png")); plt.close(fig)

    # fig2: arch line
    fig, ax = plt.subplots(figsize=(6.4, 4.3))
    ax.loglog(Ip, mj / 1e9, color=C[1], label="model (arch line)")
    if cap_differs and np.max(np.abs(cj / mj - 1)) > 0.01:
        ax.loglog(Ip, cj / 1e9, color=C[2], ls="--", label="power-capped model")
    ax.loglog(col(s, "I"), col(s, "GFLOPJ"), "o", color=C[0], label="synthetic kernel (Exp 1)")
    real_marks(ax, "GFLOPJ")
    ax.axhline(m.peak_fj / 1e9, color=MUTED, lw=0.8)
    ax.set(xlabel="Arithmetic intensity I (flop/byte)", ylabel="Energy efficiency (GFLOP/J)",
           title=tt("Energy roofline: the arch line"))
    vlines(ax, "bottom"); ax.legend(loc="lower right", bbox_to_anchor=(1, 0.1))
    nice_log(ax); fig.savefig(P("fig2_archline.png")); plt.close(fig)

    # fig3: powerline
    fig, ax = plt.subplots(figsize=(6.4, 4.3))
    ax.semilogx(Ip, mp, color=C[1], label="model (uncapped)")
    ax.semilogx(Ip, cp, color=C[2], ls="--", label=fr"power-capped model ($\Delta\pi$={m.dpi:.0f} W)")
    ax.semilogx(col(s, "I"), col(s, "P"), "o", color=C[0], label="measured (Exp 1)")
    ax.axhline(m.pi0, color=MUTED, lw=1)
    ax.text(Ip[0], m.pi0, fr" constant power $\pi_0$ = {m.pi0:.1f} W", va="bottom", fontsize=8, color=INK)
    if idle_W is not None:
        ax.axhline(idle_W, color=MUTED, lw=1, ls=":")
        ax.text(Ip[0], idle_W, f" idle package power = {idle_W:.1f} W", va="bottom", fontsize=8, color=INK)
    ax.set(xlabel="Arithmetic intensity I (flop/byte)", ylabel="Average package power (W)", title=tt("Powerline"))
    ax.set_ylim(0, max(mp.max(), col(s, "P").max()) * 1.12)
    vlines(ax, "top"); ax.legend(loc="center right")
    nice_log(ax); fig.savefig(P("fig3_powerline.png")); plt.close(fig)

    # fig4: per-level energy + bandwidth
    if lv:
        fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.8))
        names = [x["level"] for x in lv]
        v = [x["pJ_per_B"] for x in lv]
        axs[0].bar(names, v, color=C[0], width=0.6)
        for i, y in enumerate(v):
            axs[0].text(i, y, f"{y:.0f}", ha="center", va="bottom", fontsize=9, color=INK)
        axs[0].set(ylabel="Energy per byte (pJ/B)", title="Data-movement energy by level\n(inclusive upper bound)")
        bw, bthr = [], []
        for x in lv:
            best = max(sel(g, "reuse", level=x["level"]), key=lambda y: y["GBs"])
            bw.append(best["GBs"]); bthr.append(best["all_thr"])
        bars = axs[1].bar(names, bw, color=C[0], width=0.6)
        for i, (b, y, t) in enumerate(zip(bars, bw, bthr)):
            if t:
                b.set_facecolor("white"); b.set_edgecolor(C[0]); b.set_hatch("////")
            axs[1].text(i, y, f"{y:.0f}" + ("*" if t else ""), ha="center", va="bottom", fontsize=9, color=INK)
        axs[1].set(ylabel="Bandwidth (GB/s)", title="Peak streaming bandwidth by level\n(K=1-2)")
        for ax in axs:
            ax.set_ylim(0, ax.get_ylim()[1] * 1.1); ax.grid(axis="x", visible=False)
        note = "Inclusive: each value also contains the per-element load/add instruction energy and the cost of " \
               "passing through the levels above (as in paper 2)."
        excl = [f"{x['level']} K={','.join(map(str, x['excluded_K']))}" for x in lv if x["excluded_K"]]
        if excl:
            note += "\nExcluded from the energy fit (all repeats throttled): " + "; ".join(excl) + "."
        if any(bthr):
            note += "  * hatched bar: from a throttled run."
        fig.suptitle(tt("Data reuse: where the data lives"), y=1.02)
        fig.text(0.01, -0.06, note, fontsize=7.5, color=MUTED, ha="left", va="top", wrap=True)
        fig.tight_layout(); fig.savefig(P("fig4_data_reuse.png")); plt.close(fig)

        # fig5: arch lines by data location
        fig, ax = plt.subplots(figsize=(6.4, 4.3))
        for i, L in enumerate(names):
            d = sorted(sel(g, "reuse", level=L), key=lambda x: x["I"])
            ax.loglog(col(d, "I"), col(d, "GFLOPJ"), "-", color=C[i], lw=1.2)
            for x in d:
                ax.plot(x["I"], x["GFLOPJ"], "o", color=C[i], mfc="white" if x["all_thr"] else C[i])
            ax.plot([], [], "o-", color=C[i], label=L)
        ax.plot([], [], "o", color=MUTED, mfc="white", label="all repeats throttled")
        ax.set(xlabel="Arithmetic intensity I (flop/byte)", ylabel="Energy efficiency (GFLOP/J)",
               title=tt("Energy efficiency by data location"))
        ax.legend(loc="lower right")
        nice_log(ax); fig.savefig(P("fig5_reuse_archlines.png")); plt.close(fig)

    # fig6: thread scaling
    if th:
        fig, axs = plt.subplots(2, 2, figsize=(10, 7))
        tvals = sorted({x["threads"] for x in th})
        npc = 4  # P-cores (notes.txt): threads 1-4 P only, 6-8 add E-cores, 12 adds SMT
        regions = [(0.5, npc + 0.5, "P-cores"), (npc + 0.5, 8.5, "+E-cores"), (8.5, max(tvals) + 0.5, "+SMT")]
        panels = [("T", "Time per unit work (s)"), ("E", "Energy per unit work (J)"),
                  ("GFLOPJ", "Energy efficiency (GFLOP/J)"), ("P", "Average package power (W)")]
        for (key, lab), ax in zip(panels, axs.flat):
            for i, (K, d) in enumerate((K, sorted(sel(g, "threads", K=K), key=lambda x: x["threads"]))
                                       for K in sorted({x["K"] for x in th})):
                y = col(d, key)
                if key in ("T", "E"):
                    y = y / (col(d, "W") / d[0]["W"])        # normalise to the same total work
                ax.plot(col(d, "threads"), y, "-", color=C[i], lw=1.2)
                for x, yy in zip(d, y):
                    ax.plot(x["threads"], yy, "o", color=C[i], mfc="white" if x["all_thr"] else C[i])
                ax.plot([], [], "o-", color=C[i], label=f"I = {K/4:g} flop/B")
            if key == "GFLOPJ":
                ax.set_yscale("log")
            for j, (x0, x1, txt) in enumerate(regions):
                if j % 2 == 0:
                    ax.axvspan(x0, x1, color=FAINT, zorder=0, lw=0)
                ax.text((x0 + x1) / 2, 1.0, txt, transform=ax.get_xaxis_transform(), ha="center",
                        va="bottom", fontsize=8, color=MUTED)
            ax.set_xlim(0.5, max(tvals) + 0.5)
            ax.set_xticks(tvals); ax.xaxis.set_minor_locator(mt.NullLocator())
            ax.set(xlabel="Threads", ylabel=lab); ax.grid(axis="x", visible=False); nice_log(ax, "y")
        axs[0, 0].legend(loc="upper right")
        fig.suptitle(tt("Thread scaling (each point does the same total work)"), y=1.0)
        fig.tight_layout(h_pad=2.2); fig.savefig(P("fig6_threads.png")); plt.close(fig)

    # fig7: naive vs tiled matmul
    mm = [x for x in real if x["level"].startswith("matmul")]
    if mm:
        mm.sort(key=lambda x: (x["level"] != "matmul_naive", x["K"]))
        names = [x["name"].replace("naive mm", "naive").replace("tiled ", "") for x in mm]
        per = [("T", 1, "Time per multiply (s)"), ("E", 1, "Energy per multiply (J)"),
               ("GFLOPJ", 0, "Energy efficiency (GFLOP/J)")]
        fig, axs = plt.subplots(1, 3, figsize=(11, 3.8))
        for ax, (key, per_rep, lab) in zip(axs, per):
            v = [x[key] / x["reps"] if per_rep else x[key] for x in mm]
            bars = ax.bar(names, v, color=C[0], width=0.62)
            for b, x, y in zip(bars, mm, v):
                if x["all_thr"]:
                    b.set_facecolor("white"); b.set_edgecolor(C[0]); b.set_hatch("////")
                ax.text(b.get_x() + b.get_width() / 2, y, f"{y:.2f}" + ("*" if x["all_thr"] else ""),
                        ha="center", va="bottom", fontsize=8.5, color=INK)
            ax.set(ylabel=lab); ax.set_ylim(0, max(v) * 1.15); ax.grid(axis="x", visible=False)
        n0 = mm[0]
        gain = max(x["GFLOPJ"] for x in mm) / n0["GFLOPJ"]
        axs[2].set_title(f"best tiled = {gain:.1f}x naive", fontsize=9)
        axs[0].set_title(f"n = {int(n0['n'])}, {n0['threads']} threads", fontsize=9)
        fig.suptitle(tt("Data reuse in a real kernel: naive vs tiled matmul"), y=1.03)
        if any(x["all_thr"] for x in mm):
            fig.text(0.01, -0.04, "* hatched: every repeat was thermally throttled (kept for reference; "
                     "biased slow / low-power).", fontsize=7.5, color=MUTED)
        fig.tight_layout(); fig.savefig(P("fig7_matmul_reuse.png")); plt.close(fig)

    # fig8: energy breakdown (fitted constants x measured W, Q, T)
    targets = [0.25, 1, 4, 16, 64]
    pick = [min(s, key=lambda x: abs(np.log(x["I"] / t))) for t in targets]
    pick = [x for t, x in zip(targets, pick) if abs(np.log(x["I"] / t)) < 0.05]
    brk = []
    if pick:
        for x in pick:
            ef, em, e0 = m.eps_f * x["W"], m.eps_m * x["Q"], m.pi0 * x["T"]
            brk.append(dict(I=x["I"], flops=ef / x["W"] * 1e12, mem=em / x["W"] * 1e12,
                            const=e0 / x["W"] * 1e12, measured=x["E"] / x["W"] * 1e12))
        fig, axs = plt.subplots(1, 2, figsize=(10, 4))
        labs = [f"{b['I']:g}" for b in brk]
        comps = [("flops", r"$E_{flops}=W\,\epsilon_{flop}$", C[0]), ("mem", r"$E_{mem}=Q\,\epsilon_{mem}$", C[1]),
                 ("const", r"$E_0=\pi_0\,T$", C[3])]
        for ax, share in zip(axs, (False, True)):
            bottom = np.zeros(len(brk))
            for k, lab, c in comps:
                tot = np.array([b["flops"] + b["mem"] + b["const"] for b in brk])
                v = np.array([b[k] for b in brk]) / (tot / 100 if share else 1)
                ax.bar(labs, v, bottom=bottom, color=c, width=0.62, label=lab, edgecolor="white", lw=1)
                if share:
                    for i, (vv, bb) in enumerate(zip(v, bottom)):
                        if vv >= 6:
                            ax.text(i, bb + vv / 2, f"{vv:.0f}%", ha="center", va="center", fontsize=8, color="white")
                bottom += v
            if not share:
                meas = [b["measured"] for b in brk]
                ax.plot(labs, meas, "_", color=INK, ms=22, mew=2, ls="none", label="measured E/W")
                for i, (bt, mv) in enumerate(zip(bottom, meas)):
                    ax.text(i, max(bt, mv) * 1.02, f"{mv:.0f}", ha="center", va="bottom", fontsize=8, color=INK)
                ax.set(ylabel="Energy per flop (pJ/flop)", title="Absolute")
                ax.set_ylim(0, max(bottom.max(), max(meas)) * 1.12)
                ax.legend(loc="upper right")
            else:
                ax.set(ylabel="Share of total energy (%)", title="Share", ylim=(0, 100))
            ax.set_xlabel("Arithmetic intensity I (flop/byte)"); ax.grid(axis="x", visible=False)
        fig.suptitle(tt("Where the energy goes (fitted model, Exp 1 points)"), y=1.02)
        fig.tight_layout(); fig.savefig(P("fig8_energy_breakdown.png")); plt.close(fig)

    # fig9: model vs measured
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.3))
    for ax, key, f, lab in ((axs[0], "E", m.E, "energy (J)"), (axs[1], "T", m.T, "time (s)")):
        meas = col(s, key)
        ax.loglog(meas, f(W, Q), "o", color=C[0], label="Exp 1, uncapped model")
        if key == "T":
            ax.loglog(meas, f(W, Q, True), "o", color=C[2], mfc="white", label="Exp 1, capped model")
        for x in real:
            ax.plot(x[key], x[key + "_model"], x["marker"], color=INK, mfc="white" if x["all_thr"] else INK,
                    ls="none", label=x["name"])
        allv = np.r_[meas, f(W, Q), [x[key] for x in real], [x[key + "_model"] for x in real]]
        lo, hi = allv.min() / 1.5, allv.max() * 1.5
        ax.plot([lo, hi], [lo, hi], color=MUTED, lw=1, zorder=0)
        ax.set(xlim=(lo, hi), ylim=(lo, hi), xlabel=f"Measured {lab}", ylabel=f"Model {lab}")
        ek = "energy" if key == "E" else "time"
        txt = f"Exp 1 error: median {err[ek]['median']:.1f}%, max {err[ek]['max']:.1f}%"
        if key == "T":
            txt += f"\ncapped: median {err['time_capped']['median']:.1f}%, max {err['time_capped']['max']:.1f}%"
        ax.text(0.03, 0.97, txt, transform=ax.transAxes, va="top", fontsize=8, color=INK)
        ax.set_aspect("equal", adjustable="box"); nice_log(ax)
    h, l_ = axs[1].get_legend_handles_labels()
    l_ = [x + (" (throttled)" if any(r["all_thr"] and r["name"] == x for r in real) else "") for x in l_]
    fig.suptitle(tt("Model vs measurement (y = x line)"), y=1.0)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.legend(h, l_, loc="lower center", ncol=4, fontsize=8); fig.savefig(P("fig9_model_fit.png")); plt.close(fig)

    # ================================================================= summary
    verdict_rth = m.B_tau > m.B_eps_hat
    verdict = ("B_tau > B_eps_hat -> time-efficiency implies energy-efficiency; race-to-halt works."
               if verdict_rth else
               "B_eps_hat > B_tau -> balance gap: kernels with B_tau < I < B_eps_hat are compute-bound in "
               "time but memory-bound in energy; race-to-halt is NOT sufficient.")
    L = [f"=== {tag or os.path.basename(a.results)} ===", "", "Throttling:"] + drop_lines + ["",
         "=== Fitted machine parameters (Exp 1, all cores, data in DRAM) ===",
         f"energy measured           : package{' + DRAM' if any(r['E_dram_J'] >= 0 for r in rows) else ' only (no DRAM domain)'}",
         f"sustained peak            : {m.peak_f/1e9:.1f} GFLOP/s (double)",
         f"sustained bandwidth       : {m.peak_b/1e9:.1f} GB/s",
         f"eps_flop                  : {m.eps_f*1e12:.1f} pJ/flop",
         f"eps_mem                   : {m.eps_m*1e12:.1f} pJ/byte",
         f"pi0 (constant power)      : {m.pi0:.2f} W" + (f"   (idle package power {idle_W:.2f} W)" if idle_W else ""),
         f"eps0 = pi0*tau_flop       : {m.eps0*1e12:.1f} pJ/flop",
         f"time balance   B_tau      : {m.B_tau:.2f} flop/byte",
         f"energy balance B_eps      : {m.B_eps:.2f} flop/byte  (ignoring pi0)",
         f"effective B_eps_hat       : {m.B_eps_hat:.2f} flop/byte  (incl. pi0; half-max of arch line)",
         f"eta_flop                  : {m.eta:.3f}",
         f"peak energy efficiency    : {m.peak_fj/1e9:.2f} GFLOP/J  (model asymptote)",
         f"max measured power        : {m.P_max:.1f} W  -> delta_pi = {m.dpi:.1f} W",
         f"uncapped model peak power : {mp.max():.1f} W (at I = B_tau)",
         "", "Model error on Exp 1 (|model-measured|/measured):",
         f"  energy  uncapped: median {err['energy']['median']:.1f}%, max {err['energy']['max']:.1f}%"
         f"   capped: median {err['energy_capped']['median']:.1f}%, max {err['energy_capped']['max']:.1f}%",
         f"  time    uncapped: median {err['time']['median']:.1f}%, max {err['time']['max']:.1f}%"
         f"   capped: median {err['time_capped']['median']:.1f}%, max {err['time_capped']['max']:.1f}%",
         f"  power   uncapped: median {err['power']['median']:.1f}%, max {err['power']['max']:.1f}%"
         f"   capped: median {err['power_capped']['median']:.1f}%, max {err['power_capped']['max']:.1f}%",
         "  points near the corner (B_tau/4..4*B_tau), % below the uncapped roof: " +
         ", ".join(f"I={i:g}: {d:.0f}%" for i, d in corner),
         "", "Verdict: " + verdict,
         "", "=== Data-movement energy by level (Exp 2; eps_flop and pi0 held fixed; INCLUSIVE upper bounds) ==="]
    for x in lv:
        L.append(f"  {x['level']:<5} {x['pJ_per_B']:7.1f} pJ/B   max {x['max_GBs']:6.1f} GB/s   "
                 f"configs used {x['n_configs_used']}/{x['n_configs']}"
                 + (f"  (excluded K={x['excluded_K']}: all repeats throttled)" if x["excluded_K"] else ""))
    L += ["", "=== Real kernels (Exp 4) vs model (measured Q) ===",
          f"  {'kernel':<12}{'I':>6}{'GFLOP/s':>9}{'GFLOP/J':>9}{'T meas':>9}{'T model':>9}{'err':>8}"
          f"{'E meas':>9}{'E model':>9}{'err':>8}{'cap err':>9}{'err|Tmeas':>10}"]
    for x in real:
        L.append(f"  {x['name']:<12}{x['I']:6.2f}{x['GFLOPs']:9.1f}{x['GFLOPJ']:9.3f}{x['T']:9.3f}{x['T_model']:9.3f}"
                 f"{x['T_err']:7.0f}%{x['E']:9.1f}{x['E_model']:9.1f}{x['E_err']:7.0f}%{x['E_err_cap']:8.0f}%{x['E_err_Tmeas']:9.0f}%"
                 + ("  (all repeats throttled)" if x["all_thr"] else ""))
    if real:
        L.append("  (model = roofline bound; 'err|Tmeas' = energy model evaluated with the measured time)")
    if mm:
        L.append(f"  tiling gain (best tiled vs naive, GFLOP/J): {gain:.2f}x")
    L += ["", "=== Energy breakdown (pJ/flop) ==="]
    for b in brk:
        tot = b["flops"] + b["mem"] + b["const"]
        L.append(f"  I={b['I']:<6g} flops {b['flops']:7.1f}  mem {b['mem']:7.1f}  const {b['const']:7.1f}"
                 f"  (const share {100*b['const']/tot:4.1f}%)  measured {b['measured']:.1f}")
    L += ["", "=== Thread scaling (Exp 3) ==="]
    for t in thr_res:
        L.append(f"  I={t['I']:g} flop/B: fastest at {t['fastest']} threads, most energy-efficient at "
                 f"{t['most_efficient']} threads ({t['best_GFLOPJ']:.2f} GFLOP/J vs {t['GFLOPJ_at_fastest']:.2f} at fastest)")
    if not thr_res:
        L.append("  (no Exp 3 data)")
    text = "\n".join(L) + "\n"
    open(P("summary.txt"), "w").write(text)

    J = dict(tag=tag, source=os.path.abspath(a.results), flags=flags, idle_W=idle_W,
             energy_domain="package+dram" if any(r["E_dram_J"] >= 0 for r in rows) else "package",
             throttled_rows={e: sum(r["throttled"] for r in rows if r["exp"] == e) for e in exps},
             rows={e: sum(1 for r in rows if r["exp"] == e) for e in exps},
             params=dict(peak_GFLOPs=m.peak_f / 1e9, peak_GBs=m.peak_b / 1e9, eps_flop_pJ=m.eps_f * 1e12,
                         eps_mem_pJ_per_B=m.eps_m * 1e12, pi0_W=m.pi0, eps0_pJ=m.eps0 * 1e12,
                         B_tau=m.B_tau, B_eps=m.B_eps, B_eps_hat=m.B_eps_hat, eta_flop=m.eta,
                         peak_GFLOPJ=m.peak_fj / 1e9, P_max_W=m.P_max, delta_pi_W=m.dpi,
                         P_model_max_uncapped_W=float(mp.max())),
             verdict="race-to-halt" if verdict_rth else "balance-gap", verdict_text=verdict,
             model_error_pct=err, corner_below_roof_pct=[dict(I=i, pct=d) for i, d in corner],
             exp1=[dict(K=x["K"], I=x["I"], GFLOPs=x["GFLOPs"], GBs=x["GBs"], GFLOPJ=x["GFLOPJ"], P=x["P"])
                   for x in s],
             levels=lv,
             real=[{k: x[k] for k in ("level", "K", "name", "I", "W", "Q", "T", "E", "GFLOPs", "GFLOPJ", "P",
                                      "T_model", "E_model", "T_err", "E_err", "T_err_cap", "E_err_cap",
                                      "E_model_Tmeas", "E_err_Tmeas",
                                      "all_thr", "n_thr", "n_rep")} for x in real],
             breakdown=brk, threads=thr_res)
    json.dump(J, open(P("summary.json"), "w"), indent=1, default=float)

    with open(P("results_summary.csv"), "w", newline="") as f:
        keys = ["exp", "level", "K", "threads", "n", "reps", "W", "Q", "T", "E", "I", "GFLOPs", "GBs",
                "GFLOPJ", "P", "n_rep", "n_thr", "all_thr"]
        w = csv.DictWriter(f, keys, extrasaction="ignore"); w.writeheader(); w.writerows(g)
    print(text)
    print(f"Wrote figures, summary.txt, summary.json, results_summary.csv -> {out}")


if __name__ == "__main__":
    main()
