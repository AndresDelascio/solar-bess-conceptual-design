"""Run the whole conceptual design:  python main.py   -> everything lands in out/

Order mirrors how a designer works: size strings -> size plant -> lay it out -> check voltage
drop -> model energy -> take off quantities -> QA/QC -> drawings and summary sheet.
"""
import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import basis as b
import electrical
import energy
import layout

OUT = Path(__file__).parent / "out"


def main():
    OUT.mkdir(exist_ok=True)
    s = electrical.string_sizing()
    p = electrical.plant_sizing(s)
    bess = electrical.bess_sizing()
    lay = layout.build(s, p, bess)
    vd = electrical.voltage_drop(s, lay["string_worst_m"], lay["feeder_worst_m"])
    dcac = p["dc_kw"] / p["ac_kw"]

    wx = energy.weather(OUT / "tmy.csv")
    trk = energy.simulate(energy.tracker_mount(), p, wx)
    fix = energy.simulate(energy.fixed_mount(), p, wx)
    steps = energy.loss_steps(trk, p, wx)
    mwh = energy.ac_mw(trk).sum()
    spec_yield = mwh / p["dc_kw"] * 1000
    clip_pct = -dict(steps)["Inverter clipping"] / (mwh - dict(steps)["Inverter clipping"])
    tracker_gain = mwh / energy.ac_mw(fix).sum() - 1

    takeoff = pd.DataFrame([
        ("PV modules, 580 W bifacial", p["modules"], "ea", f"{p['strings']} strings x {s['n']}"),
        ("Source circuits (strings)", p["strings"], "ea", f"{p['strings_per_block']} per block"),
        (f"Single-axis trackers, 1P, {b.TRACKER['strings']} strings", p["trackers"], "ea",
         f"{lay['tracker_len']:.1f} m long, {lay['pitch']:.2f} m pitch"),
        ("Tracker piles", p["trackers"] * b.TRACKER["piles"], "ea", f"{b.TRACKER['piles']} per tracker (assumed)"),
        ("DC combiner boxes", len(lay["rects"]["DC-COMBINERS"]), "ea", f"{b.STRINGS_PER_COMBINER} strings max"),
        (f"Inverter / MV skids, {b.INVERTER['p_ac_kw'] / 1000:.1f} MVA", b.INVERTER["blocks"], "ea", "1 per block"),
        (f"String wire, {b.STRING_WIRE['name']}", int(round(lay["string_cable_m"], -2)), "m", "from layout, + and -"),
        (f"DC feeders, {b.FEEDER_WIRE['name']}", int(round(lay["feeder_cable_m"], -1)), "m", "from layout, + and -"),
        (f"MV collector cable, {b.MV_KV} kV", int(round(lay["mv_circuit_m"], -1)), "circuit-m", "radial, along roads"),
        ("Main power transformer", 1, "ea", f"{b.MV_KV}/{b.POI_KV} kV, {b.MPT_MVA} MVA"),
        (f"Access roads, {b.ROAD_W:.0f} m wide", int(round(lay["road_m"], -1)), "m", "ring + spine + block roads"),
        ("Perimeter fence", int(round(lay["fence_m"], -1)), "m", "from layout"),
        ("Fenced area", round(lay["area_ha"], 1), "ha", f"{lay['area_ha'] * 2.471:.0f} acres"),
        (f"BESS containers, {b.BESS['container_mwh']:.0f} MWh", bess["containers"], "ea",
         f"{bess['nameplate_mwh']:.0f} MWh nameplate"),
        (f"BESS power conversion (PCS), {b.BESS['pcs_mw']} MW", bess["pcs"], "ea", f"{b.BESS['mw']} MW total"),
    ], columns=["item", "qty", "unit", "basis"], dtype=object)
    takeoff.to_csv(OUT / "takeoff.csv", index=False)

    vd_total = vd["string"] + vd["feeder"]
    export_mva = (p["ac_kw"] / 1000 + b.BESS["mw"]) / 0.95   # PV + BESS exporting together at 0.95 PF
    checks = {
        f"Cold Voc string {s['voc_cold']:.0f} V <= {b.SYSTEM_VMAX} V system max": s["voc_cold"] <= b.SYSTEM_VMAX,
        f"Hot Vmp string {s['vmp_hot']:.0f} V >= MPPT min {b.INVERTER['mppt_min']} V":
            s["vmp_hot"] >= b.INVERTER["mppt_min"],
        f"Cold Vmp string {s['vmp_cold']:.0f} V <= MPPT max {b.INVERTER['mppt_max']} V":
            s["vmp_cold"] <= b.INVERTER["mppt_max"],
        f"DC/AC ratio {dcac:.2f} within 1.20-1.40": 1.20 <= dcac <= 1.40,
        f"Worst-case DC voltage drop {vd_total:.2f}% <= {b.VD_LIMIT_PCT}%": vd_total <= b.VD_LIMIT_PCT,
        f"Trackers drawn in layout ({len(lay['rects']['PV-TRACKERS'])}) = trackers sized ({p['trackers']})":
            len(lay["rects"]["PV-TRACKERS"]) == p["trackers"],
        f"MPT {b.MPT_MVA} MVA >= PV + BESS export {export_mva:.1f} MVA": b.MPT_MVA >= export_mva,
        f"Specific yield {spec_yield:.0f} kWh/kWp within 1100-1700 (S. Ontario sanity range)":
            1100 <= spec_yield <= 1700,
    }

    lines = [
        f"{p['ac_kw'] / 1000:.0f} MWac SOLAR + {b.BESS['mw']} MW / {bess['usable_mwh']} MWh BESS - CONCEPTUAL DESIGN",
        f"Site: {b.SITE['name']} ({b.SITE['lat']}, {b.SITE['lon']})   Prepared by {b.AUTHOR}",
        "",
        "PLANT",
        f"  {p['ac_kw'] / 1000:.1f} MWac / {p['dc_kw'] / 1000:.2f} MWdc, DC/AC {dcac:.2f}, "
        f"{b.INVERTER['blocks']} blocks x {b.INVERTER['p_ac_kw'] / 1000:.1f} MVA",
        "",
        "STRING SIZING",
        f"  {s['n']} modules/string (min {s['n_min']} for MPPT), {s['kw']:.2f} kWdc/string",
        f"  Voc {s['voc_cold']:.0f} V at {b.T_MIN_C:g} C | Vmp {s['vmp_hot']:.0f} V at {b.T_CELL_MAX_C:g} C "
        f"| Vmp {s['vmp_cold']:.0f} V at {b.T_MIN_C:g} C",
        "",
        "LAYOUT",
        f"  Fence {lay['fence_w']:.0f} x {lay['fence_h']:.0f} m = {lay['area_ha']:.1f} ha; "
        f"tracker {lay['tracker_len']:.1f} m long, row pitch {lay['pitch']:.2f} m (GCR {b.TRACKER['gcr']})",
        "",
        "DC VOLTAGE DROP (worst-case circuit, STC operating point)",
        f"  String {vd['string']:.2f}% over {lay['string_worst_m']:.0f} m ({b.STRING_WIRE['name']})",
        f"  Feeder {vd['feeder']:.2f}% over {lay['feeder_worst_m']:.0f} m ({b.FEEDER_WIRE['name']}), "
        f"ampacity design current {vd['feeder_design_amps']:.0f} A (125% Isc)",
        f"  Total  {vd_total:.2f}%",
        "",
        "ENERGY (typical year, PVGIS TMY)",
        "  Note: PVGIS uses ERA5 reanalysis in North America, which reads high vs satellite data.",
        "        Treat as optimistic; cross-check with NSRDB or Meteonorm (PVsyst) before quoting.",
        f"  Annual AC energy   {mwh:,.0f} MWh",
        f"  Specific yield     {spec_yield:,.0f} kWh/kWp",
        f"  Capacity factor    {mwh / (p['ac_kw'] / 1000 * 8760):.1%} (AC)",
        f"  Inverter clipping  ~{clip_pct:.1%} of potential AC energy",
        f"  Tracker vs fixed {b.FIXED_TILT} deg: {tracker_gain:+.1%} energy",
        "",
        "QUANTITY TAKEOFF (out/takeoff.csv)",
        takeoff.to_string(index=False),
        "",
        "QA/QC CHECKS",
        *[f"  [{'PASS' if ok else 'FAIL'}] {name}" for name, ok in checks.items()],
    ]
    summary = "\n".join(lines)
    print(summary)
    (OUT / "summary.txt").write_text(summary + "\n", encoding="utf-8")

    plant = f"{p['ac_kw'] / 1000:.0f} MWac / {p['dc_kw'] / 1000:.1f} MWdc"
    electrical.plot_string_window(s, OUT / "string_window.png")
    electrical.plot_sld(s, p, bess, OUT / "single_line_diagram.png")
    layout.plot(lay, OUT / "site_layout.png", f"Conceptual site layout, {plant}, {b.SITE['name']}")
    layout.to_dxf(lay, OUT / "site_layout.dxf")
    energy.plot_monthly(energy.ac_mw(trk), energy.ac_mw(fix), p, OUT / "monthly_energy.png")
    energy.plot_waterfall(steps, OUT / "loss_waterfall.png")
    energy.plot_daily(trk, fix, p, wx, OUT / "daily_profiles.png")
    summary_sheet(s, p, bess, lay, mwh, spec_yield, vd_total, checks)

    assert all(checks.values()), "QA/QC check failed - see out/summary.txt"


