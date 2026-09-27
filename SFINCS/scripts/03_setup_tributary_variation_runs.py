from pathlib import Path
from datetime import datetime, timedelta
import shutil
import numpy as np

trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz

from paths import DATA_DIR, MODELS_DIR

project_root = MODELS_DIR  # all SFINCS model folders live side by side here

source_event = project_root / "ahr_river_v03_Marg_additionalsrc_velocity_100m_cutpolygon_warmstart"

static_files = ["sfincs.dep", "sfincs.msk", "sfincs.ind", "sfincs.src",
                "sfincs.obs", "sfincs_subgrid.nc"]

src_names = ["Kreuzberg", "Denn", "Kirmutscheid", "Muesch",
             "new1", "Niederadenau", "new2"]

# All scenarios reuse the single existing baseline spinup restart unchanged (confirmed with user:
# a custom per-scenario spinup would confound the forcing perturbation with a different starting
# water state). The baseline event sfincs.inp already points rstfile there.
DT_EVENT = 900          # seconds, matches baseline event resolution
DRAIN_DURATION_H = 300  # alldrain event length (upper end of the suggested 240-300h range)


def write_dis(path, times, q):
    """Write a SFINCS .dis file: q has shape (ntimes, nsrc)."""
    lines = []
    for t, row in zip(times, q):
        q_str = "  ".join(f"{v:8.3f}" for v in row)
        lines.append(f"{t:12.1f}  {q_str}")
    path.write_text("\n".join(lines) + "\n")


def apply_scale(dis, factors):
    """factors: {src_name: factor}. Only listed columns are scaled; rest untouched."""
    scaled = dis.copy()
    for name, factor in factors.items():
        idx = src_names.index(name) + 1
        scaled[:, idx] *= factor
    return scaled


def apply_shift(dis, shifts):
    """shifts: {src_name: shift_hours}. Shift the flood perturbation p(t) = q(t) - baseflow via
    interpolation (edge-clamped beyond the domain), then rescale so total added volume is
    preserved. Only listed columns are touched."""
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


# --- Load the baseline event hydrograph and repair the NaN tail (once) ---
event_dis = np.loadtxt(source_event / "sfincs.dis")
for i in range(1, event_dis.shape[1]):
    col = event_dis[:, i]
    if np.isnan(col).any():
        n_nan = int(np.isnan(col).sum())
        col[np.isnan(col)] = col[~np.isnan(col)][-1]
        print(f"Repaired {n_nan} NaN(s) in event dis column '{src_names[i - 1]}' "
              f"(forward-filled last valid value {col[-1]:.3f})")
assert not np.isnan(event_dis).any(), "NaNs left in event dis after repair"

event_inp_template = (source_event / "sfincs.inp").read_text()
assert "rstfile" in event_inp_template

# --- Scenario definitions ---
scale_scenarios = [
    ("kirmutscheid0x", {"Kirmutscheid": 0.0}),
    ("kirmutscheid2x", {"Kirmutscheid": 2.0}),
    ("kreuzberg0x", {"Kreuzberg": 0.0}),
    ("kreuzberg2x", {"Kreuzberg": 2.0}),
    ("niederadenau0x", {"Niederadenau": 0.0}),
    ("niederadenau2x", {"Niederadenau": 2.0}),
    ("new2_0x", {"new2": 0.0}),
    ("new2_2x", {"new2": 2.0}),
    ("denn2x", {"Denn": 2.0}),
    ("muesch2x", {"Muesch": 2.0}),
    ("new1_2x", {"new1": 2.0}),
    ("kirmutscheid15x_kreuzberg05x", {"Kirmutscheid": 1.5, "Kreuzberg": 0.5}),
]

