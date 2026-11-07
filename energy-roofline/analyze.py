#!/usr/bin/env python3
"""analyze.py - fit the energy-roofline model (Choi et al. 2013/2014) to results.csv
and produce all plots + summary.txt.

Model:
  T = max(W*tau_flop, Q*tau_mem)
  E = W*eps_flop + Q*eps_mem + pi0*T
Fit (paper eq. 9):  E/W = eps_flop + eps_mem*(Q/W) + pi0*(T/W)   (non-negative least squares)
"""
import sys, numpy as np, pandas as pd, matplotlib, matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import nnls

C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]   # categorical slots 1-4
INK, MUTED = "#222222", "#888888"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6,
                     "lines.linewidth": 2, "savefig.dpi": 160, "savefig.bbox": "tight"})

df = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else "results.csv")
if (df.E_pkg_J < 0).all():
    sys.exit("No energy data (E_pkg_J = -1). RAPL was not readable - see README.")
# total energy = package (+ DRAM if the platform exposes it)
df["E"] = df.E_pkg_J + df.E_dram_J.clip(lower=0)
has_dram = (df.E_dram_J >= 0).any()
g = (df.groupby(["exp", "level", "K", "threads"], as_index=False)
       .agg(n=("n", "first"), W=("W", "median"), Q=("Q", "median"),
            T=("time_s", "median"), E=("E", "median"), Estd=("E", "std")))
g["I"] = g.W / g.Q
g["GFLOPs"] = g.W / g["T"] / 1e9
g["GBs"] = g.Q / g["T"] / 1e9
g["GFLOPJ"] = g.W / g.E / 1e9
g["P"] = g.E / g["T"]

# ---------------- Exp 1: intensity sweep -> fit -----------------
s = g[(g.exp == "intensity")].sort_values("I")
A = np.c_[np.ones(len(s)), s.Q / s.W, s["T"] / s.W]
(eps_f, eps_m, pi0), _ = nnls(A, (s.E / s.W).values)
peak_f = s.GFLOPs.max() * 1e9                 # sustained peak flop/s
peak_b = s.GBs.max() * 1e9                    # sustained bandwidth B/s
tau_f, tau_m = 1 / peak_f, 1 / peak_b
B_tau = tau_m / tau_f
B_eps = eps_m / eps_f

def model(I):
    I = np.asarray(I, float)
    t_per_flop = np.maximum(tau_f, tau_m / I)
    e_per_flop = eps_f + eps_m / I + pi0 * t_per_flop
    return 1 / t_per_flop, 1 / e_per_flop, e_per_flop / t_per_flop   # flop/s, flop/J, W

# effective energy balance: intensity where flop/J reaches half of its max (incl. pi0)
Igrid = np.logspace(-3, 4, 20000)
fj = model(Igrid)[1]
B_eps_hat = Igrid[np.argmax(fj >= 0.5 * fj[-1])]
eta = eps_f / (eps_f + pi0 * tau_f)
pred_E = s.W * model(s.I)[1] ** -1
err_E = (pred_E - s.E) / s.E
err_T = (s.W / model(s.I)[0] - s["T"]) / s["T"]

# ---------------- Exp 2: cache levels -----------------
lv_rows = []
r = g[g.exp == "reuse"]
for lv in ["L1", "L2", "L3", "DRAM"]:
    d = r[r.level == lv]
    if d.empty: continue
    resid = d.E - eps_f * d.W - pi0 * d["T"]          # energy left for data movement
    eps_lv = max(float((resid * d.Q).sum() / (d.Q ** 2).sum()), 0)
    lv_rows.append((lv, eps_lv * 1e12, d.GBs.max()))
lv_df = pd.DataFrame(lv_rows, columns=["level", "pJ_per_byte", "max_GBs"])

# ---------------- plots -----------------
Ip = np.logspace(np.log10(s.I.min() / 2), np.log10(s.I.max() * 2), 400)
mf, mj, mp = model(Ip)

def vlines(ax):
    ax.axvline(B_tau, color=MUTED, ls="--", lw=1)
    ax.text(B_tau, ax.get_ylim()[1], f" B_τ={B_tau:.2f}", va="top", fontsize=8, color=INK)
    ax.axvline(B_eps_hat, color=MUTED, ls=":", lw=1)
    ax.text(B_eps_hat, ax.get_ylim()[0], f" B̂_ε={B_eps_hat:.2f}", va="bottom", fontsize=8, color=INK)

fig, ax = plt.subplots(figsize=(6, 4))
ax.loglog(Ip, mf / 1e9, color=C[1], label="model (roofline)")
ax.loglog(s.I, s.GFLOPs, "o", ms=6, color=C[0], label="measured")
ax.set(xlabel="Arithmetic intensity (flop/byte)", ylabel="Performance (GFLOP/s)",
       title="Time roofline"); vlines(ax); ax.legend(frameon=False)
