from pathlib import Path
import shutil
import numpy as np

from paths import DATA_DIR, MODELS_DIR

project_root = MODELS_DIR  # all SFINCS model folders live side by side here
# static grid files are identical to those of the (non-warm-start) velocity model
source_model = project_root / "ahr_river_v03_Marg_additionalsrc_velocity_100m_cutpolygon_warmstart"
spinup_root  = project_root / "spinup_additionalsrc_velocity_100m_cutpolygon"

spinup_root.mkdir(exist_ok=True)

# Copy all static binary/grid files unchanged
for fname in ["sfincs.dep", "sfincs.msk", "sfincs.ind", "sfincs.src",
              "sfincs.obs", "sfincs_subgrid.nc"]:
    shutil.copy2(source_model / fname, spinup_root / fname)
    print(f"Copied {fname}")

# Write sfincs.inp
# Pre-event conditions: tref/tstart/tstop span 6 days before the flood (2021-07-06 -> 07-12).
# trstout = 518400 s (= 6 days) writes the restart file at the very end.
inp = """\
mmax                 = 332
nmax                 = 258
dx                   = 100
dy                   = 100
x0                   = 344900
y0                   = 5581800
rotation             = 0
tref                 = 20210706 000000
tstart               = 20210706 000000
tstop                = 20210712 000000
dtmapout             = 86400
dtmaxout             = 172800
trstout              = 518400 
dthisout             = 3600
alpha                = 0.5
theta                = 1
zsini                = 0
qinf                 = 0
huthresh             = 0.01
inputformat          = bin
outputformat         = net
advection            = 1
latitude             = 0
baro                 = 1
epsg                 = 32632
crsgeo               = 0
coriolis             = 1
viscosity            = 1
depfile              = sfincs.dep
mskfile              = sfincs.msk
indexfile            = sfincs.ind
sbgfile              = sfincs_subgrid.nc
srcfile              = sfincs.src
disfile              = sfincs.dis
obsfile              = sfincs.obs
storevel             = 1
"""
(spinup_root / "sfincs.inp").write_text(inp)
print("Written sfincs.inp")

# Write sfincs.dis
# Gauged tributaries use t=0 values from the flood simulation (already reflect
# elevated discharge after ~1-2 weeks antecedent rainfall).
# new1/Niederadenau/new2 had no observed data but get a small symbolic baseflow
# (0.1 m3/s each) so all inflow cells are wet at t=0 — the GNN then sees every
# source node as active from the first timestep.
# Columns: Kreuzberg, Denn, Kirmutscheid, Muesch, new1, Niederadenau, new2
baseflow_q = np.array([0.461, 2.111, 2.780, 0.645, 0.100, 0.100, 0.100])

dt = 3600          # 1-hour timestep
duration = 518400  # 6 days in seconds
times = np.arange(0, duration + dt, dt)

lines = []
for t in times:
    q_str = "  ".join(f"{q:8.3f}" for q in baseflow_q)
    lines.append(f"{t:12.1f}  {q_str}")

(spinup_root / "sfincs.dis").write_text("\n".join(lines) + "\n")
print("Written sfincs.dis")

print(f"\nBaseflow per source point (m3/s):")
names = ["Kreuzberg", "Denn", "Kirmutscheid", "Muesch", "new1", "Niederadenau", "new2"]
for name, q in zip(names, baseflow_q):
    print(f"  {name}: {q:.3f}")
print(f"  Total: {baseflow_q.sum():.3f} m3/s")
print(f"\nSpinup model written to: {spinup_root}")
print("Expected restart file after run: sfincs.20210712.000000.rst")
