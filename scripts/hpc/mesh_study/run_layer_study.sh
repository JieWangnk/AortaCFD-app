#!/bin/bash
# ===========================================================================
# Layer Study — same 9 span meshes × 2 layer configs
#
# Batch B: "standard" layers (3 layers, OF-documented smoothing)
# Batch C: no layers (addLayers: false)
#
# Batch A (current aggressive layers) is already submitted as mesh_50K/300K/1M
#
# Usage:
#   cd AortaCFD-app
#   bash scripts/hpc/mesh_study/run_layer_study.sh
# ===========================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

HPC_HOST="csf3"
HPC_USER="mchi4jw4"
HPC_SCRATCH="~/scratch/mesh_study"
HPC_OF_MODULE="apps/gcc/openfoam/12"
HPC_PARTITION="multicore"
HPC_WALLTIME="04:00:00"

MATRIX=(
    "BPM120:9:8"
    "BPM120:16:8"
    "BPM120:24:16"
    "PAT002:9:8"
    "PAT002:16:8"
    "PAT002:24:16"
    "VOL04:13:8"
    "VOL04:23:16"
    "VOL04:35:32"
)

# Target names matching Batch A
declare -A SPAN_TO_TARGET
SPAN_TO_TARGET[9]="50K"
SPAN_TO_TARGET[13]="50K"
SPAN_TO_TARGET[16]="300K"
SPAN_TO_TARGET[23]="300K"
SPAN_TO_TARGET[24]="1M"
SPAN_TO_TARGET[35]="1M"

source venv/bin/activate 2>/dev/null || true
CONF_DIR="$REPO_ROOT/scripts/hpc/mesh_study/configs"
mkdir -p "$CONF_DIR"

# ===========================================================================
# Layer profiles
# ===========================================================================

# Write layer profiles to temp files (avoids shell quoting issues)
LAYER_B_FILE=$(mktemp)
cat > "$LAYER_B_FILE" << 'LAYEREOF'
{"addLayers":true,"addLayer":3,"relativeSizes":true,"expansionRatio":1.2,"finalLayerThickness":0.3,"minThickness":0.1,"nGrow":1,"nSmoothSurfaceNormals":1,"nSmoothNormals":3,"nSmoothThickness":10,"nSmoothDisplacement":5,"maxFaceThicknessRatio":0.5,"maxThicknessToMedialRatio":0.3,"nBufferCellsNoExtrude":0,"nLayerIter":50,"nRelaxedIter":20,"featureAngle":150,"slipFeatureAngle":30,"layerTerminationAngle":-180,"minMedianAxisAngle":90,"addLayers_nRelaxIter":5}
LAYEREOF

LAYER_C_FILE=$(mktemp)
cat > "$LAYER_C_FILE" << 'LAYEREOF'
{"addLayers":false,"addLayer":0}
LAYEREOF

trap "rm -f $LAYER_B_FILE $LAYER_C_FILE" EXIT

