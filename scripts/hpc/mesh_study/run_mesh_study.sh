#!/bin/bash
# ===========================================================================
# Mesh Resolution Study — 3 cases × 3 targets = 9 meshes
#
# Generates cases locally, uploads to CSF3, submits mesh-only SLURM jobs.
#
# Usage:
#   cd AortaCFD-app
#   bash scripts/hpc/mesh_study/run_mesh_study.sh
#
# Prerequisites:
#   - SSH alias "csf3" configured
#   - OpenFOAM 12 module available on CSF3
#   - AortaCFD-app venv active locally
#   - Source OpenFOAM 12 locally for case generation
# ===========================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

# --- HPC settings ---
HPC_HOST="csf3"
HPC_USER="mchi4jw4"
HPC_SCRATCH="~/scratch/mesh_study"
HPC_OF_MODULE="apps/gcc/openfoam/12"
HPC_PARTITION="multicore"
HPC_WALLTIME="04:00:00"

# --- Study matrix ---
# Format: CASE:SPAN_TARGET:RUN_NAME:NCORES
MATRIX=(
    # BPM120 — pediatric coarctation
    "BPM120:9:mesh_50K:8"
    "BPM120:16:mesh_300K:8"
    "BPM120:24:mesh_1M:16"
    # PAT002 — adult aorta
    "PAT002:9:mesh_50K:8"
    "PAT002:16:mesh_300K:8"
    "PAT002:24:mesh_1M:16"
    # VOL04 — large healthy aorta
    "VOL04:13:mesh_50K:8"
    "VOL04:23:mesh_300K:16"
    "VOL04:35:mesh_1M:32"
)

# ===========================================================================
# Step 1: Generate cases locally (mesh dicts only, no solver run)
# ===========================================================================
echo "============================================================"
echo "  MESH STUDY — Generating 9 cases locally"
echo "============================================================"

source venv/bin/activate 2>/dev/null || true

CONF_DIR="$REPO_ROOT/scripts/hpc/mesh_study/configs"
mkdir -p "$CONF_DIR"

for entry in "${MATRIX[@]}"; do
    IFS=':' read -r CASE SPAN RUN NCORES <<< "$entry"

    echo ""
    echo ">>> $CASE / $RUN (span_target=$SPAN, cores=$NCORES)"

    # Create merged config: base case config + span overlay
    BASE_CONF="$REPO_ROOT/cases_input/$CASE/config.json"
    MERGED_CONF="$CONF_DIR/${CASE}_${RUN}.json"

    python3 -c "
import json
with open('$BASE_CONF') as f:
    cfg = json.load(f)
# Remove legacy resolution — let span control it
cfg.get('mesh', {}).pop('cells_per_diameter', None)
cfg.get('mesh', {}).pop('mesh_resolution', None)
# Set span parameters
snappy = cfg.setdefault('mesh', {}).setdefault('SNAPPY_SETTINGS', {})
snappy['mesh_strategy'] = 'adaptive_span'
snappy['span_refinement_enabled'] = True
snappy['cells_across_span'] = $SPAN
snappy['surfaceRefinementLevels'] = [0, 1]
snappy['parallel'] = True
snappy['nProcessors'] = $NCORES
with open('$MERGED_CONF', 'w') as f:
    json.dump(cfg, f, indent=2)
"

    # Generate the case (case + mesh dicts only, no OpenFOAM execution)
    python3 run_patient.py "$CASE" \
        --steps case \
        --config "$MERGED_CONF" \
        --run-name "$RUN" \
        || { echo "FAILED: $CASE/$RUN case generation"; continue; }

    echo "  Generated: output/$CASE/$RUN"
done

# ===========================================================================
# Step 2: Upload to CSF3 and submit SLURM jobs
# ===========================================================================
echo ""
echo "============================================================"
echo "  Uploading to CSF3 and submitting jobs"
echo "============================================================"

# Create remote base directory
ssh "$HPC_HOST" "mkdir -p $HPC_SCRATCH"

for entry in "${MATRIX[@]}"; do
    IFS=':' read -r CASE SPAN RUN NCORES <<< "$entry"

    LOCAL_DIR="$REPO_ROOT/output/$CASE/$RUN/openfoam"
    REMOTE_DIR="$HPC_SCRATCH/$CASE/$RUN"

    if [[ ! -d "$LOCAL_DIR/system" ]]; then
        echo "SKIP: $CASE/$RUN — no system/ directory"
        continue
    fi

    echo ""
    echo ">>> Uploading $CASE/$RUN..."

    ssh "$HPC_HOST" "mkdir -p $REMOTE_DIR/logs"

    rsync -az --copy-links \
        --exclude='processor*' \
        --exclude='logs/' \
        --exclude='postProcessing/' \
        --exclude='VTK/' \
        --exclude='*.foam' \
        "$LOCAL_DIR/" "$HPC_HOST:$REMOTE_DIR/"

    # Update decomposeParDict to match HPC cores
    ssh "$HPC_HOST" "sed -i \
        -e 's/numberOfSubdomains[[:space:]]*[0-9]*/numberOfSubdomains  $NCORES/' \
        $REMOTE_DIR/system/decomposeParDict" 2>/dev/null || true

    # Generate SLURM job script (mesh only — no solver)
    JOB_NAME="${CASE}_${RUN}"
    cat > /tmp/job_${JOB_NAME}.slurm << SLURM_EOF
