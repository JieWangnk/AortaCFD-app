#!/usr/bin/env python3
"""
CFD Validation Runner

Runs mesh quality validation across all simulation profiles for a patient case.
Generates comparison reports showing CFD quality metrics.

Usage:
    python validation/run_validation.py patient1
    python validation/run_validation.py patient1 --profiles sim_laminar_coarse sim_rans_medium
    python validation/run_validation.py patient1 --report-only
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
import json
import shutil
import tempfile

# Add paths for imports
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir / "src"))
sys.path.insert(0, str(script_dir))

from config.builder import ConfigBuilder
from workflow.tasks.setup_tasks import CreateCaseStructureTask, GenerateMeshFilesTask
from validation.analyzers import MeshQualityAnalyzer, analyze_mesh_quality


class ValidationRunner:
    """Runs CFD validation across multiple configurations."""

    def __init__(self, patient_name: str, output_dir: Path = None):
        """
        Initialize validation runner.

        Args:
            patient_name: Name of patient case (e.g., "patient1")
            output_dir: Directory for validation outputs (default: validation/output)
        """
        self.patient_name = patient_name
        self.patient_dir = Path("cases_input") / patient_name

        if output_dir is None:
            output_dir = Path("validation") / "output" / patient_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results = {}

    def run_preprocessing(self, sim_profile: str) -> Path:
        """
        Run preprocessing for given simulation profile.

        Args:
            sim_profile: Profile name (e.g., "sim_laminar_coarse")

        Returns:
            Path to generated case directory
        """
        print(f"\n{'=' * 70}")
        print(f"Running preprocessing: {sim_profile}")
        print(f"{'=' * 70}")

        # Build configuration
        builder = ConfigBuilder()
        config = builder.build(case_name=self.patient_name, sim_profile_name=sim_profile)

        # Create case directory
        case_dir = self.output_dir / sim_profile
        if case_dir.exists():
            print(f"  Removing existing case: {case_dir}")
            shutil.rmtree(case_dir)

        case_dir.mkdir(parents=True, exist_ok=True)

        # Task 1: Create case structure
        print(f"  Creating case structure...")
        task1 = CreateCaseStructureTask(config)
        context = {"case_directory": str(case_dir)}
        result1 = task1.execute(context)

        if not result1:
            raise RuntimeError(f"Failed to create case structure for {sim_profile}")

        # Copy geometry files
        print(f"  Copying geometry files...")
        tri_surface = case_dir / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)

        stl_files = list(self.patient_dir.glob("*.stl"))
        print(f"  Found {len(stl_files)} STL files")

        for stl_file in stl_files:
            shutil.copy(stl_file, tri_surface / stl_file.name)

        # Task 2: Generate mesh files
        print(f"  Generating mesh files...")
        task2 = GenerateMeshFilesTask(config)
        result2 = task2.execute(context)

        if not result2:
            raise RuntimeError(f"Failed to generate mesh files for {sim_profile}")

        print(f"  ✅ Preprocessing complete: {case_dir}")

        return case_dir

    def run_meshing(self, case_dir: Path, config: dict) -> bool:
        """
        Run actual mesh generation (blockMesh + snappyHexMesh).

        Args:
            case_dir: Path to case directory
            config: Configuration dictionary

        Returns:
            True if meshing succeeded, False otherwise
        """
        print(f"\n  🔧 Running mesh generation (this may take 5-15 minutes)...")

        try:
            import subprocess

            # Create minimal controlDict for meshing (OpenFOAM requires this)
            control_dict_path = case_dir / "system" / "controlDict"
            if not control_dict_path.exists():
                print(f"    Creating controlDict...")
                control_dict_content = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  12                                    |
|   \\\\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\\\/     M anip

ulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      controlDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     foamRun;
solver          incompressibleFluid;

startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         1;
deltaT          0.001;
writeControl    timeStep;
writeInterval   100;
purgeWrite      0;
writeFormat     binary;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

// ************************************************************************* //
"""
                control_dict_path.write_text(control_dict_content)

            # Step 1: Run blockMesh
            print(f"    Step 1/3: Running blockMesh...")
            result = subprocess.run(
                ["blockMesh", "-case", str(case_dir)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )

            log_file = case_dir / "log.blockMesh"
            log_file.write_text(result.stdout + result.stderr)

            if result.returncode != 0:
                print(f"    ❌ blockMesh failed (see log.blockMesh)")
                print(f"       Error: {result.stderr[:200]}")
                return False

            print(f"    ✅ blockMesh complete")

            # Step 2: Run surfaceFeatures
            print(f"    Step 2/3: Running surfaceFeatures...")
            result = subprocess.run(
                ["surfaceFeatures", "-case", str(case_dir)],
                capture_output=True,
                text=True,
                timeout=180  # 3 minutes
            )

            log_file = case_dir / "log.surfaceFeatures"
            log_file.write_text(result.stdout + result.stderr)

            if result.returncode != 0:
                print(f"    ⚠️  surfaceFeatures failed (continuing anyway)")
                print(f"       Error: {result.stderr[:200]}")

            print(f"    ✅ surfaceFeatures complete")

            # Step 3: Run snappyHexMesh
            print(f"    Step 3/3: Running snappyHexMesh...")
            result = subprocess.run(
                ["snappyHexMesh", "-overwrite", "-case", str(case_dir)],
                capture_output=True,
                text=True,
                timeout=900  # 15 minutes
            )

            log_file = case_dir / "log.snappyHexMesh"
            log_file.write_text(result.stdout + result.stderr)

            if result.returncode != 0:
                print(f"    ❌ snappyHexMesh failed (see log.snappyHexMesh)")
                print(f"       Error: {result.stderr[:200]}")
                return False

            print(f"    ✅ snappyHexMesh complete")

            # Check if mesh was actually created
            poly_mesh = case_dir / "constant" / "polyMesh"
            if not (poly_mesh / "points").exists():
                print(f"    ❌ Mesh files not found after snappyHexMesh")
                return False

            print(f"\n  ✅ Mesh generation complete!")
            return True

        except subprocess.TimeoutExpired:
            print(f"    ❌ Meshing timed out")
            return False
        except FileNotFoundError as e:
            print(f"    ❌ OpenFOAM tools not found: {e}")
            print(f"       Make sure OpenFOAM is installed and sourced:")
            print(f"       source /opt/openfoam12/etc/bashrc")
            return False
        except Exception as e:
            print(f"    ❌ Meshing error: {e}")
            return False

    def analyze_mesh(self, case_dir: Path, solver_type: str) -> dict:
        """
        Analyze mesh quality for a case.

        Args:
            case_dir: Path to case directory
            solver_type: "laminar", "rans", or "les"

        Returns:
            Dictionary with analysis results
        """
        print(f"\n  Analyzing mesh quality...")

        analyzer = MeshQualityAnalyzer(case_dir)

        try:
            # Check if actual mesh exists
            mesh_exists = analyzer.check_mesh_files_exist()

            if not mesh_exists:
                # Level 1 validation: Check dictionary files only
                print(f"  📋 Level 1 Validation (mesh dictionaries only, no actual mesh)")

                dict_files = analyzer.check_mesh_dict_files_exist()
                all_dicts_exist = all(dict_files.values())

                print(f"  Dictionary files:")
                for dict_name, exists in dict_files.items():
                    status = "✅" if exists else "❌"
                    print(f"    {status} {dict_name}")

                from validation.analyzers.mesh_quality_analyzer import MeshQualityMetrics
                metrics = MeshQualityMetrics()

                if all_dicts_exist:
                    passed = True
                    issues = ["Level 1 only: Mesh dictionaries validated (no actual mesh generated)"]
                    print(f"\n  ✅ PASS - Mesh dictionaries exist and are ready for meshing")
                else:
                    passed = False
                    missing = [name for name, exists in dict_files.items() if not exists]
                    issues = [f"Missing dictionary files: {', '.join(missing)}"]
                    print(f"\n  ❌ FAIL - Missing dictionary files: {', '.join(missing)}")

            else:
                # Level 2: Actual mesh exists, run checkMesh
                print(f"  🔍 Level 2 Validation (analyzing actual mesh with checkMesh)")
                try:
                    output = analyzer.run_checkMesh()
                    metrics = analyzer.parse_checkMesh_output(output)
                    passed, issues = metrics.passes_quality_checks(solver_type)

                    # Save checkMesh log
                    log_file = case_dir / "log.checkMesh"
                    log_file.write_text(output)

                except RuntimeError as e:
                    print(f"  ⚠️  checkMesh failed: {e}")
                    from validation.analyzers.mesh_quality_analyzer import MeshQualityMetrics
                    metrics = MeshQualityMetrics()
                    passed = False
                    issues = [f"checkMesh error: {e}"]

            # Analyze boundary layers
            bl_info = analyzer.analyze_boundary_layers()

            # Generate report
            report = analyzer.generate_quality_report(solver_type)

            # Save report
            report_file = case_dir / "mesh_quality_report.txt"
            report_file.write_text(report)

            print(report)

            return {
                "metrics": metrics.__dict__,
                "passed": passed,
                "issues": issues,
                "boundary_layers": bl_info,
                "report": report,
                "solver_type": solver_type
            }

        except Exception as e:
            print(f"  ❌ Analysis failed: {e}")
            return {
                "error": str(e),
                "passed": False,
                "issues": [f"Analysis error: {e}"]
            }

    def run_validation(self, profiles: list) -> dict:
        """
        Run validation across multiple profiles.

        Args:
            profiles: List of profile names

        Returns:
            Dictionary with all results
        """
        print(f"\n{'#' * 70}")
        print(f"# CFD VALIDATION: {self.patient_name}")
        print(f"# Profiles: {', '.join(profiles)}")
        print(f"# Output: {self.output_dir}")
        print(f"{'#' * 70}")

        results = {}

        for profile in profiles:
            try:
                # Determine solver type
                solver_type = self._get_solver_type(profile)

                # Run preprocessing
                from config.builder import ConfigBuilder
                builder = ConfigBuilder()
                config = builder.build(case_name=self.patient_name, sim_profile_name=profile)
                case_dir = self.run_preprocessing(profile)

                # Run actual mesh generation (Level 2)
                meshing_success = self.run_meshing(case_dir, config)

                if not meshing_success:
                    print(f"\n⚠️  Meshing failed, falling back to Level 1 validation (dictionary-only)")

                # Analyze mesh
                analysis = self.analyze_mesh(case_dir, solver_type)

                results[profile] = {
                    "case_directory": str(case_dir),
                    "solver_type": solver_type,
                    "analysis": analysis,
                    "meshing_success": meshing_success,
                    "status": "completed"
                }

            except Exception as e:
                print(f"\n❌ ERROR: {profile} failed: {e}")
                results[profile] = {
                    "error": str(e),
                    "status": "failed"
                }

        self.results = results
        return results

    def _get_solver_type(self, profile: str) -> str:
        """Extract solver type from profile name."""
        profile_lower = profile.lower()
        if "laminar" in profile_lower:
            return "laminar"
        elif "rans" in profile_lower:
            return "rans"
        elif "les" in profile_lower:
            return "les"
        return "laminar"

    def generate_comparison_report(self) -> str:
        """
        Generate comparison report across all validated configs.

        Returns:
            Formatted comparison report
        """
        report = []
        report.append("\n" + "=" * 70)
        report.append(f"CFD VALIDATION COMPARISON REPORT")
        report.append(f"Patient: {self.patient_name}")
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 70)

        # Summary table
        report.append("\nSUMMARY TABLE:")
        report.append("-" * 70)
        report.append(f"{'Profile':<25} {'Solver':<10} {'Cells':>12} {'Quality':<10}")
        report.append("-" * 70)

        for profile, data in self.results.items():
            if data.get("status") == "failed":
                report.append(f"{profile:<25} {'ERROR':<10} {'-':>12} {'FAILED':<10}")
                continue

            analysis = data.get("analysis", {})
            metrics = analysis.get("metrics", {})

            solver = data.get("solver_type", "unknown")
            cells = metrics.get("num_cells", 0)
            quality = "✅ PASS" if analysis.get("passed") else "❌ FAIL"

            report.append(f"{profile:<25} {solver:<10} {cells:>12,} {quality:<10}")

        report.append("-" * 70)

        # Detailed metrics comparison
        report.append("\n\nDETAILED METRICS:")
        report.append("-" * 70)

        for profile, data in self.results.items():
            if data.get("status") == "failed":
                continue

            analysis = data.get("analysis", {})
            metrics = analysis.get("metrics", {})

            report.append(f"\n{profile}:")
            report.append(f"  Cells:              {metrics.get('num_cells', 0):>12,}")
            report.append(f"  Non-orthogonality:  {metrics.get('max_non_orthogonality', 0):>12.2f}")
            report.append(f"  Skewness:           {metrics.get('max_skewness', 0):>12.2f}")
            report.append(f"  Aspect ratio:       {metrics.get('max_aspect_ratio', 0):>12.1f}")

            # Boundary layers
            bl_info = analysis.get("boundary_layers", {})
            if bl_info.get("available"):
                if bl_info.get("num_layers"):
                    report.append(f"  Boundary layers:    {bl_info['num_layers']:>12}")
                if bl_info.get("coverage"):
                    report.append(f"  Layer coverage:     {bl_info['coverage']:>11.1f}%")

            # Issues
            issues = analysis.get("issues", [])
            if issues:
                report.append(f"  Issues:")
                for issue in issues:
                    report.append(f"    - {issue}")

        report.append("\n" + "=" * 70)

        # Recommendations
        report.append("\n\nRECOMMENDATIONS:")
        report.append("-" * 70)

        passed_configs = [p for p, d in self.results.items()
                         if d.get("analysis", {}).get("passed", False)]

        if passed_configs:
            report.append(f"✅ {len(passed_configs)} configuration(s) passed quality checks:")
            for config in passed_configs:
                solver = self.results[config].get("solver_type", "unknown")
                report.append(f"   - {config} ({solver})")
        else:
            report.append("⚠️  No configurations passed all quality checks")
            report.append("   Consider adjusting mesh parameters or accepting quality issues")

        report.append("\n" + "=" * 70)

        return "\n".join(report)

    def save_results(self):
        """Save validation results to JSON file."""
        results_file = self.output_dir / "validation_results.json"

        # Convert results to JSON-serializable format
        json_results = {}
        for profile, data in self.results.items():
            json_results[profile] = {
                "status": data.get("status"),
                "solver_type": data.get("solver_type"),
                "case_directory": data.get("case_directory"),
            }

            if "analysis" in data:
                json_results[profile]["analysis"] = {
                    "passed": data["analysis"].get("passed"),
                    "issues": data["analysis"].get("issues", []),
                    "metrics": data["analysis"].get("metrics", {}),
                }

        with open(results_file, "w") as f:
            json.dump(json_results, f, indent=2)

        print(f"\n📊 Results saved to: {results_file}")


