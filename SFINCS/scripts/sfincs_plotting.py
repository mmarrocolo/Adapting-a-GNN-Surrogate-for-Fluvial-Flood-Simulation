"""
HydroMT-SFINCS utilities functions for plotting
"""

from typing import Tuple
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from hydromt_sfincs.plots import plot_basemap
from IPython.display import HTML
from matplotlib import animation

def make_animation(
    da_h: xr.DataArray, 
    geoms: dict, 
    bmap: str = "sat",
    zoomlevel: int = "auto",
    plot_bounds: bool = False,
    figsize: Tuple[int] = None,
    step=1, 
    cmap = 'BuPu',
    vmin=  0,
    vmax= 3,
    ):

    def update_plot(i, da_h, cax_h):
        da_h = da_h.isel(time=i)
        t = da_h.time.dt.strftime("%d-%B-%Y %H:%M:%S").item()
        ax.set_title(f"SFINCS water depth {t}")
        cax_h.set_array(da_h.values.ravel())

    fig, ax = plot_basemap(
        ds = da_h.to_dataset(),
        geoms = geoms,
        variable="",
        plot_bounds=plot_bounds,
        bmap=bmap,
        zoomlevel=zoomlevel,
        figsize=figsize,
    )

    cbar_kwargs = {"shrink": 0.6, "anchor": (0, 0)}

    cax_h = da_h.isel(time=0).plot(
        x="x", y="y", ax=ax, vmin=vmin, vmax=vmax, 
        cmap=cmap,  cbar_kwargs=cbar_kwargs
    )
    plt.close()  # to prevent double plot

    ani = animation.FuncAnimation(
        fig,
        update_plot,
        frames=np.arange(0, da_h.time.size, step),
        interval=250,  # ms between frames
        fargs=(da_h, cax_h,),
    )

    # to show in notebook:
    return HTML(ani.to_html5_video())