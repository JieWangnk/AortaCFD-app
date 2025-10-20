"""
CLI interface for patient runner - handles command-line argument parsing
"""

import sys
import argparse
from .core import PatientCaseRunner


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="AortaCFD Patient Case Runner - Modular CFD Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
WORKFLOW STEPS:
    case        Create case structure and configuration files
    mesh        Generate mesh using blockMesh, surfaceFeatures, snappyHexMesh
    boundary    Setup boundary conditions and flow data
    solver      Run CFD solver (pimpleFoam/foamRun)
    reconstruct Reconstruct parallel case from processor directories
    post        Execute post-processing
    all         Complete workflow (default)

EXAMPLES:
    # Run complete workflow for patient1:
    python run_patient.py patient1

    # Resume from most recent run:
    python run_patient.py patient1 --resume

    # Run only meshing step:
    python run_patient.py patient1 --step mesh

    # Run case setup and meshing:
    python run_patient.py patient1 --step case --step mesh

    # Quick test run:
    python run_patient.py patient1 --quick

    # List available patients:
    python run_patient.py --list

CASE STRUCTURE:
    cases_input/
    ├── patient1/
    │   ├── inlet.stl           
    │   ├── wall_aorta.stl      
    │   ├── outlet*.stl         
    │   ├── flow_data.csv       # Optional
    │   └── config.json         # Required
    └── patient2/
        ├── ...same structure
        """
    )

    parser.add_argument('patient_id', nargs='?',
                       help='Patient ID to analyze (e.g., patient1, patient2)')
    parser.add_argument('--list', '-l', action='store_true',
                       help='List available patient cases')
    parser.add_argument('--list-steps', action='store_true',
                       help='List available workflow steps')
    parser.add_argument('--step', action='append',
                       choices=['case', 'mesh', 'boundary', 'solver', 'reconstruct', 'post', 'all'],
                       help='Run specific workflow step(s) - can be used multiple times')
    parser.add_argument('--quick', action='store_true',
                       help='Quick test run (coarse settings)')
    parser.add_argument('--overwrite', action='store_true',
                       help='Overwrite existing results')
    parser.add_argument('--resume', action='store_true',
                       help='Resume from most recent run directory')
    profile_choices = list(PatientCaseRunner().get_available_profiles().keys())
    parser.add_argument('--profile',
                       choices=profile_choices,
                       help='Override simulation profile using sim_* profile keys')
    parser.add_argument('--config',
                       help='Path to a custom patient configuration JSON (defaults to cases_input/<patient_id>/config.json)')
    parser.add_argument('--case-dir',
                       help='Use existing case directory (for running post-processing on old simulations)')

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

    if args.case_dir:
        options['case_dir'] = args.case_dir

    config_override = args.config

    # Handle workflow steps
    steps = args.step if args.step else ['all']
    
    # Map CLI step names to workflow commands
    step_mapping = {
        'case': 'setup:dict',
        'mesh': 'run:mesh',
        'boundary': 'setup:bc',
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