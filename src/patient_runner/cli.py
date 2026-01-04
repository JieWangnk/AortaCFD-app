"""
CLI interface for patient runner - handles command-line argument parsing
"""

import sys
import argparse
from .core import PatientCaseRunner


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

  # Run complete workflow
  python run_patient.py patient1

  # Use custom config
  python run_patient.py patient1 --config my_config.json

  # Run only specific steps (two syntaxes)
  python run_patient.py patient1 --steps case,mesh          # comma-separated
  python run_patient.py patient1 --step mesh --step solver  # multiple flags

  # Mesh-only for testing different configs
  python run_patient.py BPM120 -c cases_input/BPM120/config_mesh_span20.json -s case,mesh

  # Update existing case with new config (preserves mesh!)
  python run_patient.py patient1 --update output/patient1/run_xxx/openfoam

═══════════════════════════════════════════════════════════════
WORKFLOW STEPS
═══════════════════════════════════════════════════════════════

  case                → Generate OpenFOAM dictionaries (controlDict, fvSchemes, etc.)
  mesh                → Create computational mesh (blockMesh + snappyHexMesh)
  boundary            → Setup boundary conditions and inlet flow data
  regenerate-numerics → Regenerate fvSchemes/fvSolution with mesh-adaptive adjustments
  solver              → Run CFD solver (parallel execution)
  reconstruct         → Reconstruct results from parallel decomposition
  post                → Post-processing and visualization
  all                 → Run complete workflow (default)

