#!/bin/bash
#------------------------------------------------------------------------------
# Test script: Implicit vs Explicit Windkessel Coupling Mode Comparison
#
# Purpose: Verify that implicit and explicit coupling modes produce identical
#          pressure and flow results (within numerical tolerance)
#
# Usage:
#   ./test_implicit_vs_explicit_WK.sh <base_case_dir>
#
# Example:
#   ./test_implicit_vs_explicit_WK.sh output/0014_H_AO_COA/testing_3M_laminar_traction
#
# Expected outcome:
#   - Both modes should produce same pressure waveforms at outlets
#   - Implicit mode may allow larger timesteps (up to 4-5x)
#   - Max pressure difference < 1% between modes
#
# Author: Generated for modularWKPressure validation
# Date: 2024-12-22
#------------------------------------------------------------------------------

set -e

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <base_case_dir>"
    echo "Example: $0 output/0014_H_AO_COA/testing_3M_laminar_traction"
    exit 1
fi

BASE_CASE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(dirname "$BASE_CASE")"
CASE_NAME="$(basename "$BASE_CASE")"

# Create test directories
EXPLICIT_CASE="${WORK_DIR}/test_WK_explicit"
IMPLICIT_CASE="${WORK_DIR}/test_WK_implicit"

echo "=============================================="
echo "Implicit vs Explicit WK Coupling Mode Test"
echo "=============================================="
echo "Base case: $BASE_CASE"
echo "Explicit test: $EXPLICIT_CASE"
echo "Implicit test: $IMPLICIT_CASE"
echo ""

# Function to modify coupling mode in p file
modify_coupling_mode() {
    local case_dir="$1"
    local mode="$2"
    local p_file="${case_dir}/openfoam/0/p"

    if [ -f "$p_file" ]; then
        # Add or replace couplingMode
        if grep -q "couplingMode" "$p_file"; then
            sed -i "s/couplingMode.*/couplingMode    ${mode};/" "$p_file"
        else
            # Add couplingMode after "order" line
            sed -i "/order/a\\        couplingMode    ${mode};" "$p_file"
        fi
        echo "Set couplingMode to '$mode' in $p_file"
    else
        echo "ERROR: $p_file not found"
        exit 1
    fi
}

# Copy base case for explicit test
echo ""
echo "--- Creating EXPLICIT mode test case ---"
if [ -d "$EXPLICIT_CASE" ]; then
    echo "Removing existing $EXPLICIT_CASE"
    rm -rf "$EXPLICIT_CASE"
fi
cp -r "$BASE_CASE" "$EXPLICIT_CASE"
modify_coupling_mode "$EXPLICIT_CASE" "explicit"

# Copy base case for implicit test
echo ""
echo "--- Creating IMPLICIT mode test case ---"
if [ -d "$IMPLICIT_CASE" ]; then
    echo "Removing existing $IMPLICIT_CASE"
    rm -rf "$IMPLICIT_CASE"
fi
cp -r "$BASE_CASE" "$IMPLICIT_CASE"
modify_coupling_mode "$IMPLICIT_CASE" "implicit"

# Modify controlDict to run shorter simulation for testing
modify_end_time() {
    local case_dir="$1"
    local end_time="$2"
    local control_dict="${case_dir}/openfoam/system/controlDict"

    if [ -f "$control_dict" ]; then
        sed -i "s/endTime.*/endTime         ${end_time};/" "$control_dict"
        echo "Set endTime to $end_time in $control_dict"
    fi
}

# Run for 1 cardiac cycle (0.5s at 120 BPM)
TEST_END_TIME="0.5"
modify_end_time "$EXPLICIT_CASE" "$TEST_END_TIME"
modify_end_time "$IMPLICIT_CASE" "$TEST_END_TIME"

echo ""
echo "=============================================="
echo "Test cases prepared:"
echo "  1. $EXPLICIT_CASE (couplingMode: explicit)"
echo "  2. $IMPLICIT_CASE (couplingMode: implicit)"
echo ""
echo "Both cases set to run for $TEST_END_TIME seconds"
echo ""
echo "Next steps:"
echo "  1. Run both cases (serial or parallel)"
echo "  2. Compare outlet pressure using postProcessing or ParaView"
echo "  3. Expected: pressure difference < 1%"
echo ""
echo "To run locally (serial):"
echo "  cd $EXPLICIT_CASE/openfoam && foamRun"
echo "  cd $IMPLICIT_CASE/openfoam && foamRun"
echo ""
echo "To compare results, use:"
echo "  postProcess -func 'patchAverage(name=outlet1,p)' -case $EXPLICIT_CASE/openfoam"
echo "  postProcess -func 'patchAverage(name=outlet1,p)' -case $IMPLICIT_CASE/openfoam"
echo "=============================================="
