import os

class CycleDataSetup:
    def __init__(self, BPM, numberOfCycle, baseDir=None):
        self.BPM = BPM
        self.cardiacPeriod = 60 / self.BPM
        self.numberOfCycle = numberOfCycle
        self.baseDir = baseDir if baseDir else os.getcwd()
        
    def create_time_dirs(self, timeDirList):
        for i in range(len(timeDirList) - 1):
            timeDirPath = os.path.join(self.baseDir, "constant/boundaryData/inlet/", timeDirList[i])
            
            # Make the directory if it does not exist
            if not os.path.exists(timeDirPath):
                os.mkdir(timeDirPath)
                
            # Copy the U_* file to the directory and rename it to U
            srcFile = os.path.join(self.baseDir, "constant/boundaryData/inlet/BPM" + str(self.BPM) + "/U_" + timeDirList[i])
            destFile = os.path.join(timeDirPath, "U")
            os.system(f"cp {srcFile} {destFile}")
            # print("cope the U_", srcFile, "to", destFile)
            # Create symbolic links for extra cycles
            for j in range(1, self.numberOfCycle):
                newTimeDir = "{:.6f}".format(float(timeDirList[i]) + j * self.cardiacPeriod)
                target_dir = os.path.join(self.baseDir, "constant/boundaryData/inlet/", newTimeDir)
                # remove the directory if it exists
                os.system(f"rm -rf {target_dir}")           
                os.system(f"ln -s {timeDirPath} {target_dir}")     
                # print(f"The symbolic link directory {newTimeDir} is created!")
            
    def execute(self):
        if not os.path.exists(os.path.join(self.baseDir, "constant/boundaryData/inlet/BPM" + str(self.BPM) + "/")):
            print("There is no inlet velocity profile data for BPM = " + str(self.BPM))
            return

        timeDirList = []
        subFile = os.listdir(os.path.join(self.baseDir, "constant/boundaryData/inlet/BPM" + str(self.BPM) + "/"))
        subFile.sort()
        
        for i in range(len(subFile)):
            if subFile[i].startswith("U"):
                timeDirList.append(subFile[i].split("_")[1])

        self.create_time_dirs(timeDirList)

if __name__ == "__main__":
    inletProfile = CycleDataSetup(BPM=120, numberOfCycle=2)
    inletProfile.execute()
