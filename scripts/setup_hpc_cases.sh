#!/bin/bash
# Setup all sensitivity study cases with mesh and boundary conditions for HPC submission
# This script prepares cases without running the solver

set -e

# Source OpenFOAM and activate Python environment
source /opt/openfoam12/etc/bashrc
source /home/mchi4jw4/GitHub/AortaCFD-app/venv/bin/activate

cd /home/mchi4jw4/GitHub/AortaCFD-app
export PYTHONPATH=src

PATIENT_INPUT_DIR="cases_input/BPM120"

echo "=============================================="
echo "SETTING UP HPC CASES FOR SENSITIVITY STUDIES"
echo "=============================================="
echo ""

# Function to setup a single case
setup_case() {
    local config_file=$1
    local output_dir=$2
    local case_name=$3

    echo "----------------------------------------"
    echo "Setting up: $case_name"
    echo "  Config: $config_file"
    echo "  Output: $output_dir"
    echo "----------------------------------------"

    # Create output directory and copy input files
    mkdir -p "$output_dir/openfoam"
    cp -n "$PATIENT_INPUT_DIR"/*.csv "$output_dir/" 2>/dev/null || true
    cp -n "$PATIENT_INPUT_DIR"/*.stl "$output_dir/" 2>/dev/null || true

    # Run case setup, mesh, and boundary conditions (no solver)
    python3 run_patient.py BPM120 \
        --config "$config_file" \
        --case-dir "$output_dir" \
        --steps case,mesh,boundary

    if [ $? -eq 0 ]; then
        echo "SUCCESS: $case_name setup complete"
    else
        echo "FAILED: $case_name setup failed"
        return 1
    fi
    echo ""
}

# ============================================
# WINDKESSEL SENSITIVITY STUDY (11 cases)
# ============================================
echo ""
echo "=============================================="
echo "WINDKESSEL SENSITIVITY STUDY (11 cases)"
echo "=============================================="

WK_DIR="output/BPM120/windkessel_sensitivity"

setup_case "$WK_DIR/config_baseline.json" "$WK_DIR/baseline" "WK: baseline"
setup_case "$WK_DIR/config_tau_1p0.json" "$WK_DIR/tau_1p0" "WK: tau=1.0"
setup_case "$WK_DIR/config_tau_1p5.json" "$WK_DIR/tau_1p5" "WK: tau=1.5"
setup_case "$WK_DIR/config_tau_2p5.json" "$WK_DIR/tau_2p5" "WK: tau=2.5"
setup_case "$WK_DIR/config_pwv_4p0.json" "$WK_DIR/pwv_4p0" "WK: pwv=4.0"
setup_case "$WK_DIR/config_pwv_8p0.json" "$WK_DIR/pwv_8p0" "WK: pwv=8.0"
setup_case "$WK_DIR/config_pwv_10p0.json" "$WK_DIR/pwv_10p0" "WK: pwv=10.0"
setup_case "$WK_DIR/config_murray_exponent_2p0.json" "$WK_DIR/murray_exponent_2p0" "WK: murray=2.0"
setup_case "$WK_DIR/config_murray_exponent_2p5.json" "$WK_DIR/murray_exponent_2p5" "WK: murray=2.5"
setup_case "$WK_DIR/config_blood_pressure_110_70.json" "$WK_DIR/blood_pressure_110_70" "WK: BP=110/70"
setup_case "$WK_DIR/config_blood_pressure_130_90.json" "$WK_DIR/blood_pressure_130_90" "WK: BP=130/90"

# ============================================
# NUMERICAL PROFILE SENSITIVITY STUDY (3 cases)
# ============================================
echo ""
echo "=============================================="
echo "NUMERICAL PROFILE SENSITIVITY STUDY (3 cases)"
echo "=============================================="

PROFILE_DIR="output/BPM120/profile_sensitivity"

setup_case "$PROFILE_DIR/config_profile_robust.json" "$PROFILE_DIR/profile_robust" "Profile: robust"
setup_case "$PROFILE_DIR/config_profile_standard.json" "$PROFILE_DIR/profile_standard" "Profile: standard"
setup_case "$PROFILE_DIR/config_profile_accurate.json" "$PROFILE_DIR/profile_accurate" "Profile: accurate"

echo ""
echo "=============================================="
echo "ALL CASES SETUP COMPLETE"
echo "=============================================="
echo ""
echo "Total cases prepared: 14"
echo "  - Windkessel sensitivity: 11 cases"
echo "  - Numerical profile: 3 cases"
echo ""
echo "Cases are ready for HPC submission with:"
echo "  - Mesh generated and decomposed"
echo "  - Boundary conditions configured"
echo "  - Ready to run foamRun solver"
echo ""
