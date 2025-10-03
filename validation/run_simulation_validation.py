#!/usr/bin/env python3
"""
Level 3 CFD Validation Runner - Full Simulation Validation

Extends Level 2 (mesh quality) with actual CFD simulations to validate:
- Solver convergence
- Physical results (velocity, pressure, WSS)
- Flow conservation
- Boundary condition correctness

Usage:
    # Run short simulation validation on COARSE mesh
    python validation/run_simulation_validation.py patient1 --profiles sim_laminar_coarse --time 0.1

    # Run full cardiac cycle validation on MEDIUM mesh
    python validation/run_simulation_validation.py patient1 --profiles sim_laminar_medium --time 1.0

    # Validate multiple profiles
    python validation/run_simulation_validation.py patient1 --profiles sim_laminar_coarse sim_laminar_medium
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
import json
import subprocess
import time

# Add paths for imports
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir / "src"))
sys.path.insert(0, str(script_dir))
sys.path.insert(0, str(script_dir / "validation"))

from analyzers.physical_results_analyzer import (
    PhysicalResultsAnalyzer, format_validation_report
)
from analyzers.mesh_quality_analyzer import MeshQualityAnalyzer, analyze_mesh_quality
from run_validation import ValidationRunner


class SimulationValidationRunner:
    """Runs Level 3 simulation validation."""

    def __init__(self, patient_name: str, output_dir: Path = None):
        """
        Initialize simulation validation runner.

        Args:
            patient_name: Name of patient case
            output_dir: Directory for validation outputs
        """
        self.patient_name = patient_name
        if output_dir is None:
            output_dir = Path("validation") / "output" / patient_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Use existing Level 2 runner for mesh generation
        self.mesh_runner = ValidationRunner(patient_name, output_dir)
        self.results = {}

    def run_simulation(self, case_dir: Path, end_time: float = 0.1,
                      write_interval: float = 0.01) -> bool:
        """
        Run OpenFOAM simulation.

        Args:
            case_dir: Path to case directory
            end_time: Simulation end time (default: 0.1s for quick test)
            write_interval: Write interval for results

        Returns:
            True if simulation completed successfully
        """
        print(f"\n  🚀 Running simulation (endTime={end_time}s)...")

        try:
            # Update controlDict for short simulation
            self._update_controlDict(case_dir, end_time, write_interval)

            # Run simulation
            log_file = case_dir / "log.foamRun"

            start_time = time.time()

            with open(log_file, 'w') as log:
                result = subprocess.run(
                    ["foamRun", "-case", str(case_dir)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=600  # 10 minute timeout
                )

            elapsed_time = time.time() - start_time

            if result.returncode == 0:
                print(f"  ✅ Simulation complete ({elapsed_time:.1f}s)")
                return True
            else:
                print(f"  ❌ Simulation failed (return code: {result.returncode})")
                return False

        except subprocess.TimeoutExpired:
            print(f"  ❌ Simulation timeout (>10 minutes)")
            return False
        except Exception as e:
            print(f"  ❌ Simulation error: {e}")
            return False

    def _update_controlDict(self, case_dir: Path, end_time: float,
                           write_interval: float):
        """Update controlDict for validation simulation."""
        control_dict = case_dir / "system" / "controlDict"

        if not control_dict.exists():
            # Create minimal controlDict
            content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      controlDict;
}}
// ************************************************************************* //

application     foamRun;
solver          incompressibleFluid;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          0.001;
writeControl    runTime;
writeInterval   {write_interval};
purgeWrite      2;
writeFormat     binary;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

// ************************************************************************* //
"""
            control_dict.write_text(content)
        else:
            # Update existing controlDict
            content = control_dict.read_text()
            content = content.replace("endTime         1;", f"endTime         {end_time};")
            content = content.replace("writeInterval   0.01;", f"writeInterval   {write_interval};")
            control_dict.write_text(content)

    def _setup_solver_files(self, case_dir: Path, sim_profile: str):
        """Set up solver configuration files using workflow tasks."""
        from config.builder import ConfigBuilder
        from workflow.tasks.setup_tasks import (
            GeneratePhysicalPropertiesTask,
            GenerateNumericalSchemesTask,
            GenerateSolverSettingsTask,
            GenerateControlDictTask
        )

        # Build config
        builder = ConfigBuilder()
        config = builder.build(case_name=self.patient_name, sim_profile_name=sim_profile)

        # Run setup tasks (skip boundary condition setup for now - focus on getting simulation running)
        try:
            # Create context for tasks - add cardiac_cycle for controlDict generation
            context = {
                "case_directory": str(case_dir),
                "cardiac_cycle": 1.0  # Default 1 second for validation
            }

            # Generate physical properties
            props_task = GeneratePhysicalPropertiesTask(config)
            props_task.execute(context)

            # Generate numerical schemes
            num_task = GenerateNumericalSchemesTask(config)
            num_task.execute(context)

            # Generate solver settings
            solver_task = GenerateSolverSettingsTask(config)
            solver_task.execute(context)

            # Generate controlDict (will be overwritten by _update_controlDict later)
            ctrl_task = GenerateControlDictTask(config)
            ctrl_task.execute(context)

            # Create minimal boundary condition files for validation
            self._create_minimal_bc_files(case_dir)

            print(f"  ✅ Solver files configured")
        except Exception as e:
            print(f"  ⚠️  Warning: Solver setup had issues: {e}")
            import traceback
            traceback.print_exc()

    def _create_minimal_bc_files(self, case_dir: Path):
        """Create minimal boundary condition files for validation."""
        zero_dir = case_dir / "0"
        zero_dir.mkdir(exist_ok=True)

        # Minimal U file
        u_file = zero_dir / "U"
        u_content = r"""/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  12
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       volVectorField;
    object      U;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);

boundaryField
{
    inlet
    {
        type            fixedValue;
        value           uniform (0 0 0.1);  // Z-direction (upward flow)
    }
    "outlet.*"
    {
        type            zeroGradient;
    }
    wall_aorta
    {
        type            noSlip;
    }
}

// ************************************************************************* //
"""
        u_file.write_text(u_content)

        # Minimal p file
        p_file = zero_dir / "p"
        p_content = r"""/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  12
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       volScalarField;
    object      p;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;

boundaryField
{
    inlet
    {
        type            zeroGradient;
    }
    "outlet.*"
    {
        type            fixedValue;
        value           uniform 0;
    }
    wall_aorta
    {
        type            zeroGradient;
    }
}

// ************************************************************************* //
"""
        p_file.write_text(p_content)

    def validate_profile(self, sim_profile: str, end_time: float = 0.1) -> dict:
        """
        Run complete Level 3 validation for a profile.

        Args:
            sim_profile: Profile name (e.g., "sim_laminar_coarse")
            end_time: Simulation end time

        Returns:
            Dictionary with validation results
        """
        print(f"\n{'#'*70}")
        print(f"# LEVEL 3 VALIDATION: {sim_profile}")
        print(f"# End Time: {end_time}s")
        print(f"{'#'*70}")

        case_dir = self.output_dir / sim_profile

        # Step 1: Check if case is ready (mesh + solver files), otherwise set up complete case
        needs_setup = (
            not (case_dir / "constant" / "polyMesh").exists() or
            not (case_dir / "system" / "fvSchemes").exists() or
            not (case_dir / "system" / "fvSolution").exists()
        )

        if needs_setup:
            print(f"\n  📐 Case not complete, running full preprocessing...")

            # Build config for meshing and solver setup
            from config.builder import ConfigBuilder
            builder = ConfigBuilder()
            config = builder.build(case_name=self.patient_name, sim_profile_name=sim_profile)

            case_dir = self.mesh_runner.run_preprocessing(sim_profile)
            mesh_success = self.mesh_runner.run_meshing(case_dir, config)

            if not mesh_success:
                return {
                    "profile": sim_profile,
                    "level": 3,
                    "mesh_generated": False,
                    "simulation_run": False,
                    "passed": False,
                    "error": "Mesh generation failed"
                }

            # Also need to generate solver files - use run_patient.py approach
            print(f"\n  ⚙️  Setting up solver files...")
            self._setup_solver_files(case_dir, sim_profile)

        # Step 2: Validate mesh quality
        print(f"\n  🔍 Checking mesh quality...")
        mesh_metrics, mesh_passed, mesh_issues = analyze_mesh_quality(case_dir, solver_type="laminar")

        if not mesh_passed:
            print(f"  ⚠️  Mesh quality issues detected:")
            for issue in mesh_issues:
                print(f"      - {issue}")
            print(f"  ⏭️  Continuing with simulation anyway for validation...")

        # Step 3: Run simulation
        sim_success = self.run_simulation(case_dir, end_time=end_time)

        if not sim_success:
            return {
                "profile": sim_profile,
                "level": 3,
                "mesh_generated": True,
                "mesh_passed": mesh_passed,
                "mesh_cells": mesh_metrics.num_cells,
                "simulation_run": False,
                "passed": False,
                "error": "Simulation failed to complete"
            }

        # Step 4: Analyze simulation results
        print(f"\n  📊 Analyzing simulation results...")
        phys_analyzer = PhysicalResultsAnalyzer(case_dir)
        results = phys_analyzer.validate_simulation()

        # Print validation report
        report = format_validation_report(results)
        print(report)

        # Save report to file
        report_file = case_dir / "validation_report.txt"
        report_file.write_text(report)

        # Check validation
        passed, issues = results.passes_validation()

        return {
            "profile": sim_profile,
            "level": 3,
            "mesh_generated": True,
            "mesh_passed": mesh_passed,
            "mesh_cells": mesh_metrics.num_cells,
            "mesh_skewness": mesh_metrics.max_skewness,
            "simulation_run": True,
            "simulation_time": results.convergence.final_time,
            "iterations": results.convergence.total_iterations,
            "converged": results.convergence.converged,
            "max_courant": results.convergence.max_courant_number,
            "pressure_residual": results.convergence.final_p_residual,
            "max_velocity": results.flow.max_velocity,
            "flow_conservation_error": results.flow.flow_conservation_error,
            "passed": passed and mesh_passed,
            "issues": issues + mesh_issues if not passed else []
        }

    def generate_comparison_report(self) -> str:
        """Generate comparison report across all validated profiles."""
        report = f"""
{'='*70}
LEVEL 3 SIMULATION VALIDATION COMPARISON REPORT
Patient: {self.patient_name}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*70}

SUMMARY TABLE:
{'-'*70}
{'Profile':<25} {'Cells':<12} {'Sim Time':<12} {'Status':<10}
{'-'*70}
"""

        for profile, result in self.results.items():
            if result['simulation_run']:
                cells = f"{result['mesh_cells']:,}"
                sim_time = f"{result['simulation_time']:.3f}s"
                status = "✅ PASS" if result['passed'] else "❌ FAIL"
                report += f"{profile:<25} {cells:<12} {sim_time:<12} {status:<10}\n"
            else:
                status = "❌ SKIP (mesh fail)"
                report += f"{profile:<25} {'N/A':<12} {'N/A':<12} {status:<10}\n"

        report += f"{'-'*70}\n\n"

        # Detailed metrics
        report += "DETAILED METRICS:\n"
        report += f"{'-'*70}\n\n"

        for profile, result in self.results.items():
            if not result['simulation_run']:
                continue

            report += f"{profile}:\n"
            report += f"  Mesh Cells:              {result['mesh_cells']:,}\n"
            report += f"  Mesh Skewness:           {result['mesh_skewness']:.2f}\n"
            report += f"  Simulation Time:         {result['simulation_time']:.3f}s\n"
            report += f"  Iterations:              {result['iterations']}\n"
            report += f"  Converged:               {'Yes' if result['converged'] else 'No'}\n"
            report += f"  Max Courant:             {result['max_courant']:.3f}\n"
            report += f"  Pressure Residual:       {result['pressure_residual']:.2e}\n"
            report += f"  Max Velocity:            {result['max_velocity']:.3f} m/s\n"
            report += f"  Flow Conservation:       {result['flow_conservation_error']*100:.2f}%\n"

            if result['issues']:
                report += "  Issues:\n"
                for issue in result['issues']:
                    report += f"    - {issue}\n"
            report += "\n"

        report += f"{'='*70}\n"

        # Recommendations
        passed_count = sum(1 for r in self.results.values() if r.get('passed', False))
        total_count = len(self.results)

        report += "\nRECOMMENDATIONS:\n"
        report += f"{'-'*70}\n"

        if passed_count == total_count:
            report += f"✅ All {total_count} configuration(s) passed simulation validation\n"
            report += "   Ready for production simulations\n"
        elif passed_count > 0:
            report += f"⚠️  {passed_count}/{total_count} configuration(s) passed\n"
            report += "   Review failed configurations before production use\n"
        else:
            report += f"❌ No configurations passed validation\n"
            report += "   Review mesh settings and boundary conditions\n"

        report += f"\n{'='*70}\n"

        return report

    def run_validation(self, profiles: list, end_time: float = 0.1):
        """
        Run Level 3 validation for multiple profiles.

        Args:
            profiles: List of profile names
            end_time: Simulation end time for all profiles
        """
        print(f"\n{'#'*70}")
        print(f"# LEVEL 3 SIMULATION VALIDATION: {self.patient_name}")
        print(f"# Profiles: {', '.join(profiles)}")
        print(f"# Simulation Time: {end_time}s")
        print(f"# Output: {self.output_dir}")
        print(f"{'#'*70}")

        for profile in profiles:
            result = self.validate_profile(profile, end_time)
            self.results[profile] = result

        # Generate comparison report
        report = self.generate_comparison_report()
        print(report)

        # Save reports
        report_file = self.output_dir / "simulation_validation_report.txt"
        report_file.write_text(report)
        print(f"\n📄 Report saved to: {report_file}")

        results_file = self.output_dir / "simulation_validation_results.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"📊 Results saved to: {results_file}")

        # Print summary
        failed = [p for p, r in self.results.items() if not r.get('passed', False)]
        if failed:
            print(f"\n⚠️  {len(failed)} configuration(s) have issues")
            return False
        else:
            print(f"\n✅ All configurations passed simulation validation!")
            return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Level 3 CFD Validation - Full Simulation Validation"
    )
    parser.add_argument(
        "patient",
        help="Patient case name (e.g., patient1)"
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["sim_laminar_coarse"],
        help="Simulation profiles to validate (default: sim_laminar_coarse)"
    )
    parser.add_argument(
        "--time",
        type=float,
        default=0.1,
        help="Simulation end time in seconds (default: 0.1 for quick test)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for validation results"
    )

    args = parser.parse_args()

    # Run validation
    runner = SimulationValidationRunner(args.patient, args.output)
    success = runner.run_validation(args.profiles, end_time=args.time)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
