"""
A class to automate ParaView visualization for an OpenFOAM case.

This script:
1. Loads an OpenFOAM case (decomposed or reconstructed).
2. For each time step, captures three different fields:
    - Velocity (U)           -> volume rendering, 'Rainbow Desaturated'
    - Pressure (p)           -> volume rendering, 'Blue - Green - Orange'
    - wallShearStress (wss)  -> surface rendering, 'Viridis (matplotlib)'
3. Ensures that only ONE color legend is shown at a time by manually hiding all
   other scalar bars before displaying the new one.
"""
import os
import vtk
from vtk.util.numpy_support import vtk_to_numpy
import numpy as np
from scipy.spatial import ConvexHull

def get_all_points_from_multiblock(mb_dataset):
    """
    Recursively collect all points from a vtkMultiBlockDataSet.
    Returns a NumPy array of all points or None if no points found.
    """
    points_list = []
    for i in range(mb_dataset.GetNumberOfBlocks()):
        block = mb_dataset.GetBlock(i)
        if block is not None:
            # If the block itself is a MultiBlock, recurse
            if isinstance(block, vtk.vtkMultiBlockDataSet):
                pts = get_all_points_from_multiblock(block)
                if pts is not None:
                    points_list.append(pts)
            else:
                pts = block.GetPoints()
                if pts is not None:
                    numpy_pts = vtk_to_numpy(pts.GetData())
                    if numpy_pts.size > 0:
                        points_list.append(numpy_pts)
    if points_list:
        return np.concatenate(points_list, axis=0)
    else:
        return None

from paraview import servermanager

from paraview.simple import *
paraview.simple._DisableFirstRenderCameraReset()

def hideAllScalarBarsManually(renderView, arrayNames):
    """
    For each arrayName in arrayNames, get the color transfer function (LUT) and
    retrieve its scalar bar in the given renderView. Then set the visibility to 0.
    This effectively hides any previously visible legends for those arrays.
    """
    for arrayName in arrayNames:
        ctf = GetColorTransferFunction(arrayName)
        if ctf is not None:
            scalarBar = GetScalarBar(ctf, renderView)
            if scalarBar is not None:
                scalarBar.Visibility = 0