fig.savefig("fig1_roofline.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(6, 4))
ax.loglog(Ip, mj / 1e9, color=C[1], label="model (arch line)")
ax.loglog(s.I, s.GFLOPJ, "o", ms=6, color=C[0], label="measured")
ax.set(xlabel="Arithmetic intensity (flop/byte)", ylabel="Energy efficiency (GFLOP/J)",
       title="Energy roofline (arch line)"); vlines(ax); ax.legend(frameon=False)
fig.savefig("fig2_archline.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(6, 4))
ax.semilogx(Ip, mp, color=C[1], label="model")
ax.semilogx(s.I, s.P, "o", ms=6, color=C[0], label="measured")
ax.axhline(pi0, color=MUTED, lw=1); ax.text(Ip[0], pi0, " constant power π₀", va="bottom", fontsize=8)
ax.set(xlabel="Arithmetic intensity (flop/byte)", ylabel="Average power (W)",
       title="Powerline"); ax.set_ylim(bottom=0); vlines(ax); ax.legend(frameon=False)
fig.savefig("fig3_powerline.png"); plt.close(fig)

if not lv_df.empty:
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    ax[0].bar(lv_df.level, lv_df.pJ_per_byte, color=C[0], width=0.6)
    for i, v in enumerate(lv_df.pJ_per_byte): ax[0].text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=9)
    ax[0].set(ylabel="Energy per byte (pJ/B)", title="Data-movement energy by level")
    ax[1].bar(lv_df.level, lv_df.max_GBs, color=C[0], width=0.6)
    for i, v in enumerate(lv_df.max_GBs): ax[1].text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=9)
    ax[1].set(ylabel="Bandwidth (GB/s)", title="Sustained bandwidth by level")
    fig.tight_layout(); fig.savefig("fig4_data_reuse.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    for i, lv in enumerate(lv_df.level):
        d = r[r.level == lv].sort_values("I")
        ax.loglog(d.I, d.GFLOPJ, "o-", ms=6, color=C[i], label=lv)
    ax.set(xlabel="Arithmetic intensity (flop/byte)", ylabel="GFLOP/J",
           title="Energy efficiency vs intensity, by data location"); ax.legend(frameon=False)
    fig.savefig("fig5_reuse_archlines.png"); plt.close(fig)

t = g[g.exp == "threads"]
if not t.empty:
    fig, axs = plt.subplots(2, 2, figsize=(9, 6.5))
    for (col, lab), ax in zip([("T", "Time (s, per run)"), ("E", "Energy (J, per run)"),
                               ("GFLOPJ", "GFLOP/J"), ("P", "Average power (W)")], axs.flat):
        for i, K in enumerate(sorted(t.K.unique())):
            d = t[t.K == K].sort_values("threads")
            y = d[col] / (d.W / d.W.iloc[0]) if col in ("T", "E") else d[col]  # normalise to same work
            ax.plot(d.threads, y, "o-", ms=6, color=C[i], label=f"I={K/4:g} flop/B")
        ax.set(xlabel="Threads", ylabel=lab); ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    axs[0, 0].legend(frameon=False)
    fig.suptitle("Thread scaling (same total work per point)")
    fig.tight_layout(); fig.savefig("fig6_threads.png"); plt.close(fig)

# ---------------- summary -----------------
lines = [
 "=== Fitted machine parameters (Exp 1, all cores, data in DRAM) ===",
 f"energy measured           : package{' + DRAM' if has_dram else ' only (no DRAM domain)'}",
 f"sustained peak            : {peak_f/1e9:.1f} GFLOP/s (double)",
 f"sustained bandwidth       : {peak_b/1e9:.1f} GB/s",
 f"eps_flop                  : {eps_f*1e12:.1f} pJ/flop",
 f"eps_mem                   : {eps_m*1e12:.1f} pJ/byte",
 f"pi0 (constant power)      : {pi0:.2f} W",
 f"time balance   B_tau      : {B_tau:.2f} flop/byte",
 f"energy balance B_eps      : {B_eps:.2f} flop/byte  (ignoring pi0)",
 f"effective B_eps_hat       : {B_eps_hat:.2f} flop/byte  (incl. pi0; half-max of arch line)",
 f"eta_flop                  : {eta:.3f}   (share of per-flop energy that is not constant power)",
 f"peak energy efficiency    : {fj[-1]/1e9:.2f} GFLOP/J",
 f"model error, energy       : median {np.median(np.abs(err_E))*100:.1f}%, max {np.max(np.abs(err_E))*100:.1f}%",
 f"model error, time         : median {np.median(np.abs(err_T))*100:.1f}%, max {np.max(np.abs(err_T))*100:.1f}%",
 "",
 "Verdict: " + ("B_tau > B_eps_hat -> time-efficiency implies energy-efficiency; race-to-halt works."
               if B_tau > B_eps_hat else
               "B_eps_hat > B_tau -> balance gap: kernels with B_tau < I < B_eps_hat are compute-bound "
               "in time but memory-bound in energy; race-to-halt is NOT sufficient."),
 "", "=== Data movement energy by level (Exp 2; eps_flop and pi0 held fixed) ===",
 lv_df.to_string(index=False) if not lv_df.empty else "(no data)",
 "", "=== Thread scaling (Exp 3): energy-optimal thread count per intensity ==="]
if not t.empty:
    for K in sorted(t.K.unique()):
        d = t[t.K == K]
        best_e, best_t = d.loc[d.GFLOPJ.idxmax()], d.loc[d.GFLOPs.idxmax()]
        lines.append(f"I={K/4:g} flop/B: fastest at {int(best_t.threads)} threads, "
                     f"most energy-efficient at {int(best_e.threads)} threads "
                     f"({best_e.GFLOPJ:.2f} GFLOP/J)")
open("summary.txt", "w").write("\n".join(lines) + "\n")
g.to_csv("results_summary.csv", index=False)
print("\n".join(lines))
print("\nWrote fig1..fig6 *.png, summary.txt, results_summary.csv")
