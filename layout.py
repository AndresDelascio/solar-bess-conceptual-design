"""Site layout: trackers, roads, DC combiners, inverter skids and the substation / BESS yard.

Coordinates are metres from the south-west fence corner (x = east, y = north). Each block has
two tiers of north-south trackers with an east-west road between them; the inverter skid sits
mid-road so DC feeders stay short. Cable lengths for voltage drop and the takeoff come from here.
"""
import math

import ezdxf
import matplotlib.pyplot as plt
from ezdxf.enums import TextEntityAlignment
from matplotlib.patches import Rectangle

import basis as b

STYLE = {  # layer: (AutoCAD colour index, fill colour, edge colour, legend label)
    "FENCE": (1, "none", "black", "Fence"),
    "ROADS": (8, "#D9D9D9", "none", "Access roads"),
    "YARD": (3, "#F1F8E9", "#7CB342", "Yard (O&M / laydown)"),
    "PV-TRACKERS": (5, "#3B6FB6", "none", "Single-axis trackers"),
    "DC-COMBINERS": (6, "#C2185B", "none", "DC combiner boxes"),
    "INVERTER-SKIDS": (1, "#E53935", "black", "Inverter / MV skids"),
    "SUBSTATION": (6, "#9575CD", "black", "Substation"),
    "BESS": (4, "#26A69A", "black", "BESS containers + PCS"),
}