def summary_sheet(s, p, bess, lay, mwh, spec_yield, vd_total, checks):
    """One-page project sheet (PDF + PNG) to attach to an application or LinkedIn message."""
    fig = plt.figure(figsize=(11, 8.5))
    grid = fig.add_gridspec(2, 3, height_ratios=[1.75, 1], hspace=0.04, wspace=0.04,
                            left=0.02, right=0.98, top=0.88, bottom=0.04)
    for cell, name in [(grid[0, :2], "site_layout"), (grid[1, 0], "single_line_diagram"),
                       (grid[1, 1], "monthly_energy"), (grid[1, 2], "loss_waterfall")]:
        ax = fig.add_subplot(cell)
        ax.imshow(plt.imread(OUT / f"{name}.png"))
        ax.set_anchor("N")
        ax.axis("off")
    fig.suptitle(f"{p['ac_kw'] / 1000:.0f} MWac Solar + {b.BESS['mw']} MW / {bess['usable_mwh']} MWh BESS "
                 f"- Conceptual Design", fontsize=15, weight="bold", x=0.02, ha="left")
    fig.text(0.02, 0.9, f"{b.SITE['name']}  |  {b.AUTHOR}  |  {datetime.date.today():%B %Y}  |  "
                          "Python, pvlib, AutoCAD (DXF)", fontsize=9, color="dimgray")
    facts = [
        ("DC / AC", f"{p['dc_kw'] / 1000:.1f} MWdc / {p['ac_kw'] / 1000:.0f} MWac ({p['dc_kw'] / p['ac_kw']:.2f})"),
        ("Modules", f"{p['modules']:,} x {b.MODULE['p_w']} W, {s['n']}/string"),
        ("Racking", f"{p['trackers']} single-axis trackers, GCR {b.TRACKER['gcr']}"),
        ("Inverters", f"{b.INVERTER['blocks']} x {b.INVERTER['p_ac_kw'] / 1000:.1f} MVA central skids"),
        ("Energy", f"{mwh:,.0f} MWh/yr ({spec_yield:,.0f} kWh/kWp)"),
        ("BESS", f"{bess['containers']} x {b.BESS['container_mwh']:.0f} MWh containers, {bess['pcs']} PCS"),
        ("Land", f"{lay['area_ha']:.1f} ha fenced ({lay['area_ha'] * 2.471:.0f} acres)"),
        ("DC voltage drop", f"{vd_total:.2f}% worst case"),
        ("QA/QC", f"{sum(checks.values())}/{len(checks)} automated checks pass"),
    ]
    ax = fig.add_subplot(grid[0, 2])
    ax.axis("off")
    for i, (k, v) in enumerate(facts):
        ax.text(0.04, 0.95 - i * 0.105, k, fontsize=9, color="dimgray", transform=ax.transAxes)
        ax.text(0.04, 0.95 - i * 0.105 - 0.045, v, fontsize=10, weight="bold", transform=ax.transAxes)
    fig.text(0.98, 0.01, "Conceptual only. Equipment: Canadian Solar CS6W-580TB-AG, SMA SC 4000 UP-US. ERA5 weather reads high. Not for construction.",
             fontsize=7, color="dimgray", ha="right")
    fig.savefig(OUT / "project_sheet.pdf")
    fig.savefig(OUT / "project_sheet.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
