#!/usr/bin/env python3
"""
Analyze profile sensitivity results for AortaCFD paper.
Compares robust, standard, and accurate numerical profiles.
"""

import json
import re
import subprocess
from pathlib import Path
import numpy as np

BASE_DIR = Path("/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120/profile_sensitivity")

PROFILES = ["profile_robust", "profile_standard", "profile_accurate"]

# Physical constants
PA_TO_MMHG = 1.0 / 133.322

def parse_log_solver(log_path):
    """Extract metrics from log.solver file."""
    metrics = {
        "final_time": 0,
        "execution_time": 0,
        "clock_time": 0,
        "total_timesteps": 0,
        "avg_outer_iterations": 0,
        "final_p_residual": 0,
        "final_U_residual": 0,
    }

    if not log_path.exists():
        return metrics

    with open(log_path, 'r') as f:
        content = f.read()

    # Find final time
    time_matches = re.findall(r'^Time = ([\d.]+)s?', content, re.MULTILINE)
    if time_matches:
        metrics["final_time"] = float(time_matches[-1])
        metrics["total_timesteps"] = len(time_matches)

    # Find execution time
    exec_matches = re.findall(r'ExecutionTime = ([\d.]+) s', content)
    if exec_matches:
        metrics["execution_time"] = float(exec_matches[-1])

    clock_matches = re.findall(r'ClockTime = (\d+) s', content)
    if clock_matches:
        metrics["clock_time"] = int(clock_matches[-1])

    # Find average outer iterations (PIMPLE)
    iter_matches = re.findall(r'PIMPLE: Iteration (\d+)', content)
    if iter_matches:
        # Count how many times we see each iteration number
        max_iters = [int(i) for i in iter_matches]
        # Group by timestep - find the max iteration for each timestep
        metrics["avg_outer_iterations"] = np.mean(max_iters) if max_iters else 0

    # Find final residuals
    p_residuals = re.findall(r'Solving for p.*Final residual = ([\d.e+-]+)', content)
    if p_residuals:
        metrics["final_p_residual"] = float(p_residuals[-1])

    U_residuals = re.findall(r'Solving for Ux.*Final residual = ([\d.e+-]+)', content)
    if U_residuals:
        metrics["final_U_residual"] = float(U_residuals[-1])

    return metrics


def get_time_directories(case_dir):
    """Get list of time directories (excluding 0)."""
    times = []
    for item in case_dir.iterdir():
        if item.is_dir():
            try:
                t = float(item.name)
                if t > 0:
                    times.append(t)
            except ValueError:
                pass
    return sorted(times)


def read_field_stats(case_dir, time, field="p"):
    """Read basic statistics from a field file."""
    field_path = case_dir / str(time) / field
    if not field_path.exists():
        return None

    try:
        with open(field_path, 'r', errors='ignore') as f:
            content = f.read()

        # Check if it's ASCII format
        match = re.search(r'internalField\s+nonuniform List<scalar>\s*\n\s*(\d+)\s*\n\s*\(([\s\S]*?)\)', content)
        if match:
            n_values = int(match.group(1))
            values_str = match.group(2)
            # Parse a sample of values for statistics
            values = [float(v) for v in values_str.split()[:min(10000, n_values)]]
            return {
                "min": min(values),
                "max": max(values),
                "mean": np.mean(values),
                "std": np.std(values),
            }

        # Check for uniform field
        match = re.search(r'internalField\s+uniform\s+([\d.e+-]+)', content)
        if match:
            val = float(match.group(1))
            return {"min": val, "max": val, "mean": val, "std": 0}

        # Binary format - try to extract from header info only
        return None
    except Exception as e:
        print(f"  Warning: Could not read {field_path}: {e}")
        return None


def read_postprocessing_pressure(case_dir, patch_name="outlet1"):
    """Read pressure time series from postProcessing data."""
    pp_dir = case_dir / "postProcessing" / f"{patch_name}_avg"
    if not pp_dir.exists():
        return None, None

    times = []
    pressures = []

    for time_dir in sorted(pp_dir.iterdir()):
        if time_dir.is_dir():
            dat_file = time_dir / "surfaceFieldValue.dat"
            if dat_file.exists():
                with open(dat_file, 'r') as f:
                    for line in f:
                        if line.startswith('#'):
                            continue
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            try:
                                t = float(parts[0])
                                p = float(parts[1])
                                times.append(t)
                                pressures.append(p)
                            except ValueError:
                                pass

    if times:
        return np.array(times), np.array(pressures)
    return None, None


