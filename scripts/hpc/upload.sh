#!/bin/bash
# ===========================================================================
# Upload OpenFOAM case to HPC cluster
# Usage: ./upload.sh [path/to/hpc.conf]
# ===========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="${1:-$SCRIPT_DIR/hpc.conf}"

if [[ ! -f "$CONF" ]]; then
    echo "ERROR: Config file not found: $CONF"
    echo "Usage: $0 [path/to/hpc.conf]"
    exit 1
fi
source "$CONF"

# Resolve local case directory (relative to repo root)
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CASE_DIR="$REPO_ROOT/$LOCAL_CASE_DIR"

if [[ ! -d "$CASE_DIR/system" ]]; then
    echo "ERROR: Not a valid OpenFOAM case: $CASE_DIR"
    echo "Expected to find system/ directory"
    exit 1
fi

REMOTE_DIR="$HPC_SCRATCH/$PATIENT_ID/$RUN_NAME"

echo "============================================================"
echo "  Upload OpenFOAM case to HPC"
echo "============================================================"
echo "  Local:   $CASE_DIR"
echo "  Remote:  $HPC_USER@$HPC_HOST:$REMOTE_DIR"
echo "  Cores:   $HPC_NCORES"
echo "============================================================"

# Create remote directory
ssh "$HPC_HOST" "mkdir -p $REMOTE_DIR"

# Upload case (excluding processor dirs, logs, VTK, postProcessing)
# --copy-links: resolve symlinks (boundaryData cycle symlinks won't work remotely)
echo ""
echo ">>> Uploading case files..."
rsync -avz --progress --copy-links \
    --exclude='processor*' \
    --exclude='logs/' \
    --exclude='postProcessing/' \
    --exclude='VTK/' \
    --exclude='*.foam' \
    --exclude='*.log' \
    "$CASE_DIR/" "$HPC_HOST:$REMOTE_DIR/"

# Update decomposeParDict on remote to match HPC_NCORES
echo ""
echo ">>> Updating decomposeParDict (numberOfSubdomains = $HPC_NCORES)..."
ssh "$HPC_HOST" "sed -i \
    -e 's/numberOfSubdomains[[:space:]]*[0-9]*/numberOfSubdomains  $HPC_NCORES/' \
    -e 's/n[[:space:]]*(1 1 [0-9]*)/n               (1 1 $HPC_NCORES)/' \
    $REMOTE_DIR/system/decomposeParDict"

# Generate and upload SLURM job script
echo ""
echo ">>> Generating job script..."
cat > /tmp/run_${PATIENT_ID}.slurm << SLURM_EOF
#!/bin/bash --login
#SBATCH --job-name=${PATIENT_ID}_LES
#SBATCH --partition=${HPC_PARTITION}
#SBATCH --ntasks=${HPC_NCORES}
#SBATCH --time=${HPC_WALLTIME}
#SBATCH --output=${PATIENT_ID}_%j.out
#SBATCH --error=${PATIENT_ID}_%j.err

# --- OpenFOAM setup ---
module purge
module load ${HPC_OF_MODULE}
source \$foamDotFile

cd ${REMOTE_DIR}

echo "============================================================"
echo "  ${PATIENT_ID} LES - \$(date)"
echo "  Cores: \$SLURM_NTASKS"
echo "  Node:  \$(hostname)"
echo "============================================================"

# Check Windkessel library
if [[ -f "\$FOAM_USER_LIBBIN/libmodularWKPressure.so" ]]; then
    echo "Windkessel library found: \$FOAM_USER_LIBBIN/libmodularWKPressure.so"
else
    echo "WARNING: libmodularWKPressure.so not found in \$FOAM_USER_LIBBIN"
    echo "Solver may fail if Windkessel BCs are used"
fi

START_TIME=\$(date +%s)

# Decompose
echo ""
echo ">>> decomposePar (\$(date))"
decomposePar -force 2>&1 | tee logs/log.decomposePar

# Solve
echo ""
echo ">>> ${HPC_SOLVER} ${HPC_SOLVER_ARGS} (\$(date))"
mkdir -p logs
mpirun ${HPC_SOLVER} ${HPC_SOLVER_ARGS} -parallel 2>&1 | tee logs/log.solver

# Reconstruct
echo ""
echo ">>> reconstructPar (\$(date))"
reconstructPar 2>&1 | tee logs/log.reconstructPar

# Clean up processor directories
echo ""
echo ">>> Cleaning up processor directories..."
rm -rf processor*

END_TIME=\$(date +%s)
ELAPSED=\$(( (END_TIME - START_TIME) / 3600 ))
echo ""
echo "============================================================"
echo "  ${PATIENT_ID} completed - \$(date)"
echo "  Wall time: \${ELAPSED} hours"
echo "============================================================"
SLURM_EOF

scp /tmp/run_${PATIENT_ID}.slurm "$HPC_HOST:$REMOTE_DIR/"
rm /tmp/run_${PATIENT_ID}.slurm

echo ""
echo "============================================================"
echo "  Upload complete!"
echo ""
echo "  To submit on $HPC_HOST:"
echo "    ssh $HPC_HOST"
echo "    cd $REMOTE_DIR"
echo "    sbatch run_${PATIENT_ID}.slurm"
echo ""
echo "  To monitor:"
echo "    squeue -u $HPC_USER"
echo "    ssh $HPC_HOST 'tail -f $REMOTE_DIR/${PATIENT_ID}_*.out'"
echo "============================================================"
