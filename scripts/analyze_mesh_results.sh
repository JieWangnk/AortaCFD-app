#!/bin/bash
# Analyze mesh study results

echo "=== MESH STUDY RESULTS ==="
echo ""
printf "%-25s %-6s %-12s %-10s %-10s\n" "Run" "Pass" "Cells" "MaxSkew" "MaxOrtho"
echo "----------------------------------------------------------------"

for dir in /home/mchi4jw4/GitHub/AortaCFD-app/output/0014_H_AO_COA/run_20251220_*; do
    logfile="$dir/openfoam/logs/log.checkMesh"
    if [ -f "$logfile" ]; then
        name=$(basename "$dir" | sed 's/run_20251220_//')
        cells=$(grep "cells:" "$logfile" | awk '{print $2}')
        skew=$(grep "Max skewness" "$logfile" | head -1 | sed 's/.*= //' | cut -d' ' -f1)
        ortho=$(grep "non-orthogonality Max" "$logfile" | sed 's/.*Max: //' | cut -d' ' -f1)

        if grep -q "Mesh OK" "$logfile"; then
            status="✓"
        else
            status="✗"
        fi

        printf "%-25s %-6s %-12s %-10s %-10s\n" "$name" "$status" "$cells" "$skew" "$ortho"
    fi
done

echo ""
echo "=== SUMMARY ==="
passed=$(grep -l "Mesh OK" /home/mchi4jw4/GitHub/AortaCFD-app/output/0014_H_AO_COA/run_20251220_*/openfoam/logs/log.checkMesh 2>/dev/null | wc -l)
total=$(ls /home/mchi4jw4/GitHub/AortaCFD-app/output/0014_H_AO_COA/run_20251220_*/openfoam/logs/log.checkMesh 2>/dev/null | wc -l)
echo "Passed: $passed / $total"