#!/bin/bash --login
#SBATCH --job-name=${JOB_NAME}
#SBATCH --partition=${HPC_PARTITION}
#SBATCH --ntasks=${NCORES}
#SBATCH --time=${HPC_WALLTIME}
#SBATCH --output=${JOB_NAME}_%j.out
#SBATCH --error=${JOB_NAME}_%j.err

module purge
module load ${HPC_OF_MODULE}
source \$foamDotFile

cd ${REMOTE_DIR}
mkdir -p logs

echo "============================================================"
echo "  MESH STUDY: ${CASE} / ${RUN}"
echo "  span_target=${SPAN}, cores=\$SLURM_NTASKS"
echo "  \$(date)"
echo "============================================================"

START=\$(date +%s)

# --- blockMesh ---
echo ">>> blockMesh"
blockMesh > logs/log.blockMesh 2>&1
BM_CELLS=\$(grep "nCells:" logs/log.blockMesh | awk '{print \$2}')
echo "  blockMesh cells: \$BM_CELLS"

# --- surfaceFeatures ---
echo ">>> surfaceFeatures"
surfaceFeatures > logs/log.surfaceFeatures 2>&1

# --- Rename closeness files for snappy ---
cd constant/triSurface
for f in *.closeness.*; do
    [ -f "\$f" ] || continue
    case "\$f" in *.stl.closeness.*) continue ;; esac
    newname=\$(echo "\$f" | sed 's/\.closeness/.stl.closeness/')
    mv "\$f" "\$newname"
done
cd ../..

# --- Parallel snappyHexMesh ---
if [ ${NCORES} -gt 1 ]; then
    echo ">>> decomposePar"
    decomposePar -force > logs/log.decomposePar 2>&1

    # Distribute closeness files to processors
    for pdir in processor*/; do
        [ -d "\$pdir" ] || continue
        mkdir -p "\${pdir}constant/triSurface"
        cp constant/triSurface/*.closeness.* "\${pdir}constant/triSurface/" 2>/dev/null || true
    done

    echo ">>> snappyHexMesh (parallel, ${NCORES} cores)"
    mpirun snappyHexMesh -parallel -overwrite > logs/log.snappyHexMesh 2>&1

    echo ">>> reconstructPar"
    reconstructPar -constant > logs/log.reconstructPar 2>&1
    rm -rf processor*
else
    echo ">>> snappyHexMesh (serial)"
    snappyHexMesh -overwrite > logs/log.snappyHexMesh 2>&1
fi

# --- checkMesh ---
echo ">>> checkMesh"
checkMesh > logs/log.checkMesh 2>&1

# --- Report ---
FINAL=\$(grep "^    cells:" logs/log.checkMesh | awk '{print \$2}')
ORTHO=\$(grep "Mesh non-orthogonality Max:" logs/log.checkMesh | grep -oP 'Max: [\d.]+' | grep -oP '[\d.]+')
SKEW=\$(grep "Max skewness" logs/log.checkMesh | grep -oP '= [\d.]+' | grep -oP '[\d.]+')
MESHOK=\$(grep -c "Mesh OK" logs/log.checkMesh || true)

END=\$(date +%s)
ELAPSED=\$(( END - START ))

echo ""
echo "============================================================"
echo "  RESULT: ${CASE} / ${RUN}"
echo "  blockMesh:    \$BM_CELLS"
echo "  final cells:  \$FINAL"
echo "  maxNonOrtho:  \$ORTHO"
echo "  maxSkewness:  \$SKEW"
echo "  checkMesh OK: \$([ "\$MESHOK" -gt 0 ] && echo YES || echo NO)"
echo "  wall time:    \${ELAPSED}s"
echo "============================================================"

# Write machine-readable summary
cat > mesh_summary.json << SUMMARY_EOF
{
    "case": "${CASE}",
    "run": "${RUN}",
    "span_target": ${SPAN},
    "ncores": ${NCORES},
    "blockmesh_cells": \$BM_CELLS,
    "final_cells": \$FINAL,
    "max_non_ortho": \$ORTHO,
    "max_skewness": \$SKEW,
    "checkmesh_ok": \$([ "\$MESHOK" -gt 0 ] && echo true || echo false),
    "wall_time_s": \$ELAPSED
}
SUMMARY_EOF

SLURM_EOF

    scp /tmp/job_${JOB_NAME}.slurm "$HPC_HOST:$REMOTE_DIR/"
    rm /tmp/job_${JOB_NAME}.slurm

    # Submit
    JOB_ID=$(ssh "$HPC_HOST" "cd $REMOTE_DIR && sbatch job_${JOB_NAME}.slurm" | grep -oP '\d+')
    echo "  Submitted: $JOB_NAME (job $JOB_ID)"

done

echo ""
echo "============================================================"
echo "  ALL 9 JOBS SUBMITTED"
echo ""
echo "  Monitor: ssh csf3 'squeue -u $HPC_USER'"
echo "  Results: ssh csf3 'cat $HPC_SCRATCH/*/mesh_*/mesh_summary.json'"
echo ""
echo "  Download results when done:"
echo "    bash scripts/hpc/mesh_study/download_results.sh"
echo "============================================================"
