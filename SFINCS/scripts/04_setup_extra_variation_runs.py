from pathlib import Path
from datetime import datetime, timedelta
import shutil
import numpy as np

trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz

from paths import DATA_DIR, MODELS_DIR

project_root = MODELS_DIR  # all SFINCS model folders live side by side here

source_event = project_root / "ahr_river_v03_Marg_additionalsrc_velocity_100m_cutpolygon_warmstart"
source_spinup_dir_name = "spinup_additionalsrc_velocity_100m_cutpolygon"  # pre-flood baseline spinup

static_files = ["sfincs.dep", "sfincs.msk", "sfincs.ind", "sfincs.src",
                "sfincs.obs", "sfincs_subgrid.nc"]

src_names = ["Kreuzberg", "Denn", "Kirmutscheid", "Muesch",
             "new1", "Niederadenau", "new2"]

DT_EVENT = 900  # seconds, matches baseline event resolution

# Real flood-peak time, determined from the baseline event's own sfincs_map.nc (total
# domain water volume argmax = t=76h; wet-area argmax = t=77h, 1h apart -- using volume).
PEAK_HOUR = 76
POSTPEAK_DRAIN_DURATION_H = 450  # upper end of the user's suggested 350-450h range


def write_dis(path, times, q):
    lines = []
    for t, row in zip(times, q):
        q_str = "  ".join(f"{v:8.3f}" for v in row)
        lines.append(f"{t:12.1f}  {q_str}")
    path.write_text("\n".join(lines) + "\n")


def apply_shift(dis, shifts):
    """shifts: {src_name: shift_hours} (fractional hours allowed). Same method as
    setup_tributary_variation_runs.py: shift the flood perturbation p(t)=q(t)-baseflow via
    edge-clamped interpolation, then rescale to preserve total added volume."""
    shifted = dis.copy()
    t = dis[:, 0]
    for name, shift_h in shifts.items():
        idx = src_names.index(name) + 1
        q = dis[:, idx]
        b = q[0]
        p = q - b
        shift_s = shift_h * 3600
        p_shift_raw = np.interp(t - shift_s, t, p)
        vol_orig = trapz(p, t)
        vol_shift_raw = trapz(p_shift_raw, t)
        scale = vol_orig / vol_shift_raw if abs(vol_shift_raw) > 1e-9 else 1.0
        p_shift = p_shift_raw * scale
        shifted[:, idx] = np.maximum(b + p_shift, 0)
    return shifted


def set_inp_field(inp_text, field, new_line):
    lines = []
    replaced = False
    for line in inp_text.splitlines():
        if line.strip().startswith(field):
            lines.append(new_line)
            replaced = True
        else:
            lines.append(line)
    assert replaced, f"field '{field}' not found in inp"
    return "\n".join(lines) + "\n"


def get_inp_field(inp_text, field):
    line = [l for l in inp_text.splitlines() if l.strip().startswith(field)][0]
    return line.split("=", 1)[1].strip()


# --- Load the baseline event hydrograph and repair the NaN tail (once) ---
event_dis = np.loadtxt(source_event / "sfincs.dis")
for i in range(1, event_dis.shape[1]):
    col = event_dis[:, i]
    if np.isnan(col).any():
        col[np.isnan(col)] = col[~np.isnan(col)][-1]
assert not np.isnan(event_dis).any()

event_inp_template = (source_event / "sfincs.inp").read_text()
tref_dt = datetime.strptime(get_inp_field(event_inp_template, "tref"), "%Y%m%d %H%M%S")


# ============================================================
# 14b — desync2: direction-flipped desync, held-out test
# ============================================================
print("\n=== 14b: desync2 ===")
shifts_14b = {
    "Kirmutscheid": -10.0, "Kreuzberg": 4.5, "Denn": -9.5, "Muesch": 5.0,
    "new1": -2.0, "Niederadenau": 3.0, "new2": -2.5,
}
assert len(set(shifts_14b.values())) == len(shifts_14b), "duplicate shift hours in desync2"

dis_14b = apply_shift(event_dis, shifts_14b)
event_dir_14b = project_root / "ahr_river_v03_Marg_desync2_additionalsrc_velocity_100m_cutpolygon_warmstart"
event_dir_14b.mkdir(exist_ok=True)
for fname in static_files:
    shutil.copy2(source_event / fname, event_dir_14b / fname)
