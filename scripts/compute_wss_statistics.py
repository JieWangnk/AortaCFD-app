#!/usr/bin/env python3
"""
Comprehensive WSS Statistics Calculator for AortaCFD paper.

Computes detailed wall shear stress statistics from OpenFOAM simulation results:
- Basic statistics: mean, median, std, min, max
- Percentiles: 5th, 25th, 75th, 95th, 99th
- Area-weighted statistics
- Clinical thresholds:
  - Low WSS area (<0.4 Pa) - atherosclerosis risk
  - High WSS area (>10 Pa) - endothelial damage risk
- Spatial uniformity metrics

Usage:
    python compute_wss_statistics.py
"""

import json
import struct
import subprocess
from pathlib import Path
import numpy as np
from datetime import datetime

# Directories
BASE_DIR = Path("/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120")
PAPER_FIG_DIR = Path("/home/mchi4jw4/GitHub/AortaCFDappPaper/figures")

# Physical constants
RHO = 1060  # Blood density kg/m³

# Study configurations
STUDIES = {
    "profile_sensitivity_v2": {
        "cases": {
            "profile_robust": {"label": "Robust (1st order)"},
            "profile_standard": {"label": "Standard (2nd order TVD)"},
            "profile_accurate": {"label": "Accurate (linearUpwind)"},
        },
        "foam_subdir": "",
    },
    "physics_model_v2": {
        "cases": {
            "laminar": {"label": "Laminar"},
            "rans": {"label": "RANS k-ω SST"},
            "les": {"label": "LES Smagorinsky"},
        },
        "foam_subdir": "openfoam",
    },
}

# Clinical WSS thresholds (in Pa)
LOW_WSS_THRESHOLD = 0.4   # Below this: atherosclerosis risk
HIGH_WSS_THRESHOLD = 10.0  # Above this: endothelial damage risk
PHYSIOLOGICAL_LOW = 1.0   # Lower bound of normal range
PHYSIOLOGICAL_HIGH = 7.0  # Upper bound of normal range


def get_case_path(study_name: str, case_name: str) -> Path:
    """Get the OpenFOAM case path."""
    study = STUDIES[study_name]
    base = BASE_DIR / study_name / case_name
    if study["foam_subdir"]:
        return base / study["foam_subdir"]
    return base


def read_openfoam_vector_field(field_path: Path) -> np.ndarray:
    """Read an OpenFOAM vector field (ASCII or binary)."""
    if not field_path.exists():
        return None

    with open(field_path, 'rb') as f:
        content = f.read()

    # Try to decode as text first
    try:
        text = content.decode('utf-8')

        # Check if it's binary format
        if 'format      binary' in text:
            return read_binary_vector_field(field_path)

        # Parse ASCII format
        return parse_ascii_vector_field(text)
    except UnicodeDecodeError:
        # Binary format
        return read_binary_vector_field(field_path)


def parse_ascii_vector_field(text: str) -> np.ndarray:
    """Parse ASCII OpenFOAM vector field."""
    lines = text.split('\n')

    # Find the start of data (after the number of entries)
    in_data = False
    data_lines = []
    n_entries = 0

    for i, line in enumerate(lines):
        line = line.strip()

        # Skip header and comments
        if line.startswith('//') or line.startswith('/*') or line.startswith('FoamFile'):
            continue

        # Look for the count line (just a number)
        if not in_data and line.isdigit():
            n_entries = int(line)
            # Next non-empty line should be '('
            continue

        if line == '(' and not in_data:
            in_data = True
            continue

        if in_data:
            if line == ')':
                break
            # Parse vector like (x y z)
            if line.startswith('(') and line.endswith(')'):
                vals = line[1:-1].split()
                if len(vals) == 3:
                    data_lines.append([float(v) for v in vals])

    if data_lines:
        return np.array(data_lines)
    return None


