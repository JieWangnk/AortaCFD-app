#!/bin/bash
# ===========================================================================
# Check HPC job status and solver progress
# Usage: ./status.sh [path/to/hpc.conf]
# ===========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="${1:-$SCRIPT_DIR/hpc.conf}"

if [[ ! -f "$CONF" ]]; then
    echo "ERROR: Config file not found: $CONF"
    exit 1
fi
source "$CONF"

REMOTE_DIR="$HPC_SCRATCH/$PATIENT_ID/$RUN_NAME"

echo "============================================================"
echo "  HPC Job Status — $PATIENT_ID"
echo "============================================================"

# Check queue
echo ""
echo ">>> SLURM queue:"
ssh "$HPC_HOST" "squeue -u $HPC_USER 2>/dev/null || echo 'No jobs in queue'"

# Check latest simulation time
echo ""
echo ">>> Latest simulation time:"
ssh "$HPC_HOST" "ls -d $REMOTE_DIR/processor0/[0-9]* 2>/dev/null | sort -t/ -k$(echo $REMOTE_DIR/processor0/ | tr -cd '/' | wc -c) -g | tail -3 || ls -d $REMOTE_DIR/[0-9]* 2>/dev/null | sort -g | tail -3 || echo 'No time directories found'"

# Check solver log tail
echo ""
echo ">>> Solver log (last 20 lines):"
ssh "$HPC_HOST" "tail -20 $REMOTE_DIR/logs/log.solver 2>/dev/null || tail -20 $REMOTE_DIR/${PATIENT_ID}_*.out 2>/dev/null || echo 'No solver log found'"

# Disk usage
echo ""
echo ">>> Disk usage:"
ssh "$HPC_HOST" "du -sh $REMOTE_DIR/ 2>/dev/null || echo 'Directory not found'"

echo "============================================================"
