#!/usr/bin/env python3
"""
Extract pressure and velocity data from windkessel sensitivity study cases.

This script uses OpenFOAM's foamPostProcess to extract average pressure values
from each outlet patch for all time steps in the last cardiac cycle.

Output: JSON file with hemodynamic metrics for each case.
"""

import subprocess
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Blood density for converting kinematic pressure
RHO = 1060  # kg/m³
MMHG_TO_PA = 133.322


def extract_patch_pressure_series(case_dir: Path, patch: str, time_range: str = "1:") -> List[Tuple[float, float]]:
    """
    Extract pressure time series from a patch.

    Returns list of (time, pressure_Pa) tuples.
    """
    cmd = [
        "bash", "-c",
        f"source /opt/openfoam12/etc/bashrc && "
        f"cd {case_dir} && "
        f"foamPostProcess -solver incompressibleFluid "
        f"-func 'patchAverage(p, name={patch}_avg, patch={patch})' "
        f"-time '{time_range}' 2>&1"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + result.stderr

    # Parse output for pressure values
    pressures = []
    time = None

    for line in output.split('\n'):
        # Extract time
        if line.startswith('Time = '):
            time = float(line.split('=')[1].strip().rstrip('s'))
        # Extract pressure
        match = re.search(rf'areaAverage\("{patch}"\) of p = ([\d.e+-]+)', line)
        if match and time is not None:
            # Convert kinematic pressure to absolute pressure in Pa
            p_kinematic = float(match.group(1))
            p_pa = p_kinematic * RHO
            pressures.append((time, p_pa))

    return pressures


def extract_peak_velocity(case_dir: Path, time: str = "latest") -> float:
    """Extract maximum velocity magnitude from the domain."""
    cmd = [
        "bash", "-c",
        f"source /opt/openfoam12/etc/bashrc && "
        f"cd {case_dir} && "
        f"foamPostProcess -solver incompressibleFluid "
        f"-func 'mag(U)' -latestTime 2>&1 | grep -E 'max\\(mag\\(U\\)\\)'"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    # This may need adjustment based on actual output format
    return 0.0  # Placeholder


def analyze_case(case_dir: Path) -> Dict:
    """Analyze a single windkessel sensitivity case."""
    case_name = case_dir.name
    print(f"  Processing {case_name}...")

    # Extract pressure from each outlet
    outlets = ['outlet1', 'outlet2', 'outlet3', 'outlet4']

    all_pressures = []
    outlet_data = {}

    for outlet in outlets:
        try:
            pressures = extract_patch_pressure_series(case_dir, outlet)
            if pressures:
                outlet_data[outlet] = pressures
                all_pressures.extend([p for _, p in pressures])
        except Exception as e:
            print(f"    Warning: Failed to extract {outlet}: {e}")

    if not all_pressures:
        return {"case_name": case_name, "error": "No pressure data extracted"}

    # Calculate systolic and diastolic from outlet pressures
    p_systolic = max(all_pressures) / MMHG_TO_PA
    p_diastolic = min(all_pressures) / MMHG_TO_PA
    p_mean = sum(all_pressures) / len(all_pressures) / MMHG_TO_PA

    # Extract execution time from log
    log_path = case_dir / "logs" / "log.solver"
    exec_time = None
    if log_path.exists():
        with open(log_path) as f:
            for line in f:
                if "ExecutionTime" in line:
                    match = re.search(r'ExecutionTime = ([\d.]+)', line)
                    if match:
                        exec_time = float(match.group(1))

    return {
        "case_name": case_name,
        "p_systolic_mmHg": round(p_systolic, 1),
        "p_diastolic_mmHg": round(p_diastolic, 1),
        "p_mean_mmHg": round(p_mean, 1),
        "p_pulse_mmHg": round(p_systolic - p_diastolic, 1),
        "execution_time_hours": round(exec_time / 3600, 1) if exec_time else None,
        "outlet_data": {
            outlet: {
                "times": [t for t, _ in data],
                "pressures_mmHg": [round(p / MMHG_TO_PA, 1) for _, p in data]
            }
            for outlet, data in outlet_data.items()
        }
    }


def main():
    study_dir = Path("/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120/windkessel_sensitivity")

    # List of cases
    cases = [
        "baseline",
        "tau_1p0", "tau_1p5", "tau_2p5",
        "pwv_4p0", "pwv_8p0", "pwv_10p0",
        "murray_exponent_2p0", "murray_exponent_2p5",
        "blood_pressure_110_70", "blood_pressure_130_90"
    ]

    results = {}

    print("Extracting windkessel sensitivity results...")
    for case in cases:
        case_dir = study_dir / case
        if case_dir.exists():
            results[case] = analyze_case(case_dir)
        else:
            print(f"  Skipping {case}: directory not found")

    # Save results
    output_path = study_dir / "sensitivity_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_path}")

    # Print summary table
    print("\n" + "=" * 80)
    print("WINDKESSEL SENSITIVITY SUMMARY")
    print("=" * 80)
    print(f"{'Case':<25} {'P_sys':>10} {'P_dia':>10} {'Runtime':>10}")
    print(f"{'':<25} {'(mmHg)':>10} {'(mmHg)':>10} {'(hours)':>10}")
    print("-" * 80)

    for case in cases:
        if case in results and "error" not in results[case]:
            r = results[case]
            runtime = f"{r['execution_time_hours']:.1f}" if r['execution_time_hours'] else "N/A"
            print(f"{case:<25} {r['p_systolic_mmHg']:>10.1f} {r['p_diastolic_mmHg']:>10.1f} {runtime:>10}")

    print("=" * 80)


if __name__ == "__main__":
    main()
