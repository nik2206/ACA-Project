#!/usr/bin/env python3
"""compare.py - compare two or more fitted machines / settings (summary.json from analyze.py).

Usage:
  python3 compare.py A/summary.json B/summary.json [C/summary.json ...]
                     [--labels "turbo on" "turbo off" ...] --out DIR

Writes into DIR:
  comparison.md           markdown table of parameters (+ ratio column when there are two)
  cmp_roofline.png        overlaid time rooflines (model + measured Exp 1 points)
  cmp_archline.png        overlaid arch lines: absolute and normalised to each peak
  cmp_powerline.png       overlaid powerlines
  cmp_ratio.png           (two inputs only) B/A ratio of measured GFLOP/J and GFLOP/s per
                          intensity, plus real kernels and data levels
Works for any two settings of one machine (e.g. turbo on vs off) or for two machines.
"""
import argparse, json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import Model, C, INK, MUTED, nice_log, L_BTAU, L_BEPS   # same style and model code


def model_of(S):
    p = S["params"]
    return Model(p["eps_flop_pJ"] * 1e-12, p["eps_mem_pJ_per_B"] * 1e-12, p["pi0_W"],
                 p["peak_GFLOPs"] * 1e9, p["peak_GBs"] * 1e9, p.get("delta_pi_W"))


