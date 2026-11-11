#!/usr/bin/env python3
"""viva_extras.py - three small analyses for the viva guide (no new measurements).

X1  Constant-power sweep: hold eps_flop, eps_mem and the peaks fixed, lower pi0 to 0 and
    recompute B_eps_hat. Where does race-to-halt (B_eps_hat < B_tau) stop holding?
    Closed form: B_eps_hat = B_tau  <=>  eps_mem = B_tau*(eps_flop + pi0*tau_flop)
                 =>  pi0* = (eps_mem/B_tau - eps_flop)/tau_flop   (no threshold if pi0* <= 0)
X2  Power-cap what-if (paper 2, Sec. V-D): turbo-on constants with dpi, dpi/2, dpi/4, dpi/8;
    the capped interval [B_tau-, B_tau+] (paper 2 eqs. 5-6); and a test of the cap model
    against turbo off, which is a real power bound reached by DVFS instead of by delay.
X3  (a) Tiling as a work-communication trade-off (paper 1 eq. 10) with f = 1 and
        m = Q_naive/Q_tiled from q_measured*.csv.
    (b) Turbo off vs turbo on under the energy-delay product, from the clean Exp 1 medians.

X1 and X2a are model what-ifs on fitted constants; X2b and X3 re-arrange measured data.

Usage (from energy-roofline/):  python3 report/viva_extras.py
Inputs : report/figures/{turbo_on,turbo_off}/summary.json and, read-only,
         data/sai-Victus-by-HP-Gaming-Laptop-15-fa1xxx/{results,run_flags,q_measured}[_turbo_off].csv
Outputs: report/figures/viva/{viva_extras.md, pi0_sweep.png, cap_whatif.png, edp_ratio.png}
"""
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from analyze import C, INK, MUTED, Model, load, aggregate, sel, read_csv   # no side effects on import

DATA = os.path.join(ROOT, "data", "sai-Victus-by-HP-Gaming-Laptop-15-fa1xxx")
FIG = os.path.join(HERE, "figures")
OUT = os.path.join(FIG, "viva")
SETTINGS = [("turbo on", "turbo_on", ""), ("turbo off", "turbo_off", "_turbo_off")]


def model_from(p, dpi=None):
    """analyze.Model from summary.json params (pJ -> J, GFLOP/s -> flop/s)."""
    return Model(p["eps_flop_pJ"] * 1e-12, p["eps_mem_pJ_per_B"] * 1e-12, p["pi0_W"],
                 p["peak_GFLOPs"] * 1e9, p["peak_GBs"] * 1e9, dpi)


def b_hat(ef, em, pi0, tau_f, bt):
    """Half-peak point of the arch line (fixed point I = B_eps_hat(I), paper 1 eq. 6)."""
    e0 = pi0 * tau_f
    eta = ef / (ef + e0)
    a = eta * em / ef
    return np.where(a >= bt, a, (a + (1 - eta) * bt) / (2 - eta))


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


