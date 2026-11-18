"""Energy model: typical-year weather from PVGIS, a pvlib PVWatts-style simulation, and energy charts."""
import calendar

import matplotlib.pyplot as plt
import pandas as pd
import pvlib

import basis as b

LOCAL_TZ = "Etc/GMT+5"  # Eastern Standard Time, no daylight saving (POSIX sign convention)


def weather(cache):
    """Hourly typical-meteorological-year data. Downloaded once from PVGIS, then read from cache."""
    if not cache.exists():
        data, meta = pvlib.iotools.get_pvgis_tmy(b.SITE["lat"], b.SITE["lon"])
        # PVGIS stamps each hour at its start; shift to the interval centre so sun position matches.
        data.index += pd.Timedelta(hours=meta["inputs"]["location"]["irradiance_time_offset"])
        data.to_csv(cache)
    return pd.read_csv(cache, index_col=0, parse_dates=True)


def tracker_mount():
    return pvlib.pvsystem.SingleAxisTrackerMount(
        axis_azimuth=180, max_angle=b.TRACKER["max_angle"], gcr=b.TRACKER["gcr"], backtrack=True)


def fixed_mount():
    return pvlib.pvsystem.FixedMount(surface_tilt=b.FIXED_TILT, surface_azimuth=180)


def simulate(mount, p, wx):
    """One typical year, hourly. Returns pvlib ModelChain results (POA, cell temp, DC, AC ...)."""
    array = pvlib.pvsystem.Array(
        mount, module_parameters=dict(pdc0=p["dc_kw"] * 1e3, gamma_pdc=b.MODULE["gamma_pmp"]),
        temperature_model_parameters=pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_glass"])
    system = pvlib.pvsystem.PVSystem(
        arrays=[array], losses_parameters=b.LOSSES,
        inverter_parameters=dict(pdc0=p["ac_kw"] * 1e3 / b.INVERTER["eta"], eta_inv_nom=b.INVERTER["eta"]))
    mc = pvlib.modelchain.ModelChain.with_pvwatts(
        system, pvlib.location.Location(b.SITE["lat"], b.SITE["lon"], altitude=b.SITE["alt"]))
    mc.run_model(wx)
    return mc.results


def ac_mw(r):
    return r.ac.clip(lower=0) / 1e6


def loss_steps(r, p, wx):
    """Energy (MWh/yr) at each step from sunlight to the grid, PVsyst-style."""
    mw = p["dc_kw"] / 1000
    poa = r.total_irrad["poa_global"].clip(lower=0)
    eff = r.effective_irradiance.clip(lower=0)
    dc_after = r.dc.clip(lower=0) / 1e6                          # after system losses
    dc_before = dc_after / (1 - pvlib.pvsystem.pvwatts_losses(**b.LOSSES) / 100)
    ac = ac_mw(r)
    clip = (dc_after * b.INVERTER["eta"] - p["ac_kw"] / 1000).clip(lower=0)  # approx, ignores part-load curve
    ghi_e, poa_e, eff_e = (mw * x / 1000 for x in (wx["ghi"].clip(lower=0), poa, eff))
    return [
        ("Sunlight on flat ground\n(GHI x DC nameplate)", ghi_e.sum()),
        ("Tracking gain", poa_e.sum() - ghi_e.sum()),
        ("Reflection\n(angle of incidence)", eff_e.sum() - poa_e.sum()),
        ("Cell temperature", dc_before.sum() - eff_e.sum()),
        ("Soiling, snow, wiring,\nmismatch, availability", dc_after.sum() - dc_before.sum()),
        ("Inverter clipping", -clip.sum()),
        ("Inverter efficiency", ac.sum() - dc_after.sum() + clip.sum()),
        ("AC to grid", ac.sum()),
    ]


def plot_waterfall(steps, path):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    total = 0
    for i, (label, val) in enumerate(steps):
        if i in (0, len(steps) - 1):
            ax.bar(i, val, color="#5B7DB1")
            ax.text(i, val, f"{val:,.0f}", ha="center", va="bottom", fontsize=9)
            total = val
            continue
        ax.bar(i, abs(val), bottom=min(total, total + val), color="#43A047" if val > 0 else "#E53935")
        ax.text(i, max(total, total + val), f"{val / total:+.1%}", ha="center", va="bottom", fontsize=9)
        total += val
    ax.set_xticks(range(len(steps)), [label for label, _ in steps], fontsize=8)
    ax.set(ylabel="Energy (MWh/yr)", title="Where the energy goes: sunlight to grid (single-axis tracker)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_monthly(tracker_ac, fixed_ac, p, path):
    monthly = pd.DataFrame({"Single-axis tracker": tracker_ac, f"Fixed tilt {b.FIXED_TILT} deg": fixed_ac})
    monthly = monthly.tz_convert(LOCAL_TZ)
    monthly = monthly.groupby(monthly.index.month).sum()
    ax = monthly.plot.bar(figsize=(9, 4.5), rot=0, color=["#E8A33D", "#5B7DB1"], width=0.8)
    ax.set_xticklabels(calendar.month_abbr[1:])
    ax.set(xlabel="", ylabel="AC energy (MWh)",
           title=f"Monthly energy, {p['ac_kw'] / 1000:.0f} MWac / {p['dc_kw'] / 1000:.1f} MWdc, {b.SITE['name']}")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def plot_daily(trk, fix, p, wx, path):
    """Sunniest June day vs sunniest December day: tracker shape, fixed shape, and clipping."""
    ghi = wx["ghi"].tz_convert(LOCAL_TZ)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, month in zip(axes, (6, 12)):
        day = str(ghi[ghi.index.month == month].resample("D").sum().idxmax().date())

        def sel(series):
            return series.tz_convert(LOCAL_TZ).loc[day]

        hours = sel(ac_mw(trk)).index.hour + 0.5
        unclipped = sel(trk.dc.clip(lower=0) / 1e6 * b.INVERTER["eta"])
        ax.fill_between(hours, sel(ac_mw(trk)), unclipped, where=unclipped > sel(ac_mw(trk)) + 0.05,
                        color="#E53935", alpha=0.3, label="Clipped (DC/AC > 1)")
        ax.plot(hours, sel(ac_mw(trk)), color="#E8A33D", lw=2.5, label="Single-axis tracker")
        ax.plot(hours, sel(ac_mw(fix)), color="#5B7DB1", lw=2.5, label=f"Fixed tilt {b.FIXED_TILT} deg")
        ax.axhline(p["ac_kw"] / 1000, color="gray", ls="--", lw=1, label="Inverter AC limit")
        ax.set(title=f"Sunniest {calendar.month_name[month]} day", xlabel="Hour (EST)", xlim=(4, 20))
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("AC power (MW)")
    axes[0].legend(fontsize=8.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
