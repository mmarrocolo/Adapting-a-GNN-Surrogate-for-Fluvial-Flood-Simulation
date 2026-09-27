from pathlib import Path
import shutil
import numpy as np

from paths import DATA_DIR, MODELS_DIR

project_root = MODELS_DIR  # all SFINCS model folders live side by side here

# Baseline (factor 1.0) folders — the source of truth for all scaled runs
source_spinup = project_root / "spinup_additionalsrc_velocity_100m_cutpolygon"
source_event  = project_root / "ahr_river_v03_Marg_additionalsrc_velocity_100m_cutpolygon_warmstart"

static_files = ["sfincs.dep", "sfincs.msk", "sfincs.ind", "sfincs.src",
                "sfincs.obs", "sfincs_subgrid.nc"]

src_names = ["Kreuzberg", "Denn", "Kirmutscheid", "Muesch",
             "new1", "Niederadenau", "new2"]

# Spinup baseflow (m3/s), same order as sfincs.src / src_names
baseflow_q = np.array([0.461, 2.111, 2.780, 0.645, 0.100, 0.100, 0.100])
spinup_dt = 3600
spinup_duration = 518400  # 6 days, must match tstop - tref in the spinup inp

factors = [0.5, 0.75, 1.25, 1.5, 2.0, 3.0]  # 1.0 = the baseline event itself

def write_dis(path, times, q):
    """Write a SFINCS .dis file: q has shape (ntimes, nsrc)."""
    lines = []
    for t, row in zip(times, q):
        q_str = "  ".join(f"{v:8.3f}" for v in row)
        lines.append(f"{t:12.1f}  {q_str}")
    path.write_text("\n".join(lines) + "\n")


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

for factor in factors:
    suffix = f"q{int(round(factor * 100)):03d}"  # 0.5 -> "q050"
    print(f"\n=== factor {factor} ({suffix}) ===")

    # ---------------- Spinup folder ----------------
    spinup_dir = project_root / f"spinup_additionalsrc_velocity_100m_cutpolygon_{suffix}"
    spinup_dir.mkdir(exist_ok=True)

    for fname in static_files:
        shutil.copy2(source_spinup / fname, spinup_dir / fname)
    # inp is identical for all factors: reuse the validated 6-day baseline
    shutil.copy2(source_spinup / "sfincs.inp", spinup_dir / "sfincs.inp")

    times = np.arange(0, spinup_duration + spinup_dt, spinup_dt)
    q_spinup = np.tile(baseflow_q * factor, (len(times), 1))
    write_dis(spinup_dir / "sfincs.dis", times, q_spinup)
    print(f"Spinup written: {spinup_dir.name}")

    # ---------------- Event folder ----------------
    event_dir = project_root / (
        f"ahr_river_v03_Marg_additionalsrc_velocity_100m_cutpolygon_warmstart_{suffix}"
    )
    event_dir.mkdir(exist_ok=True)

    for fname in static_files:
        shutil.copy2(source_event / fname, event_dir / fname)

    # Point rstfile at the matching scaled spinup
    inp = event_inp_template.replace(
        "../spinup_additionalsrc_velocity_100m_cutpolygon/",
        f"../spinup_additionalsrc_velocity_100m_cutpolygon_{suffix}/",
    )
    assert f"_{suffix}/" in inp, "rstfile replacement failed — check baseline inp"
    (event_dir / "sfincs.inp").write_text(inp)

    scaled = event_dis.copy()
    scaled[:, 1:] *= factor
    write_dis(event_dir / "sfincs.dis", scaled[:, 0], scaled[:, 1:])
    print(f"Event written:  {event_dir.name}")

    rst_line = [l for l in inp.splitlines() if "rstfile" in l][0]
    print(f"  {rst_line.strip()}")
    print(f"  peak Q per source (m3/s):")
    for name, qmax in zip(src_names, scaled[:, 1:].max(axis=0)):
        print(f"    {name:14s} {qmax:8.1f}")

print(f"\nDone. Created {2 * len(factors)} folders for factors {factors}.")
print("Run order: all spinups first, then the events.")
