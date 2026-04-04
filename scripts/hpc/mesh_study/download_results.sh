#!/bin/bash
# ===========================================================================
# Download mesh study results from CSF3
# Usage: bash scripts/hpc/mesh_study/download_results.sh
# ===========================================================================
set -euo pipefail

HPC_HOST="csf3"
HPC_SCRATCH="~/scratch/mesh_study"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RESULTS_DIR="$REPO_ROOT/scripts/hpc/mesh_study/results"
mkdir -p "$RESULTS_DIR"

echo "============================================================"
echo "  Downloading mesh study results from CSF3"
echo "============================================================"

# Download all mesh_summary.json and logs
for CASE in BPM120 PAT002 VOL04; do
    for RUN in mesh_50K mesh_300K mesh_1M; do
        REMOTE="$HPC_SCRATCH/$CASE/$RUN"
        LOCAL="$RESULTS_DIR/${CASE}_${RUN}"
        mkdir -p "$LOCAL"

        echo ">>> $CASE/$RUN"

        # Download summary + logs
        scp "$HPC_HOST:$REMOTE/mesh_summary.json" "$LOCAL/" 2>/dev/null || echo "  (no summary yet)"
        rsync -az "$HPC_HOST:$REMOTE/logs/" "$LOCAL/logs/" 2>/dev/null || echo "  (no logs yet)"
        scp "$HPC_HOST:$REMOTE/${CASE}_${RUN}_*.out" "$LOCAL/" 2>/dev/null || true
    done
done

# Print combined results table
echo ""
echo "============================================================"
echo "  MESH STUDY RESULTS"
echo "============================================================"
echo ""
printf "%-10s %-10s %8s %10s %10s %8s %8s %6s %6s\n" \
    "Case" "Target" "Span" "BlockMesh" "Final" "NonOrtho" "Skew" "OK?" "Time"
printf "%-10s %-10s %8s %10s %10s %8s %8s %6s %6s\n" \
    "----------" "----------" "--------" "----------" "----------" "--------" "--------" "------" "------"

for f in "$RESULTS_DIR"/*/mesh_summary.json; do
    [ -f "$f" ] || continue
    python3 -c "
import json
with open('$f') as fh:
    d = json.load(fh)
print(f'{d[\"case\"]:<10} {d[\"run\"]:<10} {d[\"span_target\"]:>8} {d[\"blockmesh_cells\"]:>10,} {d[\"final_cells\"]:>10,} {d[\"max_non_ortho\"]:>8.1f} {d[\"max_skewness\"]:>8.2f} {\"YES\" if d[\"checkmesh_ok\"] else \"NO\":>6} {d[\"wall_time_s\"]:>5}s')
" 2>/dev/null
done

echo ""
echo "Raw results in: $RESULTS_DIR/"
