#!/bin/bash
#SBATCH --job-name=mswe-gnn-scenario-scaling
#SBATCH --output=logs/%j_scenario_scaling.out
#SBATCH --error=logs/%j_scenario_scaling.err
#SBATCH --partition=gpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem-per-cpu=7500M
#SBATCH --time=02:00:00
# #SBATCH --mail-user=<your-email>
# #SBATCH --mail-type=BEGIN,END,FAIL

# Scenario-analysis throughput sweep: batches B=1..4096 independent scenarios into a single
# GPU forward pass (torch_geometric.data.Batch) and times it, vs SFINCS's per-process cost
# with hal8's `4vcpu` partition concurrency (P=19 nodes, see sinfo -p 4vcpu). Longer time
# budget than slurm/run_measure_ahr_timing_gpu_hal8.sh because it sweeps 13 batch sizes instead of
# 6 fixed scenarios, and the largest batches take longer to run (and to load initially).

export HDF5_USE_FILE_LOCKING=FALSE
export PYTHONUNBUFFERED=1
export WANDB_MODE=offline
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "Job ID:     $SLURM_JOB_ID"
echo "Node:       $SLURMD_NODENAME"
echo "GPU:        $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null)"
echo "Start time: $(date)"

mkdir -p logs

# Activate your conda environment (adapt to your cluster)
source "${CONDA_SH:-$HOME/miniconda3/etc/profile.d/conda.sh}"
conda activate mswe-gnn

cd "$SLURM_SUBMIT_DIR"
export PYTHONPATH="$SLURM_SUBMIT_DIR"

srun jupyter nbconvert --to notebook --execute --inplace \
    notebooks/measure_ahr_scenario_scaling_gpu.ipynb \
    2>&1 | tee logs/${SLURM_JOB_ID}_scenario_scaling.log

echo "End time: $(date)"
