"""Design basis: every input for the project lives here. Change a value, rerun main.py.

Conceptual level only. Module and inverter values come from the manufacturers' published
datasheets (sources below); the site is still a placeholder parcel.
"""

# --- Site -------------------------------------------------------------------
SITE = dict(name="Haldimand County, ON", lat=42.95, lon=-79.85, alt=190)  # placeholder parcel
# Climate: ASHRAE 2017 Fundamentals, HAMILTON INTL (WMO 712630, ~25 km from site), 1999-2014.
#   Extreme annual min DB: mean -21.7 C, 50-year return -30.6 C. Extreme annual max DB: mean 32.9 C.
T_MIN_C = -30.6      # design low for max Voc: 50-year return min (conservative vs the -21.7 C mean)
T_CELL_MAX_C = 70.0  # hot cell for min Vmp: ~35 C ambient (above 32.9 C extreme mean) + 35 C rise

# --- PV module: Canadian Solar CS6W-580TB-AG (TOPBiHiKu6, bifacial TOPCon, 144 half-cells, 1500 V)
# Source: CSI Solar datasheet "PV Module Product Datasheet V2.1_EN", Apr 2025, STC values.
# Bifaciality 80% on the datasheet; this model is monofacial (rear-side gain not counted).
MODULE = dict(
    p_w=580, voc=52.2, vmp=43.1, isc=13.93, imp=13.46,
    beta_voc=-0.0025, gamma_pmp=-0.0029, alpha_isc=0.0005,  # temperature coefficients, per deg C
    length_m=2.278, width_m=1.134,
)

# --- Inverter: SMA Sunny Central SC 4000 UP-US (1500 V central, on an MV skid) ------
# Source: SMA datasheet SCXXXXUP-US-DS-en-27. 4000 kVA at 35 C (3600 kVA at 50 C), 600 V AC,
# CEC efficiency 98.5%. Standard operating range is -25 C to 60 C; the -37 C cold-climate option
# is needed here because the 50-year low is -30.6 C.
SYSTEM_VMAX = 1500   # V DC, max system voltage (module and inverter both rated 1500 V)
INVERTER = dict(p_ac_kw=4000, blocks=5, mppt_min=880, mppt_max=1325, eta=0.985, v_ac_kv=0.60)
DC_AC_TARGET = 1.30

# --- Racking: 1P single-axis tracker, north-south axis, backtracking ------------
TRACKER = dict(strings=3, max_angle=60, gcr=0.35, piles=10, module_gap_m=0.02, motor_gap_m=1.0)
FIXED_TILT = 30      # trade-study alternative (deg, south-facing)

# --- Layout: each block = two tiers of trackers with an E-W road between them ----
ROAD_W = 6.0       # m, internal access road width
BLOCK_GAP = 10.0     # m, between blocks (road + clearance)
SETBACK = 15.0       # m, fence to nearest array (perimeter road inside)
GRID_COLS = 2        # blocks per row; the last grid cell is the substation / BESS / laydown yard

# --- DC collection ------------------------------------------------------------
STRINGS_PER_COMBINER = 24
STRING_WIRE = dict(name="10 AWG Cu PV wire", ohm_per_km=4.07)   # DC resistance at 75 C
FEEDER_WIRE = dict(name="500 kcmil Al", ohm_per_km=0.139)      # DC resistance at 75 C
VD_LIMIT_PCT = 3.0   # max total DC voltage drop, worst-case circuit

# --- Energy model losses (percent, PVWatts categories) ----------------------------
LOSSES = dict(soiling=2, shading=1, snow=3, mismatch=1, wiring=2, connections=0.5,
              lid=1, nameplate_rating=0.5, age=0, availability=1)

# --- AC side / grid (assumed until an interconnection study says otherwise) -------
MV_KV = 34.5         # collector system voltage
POI_KV = 115         # point of interconnection (transmission)
MPT_MVA = 33         # main power transformer (top rating)
BESS = dict(mw=10, hours=4, usable=0.90, container_mwh=5.0, pcs_mw=2.5)  # AC-coupled on the MV bus

AUTHOR = "Andres Delascio"