# ---------------------------------------------------------------- X1
def x1(S, md):
    md += ["## X1. Constant-power sweep: does race-to-halt survive as π₀ → 0?", "",
           "ε_flop, ε_mem, peak flop/s and peak bandwidth held at their fitted values; only π₀ changes. "
           "Race-to-halt holds while B̂_ε < B_τ. Threshold π₀* = (ε_mem/B_τ − ε_flop)/τ_flop.", ""]
    rows = []
    fig, axs = plt.subplots(1, 2, figsize=(10.8, 4.0))
    for ax, (tag, s) in zip(axs, S):
        p = s["params"]
        ef, em = p["eps_flop_pJ"], p["eps_mem_pJ_per_B"]
        tau_f = 1e12 / (p["peak_GFLOPs"] * 1e9)              # ps per flop
        bt, pi0, idle = p["B_tau"], p["pi0_W"], s["idle_W"]
        star = (em / bt - ef) / tau_f                          # W
        x = np.linspace(0, 1.25 * pi0, 501)
        bh = b_hat(ef, em, x, tau_f, bt)
        chk = float(b_hat(ef, em, pi0, tau_f, bt))
        rows.append([tag, f"{pi0:.2f}", f"{idle:.2f}",
                     f"{star:.2f}" if star > 0 else "none (B_ε < B_τ)",
                     f"{float(b_hat(ef, em, idle, tau_f, bt)):.2f}", f"{float(b_hat(ef, em, 0.0, tau_f, bt)):.2f}",
                     f"{chk:.2f}", f"{bt:.2f}"])
        ax.plot(x, bh, color=C[0], label=r"$\hat{B}_\epsilon$ (half-peak point of the arch line)")
        ax.axhline(bt, color=MUTED, lw=1.2)
        ax.text(x[-1], bt, fr"$B_\tau$ = {bt:.2f}", ha="right", va="bottom", fontsize=8, color=INK)
        ax.axvline(pi0, color=C[1], lw=1, ls="--", label=fr"fitted $\pi_0$ = {pi0:.1f} W")
        ax.axvline(idle, color=C[2], lw=1, ls=":", label=f"idle package power = {idle:.2f} W")
        if star > 0:
            ax.axvline(star, color=INK, lw=0.8)
            ax.text(star, 0.04, fr" $\pi_0^*$ = {star:.1f} W", transform=ax.get_xaxis_transform(),
                    fontsize=8, color=INK)
            ax.axvspan(0, star, color="#f1f1f1", lw=0, zorder=0)
            ax.text(star / 2, 0.93, "balance gap:\nrace-to-halt fails", transform=ax.get_xaxis_transform(),
                    ha="center", va="top", fontsize=7.5, color=INK)
        ax.set(xlabel=r"constant power $\pi_0$ (W)", ylabel="flop/byte", title=tag, xlim=(0, x[-1]),
               ylim=(0, max(bt, bh.max()) * 1.18))
        ax.legend(loc="lower right", fontsize=7.5)
    fig.suptitle(r"X1: lowering $\pi_0$ with the other constants fixed", y=1.02)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "pi0_sweep.png"), dpi=130, bbox_inches="tight"); plt.close(fig)
    md += table(["Setting", "fitted π₀ (W)", "idle (W)", "threshold π₀* (W)", "B̂_ε at π₀ = idle",
                 "B̂_ε at π₀ = 0 (= B_ε)", "B̂_ε at fitted π₀ (check)", "B_τ"], rows)
    md += ["", "Turbo on has no threshold: B_ε (6.43) < B_τ (9.03), so even with π₀ = 0 the arch line reaches half "
           "its peak before the roofline corner, the situation paper 1 describes for its Intel CPU (§V-B). "
           "Turbo off flips below π₀* ≈ 2.2 W, which is below its idle package power (2.71 W): the constant "
           "power would have to fall below what the chip draws doing nothing.", ""]
    return rows


# ---------------------------------------------------------------- X2
def interval(p):
    pf = p["eps_flop_pJ"] * 1e-12 * p["peak_GFLOPs"] * 1e9      # W
    pm = p["eps_mem_pJ_per_B"] * 1e-12 * p["peak_GBs"] * 1e9    # W
    d, bt = p["delta_pi_W"], p["B_tau"]
    bplus = bt * max(1.0, pm / (d - pf)) if d > pf else float("inf")
    bminus = bt * min(1.0, (d - pm) / pf)
    return pf, pm, bminus, bplus