def run_postprocess_for_profile(case_dir):
    """Run postProcess to generate pressure averages."""
    import os

    # Check if postProcessing already exists
    pp_dir = case_dir / "postProcessing"
    if pp_dir.exists() and (pp_dir / "outlet1_avg").exists():
        return True

    # Create function object file for surface averaging
    funcs_dir = case_dir / "system" / "functions"
    funcs_dir.mkdir(exist_ok=True)

    # Generate patchAverage function objects
    patches = ["inlet", "outlet1", "outlet2", "outlet3", "outlet4"]
    for patch in patches:
        func_file = funcs_dir / f"{patch}_avg"
        func_content = f'''/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  12                                    |
|   \\\\  /    A nd           | Website:  www.openfoam.org                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       dictionary;
    object      {patch}_avg;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

type            surfaceFieldValue;
libs            ("libfieldFunctionObjects.so");
writeControl    writeTime;
writeFields     false;
log             true;
operation       areaAverage;
select          patch;
patch           {patch};
fields          (p);

// ************************************************************************* //
'''
        with open(func_file, 'w') as f:
            f.write(func_content)

    # Run postProcess
    orig_dir = os.getcwd()
    os.chdir(case_dir)
    try:
        result = subprocess.run(
            ["bash", "-c", "source /opt/openfoam12/etc/bashrc && postProcess -funcs '(inlet_avg outlet1_avg outlet2_avg outlet3_avg outlet4_avg)'"],
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  Warning: postProcess failed: {e}")
        return False
    finally:
        os.chdir(orig_dir)


def main():
    results = {}

    print("=" * 70)
    print("PROFILE SENSITIVITY ANALYSIS - AortaCFD")
    print("=" * 70)

    for profile in PROFILES:
        case_dir = BASE_DIR / profile
        log_path = case_dir / "logs" / "log.solver"

        print(f"\n--- {profile.upper()} ---")

        # Parse solver log
        metrics = parse_log_solver(log_path)

        # Check for time directories (reconstructed results)
        times = get_time_directories(case_dir)

        if times:
            metrics["completed"] = True
            metrics["final_time_dir"] = max(times)
            metrics["num_time_dirs"] = len(times)

            # Try to run postProcess to get pressure data
            print("  Running postProcess for pressure averages...")
            run_postprocess_for_profile(case_dir)

            # Read outlet pressure from postProcessing
            times_p, outlet1_p = read_postprocessing_pressure(case_dir, "outlet1")
            if times_p is not None and len(times_p) > 0:
                # Get last cardiac cycle (t > 1.0)
                mask = times_p >= 1.0
                if np.any(mask):
                    last_cycle_p = outlet1_p[mask]
                    metrics["outlet1_p_mean_Pa"] = float(np.mean(last_cycle_p))
                    metrics["outlet1_p_max_Pa"] = float(np.max(last_cycle_p))
                    metrics["outlet1_p_min_Pa"] = float(np.min(last_cycle_p))
                    metrics["outlet1_p_mean_mmHg"] = metrics["outlet1_p_mean_Pa"] * PA_TO_MMHG
                    metrics["outlet1_p_max_mmHg"] = metrics["outlet1_p_max_Pa"] * PA_TO_MMHG

            # Read inlet pressure
            times_in, inlet_p = read_postprocessing_pressure(case_dir, "inlet")
            if times_in is not None and len(times_in) > 0:
                mask = times_in >= 1.0
                if np.any(mask):
                    last_cycle_in = inlet_p[mask]
                    metrics["inlet_p_mean_Pa"] = float(np.mean(last_cycle_in))
                    metrics["inlet_p_mean_mmHg"] = metrics["inlet_p_mean_Pa"] * PA_TO_MMHG

            # Compute pressure drop
            if "inlet_p_mean_Pa" in metrics and "outlet1_p_mean_Pa" in metrics:
                metrics["pressure_drop_Pa"] = metrics["inlet_p_mean_Pa"] - metrics["outlet1_p_mean_Pa"]
                metrics["pressure_drop_mmHg"] = metrics["pressure_drop_Pa"] * PA_TO_MMHG
        else:
            metrics["completed"] = False
            metrics["final_time_dir"] = 0
            metrics["num_time_dirs"] = 0

        results[profile] = metrics

        # Print summary
        print(f"  Completed: {metrics['completed']}")
        print(f"  Final time: {metrics.get('final_time_dir', 0):.2f} s ({metrics['num_time_dirs']} time dirs)")
        print(f"  Execution time: {metrics['execution_time']:.1f} s ({metrics['execution_time']/60:.1f} min)")
        print(f"  Total timesteps: {metrics['total_timesteps']}")
        if metrics.get('outlet1_p_mean_mmHg'):
            print(f"  Outlet1 pressure (mean): {metrics['outlet1_p_mean_mmHg']:.2f} mmHg")
            print(f"  Outlet1 pressure (peak): {metrics['outlet1_p_max_mmHg']:.2f} mmHg")
        if metrics.get('pressure_drop_mmHg'):
            print(f"  Pressure drop: {metrics['pressure_drop_mmHg']:.2f} mmHg")

    # Comparison summary
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)

    completed_profiles = [p for p in PROFILES if results[p]["completed"]]

    if len(completed_profiles) >= 2:
        ref_profile = "profile_standard"
        if ref_profile in completed_profiles:
            ref_time = results[ref_profile]["execution_time"]
            print(f"\nExecution time (relative to {ref_profile}):")
            for profile in completed_profiles:
                rel_time = results[profile]["execution_time"] / ref_time * 100
                print(f"  {profile}: {results[profile]['execution_time']:.0f}s ({rel_time:.0f}%)")

            if all(results[p].get("outlet1_p_mean_mmHg") for p in completed_profiles):
                ref_p = results[ref_profile]["outlet1_p_mean_mmHg"]
                print(f"\nOutlet pressure difference from {ref_profile}:")
                for profile in completed_profiles:
                    if profile != ref_profile:
                        diff = results[profile]["outlet1_p_mean_mmHg"] - ref_p
                        pct = diff / ref_p * 100 if ref_p != 0 else 0
                        print(f"  {profile}: {diff:+.2f} mmHg ({pct:+.1f}%)")

            if all(results[p].get("pressure_drop_mmHg") for p in completed_profiles):
                ref_dp = results[ref_profile]["pressure_drop_mmHg"]
                print(f"\nPressure drop difference from {ref_profile}:")
                for profile in completed_profiles:
                    if profile != ref_profile:
                        diff = results[profile]["pressure_drop_mmHg"] - ref_dp
                        pct = diff / ref_dp * 100 if ref_dp != 0 else 0
                        print(f"  {profile}: {diff:+.2f} mmHg ({pct:+.1f}%)")

    # Save results to JSON
    output_file = BASE_DIR / "profile_sensitivity_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")

    return results


if __name__ == "__main__":
    main()