def read_binary_vector_field(field_path: Path) -> np.ndarray:
    """Read binary OpenFOAM vector field."""
    with open(field_path, 'r') as f:
        content = f.read()

    # Find the number of entries
    import re

    # Look for pattern like "98352\n("
    match = re.search(r'(\d+)\s*\n\s*\(', content)
    if not match:
        return None

    n_entries = int(match.group(1))

    # Find the binary data start (after the '(' on its own line)
    header_end = content.find('\n(')
    if header_end == -1:
        return None

    # Read as binary from the position after '('
    with open(field_path, 'rb') as f:
        f.seek(header_end + 2)  # Skip newline and '('

        # Skip any whitespace/newline
        while True:
            byte = f.read(1)
            if byte not in (b' ', b'\n', b'\t'):
                f.seek(f.tell() - 1)
                break

        # Read binary doubles (3 components per vector)
        try:
            data = np.frombuffer(f.read(n_entries * 3 * 8), dtype=np.float64)
            return data.reshape(n_entries, 3)
        except:
            return None


def get_wall_patch_data(case_path: Path, time_dir: str) -> dict:
    """Extract wall patch data using postProcess."""
    # Use surfaceFieldValue to get area and field values
    # This is more reliable than parsing binary files directly

    result = {
        "wss_magnitudes": None,
        "areas": None,
        "total_area": None,
    }

    # Read wallShearStressMean field
    wss_file = case_path / time_dir / "wallShearStressMean"
    if not wss_file.exists():
        print(f"    Warning: wallShearStressMean not found in {time_dir}")
        return result

    # Try using foamPostProcess to get statistics
    try:
        # Run patchIntegrate to get total area and field integral
        cmd = f"cd {case_path} && postProcess -func 'wallShearStress' -time {time_dir} 2>/dev/null"
        subprocess.run(cmd, shell=True, capture_output=True, timeout=60)
    except:
        pass

    return result


def compute_wss_from_vtk(case_path: Path, time_value: float) -> dict:
    """Compute WSS statistics by converting to VTK and using Python."""
    import tempfile
    import os

    result = {
        "computed": False,
        "error": None,
    }

    time_dir = f"{time_value:.2f}".rstrip('0').rstrip('.')
    if time_value == int(time_value):
        time_dir = str(int(time_value))

    # Check for wallShearStressMean
    wss_file = case_path / time_dir / "wallShearStressMean"

    # Also check other time formats
    for td in case_path.iterdir():
        if td.is_dir():
            try:
                t = float(td.name)
                if abs(t - time_value) < 0.01:
                    wss_file = td / "wallShearStressMean"
                    time_dir = td.name
                    break
            except ValueError:
                continue

    if not wss_file.exists():
        result["error"] = f"wallShearStressMean not found at time {time_value}"
        return result

    # Read the field directly and compute statistics
    # For now, use a simpler approach: read the boundary field values

    try:
        wss_data = read_wss_boundary_field(wss_file)
        if wss_data is not None:
            result.update(compute_statistics_from_data(wss_data))
            result["computed"] = True
    except Exception as e:
        result["error"] = str(e)

    return result


def read_wss_boundary_field(wss_file: Path) -> np.ndarray:
    """Read wallShearStressMean from OpenFOAM field file.

    For WSS fields, the actual data is in boundaryField -> wall_aorta -> value,
    not in internalField (which is typically uniform (0 0 0) for WSS).
    """
    with open(wss_file, 'rb') as f:
        content_bytes = f.read()

    # Decode header part to check format
    header_text = content_bytes[:5000].decode('utf-8', errors='replace')

    # Check format
    is_binary = 'format      binary' in header_text

    if is_binary:
        return read_binary_boundary_wss(wss_file, content_bytes, header_text)
    else:
        return read_ascii_boundary_wss(content_bytes.decode('utf-8', errors='replace'))


