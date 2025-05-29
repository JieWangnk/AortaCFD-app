import os
import shutil
from SCRIPTS.logger import Logger

# Initialize the logger
log_file_path = os.path.join(os.getcwd(), "cycleDataSetup.log")
logger = Logger(log_file_path).get_logger()

class CycleDataSetup:
    def __init__(self, inletDataFile, determined_cardiac_period, number_of_cycles, case_directory="."):
        """
        Initializes the CycleDataSetup class.

        Args:
            inletDataFile (str): Name of the directory containing U-field files for a single cycle.
            determined_cardiac_period (float): Duration of one cardiac cycle in seconds.
            number_of_cycles (int): Number of cycles to simulate.
            case_directory (str): Base directory for the OpenFOAM case.
        """
        self.inletDataFile = os.path.splitext(inletDataFile)[0]
        self.cardiacPeriod = float(determined_cardiac_period)
        self.numberOfCycles = number_of_cycles
        self.baseDir = case_directory
        self.source_U_files_dir = os.path.join(self.baseDir, "constant", "boundaryData", "inlet", self.inletDataFile)

    def create_time_dirs(self, timeDirList):
        """
        Creates time directories for the simulation and sets up symbolic links for extra cycles.

        Args:
            timeDirList (list): List of time directories for the first cycle.
        """
        for i in range(len(timeDirList)):  # Include the last time point
            timeDirPath = os.path.join(self.baseDir, "constant", "boundaryData", "inlet", timeDirList[i])

            # Make the directory if it does not exist
            if not os.path.exists(timeDirPath):
                os.mkdir(timeDirPath)

            # Copy the U_* file to the directory and rename it to U
            srcFile = os.path.join(self.source_U_files_dir, f"U_{timeDirList[i]}")
            destFile = os.path.join(timeDirPath, "U")
            try:
                shutil.copy2(srcFile, destFile)
            except Exception as e:
                logger.error(f"Failed to copy {srcFile} to {destFile}: {e}")
                raise

            # Create symbolic links for extra cycles
            for j in range(1, self.numberOfCycles):
                newTimeDir = "{:.6f}".format(float(timeDirList[i]) + j * self.cardiacPeriod)
                target_dir = os.path.join(self.baseDir, "constant", "boundaryData", "inlet", newTimeDir)
                try:
                    # Remove the directory if it exists
                    if os.path.lexists(target_dir):
                        os.unlink(target_dir)
                    # Create the symbolic link
                    relative_path = os.path.relpath(timeDirPath, os.path.dirname(target_dir))
                    os.symlink(relative_path, target_dir)
                except Exception as e:
                    logger.error(f"Failed to create symbolic link for {newTimeDir}: {e}")
                    raise

    def execute(self):
        """
        Executes the setup of time directories for the simulation.
        """
        if not os.path.exists(self.source_U_files_dir):
            logger.error(f"No inlet velocity profile data found in {self.source_U_files_dir}")
            raise FileNotFoundError(f"No inlet velocity profile data found in {self.source_U_files_dir}")

        timeDirList = []
        subFiles = os.listdir(self.source_U_files_dir)
        subFiles.sort()

        for file in subFiles:
            if file.startswith("U_"):
                timeDirList.append(file.split("_")[1])

        if not timeDirList:
            logger.error(f"No U_* files found in {self.source_U_files_dir}")
            raise ValueError(f"No U_* files found in {self.source_U_files_dir}")

        # Sort timeDirList numerically
        timeDirList.sort(key=float)

        if self.cardiacPeriod <= 0:
            raise ValueError(f"Invalid cardiac period: {self.cardiacPeriod}. Must be positive.")
        if self.numberOfCycles <= 0:
            raise ValueError(f"Invalid number of cycles: {self.numberOfCycles}. Must be positive.")

        self.create_time_dirs(timeDirList)

if __name__ == "__main__":
    try:
        # Example test setup
        inletProfile = CycleDataSetup(
            inletDataFile="inletProfileData",
            determined_cardiac_period=0.81,
            number_of_cycles=2,
            case_directory=os.getcwd()
        )
        inletProfile.execute()
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        raise
