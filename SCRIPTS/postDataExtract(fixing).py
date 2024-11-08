#!/home/jie/Downloads/ParaView-5.11.0-MPI-Linux-Python3.9-x86_64/bin/pvpython
# load paraview modules
from paraview.simple import *

class DataProcessor:
    def __init__(self, file_name, csv_file_path, save_data_path,time):
        self.file_name = file_name
        self.csv_file_path = csv_file_path
        self.save_data_path = save_data_path
        self.time = time
        paraview.simple._DisableFirstRenderCameraReset()

    def process_data(self):
        # Create a new 'XML MultiBlock Data Reader'
        data_reader = XMLMultiBlockDataReader(
            registrationName='DataReader', FileName=[self.file_name]
        )
        data_reader.CellArrayStatus = ['U', 'p']
        data_reader.PointArrayStatus = ['U', 'p']

        # Get animation scene and update it based on data time steps
        animation_scene = GetAnimationScene()
        animation_scene.UpdateAnimationUsingDataTimeSteps()
        # Get active view
        render_view = GetActiveViewOrCreate('RenderView')
        # Show data in view
        data_reader_display = Show(data_reader, render_view, 'UnstructuredGridRepresentation')
        UpdatePipeline()

        # Create a new 'Programmable Source'
        programmable_source = self.create_programmable_source()
        UpdatePipeline()

        # set active source
        SetActiveSource(data_reader)
        # Create a new 'Resample With Dataset'
        resample_with_dataset = ResampleWithDataset(
            registrationName='ResampleWithDataset',
            SourceDataArrays=data_reader,
            DestinationMesh=programmable_source
        )
        resample_with_dataset.CellLocator = 'Static Cell Locator'
        UpdatePipeline()

        # Show data in view
        programmable_source_display = Show(
            resample_with_dataset, render_view, 'UnstructuredGridRepresentation'
        )
        UpdatePipeline()

        # Save data
        SaveData(
            f'{self.save_data_path}/{self.time}.csv',
            proxy=resample_with_dataset,
            PointDataArrays=[
                'U','p'
            ]
        )

        # Clean up
        #for obj in [resample_with_dataset, programmable_source, data_reader]:
        #    Delete(obj)
        #    del obj

        # Update animation scene based on data time steps
        animation_scene.UpdateAnimationUsingDataTimeSteps()

    def create_programmable_source(self):
        programmable_source = ProgrammableSource(
            registrationName='ProgrammableSource'
        )
        programmable_source.OutputDataSetType = 'vtkUnstructuredGrid'
        programmable_source.Script = f"""
import numpy as np
from vtk.numpy_interface import dataset_adapter as dsa
from vtk.numpy_interface import algorithms as algs
import vtk

# Read centerPathLine.csv file
file_path = '{self.csv_file_path}'
center_Path_Line = np.genfromtxt(file_path, dtype=None, names=True, delimiter=',', autostrip=True)
# convert the 3 arrays into a single 3 component array for
# use as the coordinates for the points.
coordinates = algs.make_vector(center_Path_Line["pos_x"], center_Path_Line["pos_y"], center_Path_Line["pos_z"])
# create a vtkPoints container to store all the
# point coordinates.
pts = vtk.vtkPoints()
# numpyTovtkDataArray is needed to called directly to convert the NumPy
# to a vtkDataArray which vtkPoints::SetData() expects.
pts.SetData(dsa.numpyTovtkDataArray(coordinates, name="Points"))
# set the pts on the output.
output.SetPoints(pts)
numPts = pts.GetNumberOfPoints()
# ptIds is the list of point ids in this cell
# (which is all the points)
ptIds = vtk.vtkIdList()
ptIds.SetNumberOfIds(numPts)
for i in range(numPts):
    ptIds.SetId(i, i)
# Allocate space for 1 cell.
output.Allocate(1)
# Add the cell to the mesh
output.InsertNextCell(vtk.vtkPolyVertex().GetCellType(), ptIds)
for name in center_Path_Line.dtype.names:
    array = center_Path_Line[name]
    output.PointData.append(array, name)
        """
        return programmable_source

# Usage:
processor = DataProcessor(
        file_name='/home/jie/aorta/multifidelity/betaBlocker_cleanCut/BPM_hifi/120BPM/phaseAverage10cycles/14.59.vtm',
        csv_file_path='/home/jie/aorta/cardio-app_old/CAD/centerPathLine.csv',
        save_data_path='/home/jie/aorta/multifidelity/betaBlocker_cleanCut/BPM_hifi/120BPM/data/PAcenterLineData/',
        time= "0.09"
)
processor.process_data()
