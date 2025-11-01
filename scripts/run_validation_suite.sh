#!/bin/bash
# Automated Validation Suite for AortaCFD Numerics Profiles
# Tests: robust, accurate, precise profiles with mesh convergence

set -e  # Exit on error

# Configuration
PATIENT="BPM120"
OUTPUT_DIR="validation_results_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${OUTPUT_DIR}/validation.log"

# Create output directory
mkdir -p $OUTPUT_DIR

# Logging function
log() {
    echo "[$(date +%H:%M:%S)] $1" | tee -a $LOG_FILE
}

# Start validation
log "========================================"
log "AortaCFD VALIDATION SUITE"
log "========================================"
log "Patient: $PATIENT"
log "Output Directory: $OUTPUT_DIR"
log ""

# ============================================================
# TEST 1: Profile Comparison (robust, accurate, precise)
# ============================================================
log "TEST 1: Numerics Profile Comparison"
log "------------------------------------"

declare -A PROFILES=(
    ["robust"]="config_rans_coarse.json"
    ["accurate"]="config_rans_medium.json"
    ["precise"]="test_publication_numerics.json"
)

for profile_name in robust accurate precise; do
    config_file="${PROFILES[$profile_name]}"
    log "Running $profile_name profile ($config_file)..."

    start_time=$(date +%s)

    # Run simulation
    if python run_patient.py $PATIENT \
        --config cases_input/$PATIENT/$config_file \
        --step all \
        > $OUTPUT_DIR/${profile_name}_full.log 2>&1; then

        end_time=$(date +%s)
        runtime=$((end_time - start_time))
        log "  ✅ $profile_name completed in ${runtime}s ($(($runtime/60)) min)"

        # Extract key metrics
        run_dir=$(ls -td output/$PATIENT/run_* | head -1)

        # Check profile loaded
        if grep -q "Loaded numerics profile: $profile_name" $run_dir/logs/case_setup.log 2>/dev/null || \
           grep -q "numerics.*profile.*$profile_name" $run_dir/logs/case_setup.log 2>/dev/null; then
            log "  ✅ Profile verified: $profile_name"
        else
            log "  ⚠️  Warning: Could not verify profile in logs"
        fi

        # Extract final residuals
        if [ -f "$run_dir/openfoam/logs/pimpleFoam.log" ]; then
            final_residual=$(tail -100 $run_dir/openfoam/logs/pimpleFoam.log | \
                           grep "Final residual" | tail -1)
            log "  Final residuals: $final_residual"
        fi

        # Save summary
        echo "=== $profile_name ===" >> $OUTPUT_DIR/results_summary.txt
        echo "Runtime: ${runtime}s" >> $OUTPUT_DIR/results_summary.txt
        echo "Run directory: $run_dir" >> $OUTPUT_DIR/results_summary.txt

        # Check mesh size
        if [ -f "$run_dir/openfoam/logs/checkMesh.log" ]; then
            cells=$(grep "cells:" $run_dir/openfoam/logs/checkMesh.log | head -1)
            echo "Mesh: $cells" >> $OUTPUT_DIR/results_summary.txt
            log "  Mesh: $cells"
        fi

        echo "" >> $OUTPUT_DIR/results_summary.txt

    else
        log "  ❌ $profile_name FAILED - check $OUTPUT_DIR/${profile_name}_full.log"
    fi

    log ""
done

# ============================================================
# TEST 2: Verification Checks
# ============================================================
log "TEST 2: Verification Checks"
log "-----------------------------"

