#!/bin/bash
# ===========================================================================
# Sync a batch of prepared cases between laptop and HPC for the
# hybrid local-prep → HPC-solve → local-post workflow.
#
# Use it AFTER `run_batch.py --steps case,mesh,boundary --run-name X` has
# written your cases into output/<case>/<X>/, and BEFORE the HPC submission.
# Then reverse the direction after the solver finishes.
#
# Usage:
#   bash sync_prepared_cases.sh up   conf cases...     # laptop → HPC
#   bash sync_prepared_cases.sh down conf cases...     # HPC → laptop
#
# Example:
#   bash scripts/hpc/sync_prepared_cases.sh up   scripts/hpc/csf3.conf \
#       output/sev_001/hpc_batch output/sev_002/hpc_batch ...
#
# Differences from scripts/hpc/upload.sh:
#   - That script handles ONE single canonical patient case (uses
#     LOCAL_CASE_DIR from the conf, embeds its own SLURM script)
#   - This one handles N prepared case dirs for the run_batch.py
#     `--slurm --run-name X` flow, with no script generation.
# ===========================================================================
set -euo pipefail

if [[ $# -lt 3 ]]; then
    echo "Usage: $0 {up|down} <conf> <prepared_case_dir>..."
    echo "  up   = laptop -> HPC"
    echo "  down = HPC -> laptop"
    exit 1
fi

DIRECTION="$1"
CONF="$2"
shift 2

if [[ ! -f "$CONF" ]]; then
    echo "ERROR: conf file not found: $CONF"
    exit 1
fi
# shellcheck disable=SC1090
source "$CONF"

REMOTE_BASE="$HPC_HOST:$HPC_SCRATCH/AortaCFD-batch"

case "$DIRECTION" in
    up)
        ssh "$HPC_HOST" "mkdir -p $HPC_SCRATCH/AortaCFD-batch"
        for d in "$@"; do
            if [[ ! -d "$d" ]]; then
                echo "WARN: skipping (not a dir): $d"
                continue
            fi
            echo ">>> Uploading $d -> $REMOTE_BASE/$d"
            # -R preserves the parent path, so output/sev_001/hpc_batch lands
            # under $HPC_SCRATCH/AortaCFD-batch/output/sev_001/hpc_batch.
            rsync -avzR --copy-links \
                --exclude='processor*' --exclude='postProcessing/' \
                --exclude='VTK/' --exclude='*.foam' \
                "$d" "$REMOTE_BASE/"
        done
        ;;
    down)
        for d in "$@"; do
            echo ">>> Downloading $REMOTE_BASE/$d -> $d"
            mkdir -p "$(dirname "$d")"
            rsync -avz \
                --exclude='processor*' \
                "$REMOTE_BASE/$d/" "$d/"
        done
        ;;
    *)
        echo "ERROR: direction must be 'up' or 'down', got '$DIRECTION'"
        exit 1
        ;;
esac

echo "Done."
