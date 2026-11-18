# Learning Guide: Solar + BESS Conceptual Design

This guide teaches the whole project in 11 lessons. Each lesson has a short concept section,
where to look in the code, a chart to study, an exercise, and a check question with the
answer hidden. Do them in order. Plan about 1–2 hours each; lessons 5 and 10 take longer
because they use AutoCAD and PVsyst.

**Working with Claude:** in this session, say "lesson 3" (or any number) and I'll walk you
through it, answer questions, and quiz you before you move on.

---

## Part 0: Install the tools

You already have **Python 3.13**, **Git** and the **GitHub CLI** (`gh`); I checked. Install the rest yourself, in this order:

| # | Tool | Cost | Get it from | Needed for |
|---|---|---|---|---|
| 1 | **VS Code** | Free | https://code.visualstudio.com/download | Reading and running the code |
| 2 | VS Code **Python** extension (by Microsoft) | Free | Inside VS Code: Extensions (Ctrl+Shift+X) → search "Python" | Running and debugging |
| 3 | **GitHub account** | Free | https://github.com/signup | Publishing the project |
| 4 | **Google Earth Pro** (desktop) | Free | https://www.google.com/earth/about/versions/ | Picking and measuring a real parcel |
| 5 | **AutoCAD** 30-day trial | Free trial | https://www.autodesk.com/products/autocad/free-trial | Lesson 5 (layout) |
| 6 | **PVsyst** 30-day trial | Free trial | https://www.pvsyst.com (Download) | Lesson 10 (energy cross-check) |
| 7 | *Optional:* Civil 3D 30-day trial | Free trial | https://www.autodesk.com/products/civil-3d/free-trial | Grading and topography (beyond this project) |
| 8 | *Optional:* DWG TrueView | Free | https://www.autodesk.com/products/dwg/viewers | Viewing the DXF after the AutoCAD trial ends |

> **Trial timing:** AutoCAD and PVsyst start a 30-day clock when you first launch them.
> Install them now, but don't open them until you reach Lessons 5 and 10.

### Set up the project (once)

1. Open VS Code → **File → Open Folder** → choose this project folder.
2. Open a terminal in VS Code (**Terminal → New Terminal**) and run each line:

```bash
python -m venv .venv
```
```bash
.venv\Scripts\python -m pip install -r requirements.txt
```
```bash
.venv\Scripts\python main.py
```

3. VS Code may ask "Select interpreter". Pick the one that shows `.venv`.
4. Success: the terminal prints the summary and ends with 8 `[PASS]` lines, and `out/` fills with drawings.

**How the code is organized:** one file per topic, run in the order a designer works.

```
basis.py       every input (the only file you normally edit)
electrical.py  string sizing, plant sizing, voltage drop, BESS, string chart, single-line diagram
layout.py      site layout -> DXF for AutoCAD + PNG
energy.py      weather, pvlib simulation, energy charts
main.py        runs everything, takeoff, QA/QC checks, summary sheet
out/           all results (regenerated each run)
```

---

## Lesson 1: The design basis

**Goal:** know what every input means and where it comes from.

**Concept.** Every design starts from a *design basis*: the site, the equipment datasheets,
and the assumptions everyone agrees on. If a number isn't in the design basis, it shouldn't
be in the design. Key module datasheet values, from the Canadian Solar CS6W-580TB-AG datasheet
(V2.1, Apr 2025):

| Symbol | Meaning | Our value |
|---|---|---|
| Pmax | Rated power at STC (1000 W/m², 25 °C cell) | 580 W |
| Voc | Open-circuit voltage: no current flowing (inverter off) | 52.2 V |
| Vmp / Imp | Voltage / current at the maximum power point (normal operation) | 43.1 V / 13.46 A |
| Isc | Short-circuit current | 13.93 A |
| β_Voc | How Voc changes with temperature | −0.25 %/°C |
| γ_Pmp | How power changes with temperature | −0.29 %/°C |

The inverter is an SMA Sunny Central SC 4000 UP-US (MPPT 880–1,325 V, 1,500 V max). The design
temperatures come from the ASHRAE 2017 climate table for Hamilton airport.

**In the code:** [basis.py](basis.py). Read it top to bottom; each block names its source.

**Exercise.** Download a different 580–600 W TOPCon datasheet (Jinko, Trina or LONGi), put its
values in `basis.py`, and run. Does the string length change? Which value moved it?