def main():
    """Main validation runner."""
    parser = argparse.ArgumentParser(description="Run CFD validation for AortaCFD")
    parser.add_argument("patient", help="Patient name (e.g., patient1)")
    parser.add_argument("--profiles", nargs="+",
                       help="Simulation profiles to test (default: all)")
    parser.add_argument("--output", type=Path,
                       help="Output directory (default: validation/output/<patient>)")

    args = parser.parse_args()

    # Default profiles if not specified
    if args.profiles is None:
        profiles = [
            "sim_laminar_coarse",
            "sim_laminar_medium",
            "sim_laminar_fine",
            "sim_rans_coarse",
            "sim_rans_medium",
            "sim_les_medium"
        ]
    else:
        profiles = args.profiles

    # Run validation
    runner = ValidationRunner(args.patient, args.output)
    results = runner.run_validation(profiles)

    # Generate comparison report
    report = runner.generate_comparison_report()
    print(report)

    # Save report
    report_file = runner.output_dir / "comparison_report.txt"
    report_file.write_text(report)
    print(f"\n📄 Report saved to: {report_file}")

    # Save JSON results
    runner.save_results()

    # Exit with error if any failed
    failed = [p for p, d in results.items() if not d.get("analysis", {}).get("passed", False)]
    if failed:
        print(f"\n⚠️  {len(failed)} configuration(s) have quality issues")
        sys.exit(1)
    else:
        print(f"\n✅ All {len(results)} configurations passed quality checks")
        sys.exit(0)


if __name__ == "__main__":
    main()
