# mSWE-GNN for Fluvial Flooding in the Ahr Valley

This repository contains the code developed to adapt **mSWE-GNN** (multi-scale Shallow Water Equation Graph Neural Network) to fluvial flooding in the Ahr Valley, Germany, using the July 2021 flood as a case study.

The model is trained and evaluated using hydraulic simulations generated with [SFINCS](https://sfincs.readthedocs.io/) on a 100 m computational grid. The finest scale of the GNN graph corresponds directly to the active SFINCS grid cells, while progressively coarser meshes allow hydraulic information to propagate over larger spatial distances.

The repository covers the complete workflow from SFINCS simulations to GNN training and evaluation:

**SFINCS simulations → multiscale mesh → GNN datasets → training → inference and evaluation**

Compared with the original mSWE-GNN implementation, the main additions are:

* support for multiple simultaneous discharge boundary conditions through ghost nodes;
* preprocessing of SFINCS hydraulic output into PyTorch Geometric-compatible datasets;
* multi-event training using different discharge magnitudes and spatially varying boundary-condition perturbations;
* representation of hydraulic structures, including levees and flow obstructions, within the GNN mesh;
* additional loss configurations and training experiments for fluvial flood modelling;
* evaluation routines for flood extent, water-depth accuracy, boundary-condition sensitivity, and computational performance relative to SFINCS.

## Attribution

This work builds on the mSWE-GNN framework developed by R. Bentivoglio et al. in *Multi-scale hydraulic graph neural networks for flood modelling*.

The original code, datasets, and trained models are available at:

https://doi.org/10.5281/zenodo.13326595

Parts of the model, training, and graph-construction code in `models/`, `training/`, and `database/graph_creation.py` derive from the original mSWE-GNN implementation and were subsequently modified for the fluvial application presented here. These components remain subject to the licence terms of the original mSWE-GNN repository.

## Repository Structure

```text
.
├── configs/                     Experiment configuration files
├── database/                    Mesh construction and SFINCS-to-GNN conversion
│   ├── raw_datasets_ahr/        SFINCS simulations and input files
│   └── datasets/                Generated GNN datasets 
├── models/                      SWE-GNN and mSWE-GNN model definitions
├── training/                    Training module, losses, and curriculum learning
├── utils/                       Dataset handling, scaling, configuration, and utilities
├── scripts/                     Dataset and mesh preparation scripts
├── slurm/                       Example SLURM scripts for HPC execution
├── notebooks/                   Analysis and visualisation notebooks
├── results/                     Model checkpoints and inference outputs
├── finetune_ahr.py              Main training entry point
├── run_inference.py             Rollout inference and evaluation
└── requirements.txt             Python dependencies
```

## Installation

Create and activate a dedicated environment:

```bash
conda create -n mswe-gnn python=3.10
conda activate mswe-gnn
pip install -r requirements.txt
```

## From SFINCS to a GNN Dataset

The data-preparation pipeline is divided into two steps.

### 1. Build the multiscale mesh template

The template defines the spatial domain independently of a particular flood simulation. It contains:

* the active 100 m SFINCS grid used as the finest GNN scale;
* the progressively coarser meshes;
* terrain and static mesh attributes;
* graph connectivity;
* ghost and boundary nodes;
* placeholders for the time-varying hydraulic variables and boundary conditions.

The template used in the final experiments (the 100 m SFINCS grid plus 500 m, 1000 m and 2000 m meshes) is generated with:

```bash
python scripts/build_template.py
```

For the hydraulic-structures experiments, a separate template that carries the structure edge feature is generated with:

```bash
python scripts/build_template_structures.py
```

The underlying mesh and graph operations are implemented in `database/graph_creation.py`, while the Ahr-specific template construction is handled by `database/create_mesh_template_marg.py`.

### 2. Convert SFINCS simulations

Once the mesh template has been generated, hydraulic output from a SFINCS simulation is inserted into it to create the dataset used by mSWE-GNN.

The conversion extracts the time-varying hydraulic fields from `sfincs_map.nc` and maps them onto the GNN nodes. The discharge hydrographs specified by the SFINCS source files are converted into the corresponding boundary conditions for the GNN ghost nodes.

For the reference (1.0x) event, use `database/create_dataset_100m.ipynb`.

For the multi-event training dataset, first convert the uniform discharge-scaling events and then the boundary-condition perturbation events, which are merged into one training set:

```bash
python scripts/run_convert_multisim.py
python scripts/run_convert_bc_augmentation.py
```

For the hydraulic-structures dataset (levee and thin-dam scenarios merged with the boundary-condition perturbation events):

```bash
python scripts/run_convert_structures.py
```

The resulting files are written to:

```text
database/datasets/train/<dataset>.pkl
database/datasets/test/<dataset>.pkl
```

These `.pkl` files contain the multiscale graph together with the static and time-varying hydraulic information required during training and inference.

## Training

Training experiments are controlled through YAML configuration files in `configs/`.

A model can be trained with:

```bash
python finetune_ahr.py \
    --config configs/config_best_sweep_bcaugment.yaml \
    --output results/my_model.h5
```

The hydraulic-structures model is trained with `configs/config_best_sweep_structures_bcaugment_weircrest.yaml`, and the hyper-parameter search is defined in `configs/sweep_config.yaml`.

The configuration files define the dataset, model architecture, loss formulation, training parameters, and other experiment-specific settings.

The configurations retained in this repository correspond to the main experiments used during the thesis. Development configurations that were superseded during model testing are not included in the public workflow.

## Inference and Evaluation

A trained model can be evaluated through the inference scripts:

```bash
python run_inference.py ...
```

The `notebooks/` directory contains the remaining interactive analyses used to inspect and visualise model behaviour, including:

* autoregressive rollout visualisation;
* water-depth and flood-extent metrics;
* boundary-condition sensitivity experiments;
* hydraulic-structure scenarios;
* computational-performance comparisons.

The notebooks assume that the required datasets are available under `database/datasets/` and trained checkpoints under `results/`.

## Reproducing the Workflow

For a new SFINCS simulation using the same Ahr computational domain, the general workflow is:

```text
1. Run or obtain the SFINCS simulation
                 │
                 ▼
2. Build/reuse the multiscale mesh template
                 │
                 ▼
3. Convert SFINCS output to a GNN .pkl dataset
                 │
                 ▼
4. Select or create a YAML configuration
                 │
                 ▼
5. Train mSWE-GNN
                 │
                 ▼
6. Run autoregressive inference
                 │
                 ▼
7. Compute metrics and visualise results
```
