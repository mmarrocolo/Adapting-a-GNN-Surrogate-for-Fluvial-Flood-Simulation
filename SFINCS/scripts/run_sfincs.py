"""Run SFINCS in one or more model folders under models/.

Usage:
    python scripts/run_sfincs.py spinup_additionalsrc_velocity_100m_cutpolygon
    python scripts/run_sfincs.py "ahr_river_v03_Marg_*_warmstart"   # glob patterns allowed

The executable is taken from the SFINCS_EXE environment variable, or else from
bin/SFINCS_v2.3.0_mt_Faber_release_exe/sfincs.exe.

Console output goes to console_out.txt, NOT sfincs.log: SFINCS opens sfincs.log
itself and crashes (forrtl error 47) if stdout is redirected to that file.
Spin-up folders (spinup_*) are always run before the event folders that restart
from them.
"""
import os
import subprocess
import sys
from pathlib import Path

from paths import MODELS_DIR, PROJECT_ROOT

DEFAULT_EXE = PROJECT_ROOT / "bin" / "SFINCS_v2.3.0_mt_Faber_release_exe" / "sfincs.exe"


def run(model_dir, exe):
    print(f"Running {model_dir.name} ...", flush=True)
    with open(model_dir / "console_out.txt", "w") as out:
        result = subprocess.run([str(exe)], cwd=model_dir, stdout=out, stderr=subprocess.STDOUT)
    status = "ok" if result.returncode == 0 else f"FAILED (exit {result.returncode})"
    print(f"  {status}")
    return result.returncode


if __name__ == "__main__":
    exe = Path(os.environ.get("SFINCS_EXE", DEFAULT_EXE))
    if not exe.exists():
        sys.exit(f"SFINCS executable not found: {exe} (set SFINCS_EXE)")
    matches = [d for pattern in sys.argv[1:] for d in sorted(MODELS_DIR.glob(pattern)) if d.is_dir()]
    folders = list(dict.fromkeys(matches))  # de-duplicate, keep order
    # spin-ups first: event runs read their restart files
    folders.sort(key=lambda d: not d.name.startswith("spinup_"))
    if not folders:
        sys.exit("No matching model folders in models/")
    failed = [d.name for d in folders if run(d, exe) != 0]
    if failed:
        sys.exit(f"Failed: {failed}")