def build(s, p, bess):
    m, t, rw = b.MODULE, b.TRACKER, b.ROAD_W
    tracker_len = t["strings"] * s["n"] * (m["width_m"] + t["module_gap_m"]) + t["motor_gap_m"]
    pitch = m["length_m"] / t["gcr"]               # 1P portrait: collector width = module length
    rows = math.ceil(p["trackers_per_block"] / 2)   # two tiers per block
    bw, bh = rows * pitch, 2 * tracker_len + rw
    cells = b.INVERTER["blocks"] + 1                 # PV blocks + the yard
    grid_rows = math.ceil(cells / b.GRID_COLS)
    fw = 2 * b.SETBACK + b.GRID_COLS * bw + (b.GRID_COLS - 1) * b.BLOCK_GAP
    fh = 2 * b.SETBACK + grid_rows * bh + (grid_rows - 1) * b.BLOCK_GAP

    rects = {layer: [] for layer in STYLE}
    texts = []
    rects["FENCE"].append((0, 0, fw, fh))
    half = b.SETBACK / 2                              # ring road runs inside the fence
    rects["ROADS"] += [(half - rw / 2, half - rw / 2, fw - 2 * half + rw, rw),
                       (half - rw / 2, fh - half - rw / 2, fw - 2 * half + rw, rw),
                       (half - rw / 2, half - rw / 2, rw, fh - 2 * half + rw),
                       (fw - half - rw / 2, half - rw / 2, rw, fh - 2 * half + rw)]
    for c in range(1, b.GRID_COLS):                   # north-south spine road between block columns
        xc = b.SETBACK + c * (bw + b.BLOCK_GAP) - b.BLOCK_GAP / 2
        rects["ROADS"].append((xc - rw / 2, half, rw, fh - 2 * half))

    rows_per_combiner = b.STRINGS_PER_COMBINER // (2 * t["strings"])  # both tiers feed one combiner
    string_runs, feeder_runs, skids = [], [], []
    for i in range(cells):
        x0 = b.SETBACK + (i % b.GRID_COLS) * (bw + b.BLOCK_GAP)
        y0 = b.SETBACK + (i // b.GRID_COLS) * (bh + b.BLOCK_GAP)
        if i == b.INVERTER["blocks"]:
            sub = _yard(x0, y0, bw, bh, bess, rects, texts)
            continue
        road_y = y0 + tracker_len + rw / 2
        inv_x = x0 + bw / 2
        skids.append((inv_x, road_y))
        rects["ROADS"].append((x0 - b.BLOCK_GAP / 2, road_y - rw / 2, bw + b.BLOCK_GAP, rw))
        rects["INVERTER-SKIDS"].append((inv_x - 3, road_y - 1.5, 6, 3))
        texts.append((inv_x, y0 + tracker_len / 2, f"BLOCK {i + 1}", 14))
        for r in range(rows):
            xc = x0 + (r + 0.5) * pitch
            rects["PV-TRACKERS"] += [(xc - m["length_m"] / 2, y0, m["length_m"], tracker_len),
                                     (xc - m["length_m"] / 2, road_y + rw / 2, m["length_m"], tracker_len)]
        for c in range(math.ceil(rows / rows_per_combiner)):
            group = range(c * rows_per_combiner, min((c + 1) * rows_per_combiner, rows))
            cx = x0 + (sum(group) / len(group) + 0.5) * pitch
            rects["DC-COMBINERS"].append((cx - 1, road_y - rw / 2 + 0.3, 2, 1.2))
            feeder_runs.append(abs(cx - inv_x) + 5)   # along the road + 5 m risers / terminations
            for r in group:
                dx = abs(x0 + (r + 0.5) * pitch - cx)
                for j in range(t["strings"]):           # j = 0 is the string nearest the road
                    run = j * tracker_len / t["strings"] + dx + rw / 2
                    string_runs += [run, run]            # one string per tier

    mv_runs = [abs(x - sub[0]) + abs(y - sub[1]) for x, y in skids]  # follows roads (Manhattan)
    return dict(rects=rects, texts=texts, fence_w=fw, fence_h=fh, area_ha=fw * fh / 1e4,
                fence_m=2 * (fw + fh), tracker_len=tracker_len, pitch=pitch, block_w=bw, block_h=bh,
                road_m=sum(max(w, h) for _, _, w, h in rects["ROADS"]),
                string_cable_m=2 * sum(string_runs), string_worst_m=max(string_runs),   # x2: + and -
                feeder_cable_m=2 * sum(feeder_runs), feeder_worst_m=max(feeder_runs),
                mv_circuit_m=sum(mv_runs))


def _yard(x0, y0, w, h, bess, rects, texts):
    """Substation in the NE corner of the yard, BESS beside it. Returns the substation centre."""
    rects["YARD"].append((x0, y0, w, h))
    sx, sy, sw, sh = x0 + w - 70, y0 + h - 55, 60, 45
    rects["SUBSTATION"].append((sx, sy, sw, sh))
    texts.append((sx + sw / 2, sy + sh / 2, "SUBSTATION", 5))
    per_row, c_len, c_wid = 5, 6.1, 2.44              # 20 ft containers, 3 m apart, rows 8 m apart
    bx = sx - 20 - per_row * (c_len + 3)
    for k in range(bess["containers"]):
        rects["BESS"].append((bx + (k % per_row) * (c_len + 3), sy + sh - c_wid - (k // per_row) * 8, c_len, c_wid))
    pcs_y = sy + sh - c_wid - math.ceil(bess["containers"] / per_row) * 8
    for k in range(bess["pcs"]):
        rects["BESS"].append((bx + k * (c_len + 3), pcs_y, 6, 2.5))
    texts.append((bx + per_row * (c_len + 3) / 2, pcs_y - 8, "BESS", 5))
    texts.append((x0 + w * 0.3, y0 + h / 2, "O&M / LAYDOWN", 10))
    return sx + sw / 2, sy + sh / 2


def plot(lay, path, title):
    fig, ax = plt.subplots(figsize=(14, 10.5))
    for layer, (_, fc, ec, _) in STYLE.items():
        for x, y, w, h in lay["rects"][layer]:
            ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=2.5 if layer == "FENCE" else 0.5))
    for x, y, txt, height in lay["texts"]:
        ax.text(x, y, txt, ha="center", va="center", fontsize=6 + height * 0.35, weight="bold",
                bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.5))
    fw, fh = lay["fence_w"], lay["fence_h"]
    ax.plot([0, 100], [-25, -25], color="black", lw=3)             # scale bar
    ax.text(50, -32, "100 m", ha="center", va="top", fontsize=9)
    ax.annotate("N", xy=(fw + 35, fh), xytext=(fw + 35, fh - 60), ha="center", fontsize=13, weight="bold",
                arrowprops=dict(arrowstyle="-|>", lw=2))
    handles = [Rectangle((0, 0), 1, 1, fc=fc if fc != "none" else "white", ec=ec if ec != "none" else fc,
                         label=label) for _, fc, ec, label in STYLE.values()]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 0.85), fontsize=9, frameon=False)
    ax.set(xlim=(-20, fw + 60), ylim=(-45, fh + 20), aspect="equal", title=title)
    ax.axis("off")
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def to_dxf(lay, path):
    """Write the layout to a DXF that AutoCAD / Civil 3D opens directly (units: metres)."""
    doc = ezdxf.new("R2013", units=ezdxf.units.M)
    msp = doc.modelspace()
    for layer, (aci, *_) in STYLE.items():
        doc.layers.add(layer, color=aci)
    doc.layers.add("TEXT", color=7)
    for layer, items in lay["rects"].items():
        for x, y, w, h in items:
            msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True,
                               dxfattribs={"layer": layer})
    for x, y, txt, height in lay["texts"]:
        msp.add_text(txt, height=height, dxfattribs={"layer": "TEXT"}).set_placement(
            (x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    doc.saveas(path)
