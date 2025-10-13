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
    def __init__(self, casePath, caseType='Reconstructed', timeSteps=None, fields=None, rescaleSettings=None):
        """
        Initialize OpenFOAM ParaView post-processor.

        Args:
            casePath: Path to OpenFOAM case directory
            caseType: 'Reconstructed' or 'Decomposed' case type
            timeSteps: List of time steps to process. Options:
                      - None: Use all available time steps (default)
                      - [t1, t2, ...]: Specific time steps
                      - 'last': Only the last time step
                      - 'peak': Only peak systole (maximum velocity time)
            fields: List of fields to visualize ['U', 'p', 'wallShearStress']
            rescaleSettings: Dictionary of rescale settings per field
        """
        self.casePath  = casePath
        self.caseType  = caseType
        self.foamFile  = f"{casePath}/f.foam"

        # Place images directory at run level (one level up from openfoam/)
        # e.g., output/patient1/run_*/images/ instead of output/patient1/run_*/openfoam/Images/
        run_dir = os.path.dirname(os.path.abspath(casePath))
        self.imageDir  = os.path.join(run_dir, "images")

        self.timeSteps = timeSteps
        self.fields    = fields if fields else ["U", "p", "wallShearStress"]

        # check the images folder
        if not os.path.exists(self.imageDir):
            os.makedirs(self.imageDir, exist_ok=True)

        self.property_map = {
            "U": {
                "name": "U",
                "derived": False,
                "prefix": "Velocity",
                "component": ('POINTS', 'U', 'Magnitude'),
                "preset": "Rainbow Desaturated",
                "representation": "Volume",
                "unit": "m/s"
            },
            "p": {
                "name": "Pressure",
                "derived": True,
                "prefix": "Pressure",
                "component": ('POINTS', 'Pressure'),
                "preset": "Blue - Green - Orange",
                "representation": "Surface",
                "unit": "Pa"
            },
            "wallShearStress": {
                "name": "WSS",
                "derived": True,
                "prefix": "WSS",
                "component": ('POINTS', 'WSS'),
                "preset": "Viridis (matplotlib)",
                "representation": "Surface",
                "unit": "Pa"
            },
            "KE": {
                "name": "KE",
                "derived": True,
                "prefix": "KE",
                "component": ('POINTS', 'KE'),
                "preset": "Inferno (matplotlib)",
                "representation": "Volume",
                "unit": "Pa"
            }
        }

        default_ranges = {
            "U": [0, 1],
            "KE": [0, 100],
            "WSS": [0, 10],
            "Pressure": [0, 20]
        }
        self.rescaleSettings = rescaleSettings or {
            key: {"rescaleToData": False, "rescaleRange": val} for key, val in default_ranges.items()
        }

    def generate_screenshots(self):
        """
        Build the pipeline, do PCA-based camera orientation, generate
        new 'KE', 'WSS', and 'Pressure' fields, and save screenshots.

        Screenshots saved to: run_directory/images/
        """
        # Ensure the images directory exists
        if not os.path.exists(self.imageDir):
            os.makedirs(self.imageDir, exist_ok=True)
            print(f"[INFO] Created directory: {self.imageDir}\n")

        log_file = os.path.join(self.imageDir, "postProcessing.log")

        # 1) Create the OpenFOAM reader
        ffoam = OpenFOAMReader(FileName=self.foamFile)
        ffoam.CaseType = self.caseType + " Case"
        ffoam.MeshRegions = ['internalMesh']

        # 2) Create one RenderView
        renderView1 = CreateView('RenderView')
        renderView1.ViewSize = [1600, 900]

        # 3) Show the raw data first, so we can do camera PCA
        ffoamDisplay = Show(ffoam, renderView1)
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
            best_axis = eigenvectors[best_index]

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
        calculatorKE.ResultArrayName = 'KE'
        calculatorKE.Function = '0.5*1060*(U_X^2 + U_Y^2 + U_Z^2)'

        calculatorWSS = Calculator(Input=calculatorKE)
        calculatorWSS.ResultArrayName = 'WSS'
        calculatorWSS.Function = '1060*mag(wallShearStress)'

        calculatorP = Calculator(Input=calculatorWSS)
        calculatorP.ResultArrayName = 'Pressure'
        calculatorP.Function = 'p*1060/133.32'

        # 6) Create a single Display object for the final pipeline object
        finalDisplay = Show(calculatorP, renderView1)
        Hide(ffoam, renderView1)
        renderView1.Update()

        # 7) Construct new_properties dynamically based on fields
        new_properties = []
        for field in self.fields:
            if field in self.property_map:
                prop = self.property_map[field]
                rescale_setting = self.rescaleSettings.get(
                    field, {"rescaleToData": False, "rescaleRange": [0, 10]}
                )

                new_properties.append({
                    "name": prop["name"],
                    "component": prop["component"],
                    "preset": prop["preset"],
                    "representation": prop["representation"],
                    "filePrefix": prop["prefix"],
                    "unit": prop["unit"],
                    "rescaleToData": rescale_setting.get("rescaleToData", False),
                    "rescaleRange": rescale_setting.get("rescaleRange", [0, 1])
                })
        # We'll gather all array names for hideAllScalarBarsManually
        arrayList = [prop["name"] for prop in new_properties]

        # 8) Prepare time steps
        animationScene1 = GetAnimationScene()
        timeKeeper1 = GetTimeKeeper()

        # Get all available time steps from OpenFOAM case
        availableTimes = timeKeeper1.TimestepValues if timeKeeper1 else []

        if not self.timeSteps:
            # Default: use all available time steps
            if availableTimes:
                self.timeSteps = list(availableTimes)
                with open(log_file, "a") as log:
                    log.write(f"[INFO] Using all available time steps ({len(self.timeSteps)} total): {self.timeSteps[0]:.6f} to {self.timeSteps[-1]:.6f}\n")
            else:
                self.timeSteps = [0.0]
                with open(log_file, "a") as log:
                    log.write("[INFO] No available timesteps found. Using 0.0.\n")

        elif self.timeSteps == 'last':
            # Use only the last time step
            if availableTimes:
                self.timeSteps = [max(availableTimes)]
                with open(log_file, "a") as log:
                    log.write(f"[INFO] Using last time step only: {self.timeSteps[0]:.6f}\n")
            else:
                self.timeSteps = [0.0]
                with open(log_file, "a") as log:
                    log.write("[INFO] No available timesteps found. Using 0.0.\n")

        elif self.timeSteps == 'peak':
            # Use peak systole (time with maximum velocity)
            if availableTimes:
                max_vel = 0
                peak_time = availableTimes[0]
                for t in availableTimes:
                    animationScene1.AnimationTime = t
                    timeKeeper1.Time = t
                    renderView1.Update()
                    data = servermanager.Fetch(ffoam)
                    try:
                        if hasattr(data, 'GetPointData'):
                            u_array = data.GetPointData().GetArray('U')
                            if u_array:
                                u_data = vtk_to_numpy(u_array)
                                vel_mag = np.linalg.norm(u_data, axis=1).max()
                                if vel_mag > max_vel:
                                    max_vel = vel_mag
                                    peak_time = t
                    except Exception:
                        pass
                self.timeSteps = [peak_time]
                with open(log_file, "a") as log:
                    log.write(f"[INFO] Using peak systole time step: {peak_time:.6f} (max velocity: {max_vel:.4f} m/s)\n")
            else:
                self.timeSteps = [0.0]
                with open(log_file, "a") as log:
                    log.write("[INFO] No available timesteps found. Using 0.0.\n")

        elif isinstance(self.timeSteps, (list, tuple)):
            # User specified exact time steps
            with open(log_file, "a") as log:
                log.write(f"[INFO] Using user-specified time steps: {self.timeSteps}\n")

        else:
            # Invalid input - use last time step as fallback
            if availableTimes:
                self.timeSteps = [max(availableTimes)]
                with open(log_file, "a") as log:
                    log.write(f"[WARNING] Invalid timeSteps parameter. Using last time step: {self.timeSteps[0]:.6f}\n")
            else:
                self.timeSteps = [0.0]
                with open(log_file, "a") as log:
                    log.write("[INFO] No available timesteps found. Using 0.0.\n")

        # 9) Loop over time steps and new properties, saving screenshots
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
                pwf = GetOpacityTransferFunction(prop["name"])
                lut.ApplyPreset(prop["preset"], True)

                if prop["rescaleToData"]:
                    finalDisplay.RescaleTransferFunctionToDataRange(False, True)
                else:
                    lut.RescaleTransferFunction(*prop["rescaleRange"])
                    pwf.RescaleTransferFunction(*prop["rescaleRange"])

                # Show colorbar with units
                finalDisplay.SetScalarBarVisibility(renderView1, True)
                scalarBar = GetScalarBar(lut, renderView1)
                if scalarBar:
                    scalarBar.Title = f"{prop['name']} ({prop['unit']})"
                    scalarBar.TitleBold = 1
                    scalarBar.TitleFontSize = 20
                    scalarBar.LabelBold = 1
                    scalarBar.LabelFontSize = 20
                    scalarBar.AddRangeLabels = 0
                    scalarBar.Visibility = 1

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

    def anima(self, fps=30):
        log_file = os.path.join(self.imageDir, "postProcessing.log")

        with open(log_file, "a") as log:
            properties = [self.property_map[f]["prefix"] for f in self.fields if f in self.property_map]
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
                    continue

                images.sort(key=lambda x: float(x[0]))
                list_file = os.path.join(self.imageDir, f"{prop}_files.txt")
                with open(list_file, "w") as lf:
                    for _, filename in images:
                        lf.write(f"file '{filename}'\n")

                output_video = os.path.join(self.imageDir, f"{prop}.avi")
                ffmpeg_cmd = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-r", str(fps),
                    "-i", list_file, "-c:v", "mpeg4", "-q:v", "5", output_video
                ]

                try:
                    log.write(f"[INFO] Creating animation for '{prop}'...\n")
                    result = subprocess.run(ffmpeg_cmd, check=True, cwd=self.imageDir,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    log.write(f"[INFO] Animation for '{prop}' saved as '{output_video}'.\n")
                except subprocess.CalledProcessError as e:
                    log.write(f"[ERROR] ffmpeg failed for property '{prop}': {e.stderr}\n")
                finally:
                    if os.path.exists(list_file):
                        os.remove(list_file)

            log.write("[INFO] Animation creation completed.\n")


# Main execution block
if __name__ == "__main__":
    """
    Main execution when running with pvbatch.

    Usage:
        # All time steps (default) with animations
        pvbatch ../../../../src/aortacfd_lib/post_processor.py

        # All time steps explicitly
        pvbatch ../../../../src/aortacfd_lib/post_processor.py . all

        # Only last time step
        pvbatch ../../../../src/aortacfd_lib/post_processor.py . last

        # Only peak systole (max velocity)
        pvbatch ../../../../src/aortacfd_lib/post_processor.py . peak

        # Custom case path
        pvbatch post_processor.py /path/to/case last
    """
    import sys

    # Get case path from command line argument or environment variable
    if len(sys.argv) > 1:
        case_path = sys.argv[1]
    elif "CASE_PATH" in os.environ:
        case_path = os.environ["CASE_PATH"]
    else:
        # Use current directory
        case_path = os.getcwd()

    print(f"[INFO] OpenFOAM Post-Processing with ParaView")
    print(f"[INFO] Case path: {case_path}")

    # Check if case exists
    if not os.path.exists(case_path):
        print(f"[ERROR] Case directory not found: {case_path}")
        sys.exit(1)

    # Look for .foam file
    foam_files = [f for f in os.listdir(case_path) if f.endswith('.foam')]
    if not foam_files:
        print(f"[ERROR] No .foam file found in {case_path}")
        print("[INFO] Make sure meshing completed successfully")
        sys.exit(1)

    print(f"[INFO] Found {foam_files[0]}")

    # Parse command-line options for time step selection
    time_option = None
    if len(sys.argv) > 2:
        time_arg = sys.argv[2].lower()
        if time_arg == 'last':
            time_option = 'last'
            print("[INFO] Time step mode: Last time step only")
        elif time_arg == 'peak':
            time_option = 'peak'
            print("[INFO] Time step mode: Peak systole (maximum velocity)")
        elif time_arg == 'all':
            time_option = None
            print("[INFO] Time step mode: All available time steps")
        else:
            print(f"[WARNING] Unknown time option '{time_arg}'. Using default (all time steps)")

    # Initialize post-processor
    try:
        processor = OpenFOAMParaView(
            casePath=case_path,
            caseType='Reconstructed',
            timeSteps=time_option,  # None, 'last', or 'peak'
            fields=["U", "p", "wallShearStress"]  # All available fields
        )

        print("[INFO] Generating visualizations...")

        # Generate screenshots for specified time steps
        processor.generate_screenshots()

        print(f"[INFO] Screenshots saved to: {processor.imageDir}")
        print("[INFO] Post-processing completed successfully!")

        # Optionally create animations if multiple time steps and ffmpeg available
        if time_option is None:  # Only create animations for all time steps
            try:
                print("[INFO] Creating animations...")
                processor.anima(fps=30)
                print("[INFO] Animations created successfully!")
            except Exception as e:
                print(f"[WARNING] Could not create animations: {e}")
                print("[INFO] Install ffmpeg to enable animation generation")
        else:
            print("[INFO] Skipping animation (single time step mode)")

    except Exception as e:
        print(f"[ERROR] Post-processing failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
