#!/bin/bash
# ===========================================================================
# Example SLURM template for `run_batch.py --slurm-template`.
# Copy this file, adapt it for your cluster, then pass it via
# --slurm-template path/to/your_template.sh.
#
# For the full list of substitution tokens see scripts/hpc/README.md
# (section "SLURM template tokens"). Tokens use percent-percent-NAME-
# percent-percent syntax.
# ===========================================================================

#SBATCH --job-name=%%JOB_NAME%%
#SBATCH --array=0-%%ARRAY_MAX%%
#SBATCH --partition=%%PARTITION%%
#SBATCH --time=%%TIME_LIMIT%%
#SBATCH --cpus-per-task=%%CPUS_PER_TASK%%
#SBATCH --mem-per-cpu=%%MEM_PER_CPU%%
#SBATCH --output=output/slurm_%A_%a.log
#SBATCH --error=output/slurm_%A_%a.err
# Uncomment + adapt as your cluster requires:
#   #SBATCH --account=%%HPC_ACCOUNT%%
#   #SBATCH --qos=%%HPC_QOS%%
#   #SBATCH --reservation=%%HPC_RESERVATION%%

# ── AortaCFD SLURM Batch Script ──
# Generated: %%GENERATED_AT%%
# Cases:     %%N_CASES%%

%%CLUSTER_ENV_SETUP%%

# Resolve the repo root (= submission directory).
REPO_ROOT="${SLURM_SUBMIT_DIR:-$PWD}"
cd "$REPO_ROOT"

# Activate the AortaCFD venv if it exists locally
if [[ -f "$REPO_ROOT/venv/bin/activate" ]]; then
    source "$REPO_ROOT/venv/bin/activate"
fi

# Fail fast if OpenFOAM 12 is not actually on PATH yet
command -v foamRun >/dev/null 2>&1 || {
    echo "ERROR: foamRun not on PATH. Did you forget --cluster-conf?"
    exit 64
}

CASES=(%%CASES%%)
CASE_ID="${CASES[$SLURM_ARRAY_TASK_ID]}"

echo "=== AortaCFD SLURM Job ==="
echo "Job array ID : $SLURM_ARRAY_JOB_ID"
echo "Task index   : $SLURM_ARRAY_TASK_ID"
echo "Case         : $CASE_ID"
echo "Node         : $(hostname)"
echo "Start time   : $(date)"
echo "=========================="

python run_patient.py "$CASE_ID" --steps %%STEPS%%%%CONFIG_FLAG%%%%RUN_NAME_FLAG%%

echo "=== Finished: $CASE_ID at $(date) ==="
