#!/usr/bin/env python3
"""Setup remaining sensitivity cases by copying entire case from baseline.

For WK sensitivity: Same mesh, same inlet BC, only Windkessel params change.
For profile sensitivity: Same mesh, same inlet BC, different numerics (fvSchemes/fvSolution).

The approach: Copy entire case, then run only what's needed:
- WK cases: Re-run boundary step to recalculate Windkessel with new params
- Profile cases: Copy and regenerate fvSchemes/fvSolution from profile config
"""
import os
import shutil
import subprocess
import sys
import json

ROOT = "/home/mchi4jw4/GitHub/AortaCFD-app"
PATIENT_INPUT = f"{ROOT}/cases_input/BPM120"

# Baseline mesh source
WK_BASELINE = f"{ROOT}/output/BPM120/windkessel_sensitivity/baseline"

# Remaining WK cases (same mesh, different BC)
WK_REMAINING = [
    "blood_pressure_110_70",
    "blood_pressure_130_90",
    "murray_exponent_2p0",
    "murray_exponent_2p5",
    "pwv_10p0",
]

# Profile cases (same mesh as WK baseline, different numerics)
PROFILE_CASES = [
    "profile_robust",
    "profile_standard",
    "profile_accurate",
]

def copy_entire_case(src_dir, dst_dir):
    """Copy entire OpenFOAM case directory."""
    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir, symlinks=True)
    print(f"  Copied entire case from {os.path.basename(src_dir)}")

def setup_wk_case(config_file, output_dir, case_name):
    """Setup WK case - copy everything, re-run boundary for new WK params."""
    print(f"\n{'='*60}")
    print(f"Setting up: {case_name}")
    print(f"{'='*60}")

    # Copy entire case from baseline
    print("Copying case from baseline...")
    copy_entire_case(WK_BASELINE, output_dir)

    # Copy input files (CSV, STL)
    for ext in ["csv", "stl"]:
        for f in os.listdir(PATIENT_INPUT):
            if f.endswith(f".{ext}"):
                src = f"{PATIENT_INPUT}/{f}"
                dst = f"{output_dir}/{f}"
                shutil.copy2(src, dst)

    # Re-run boundary step to recalculate Windkessel with new params
    print("Running boundary setup with new Windkessel params...")
    cmd = [
        "python3", "run_patient.py", "BPM120",
        "--config", config_file,
        "--case-dir", output_dir,
        "--steps", "boundary"
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ SUCCESS: {case_name}")
        return True
    else:
        print(f"❌ FAILED: {case_name}")
        if result.stderr:
            # Print last 10 lines of error
            lines = result.stderr.strip().split('\n')
            for line in lines[-10:]:
                print(f"  {line}")
        return False

def setup_profile_case(config_file, output_dir, case_name):
    """Setup profile case - copy everything, regenerate fvSchemes/fvSolution."""
    print(f"\n{'='*60}")
    print(f"Setting up: {case_name}")
    print(f"{'='*60}")

    # Copy entire case from baseline
    print("Copying case from baseline...")
    copy_entire_case(WK_BASELINE, output_dir)

    # Copy input files (CSV, STL)
    for ext in ["csv", "stl"]:
        for f in os.listdir(PATIENT_INPUT):
            if f.endswith(f".{ext}"):
                src = f"{PATIENT_INPUT}/{f}"
                dst = f"{output_dir}/{f}"
                shutil.copy2(src, dst)

    # Re-run case + boundary steps to regenerate files with new profile
    print("Regenerating case files with new numerical profile...")
    cmd = [
        "python3", "run_patient.py", "BPM120",
        "--config", config_file,
        "--case-dir", output_dir,
        "--steps", "case,boundary"
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ SUCCESS: {case_name}")
        return True
    else:
        print(f"❌ FAILED: {case_name}")
        if result.stderr:
            lines = result.stderr.strip().split('\n')
            for line in lines[-10:]:
                print(f"  {line}")
        return False

def main():
    os.chdir(ROOT)
    os.environ["PYTHONPATH"] = f"{ROOT}/src"

    success_count = 0
    total_count = len(WK_REMAINING) + len(PROFILE_CASES)

    # Setup remaining WK cases
    print("\n" + "="*60)
    print("WINDKESSEL SENSITIVITY (remaining cases)")
    print("="*60)

    for case in WK_REMAINING:
        config = f"{ROOT}/output/BPM120/windkessel_sensitivity/config_{case}.json"
        output = f"{ROOT}/output/BPM120/windkessel_sensitivity/{case}"
        if setup_wk_case(config, output, f"WK: {case}"):
            success_count += 1

    # Setup profile cases
    print("\n" + "="*60)
    print("NUMERICAL PROFILE SENSITIVITY")
    print("="*60)

    for case in PROFILE_CASES:
        config = f"{ROOT}/output/BPM120/profile_sensitivity/config_{case}.json"
        output = f"{ROOT}/output/BPM120/profile_sensitivity/{case}"
        if setup_profile_case(config, output, f"Profile: {case}"):
            success_count += 1

    print("\n" + "="*60)
    print(f"COMPLETED: {success_count}/{total_count} cases")
    print("="*60)

    return 0 if success_count == total_count else 1

if __name__ == "__main__":
    sys.exit(main())