def x2(S, G, md):
    md += ["## X2. Power-cap what-if, and paper 2's throttle model against turbo off", ""]
    rows = []
    for tag, s in S:
        p = s["params"]
        pf, pm, bm, bp = interval(p)
        e1 = s["exp1"]
        P = np.array([x["P"] for x in e1])
        rows.append([tag, f"{pf:.1f}", f"{pm:.1f}", f"{p['pi0_W']:.2f}", f"{p['delta_pi_W']:.1f}",
                     f"{p['pi0_W'] + pf:.1f}", f"{p['pi0_W'] + pm:.1f}", f"{p['pi0_W'] + pf + pm:.1f}",
                     f"[{bm:.2f}, {bp:.1f}]", f"{P.min():.1f}–{P.max():.1f} W ({P.min() / P.max():.2f}–1.00)",
                     f"{p['pi0_W'] / p['P_max_W']:.2f}"])
    md += ["### Powerline numbers and the capped interval (paper 2 eqs. 5–7)", ""]
    md += table(["Setting", "π_flop (W)", "π_mem (W)", "π₀ (W)", "Δπ (W)", "π₀+π_flop (W)", "π₀+π_mem (W)",
                 "uncapped peak π₀+π_flop+π_mem (W)", "[B_τ⁻, B_τ⁺] (flop/B)", "Exp 1 power range (÷ P_max)",
                 "π₀/(π₀+Δπ)"], rows)
    md += ["", "π_flop = ε_flop/τ_flop, π_mem = ε_mem/τ_mem. Inside [B_τ⁻, B_τ⁺] the capped model holds power at "
           "π₀ + Δπ. Paper 2 reports 0.65–1.15 of π₁ + Δπ within a platform; its π₁/(π₁ + Δπ) exceeds 0.5 on 7 of 12.", ""]

    # (a) turbo-on what-if curves
    p_on = S[0][1]["params"]
    I = np.logspace(np.log2(0.125), np.log2(256), 400, base=2)
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.0))
    caprows = []
    for k, c in zip((1, 2, 4, 8), C):
        m = model_from(p_on, p_on["delta_pi_W"] / k)
        fs, fj, pw = m.curves(I, capped=True)
        lab = "Δπ" if k == 1 else f"Δπ/{k}"
        lab_tex = r"$\Delta\pi$" if k == 1 else fr"$\Delta\pi/{k}$"
        axs[0].plot(I, fs / 1e9, color=c, label=lab_tex + f" ({p_on['delta_pi_W'] / k:.1f} W)")
        axs[1].plot(I, fj / 1e9, color=c, label=lab_tex)
        axs[2].plot(I, pw, color=c, label=lab_tex)
        r = [lab, f"{p_on['delta_pi_W'] / k:.1f}", f"{p_on['pi0_W'] + p_on['delta_pi_W'] / k:.1f}"]
        for Ii in (0.25, 4, 64):
            a, b, _ = m.curves(np.array([Ii]), capped=True)
            r += [f"{a[0] / 1e9:.1f} / {b[0] / 1e9:.2f}"]
        caprows.append(r)
    m0 = model_from(p_on)
    fs0, fj0, pw0 = m0.curves(I)
    for ax, y in zip(axs, (fs0 / 1e9, fj0 / 1e9, pw0)):
        ax.plot(I, y, color=MUTED, lw=1, ls="--", label="uncapped")
    # measured turbo off for comparison
    off = sorted(G["turbo off"], key=lambda x: x["I"])
    Io = np.array([x["I"] for x in off])
    axs[0].plot(Io, [x["GFLOPs"] for x in off], "o", color=INK, ms=4, label="measured, turbo off")
    axs[1].plot(Io, [x["GFLOPJ"] for x in off], "o", color=INK, ms=4, label="measured, turbo off")
    axs[2].plot(Io, [x["P"] for x in off], "o", color=INK, ms=4, label="measured, turbo off")
    for ax, yl, t in zip(axs, ("GFLOP/s", "GFLOP/J", "power (W)"), ("speed", "energy efficiency", "power")):
        ax.set_xscale("log", base=2); ax.set(xlabel="intensity I (flop/byte)", ylabel=yl, title=t)
        if t != "power":
            ax.set_yscale("log", base=2)
        ax.legend(fontsize=7, loc="lower right" if t != "power" else "upper right")
    axs[2].set_ylim(0, None)
    fig.suptitle("X2: paper 2's throttle model on the turbo-on constants (lines) vs the real turbo-off setting (dots)", y=1.02)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "cap_whatif.png"), dpi=130, bbox_inches="tight"); plt.close(fig)

    p_off = S[1][1]["params"]
    bound = p_off["P_max_W"]
    meas = {}
    for x in off:
        meas[x["K"] / 4] = x
    mrow = ["measured turbo off (DVFS)", "–", f"{bound:.1f} (max measured)"]
    for Ii in (0.25, 4, 64):
        x = meas[Ii]
        mrow += [f"{x['GFLOPs']:.1f} / {x['GFLOPJ']:.2f}"]
    caprows.append(mrow)
    md += ["### (a) Cutting the usable power on the turbo-on constants (paper 2 Fig. 6–7 on our chip)", ""]
    md += table(["Cap", "Δπ (W)", "power bound π₀+Δπ (W)", "I = 0.25: GFLOP/s / GFLOP/J", "I = 4",
                 "I = 64"], caprows)
    feasible = bound - p_on["pi0_W"]
    md += ["", f"### (b) Turbo off as a real power bound", "",
           f"Turbo off never drew more than {bound:.1f} W in Exp 1. The turbo-on capped model cannot reach that bound at "
           f"all: its constant power alone is {p_on['pi0_W']:.2f} W, so the required Δπ would be {feasible:.1f} W "
           f"(negative). The nearest feasible case in the table, Δπ/8 (bound {p_on['pi0_W'] + p_on['delta_pi_W'] / 8:.1f} W), "
           "is still above the turbo-off power and is slower and far less efficient than what turbo off actually "
           "achieved. Paper 2's cap delays operations at fixed energy per operation with π₁ fixed; the real CPU met "
           "a lower power by moving to a lower frequency and voltage, which cut ε_flop, ε_mem and π₀ together "
           "(all about 3×). Paper 2 suspected the same mechanism on the Arndale GPU (§V-C).", ""]
    return rows


