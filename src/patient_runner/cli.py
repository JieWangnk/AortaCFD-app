"""
CLI interface for patient runner - handles command-line argument parsing
"""

import sys
import argparse

# Delay PatientCaseRunner import until after Logger is configured


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog='run_patient.py',
        description="AortaCFD - Automated Aortic CFD Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
═══════════════════════════════════════════════════════════════
QUICK START EXAMPLES
═══════════════════════════════════════════════════════════════

  # Run complete workflow (output: output/PAT003/run_YYYYMMDD_HHMMSS/)
  python run_patient.py PAT003

  # Custom run name (output: output/PAT003/my_test/)
  python run_patient.py PAT003 --run-name my_test

  # Use custom config
  python run_patient.py PAT003 --config config_fine_mesh.json

  # Run only specific steps
  python run_patient.py PAT003 --steps case,mesh,boundary

  # Update existing case (preserves mesh, regenerates BCs)
  python run_patient.py PAT003 --update output/PAT003/run_xxx/openfoam

  # Update and run solver
  python run_patient.py PAT003 --update output/PAT003/run_xxx/openfoam --steps solver

═══════════════════════════════════════════════════════════════
WORKFLOW STEPS
═══════════════════════════════════════════════════════════════

  case                → Generate OpenFOAM dictionaries
  mesh                → Create computational mesh
  boundary            → Setup boundary conditions
  regenerate-numerics → Regenerate fvSchemes/fvSolution
  solver              → Run CFD solver
  reconstruct         → Reconstruct parallel case
  hemodynamics        → Compute WSS, TAWSS, OSI, RRT
  post                → ParaView visualization
  all                 → Complete workflow (default)

