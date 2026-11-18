"""Electrical design: string sizing, plant sizing, voltage drop, BESS sizing, and their drawings."""
import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle

import basis as b


def string_voltages(n, t_c):
    """String Voc and Vmp at cell temperature t_c (works on numbers or numpy arrays)."""
    m = b.MODULE
    # Datasheets rarely list a Vmp coefficient; Pmp coefficient minus Isc coefficient approximates it.
    beta_vmp = m["gamma_pmp"] - m["alpha_isc"]
    voc = n * m["voc"] * (1 + m["beta_voc"] * (t_c - 25))
    vmp = n * m["vmp"] * (1 + beta_vmp * (t_c - 25))
    return voc, vmp


def string_sizing():
    # Longest string that stays under the system max on the coldest morning = fewest strings and combiners.
    n = math.floor(b.SYSTEM_VMAX / string_voltages(1, b.T_MIN_C)[0])
    voc_cold, vmp_cold = string_voltages(n, b.T_MIN_C)
    vmp_hot = string_voltages(n, b.T_CELL_MAX_C)[1]
    n_min = math.ceil(b.INVERTER["mppt_min"] / string_voltages(1, b.T_CELL_MAX_C)[1])
    return dict(n=n, n_min=n_min, voc_cold=voc_cold, vmp_cold=vmp_cold, vmp_hot=vmp_hot,
                v_stc=n * b.MODULE["vmp"], kw=n * b.MODULE["p_w"] / 1000)


def plant_sizing(s):
    inv = b.INVERTER
    # Round up to whole trackers per block so every tracker is full.
    trackers_per_block = math.ceil(b.DC_AC_TARGET * inv["p_ac_kw"] / s["kw"] / b.TRACKER["strings"])
    strings_per_block = trackers_per_block * b.TRACKER["strings"]
    strings = strings_per_block * inv["blocks"]
    return dict(trackers_per_block=trackers_per_block, strings_per_block=strings_per_block,
                strings=strings, trackers=trackers_per_block * inv["blocks"], modules=strings * s["n"],
                dc_kw=strings * s["kw"], ac_kw=inv["p_ac_kw"] * inv["blocks"])


def voltage_drop(s, string_m, feeder_m):
    """Worst-case DC voltage drop (%) at the STC operating point. Lengths are one-way, in m."""
    def pct(length_m, ohm_per_km, amps):
        return 2 * length_m / 1000 * ohm_per_km * amps / s["v_stc"] * 100  # x2: out and back

    i_string = b.MODULE["imp"]
    return dict(string=pct(string_m, b.STRING_WIRE["ohm_per_km"], i_string),
                feeder=pct(feeder_m, b.FEEDER_WIRE["ohm_per_km"], b.STRINGS_PER_COMBINER * i_string),
                feeder_design_amps=1.25 * b.MODULE["isc"] * b.STRINGS_PER_COMBINER)


def bess_sizing():
    e = b.BESS
    usable = e["mw"] * e["hours"]
    containers = math.ceil(usable / e["usable"] / e["container_mwh"])
    return dict(usable_mwh=usable, nameplate_mwh=containers * e["container_mwh"],
                containers=containers, pcs=math.ceil(e["mw"] / e["pcs_mw"]))


