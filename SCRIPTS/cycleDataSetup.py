import os
from SCRIPTS.logger import Logger

# Initialize the logger
log_file_path = os.path.join(os.getcwd(), "cycleDataSetup.log")
logger = Logger(log_file_path).get_logger()

class CycleDataSetup:
    def __init__(self, inletDataFile, cardiacCycle, numberOfCycle, case_directory="."):
        self.inletDataFile = os.path.splitext(inletDataFile)[0]
        self.BPM = int(60 / cardiacCycle)
        self.cardiacPeriod = float(cardiacCycle)
        self.numberOfCycle = numberOfCycle
        self.baseDir = case_directory

    def create_time_dirs(self, timeDirList):
        for i in range(len(timeDirList) - 1):
            timeDirPath = os.path.join(self.baseDir, "constant/boundaryData/inlet/", timeDirList[i])

            # Make the directory if it does not exist
            if not os.path.exists(timeDirPath):
                os.mkdir(timeDirPath)

            # Copy the U_* file to the directory and rename it to U
            srcFile = os.path.join(self.baseDir, "constant/boundaryData/inlet/" + str(self.inletDataFile) + "/U_" + timeDirList[i])
            destFile = os.path.join(timeDirPath, "U")
            try:
                os.system(f"cp {srcFile} {destFile}")
                
            except Exception as e:
                logger.error(f"Failed to copy {srcFile} to {destFile}: {e}")
                raise

            # Create symbolic links for extra cycles
            for j in range(1, self.numberOfCycle):
                newTimeDir = "{:.6f}".format(float(timeDirList[i]) + j * self.cardiacPeriod)
                target_dir = os.path.join(self.baseDir, "constant/boundaryData/inlet/", newTimeDir)
                try:
                    # Remove the directory if it exists
                    os.system(f"rm -rf {target_dir}")
                    # Create the symbolic link
                    os.system(f"ln -s {timeDirPath} {target_dir}")
                    
                except Exception as e:
                    logger.error(f"Failed to create symbolic link for {newTimeDir}: {e}")
                    raise

    def execute(self):
        inlet_data_dir = os.path.join(self.baseDir, "constant/boundaryData/inlet/" + str(self.inletDataFile) + "/")
        if not os.path.exists(inlet_data_dir):
            logger.error(f"No inlet velocity profile data found for BPM = {self.inletDataFile}")
            return

        timeDirList = []
        subFile = os.listdir(inlet_data_dir)
        subFile.sort()

        for file in subFile:
            if file.startswith("U"):
                timeDirList.append(file.split("_")[1])

        self.create_time_dirs(timeDirList)

if __name__ == "__main__":
    try:
        inletProfile = CycleDataSetup(inletDataFile="inletProfile", cardiacCycle=0.81, numberOfCycle=2)
        inletProfile.execute()
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        raise
