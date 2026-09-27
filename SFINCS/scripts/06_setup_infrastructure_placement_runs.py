"""Strategic hydraulic-infrastructure placement runs for the Bad Neuenahr-Ahrweiler /
Heimersheim reach (the levee corridor already digitized in data/measures/levees_north.geojson
and levees_south.geojson, EPSG:32632).

Train set: 5 placement footprints x 2 crest heights (dz), all built by cutting the existing
north/south alignment with shapely (no new digitizing needed).
Held-out test set: bothbanks at dz=10m (crest height 2x beyond the trained max -- magnitude
extrapolation) and a gapped/partial-coverage levee (structural footprint not seen in training).

Dropped entirely (not train, not test): "setback" (offset-from-channel variant) and the
Niederadenau reservoir/storage measure -- excluded per user decision, not part of this dataset.

IMPORTANT: levees_north.geojson / levees_south.geojson were redrawn in QGIS to clear the river
channel (see channel_keepout_100m.geojson) -- this script always reads whatever is currently
saved there, so re-run it after any further redraw to keep every scenario in sync. (Caught one
round of drift already: a QGIS re-save after an earlier batch run left 12 of 13 scenarios stale
until this script was re-run against the then-current file.)

All runs reuse the shared warm-start spinup restart unchanged (same "hold initial state fixed,
vary only the structure" principle as the tributary/forcing variation scripts) -- only a
weir/thd geom or a vol grid layer is added on top of the baseline event.

Evaluation (not done here): windowed max-depth / wet-cell comparison against the baseline
(no-infrastructure) run, using the padded bbox of the levee reach as the comparison window:
  x: 363500-369900, y: 5598900-5600950 (EPSG:32632)
"""
from pathlib import Path
import shutil

import geopandas as gpd
import numpy as np
from shapely.ops import substring
from hydromt_sfincs import SfincsModel

from weir_grid_snap import snap_line_to_grid

from paths import DATA_DIR, MODELS_DIR

project_root = MODELS_DIR  # all SFINCS model folders live side by side here
source_event = project_root / "ahr_river_v03_Marg_additionalsrc_velocity_100m_cutpolygon_warmstart"
dep_subgrid = source_event / "subgrid" / "dep_subgrid.tif"

# flux-grid origin/spacing (from sfincs.inp: x0, y0, dx, dy) -- every weir line is snapped onto
# this grid as a leak-proof cell-side cut (see weir_grid_snap.py) before being handed to
# setup_structures, instead of the raw digitized line. Sampling which cells a smooth line passes
# through doesn't guarantee a continuous barrier (even a straight line can cross several
# east-west cell edges while staying inside one row, leaving that row's north-south edges
# unblocked); classifying every nearby cell by which side of the line it's on and blocking every
# disagreeing neighbor pair does.
_cfg = SfincsModel(root=str(source_event), mode="r", write_gis=False).config
X0, Y0, DX, DY = float(_cfg["x0"]), float(_cfg["y0"]), float(_cfg["dx"]), float(_cfg["dy"])
assert _cfg["rotation"] == 0, "snap_line_to_grid assumes an unrotated grid"

# static files shared by every weir scenario (unchanged -- copied, not rewritten by hydromt_sfincs).
# sfincs.dis is handled separately (NaN-repaired), see write_dis() below.
static_files = ["sfincs.dep", "sfincs.msk", "sfincs.ind", "sfincs.src",
                "sfincs.obs", "sfincs_subgrid.nc"]

# The source event's sfincs.dis has NaNs in its last 6 rows (final 1.5h) for the new1/
# Niederadenau/new2 columns (same issue setup_extra_variation_runs.py/setup_tributary_variation_runs.py
# forward-fill before writing). This build of sfincs.exe does NOT tolerate them -- it segfaults with
# an access violation right when it reaches that forcing window (~95-100% through the run), so every
# scenario here must get the repaired array, not a raw copy of sfincs.dis.
_event_dis = np.loadtxt(source_event / "sfincs.dis")
for _i in range(1, _event_dis.shape[1]):
    _col = _event_dis[:, _i]
    if np.isnan(_col).any():
        _col[np.isnan(_col)] = _col[~np.isnan(_col)][-1]