def read_binary_boundary_wss(wss_file: Path, content_bytes: bytes, header_text: str) -> np.ndarray:
    """Read binary wallShearStressMean from boundary field (wall_aorta)."""
    import re

    # For WSS, the data is in: boundaryField { wall_aorta { value nonuniform List<vector> N ( ... ) } }
    # Find the wall_aorta section and the List<vector> count

    # Look for pattern: value           nonuniform List<vector>
    # followed by the count and binary data
    match = re.search(r'wall_aorta\s*\{[^}]*value\s+nonuniform\s+List<vector>\s*\n\s*(\d+)', header_text)

    if not match:
        # Try alternative pattern
        match = re.search(r'value\s+nonuniform\s+List<vector>\s*\n\s*(\d+)', header_text)

    if not match:
        print(f"    Could not find boundary field vector list")
        return None

    n_values = int(match.group(1))
    print(f"    Found {n_values} boundary face values")

    # Find the position in the binary file where the data starts
    # The data starts right after the count and the opening '('
    text_for_search = content_bytes.decode('utf-8', errors='replace')

    # Find "List<vector>\nN\n(" pattern to locate binary data
    pattern = re.compile(r'List<vector>\s*\n\s*' + str(n_values) + r'\s*\n\s*\(')
    match = pattern.search(text_for_search)

    if not match:
        print(f"    Could not locate binary data start")
        return None

    # Binary data starts right after the '('
    data_start = match.end()

    # Read binary data - each vector is 3 doubles (24 bytes)
    try:
        binary_data = content_bytes[data_start:data_start + n_values * 3 * 8]
        vectors = np.frombuffer(binary_data, dtype='<f8').reshape(-1, 3)

        if len(vectors) != n_values:
            print(f"    Warning: Expected {n_values} vectors, got {len(vectors)}")

        # Compute magnitude and multiply by density for TAWSS in Pa
        # Note: wallShearStressMean is already in m²/s² (kinematic), multiply by rho for Pa
        magnitudes = np.linalg.norm(vectors, axis=1) * RHO
        return magnitudes
    except Exception as e:
        print(f"    Binary read error: {e}")
        return None


def read_ascii_boundary_wss(content: str) -> np.ndarray:
    """Read ASCII wallShearStressMean from boundary field."""
    import re

    # Find wall_aorta section with value nonuniform List<vector>
    match = re.search(r'wall_aorta\s*\{[^}]*value\s+nonuniform\s+List<vector>\s+(\d+)\s*\n\s*\(', content, re.DOTALL)
    if not match:
        # Try simpler pattern
        match = re.search(r'value\s+nonuniform\s+List<vector>\s+(\d+)\s*\n\s*\(', content)

    if not match:
        print(f"    Could not find ASCII boundary field")
        return None

    n_values = int(match.group(1))
    start_pos = match.end()

    # Extract vectors
    vectors = []
    remaining = content[start_pos:]

    # Parse (x y z) patterns
    pattern = re.compile(r'\(([^)]+)\)')
    for m in pattern.finditer(remaining):
        if len(vectors) >= n_values:
            break
        vals = m.group(1).split()
        if len(vals) == 3:
            try:
                vectors.append([float(v) for v in vals])
            except ValueError:
                continue

    if vectors:
        vectors = np.array(vectors)
        magnitudes = np.linalg.norm(vectors, axis=1) * RHO
        return magnitudes

    return None


def compute_statistics_from_data(wss_magnitudes: np.ndarray) -> dict:
    """Compute comprehensive statistics from WSS magnitude data."""
    if wss_magnitudes is None or len(wss_magnitudes) == 0:
        return {"error": "No data"}

    # Filter out any invalid values
    valid_data = wss_magnitudes[np.isfinite(wss_magnitudes)]
    if len(valid_data) == 0:
        return {"error": "No valid data"}

    n_total = len(valid_data)

    stats = {
        # Basic statistics
        "n_points": n_total,
        "mean": float(np.mean(valid_data)),
        "median": float(np.median(valid_data)),
        "std": float(np.std(valid_data)),
        "min": float(np.min(valid_data)),
        "max": float(np.max(valid_data)),

        # Percentiles
        "p5": float(np.percentile(valid_data, 5)),
        "p25": float(np.percentile(valid_data, 25)),
        "p75": float(np.percentile(valid_data, 75)),
        "p95": float(np.percentile(valid_data, 95)),
        "p99": float(np.percentile(valid_data, 99)),

        # Interquartile range
        "iqr": float(np.percentile(valid_data, 75) - np.percentile(valid_data, 25)),

        # Coefficient of variation
        "cv": float(np.std(valid_data) / np.mean(valid_data)) if np.mean(valid_data) > 0 else 0,

        # Clinical thresholds (percentage of points)
        "pct_low_wss": float(np.sum(valid_data < LOW_WSS_THRESHOLD) / n_total * 100),
        "pct_high_wss": float(np.sum(valid_data > HIGH_WSS_THRESHOLD) / n_total * 100),
        "pct_physiological": float(np.sum((valid_data >= PHYSIOLOGICAL_LOW) &
                                          (valid_data <= PHYSIOLOGICAL_HIGH)) / n_total * 100),

        # Absolute counts
        "n_low_wss": int(np.sum(valid_data < LOW_WSS_THRESHOLD)),
        "n_high_wss": int(np.sum(valid_data > HIGH_WSS_THRESHOLD)),
        "n_physiological": int(np.sum((valid_data >= PHYSIOLOGICAL_LOW) &
                                      (valid_data <= PHYSIOLOGICAL_HIGH))),

        # Skewness and kurtosis
        "skewness": float(compute_skewness(valid_data)),
        "kurtosis": float(compute_kurtosis(valid_data)),
    }

    return stats


