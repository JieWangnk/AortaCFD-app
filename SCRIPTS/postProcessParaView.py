import os
import vtk
from vtk.util.numpy_support import vtk_to_numpy
import numpy as np
from scipy.spatial import ConvexHull
import re
import subprocess
from paraview import servermanager
from paraview.simple import *
paraview.simple._DisableFirstRenderCameraReset()

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
    Automate ParaView-based visualization for an OpenFOAM case,
    including KE (Pa), WSS (Pa), and Pressure (Pa) as calculated fields.
    """
    def __init__(self, casePath, caseType='Reconstructed', timeSteps=None, fields=None):
        """
        Args:
            casePath  (str): Path to the OpenFOAM case directory (contains f.foam).
            caseType  (str): 'ReconstructedCase' or 'DecomposedCase'.
            timeSteps (list): A list of times at which to save images, e.g. [0.0, 0.02].
                              If None, uses just the last available timestep.
            fields    (list): Additional fields to process. (We already handle KE, WSS, P.)
        """
        self.casePath  = casePath
        self.caseType  = caseType
        self.foamFile  = f"{casePath}/f.foam"
        self.imageDir  = f"{casePath}/Images"
        self.timeSteps = timeSteps
        # Default fields: keep your original logic if you want
        self.fields    = fields if fields else ["U", "p", "wallShearStress"]

    def run(self):
        """
        Build the pipeline, do PCA-based camera orientation, generate
        new 'KE (Pa)', 'WSS (Pa)', and 'Pressure (Pa)' fields, and save screenshots.
        """
        # Ensure the Images directory exists
        if not os.path.exists(self.imageDir):
            os.makedirs(self.imageDir)
            print(f"[INFO] Created directory: {self.imageDir}\n")

        log_file = os.path.join(self.imageDir, "postProcessing.log")

        # 1) Create the OpenFOAM reader
        ffoam = OpenFOAMReader(FileName=self.foamFile)
        ffoam.CaseType    = self.caseType + " Case"
        ffoam.MeshRegions = ['internalMesh']

        # 2) Create one RenderView
        renderView1 = CreateView('RenderView')
        renderView1.ViewSize = [1600, 900]

        # 3) Show the raw data first, so we can do camera PCA
        ffoamDisplay = Show(ffoam, renderView1)
        # annotateTimeFilter1 = AnnotateTimeFilter(registrationName='AnnotateTimeFilter1',Input=ffoam)
        # annotateTimeFilter1Display = Show(annotateTimeFilter1, renderView1, 'TextSourceRepresentation')
        # annotateTimeFilter1Display.WindowLocation = 'UpperCenter'  
        ffoamDisplay.SetScalarBarVisibility(renderView1, False)
        renderView1.Update()

        # 4) Attempt PCA for camera orientation
        try:
            data = servermanager.Fetch(ffoam)
            pts = None
            if hasattr(data, 'GetPoints') and data.GetPoints() is not None:
                pts = vtk_to_numpy(data.GetPoints().GetData())
            elif isinstance(data, vtk.vtkMultiBlockDataSet):
                pts = get_all_points_from_multiblock(data)

            if pts is None or len(pts) == 0:
                raise Exception("No points found in dataset for camera PCA.")

            mean = np.mean(pts, axis=0)
            centered = pts - mean
            cov = np.cov(centered, rowvar=False)
            eigvals, eigvecs = np.linalg.eigh(cov)
            sorted_indices = np.argsort(eigvals)[::-1]
            eigenvectors = [eigvecs[:, sorted_indices[i]] for i in range(3)]

            # Evaluate projected area in the plane perpendicular to each eigenvector
            areas = []
            for i, vec in enumerate(eigenvectors):
                other_indices = [j for j in range(3) if j != i]
                basis = np.column_stack([eigenvectors[j] for j in other_indices])
                projected_points = pts.dot(basis)
                try:
                    hull = ConvexHull(projected_points)
                    areas.append(hull.volume)  # 2D area
                except Exception:
                    areas.append(0)

            best_index = np.argmax(areas)
            best_axis  = eigenvectors[best_index]

            info = ffoam.GetDataInformation()
            bounds = info.GetBounds()
            xmin, xmax, ymin, ymax, zmin, zmax = bounds
            dx = xmax - xmin
            dy = ymax - ymin
            dz = zmax - zmin
            radius = max(dx, dy, dz) / 2.0

            renderView1.CameraFocalPoint = mean.tolist()
            camera_position = mean + 5 * radius * best_axis
            renderView1.CameraPosition = camera_position.tolist()

            # Compute a view-up vector
            arbitrary = np.array([0, 1, 0])
            if np.allclose(best_axis, arbitrary) or np.allclose(best_axis, -arbitrary):
                arbitrary = np.array([1, 0, 0])
            view_up = np.cross(best_axis, arbitrary)
            norm = np.linalg.norm(view_up)
            if norm == 0:
                view_up = np.array([0, 0, 1])
            else:
                view_up /= norm
            renderView1.CameraViewUp = view_up.tolist()
            renderView1.CameraParallelScale = radius

            with open(log_file, "a") as log:
                log.write(f"[INFO] PCA camera axis={best_index}, area={areas[best_index]}, position={renderView1.CameraPosition}, up={renderView1.CameraViewUp}\n")

        except Exception as e:
            print(f"[WARNING] PCA-based camera failed: {e}")
            with open(log_file, "a") as log:
                log.write(f"[WARNING] PCA-based camera failed: {e}\n")
            renderView1.ResetCamera()
            renderView1.CameraViewUp = [0.0, 0.0, 1.0]

        # ---------------------------------------------------------------------
        # 5) Create new Calculator filters for KE, WSS, Pressure:
        #    chain them so final pipeline is ffoam -> calcKE -> calcWSS -> calcP
        calculatorKE = Calculator(Input=ffoam)
        calculatorKE.ResultArrayName = 'KE (Pa)'
        # 0.5 * 1060 * (U_X^2 + U_Y^2 + U_Z^2) <--- note we need Z^2
        calculatorKE.Function = '0.5*1060*(U_X^2 + U_Y^2 + U_Z^2)'

        calculatorWSS = Calculator(Input=calculatorKE)
        calculatorWSS.ResultArrayName = 'WSS (Pa)'
        # 1060 * mag(wallShearStress)
        calculatorWSS.Function = '1060*mag(wallShearStress)'

        calculatorP = Calculator(Input=calculatorWSS)
        calculatorP.ResultArrayName = 'Pressure (Pa)'
        # p * 1060 / 133.32
        calculatorP.Function = 'p*1060/133.32'

        # 6) Create a single Display object for the final pipeline object
        #    (We will switch color arrays for KE, WSS, Pressure, etc.)
        finalDisplay = Show(calculatorP, renderView1)
        # Hide the original ffoam display to avoid overlap
        Hide(ffoam, renderView1)
        renderView1.Update()

        # We'll define a property dictionary for the newly calculated fields:
        # Similar structure to your old approach
        new_properties = [
            # ADD THIS BLOCK FOR VELOCITY:
            {
                "name": "U",                       #  <--- important
                "component": ('POINTS', 'U', 'Magnitude'),  
                "preset": "Rainbow Desaturated",   # or any preset you like
                "representation": "Volume",        # or "Surface"
                "filePrefix": "Velocity",          # how you want the .png named
                "rescaleToData": False,             # rescale to data range
                "rescaleRange": [0, 1]            # optional custom range
            },
            {
                "name": "KE (Pa)",
                "component": ('POINTS', 'KE (Pa)'),
                "preset": "Inferno (matplotlib)",
                "representation": "Volume",
                "filePrefix": "KE",
                "rescaleToData": False,
                "rescaleRange": [0, 1e2]
            },
            {
                "name": "WSS (Pa)",
                "component": ('POINTS', 'WSS (Pa)'),
                "preset": "Viridis (matplotlib)",
                "representation": "Surface",
                "filePrefix": "WSS",
                "rescaleToData": False,
                "rescaleRange": [0,10]
            },
            {
                "name": "Pressure (Pa)",
                "component": ('POINTS', 'Pressure (Pa)'),
                "preset": "Blue - Green - Orange",
                "representation": "Surface",
                "filePrefix": "Pressure",
                "rescaleToData": True,
                "rescaleRange": [0, 20]
            }
        ]

        # We also combine them with your old fields if desired...
        # But in this example, we'll only generate screenshots for new properties.
        # If you want to hide old fields or show them, you can adapt as needed.

        # We'll gather all array names for hideAllScalarBarsManually
        arrayList = [prop["name"] for prop in new_properties]

        # 7) Prepare time steps
        animationScene1 = GetAnimationScene()
        timeKeeper1     = GetTimeKeeper()
        if not self.timeSteps:
            availableTimes = timeKeeper1.TimestepValues if timeKeeper1 else []
            if availableTimes:
                self.timeSteps = [max(availableTimes)]
                with open(log_file, "a") as log:
                    log.write(f"[INFO] Defaulting to last time step: {self.timeSteps}\n")
            else:
                self.timeSteps = [0.0]
                with open(log_file, "a") as log:
                    log.write("[INFO] No available timesteps found. Using 0.0.\n")

        # 8) Loop over time steps and new properties, saving screenshots
        for t in self.timeSteps:
            animationScene1.AnimationTime = t
            timeKeeper1.Time = t
            renderView1.Update() 

            for prop in new_properties:
                # Hide previously shown scalar bars
                hideAllScalarBarsManually(renderView1, arrayList)

                # Color by the new field
                ColorBy(finalDisplay, prop["component"])
                finalDisplay.SetRepresentationType(prop["representation"])

                # Get the LUT
                lut = GetColorTransferFunction(prop["name"])
                # get PWF
                pwf = GetOpacityTransferFunction(prop["name"])
                # Optionally apply preset
                lut.ApplyPreset(prop["preset"], True)

                # Rescale data if needed
                if prop.get("rescaleToData", False):
                    finalDisplay.RescaleTransferFunctionToDataRange(False, True)
                else:
                    # rescale to custom range if needed
                    lut.RescaleTransferFunction(*prop.get("rescaleRange", [0, 1]))
                    pwf.RescaleTransferFunction(*prop.get("rescaleRange", [0, 1]))                    

                # Show colorbar
                finalDisplay.SetScalarBarVisibility(renderView1, True)
                scalarBar = GetScalarBar(lut, renderView1)
                if scalarBar:
                    scalarBar.TitleBold      = 1
                    scalarBar.TitleFontSize  = 20
                    scalarBar.LabelBold      = 1
                    scalarBar.LabelFontSize  = 20
                    scalarBar.AddRangeLabels = 0
                    scalarBar.Visibility     = 1

                # Update
                renderView1.Update()

                # Build filename
                formatted_t = f"{t:.6f}".rstrip('0').rstrip('.')
                screenshotFile = f"{self.imageDir}/{prop['filePrefix']}_{formatted_t}.png"
                SaveScreenshot(
                    screenshotFile,
                    renderView1,
                    ImageResolution=[1600, 900],
                    OverrideColorPalette='WhiteBackground',
                    TransparentBackground=0
                )

                with open(log_file, "a") as log:
                    log.write(f"[INFO] Saved screenshot for {prop['name']} at t={t}: {screenshotFile}\n")

    def anima(self):
        """
        Create AVI animations for each property by stacking the corresponding PNG images.
        Requires ffmpeg to be installed and accessible in the system PATH.
        """
        print("[INFO] Starting animation creation...")
        log_file = os.path.join(self.imageDir, "postProcessing.log")
        with open(log_file, "a") as log:
            # We want animations for the new property prefixes: "KE", "WSS", "Pressure"
            # plus any old ones you used before, e.g. "Velocity", "Pressure", "wallShearStress"
            properties = ["KE", "WSS", "Pressure","Velocity"]  # feel free to add "Velocity", etc.

            for prop in properties:
                pattern = re.compile(rf"{re.escape(prop)}_(\d+\.?\d*)\.png")
                images = []
                for filename in os.listdir(self.imageDir):
                    match = pattern.match(filename)
                    if match:
                        time_step = float(match.group(1))
                        images.append((time_step, filename))
                
                if not images:
                    log.write(f"[WARNING] No images found for property '{prop}'. Skipping animation.\n")
                    print(f"[WARNING] No images found for property '{prop}'. Skipping animation.")
                    continue
                
                # Sort by numeric time
                images.sort(key=lambda x: float(x[0]))

                # Generate a temporary list file for ffmpeg
                list_file = os.path.join(self.imageDir, f"{prop}_files.txt")
                with open(list_file, "w") as lf:
                    for _, filename in images:
                        lf.write(f"file '{filename}'\n")
                
                output_video = os.path.join(self.imageDir, f"{prop}.avi")
                
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-r", "15",  # frame rate
                    "-i", list_file,
                    "-c:v", "mpeg4",
                    "-q:v", "5",
                    output_video
                ]
                
                try:
                    log.write(f"[INFO] Creating animation for '{prop}'...\n")
                    print(f"[INFO] Creating animation for '{prop}'...")
                    result = subprocess.run(ffmpeg_cmd, check=True, cwd=self.imageDir,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    log.write(f"[INFO] Animation for '{prop}' saved as '{output_video}'.\n")
                    print(f"[INFO] Animation for '{prop}' saved as '{output_video}'.")
                except subprocess.CalledProcessError as e:
                    log.write(f"[ERROR] ffmpeg failed for property '{prop}': {e.stderr}\n")
                    print(f"[ERROR] ffmpeg failed for property '{prop}': {e.stderr}")
                finally:
                    if os.path.exists(list_file):
                        os.remove(list_file)

            log.write("[INFO] Animation creation completed.\n")
            print("[INFO] Animation creation completed.")


# ------------------- MAIN for pvbatch usage ----------------------
if __name__ == "__main__":
    case_type   = os.getenv("CASE_TYPE")
    case_path   = os.getenv("CASE_PATH")
    time_array  = os.getenv("TIME_ARRAY").split(",")
    time_array  = [float(x) for x in time_array]
    print(f"[INFO] Received case type: {case_type}")
    print(f"[INFO] Received case path: {case_path}")
    print(f"[INFO] Received time array: {time_array}")

    pv_script = OpenFOAMParaView(
        casePath  = str(case_path),
        caseType  = str(case_type),
        timeSteps = time_array
    )
    pv_script.run()
    pv_script.anima()