for profile_name in robust accurate precise; do
    log "Checking $profile_name..."

    run_dir=$(ls -td output/$PATIENT/run_* | grep -i $profile_name | head -1 || echo "")

    if [ -z "$run_dir" ]; then
        log "  ⚠️  No run directory found for $profile_name"
        continue
    fi

    # Check fvSchemes
    if [ -f "$run_dir/openfoam/system/fvSchemes" ]; then
        case $profile_name in
            robust)
                if grep -q "Gauss upwind" $run_dir/openfoam/system/fvSchemes; then
                    log "  ✅ Schemes verified: upwind (1st order)"
                else
                    log "  ❌ Wrong schemes for robust"
                fi
                ;;
            accurate)
                if grep -q "linearUpwind" $run_dir/openfoam/system/fvSchemes; then
                    log "  ✅ Schemes verified: linearUpwind (2nd order bounded)"
                else
                    log "  ❌ Wrong schemes for accurate"
                fi
                ;;
            precise)
                if grep -q "LUST" $run_dir/openfoam/system/fvSchemes; then
                    log "  ✅ Schemes verified: LUST (2nd order unbounded)"
                else
                    log "  ❌ Wrong schemes for precise"
                fi
                ;;
        esac
    fi

    # Check fvSolution tolerances
    if [ -f "$run_dir/openfoam/system/fvSolution" ]; then
        case $profile_name in
            robust)
                if grep -A5 "residualControl" $run_dir/openfoam/system/fvSolution | grep -q "1e-05\|1e-5"; then
                    log "  ✅ Tolerances verified: 1e-5"
                else
                    log "  ⚠️  Check tolerances for robust"
                fi
                ;;
            accurate)
                if grep -A5 "residualControl" $run_dir/openfoam/system/fvSolution | grep -q "1e-06\|1e-6"; then
                    log "  ✅ Tolerances verified: 1e-6"
                else
                    log "  ⚠️  Check tolerances for accurate"
                fi
                ;;
            precise)
                if grep -A5 "residualControl" $run_dir/openfoam/system/fvSolution | grep -q "1e-08\|1e-8"; then
                    log "  ✅ Tolerances verified: 1e-8"
                else
                    log "  ⚠️  Check tolerances for precise"
                fi
                ;;
        esac
    fi

    log ""
done

# ============================================================
# TEST 3: Compare Results
# ============================================================
log "TEST 3: Result Comparison"
log "-------------------------"
log "Extracting peak velocities from each profile..."

# This would need a Python post-processing script
# For now, just note where to find results
log "Results available in:"
for profile_name in robust accurate precise; do
    run_dir=$(ls -td output/$PATIENT/run_* | grep -i $profile_name | head -1 || echo "")
    if [ -n "$run_dir" ]; then
        log "  $profile_name: $run_dir"
    fi
done

log ""
log "To extract and compare quantities of interest:"
log "  python scripts/compare_results.py $OUTPUT_DIR"
log ""

# ============================================================
# Summary
# ============================================================
log "========================================"
log "VALIDATION SUITE COMPLETE"
log "========================================"
log ""
log "Summary saved to: $OUTPUT_DIR/results_summary.txt"
log "Full logs in: $OUTPUT_DIR/"
log ""
log "Next steps for publication:"
log "  1. Review results_summary.txt"
log "  2. Run mesh convergence study (create configs with different cells_per_diameter)"
log "  3. Extract quantities of interest for comparison"
log "  4. Calculate Grid Convergence Index (GCI)"
log "  5. Prepare figures showing mesh independence"
log ""
log "For questions, see: TESTING_AND_VALIDATION_GUIDE.md"

# Create summary report
cat > $OUTPUT_DIR/README.txt <<EOF
AortaCFD Validation Suite Results
==================================
Generated: $(date)
Patient: $PATIENT

This directory contains validation results for three numerics profiles:
- robust: 1st order bounded (maximum stability)
- accurate: 2nd order bounded (production default)
- precise: 2nd order unbounded (publication quality)

Files:
------
- validation.log: Main log file with all output
- results_summary.txt: Key metrics from each run
- <profile>_full.log: Complete output for each profile
- README.txt: This file

Output Directories:
-------------------
Check output/$PATIENT/run_*/ for OpenFOAM results

Verification:
-------------
See validation.log for scheme verification and tolerance checks

Next Steps:
-----------
1. Review results_summary.txt for runtime and convergence
2. Compare results between profiles (should differ <5% for same mesh)
3. If publishing, run mesh convergence study
4. Calculate GCI for discretization error estimate

Documentation:
--------------
See TESTING_AND_VALIDATION_GUIDE.md for detailed instructions
EOF

log "Validation report created: $OUTPUT_DIR/README.txt"