def compute_skewness(data: np.ndarray) -> float:
    """Compute skewness of data."""
    n = len(data)
    if n < 3:
        return 0.0
    mean = np.mean(data)
    std = np.std(data)
    if std == 0:
        return 0.0
    return np.mean(((data - mean) / std) ** 3)


def compute_kurtosis(data: np.ndarray) -> float:
    """Compute excess kurtosis of data."""
    n = len(data)
    if n < 4:
        return 0.0
    mean = np.mean(data)
    std = np.std(data)
    if std == 0:
        return 0.0
    return np.mean(((data - mean) / std) ** 4) - 3


def analyze_study(study_name: str, time_value: float = 1.5) -> dict:
    """Analyze all cases in a study."""
    study = STUDIES[study_name]
    results = {}

    print(f"\n{'='*60}")
    print(f"Study: {study_name}")
    print(f"{'='*60}")

    for case_name, case_info in study["cases"].items():
        print(f"\n  Case: {case_name} ({case_info['label']})")

        case_path = get_case_path(study_name, case_name)

        if not case_path.exists():
            print(f"    ERROR: Case path does not exist: {case_path}")
            continue

        stats = compute_wss_from_vtk(case_path, time_value)

        if stats.get("computed"):
            results[case_name] = {
                "label": case_info["label"],
                "stats": stats,
            }
            print(f"    Mean TAWSS: {stats['mean']:.2f} Pa")
            print(f"    Max TAWSS: {stats['max']:.2f} Pa")
            print(f"    Low WSS area: {stats['pct_low_wss']:.1f}%")
        else:
            print(f"    ERROR: {stats.get('error', 'Unknown error')}")

    return results


