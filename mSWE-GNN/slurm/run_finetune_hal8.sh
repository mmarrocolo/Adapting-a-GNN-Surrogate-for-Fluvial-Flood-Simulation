#!/bin/bash
#SBATCH --job-name=mswe-gnn-finetune
#SBATCH --output=logs/%j_finetune.out
#SBATCH --error=logs/%j_finetune.err
#SBATCH --partition=gpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem-per-cpu=7500M
#SBATCH --time=24:00:00
# #SBATCH --mail-user=<your-email>
# #SBATCH --mail-type=BEGIN,END,FAIL

export HDF5_USE_FILE_LOCKING=FALSE
export PYTHONUNBUFFERED=1
export WANDB_MODE=offline
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "Job ID:     $SLURM_JOB_ID"
echo "Node:       $SLURMD_NODENAME"
echo "GPU:        $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null)"
echo "Start time: $(date)"

mkdir -p logs

# Activate your conda environment (adapt to your cluster)
source "${CONDA_SH:-$HOME/miniconda3/etc/profile.d/conda.sh}"
conda activate mswe-gnn

cd "$SLURM_SUBMIT_DIR"
export PYTHONPATH="$SLURM_SUBMIT_DIR"

PYTHON=${PYTHON:-python}


# Datasets must already exist under database/datasets/ (see README, "Workflow").


CONFIG=${MSWE_CONFIG:-configs/config_best_sweep_bcaugment.yaml}
OUTPUT=${MSWE_OUTPUT:-results/best_sweep_bcaugment.h5}
CHECKPOINT_DIR=${MSWE_CHECKPOINT_DIR:-lightning_logs/finetune_ahr/${SLURM_JOB_ID}}
echo "Config: $CONFIG"
echo "Output: $OUTPUT"
echo "Checkpoint dir: $CHECKPOINT_DIR"

RESUME_ARGS=()
if [ -n "$MSWE_RESUME" ]; then
    echo "Resuming from: $MSWE_RESUME"
    RESUME_ARGS=(--resume "$MSWE_RESUME")
fi

srun $PYTHON -u finetune_ahr.py --config $CONFIG --output $OUTPUT \
    --checkpoint-dir "$CHECKPOINT_DIR" "${RESUME_ARGS[@]}" \
    2>&1 | tee logs/${SLURM_JOB_ID}_finetune.log

echo "End time: $(date)"
