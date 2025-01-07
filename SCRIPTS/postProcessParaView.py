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
    Automate ParaView-based visualization for an OpenFOAM case.
    """
    def __init__(self, casePath, caseType='Reconstructed', timeSteps=None, fields=None):
        """
        Args:
            casePath  (str): Path to the OpenFOAM case directory (contains f.foam).
            caseType  (str): 'ReconstructedCase' or 'DecomposedCase'.
            timeSteps (list): A list of times at which to save images, 
                              e.g. [0.0, 0.02, 0.04].
                              If None, uses just the last available timestep.
            fields    (list): List of fields to process (optional).
        """
        self.casePath  = casePath
        self.caseType  = caseType
        self.foamFile  = f"{casePath}/f.foam"
        self.imageDir  = f"{casePath}/Images"
        self.timeSteps = timeSteps
        self.fields    = fields if fields else ["U", "p", "wallShearStress"]

    def run(self):
        """
        Execute the ParaView pipeline and save screenshots for each time.
        Captures specified fields with appropriate visualization settings.
        """
        # Ensure the Images directory exists
        if not os.path.exists(self.imageDir):
            os.makedirs(self.imageDir)
            print(f"[INFO] Created directory: {self.imageDir}\n")

        # ---------------------------------------------------------------------
        # 1) Create the OpenFOAM reader
        ffoam = OpenFOAMReader(FileName=self.foamFile)
        ffoam.CaseType    = self.caseType + " Case"
        ffoam.MeshRegions = ['internalMesh']

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
            
            # Log the selected axis
            log_file = os.path.join(self.imageDir, "postProcessing.log")
            with open(log_file, "a") as log:
                log.write(f"[INFO] Selected principal axis index {best_index} with projected area {areas[best_index]}\n")

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
            camera_position = mean + 5 * radius * best_axis  # Using a multiplier of 5 as per user preference
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

            # Log the camera settings
            with open(log_file, "a") as log:
                log.write(f"[INFO] Camera set with position {renderView1.CameraPosition}, view up {renderView1.CameraViewUp}\n")

        except Exception as e:
            print(f"[WARNING] PCA-based camera adjustment failed: {e}")
            with open(log_file, "a") as log:
                log.write(f"[WARNING] PCA-based camera adjustment failed: {e}\n")
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

        # If no timeSteps provided, default to the last available time step
        if not self.timeSteps:
            availableTimes = timeKeeper1.TimestepValues if timeKeeper1 else []
            if availableTimes:
                self.timeSteps = [max(availableTimes)]
                print(f"[INFO] No time steps provided. Defaulting to last time step: {self.timeSteps}")
                with open(log_file, "a") as log:
                    log.write(f"[INFO] No time steps provided. Defaulting to last time step: {self.timeSteps}\n")
            else:
                self.timeSteps = [0.0]
                print(f"[INFO] No available timesteps found. Defaulting to 0.0.")
                with open(log_file, "a") as log:
                    log.write(f"[INFO] No available timesteps found. Defaulting to 0.0.\n")

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

                # h) Build the screenshot filename with trimmed decimals
                formatted_t = f"{t:.6f}".rstrip('0').rstrip('.')
                screenshotFile = f"{self.imageDir}/{prop['filePrefix']}_{formatted_t}.png"

                # i) Save screenshot
                SaveScreenshot(
                    screenshotFile,
                    renderView1,
                    ImageResolution=[1600, 900],
                    OverrideColorPalette='WhiteBackground',
                    TransparentBackground=0
                )
                # Log the saved screenshot
                with open(log_file, "a") as log:
                    log.write(f"[INFO] Saved screenshot: {screenshotFile}\n")
                print(f"[INFO] Saved screenshot: {screenshotFile}")

    def anima(self):
        """
        Create AVI animations for each property by stacking the corresponding PNG images.
        Requires ffmpeg to be installed and accessible in the system's PATH.
        """
        print("[INFO] Starting animation creation...")
        log_file = os.path.join(self.imageDir, "postProcessing.log")
        with open(log_file, "a") as log:
            properties = ["Velocity", "Pressure", "wallShearStress"]
            for prop in properties:
                # Collect all images for the property
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
                
                # Sort images by time_step
                images.sort(key=lambda x: x[0])
                
                # Generate a temporary list file for ffmpeg
                list_file = os.path.join(self.imageDir, f"{prop}_files.txt")
                with open(list_file, "w") as lf:
                    for _, filename in images:
                        lf.write(f"file '{filename}'\n")
                
                # Define output video file
                output_video = os.path.join(self.imageDir, f"{prop}.avi")
                
                # Build the ffmpeg command
                # -r is the frame rate
                # -f is the format
                # -i is the input list file
                # -c:v specifies the codec, here 'mpeg4' for AVI
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-y",  # Overwrite output file if it exists
                    "-f", "concat",
                    "-safe", "0",
                    "-r", "15",  # Frame rate
                    "-i", list_file,
                    "-c:v", "mpeg4",
                    "-q:v", "5",  # Quality (1-31, lower is better)
                    output_video
                ]
                
                try:
                    log.write(f"[INFO] Creating animation for '{prop}'...\n")
                    print(f"[INFO] Creating animation for '{prop}'...")
                    # Run the ffmpeg command
                    result = subprocess.run(ffmpeg_cmd, check=True, cwd=self.imageDir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    log.write(f"[INFO] Animation for '{prop}' saved as '{output_video}'.\n")
                    print(f"[INFO] Animation for '{prop}' saved as '{output_video}'.")
                except subprocess.CalledProcessError as e:
                    log.write(f"[ERROR] ffmpeg failed for property '{prop}': {e.stderr}\n")
                    print(f"[ERROR] ffmpeg failed for property '{prop}': {e.stderr}")
                finally:
                    # Remove the temporary list file
                    if os.path.exists(list_file):
                        os.remove(list_file)
        
            log.write("[INFO] Animation creation completed.\n")
            #print("[INFO] Animation creation completed.")


if __name__ == "__main__":
    case_type   = os.getenv("CASE_TYPE")
    case_path   = os.getenv("CASE_PATH")
    time_array  = os.getenv("TIME_ARRAY").split(",")
    time_array  = [float(x) for x in time_array]

    # Now pass them into your OpenFOAMParaView:
    pv_script = OpenFOAMParaView(
        casePath = case_path,
        caseType = case_type,
        timeSteps = time_array,
        fields = None
    )
    pv_script.run()
    pv_script.anima()