shift_scenarios = [
    ("kirmutscheid_shiftm12h", {"Kirmutscheid": -12}),
    ("kirmutscheid_shiftp12h", {"Kirmutscheid": 12}),
    ("alldesync", {"Kirmutscheid": 8, "Kreuzberg": -3, "Denn": 7, "Muesch": -6,
                   "new1": 3, "Niederadenau": -2, "new2": 1}),
]

# sanity check: no accidental hour collisions across desync locations
desync_hours = list(shift_scenarios[-1][1].values())
assert len(desync_hours) == len(set(desync_hours)), "duplicate shift hours in alldesync"


def print_peaks(tag, dis):
    print(f"  peak Q per source (m3/s):")
    for name, qmax in zip(src_names, dis[:, 1:].max(axis=0)):
        print(f"    {name:14s} {qmax:8.1f}")


def build_event(tag, dis):
    event_dir = project_root / f"ahr_river_v03_Marg_{tag}_additionalsrc_velocity_100m_cutpolygon_warmstart"
    event_dir.mkdir(exist_ok=True)
    for fname in static_files:
        shutil.copy2(source_event / fname, event_dir / fname)
    (event_dir / "sfincs.inp").write_text(event_inp_template)
    write_dis(event_dir / "sfincs.dis", dis[:, 0], dis[:, 1:])
    rst_line = [l for l in event_inp_template.splitlines() if "rstfile" in l][0]
    print(f"Event written: {event_dir.name}")
    print(f"  {rst_line.strip()}")
    print_peaks(tag, dis)
    return event_dir


print("\n=== Scale scenarios ===")
for tag, factors in scale_scenarios:
    print(f"\n--- {tag}: {factors} ---")
    dis = apply_scale(event_dis, factors)
    build_event(tag, dis)

print("\n=== Shift scenarios ===")
for tag, shifts in shift_scenarios:
    print(f"\n--- {tag}: {shifts} ---")
    dis = apply_shift(event_dis, shifts)
    build_event(tag, dis)

print("\n=== Drain scenario ===")
tag = "alldrain"
print(f"\n--- {tag}: all discharges -> 0, {DRAIN_DURATION_H}h ---")
duration_s = DRAIN_DURATION_H * 3600
times = np.arange(0, duration_s + DT_EVENT, DT_EVENT)
drain_dis = np.zeros((len(times), event_dis.shape[1]))
drain_dis[:, 0] = times

tref_line = [l for l in event_inp_template.splitlines() if l.strip().startswith("tref")][0]
tref_str = tref_line.split("=", 1)[1].strip()
tref_dt = datetime.strptime(tref_str, "%Y%m%d %H%M%S")
tstop_dt = tref_dt + timedelta(hours=DRAIN_DURATION_H)
tstop_str = tstop_dt.strftime("%Y%m%d %H%M%S")

drain_inp_lines = []
for line in event_inp_template.splitlines():
    if line.strip().startswith("tstop"):
        drain_inp_lines.append(f"tstop                = {tstop_str}")
    else:
        drain_inp_lines.append(line)
drain_inp = "\n".join(drain_inp_lines) + "\n"

event_dir = project_root / f"ahr_river_v03_Marg_{tag}_additionalsrc_velocity_100m_cutpolygon_warmstart"
event_dir.mkdir(exist_ok=True)
for fname in static_files:
    shutil.copy2(source_event / fname, event_dir / fname)
(event_dir / "sfincs.inp").write_text(drain_inp)
write_dis(event_dir / "sfincs.dis", drain_dis[:, 0], drain_dis[:, 1:])
rst_line = [l for l in drain_inp.splitlines() if "rstfile" in l][0]
tstop_written = [l for l in drain_inp.splitlines() if l.strip().startswith("tstop")][0]
print(f"Event written: {event_dir.name}")
print(f"  {rst_line.strip()}")
print(f"  {tstop_written.strip()}")

n_scenarios = len(scale_scenarios) + len(shift_scenarios) + 1
print(f"\nDone. Created {n_scenarios} event folders (all pointing at the shared baseline spinup).")
