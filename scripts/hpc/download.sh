#!/bin/bash
# ===========================================================================
# Download OpenFOAM results from HPC cluster
# Usage: ./download.sh [path/to/hpc.conf]
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

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CASE_DIR="$REPO_ROOT/$LOCAL_CASE_DIR"
REMOTE_DIR="$HPC_SCRATCH/$PATIENT_ID/$RUN_NAME"

echo "============================================================"
echo "  Download results from HPC"
echo "============================================================"
echo "  Remote:  $HPC_USER@$HPC_HOST:$REMOTE_DIR"
echo "  Local:   $CASE_DIR"
echo "============================================================"

# Check remote job status
echo ""
echo ">>> Checking remote directory..."
ssh "$HPC_HOST" "ls -d $REMOTE_DIR/[0-9]* 2>/dev/null | tail -5; echo '---'; du -sh $REMOTE_DIR/ 2>/dev/null"

echo ""
read -p "Download results? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Download results — time directories, postProcessing, logs, SLURM output
# Skip constant/ and system/ (already local), skip processor dirs
echo ""
echo ">>> Downloading results..."
rsync -avz --progress \
    --exclude='processor*' \
    --exclude='constant/' \
    --exclude='system/' \
    "$HPC_HOST:$REMOTE_DIR/" "$CASE_DIR/"

echo ""
echo "============================================================"
echo "  Download complete!"
echo ""
echo "  Local results: $CASE_DIR"
du -sh "$CASE_DIR" 2>/dev/null
echo ""
echo "  To view in ParaView:"
echo "    paraview $CASE_DIR/openfoam.foam"
echo "============================================================"