class OpenFOAMParaView:
    """
    Automate ParaView-based visualization for an OpenFOAM case.
    """
    def __init__(self, casePath, caseType='Reconstructed', timeSteps=None, fields=None):
        """
        Args:
            casePath  (str): Path to the OpenFOAM case directory (contains f.foam).
            caseType  (str): 'ReconstructedCase' or 'DecomposedCase'.
            timeSteps (list): A list of times at which to save images, 
                              e.g. [0.0, 0.02, 0.04].
                              If None, uses just the first available timestep.
        """
        self.casePath  = casePath
        self.caseType  = caseType
        self.foamFile  = f"{casePath}/f.foam"
        self.imageDir  = f"{casePath}/Images"
        self.timeSteps = timeSteps
        self.fields    = fields

    def run(self):
        """
        Execute the ParaView pipeline and save screenshots for each time.
        We capture three fields: Velocity (U), Pressure (p), and wallShearStress.
        """
        # Ensure the Images directory exists
        if not os.path.exists(self.imageDir):
            os.makedirs(self.imageDir)
            log.write(f"[INFO] Created directory: {self.imageDir}\n")

        # ---------------------------------------------------------------------
        # 1) Create the OpenFOAM reader
        ffoam = OpenFOAMReader(FileName=self.foamFile)
        ffoam.CaseType    = self.caseType + " Case"
        ffoam.MeshRegions = ['internalMesh']
        #ffoam.CellArrays  = ['U', 'nut', 'p', 'wallShearStress']

        # 2) Create one RenderView
        renderView1 = CreateView('RenderView')
        renderView1.ViewSize = [1600, 900]  # Adjust as needed

        # 3) Show data in the view
        ffoamDisplay = Show(ffoam, renderView1)
        ffoamDisplay.SetScalarBarVisibility(renderView1, False)

        # Update the view to ensure data is loaded
        renderView1.Update()

        try:
            # Fetch the complete dataset from the reader
            data = servermanager.Fetch(ffoam)

            # Attempt to extract points from multi-block datasets as before
            pts = None
            if hasattr(data, 'GetPoints') and data.GetPoints() is not None:
                pts = vtk_to_numpy(data.GetPoints().GetData())
            elif isinstance(data, vtk.vtkMultiBlockDataSet):
                pts = get_all_points_from_multiblock(data)
            
            if pts is None or len(pts) == 0:
                raise Exception("No points found in dataset.")

            # Calculate the mean and covariance of the points
            mean = np.mean(pts, axis=0)
            centered = pts - mean
            cov = np.cov(centered, rowvar=False)
            
            # Perform eigen decomposition (PCA)
            eigvals, eigvecs = np.linalg.eigh(cov)
            sorted_indices = np.argsort(eigvals)[::-1]  # descending order
            eigenvectors = [eigvecs[:, sorted_indices[i]] for i in range(3)]

            # Determine optimal viewing axis by maximizing projected area
            areas = []
            for i, vec in enumerate(eigenvectors):
                # Use the other two eigenvectors as the basis for plane projection
                other_indices = [j for j in range(3) if j != i]
                basis = np.column_stack([eigenvectors[j] for j in other_indices])
                projected_points = pts.dot(basis)
                try:
                    hull = ConvexHull(projected_points)
                    areas.append(hull.volume)  # in 2D, hull.volume gives the area
                except Exception as e:
                    areas.append(0)

            best_index = np.argmax(areas)
            best_axis = eigenvectors[best_index]
            log.write(f"[INFO] Selected principal axis index {best_index} with projected area {areas[best_index]}")

            # Get the bounding box to determine an appropriate distance (radius)
            info = ffoam.GetDataInformation()
            bounds = info.GetBounds()
            xmin, xmax, ymin, ymax, zmin, zmax = bounds
            dx = xmax - xmin
            dy = ymax - ymin
            dz = zmax - zmin
            radius = max(dx, dy, dz) / 2.0

            # Set camera properties using the best axis
            renderView1.CameraFocalPoint = mean.tolist()
            camera_position = mean +  5 * radius * best_axis
            renderView1.CameraPosition = camera_position.tolist()

            # Compute a view-up vector orthogonal to the chosen axis
            arbitrary = np.array([0, 1, 0])
            if np.allclose(best_axis, arbitrary) or np.allclose(best_axis, -arbitrary):
                arbitrary = np.array([1, 0, 0])
            view_up = np.cross(best_axis, arbitrary)
            norm = np.linalg.norm(view_up)
            if norm == 0:
                view_up = np.array([0, 0, 1])
            else:
                view_up = view_up / norm
            renderView1.CameraViewUp = view_up.tolist()

            renderView1.CameraParallelScale = radius

            log.write(f"[INFO] Camera set with position {renderView1.CameraPosition}, view up {renderView1.CameraViewUp}")

        except Exception as e:
            print(f"[WARNING] PCA-based camera adjustment failed: {e}")
            renderView1.ResetCamera()
            renderView1.CameraViewUp = [0.0, 0.0, 1.0]



        # 5) Define the properties of interest (arrays, color presets, etc.)
        properties = [
            {
                "arrayName": "U",
                "component": ('POINTS', 'U', 'Magnitude'),
                "preset": "Rainbow Desaturated",
                "representation": "Volume",
                "filePrefix": "Velocity",
                "rescale": True
            },
            {
                "arrayName": "p",
                "component": ('POINTS', 'p'),
                "preset": "Blue - Green - Orange",
                "representation": "Volume",
                "filePrefix": "Pressure",
                "rescale": True
            },
            {
                "arrayName": "wallShearStress",
                "component": ('POINTS', 'wallShearStress', 'Magnitude'),
                "preset": "Viridis (matplotlib)",
                "representation": "Surface",
                "filePrefix": "wallShearStress",
                "rescale": True
            }
        ]
        # We'll use the arrayName fields to hide bars
        arrayList = [p["arrayName"] for p in properties]

        # 6) Prepare to iterate over timesteps
        animationScene1 = GetAnimationScene()
        timeKeeper1     = GetTimeKeeper()

        # For each requested time
        for t in self.timeSteps:
            animationScene1.AnimationTime = t
            renderView1.Update()

            # For each property of interest
            for prop in properties:
                # a) Hide any previously shown scalar bars
                hideAllScalarBarsManually(renderView1, arrayList)

                # b) Color by the chosen array
                ColorBy(ffoamDisplay, prop["component"])

                # c) Rescale the color map if requested
                if prop["rescale"]:
                    ffoamDisplay.RescaleTransferFunctionToDataRange(True, False)

                # d) Set representation (volume or surface)
                ffoamDisplay.SetRepresentationType(prop["representation"])

                # e) Get the LUT and apply the color preset
                ctf = GetColorTransferFunction(prop["arrayName"])
                ctf.ApplyPreset(prop["preset"], True)

                # f) Show the scalar bar for the current LUT
                ffoamDisplay.SetScalarBarVisibility(renderView1, True)
                scalarBar = GetScalarBar(ctf, renderView1)
                if scalarBar is not None:
                    scalarBar.TitleBold      = 1
                    scalarBar.TitleFontSize  = 20
                    scalarBar.LabelBold      = 1
                    scalarBar.LabelFontSize  = 20
                    scalarBar.AddRangeLabels = 0
                    scalarBar.Visibility     = 1

                # g) Update the view
                renderView1.Update()

                # h) Build the screenshot filename
                screenshotFile = f"{self.imageDir}/{prop['filePrefix']}_{t:.6f}.png"

                # i) Save screenshot
                SaveScreenshot(
                    screenshotFile,
                    renderView1,
                    ImageResolution=[1600, 900],
                    OverrideColorPalette='WhiteBackground',
                    TransparentBackground=0
                )
                # log the saved screenshot into postProcessing.log
                log.write(f"[INFO] Saved screenshot: {screenshotFile}\n")


if __name__ == "__main__":
    case_type   = os.getenv("CASE_TYPE")
    case_path   = os.getenv("CASE_PATH")
    time_array  = os.getenv("TIME_ARRAY").split(",")
    time_array  = [float(x) for x in time_array]

    with open(f"{case_path}/Images/postProcessing.log", "w") as log:
        # Now pass them into your OpenFOAMParaView:
        pv_script = OpenFOAMParaView(
            casePath = case_path,
            caseType = case_type,
            timeSteps = time_array,
            fields = None
        )
        pv_script.run()