# ---------------------------------------------------------------- X3
def x3(S, G, md):
    md += ["## X3. Tiling as a work–communication trade-off, and turbo under the energy-delay product", ""]
    md += ["### (a) Greenup condition (paper 1 eq. 10) applied to tiling", "",
           "Baseline = naive matmul (W, Q); new = tiled (f·W, Q/m) with f = 1 (same flops). Paper 1's condition for a "
           "greenup (stated for π₀ = 0): f < 1 + ((m − 1)/m)·B_ε/I, with I the baseline intensity. With f = 1 the "
           "condition always holds; the bound is the extra work the tiled version could afford and still save energy.", ""]
    rows = []
    for tag, s in S:
        p = s["params"]
        qm = read_csv(os.path.join(DATA, "q_measured" + dict(SETTINGS_SFX)[tag] + ".csv"))
        qn = float(next(r["Q_measured_per_rep"] for r in qm if r["kernel"] == "matmul_naive"))
        real = {r["name"]: r for r in s["real"]}
        naive = real["naive mm"]
        In = naive["I"]
        for r in qm:
            if r["kernel"] != "matmul_tiled":
                continue
            b = int(r["tile"]); m = qn / float(r["Q_measured_per_rep"])
            t = real[f"tiled b={b}"]
            bound = 1 + (m - 1) / m * p["B_eps"] / In
            g_model = naive["E_model"] / t["E_model"]
            g_model_tm = naive["E_model_Tmeas"] / t["E_model_Tmeas"]
            g_meas = t["GFLOPJ"] / naive["GFLOPJ"]
            rows.append([tag, b, f"{m:.1f}", f"{In:.2f}", f"{bound:.1f}", f"{g_model:.2f}", f"{g_model_tm:.2f}",
                         f"{g_meas:.2f}" + (" *" if t["all_thr"] else "")])
    md += table(["Setting", "tile b", "m = Q_naive/Q_tiled", "I naive", "max extra work f (π₀ = 0)",
                 "greenup, model (roofline T)", "greenup, model (measured T)", "greenup, measured"], rows)
    md += ["", "\\* every repeat thermally throttled (turbo on, b = 64 and 128).", ""]
    md += ["For a baseline already compute-bound in time (I ≥ B_τ), paper 1's limit is f < 1 + B_ε/B_τ: "
           + ", ".join(f"{tag} {1 + s['params']['B_eps'] / s['params']['B_tau']:.2f}" for tag, s in S)
           + ". On our turbo-on machine, an algorithm that is already fast may spend at most 71% more flops to "
           "remove all its DRAM traffic and still save energy; with turbo off, 139%.", ""]

    # (b) EDP
    md += ["### (b) Turbo off / turbo on under energy, time and energy-delay product (clean Exp 1 medians)", ""]
    on = {x["K"] / 4: x for x in G["turbo on"]}
    off = {x["K"] / 4: x for x in G["turbo off"]}
    Is = sorted(set(on) & set(off))
    rows, rt, re_, red = [], [], [], []
    for Ii in Is:
        a, b = on[Ii], off[Ii]
        tr = (b["T"] / b["W"]) / (a["T"] / a["W"])
        er = (b["E"] / b["W"]) / (a["E"] / a["W"])
        rt.append(tr); re_.append(er); red.append(tr * er)
        rows.append([f"{Ii:g}", f"{tr:.2f}", f"{er:.2f}", f"{tr * er:.2f}", "off" if tr * er < 1 else "on"])
    md += table(["I (flop/B)", "time ratio off/on", "energy ratio off/on", "EDP ratio off/on", "better under EDP"], rows)
    md += ["", "Ratios are per flop (time per flop, energy per flop, their product), so different repetition "
           "counts do not matter. Below 1 means turbo off is better.", ""]
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(Is, rt, "o-", color=C[1], label="time per flop")
    ax.plot(Is, re_, "o-", color=C[2], label="energy per flop")
    ax.plot(Is, red, "o-", color=C[0], label="energy × time (EDP)")
    ax.axhline(1, color=MUTED, lw=1)
    ax.set_xscale("log", base=2)
    ax.set(xlabel="intensity I (flop/byte)", ylabel="turbo off / turbo on", title="X3: below 1, turbo off is better")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "edp_ratio.png"), dpi=130); plt.close(fig)
    return rows


