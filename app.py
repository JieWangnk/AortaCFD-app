# app.py
import sys
import argparse
from config.builder import ConfigBuilder
from workflow.manager import WorkflowManager, AortaCFDError
from aortacfd_lib.utils.logger import Logger

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="AortaCFD Intelligent Workflow.")
    parser.add_argument("command", help="The command to run (e.g., createCase, runAll)")
    parser.add_argument("--case", required=True, help="Name of the case directory in CAD/")
    parser.add_argument("--profile", required=True, help="Name of the simulation profile in CONFIG/profiles/")
    args = parser.parse_args()

    log_file_path = "AortaCFD.log"
    logger = Logger(log_file_path).get_logger()
    
    logger.info("========================================================")
    logger.info(f"Starting command '{args.command}' for case '{args.case}' with profile '{args.profile}'")

    try:
        # 1. Build the dynamic configuration
        builder = ConfigBuilder()
        config = builder.build(case_name=args.case, sim_profile_name=args.profile)
        logger.info("Configuration built successfully.")

        # 2. Initialize and run the workflow
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