(event_dir_14b / "sfincs.inp").write_text(event_inp_template)
write_dis(event_dir_14b / "sfincs.dis", dis_14b[:, 0], dis_14b[:, 1:])
print(f"Event written: {event_dir_14b.name}")
print(f"  rstfile: {get_inp_field(event_inp_template, 'rstfile')}  (same shared pre-flood spinup)")
print("  peak Q per source (m3/s):")
for name, qmax in zip(src_names, dis_14b[:, 1:].max(axis=0)):
    print(f"    {name:14s} {qmax:8.1f}")


# ============================================================
# 16b — emptying_postpeak: catchment emptying from the real flood-peak state
# ============================================================
print("\n=== 16b: emptying_postpeak ===")

# --- Stage 1: mini spinup run that replays the real event up to PEAK_HOUR and dumps a restart ---
spinup_pp_dir = project_root / "spinup_postpeak_additionalsrc_velocity_100m_cutpolygon"
spinup_pp_dir.mkdir(exist_ok=True)
for fname in static_files:
    shutil.copy2(source_event / fname, spinup_pp_dir / fname)

peak_dt = tref_dt + timedelta(hours=PEAK_HOUR)
peak_str = peak_dt.strftime("%Y%m%d %H%M%S")

spinup_pp_inp = event_inp_template
spinup_pp_inp = set_inp_field(spinup_pp_inp, "tstop", f"tstop                = {peak_str}")
spinup_pp_inp = set_inp_field(spinup_pp_inp, "trstout", f"trstout              = {PEAK_HOUR * 3600}")
(spinup_pp_dir / "sfincs.inp").write_text(spinup_pp_inp)
# Same real event forcing up to the peak -- SFINCS stops at tstop, ignores the rest.
write_dis(spinup_pp_dir / "sfincs.dis", event_dis[:, 0], event_dis[:, 1:])
print(f"Postpeak spinup written: {spinup_pp_dir.name}")
print(f"  rstfile: {get_inp_field(spinup_pp_inp, 'rstfile')}  (pre-flood baseline spinup, replays real event)")
print(f"  tstop:   {peak_str}  (t={PEAK_HOUR}h, real flood peak per sfincs_map.nc total-volume argmax)")
expected_rst = f"sfincs.{peak_dt.strftime('%Y%m%d')}.{peak_dt.strftime('%H%M%S')}.rst"
print(f"  expected restart output: {expected_rst}")

# --- Stage 2: event folder, all discharges -> 0, starting from the peak restart ---
event_dir_16b = project_root / "ahr_river_v03_Marg_emptying_postpeak_additionalsrc_velocity_100m_cutpolygon_warmstart"
event_dir_16b.mkdir(exist_ok=True)
for fname in static_files:
    shutil.copy2(source_event / fname, event_dir_16b / fname)

duration_s = POSTPEAK_DRAIN_DURATION_H * 3600
tstop_16b_dt = peak_dt + timedelta(hours=POSTPEAK_DRAIN_DURATION_H)

inp_16b = event_inp_template
inp_16b = set_inp_field(inp_16b, "tref", f"tref                 = {peak_str}")
inp_16b = set_inp_field(inp_16b, "tstart", f"tstart               = {peak_str}")
inp_16b = set_inp_field(inp_16b, "tstop", f"tstop                = {tstop_16b_dt.strftime('%Y%m%d %H%M%S')}")
inp_16b = set_inp_field(inp_16b, "rstfile",
                         f"rstfile              = ../spinup_postpeak_additionalsrc_velocity_100m_cutpolygon/{expected_rst}")
(event_dir_16b / "sfincs.inp").write_text(inp_16b)

times_16b = np.arange(0, duration_s + DT_EVENT, DT_EVENT)
drain_dis_16b = np.zeros((len(times_16b), event_dis.shape[1]))
drain_dis_16b[:, 0] = times_16b
write_dis(event_dir_16b / "sfincs.dis", drain_dis_16b[:, 0], drain_dis_16b[:, 1:])

print(f"Event written: {event_dir_16b.name}")
print(f"  rstfile: {get_inp_field(inp_16b, 'rstfile')}")
print(f"  tref/tstart: {peak_str}   tstop: {tstop_16b_dt.strftime('%Y%m%d %H%M%S')}  ({POSTPEAK_DRAIN_DURATION_H}h)")

print("\nDone. Run order: spinup_postpeak_... first, then desync2 and emptying_postpeak (any order).")