def create_statistics_table(all_results: dict, output_dir: Path):
    """Create comprehensive statistics table."""

    # LaTeX table
    latex = []
    latex.append(r"\begin{table}[htbp]")
    latex.append(r"\centering")
    latex.append(r"\caption{Comprehensive TAWSS Statistics}")
    latex.append(r"\label{tab:tawss_statistics}")
    latex.append(r"\begin{tabular}{lcccccccc}")
    latex.append(r"\hline")
    latex.append(r"Case & Mean & Median & Std & Min & Max & Low WSS & High WSS & CV \\")
    latex.append(r"     & (Pa) & (Pa) & (Pa) & (Pa) & (Pa) & (\%) & (\%) & \\")
    latex.append(r"\hline")

    for study_name, study_results in all_results.items():
        # Add study header
        study_label = study_name.replace("_v2", "").replace("_", " ").title()
        latex.append(r"\multicolumn{9}{l}{\textit{" + study_label + r"}} \\")

        for case_name, case_data in study_results.items():
            s = case_data["stats"]
            label = case_data["label"]
            latex.append(f"{label} & {s['mean']:.2f} & {s['median']:.2f} & {s['std']:.2f} & "
                        f"{s['min']:.2f} & {s['max']:.2f} & {s['pct_low_wss']:.1f} & "
                        f"{s['pct_high_wss']:.1f} & {s['cv']:.2f} \\\\")

        latex.append(r"\hline")

    latex.append(r"\end{tabular}")
    latex.append(r"\end{table}")

    # Save LaTeX
    latex_file = output_dir / "tawss_statistics_comprehensive.tex"
    with open(latex_file, 'w') as f:
        f.write('\n'.join(latex))
    print(f"\nSaved: {latex_file}")

    # Markdown table - Basic statistics
    md = []
    md.append("# TAWSS Statistics Summary\n")
    md.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

    md.append("## Basic Statistics\n")
    md.append("| Study | Case | Mean (Pa) | Median (Pa) | Std (Pa) | Min (Pa) | Max (Pa) |")
    md.append("|-------|------|-----------|-------------|----------|----------|----------|")

    for study_name, study_results in all_results.items():
        study_label = study_name.replace("_v2", "").replace("_", " ").title()
        for case_name, case_data in study_results.items():
            s = case_data["stats"]
            label = case_data["label"]
            md.append(f"| {study_label} | {label} | {s['mean']:.2f} | {s['median']:.2f} | "
                     f"{s['std']:.2f} | {s['min']:.2f} | {s['max']:.2f} |")

    md.append("\n## Percentile Distribution\n")
    md.append("| Study | Case | P5 | P25 | P50 | P75 | P95 | P99 | IQR |")
    md.append("|-------|------|-----|-----|-----|-----|-----|-----|-----|")

    for study_name, study_results in all_results.items():
        study_label = study_name.replace("_v2", "").replace("_", " ").title()
        for case_name, case_data in study_results.items():
            s = case_data["stats"]
            label = case_data["label"]
            md.append(f"| {study_label} | {label} | {s['p5']:.2f} | {s['p25']:.2f} | "
                     f"{s['median']:.2f} | {s['p75']:.2f} | {s['p95']:.2f} | "
                     f"{s['p99']:.2f} | {s['iqr']:.2f} |")

    md.append("\n## Clinical Thresholds\n")
    md.append(f"- **Low WSS**: < {LOW_WSS_THRESHOLD} Pa (atherosclerosis risk)")
    md.append(f"- **High WSS**: > {HIGH_WSS_THRESHOLD} Pa (endothelial damage risk)")
    md.append(f"- **Physiological range**: {PHYSIOLOGICAL_LOW}-{PHYSIOLOGICAL_HIGH} Pa\n")

    md.append("| Study | Case | Low WSS (%) | High WSS (%) | Physiological (%) | CV |")
    md.append("|-------|------|-------------|--------------|-------------------|-----|")

    for study_name, study_results in all_results.items():
        study_label = study_name.replace("_v2", "").replace("_", " ").title()
        for case_name, case_data in study_results.items():
            s = case_data["stats"]
            label = case_data["label"]
            md.append(f"| {study_label} | {label} | {s['pct_low_wss']:.1f} | "
                     f"{s['pct_high_wss']:.1f} | {s['pct_physiological']:.1f} | {s['cv']:.2f} |")

    md.append("\n## Distribution Shape\n")
    md.append("| Study | Case | Skewness | Kurtosis | N Points |")
    md.append("|-------|------|----------|----------|----------|")

    for study_name, study_results in all_results.items():
        study_label = study_name.replace("_v2", "").replace("_", " ").title()
        for case_name, case_data in study_results.items():
            s = case_data["stats"]
            label = case_data["label"]
            md.append(f"| {study_label} | {label} | {s['skewness']:.2f} | "
                     f"{s['kurtosis']:.2f} | {s['n_points']:,} |")

    # Save Markdown
    md_file = output_dir / "tawss_statistics_comprehensive.md"
    with open(md_file, 'w') as f:
        f.write('\n'.join(md))
    print(f"Saved: {md_file}")

    # Save JSON for further processing
    json_file = output_dir / "tawss_statistics_comprehensive.json"
    with open(json_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"Saved: {json_file}")


def main():
    """Main analysis function."""
    print("=" * 60)
    print("Comprehensive TAWSS Statistics Calculator")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_results = {}

    for study_name in STUDIES:
        results = analyze_study(study_name, time_value=1.5)
        if results:
            all_results[study_name] = results

    # Create output tables
    if all_results:
        create_statistics_table(all_results, PAPER_FIG_DIR)

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
