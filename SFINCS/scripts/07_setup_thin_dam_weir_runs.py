"""Setup script for the Altenahr bridge-blockage scenarios (two candidate crossing locations,
data/measures/thin_dam.geojson and thin_dam2.geojson), representing a debris-clogged-bridge
failure mode from the real 2021 event -- a different site and structure mechanism than the
Ahrweiler/Heimersheim levee placement study (see setup_infrastructure_placement_runs.py).

WEIR structures with a high but finite crest height (dz) are used to block the channel,
instead of a levee with a low crest height.

DZ_SWEEP: crest heights to generate for each of the two candidate locations. dz=15m was the first
(stable) attempt; dz=20m added on request to see whether the backwater response saturates (same
question as the bothbanks dz5m vs dz10m comparison in the main placement study) or keeps growing.
"""
from pathlib import Path
import shutil

import geopandas as gpd
import numpy as np
from hydromt_sfincs import SfincsModel

from weir_grid_snap import snap_line_to_grid

from paths import DATA_DIR, MODELS_DIR

project_root = MODELS_DIR  # all SFINCS model folders live side by side here
source_event = project_root / "ahr_river_v03_Marg_additionalsrc_velocity_100m_cutpolygon_warmstart"
dep_subgrid = source_event / "subgrid" / "dep_subgrid.tif"
measures_dir = DATA_DIR / "measures"

_cfg = SfincsModel(root=str(source_event), mode="r", write_gis=False).config
X0, Y0, DX, DY = float(_cfg["x0"]), float(_cfg["y0"]), float(_cfg["dx"]), float(_cfg["dy"])
assert _cfg["rotation"] == 0

static_files = ["sfincs.dep", "sfincs.msk", "sfincs.ind", "sfincs.src",
                "sfincs.obs", "sfincs_subgrid.nc"]

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


SITES = {
    "thin_dam": "thin_dam.geojson",
    "thin_dam2": "thin_dam2.geojson",
}
DZ_SWEEP = [15, 20]


def make_weir_run(tag, geojson_name, dz):
    gdf_in = gpd.read_file(measures_dir / geojson_name)
    line = gdf_in.geometry.iloc[0]
    snapped = snap_line_to_grid(line, X0, Y0, DX, DY)

    sf = SfincsModel(root=str(source_event), mode="r", write_gis=False)
    gdf = gpd.GeoDataFrame(geometry=[snapped], crs=gdf_in.crs)
    sf.setup_structures(structures=gdf, stype="weir", dep=str(dep_subgrid), dz=dz, merge=False)

    out_root = project_root / f"{source_event.name}_infra_{tag}"
    out_root.mkdir(exist_ok=True)
    for fname in static_files:
        shutil.copy2(source_event / fname, out_root / fname)
    write_dis(out_root / "sfincs.dis")
    sf.set_root(str(out_root), mode="w+")
    sf.write_geoms()
    sf.write_config()

    zs = [pt[2] for line_ in sf.geoms["weir"].geometry for pt in line_.coords]
    print(f"{tag}: crest z {min(zs):.1f}-{max(zs):.1f} m -> {out_root.name}")


for site_name, geojson_name in SITES.items():
    for dz in DZ_SWEEP:
        make_weir_run(f"{site_name}_dz{dz}m", geojson_name, dz)
