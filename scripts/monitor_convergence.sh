#!/bin/bash
# Monitor convergence study progress
#
# Usage: ./scripts/monitor_convergence.sh [study_directory]

if [ -z "$1" ]; then
    # Find most recent convergence study
    STUDY_DIR=$(ls -td output/mesh_convergence/patient*_* 2>/dev/null | head -1)
    if [ -z "$STUDY_DIR" ]; then
        echo "No convergence studies found in output/mesh_convergence/"
        exit 1
    fi
else
    STUDY_DIR="$1"
fi

echo "========================================================================"
echo "  CONVERGENCE STUDY MONITOR"
echo "========================================================================"
echo "Study: $STUDY_DIR"
echo ""

# Check mesh completion status
check_mesh_status() {
    local mesh_name=$1
    local mesh_dir=$2

    echo "--- $mesh_name ---"

    if [ ! -d "$mesh_dir" ]; then
        echo "  Status: Not started"
        return
    fi

    local openfoam_dir="$mesh_dir/openfoam"

    # Check if meshing complete
    if [ -d "$openfoam_dir/constant/polyMesh" ]; then
        local cell_count=$(grep -o "cells:.*" "$openfoam_dir/log.checkMesh" 2>/dev/null | awk '{print $2}')
        echo "  ✓ Mesh generated: $cell_count cells"
    else
        echo "  ⏳ Meshing in progress..."
        return
    fi

    # Check solver progress
    if [ -f "$openfoam_dir/log.foamRun" ] || [ -f "$openfoam_dir/log.pimpleFoam" ]; then
        local log_file="$openfoam_dir/log.foamRun"
        [ ! -f "$log_file" ] && log_file="$openfoam_dir/log.pimpleFoam"

        # Get latest time
        local latest_time=$(tail -100 "$log_file" | grep "^Time = " | tail -1 | awk '{print $3}')

        if [ ! -z "$latest_time" ]; then
            # Get end time from controlDict
            local end_time=$(grep "endTime" "$openfoam_dir/system/controlDict" | awk '{print $2}' | tr -d ';')

            if [ ! -z "$end_time" ]; then
                local progress=$(awk "BEGIN {printf \"%.1f\", ($latest_time/$end_time)*100}")
                echo "  ⏳ Solving: t=$latest_time/$end_time (${progress}%)"
            else
                echo "  ⏳ Solving: t=$latest_time"
            fi

            # Show latest residuals
            local p_res=$(tail -50 "$log_file" | grep "Solving for p" | tail -1 | awk '{print $NF}')
            local u_res=$(tail -50 "$log_file" | grep "Solving for Ux" | tail -1 | awk '{print $NF}')

            if [ ! -z "$p_res" ]; then
                echo "  Residuals: p=$p_res, U=$u_res"
            fi
        else
            echo "  Status: Solver starting..."
        fi
    else
        echo "  Status: Solver not started"
    fi

    # Check if complete (time directories exist)
    local time_dirs=$(find "$openfoam_dir" -maxdepth 1 -type d -name "[0-9]*" 2>/dev/null | wc -l)
    if [ $time_dirs -gt 1 ]; then
        echo "  ✓ Simulation complete ($time_dirs time steps)"
    fi

    echo ""
}

# Check each mesh
check_mesh_status "COARSE MESH" "$STUDY_DIR/coarse"
check_mesh_status "MEDIUM MESH" "$STUDY_DIR/medium"
check_mesh_status "FINE MESH" "$STUDY_DIR/fine"

# Check for final report
echo "--- CONVERGENCE ANALYSIS ---"
if [ -f "$STUDY_DIR/convergence_report.md" ]; then
    echo "  ✅ COMPLETE - Report generated"
    echo ""
    echo "View report:"
    echo "  cat $STUDY_DIR/convergence_report.md"
    echo ""

    # Extract key GCI values
    echo "Quick Results:"
    grep -A 2 "GCI fine:" "$STUDY_DIR/convergence_report.md" 2>/dev/null || echo "  (parsing report...)"
else
    echo "  ⏳ Analysis pending (waiting for fine mesh completion)"
fi

echo ""
echo "========================================================================"
echo "Refresh: watch -n 10 ./scripts/monitor_convergence.sh $STUDY_DIR"
echo "========================================================================"
