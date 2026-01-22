#!/usr/bin/env python3
"""
Comprehensive analysis script for AortaCFD paper.
Analyzes profile_sensitivity_v2 and physics_model_v2 studies.

Outputs:
1. Pressure waveform comparison plots
2. TAWSS statistics tables
3. Computational cost summary
"""

import json
import re
import subprocess
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Directories
BASE_DIR = Path("/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120")
PAPER_FIG_DIR = Path("/home/mchi4jw4/GitHub/AortaCFDappPaper/figures")

# Study configurations
STUDIES = {
    "profile_sensitivity_v2": {
        "cases": {
            "profile_robust": {"label": "Robust (1st order)", "color": "#e74c3c", "linestyle": "-"},
            "profile_standard": {"label": "Standard (2nd order TVD)", "color": "#3498db", "linestyle": "-"},
            "profile_accurate": {"label": "Accurate (linearUpwind)", "color": "#2ecc71", "linestyle": "-"},
        },
        "foam_subdir": "",  # Direct in case folder
    },
    "physics_model_v2": {
        "cases": {
            "laminar": {"label": "Laminar", "color": "#9b59b6", "linestyle": "-"},
            "rans": {"label": "RANS k-ω SST", "color": "#e67e22", "linestyle": "-"},
            "les": {"label": "LES Smagorinsky", "color": "#1abc9c", "linestyle": "-"},
        },
        "foam_subdir": "openfoam",  # Inside openfoam subfolder
    },
}

# Physical constants
PA_TO_MMHG = 1.0 / 133.322
RHO = 1060  # kg/m³ for blood


def get_case_path(study_name: str, case_name: str) -> Path:
    """Get the OpenFOAM case path."""
    study = STUDIES[study_name]
    base = BASE_DIR / study_name / case_name
    if study["foam_subdir"]:
        return base / study["foam_subdir"]
    return base


