"""
CLI interface for patient runner - handles command-line argument parsing
"""

import sys
import argparse

from aortacfd_lib import __version__ as _aortacfd_version

# Delay PatientCaseRunner import until after Logger is configured


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="run_patient.py",
        description="AortaCFD — automated patient-specific aortic CFD pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  python run_patient.py BPM120
  python run_patient.py BPM120 --run-name baseline
  python run_patient.py BPM120 --config cases_input/BPM120/config_mesh_fine.json
  python run_patient.py BPM120 --steps case,mesh,boundary
  python run_patient.py BPM120 --update output/BPM120/run_xxx --steps solver
  python run_patient.py --postprocess output/BPM120/run_xxx
  python run_patient.py --list

steps:
  case                generate OpenFOAM dictionaries
  mesh                create computational mesh (snappyHexMesh)
  boundary            set up boundary conditions and flow data
  regenerate-numerics regenerate fvSchemes/fvSolution after meshing
  solver              run CFD solver
  reconstruct         reconstruct parallel case
  postprocess         compute hemodynamics and export QoIs
  paraview            ParaView visualization
  all                 complete workflow (default)
        """,
    )

    # Positional argument
    parser.add_argument("patient_id", nargs="?", help="case ID matching a folder under cases_input/")

    # Information
    info_group = parser.add_argument_group("information")
    info_group.add_argument("--version", "-V", action="version", version=f"AortaCFD {_aortacfd_version}")
    info_group.add_argument("--list", "-l", action="store_true", help="list available cases in cases_input/")
    info_group.add_argument("--list-steps", action="store_true", help="show workflow steps and their dependencies")
    info_group.add_argument(
        "--doctor",
        action="store_true",
        help="run environment diagnostics (Python, deps, STLs, OpenFOAM, disk space)",
    )

    # Workflow control
    workflow_group = parser.add_argument_group("workflow control")
    workflow_group.add_argument(
        "--steps", "-s", metavar="STEPS", help="comma-separated steps to run (e.g. case,mesh,boundary)"
    )
    workflow_group.add_argument(
        "--step",
        action="append",
        dest="step_list",
        choices=[
            "case",
            "mesh",
            "boundary",
            "regenerate-numerics",
            "solver",
            "reconstruct",
            "postprocess",
            "paraview",
            "all",
        ],
        help="run a single step (repeatable)",
    )

    # Configuration
    config_group = parser.add_argument_group("configuration")
    config_group.add_argument(
        "--config", "-c", metavar="PATH", help="config JSON (default: cases_input/<case_id>/config.json)"
    )
    # Get profile choices dynamically - import here to avoid early Logger initialization
    from .core import PatientCaseRunner as _PCR

    profile_choices = list(_PCR().get_available_profiles().keys())
    config_group.add_argument("--profile", metavar="NAME", choices=profile_choices, help="override simulation profile")
    config_group.add_argument("--quick", action="store_true", help="coarse-mesh fast-settings test mode")
    config_group.add_argument(
        "--end-time",
        metavar="T",
        type=float,
        help="override simulation endTime in seconds (overrides config and cardiac-cycle calculation)",
    )

    # Output and update
    output_group = parser.add_argument_group("output and update")
    output_group.add_argument(
        "--run-name", "-n", metavar="NAME", help="output folder name (default: run_YYYYMMDD_HHMMSS)"
    )
    output_group.add_argument(
        "--update",
        "-u",
        metavar="CASE_PATH",
        help="update existing case, preserving mesh (default steps: case,boundary)",
    )
    output_group.add_argument(
        "--postprocess", "-p", metavar="RUN_DIR", help="re-run post-processing on an existing run directory"
    )
    output_group.add_argument(
        "--max-runs",
        metavar="N",
        type=int,
        default=0,
        help="after creating a new run, prune oldest run_*/ subdirs so at most N remain " "(0 = no pruning, default)",
    )

    # Other
    other_group = parser.add_argument_group("other")
    other_group.add_argument(
        "--verbose", "-v", action="store_true", help="show full log output instead of summary mode"
    )

    return parser


def run_standalone_postprocess(run_dir: str) -> None:
    """
    Run standalone post-processing on an existing simulation run.

    This loads the merged_config.json from the run directory, re-runs
    hemodynamics analysis, and exports QoIs to JSON/CSV.

    Args:
        run_dir: Path to the run directory (e.g., output/PAT003/run_xxx/)
    """
    import json
    from pathlib import Path

    run_path = Path(run_dir)

    # Find the OpenFOAM case directory
    if (run_path / "openfoam").exists():
        case_dir = run_path / "openfoam"
        reports_dir = run_path / "reports"
    elif (run_path / "constant" / "polyMesh").exists():
        case_dir = run_path
        reports_dir = run_path.parent / "reports"
    else:
        print(f"Error: cannot find OpenFOAM case in {run_dir}")
        print("  Expected openfoam/ subdirectory or constant/polyMesh/")
        return

    # Find merged_config.json
    config_candidates = [
        run_path / "reports" / "merged_config.json",
        reports_dir / "merged_config.json",
        run_path / "merged_config.json",
    ]

    config = {}
    config_file = None
    for candidate in config_candidates:
        if candidate.exists():
            config_file = candidate
            with open(candidate, "r") as f:
                config = json.load(f)
            break

    if config_file:
        print(f"Config:  {config_file}")
    else:
        print("Warning: merged_config.json not found, using defaults")

    print(f"\nPost-processing: {run_path}")
    print(f"  Case:    {case_dir}")
    print(f"  Output:  {reports_dir}")

    # Import and run hemodynamics analysis
    from aortacfd_lib.hemodynamics_postprocessor import HemodynamicsPostProcessor

    processor = HemodynamicsPostProcessor(str(case_dir), config)

    # Check if WSS exists
    if not processor._check_wss_exists():
        print("  WSS data not found, running foamPostProcess...")
        processor.run_wss_postprocess()

    print("  Computing hemodynamic metrics...")
    results = processor.compute_all()

    reports_dir.mkdir(parents=True, exist_ok=True)
    processor.generate_report(results, str(reports_dir))

    json_path, csv_path = processor.export_qoi(results, str(run_path))

    # Summary
    print("\nResults:")
    if results.pressure_drop_mmhg:
        mean_dp = sum(results.pressure_drop_mmhg.values()) / len(results.pressure_drop_mmhg)
        print(f"  Pressure drop (mean): {mean_dp:.2f} mmHg")
    print(f"  WSS p99 (peak systole): {results.wss_p99:.2f} Pa")
    if results.tawss_p99 > 0:
        print(f"  TAWSS p99: {results.tawss_p99:.2f} Pa")
        print(f"  OSI mean (masked): {results.osi_mean_masked:.4f}")
    if results.peak_systole_detected:
        print(f"  Peak systole: t = {results.peak_systole_time:.4f} s")

    print("\nOutputs:")
    print(f"  {json_path}")
    print(f"  {csv_path}")
    print(f"  {reports_dir / 'hemodynamics_report.txt'}")


def main():
    """Main CLI entry point."""
    # Pre-parse just the --verbose flag before full parsing
    # This ensures Logger is configured before any imports that use it
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    # Initialize logger with verbosity setting BEFORE anything else
    from aortacfd_lib.utils.logger import Logger

    Logger(verbose=verbose)

    # Now safe to create parser and parse all args
    parser = create_parser()
    args = parser.parse_args()

    # Initialize runner (import here to ensure Logger is configured first)
    from .core import PatientCaseRunner

    runner = PatientCaseRunner()

    # Environment diagnostics
    if args.doctor:
        from .doctor import run_doctor

        sys.exit(run_doctor())

    # List available patients
    if args.list:
        patients = runner.list_available_patients()
        if patients:
            print("\nAvailable cases:")
            for patient in patients:
                print(f"  {patient}")
            print("\nRun:  python run_patient.py <case_id>")
        else:
            print("No cases found in cases_input/")
        return

    # List available workflow steps
    if args.list_steps:
        from .steps import WorkflowSteps

        steps = WorkflowSteps()

        step_info = {
            "case": ("generate OpenFOAM dictionaries", "setup:dict"),
            "mesh": ("create mesh (blockMesh + snappyHexMesh)", "run:mesh"),
            "boundary": ("set up boundary conditions and flow data", "setup:bc"),
            "regenerate-numerics": ("regenerate fvSchemes/fvSolution after meshing", "setup:regenerate-numerics"),
            "solver": ("run CFD solver", "run:solver"),
            "reconstruct": ("reconstruct parallel case", "run:reconstruct"),
            "postprocess": ("compute hemodynamics and export QoIs", "run:hemodynamics"),
            "paraview": ("ParaView visualization", "execute_post"),
            "all": ("complete workflow (default)", "runAll"),
        }

        print("\nWorkflow steps:")
        for step_name, (description, workflow_cmd) in step_info.items():
            deps = steps.get_step_dependencies(step_name)
            deps_str = f"  (after: {', '.join(deps)})" if deps else ""
            print(f"  {step_name:<22s} {description}{deps_str}")

        print("\nExamples:")
        print("  python run_patient.py BPM120 --steps case,mesh,boundary")
        print("  python run_patient.py BPM120 --steps solver")
        print("  python run_patient.py BPM120   # runs all steps")
        return

    # Handle standalone post-processing mode
    if args.postprocess:
        run_standalone_postprocess(args.postprocess)
        return

    # Validate patient ID
    if not args.patient_id:
        parser.print_help()
        sys.exit(1)

    # Prepare options
    options = {}
    if args.quick:
        options["profile"] = "sim_laminar_coarse"
    if args.profile:
        options["profile"] = args.profile
    if args.run_name:
        options["run_name"] = args.run_name
    if args.end_time is not None:
        if args.end_time <= 0:
            print(f"Error: --end-time must be > 0 (got {args.end_time})")
            sys.exit(1)
        options["end_time"] = args.end_time
    if args.max_runs > 0:
        options["max_runs"] = args.max_runs

    # Get config override
    config_override = args.config

    # Handle --update mode
    if args.update:
        from pathlib import Path

        update_case = Path(args.update)
        if not update_case.exists():
            print(f"Error: case not found: {update_case}")
            sys.exit(1)

        # Check if it has polyMesh (either directly or in openfoam subdir)
        if (update_case / "constant" / "polyMesh").exists():
            case_path = update_case
        elif (update_case / "openfoam" / "constant" / "polyMesh").exists():
            case_path = update_case / "openfoam"
        else:
            print(f"Error: no polyMesh found in {update_case}")
            print("  Expected: constant/polyMesh or openfoam/constant/polyMesh")
            sys.exit(1)

        print("\nUpdate mode")
        print(f"  Case:  {case_path}")
        print("  Mesh:  preserved")
        if config_override:
            print(f"  Config: {config_override}")

        options["case_dir"] = str(case_path)
        options["update_mode"] = True

    # Handle workflow steps
    valid_steps = {
        "case",
        "mesh",
        "boundary",
        "regenerate-numerics",
        "solver",
        "reconstruct",
        "postprocess",
        "paraview",
        "all",
    }
    steps = []

    # Parse --steps (comma-separated string)
    if args.steps:
        for s in args.steps.split(","):
            s = s.strip()
            if s not in valid_steps:
                print(f"Error: unknown step '{s}'")
                print(f"  Valid: {', '.join(sorted(valid_steps))}")
                sys.exit(1)
            steps.append(s)

    # Parse --step (multiple arguments)
    if args.step_list:
        steps.extend(args.step_list)

    # Default steps depend on mode
    if not steps:
        if args.update:
            # Update mode: regenerate case setup and boundary conditions, skip mesh
            steps = ["case", "boundary"]
        else:
            steps = ["all"]

    # Map CLI step names to workflow commands
    step_mapping = {
        "case": "setup:dict",
        "mesh": "run:mesh",
        "boundary": "setup:bc",
        "regenerate-numerics": "setup:regenerate-numerics",
        "solver": "run:solver",
        "reconstruct": "run:reconstruct",
        "postprocess": "run:hemodynamics",
        "paraview": "execute_post",
        "all": "runAll",
    }

    print(f"\nAortaCFD — {args.patient_id}")
    print(f"  Steps: {', '.join(steps)}")

    try:
        # Load patient case first
        case_info = runner.load_patient_case(args.patient_id, config_path=config_override)
        print(f"  Config: {case_info['config_file']}")
        description = case_info["config"].get("case_info", {}).get("description")
        if description:
            print(f"  Description: {description}")

        # Prepare simulation
        sim_config = runner.prepare_simulation(case_info, options)
        print(f"  Profile: {sim_config['profile_name']}")

        # Show output path
        if not args.update:
            print(f"  Output: {sim_config['run_dir']}")

        # Run workflow steps
        success = True
        for step in steps:
            workflow_command = step_mapping.get(step, step)
            print(f"\n  [{step}] running...")

            options["workflow_step"] = workflow_command
            case_dir = options.get("case_dir")
            step_success = runner.run_workflow_step(sim_config, workflow_command, case_dir=case_dir)

            if not step_success:
                print(f"  [{step}] FAILED")
                success = False
                break
            else:
                print(f"  [{step}] done")

        if success:
            # Generate results summary
            results_path = runner.generate_results_summary(case_info, sim_config)
            print(f"\nCompleted. Results: {results_path}")
            sys.exit(0)
        else:
            print("\nWorkflow failed.")
            sys.exit(1)

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