═══════════════════════════════════════════════════════════════
        """
    )

    # Positional argument
    parser.add_argument('patient_id', nargs='?',
                       help='Patient case to run (e.g., patient1, BPM120)')

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
                               choices=['case', 'mesh', 'boundary', 'regenerate-numerics', 'solver', 'reconstruct', 'post', 'all'],
                               help='Run specific step (can use multiple times: --step case --step mesh)')

    # ═══ CONFIGURATION ═══
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument('--config', '-c', metavar='PATH',
                             help='Config JSON file (default: cases_input/<patient_id>/config.json)')
    profile_choices = list(PatientCaseRunner().get_available_profiles().keys())
    config_group.add_argument('--profile', metavar='NAME',
                             choices=profile_choices,
                             help='Override simulation profile')
    config_group.add_argument('--quick', action='store_true',
                             help='Quick test mode (coarse mesh, fast settings)')

    # ═══ RESUME / UPDATE ═══
    resume_group = parser.add_argument_group('Resume & Update')
    resume_group.add_argument('--resume', action='store_true',
                             help='Resume from most recent run')
    resume_group.add_argument('--update', metavar='CASE_PATH',
                             help='Update existing case (preserves mesh, regenerates all else)')

    # ═══ ADVANCED ═══
    advanced_group = parser.add_argument_group('Advanced Options')
    advanced_group.add_argument('--case-dir', metavar='PATH',
                               help='Use specific case directory')
    advanced_group.add_argument('--overwrite', action='store_true',
                               help='Overwrite existing output')

    return parser


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Initialize runner
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
            'post': ('Execute post-processing', ['execute_post']),
            'all': ('Complete workflow (default)', ['runAll'])
        }
        
        for step_name, (description, workflow_cmds) in step_info.items():
            deps = steps.get_step_dependencies(step_name)
            deps_str = f" (requires: {', '.join(deps)})" if deps else ""
            print(f"  🔸 {step_name:10} - {description}{deps_str}")
            print(f"     {'':10}   Workflow: {', '.join(workflow_cmds)}")
        
        print(f"\nUsage Examples:")
        print(f"  python run_patient.py patient1 --step mesh")
        print(f"  python run_patient.py patient1 --step case --step mesh")
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
    if args.overwrite:
        options['overwrite'] = True

    # Handle --resume flag
    if args.resume:
        from pathlib import Path
        import glob

        # Find most recent run directory for this patient
        output_dir = Path('output') / args.patient_id
        if output_dir.exists():
            run_dirs = sorted(output_dir.glob('run_*'), key=lambda p: p.stat().st_mtime, reverse=True)
            if run_dirs:
                most_recent = run_dirs[0]
                # Check if it's already an OpenFOAM case directory (has system/, constant/, 0/)
                if (most_recent / 'system').exists() and (most_recent / 'constant').exists():
                    # Direct OpenFOAM case directory
                    options['case_dir'] = str(most_recent)
                    print(f"🔄 Resuming from: {most_recent}")
                elif (most_recent / 'openfoam').exists():
                    # Nested structure with openfoam subdirectory
                    options['case_dir'] = str(most_recent / 'openfoam')
                    print(f"🔄 Resuming from: {most_recent / 'openfoam'}")
                else:
                    print(f"⚠️  Run directory exists but doesn't contain OpenFOAM case files")
                    print(f"   Directory: {most_recent}")
                    print(f"   Starting fresh run instead")
                    options['case_dir'] = None

                # If no specific steps provided, suggest what to run
                if not args.step and options.get('case_dir'):
                    print(f"\n💡 Tip: Specify which step to resume from, e.g.:")
                    print(f"   --step boundary    (if mesh is done)")
                    print(f"   --step solver      (if BC is done)")
                    print(f"   --step reconstruct (if solver is done)")
            else:
                print(f"⚠️  No existing run directories found for {args.patient_id}")
                print(f"   Starting fresh run instead")
        else:
            print(f"⚠️  No output directory found for {args.patient_id}")
            print(f"   Starting fresh run instead")

    # Get config override first (used in multiple paths below)
    config_override = args.config

    # Handle --update: regenerate all files except polyMesh
    if args.update:
        from pathlib import Path
        import shutil

        update_case = Path(args.update)
        if not update_case.exists():
            print(f"❌ Update case not found: {update_case}")
            sys.exit(1)

        # Check if it has polyMesh
        polymesh_dir = update_case / 'constant' / 'polyMesh'
        if not polymesh_dir.exists():
            print(f"❌ No polyMesh found in: {update_case}")
            print(f"   Expected: {polymesh_dir}")
            sys.exit(1)

        print(f"\n🔄 UPDATE MODE")
        print(f"=" * 60)
        print(f"📁 Updating case: {update_case}")
        print(f"✅ Preserving mesh: {polymesh_dir}")
        print(f"🔧 Will regenerate: system/, 0/, controlDict, fvSchemes, fvSolution")

        # Use config if specified
        if config_override:
            print(f"📝 Using config: {config_override}")
        else:
            print(f"📝 Using default config for {args.patient_id}")

        # Backup polyMesh
        backup_polymesh = update_case / 'constant' / 'polyMesh_BACKUP'
        print(f"💾 Backing up polyMesh...")
        if backup_polymesh.exists():
            shutil.rmtree(backup_polymesh)
        shutil.copytree(polymesh_dir, backup_polymesh)

        # Set options to regenerate everything except mesh
        options['case_dir'] = str(update_case)
        options['update_mode'] = True
        options['preserve_polymesh'] = str(backup_polymesh)

        print(f"=" * 60)
        print()
    elif args.case_dir:
        options['case_dir'] = args.case_dir

    # Handle workflow steps - support both --steps (comma-separated) and --step (multiple)
    valid_steps = {'case', 'mesh', 'boundary', 'regenerate-numerics', 'solver', 'reconstruct', 'post', 'all'}
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

    # Default to 'all' if no steps specified
    if not steps:
        steps = ['all']

    # Map CLI step names to workflow commands
    step_mapping = {
        'case': 'setup:dict',
        'mesh': 'run:mesh',
        'boundary': 'setup:bc',
        'regenerate-numerics': 'setup:regenerate-numerics',
        'solver': 'run:solver',
        'reconstruct': 'run:reconstruct',
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