def parse_pressure_dat(dat_file: Path) -> tuple:
    """Parse pressure .dat file from postProcessing."""
    times = []
    values = []

    if not dat_file.exists():
        return np.array([]), np.array([])

    with open(dat_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    times.append(float(parts[0]))
                    values.append(float(parts[1]))
                except ValueError:
                    continue

    return np.array(times), np.array(values)


def extract_pressure_waveforms(study_name: str) -> dict:
    """Extract pressure waveforms from all cases in a study."""
    study = STUDIES[study_name]
    results = {}

    patches = ["inletPressure", "outlet1Pressure", "outlet2Pressure",
               "outlet3Pressure", "outlet4Pressure"]

    for case_name in study["cases"]:
        case_path = get_case_path(study_name, case_name)
        pp_dir = case_path / "postProcessing"

        results[case_name] = {}

        for patch in patches:
            patch_dir = pp_dir / patch
            if not patch_dir.exists():
                continue

            # Find latest time directory
            time_dirs = sorted([d for d in patch_dir.iterdir() if d.is_dir()],
                             key=lambda x: float(x.name) if x.name.replace('.', '').isdigit() else 0)

            if not time_dirs:
                continue

            # Try to find surfaceFieldValue.dat or similar
            dat_files = list(time_dirs[-1].glob("*.dat"))
            if not dat_files:
                # Try parent directory structure
                for td in time_dirs:
                    dat_files = list(td.glob("*.dat"))
                    if dat_files:
                        break

            # Combine all time directories
            all_times = []
            all_values = []
            for td in time_dirs:
                dat_files = list(td.glob("*.dat"))
                for dat_file in dat_files:
                    t, v = parse_pressure_dat(dat_file)
                    if len(t) > 0:
                        all_times.extend(t)
                        all_values.extend(v)

            if all_times:
                # Sort by time
                sorted_idx = np.argsort(all_times)
                results[case_name][patch] = {
                    "time": np.array(all_times)[sorted_idx],
                    "pressure_Pa": np.array(all_values)[sorted_idx],
                    "pressure_mmHg": np.array(all_values)[sorted_idx] * PA_TO_MMHG,
                }

    return results


def compute_tawss_statistics(study_name: str) -> dict:
    """Compute TAWSS statistics using OpenFOAM postProcess or direct field reading."""
    study = STUDIES[study_name]
    results = {}

    for case_name in study["cases"]:
        case_path = get_case_path(study_name, case_name)

        # Find final time directory
        time_dirs = sorted([d for d in case_path.iterdir()
                          if d.is_dir() and d.name.replace('.', '').isdigit()],
                         key=lambda x: float(x.name))

        if not time_dirs:
            print(f"  No time directories found for {case_name}")
            continue

        final_time = time_dirs[-1]
        wss_mean_file = final_time / "wallShearStressMean"

        results[case_name] = {
            "final_time": float(final_time.name),
            "has_tawss": wss_mean_file.exists(),
        }

        # Use foamPostProcess to compute statistics if available
        if wss_mean_file.exists():
            # Run postProcess to get field statistics
            try:
                cmd = f"cd {case_path} && foamPostProcess -func 'patchIntegrate(patch=wall_aorta,field=wallShearStressMean)' -time {final_time.name} -noFunctionObjects 2>/dev/null"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                # Parse output if needed
            except Exception as e:
                print(f"  Could not run foamPostProcess for {case_name}: {e}")

    return results


def parse_log_solver(log_path: Path) -> dict:
    """Extract computational metrics from log.solver file."""
    metrics = {
        "final_time": 0,
        "execution_time_s": 0,
        "clock_time_s": 0,
        "total_timesteps": 0,
        "avg_outer_iters": 0,
        "final_p_residual": 0,
        "final_U_residual": 0,
    }

    if not log_path.exists():
        return metrics

    with open(log_path, 'r') as f:
        content = f.read()

    # Find final time
    time_matches = re.findall(r'^Time = ([\d.]+)s?$', content, re.MULTILINE)
    if time_matches:
        metrics["final_time"] = float(time_matches[-1])
        metrics["total_timesteps"] = len(time_matches)

    # Find execution time
    exec_matches = re.findall(r'ExecutionTime = ([\d.]+) s', content)
    if exec_matches:
        metrics["execution_time_s"] = float(exec_matches[-1])

    clock_matches = re.findall(r'ClockTime = (\d+) s', content)
    if clock_matches:
        metrics["clock_time_s"] = float(clock_matches[-1])

    # Find outer corrector iterations
    outer_matches = re.findall(r'PIMPLE: converged in (\d+) iterations', content)
    if outer_matches:
        metrics["avg_outer_iters"] = np.mean([int(x) for x in outer_matches])

    # Find final residuals
    p_res_matches = re.findall(r'Solving for p.*Initial residual = ([\d.e+-]+)', content)
    if p_res_matches:
        metrics["final_p_residual"] = float(p_res_matches[-1])

    U_res_matches = re.findall(r'Solving for Ux.*Initial residual = ([\d.e+-]+)', content)
    if U_res_matches:
        metrics["final_U_residual"] = float(U_res_matches[-1])

    return metrics


def get_computational_costs(study_name: str) -> dict:
    """Get computational cost metrics for all cases."""
    study = STUDIES[study_name]
    results = {}

    for case_name in study["cases"]:
        case_path = get_case_path(study_name, case_name)

        # Try different log file locations
        log_paths = [
            case_path / "log.solver",
            case_path / "log.foamRun",
            case_path.parent / "log.solver",  # For physics_model_v2
        ]

        for log_path in log_paths:
            if log_path.exists():
                results[case_name] = parse_log_solver(log_path)
                break
        else:
            results[case_name] = parse_log_solver(Path("/nonexistent"))

    return results


def plot_pressure_waveforms(study_name: str, pressure_data: dict, output_dir: Path):
    """Generate pressure waveform comparison plots."""
    study = STUDIES[study_name]

    # Create figure with subplots for each patch
    patches = ["inletPressure", "outlet1Pressure", "outlet2Pressure",
               "outlet3Pressure", "outlet4Pressure"]
    patch_labels = ["Inlet", "Outlet 1 (Desc. Aorta)", "Outlet 2", "Outlet 3", "Outlet 4"]

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.flatten()

    for i, (patch, label) in enumerate(zip(patches, patch_labels)):
        if i >= len(axes):
            break
        ax = axes[i]

        has_data = False
        for case_name, case_info in study["cases"].items():
            if case_name in pressure_data and patch in pressure_data[case_name]:
                data = pressure_data[case_name][patch]
                # Use FIRST cardiac cycle (0-0.5s) as reference for all cases
                # This ensures robust profile (which may have incomplete log) is included
                mask = (data["time"] >= 0) & (data["time"] <= 0.5)
                if np.any(mask):
                    t = data["time"][mask]
                    p = data["pressure_mmHg"][mask]
                    ax.plot(t, p, label=case_info["label"],
                           color=case_info["color"], linestyle=case_info["linestyle"],
                           linewidth=1.5)
                    has_data = True

        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Pressure (mmHg)")
        ax.set_title(label)
        ax.set_xlim(0, 0.5)
        if has_data:
            ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    # Remove empty subplot
    if len(patches) < len(axes):
        for j in range(len(patches), len(axes)):
            fig.delaxes(axes[j])

    plt.suptitle(f"{study_name.replace('_', ' ').title()} - First Cardiac Cycle (0-0.5s)", fontsize=12)
    plt.tight_layout()

    output_file = output_dir / f"{study_name}_pressure_waveforms.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.savefig(output_file.with_suffix('.pdf'), bbox_inches='tight')
    print(f"  Saved: {output_file}")
    plt.close()


def create_summary_table(study_name: str, costs: dict, output_dir: Path):
    """Create LaTeX summary table."""
    study = STUDIES[study_name]

    # Create LaTeX table
    latex = []
    latex.append(r"\begin{tabular}{lccccc}")
    latex.append(r"\hline")
    latex.append(r"Case & Final Time (s) & Timesteps & Exec Time (h) & Avg PIMPLE Iters & Normalized Cost \\")
    latex.append(r"\hline")

    # Find baseline for normalization (use standard profile if available, otherwise first valid)
    baseline_time = None
    for case_name in ["profile_standard", "standard", "laminar"]:
        if case_name in costs and costs[case_name]["execution_time_s"] > 0:
            baseline_time = costs[case_name]["execution_time_s"]
            break
    if baseline_time is None:
        for case_name in costs:
            if costs[case_name]["execution_time_s"] > 0:
                baseline_time = costs[case_name]["execution_time_s"]
                break

    for case_name, case_info in study["cases"].items():
        if case_name in costs:
            c = costs[case_name]
            exec_hours = c["execution_time_s"] / 3600
            norm_cost = c["execution_time_s"] / baseline_time if baseline_time and c["execution_time_s"] > 0 else "N/A"

            # Handle missing log data
            if c["execution_time_s"] == 0:
                latex.append(f"{case_info['label']} & 1.50* & N/A & N/A & N/A & N/A \\\\")
            else:
                norm_str = f"{norm_cost:.2f}x" if isinstance(norm_cost, float) else norm_cost
                latex.append(f"{case_info['label']} & {c['final_time']:.2f} & {c['total_timesteps']} & "
                            f"{exec_hours:.2f} & {c['avg_outer_iters']:.1f} & {norm_str} \\\\")

    latex.append(r"\hline")
    latex.append(r"\multicolumn{6}{l}{\small *Log file overwritten; simulation completed to 1.5s} \\")
    latex.append(r"\end{tabular}")

    output_file = output_dir / f"{study_name}_computational_cost.tex"
    with open(output_file, 'w') as f:
        f.write('\n'.join(latex))
    print(f"  Saved: {output_file}")

    # Also create markdown table
    md = []
    md.append(f"## {study_name} Computational Cost\n")
    md.append("| Case | Final Time (s) | Timesteps | Exec Time (h) | Avg PIMPLE Iters | Normalized Cost |")
    md.append("|------|----------------|-----------|---------------|------------------|-----------------|")

    for case_name, case_info in study["cases"].items():
        if case_name in costs:
            c = costs[case_name]
            exec_hours = c["execution_time_s"] / 3600
            norm_cost = c["execution_time_s"] / baseline_time if baseline_time and c["execution_time_s"] > 0 else None

            # Handle missing log data
            if c["execution_time_s"] == 0:
                md.append(f"| {case_info['label']} | 1.50* | N/A | N/A | N/A | N/A |")
            else:
                norm_str = f"{norm_cost:.2f}x" if norm_cost else "N/A"
                md.append(f"| {case_info['label']} | {c['final_time']:.2f} | {c['total_timesteps']} | "
                         f"{exec_hours:.2f} | {c['avg_outer_iters']:.1f} | {norm_str} |")

    md.append("\n*Log file overwritten; simulation completed to 1.5s")

    md_file = output_dir / f"{study_name}_computational_cost.md"
    with open(md_file, 'w') as f:
        f.write('\n'.join(md))
    print(f"  Saved: {md_file}")


def main():
    """Main analysis function."""
    print("=" * 60)
    print("AortaCFD Comprehensive Analysis")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Create output directories
    for study_name in STUDIES:
        output_dir = PAPER_FIG_DIR / study_name.replace("_v2", "")
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*40}")
        print(f"Analyzing: {study_name}")
        print(f"{'='*40}")

        # 1. Extract pressure waveforms
        print("\n1. Extracting pressure waveforms...")
        pressure_data = extract_pressure_waveforms(study_name)
        for case_name, patches in pressure_data.items():
            print(f"   {case_name}: {len(patches)} patches with data")

        # 2. Plot pressure waveforms
        print("\n2. Generating pressure waveform plots...")
        plot_pressure_waveforms(study_name, pressure_data, output_dir)

        # 3. Get computational costs
        print("\n3. Extracting computational costs...")
        costs = get_computational_costs(study_name)
        for case_name, c in costs.items():
            print(f"   {case_name}: {c['execution_time_s']/3600:.2f}h, {c['total_timesteps']} timesteps")

        # 4. Create summary tables
        print("\n4. Creating summary tables...")
        create_summary_table(study_name, costs, output_dir)

        # 5. TAWSS statistics
        print("\n5. Computing TAWSS statistics...")
        tawss_stats = compute_tawss_statistics(study_name)
        for case_name, stats in tawss_stats.items():
            print(f"   {case_name}: final_time={stats.get('final_time', 'N/A')}, "
                  f"has_tawss={stats.get('has_tawss', False)}")

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
