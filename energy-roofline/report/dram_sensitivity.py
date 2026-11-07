#!/usr/bin/env python3
"""dram_sensitivity.py - how much missing DRAM energy would flip the race-to-halt verdict?

RAPL here measures the package only, so the fitted eps_mem is the CPU-side energy per byte (a
lower bound). We add an assumed DRAM-device energy x (pJ/B) to eps_mem, plus optionally a DRAM
background power d_pi0 (W) to pi0, and recompute B_eps and B_eps_hat. Time (tau_flop, tau_mem,
B_tau) is unaffected.

Race-to-halt holds iff B_eps_hat < B_tau  <=>  eta*B_eps < B_tau  <=>  eps_mem < B_tau*(eps_flop+eps0).

Usage: python3 report/dram_sensitivity.py [report/figures/turbo_on/summary.json report/figures/turbo_off/summary.json]
Writes report/figures/comparison/dram_sensitivity.png and dram_sensitivity.md.
"""
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from analyze import C, INK, MUTED   # same style

KECKLER = (253, 389)          # pJ/B, DRAM + interface + wire estimate quoted in paper 1, Sec. V-A
X = np.linspace(0, 1000, 1001)


def balances(p, x, d_pi0=0.0):
    ef, em = p["eps_flop_pJ"], p["eps_mem_pJ_per_B"] + x
    e0 = (p["pi0_W"] + d_pi0) / (p["peak_GFLOPs"] * 1e9) * 1e12
    eta, bt = ef / (ef + e0), p["B_tau"]
    a = eta * em / ef                                    # eta * B_eps
    bh = np.where(a >= bt, a, (a + (1 - eta) * bt) / (2 - eta))
    return em / ef, bh, bt * (ef + e0) - p["eps_mem_pJ_per_B"]   # B_eps, B_eps_hat, headroom x*


def main():
    files = sys.argv[1:] or [os.path.join(HERE, "figures", t, "summary.json") for t in ("turbo_on", "turbo_off")]
    S = [json.load(open(f)) for f in files]
    out = os.path.join(HERE, "figures", "comparison"); os.makedirs(out, exist_ok=True)

    md = ["| Setting | ε_mem fitted (pJ/B) | B_τ | Max extra DRAM energy keeping race-to-halt (pJ/B): +0 W | +1 W | +3 W | B̂_ε at +253 / +389 pJ/B |",
          "|---|---|---|---|---|---|---|"]
    fig, axs = plt.subplots(1, len(S), figsize=(5.4 * len(S), 4.2))
    for ax, s in zip(np.atleast_1d(axs), S):
        p = s["params"]
        be, bh, x0 = balances(p, X)
        _, bh3, x3 = balances(p, X, 3.0)
        x1 = balances(p, X, 1.0)[2]
        k = [float(balances(p, np.array([v]))[1][0]) for v in KECKLER]
        md.append(f"| {s.get('tag', '')} | {p['eps_mem_pJ_per_B']:.0f} | {p['B_tau']:.2f} | {x0:.0f} | {x1:.0f} | {x3:.0f} | "
                  f"{k[0]:.2f} / {k[1]:.2f} |")
        ax.axvspan(*KECKLER, color="#f1f1f1", lw=0, zorder=0)
        ax.text(sum(KECKLER) / 2, 0.97, "Keckler et al.\nDRAM+interface", transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=7.5, color=INK)
        ax.plot(X, be, color=C[1], label=r"$B_\epsilon$")
        ax.plot(X, bh, color=C[0], label=r"$\hat{B}_\epsilon$")
        ax.plot(X, bh3, color=C[0], ls="--", lw=1.1, label=r"$\hat{B}_\epsilon$, +3 W DRAM background")
        ax.axhline(p["B_tau"], color=MUTED, lw=1.2)
        ax.text(12, p["B_tau"], fr"$B_\tau$ = {p['B_tau']:.2f}", ha="left", va="bottom", fontsize=8, color=INK)
        ax.axvline(x0, color=C[0], lw=0.8, ls=":")
        ax.text(x0, 0.02, f" flips at +{x0:.0f} pJ/B ", transform=ax.get_xaxis_transform(), fontsize=8, color=INK,
                ha="left" if x0 < 700 else "right", va="bottom")
        ax.set(xlim=(0, 1000), ylim=(0, max(be.max(), p["B_tau"]) * 1.05),
               xlabel="Assumed extra DRAM energy (pJ/B)", ylabel="Balance point (flop/B)",
               title=fr"{s.get('tag', '')}: fitted $\epsilon_{{mem}}$ = {p['eps_mem_pJ_per_B']:.0f} pJ/B")
        ax.legend(loc="upper left", bbox_to_anchor=(0, 0.88), fontsize=7.5)
    fig.suptitle("DRAM energy sensitivity: race-to-halt holds while $\\hat{B}_\\epsilon$ < $B_\\tau$", y=1.02)
    fig.tight_layout(); fig.savefig(os.path.join(out, "dram_sensitivity.png")); plt.close(fig)
    open(os.path.join(out, "dram_sensitivity.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