def plot_string_window(s, path):
    t = np.linspace(-40, 80, 200)
    voc, vmp = string_voltages(s["n"], t)
    voc_long = string_voltages(s["n"] + 1, t)[0]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axhspan(b.INVERTER["mppt_min"], b.INVERTER["mppt_max"], color="#4CAF50", alpha=0.12,
               label=f"Inverter MPPT window {b.INVERTER['mppt_min']}-{b.INVERTER['mppt_max']} V")
    ax.axhline(b.SYSTEM_VMAX, color="#C62828", lw=2, label=f"{b.SYSTEM_VMAX} V system maximum")
    ax.plot(t, voc_long, color="#E8A33D", lw=1.5, ls="--", label=f"Voc, {s['n'] + 1} modules (too long)")
    ax.plot(t, voc, color="#E8A33D", lw=2.5, label=f"Voc, {s['n']} modules (open circuit)")
    ax.plot(t, vmp, color="#5B7DB1", lw=2.5, label=f"Vmp, {s['n']} modules (operating)")
    for x, y, txt, offset in [
            (b.T_MIN_C, s["voc_cold"], f"{s['voc_cold']:.0f} V at {b.T_MIN_C:g} C", (8, -16)),
            (b.T_CELL_MAX_C, s["vmp_hot"], f"{s['vmp_hot']:.0f} V at {b.T_CELL_MAX_C:g} C", (-8, 10))]:
        ax.plot(x, y, "ko", ms=6)
        ax.annotate(txt, (x, y), xytext=offset, textcoords="offset points", fontsize=9,
                    ha="left" if offset[0] > 0 else "right")
        ax.axvline(x, color="gray", ls=":", lw=1)
    ax.set(xlabel="Cell temperature (deg C)", ylabel="String voltage (V DC)", ylim=(700, 1700),
           title="String sizing: the string must stay inside the window at every temperature")
    ax.legend(loc="lower left", fontsize=8.5)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_sld(s, p, bess, path):
    """Simplified single-line diagram: one typical PV block, the other feeders, BESS, MPT, POI."""
    fig, ax = plt.subplots(figsize=(13, 8))
    ax.set(xlim=(0, 100), ylim=(2, 64), aspect="equal")
    ax.axis("off")

    def wire(*pts, **kw):
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color="black", lw=1.3, **kw)

    def box(x, y, text, w=14, h=8, fc="#FFF4E0"):
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc=fc, ec="black", lw=1.2))
        ax.text(x, y, text, ha="center", va="center", fontsize=8)

    def xfmr(x, y, text):
        for dx in (-1.2, 1.2):
            ax.add_patch(Circle((x + dx, y), 2, fc="none", ec="black", lw=1.2))
        ax.text(x, y - 3, text, ha="center", va="top", fontsize=7.5)

    def breaker(x, y):
        ax.add_patch(Rectangle((x - 0.9, y - 0.9), 1.8, 1.8, fc="white", ec="black", lw=1.2, zorder=3))

    inv, bus_x = b.INVERTER, 68
    # Typical PV block
    y = 54
    ax.add_patch(Rectangle((1, 45.5), 61, 16, fc="none", ec="gray", ls="--"))
    ax.text(2, 60.3, f"Typical PV block (x{inv['blocks']})", fontsize=8.5, color="dimgray")
    box(8, y, f"PV strings\n{s['n']} x {b.MODULE['p_w']} W\n{p['strings_per_block']} per block")
    box(25, y, f"DC combiners\n{b.STRINGS_PER_COMBINER} strings each\n"
               f"{math.ceil(p['strings_per_block'] / b.STRINGS_PER_COMBINER)} per block")
    box(42, y, f"Central inverter\n{inv['p_ac_kw'] / 1000:.1f} MVA\n1500 V DC / {inv['v_ac_kv']} kV AC")
    xfmr(56, y, f"{inv['v_ac_kv']}/{b.MV_KV} kV")
    wire((15, y), (18, y))
    wire((32, y), (35, y))
    wire((49, y), (52.8, y))     # transformer circles span x +/- 3.2
    wire((59.2, y), (bus_x, y))
    breaker(64, y)
    ax.text(64, y + 1.5, "Block 1", ha="center", fontsize=7.5)
    # Other PV feeders
    for i in range(2, inv["blocks"] + 1):
        yi = y - 10 - (i - 2) * 6
        wire((56, yi), (bus_x, yi))
        breaker(64, yi)
        ax.text(55, yi, f"PV block {i}", ha="right", va="center", fontsize=8)
    # BESS
    yb = 14
    box(8, yb, f"BESS\n{bess['containers']} x {b.BESS['container_mwh']:.0f} MWh containers\n"
               f"{bess['usable_mwh']} MWh usable", fc="#E3ECF8")
    box(25, yb, f"PCS\n{bess['pcs']} x {b.BESS['pcs_mw']} MW", fc="#E3ECF8")
    xfmr(42, yb, f"{inv['v_ac_kv']}/{b.MV_KV} kV")
    wire((15, yb), (18, yb))
    wire((32, yb), (38.8, yb))
    wire((45.2, yb), (bus_x, yb))
    breaker(64, yb)
    # Collector bus, main power transformer, point of interconnection
    ax.plot([bus_x, bus_x], [yb, y], color="black", lw=4)
    ax.text(bus_x + 1, y + 2, f"{b.MV_KV} kV collector bus", fontsize=8)
    ym = 35
    wire((bus_x, ym), (76.8, ym))
    breaker(72, ym)
    xfmr(80, ym, f"MPT {b.MV_KV}/{b.POI_KV} kV\n{b.MPT_MVA} MVA")
    wire((83.2, ym), (93, ym))
    breaker(86, ym)
    ax.add_patch(Circle((90, ym), 1.4, fc="white", ec="black", lw=1.2, zorder=3))
    ax.text(90, ym, "M", ha="center", va="center", fontsize=7, zorder=4)
    ax.annotate("", xy=(98, ym), xytext=(93, ym), arrowprops=dict(arrowstyle="-|>", lw=1.3))
    ax.text(96, ym + 2.5, f"POI\n{b.POI_KV} kV\n(utility)", ha="center", va="bottom", fontsize=8)
    ax.set_title(f"Simplified single-line diagram: {p['ac_kw'] / 1000:.0f} MWac PV + "
                 f"{b.BESS['mw']} MW / {bess['usable_mwh']} MWh BESS", fontsize=12)
    ax.text(1, 4, "Conceptual, not for construction. Protection, grounding, auxiliary power and "
                  "instrument transformers are omitted. M = revenue meter.", fontsize=7.5, color="dimgray")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
