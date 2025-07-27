# app.py
import sys
import argparse
from src.config.builder import ConfigBuilder
from src.workflow.manager import WorkflowManager, AortaCFDError
from src.aortacfd_lib.utils.logger import Logger
from src.aortacfd_lib.simulation_reporter import create_simulation_report

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="AortaCFD Intelligent Workflow.")
    parser.add_argument("command", help="The command to run (e.g., setup:all, setup:bc, runMesh, runAll, report)")
    parser.add_argument("--case", required=True, help="Name of the case directory in data/CAD/")
    parser.add_argument("--profile", help="Name of the simulation profile in src/config/profiles/ (not required for report command)")
    # OpenFOAM 12 only - no version selection needed
    parser.add_argument("--clean", action="store_true", help="Perform a clean run by deleting the case directory first.")
    
    args = parser.parse_args()

    # Handle report command separately
    if args.command == "report":
        if not args.profile:
            # For report command, try to infer case from output directory
            import os
            case_path = f"output/OPENFOAM/{args.case}"
            if not os.path.exists(case_path):
                print(f"Error: Case directory not found: {case_path}")
                print("Available cases:")
                for case in os.listdir("output/OPENFOAM"):
                    print(f"  {case}")
                sys.exit(1)
            
            try:
                report_path = create_simulation_report(case_path, "reports")
                print(f"Simulation report generated: {report_path}")
                return
            except Exception as e:
                print(f"Error generating report: {e}")
                sys.exit(1)

    # Validate profile is provided for non-report commands
    if not args.profile:
        parser.error("--profile is required for all commands except 'report'")

    log_file_path = "AortaCFD.log"
    # Clear the log file for a new session
    Logger.clear_log_file(log_file_path)
    logger = Logger("main", log_file_path).get_logger()
    
    logger.info("========================================================")
    logger.info(f"Starting command '{args.command}' for case '{args.case}' with profile '{args.profile}'")
    logger.info("Using OpenFOAM version: 12")

    try:
        builder = ConfigBuilder()
        # OpenFOAM 12 only - no version parameter needed
        config = builder.build(case_name=args.case, sim_profile_name=args.profile)

        # --- PASS THE FLAG TO THE CONFIG ---
        config['clean_run'] = args.clean

        manager = WorkflowManager(config)
        manager.run_workflow(args.command)

    except (AortaCFDError, FileNotFoundError, ValueError) as e:
        logger.error(f"A critical error occurred: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()