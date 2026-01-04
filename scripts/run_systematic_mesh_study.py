#!/usr/bin/env python3
"""
Systematic Mesh Refinement Study for GCI Analysis

This script creates a proper mesh convergence study using span-based refinement
(cells_across_span) which is more appropriate for cardiovascular geometries.

Key principle: The cells_across_span parameter guarantees a minimum number of
cells across the vessel diameter, regardless of local geometry variations.
This provides consistent refinement ratios for valid Richardson extrapolation.

Mesh levels (using cells_across_span):
- Level 1 (Coarse):  cells_across_span = 10 → ~100k cells
- Level 2 (Medium):  cells_across_span = 15 → ~300k cells  (r ≈ 1.5)
- Level 3 (Fine):    cells_across_span = 20 → ~700k cells  (r ≈ 1.33)
- Level 4 (V.Fine):  cells_across_span = 25 → ~1.2M cells  (r ≈ 1.25)

The refinement ratio r = span_fine / span_coarse for cell spacing.
For 3-grid GCI with span=[10,15,20], r ≈ 1.33-1.5 which is acceptable.

Usage:
    python scripts/run_systematic_mesh_study.py --patient BPM120 --cycles 3
    python scripts/run_systematic_mesh_study.py --patient BPM120 --spans 10 15 20 --cycles 3
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import shutil

# Default patient directory
DEFAULT_PATIENT = "BPM120"


def create_mesh_config(base_config_path: Path, output_dir: Path,
                       cells_across_span: int, label: str) -> Path:
    """
    Create a mesh configuration file with specific cells_across_span.

    Parameters:
    -----------
    base_config_path : Path
        Path to base configuration JSON
    output_dir : Path
        Output directory for the study
    cells_across_span : int
        Number of cells across the vessel span (diameter)
    label : str
        Label for this mesh level (e.g., "span10", "span15", "span20")
    """
    with open(base_config_path) as f:
        config = json.load(f)

    # Update mesh settings for span-based refinement
    if "mesh" not in config:
        config["mesh"] = {}

    if "SNAPPY_SETTINGS" not in config["mesh"]:
        config["mesh"]["SNAPPY_SETTINGS"] = {}

    # Enable span-based refinement
    config["mesh"]["SNAPPY_SETTINGS"]["span_refinement_enabled"] = True
    config["mesh"]["SNAPPY_SETTINGS"]["cells_across_span"] = cells_across_span

    # Use span_refinement_level = 2 (DOE validated as safe)
    # Level 3 causes skewness > 4.0
    config["mesh"]["SNAPPY_SETTINGS"]["span_refinement_level"] = 2
    config["mesh"]["SNAPPY_SETTINGS"]["surfaceRefinementLevels"] = [1, 2]

    # Keep layer settings consistent across meshes for fair comparison
    config["mesh"]["SNAPPY_SETTINGS"]["addLayer"] = 5

    # Use high_quality preset for consistent mesh quality
    config["mesh"]["quality_preset"] = "high_quality"

    # Add study metadata
    config["study_metadata"] = {
        "type": "systematic_mesh_convergence_span",
        "cells_across_span": cells_across_span,
        "label": label,
        "span_refinement_level": 2,
        "timestamp": datetime.now().isoformat()
    }

    # Output path
    config_path = output_dir / f"config_{label}.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Created config: {config_path}")
    print(f"  cells_across_span: {cells_across_span}")

    return config_path


def run_simulation(config_path: Path, output_dir: Path, label: str,
                   cycles: int = 3, dry_run: bool = False) -> dict:
    """
    Run a simulation with the given configuration.

    Returns dict with results or error information.
    """
    run_dir = output_dir / label

    cmd = [
        sys.executable, "-m", "patient_runner.cli",
        str(config_path),
        "--output-dir", str(run_dir),
        "--profile", "robust",  # Use robust profile for mesh study
        "--cycles", str(cycles)
    ]

    print(f"\n{'='*60}")
    print(f"Running {label} mesh simulation...")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")

    if dry_run:
        print("  [DRY RUN - skipping execution]")
        return {"status": "dry_run", "label": label}

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hour timeout
            cwd=Path(__file__).parent.parent
        )

        return {
            "status": "success" if result.returncode == 0 else "failed",
            "label": label,
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:],  # Last 2000 chars
            "stderr": result.stderr[-1000:]
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "label": label}
    except Exception as e:
        return {"status": "error", "label": label, "error": str(e)}


def extract_mesh_statistics(run_dir: Path) -> dict:
    """Extract mesh statistics from checkMesh output."""
    log_file = run_dir / "openfoam" / "logs" / "log.checkMesh"

    if not log_file.exists():
        # Try alternative location
        log_file = run_dir / "openfoam" / "log.checkMesh"

    if not log_file.exists():
        return {"error": f"checkMesh log not found: {log_file}"}

    import re
    with open(log_file) as f:
        content = f.read()

    stats = {}

    # Extract cell count
    match = re.search(r'cells:\s*(\d+)', content)
    if match:
        stats["cells"] = int(match.group(1))

    # Extract non-orthogonality
    match = re.search(r'Max non-orthogonality:\s*([\d.]+)', content)
    if match:
        stats["max_non_ortho"] = float(match.group(1))

    match = re.search(r'Average non-orthogonality:\s*([\d.]+)', content)
    if match:
        stats["avg_non_ortho"] = float(match.group(1))

    # Extract skewness
    match = re.search(r'Max skewness:\s*([\d.]+)', content)
    if match:
        stats["max_skewness"] = float(match.group(1))

    # Check if mesh is OK
    stats["mesh_ok"] = "Mesh OK" in content

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Run systematic mesh convergence study for GCI analysis"
    )
    parser.add_argument(
        "--patient", default=DEFAULT_PATIENT,
        help=f"Patient case directory name (default: {DEFAULT_PATIENT})"
    )
    parser.add_argument(
        "--base-config", type=Path,
        help="Path to base configuration JSON (default: cases_input/PATIENT/config.json)"
    )
    parser.add_argument(
        "--output-dir", type=Path,
        help="Output directory for mesh study (default: output/PATIENT/mesh_span_study)"
    )
    parser.add_argument(
        "--cycles", type=int, default=3,
        help="Number of cardiac cycles to simulate (default: 3)"
    )
    parser.add_argument(
        "--spans", nargs="+", type=int, default=[10, 15, 20],
        help="cells_across_span values to test (default: 10 15 20)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Create configs but don't run simulations"
    )
    parser.add_argument(
        "--mesh-only", action="store_true",
        help="Only run meshing step (faster for mesh convergence)"
    )

    args = parser.parse_args()

    # Set default paths
    base_dir = Path(__file__).parent.parent

    if args.base_config is None:
        args.base_config = base_dir / "cases_input" / args.patient / "config.json"

    if args.output_dir is None:
        args.output_dir = base_dir / "output" / args.patient / "mesh_span_study"

    # Verify base config exists
    if not args.base_config.exists():
        print(f"ERROR: Base config not found: {args.base_config}")
        sys.exit(1)

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("="*70)
    print("Systematic Mesh Convergence Study (Span-Based)")
    print("="*70)
    print(f"Patient: {args.patient}")
    print(f"Base config: {args.base_config}")
    print(f"Output: {args.output_dir}")
    print(f"Cycles: {args.cycles}")
    print(f"Span values: {args.spans}")
    print()

    # Create configurations for each span value
    configs = {}
    for span in sorted(args.spans):
        label = f"span{span}"
        config_path = create_mesh_config(
            args.base_config,
            args.output_dir,
            span,
            label
        )
        configs[span] = {
            "config_path": config_path,
            "label": label,
            "cells_across_span": span
        }

    print()
    print("="*70)
    print("Mesh Level Summary (Span-Based Refinement)")
    print("="*70)
    print()
    print("cells_across_span guarantees minimum cells across vessel diameter")
    print("This is more appropriate for cardiovascular geometries than uniform refinement")
    print()
    print("Span | Label    | Expected Cells | h ratio (vs prev)")
    print("-"*60)

    # Expected cells based on span (empirical from previous runs)
    expected = {10: "~100k", 15: "~300k", 20: "~700k", 25: "~1.2M", 30: "~2M"}
    prev_span = None
    for span in sorted(configs.keys()):
        info = configs[span]
        exp = expected.get(span, "N/A")
        if prev_span:
            # h ratio = span_prev / span_current (cell size ratio)
            h_ratio = f"{prev_span/span:.2f}"
        else:
            h_ratio = "base"
        print(f"  {span:2d}  | {info['label']:8s} | {exp:14s} | {h_ratio}")
        prev_span = span

    print()
    print("For GCI computation, the effective refinement ratio is:")
    print("  r = h_coarse / h_fine = span_fine / span_coarse")
    print(f"  For spans {args.spans}: r ≈ {args.spans[-1]/args.spans[0]:.2f} overall")
    print()

    if args.dry_run:
        print("DRY RUN - Configurations created but simulations not executed.")
        print(f"Configs saved to: {args.output_dir}")
        print()
        print("To run the study:")
        print(f"  python scripts/run_systematic_mesh_study.py --patient {args.patient} --spans {' '.join(map(str, args.spans))} --cycles {args.cycles}")
        return

    # Run simulations
    results = []
    for span in sorted(configs.keys()):
        info = configs[span]
        result = run_simulation(
            info["config_path"],
            args.output_dir,
            info["label"],
            args.cycles,
            args.dry_run
        )
        result["cells_across_span"] = span
        results.append(result)

        # Extract mesh statistics if successful
        if result.get("status") == "success":
            run_dir = args.output_dir / info["label"]
            mesh_stats = extract_mesh_statistics(run_dir)
            result["mesh_stats"] = mesh_stats

            if "cells" in mesh_stats:
                print(f"\n  Mesh statistics for {info['label']}:")
                print(f"    Cells: {mesh_stats['cells']:,}")
                if "max_non_ortho" in mesh_stats:
                    print(f"    Max non-ortho: {mesh_stats['max_non_ortho']:.1f}°")
                if "max_skewness" in mesh_stats:
                    print(f"    Max skewness: {mesh_stats['max_skewness']:.2f}")

    # Save results summary
    results_file = args.output_dir / "mesh_study_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {results_file}")

    # Print summary
    print()
    print("="*70)
    print("Study Complete")
    print("="*70)

    for result in results:
        status = result.get("status", "unknown")
        label = result.get("label", "unknown")
        span = result.get("cells_across_span", "?")
        cells = result.get("mesh_stats", {}).get("cells", "N/A")
        if isinstance(cells, int):
            print(f"  {label} (span={span}): {status} ({cells:,} cells)")
        else:
            print(f"  {label} (span={span}): {status}")

    print()
    print("Next steps:")
    print(f"  1. Run GCI analysis: python scripts/compute_gci_systematic.py --study-dir {args.output_dir}")
    print("  2. Generate publication figures")


if __name__ == "__main__":
    main()
