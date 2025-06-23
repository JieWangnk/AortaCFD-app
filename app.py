# app.py
import sys
import argparse
from config.builder import ConfigBuilder
from workflow.manager import WorkflowManager, AortaCFDError
from aortacfd_lib.utils.logger import Logger

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="AortaCFD Intelligent Workflow.")
    parser.add_argument("command", help="The command to run (e.g., setup:all, setup:bc, runMesh, runAll)")
    parser.add_argument("--case", required=True, help="Name of the case directory in CAD/")
    parser.add_argument("--profile", required=True, help="Name of the simulation profile in CONFIG/profiles/")
    
    # --- ADD THIS NEW FLAG ---
    parser.add_argument("--clean", action="store_true", help="Perform a clean run by deleting the case directory first.")
    
    args = parser.parse_args()

    log_file_path = "AortaCFD.log"
    logger = Logger(log_file_path).get_logger()
    
    logger.info("========================================================")
    logger.info(f"Starting command '{args.command}' for case '{args.case}' with profile '{args.profile}'")

    try:
        builder = ConfigBuilder()
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