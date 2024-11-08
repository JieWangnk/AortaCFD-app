from paraview.simple import *

class AortaAnalysis:
    def __init__(self, input_file, output_file, time_list):
        self.input_file = input_file
        self.output_file = output_file
        self.time_list = time_list
    
    def run_analysis(self):
        paraview.simple._DisableFirstRenderCameraReset()
        
        # create a new 'OpenFOAMReader'
        ffoam = OpenFOAMReader(registrationName='f.foam', FileName=self.input_file)
        ffoam.MeshRegions = ['internalMesh']
        #ffoam.CellArrays = ['R', 'U','nut', 'p', 'wallShearStress']

        # Properties modified on ffoam
        ffoam.CaseType = 'Decomposed Case'    #'Reconstructed Case'

	    # get animation scene
        animationScene1 = GetAnimationScene()

        # get the time-keeper
        timeKeeper1 = GetTimeKeeper()

        # update animation scene based on data timesteps
        animationScene1.UpdateAnimationUsingDataTimeSteps()

        # get active view
        renderView1 = GetActiveViewOrCreate('RenderView')

        # show data in view
        ffoamDisplay = Show(ffoam, renderView1, 'UnstructuredGridRepresentation')
        
        force_time_objects = [self.create_force_time(ffoam, time, renderView1) for time in self.time_list]
        
        programmableFilter1 = self.create_programmable_filter(force_time_objects)
        
        # hide data in view
        Hide(ffoam, renderView1)

        # show data in view
        programmableFilter1Display = Show(programmableFilter1, renderView1, 'UnstructuredGridRepresentation')

        # save data
        SaveData(self.output_file, proxy=programmableFilter1, PointDataArrays=['PAWSS', 'fluctuationWSSPrime2Mean'],
        CellDataArrays=['PAU', 'PAp', 'fluctuationUPrime2Mean', 'fluctuationUMeanPrime2Mean', 'PAUMean'],
        FieldDataArrays=['CasePath'])

        print("ProgrammableFilter is saved.")
        # ... rest of your code ...
    
    def create_force_time(self, ffoam, time,rederView):
        force_time = ForceTime(Input=ffoam)
        force_time.ForcedTime = time
        # show data in view
        force_timeDisplay = Show(force_time, rederView, 'UnstructuredGridRepresentation')
        return force_time
    
    def create_programmable_filter(self, force_time_objects):
        programmableFilter1 = ProgrammableFilter(registrationName='ProgrammableFilter1', Input=force_time_objects)
        programmableFilter1.Script = ''
        programmableFilter1.RequestInformationScript = ''
        programmableFilter1.RequestUpdateExtentScript = ''
        programmableFilter1.PythonPath = ''

        # Properties modified on programmableFilter1
        programmableFilter1.Script = """import numpy as np
n = len(inputs)

wss_avg = inputs[0].PointData["wallShearStress"]
p_avg = inputs[-1].CellData["p"]
U_avg = inputs[0].CellData["U"]
UMean_avg = inputs[0].CellData["UMean_w1"]

print("numberOfInput",n)

for i in range(1,n):
    wss_avg += inputs[i].PointData["wallShearStress"]
    U_avg += inputs[i].CellData["U"]
    UMean_avg += inputs[i].CellData["UMean_w1"]


wss_avg /= n
U_avg /= n
UMean_avg /= n

for i in range(n):
    fluctuation_temp = (inputs[i].CellData["U"] - U_avg)**2
    fluctuation = fluctuation_temp if i == 0 else fluctuation + fluctuation_temp
    wssfluctuation_temp = (inputs[i].PointData["wallShearStress"] - wss_avg)**2
    wssfluctuation = wssfluctuation_temp if i == 0 else wssfluctuation + wssfluctuation_temp
    fluctuationMean_temp = (inputs[i].CellData["UMean_w1"] - UMean_avg)**2
    fluctuationMean = fluctuationMean_temp if i == 0 else fluctuationMean + fluctuationMean_temp


fluctuation /= n
#fluctuation = math.sqrt(fluctuation)
wssfluctuation /= n
#wssfluctuation = math.sqrt(wssfluctuation)
fluctuationMean /= n

output.PointData.append(wss_avg, "PAWSS")
output.CellData.append(U_avg, "PAU")
output.CellData.append(p_avg, "PAp")
output.CellData.append(UMean_avg, "PAUMean")
output.PointData.append(wssfluctuation, "fluctuationWSSPrime2Mean")
output.CellData.append(fluctuation, "fluctuationUPrime2Mean")
output.CellData.append(fluctuationMean, "fluctuationUMeanPrime2Mean")"""
        programmableFilter1.RequestInformationScript = ''
        programmableFilter1.RequestUpdateExtentScript = ''
        programmableFilter1.PythonPath = ''
        return programmableFilter1

    def reset(self):
        for f in GetSources().values():
            if f.GetProperty("Input") is not None:
                Delete(f)
def generate_times(cardiac_cycle, bin_size, bin_index, end_cycle, start_cycle):
    bin_time = bin_size * bin_index
    times = [round(start_cycle * cardiac_cycle + bin_time + i * cardiac_cycle, 4) for i in range(end_cycle - start_cycle)]
    return times        
# Usage:
import os, sys
cardiac_cycle = 0.375 
bin_size = 0.0075
#bin_index = 8
end_cycle = 30
start_cycle = 5

# take argument for bin_index
if len(sys.argv) > 1:
    bin_index = int(sys.argv[1])
    print("bin_index is: ", bin_index)
else:
    print("Default bin index is 8")
    bin_index = 8
if len(sys.argv) > 2:
    end_cycle = int(sys.argv[2])
    print("end_cycle is: ", end_cycle)
else:
    print("Default end_cycle is 30tg")
    end_cycle = 30
if len(sys.argv) > 3:
    start_cycle = int(sys.argv[3])
    print("start_cycle is: ", start_cycle)
else:
    print("Default start_cycle is 5th")
    start_cycle = 5

time_list = generate_times(cardiac_cycle, bin_size, bin_index, end_cycle, start_cycle)
print("Phase avergae time series in: ", time_list)
file_path = os.getcwd()
input_file = os.path.join(file_path+"/f.foam")
distination = os.path.join(file_path+"/phaseAverageCycle"+str(start_cycle)+"ToCycle"+str(end_cycle)+"/")

output_file = distination+str(time_list[-1])+'.vtm'
analysis = AortaAnalysis(input_file, output_file, time_list)
analysis.run_analysis()
analysis.reset() 