═══════════════════════════════════════════════════════════════
        """
    )

    # Positional argument
    parser.add_argument('patient_id', nargs='?',
                       help='Patient case to run (e.g., PAT003, BPM120)')

    # ═══ INFORMATIONAL ═══
    info_group = parser.add_argument_group('Information')
    info_group.add_argument('--list', '-l', action='store_true',
                           help='List available patient cases')
    info_group.add_argument('--list-steps', action='store_true',
                           help='List all workflow steps with details')

    # ═══ WORKFLOW CONTROL ═══
    workflow_group = parser.add_argument_group('Workflow Control')
    workflow_group.add_argument('--steps', '-s', metavar='STEPS',
                               help='Run specific step(s), comma-separated (e.g., --steps case,mesh)')
    workflow_group.add_argument('--step', action='append', dest='step_list',
                               choices=['case', 'mesh', 'boundary', 'regenerate-numerics', 'solver', 'reconstruct', 'hemodynamics', 'post', 'all'],
                               help='Run specific step (can use multiple times)')

    # ═══ CONFIGURATION ═══
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument('--config', '-c', metavar='PATH',
                             help='Config JSON file (default: cases_input/<patient_id>/config.json)')
    # Get profile choices dynamically - import here to avoid early Logger initialization
    from .core import PatientCaseRunner as _PCR
    profile_choices = list(_PCR().get_available_profiles().keys())
    config_group.add_argument('--profile', metavar='NAME',
                             choices=profile_choices,
                             help='Override simulation profile')
    config_group.add_argument('--quick', action='store_true',
                             help='Quick test mode (coarse mesh, fast settings)')

    # ═══ OUTPUT & UPDATE ═══
    output_group = parser.add_argument_group('Output & Update')
    output_group.add_argument('--run-name', '-n', metavar='NAME',
                             help='Custom run folder name (default: run_YYYYMMDD_HHMMSS). '
                                  'Output: output/<patient_id>/<NAME>/')
    output_group.add_argument('--update', '-u', metavar='CASE_PATH',
                             help='Update existing case at CASE_PATH. Preserves mesh, '
                                  'regenerates specified --steps (default: case,boundary)')

    # ═══ OTHER ═══
    other_group = parser.add_argument_group('Other Options')
    other_group.add_argument('--verbose', '-v', action='store_true',
                            help='Show detailed log output (default: clean summary mode)')

    return parser


def main():
    """Main CLI entry point."""
    # Pre-parse just the --verbose flag before full parsing
    # This ensures Logger is configured before any imports that use it
    verbose = '-v' in sys.argv or '--verbose' in sys.argv

    # Initialize logger with verbosity setting BEFORE anything else
    from aortacfd_lib.utils.logger import Logger
    Logger(verbose=verbose)

    # Now safe to create parser and parse all args
    parser = create_parser()
    args = parser.parse_args()

    # Initialize runner (import here to ensure Logger is configured first)
    from .core import PatientCaseRunner
    runner = PatientCaseRunner()

    # List available patients
    if args.list:
        patients = runner.list_available_patients()
        if patients:
            print("\n📋 Available Patient Cases:")
            print("=" * 30)
            for patient in patients:
                print(f"  👤 {patient}")
            print(f"\nUsage: python run_patient.py <patient_id>")
        else:
            print("❌ No patient cases found in cases_input/")
        return

    # List available workflow steps
    if args.list_steps:
        from .steps import WorkflowSteps
        steps = WorkflowSteps()

        print("\n🔧 Available Workflow Steps:")
        print("=" * 50)

        step_info = {
            'case': ('Create case structure and configuration files', ['setup:dict']),
            'mesh': ('Generate mesh using blockMesh, surfaceFeatures, snappyHexMesh', ['run:mesh']),
            'boundary': ('Setup boundary conditions and flow data', ['setup:bc']),
            'regenerate-numerics': ('Regenerate fvSchemes/fvSolution with mesh-adaptive adjustments', ['setup:regenerate-numerics']),
            'solver': ('Run CFD solver (pimpleFoam/foamRun)', ['run:solver']),
            'reconstruct': ('Reconstruct parallel case from processor directories', ['run:reconstruct']),
            'hemodynamics': ('Compute WSS, TAWSS, OSI, RRT, pressure drop', ['run:hemodynamics']),
            'post': ('Execute ParaView visualization', ['execute_post']),
            'all': ('Complete workflow (default)', ['runAll'])
        }

        for step_name, (description, workflow_cmds) in step_info.items():
            deps = steps.get_step_dependencies(step_name)
            deps_str = f" (requires: {', '.join(deps)})" if deps else ""
            print(f"  🔸 {step_name:10} - {description}{deps_str}")
            print(f"     {'':10}   Workflow: {', '.join(workflow_cmds)}")

        print(f"\nUsage Examples:")
        print(f"  python run_patient.py patient1 --step mesh")
        print(f"  python run_patient.py patient1 --steps case,mesh,boundary")
        print(f"  python run_patient.py patient1  # (runs all steps)")
        return

    # Validate patient ID
    if not args.patient_id:
        parser.print_help()
        sys.exit(1)

    # Prepare options
    options = {}
    if args.quick:
        options['profile'] = 'sim_laminar_coarse'
    if args.profile:
        options['profile'] = args.profile
    if args.run_name:
        options['run_name'] = args.run_name

    # Get config override
    config_override = args.config

    # Handle --update mode
    if args.update:
        from pathlib import Path

        update_case = Path(args.update)
        if not update_case.exists():
            print(f"❌ Update case not found: {update_case}")
            sys.exit(1)

        # Check if it has polyMesh (either directly or in openfoam subdir)
        if (update_case / 'constant' / 'polyMesh').exists():
            case_path = update_case
        elif (update_case / 'openfoam' / 'constant' / 'polyMesh').exists():
            case_path = update_case / 'openfoam'
        else:
            print(f"❌ No polyMesh found in: {update_case}")
            print(f"   Expected: {update_case}/constant/polyMesh or {update_case}/openfoam/constant/polyMesh")
            sys.exit(1)

        print(f"\n🔄 UPDATE MODE")
        print(f"=" * 60)
        print(f"📁 Updating case: {case_path}")
        print(f"✅ Mesh preserved: {case_path}/constant/polyMesh")

        if config_override:
            print(f"📝 Using config: {config_override}")
        else:
            print(f"📝 Using default config for {args.patient_id}")

        options['case_dir'] = str(case_path)
        options['update_mode'] = True
        print(f"=" * 60)

    # Handle workflow steps
    valid_steps = {'case', 'mesh', 'boundary', 'regenerate-numerics', 'solver', 'reconstruct', 'hemodynamics', 'post', 'all'}
    steps = []

    # Parse --steps (comma-separated string)
    if args.steps:
        for s in args.steps.split(','):
            s = s.strip()
            if s not in valid_steps:
                print(f"❌ Invalid step: '{s}'")
                print(f"   Valid steps: {', '.join(sorted(valid_steps))}")
                sys.exit(1)
            steps.append(s)

    # Parse --step (multiple arguments)
    if args.step_list:
        steps.extend(args.step_list)

    # Default steps depend on mode
    if not steps:
        if args.update:
            # Update mode: regenerate case setup and boundary conditions, skip mesh
            steps = ['case', 'boundary']
            print(f"ℹ️  Update mode default: running steps [case, boundary]")
        else:
            steps = ['all']

    # Map CLI step names to workflow commands
    step_mapping = {
        'case': 'setup:dict',
        'mesh': 'run:mesh',
        'boundary': 'setup:bc',
        'regenerate-numerics': 'setup:regenerate-numerics',
        'solver': 'run:solver',
        'reconstruct': 'run:reconstruct',
        'hemodynamics': 'run:hemodynamics',
        'post': 'execute_post',
        'all': 'runAll'
    }

    print("\n" + "="*60)
    print(f"🏥 AortaCFD Patient Case Runner")
    print(f"🔬 Running analysis for: {args.patient_id}")
    print(f"📋 Steps: {', '.join(steps)}")
    print("="*60)

    try:
        # Load patient case first
        case_info = runner.load_patient_case(args.patient_id, config_path=config_override)
        print(f"✅ Patient case loaded from: {case_info['config_file']}")
        description = case_info['config'].get('case_info', {}).get('description')
        if description:
            print(f"   📄 Description: {description}")

        # Prepare simulation
        sim_config = runner.prepare_simulation(case_info, options)
        print(f"✅ Configuration prepared - Profile: {sim_config['profile_name']}")

        # Show output path
        if not args.update:
            print(f"📁 Output: {sim_config['run_dir']}")

        # Run workflow steps
        success = True
        for step in steps:
            workflow_command = step_mapping.get(step, step)
            print(f"\n🔄 Running workflow step: {step} ({workflow_command})")

            options['workflow_step'] = workflow_command
            case_dir = options.get('case_dir')
            step_success = runner.run_workflow_step(sim_config, workflow_command, case_dir=case_dir)

            if not step_success:
                print(f"❌ Step '{step}' failed!")
                success = False
                break
            else:
                print(f"✅ Step '{step}' completed successfully")

        if success:
            # Generate results summary
            results_path = runner.generate_results_summary(case_info, sim_config)
            print("\n" + "="*60)
            print("✅ WORKFLOW COMPLETED SUCCESSFULLY!")
            print("="*60)
            print(f"📁 Results: {results_path}")
            sys.exit(0)
        else:
            print("\n❌ Workflow failed!")
            sys.exit(1)

    except Exception as e:
        print(f"\n💥 Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
