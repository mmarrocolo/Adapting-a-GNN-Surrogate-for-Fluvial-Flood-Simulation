# SFINCS Model of the July 2021 Ahr Flood

This repository contains the SFINCS model developed for the July 2021 flood in the Ahr Valley, Germany. It includes the baseline hydraulic model, the discharge forcing used for the event, and the scripts used to generate the forcing and hydraulic-structure scenarios analysed in the accompanying MSc thesis.

The model uses a 100 m computational grid with subgrid topography derived from a 1 m digital terrain model. The model domain covers the main Ahr valley and the lower reaches of its tributaries. Inflow is represented through seven discharge source points: four gauged tributaries and three ungauged tributaries whose hydrographs were estimated from the residual discharge at Altenahr.

Event simulations are warm-started from a preceding baseflow simulation to provide a physically meaningful initial hydraulic state.

## Repository Structure

```text
.
├── data/                       Model inputs and derived forcing
│   ├── catchment/              Catchment and model-domain geometries
│   ├── measures/               Hydraulic-structure geometries
│   └── observations/           Source points, gauges, and discharge hydrographs
├── models/
│   └── ahr_river_v03_Marg_additionalsrc_velocity_100m_cutpolygon_warmstart/
│                               Baseline SFINCS model
├── notebooks/
│   ├── 01_prepare_source_points.ipynb
│   ├── 02_setup_base_model.ipynb
│   ├── 03_results_baseline.ipynb
│   ├── 04_results_scaled_runs.ipynb
│   └── 05_results_infrastructure.ipynb
├── scripts/
│   ├── 01_setup_spinup.py
│   ├── 02_setup_scaled_runs.py
│   ├── 03_setup_tributary_variation_runs.py
│   ├── 04_setup_extra_variation_runs.py
│   ├── 05_setup_source_group_scenarios.py
│   ├── 06_setup_infrastructure_placement_runs.py
│   ├── 07_setup_thin_dam_weir_runs.py
│   └── run_sfincs.py
└── environment.yml
```

The notebooks document the preparation of the discharge forcing, construction of the baseline model, and analysis of the simulations. The scripts generate the spin-up and the different scenarios used in the thesis.

## Installation

Create the Python environment with:

```bash
conda env create -f environment.yml
conda activate ahr-sfincs
```

The simulations were performed with **SFINCS v2.3.0**. The SFINCS executable can be obtained from the official SFINCS repository.

## Running the Model

The baseline event uses a warm-start initial condition obtained from a six-day baseflow spin-up. The spin-up must therefore be completed before running the event simulation.

From the repository root:

```bash
python scripts/01_setup_spinup.py
python scripts/run_sfincs.py spinup_additionalsrc_velocity_100m_cutpolygon

python scripts/run_sfincs.py \
    ahr_river_v03_Marg_additionalsrc_velocity_100m_cutpolygon_warmstart
```

Additional scenarios can then be generated using the numbered scripts in `scripts/`.


The scenario scripts cover the experiments used in the thesis, including:

* uniform scaling of the discharge hydrographs;
* perturbations of individual inflow sources;
* changes in the timing of the inflow hydrographs;
* source-group sensitivity experiments;
* post-peak catchment emptying;
* levee configurations near Bad Neuenahr-Ahrweiler;
* flow-obstruction scenarios near Altenahr.

Most scenarios reuse the baseline warm-start state so that differences between simulations arise from the imposed perturbation rather than from different initial hydraulic conditions. Uniformly scaled events use corresponding scaled spin-up simulations.

## Data

Small project-generated inputs and derived datasets required by the model are included under `data/`. Large or third-party datasets are not added.

The main external datasets used to construct and evaluate the model are:

| Dataset                                | Source                                             | Use                                        |
| -------------------------------------- | -------------------------------------------------- | ------------------------------------------ |
| DGM1 1 m digital terrain model         | German state survey data, obtained through OpenDEM | Model topography and subgrid construction  |
| Discharge and water-level observations | Landesamt für Umwelt Rheinland-Pfalz               | Boundary forcing and model evaluation      |
| RADFLOOD21 precipitation               | Royal Meteorological Institute of Belgium          | Estimation of ungauged tributary discharge |
| ESA WorldCover 2021                    | ESA                                                | Spatially varying surface roughness        |


The final discharge forcing used by the model is included as:

```text
data/observations/src_points_ts_Marg_additionalsrc.csv
```

It contains observed hydrographs for the four gauged inflows and estimated hydrographs for the three ungauged tributaries.

## Scenario Outputs

Simulation outputs such as `sfincs_map.nc` and restart files are not stored in the repository because of their size. They can be regenerated from the included model inputs and scenario-generation scripts.