generate_and_submit() {
    local BATCH_NAME="$1"
    local LAYER_FILE="$2"
    local RUN_SUFFIX="$3"

    echo ""
    echo "============================================================"
    echo "  $BATCH_NAME — Generating and submitting"
    echo "============================================================"

    for entry in "${MATRIX[@]}"; do
        IFS=':' read -r CASE SPAN NCORES <<< "$entry"
        TARGET="${SPAN_TO_TARGET[$SPAN]}"
        RUN="mesh_${TARGET}_${RUN_SUFFIX}"

        echo ""
        echo ">>> $CASE / $RUN (span=$SPAN, cores=$NCORES)"

        BASE_CONF="$REPO_ROOT/cases_input/$CASE/config.json"
        MERGED_CONF="$CONF_DIR/${CASE}_${RUN}.json"

        python3 -c "
import json
with open('$BASE_CONF') as f:
    cfg = json.load(f)
cfg.get('mesh', {}).pop('cells_per_diameter', None)
cfg.get('mesh', {}).pop('mesh_resolution', None)
snappy = cfg.setdefault('mesh', {}).setdefault('SNAPPY_SETTINGS', {})
snappy['mesh_strategy'] = 'adaptive_span'
snappy['span_refinement_enabled'] = True
snappy['cells_across_span'] = $SPAN
snappy['surfaceRefinementLevels'] = [0, 1]
snappy['parallel'] = True
snappy['nProcessors'] = $NCORES

with open('$LAYER_FILE') as lf:
    layer_overrides = json.load(lf)
snappy.update(layer_overrides)

bl = cfg.setdefault('mesh', {}).setdefault('boundary_layers', {})
bl['enabled'] = layer_overrides.get('addLayers', False)
bl['num_layers'] = layer_overrides.get('addLayer', 0)
if 'expansionRatio' in layer_overrides:
    bl['expansion_ratio'] = layer_overrides['expansionRatio']
if 'finalLayerThickness' in layer_overrides:
    bl['final_layer_thickness'] = layer_overrides['finalLayerThickness']
if 'minThickness' in layer_overrides:
    bl['min_thickness'] = layer_overrides['minThickness']

with open('$MERGED_CONF', 'w') as f:
    json.dump(cfg, f, indent=2)
"

        python3 run_patient.py "$CASE" \
            --steps case \
            --config "$MERGED_CONF" \
            --run-name "$RUN" 2>&1 | grep -E "Completed|Error" || true

        LOCAL_DIR="$REPO_ROOT/output/$CASE/$RUN/openfoam"
        REMOTE_DIR="$HPC_SCRATCH/$CASE/$RUN"

        if [[ ! -d "$LOCAL_DIR/system" ]]; then
            echo "  SKIP: no system/ directory"
            continue
        fi

        ssh "$HPC_HOST" "mkdir -p $REMOTE_DIR/logs"

        rsync -az --copy-links \
            --exclude='processor*' --exclude='logs/' \
            --exclude='postProcessing/' --exclude='VTK/' --exclude='*.foam' \
            "$LOCAL_DIR/" "$HPC_HOST:$REMOTE_DIR/"

        ssh "$HPC_HOST" "sed -i \
            -e 's/numberOfSubdomains[[:space:]]*[0-9]*/numberOfSubdomains  $NCORES/' \
            $REMOTE_DIR/system/decomposeParDict" 2>/dev/null || true

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
echo "  LAYER STUDY: ${CASE} / ${RUN}"
echo "  span=${SPAN}, layers=${RUN_SUFFIX}, cores=\$SLURM_NTASKS"
echo "  \$(date)"
echo "============================================================"

START=\$(date +%s)

echo ">>> blockMesh"
blockMesh > logs/log.blockMesh 2>&1
BM_CELLS=\$(grep "nCells:" logs/log.blockMesh | awk '{print \$2}')
echo "  blockMesh cells: \$BM_CELLS"

echo ">>> surfaceFeatures"
surfaceFeatures > logs/log.surfaceFeatures 2>&1

cd constant/triSurface
for f in *.closeness.*; do
    [ -f "\$f" ] || continue
    case "\$f" in *.stl.closeness.*) continue ;; esac
    newname=\$(echo "\$f" | sed 's/\.closeness/.stl.closeness/')
    mv "\$f" "\$newname"
done
cd ../..

if [ ${NCORES} -gt 1 ]; then
    echo ">>> decomposePar"
    decomposePar -force > logs/log.decomposePar 2>&1

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

echo ">>> checkMesh"
checkMesh > logs/log.checkMesh 2>&1

FINAL=\$(grep "^    cells:" logs/log.checkMesh | awk '{print \$2}')
ORTHO=\$(grep "Mesh non-orthogonality Max:" logs/log.checkMesh | grep -oP 'Max: [\d.]+' | grep -oP '[\d.]+')
SKEW=\$(grep "Max skewness" logs/log.checkMesh | grep -oP '= [\d.]+' | grep -oP '[\d.]+')
MESHOK=\$(grep -c "Mesh OK" logs/log.checkMesh || true)

# Layer coverage from snappy log
LAYER_ADDED=\$(grep "Added.*layers" logs/log.snappyHexMesh 2>/dev/null | tail -1 || echo "?")

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
echo "  layers:       \$LAYER_ADDED"
echo "  wall time:    \${ELAPSED}s"
echo "============================================================"

cat > mesh_summary.json << SUMMARY_EOF
{
    "case": "${CASE}",
    "run": "${RUN}",
    "span_target": ${SPAN},
    "layer_mode": "${RUN_SUFFIX}",
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

        JOB_ID=$(ssh "$HPC_HOST" "cd $REMOTE_DIR && sbatch job_${JOB_NAME}.slurm" | grep -oP '\d+')
        echo "  Submitted: $JOB_NAME (job $JOB_ID)"
    done
}

# ===========================================================================
# Submit both batches
# ===========================================================================

generate_and_submit "Batch B: standard layers (3 layers)" "$LAYER_B_FILE" "lay3"
generate_and_submit "Batch C: no layers" "$LAYER_C_FILE" "nolay"

echo ""
echo "============================================================"
echo "  ALL LAYER STUDY JOBS SUBMITTED"
echo ""
echo "  Batch A (current layers):    mesh_50K / mesh_300K / mesh_1M"
echo "  Batch B (3 layers standard): mesh_50K_lay3 / mesh_300K_lay3 / mesh_1M_lay3"
echo "  Batch C (no layers):         mesh_50K_nolay / mesh_300K_nolay / mesh_1M_nolay"
echo ""
echo "  Monitor: ssh csf3 'squeue -u $HPC_USER'"
echo "  Download: bash scripts/hpc/mesh_study/download_results.sh"
echo "============================================================"