SETTINGS_SFX = [(t, sfx) for t, _, sfx in SETTINGS]


def main():
    os.makedirs(OUT, exist_ok=True)
    S = [(tag, json.load(open(os.path.join(FIG, d, "summary.json")))) for tag, d, _ in SETTINGS]
    G = {}
    for tag, _, sfx in SETTINGS:
        rows = load(os.path.join(DATA, f"results{sfx}.csv"), os.path.join(DATA, f"run_flags{sfx}.csv"))
        G[tag] = [x for x in sel(aggregate(rows), "intensity") if not x["all_thr"]]
    md = ["# Viva extras: X1–X3", "",
          "Generated by `report/viva_extras.py` from the committed `summary.json` files and the raw CSVs (read-only). "
          "X1 and X2(a) are model what-ifs on fitted constants, not measurements; X2(b) and X3 re-arrange measured data.", ""]
    # sanity: recomputed balance points must match analyze.py
    for tag, s in S:
        m = model_from(s["params"])
        assert abs(m.B_eps_hat - s["params"]["B_eps_hat"]) < 1e-6, tag
        md.append(f"- {tag}: B̂_ε recomputed = {m.B_eps_hat:.2f} (summary.json {s['params']['B_eps_hat']:.2f})")
    md.append("")
    x1(S, md); x2(S, G, md); x3(S, G, md)
    open(os.path.join(OUT, "viva_extras.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