assert not np.isnan(_event_dis).any()


def write_dis(path):
    lines = []
    for row in _event_dis:
        q_str = "  ".join(f"{v:8.3f}" for v in row[1:])
        lines.append(f"{row[0]:12.1f}  {q_str}")
    path.write_text("\n".join(lines) + "\n")

measures_dir = DATA_DIR / "measures"
levees_north = gpd.read_file(measures_dir / "levees_north.geojson")
levees_south = gpd.read_file(measures_dir / "levees_south.geojson")
CRS = levees_north.crs
ln = levees_north.geometry.iloc[0]
ls = levees_south.geometry.iloc[0]

GAP_M = 300          # gap width for the held-out "gapped" test


def half(line, part):
    """First or second half of a line, split by arc length."""
    L = line.length
    return substring(line, 0, L / 2) if part == "up" else substring(line, L / 2, L)


def gapped_pair(line, gap_m=GAP_M):
    """Two segments with a gap_m-wide gap centered on the line's midpoint."""
    L = line.length
    return [substring(line, 0, L / 2 - gap_m / 2), substring(line, L / 2 + gap_m / 2, L)]


PLACEMENTS = {
    "bothbanks": lambda: [ln, ls],
    "northonly": lambda: [ln],
    "southonly": lambda: [ls],
    "upstream": lambda: [half(ln, "up"), half(ls, "up")],
    "downstream": lambda: [half(ln, "down"), half(ls, "down")],
}

DZ_TRAIN = [2, 5]


def make_weir_run(tag, lines, dz):
    sf = SfincsModel(root=str(source_event), mode="r", write_gis=False)
    snapped_lines = [snap_line_to_grid(line, X0, Y0, DX, DY) for line in lines]
    gdf = gpd.GeoDataFrame(geometry=snapped_lines, crs=CRS)
    sf.setup_structures(structures=gdf, stype="weir", dep=str(dep_subgrid), dz=dz, merge=False)

    out_root = project_root / f"{source_event.name}_infra_{tag}"
    out_root.mkdir(exist_ok=True)
    for fname in static_files:
        shutil.copy2(source_event / fname, out_root / fname)
    write_dis(out_root / "sfincs.dis")
    sf.set_root(str(out_root), mode="w+")
    sf.write_geoms()
    sf.write_config()

    zs = [pt[2] for line in sf.geoms["weir"].geometry for pt in line.coords]
    print(f"  {tag}: {len(gdf)} line(s), {sum(len(l.coords) for l in lines)} pts total, "
          f"crest z {min(zs):.1f}-{max(zs):.1f} m -> {out_root.name}")


# ============================================================
# Train: 5 placements x 2 crest heights
# ============================================================
print("=== Train: placement x crest-height sweep ===")
for name, lines_fn in PLACEMENTS.items():
    for dz in DZ_TRAIN:
        make_weir_run(f"{name}_dz{dz}m", lines_fn(), dz)

# ============================================================
# Held-out test 1: bothbanks at dz=10m -- crest height 2x beyond the trained max (magnitude
# extrapolation), same placement/site/mechanism as training so it isolates the height dimension
# ============================================================
print("\n=== Held-out test: bothbanks dz=10m (magnitude extrapolation) ===")
make_weir_run("bothbanks_dz10m", PLACEMENTS["bothbanks"](), 10)

# ============================================================
# Held-out test 2: gapped both-banks levee -- structural footprint not seen in training
# ============================================================
print("\n=== Held-out test: gapped (structural extrapolation) ===")
gap_lines = gapped_pair(ln) + gapped_pair(ls)
make_weir_run("gap_dz5m", gap_lines, 5)

print("\nDone. 10 train runs + 2 held-out test runs written. "
      "Run each via bin/SFINCS_.../sfincs.exe next (input generation only, not executed here).")
