from pathlib import Path
import shutil
import numpy as np

from paths import DATA_DIR, MODELS_DIR

project_root = MODELS_DIR  # all SFINCS model folders live side by side here

source_event = project_root / "ahr_river_v03_Marg_additionalsrc_velocity_100m_cutpolygon_warmstart"

static_files = ["sfincs.dep", "sfincs.msk", "sfincs.ind", "sfincs.src",
                "sfincs.obs", "sfincs_subgrid.nc"]

src_names = ["Kreuzberg", "Denn", "Kirmutscheid", "Muesch",
             "new1", "Niederadenau", "new2"]

MAINSTEM = "Kirmutscheid"                          # mean 70.0 m3/s, ~4x the next largest
SMALLEST_TRIBUTARIES = ["new1", "Niederadenau", "new2"]   # mean 10.4/10.5/5.0 m3/s
SMALLEST_TRIBUTARY = "new2"                        # mean 5.0 m3/s, smallest of the three

# All scenarios reuse the single existing baseline spinup restart unchanged (project convention:
# a custom per-scenario spinup would confound the forcing perturbation with a different starting
# water state; see setup_tributary_variation_runs.py). The baseline event sfincs.inp already
# points rstfile there.


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

zero_all_but_mainstem = {n: 0.0 for n in src_names if n != MAINSTEM}
zero_all_but_smallest = {n: 0.0 for n in src_names if n != SMALLEST_TRIBUTARY}

scenarios = [
    ("baseline_1x", {}),
    ("tributaries_0x", {n: 0.0 for n in SMALLEST_TRIBUTARIES}),
    ("tributaries_2x", {n: 2.0 for n in SMALLEST_TRIBUTARIES}),
    ("mainstem_0x", {MAINSTEM: 0.0}),
    ("mainstem_2x", {MAINSTEM: 2.0}),
    ("only_mainstem", zero_all_but_mainstem),
    ("only_smallest_tributary", zero_all_but_smallest),
]


def print_peaks(dis):
    print("  peak Q per source (m3/s):")
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
    print_peaks(dis)
    return event_dir


print("\n=== Source-group scenarios ===")
for tag, factors in scenarios:
    print(f"\n--- {tag}: {factors if factors else '(unchanged baseline)'} ---")
    dis = apply_scale(event_dis, factors)
    build_event(tag, dis)

print(f"\nDone. Created {len(scenarios)} event folders (all pointing at the shared baseline spinup).")