def fmt(v, d=2):
    if v is None or (isinstance(v, float) and v != v):
        return "-"
    return f"{v:.{d}f}" if isinstance(v, (int, float)) else str(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("summaries", nargs="+")
    ap.add_argument("--labels", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if len(a.summaries) < 2:
        sys.exit("need at least two summary.json files")
    if len(a.summaries) > len(C):
        sys.exit(f"at most {len(C)} inputs (one palette slot each)")
    S = [json.load(open(f)) for f in a.summaries]
    labels = a.labels or [s.get("tag") or os.path.basename(os.path.dirname(os.path.abspath(f)))
                          for s, f in zip(S, a.summaries)]
    if len(labels) != len(S):
        sys.exit("--labels must give one label per summary")
    os.makedirs(a.out, exist_ok=True)
    M = [model_of(s) for s in S]
    two = len(S) == 2

    # ------------------------------------------------------------ table
    P = lambda s, k: s["params"].get(k)
    rows = [("Sustained peak (GFLOP/s)", "peak_GFLOPs", 1), ("Sustained bandwidth (GB/s)", "peak_GBs", 1),
            ("ε_flop (pJ/flop)", "eps_flop_pJ", 1), ("ε_mem (pJ/B)", "eps_mem_pJ_per_B", 1),
            ("π₀ (W)", "pi0_W", 2), ("ε₀ = π₀·τ_flop (pJ/flop)", "eps0_pJ", 1),
            ("B_τ (flop/B)", "B_tau", 2), ("B_ε (flop/B)", "B_eps", 2), ("B̂_ε (flop/B)", "B_eps_hat", 2),
            ("η_flop", "eta_flop", 3), ("Peak energy efficiency (GFLOP/J)", "peak_GFLOPJ", 2),
            ("Max measured power (W)", "P_max_W", 1), ("Δπ = P_max − π₀ (W)", "delta_pi_W", 1),
            ("Uncapped model peak power (W)", "P_model_max_uncapped_W", 1)]
    hdr = "| Parameter | " + " | ".join(labels) + (f" | {labels[1]} / {labels[0]} |" if two else " |")
    md = [f"# Comparison: {' vs '.join(labels)}", "", hdr, "|" + "---|" * (len(S) + 1 + two)]
    for name, k, d in rows:
        vals = [P(s, k) for s in S]
        r = f"| {name} | " + " | ".join(fmt(v, d) for v in vals)
        if two:
            r += f" | {vals[1] / vals[0]:.2f}" if vals[0] and vals[1] is not None else " | -"
        md.append(r + " |")
    extra = [("Idle package power (W)", [s.get("idle_W") for s in S], 2),
             ("Energy model error, median / max (%)",
              [f"{s['model_error_pct']['energy']['median']:.1f} / {s['model_error_pct']['energy']['max']:.1f}" for s in S], 0),
             ("Time model error, median / max (%)",
              [f"{s['model_error_pct']['time']['median']:.1f} / {s['model_error_pct']['time']['max']:.1f}" for s in S], 0),
             ("Time error with power cap, median / max (%)",
              [f"{s['model_error_pct']['time_capped']['median']:.1f} / {s['model_error_pct']['time_capped']['max']:.1f}" for s in S], 0),
             ("Verdict", [f"{s['verdict']} (B_τ {'>' if s['params']['B_tau'] > s['params']['B_eps_hat'] else '<'} B̂_ε)" for s in S], 0),
             ("Throttled rows dropped", [f"{sum(s['throttled_rows'].values())} of {sum(s['rows'].values())}" for s in S], 0)]
    for name, vals, d in extra:
        md.append(f"| {name} | " + " | ".join(fmt(v, d) for v in vals) + (" | |" if two else " |"))

    lvls = [lv for lv in ["L1", "L2", "L3", "DRAM"] if all(any(x["level"] == lv for x in s.get("levels", [])) for s in S)]
    if lvls:
        md += ["", "**Data-movement energy by level (pJ/B, inclusive upper bounds)**", "",
               "| Level | " + " | ".join(labels) + (" | ratio |" if two else " |"), "|" + "---|" * (len(S) + 1 + two)]
        for lv in lvls:
            v = [next(x["pJ_per_B"] for x in s["levels"] if x["level"] == lv) for s in S]
            md.append(f"| {lv} | " + " | ".join(f"{x:.0f}" for x in v) + (f" | {v[1]/v[0]:.2f} |" if two else " |"))
    names = [x["name"] for x in S[0].get("real", []) if all(any(y["name"] == x["name"] for y in s.get("real", [])) for s in S)]
    if names:
        md += ["", "**Real kernels (GFLOP/s, GFLOP/J; * = all repeats throttled)**", "",
               "| Kernel | " + " | ".join(f"{l} GFLOP/s | {l} GFLOP/J" for l in labels)
               + (" | GFLOP/J ratio | speed ratio |" if two else " |"), "|" + "---|" * (2 * len(S) + 1 + 2 * two)]
        for n in names:
            v = [next(y for y in s["real"] if y["name"] == n) for s in S]
            r = f"| {n} | " + " | ".join(f"{y['GFLOPs']:.1f}{'*' if y['all_thr'] else ''} | {y['GFLOPJ']:.3f}{'*' if y['all_thr'] else ''}" for y in v)
            if two:
                r += f" | {v[1]['GFLOPJ']/v[0]['GFLOPJ']:.2f} | {v[1]['GFLOPs']/v[0]['GFLOPs']:.2f}"
            md.append(r + " |")
    pts = None
    if two:
        A = {x["K"]: x for x in S[0]["exp1"]}; B = {x["K"]: x for x in S[1]["exp1"]}
        pts = [(A[k]["I"], B[k]["GFLOPJ"] / A[k]["GFLOPJ"], B[k]["GFLOPs"] / A[k]["GFLOPs"]) for k in sorted(A) if k in B]
        if pts:
            md += ["", f"**Exp 1, measured {labels[1]} / {labels[0]}**", "", "| I (flop/B) | GFLOP/J ratio | GFLOP/s ratio |",
                   "|---|---|---|"] + [f"| {i:g} | {e:.2f} | {t:.2f} |" for i, e, t in pts]
    open(os.path.join(a.out, "comparison.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))

    # ------------------------------------------------------------ figures
    allI = [x["I"] for s in S for x in s["exp1"]]
    Ip = np.logspace(np.log10(min(allI) / 2), np.log10(max(allI) * 2), 600)

    def overlay(fname, key, ylab, title, curve, logy=True):
        fig, ax = plt.subplots(figsize=(6.6, 4.4))
        for i, (s, m, lab) in enumerate(zip(S, M, labels)):
            y = curve(m)
            (ax.loglog if logy else ax.semilogx)(Ip, y, color=C[i], lw=1.6, label=f"{lab}: model")
            ax.plot([x["I"] for x in s["exp1"]], [x[key] for x in s["exp1"]], "o", color=C[i], label=f"{lab}: measured")
            ax.axvline(m.B_tau, color=C[i], ls="--", lw=0.9)
            ax.axvline(m.B_eps_hat, color=C[i], ls=":", lw=0.9)
        ax.set(xlabel="Arithmetic intensity I (flop/byte)", ylabel=ylab, title=title)
        if not logy:
            ax.set_ylim(bottom=0)
        ax.plot([], [], color=MUTED, ls="--", lw=0.9, label=L_BTAU)
        ax.plot([], [], color=MUTED, ls=":", lw=0.9, label=L_BEPS)
        nice_log(ax)
        return fig, ax

    fig, ax = overlay("cmp_roofline.png", "GFLOPs", "Performance (GFLOP/s)", "Time rooflines",
                      lambda m: m.curves(Ip)[0] / 1e9)
    ax.legend(loc="lower right", ncol=1); fig.savefig(os.path.join(a.out, "cmp_roofline.png")); plt.close(fig)

    fig, ax = overlay("cmp_powerline.png", "P", "Average package power (W)", "Powerlines (uncapped model)",
                      lambda m: m.curves(Ip)[2], logy=False)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5)); fig.savefig(os.path.join(a.out, "cmp_powerline.png")); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4))
    for i, (s, m, lab) in enumerate(zip(S, M, labels)):
        for ax, norm in zip(axs, (1e9, m.peak_fj)):
            ax.loglog(Ip, m.curves(Ip)[1] / norm, color=C[i], lw=1.6, label=f"{lab}: model")
            ax.plot([x["I"] for x in s["exp1"]], [x["GFLOPJ"] * 1e9 / norm for x in s["exp1"]], "o", color=C[i],
                    label=f"{lab}: measured")
            ax.axvline(m.B_eps_hat, color=C[i], ls=":", lw=0.9)
    axs[0].set(ylabel="Energy efficiency (GFLOP/J)", title="Arch lines (absolute)")
    axs[1].set(ylabel="Fraction of own peak GFLOP/J", title="Arch lines (normalised to each peak)")
    axs[1].axhline(0.5, color=MUTED, lw=0.8)
    axs[1].text(Ip[0], 0.5, " half of peak: I = " + L_BEPS, va="bottom", fontsize=8, color=INK)
    for ax in axs:
        ax.set_xlabel("Arithmetic intensity I (flop/byte)"); nice_log(ax)
    axs[0].plot([], [], color=MUTED, ls=":", lw=0.9, label=L_BEPS)
    axs[0].legend(loc="lower right")
    fig.tight_layout(); fig.savefig(os.path.join(a.out, "cmp_archline.png")); plt.close(fig)

    if two and pts:
        fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw=dict(width_ratios=[1.1, 1]))
        I_, e_, t_ = map(np.array, zip(*pts))
        axs[0].semilogx(I_, e_, "o-", color=C[0], label="energy efficiency (GFLOP/J)")
        axs[0].semilogx(I_, t_, "o-", color=C[1], label="speed (GFLOP/s)")
        axs[0].axhline(1, color=MUTED, lw=1)
        for x, y in zip(I_, e_):
            axs[0].text(x, y * 1.03, f"{y:.1f}x", ha="center", va="bottom", fontsize=7.5, color=INK)
        axs[0].set(xlabel="Arithmetic intensity I (flop/byte)", ylabel=f"{labels[1]} / {labels[0]}",
                   title="Synthetic kernel (Exp 1)", ylim=(0, max(e_.max(), t_.max()) * 1.18))
        axs[0].legend(loc="upper right"); nice_log(axs[0], "x")
        cats, er, sr = [], [], []
        for n in names:
            v = [next(y for y in s["real"] if y["name"] == n) for s in S]
            cats.append(n + ("*" if v[0]["all_thr"] or v[1]["all_thr"] else ""))
            er.append(v[1]["GFLOPJ"] / v[0]["GFLOPJ"]); sr.append(v[1]["GFLOPs"] / v[0]["GFLOPs"])
        if cats:
            x = np.arange(len(cats)); w = 0.38
            axs[1].bar(x - w / 2, er, w, color=C[0], label="energy efficiency")
            axs[1].bar(x + w / 2, sr, w, color=C[1], label="speed")
            for xi, y in zip(x - w / 2, er):
                axs[1].text(xi, y, f"{y:.1f}x", ha="center", va="bottom", fontsize=7.5, color=INK)
            axs[1].axhline(1, color=MUTED, lw=1)
            axs[1].set_xticks(x); axs[1].set_xticklabels(cats, rotation=20, ha="right")
            axs[1].set(ylabel=f"{labels[1]} / {labels[0]}", title="Real kernels (Exp 4)",
                       ylim=(0, max(max(er), max(sr)) * 1.28))
            axs[1].grid(axis="x", visible=False); axs[1].legend(loc="upper center", ncol=2)
        else:
            axs[1].axis("off")
        fig.suptitle(f"{labels[1]} relative to {labels[0]} (measured; > 1 means {labels[1]} is better)", y=1.01)
        if any(c.endswith("*") for c in cats):
            fig.text(0.55, -0.06, "* every repeat thermally throttled in at least one setting", fontsize=7.5, color=MUTED)
        fig.tight_layout(); fig.savefig(os.path.join(a.out, "cmp_ratio.png")); plt.close(fig)
    print(f"\nWrote comparison.md and cmp_*.png -> {a.out}")


if __name__ == "__main__":
    main()