<details><summary>Check yourself: why is "STC" not what the module sees in the field?</summary>

STC is a lab condition: 1000 W/m² and a 25 °C cell. In the field the cell is usually much
hotter (often 50–70 °C in summer), so power and voltage are lower. That's why we correct for
temperature everywhere.
</details>

---

## Lesson 2: String sizing (the most important electrical calc)

**Goal:** choose how many modules go in series and prove it's safe.

**Concept.** Modules in a string add their voltages. Voltage *rises* in the cold, so the
coldest sunny morning sets the maximum string length. Voltage *falls* in the heat, so the hottest
afternoon sets the minimum length the inverter can still track.

```
Voc(T) = Voc × (1 + β_Voc × (T − 25))
       = 52.2 × (1 + (−0.0025) × (−30.6 − 25)) = 59.46 V per module at −30.6 °C

Max modules = floor(1500 V / 59.46 V) = floor(25.2) = 25
```

−30.6 °C is the ASHRAE 50-year return minimum for Hamilton airport. The mean extreme annual
minimum (−21.7 °C, the usual NEC 690.7 basis) also gives 25 modules, so the choice doesn't change
the design; the 50-year value just adds margin.

Three checks have to pass:
1. Cold Voc × 25 = **1,486 V ≤ 1,500 V** (code and equipment limit; going over can damage equipment)
2. Hot Vmp × 25 = **913 V ≥ 880 V** (below this the inverter can't find the maximum power point)
3. Cold Vmp × 25 = **1,281 V ≤ 1,325 V** (top of the MPPT window)

**In the code:** `string_voltages()` and `string_sizing()` in [electrical.py](electrical.py).

**Look at:** [out/string_window.png](out/string_window.png). The dashed line shows why 26 modules fails.

**Exercise.** In `basis.py` set `T_MIN_C = -15`, run `main.py`, and read the string sizing section. Then set it back to −30.6.

<details><summary>Answer</summary>

The string grows to **26 modules** (1,725 strings instead of 1,800, so fewer combiners and less
cable). But if a real −30.6 °C morning happens, 26 × 59.46 V = **1,546 V**, which exceeds 1,500 V. That's why
the design low temperature must come from real climate data (ASHRAE extreme minimum), not a guess.
</details>

<details><summary>Check yourself: the minimum and maximum string length are both 25. Is that a problem?</summary>

It means there's no flexibility: the MPPT window is only one module wide. With a different
inverter (lower MPPT minimum) you'd have room to choose. This is a good point to raise in an interview.
</details>

---

## Lesson 3: Plant sizing and the DC/AC ratio

**Goal:** understand why we put 26 MW of panels on 20 MW of inverters.

**Concept.** Panels rarely reach nameplate power (heat, sun angle, clouds). Adding extra DC (DC/AC > 1)
keeps the inverters busier all day. On the sunniest hours the inverter caps output at its AC rating.
This is **clipping**, and that energy is lost.

```
Target DC per block = 1.30 × 4,000 kW = 5,200 kW
Strings needed      = 5,200 / 14.5 kW = 358.6 → round up to whole trackers (3 strings each)
                    = 120 trackers = 360 strings = 5,220 kW → DC/AC = 1.305
```

**In the code:** `plant_sizing()` in [electrical.py](electrical.py).

**Look at:** [out/daily_profiles.png](out/daily_profiles.png). The red area is clipped energy on a sunny June day.

**Exercise.** Try `DC_AC_TARGET` = 1.1, 1.2, 1.4, 1.5. Record MWh, kWh/kWp and clipping each time.

<details><summary>Answer</summary>

| DC/AC | MWh/yr | kWh/kWp | Clipping |
|---|---|---|---|
| 1.1 | 36,787 | 1,658 | 0.1% |
| 1.2 | 39,909 | 1,653 | 0.4% |
| 1.3 | 42,782 | 1,639 | 1.3% |
| 1.4 | 45,285 | 1,614 | 2.8% |
| 1.5 | 47,458 | 1,581 | 4.8% |

Total energy keeps rising, but each extra panel produces less (kWh/kWp falls). The best ratio
is an *economic* decision: the cost of extra panels vs the value of the extra MWh. 1.25–1.35 is typical.
</details>

---

## Lesson 4: The energy model

**Goal:** go from weather data to MWh, and explain every loss.

**Concept.**
- **GHI** = sunlight on flat ground. **DNI** = direct beam from the sun. **DHI** = diffuse light from the sky.
- **POA** (plane of array) = sunlight on the tilted panel. Trackers rotate east to west to keep POA high.
- **TMY** (typical meteorological year) = 12 representative months stitched into one year, used for long-term averages.
- **Backtracking:** at low sun angles, trackers rotate *back* toward flat so rows don't shade each other.
- The model chain: weather → sun position → POA → reflection loss → cell temperature → DC power → system losses → inverter → AC.

**In the code:** [energy.py](energy.py). `simulate()` builds the pvlib model; `loss_steps()` builds the waterfall.

**Look at:**
- [out/loss_waterfall.png](out/loss_waterfall.png). Read it left to right like a PVsyst loss diagram.
- [out/daily_profiles.png](out/daily_profiles.png) (December). The tracker dips at noon because it lies flat while the sun is low in the south.

**Two things I caught while building it (good interview stories):**
1. PVGIS labels each hour of sunlight at its *start*. The model computed sun position at the
   wrong time until the data was shifted 30 minutes to the middle of each hour.
2. PVGIS uses **ERA5 reanalysis** weather in North America, which reads high. The +38% tracking
   gain is a symptom; the realistic range is about +25–30%. Treat 1,639 kWh/kWp as optimistic.

**Exercise.** Set `FIXED_TILT = 40` and compare the fixed-tilt monthly bars with the 30° result.

<details><summary>Answer</summary>

Annual energy barely changes (37,133 → 37,256 MWh, +0.3%). The steeper panel gains in winter
(low sun) and loses in summer. Around 30–40° is close to optimal at 43° latitude.
</details>

<details><summary>Check yourself: why is "cell temperature" only −2.5% here?</summary>

Ontario is cool for most of the year, so cells run near or below 25 °C much of the time. In
Arizona the same loss would be closer to −6 to −8%.
</details>

---

## Lesson 5: Site layout and AutoCAD

**Goal:** turn sizing numbers into geometry, and work with it in AutoCAD.

**Concept.**
- **GCR** (ground coverage ratio) = panel width ÷ row spacing. Higher GCR uses less land but causes more shading/backtracking.
  `pitch = 2.278 m ÷ 0.35 = 6.51 m`
- Tracker length = 75 modules × (1.134 m + 0.02 m gap) + 1 m motor gap = **87.5 m**
- **Block** = one inverter's worth of trackers: 2 tiers × 60 rows, with the road and inverter skid in the middle (to keep DC cables short).

**In the code:** `build()` in [layout.py](layout.py) places everything and measures cable runs; `to_dxf()` writes the AutoCAD file.

**AutoCAD exercise (start your trial here):**
1. Open `out/site_layout.dxf`. Units are metres.
2. Type `LAYER`: you'll see FENCE, ROADS, PV-TRACKERS, DC-COMBINERS, INVERTER-SKIDS, SUBSTATION, BESS, YARD, TEXT.
3. Click one tracker, right-click → **Select Similar**, then open Properties (`Ctrl+1`). The
   dropdown at the top shows the count: **Polyline (600)**, matching the takeoff. Press `Esc` to clear.
4. Type `DIST` and click two neighbouring tracker centres → about **6.51 m** (the pitch).
5. Type `AREA`, choose Object, click the fence → about **487,000 m²** (48.7 ha).

**Real-parcel exercise (Google Earth Pro):**
1. Find farmland in southern Ontario (Haldimand, Norfolk or Chatham-Kent have existing solar farms).
2. Use the **Ruler → Polygon** tool to outline a parcel and read its perimeter and area.
3. In AutoCAD, draw that parcel outline on a new PARCEL layer, then MOVE/ROTATE the blocks to fit inside it.
4. Put the parcel's centre coordinates into `SITE` in `basis.py`, delete `out/tmy.csv`, and rerun.

**Exercise.** Try `TRACKER["gcr"]` = 0.30 and 0.45.

<details><summary>Answer</summary>

| GCR | MWh/yr | Fenced ha |
|---|---|---|
| 0.30 | 43,381 (+1.4%) | 56.4 |
| 0.35 | 42,782 | 48.7 |
| 0.45 | 41,453 (−3.1%) | 38.4 |

Tighter rows lose energy to backtracking but save about 10 ha. Land cost and lease terms usually decide.
</details>

**Challenge:** the yard takes a whole block cell (~7 ha) but the substation and BESS need well
under 1 ha. Change `layout.py` so the yard is smaller and the fence shrinks. A real designer would make this fix.

---

## Lesson 6: DC collection, voltage drop and the single-line diagram

**Goal:** size the cable path from module to grid.

**Concept.** Current flowing through a cable loses voltage (and energy) to resistance:

```
VD% = 2 × L × I × R ÷ V × 100      (×2 because current goes out and back)

Feeder:  2 × 0.187 km × 323.0 A × 0.139 Ω/km ÷ 1,078 V = 1.56%
String:  2 × 0.071 km ×  13.46 A × 4.07 Ω/km ÷ 1,078 V = 0.72%
Total worst case = 2.28%  (limit 3%)
```

Lengths come from the layout (worst-case run), not guesses. The feeder carries 24 strings, so
it needs a much bigger conductor than the string wire.

The **single-line diagram** shows the power path: strings → combiners → inverter (DC to AC, 0.6 kV) →
skid transformer (to 34.5 kV) → collector bus → main power transformer (to 115 kV) → revenue meter →
point of interconnection. Voltage is stepped up because the same power at higher voltage means
lower current, so less cable loss.

**In the code:** `voltage_drop()` and `plot_sld()` in [electrical.py](electrical.py).

**Look at:** [out/single_line_diagram.png](out/single_line_diagram.png).

**Exercise.** Change `FEEDER_WIRE` to `dict(name="350 kcmil Al", ohm_per_km=0.1985)` and run.

<details><summary>Answer</summary>

Total voltage drop becomes **2.95%**. The QA check still passes, but with only 0.05% margin:
any longer run or hotter conductor would push it over 3%. Smaller cable is cheaper, but the energy
lost over 30+ years costs more, so 500 kcmil stays. (With the earlier generic module values, this
same change failed at 3.02%: the real module's lower current and higher voltage bought the margin.)
</details>

<details><summary>Check yourself: where does ETAP fit in?</summary>

ETAP takes the single-line diagram and runs AC studies: load flow, short circuit, protection
coordination and arc flash. That's the next step after a conceptual SLD like this one.
</details>

---

## Lesson 7: Quantity takeoff

**Goal:** know where every quantity comes from.

**Concept.** The takeoff is the bill of quantities that estimators price and procurement buys
from. Every line must trace back to a calc or a drawing.

| Item | Comes from |
|---|---|
| Modules, strings, trackers | `plant_sizing()` |
| Piles | trackers × 10 (assumed; geotech sets the real number) |
| Combiners, cable lengths, roads, fence | measured from the layout |
| BESS containers, PCS | `bess_sizing()` |

**Look at:** [out/takeoff.csv](out/takeoff.csv) (opens in Excel).

**Exercise.** In Excel, add a unit-cost column using public numbers (search for NREL's annual
"Solar Photovoltaic System and Energy Storage Cost Benchmarks") and total the cost. Label it as a rough estimate.

---

## Lesson 8: Battery storage (BESS)

**Goal:** speak confidently about MW vs MWh.

**Concept.**
- **MW** = how fast the battery charges or discharges (power). **MWh** = how much it holds (energy).
- 10 MW × 4 h = **40 MWh usable**. Not all nameplate energy is usable (depth-of-discharge limits,
  auxiliary loads, degradation reserve), so we assume 90% usable: 40 ÷ 0.9 = 44.4 MWh → **9 containers × 5 MWh**.
- The **PCS** (power conversion system) is the battery's inverter: 10 MW ÷ 2.5 MW = 4 units.
- **AC-coupled** (ours) = the battery has its own inverters and connects on the AC bus. **DC-coupled**
  = it shares the solar inverters and can store energy that would otherwise be clipped.
- Why add storage in Ontario: solar peaks at midday, but demand peaks in the evening. Storage shifts that energy to when it's worth more.

**In the code:** `bess_sizing()` in [electrical.py](electrical.py).

**Exercise.** Set `BESS["hours"] = 2`.

<details><summary>Answer</summary>

20 MWh usable → 20 ÷ 0.9 ÷ 5 = 4.4 → **5 containers**. The PCS count stays at 4, because power didn't change.
</details>

---

## Lesson 9: QA/QC

**Goal:** check your own work before anyone else does.

**Automated (in `main.py`)**: 8 checks, and the run fails loudly if any fail. Note the
*cross-check* type: the tracker count in the drawing must equal the tracker count in the calc.
Two independent paths agreeing is strong evidence both are right.

**Manual checklist (things code can't check):**
- [ ] Datasheet values match the exact revision of the datasheet you cite
- [ ] Design temperatures come from a named source (ASHRAE, Environment Canada)
- [ ] Code references are the current edition (CSA C22.1 Section 64)
- [ ] Drawing counts in AutoCAD match the takeoff
- [ ] Units consistent (m vs ft, kW vs MW, AC vs DC)
- [ ] Setbacks from roads, property lines, wetlands, watercourses (municipal and conservation authority rules)
- [ ] Assumptions labelled as assumptions on every deliverable

**Exercise.** Add one more cross-check to `main.py`: the combiner boxes drawn in the layout
(`len(lay["rects"]["DC-COMBINERS"])`) must equal the strings divided by 24, rounded up.
(Hint: `import math` at the top, then copy the format of the tracker-count check.) Both should be 75.

---

## Lesson 10: PVsyst cross-check (start your trial here)

**Goal:** reproduce the system in the industry-standard tool and explain the difference.

Menu names vary slightly by PVsyst version, so follow them in spirit:

1. **Project design → Grid-connected** → new project. Set the site by coordinates (42.95, −79.85).
   Use PVsyst's built-in Meteonorm weather (a different source from our ERA5, which is the point).
2. **Project settings:** set the lower design temperature for the absolute voltage limit to −30.6 °C, to match `T_MIN_C`.
3. **Orientation:** tracking, horizontal axis, north-south, with backtracking. Pitch 6.51 m, collector width 2.28 m, rotation limits ±60°.
4. **System:** pick a ~580 W TOPCon module from the database (or enter ours), and a ~4 MW central inverter.
   25 modules in series, 1,800 strings, 5 inverters. PVsyst will warn you if string voltages break limits. Compare with Lesson 2.
5. **Detailed losses:** soiling 2%, availability 1%; match the others in `LOSSES` as closely as PVsyst allows.
6. **Simulate** and open the report. Compare specific yield and the loss diagram with [out/loss_waterfall.png](out/loss_waterfall.png).
7. Write the result in the README: "PVsyst (Meteonorm): X kWh/kWp vs pvlib (ERA5): 1,639 kWh/kWp (−Y%), mainly due to …"

Expect PVsyst to come out lower. Explaining *why* is worth more than matching exactly.

---

## Lesson 11: Publish and reach out

1. Sign in to GitHub from the terminal (one time):
```bash
gh auth login
```
2. Create the repository and push (run these in the project folder):
```bash
git init
```
```bash
git add .
```
```bash
git commit -m "Conceptual 20 MWac solar + BESS design"
```
```bash
gh repo create solar-bess-conceptual-design --public --source . --push
```
3. On your GitHub profile, **pin** the repository.
4. Attach `out/project_sheet.pdf` to your application follow-up / LinkedIn message.

---

## Interview prep: questions you can now answer

1. **Walk me through string sizing.** Cold Voc sets the maximum, hot Vmp sets the minimum; 25 modules, 1,486 V at −30.6 °C (ASHRAE 50-year low, Hamilton). The −21.7 °C mean extreme gives the same 25.
2. **Why DC/AC 1.3?** More energy per inverter dollar; 1.3% clipping; the trade-off table in Lesson 3.
3. **Tracker or fixed?** +15% energy annually, but fixed wins on winter days; trackers cost more and need stow strategies for snow and wind.
4. **How do you know your energy number is right?** I don't fully trust it: ERA5 reads high. I sanity-checked it, flagged it, and cross-checked in PVsyst.
5. **What's GCR?** Panel width ÷ row pitch; it trades land against shading/backtracking loss (Lesson 5 table).
6. **What changes on a real site?** Parcel shape, setbacks, wetlands, topography and grading (Civil 3D), geotech for piles, interconnection voltage and capacity.
7. **What does your takeoff feed?** Estimating and procurement; every line traces to a calc or drawing.
8. **What would you do next?** Real datasheets and parcel, PVsyst with Meteonorm, conductor ampacity per CEC, then AC studies in ETAP.
