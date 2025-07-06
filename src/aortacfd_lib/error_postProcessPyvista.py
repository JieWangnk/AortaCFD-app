import os
import sys
import numpy as np
from scipy.spatial import ConvexHull
import re
import subprocess
import json
from .utils.logger import Logger
import pyvista as pv

# --- Helper: Map ParaView Presets to Matplotlib/PyVista CMaps ---
# This is a basic mapping, more can be added or customized.
# PyVista can also use ParaView's XML colormaps directly if available.
# from pyvista.plotting.colors import paraview_cmap_translator # May need specific PyVista version
paraview_to_matplotlib_cmap = {
    "Rainbow Desaturated": "nipy_spectral", # nipy_spectral is often a good alternative
    "Blue - Green - Orange": "RdYlGn", # Example, might need custom
    "Viridis (matplotlib)": "viridis",
    "Inferno (matplotlib)": "inferno",
    "Cool Warm": "coolwarm",
    "erdc_rainbow_bright": "rainbow" # Generic rainbow
    # Add more mappings as needed
}

class OpenFOAMPyVista:
    def __init__(self, casePath, caseType='Reconstructed', timeSteps=None, fields=None, rescaleSettings=None):
        self.casePath = casePath
        self.caseType = caseType  # Note: PyVista's POpenFOAMReader doesn't directly use 'Reconstructed Case' string like ParaView.
                                  # It infers from the directory structure.
        self.foamFile = os.path.join(casePath, "system", "controlDict") # POpenFOAMReader typically points to controlDict or the case dir
        # Alternative: self.foamFile = os.path.join(casePath, f"{os.path.basename(casePath)}.foam") # if you create a .foam file
        # For robust reading, pointing to the case directory itself is often best:
        self.foamFile = casePath

        self.imageDir = os.path.join(casePath, "Images_PyVista") # Separate directory for PyVista output
        if not os.path.exists(self.imageDir):
            os.makedirs(self.imageDir)

        self.timeSteps = timeSteps
        self.requested_fields_config = fields if fields else ["U", "p", "wallShearStress"] # Config keys

        # Define properties for visualization.
        # 'pv_array_name' is the original field name in OpenFOAM files.
        # 'derived_name' is the name after calculation (e.g., magnitude, scaled value).
        # 'representation_style': 'surface', 'points', or 'volume'.
        self.property_map = {
            "U": {
                "name": "Velocity", "pv_array_name": "U", "derived_name": "U_Magnitude",
                "cmap_pv_preset": "Rainbow Desaturated", "representation_style": "volume", "unit": "m/s"
            },
            "p": {
                "name": "Pressure", "pv_array_name": "p", "derived_name": "Pressure_Custom",
                "cmap_pv_preset": "Blue - Green - Orange", "representation_style": "surface", "unit": "mmHg" # Original was Pa, but formula converted
            },
            "wallShearStress": {
                "name": "WSS", "pv_array_name": "wallShearStress", "derived_name": "WSS_Scaled",
                "cmap_pv_preset": "Viridis (matplotlib)", "representation_style": "surface", "unit": "Pa"
            },
            "KE": {
                "name": "KE", "pv_array_name": "U", "derived_name": "KineticEnergy", # Derived from U
                "cmap_pv_preset": "Inferno (matplotlib)", "representation_style": "volume", "unit": "J/kg (Specific KE)" # p = 1060 kg/m3
            }
        }

        default_ranges = { # These are for derived names
            "U_Magnitude": [0, 1.5],
            "KineticEnergy": [0, 1.0], # Adjust based on expected values
            "WSS_Scaled": [0, 10],
            "Pressure_Custom": [0, 160] # mmHg typical aorta systolic range
        }
        self.rescaleSettings = rescaleSettings or {
            key: {"rescaleToData": False, "rescaleRange": val} for key, val in default_ranges.items()
        }
        self.log_file_path = os.path.join(self.imageDir, "postProcessing_pyvista.log")
        self.logger = Logger(self.log_file_path).get_logger()

    def _setup_camera_pca(self, plotter, mesh_for_pca):
        """Sets up the camera based on PCA of the mesh points."""
        self.logger.info("Starting PCA for camera orientation.")
        if mesh_for_pca is None or mesh_for_pca.n_points == 0:
            self.logger.warning("No points found in mesh for PCA. Using default camera reset.")
            plotter.reset_camera()
            plotter.camera.viewup = [0.0, 0.0, 1.0] # Common Z-up
            return

        pts = mesh_for_pca.points
        try:
            mean = np.mean(pts, axis=0)
            centered = pts - mean
            cov = np.cov(centered, rowvar=False)
            eigvals, eigvecs = np.linalg.eigh(cov)
            sorted_indices = np.argsort(eigvals)[::-1]
            principal_axes = eigvecs[:, sorted_indices] # Each column is an eigenvector

            # Determine best viewing axis by projecting points and finding max area
            # This is a simplified approach; more robust methods might be needed for complex shapes.
            # For now, we'll pick the axis corresponding to the smallest variance (view along it)
            # or largest variance (view perpendicular to it). Let's try viewing along minor axis.
            # view_direction = principal_axes[:, 2] # Axis of least variance
            
            # Original script's logic for best_axis based on projected area
            areas = []
            for i in range(3):
                vec = principal_axes[:, i]
                other_indices = [j for j in range(3) if j != i]
                basis_vectors = principal_axes[:, other_indices]
                projected_points = centered @ basis_vectors # Project centered points
                try:
                    if projected_points.shape[0] < 3: # ConvexHull needs at least dim+1 points
                        areas.append(0)
                        continue
                    hull = ConvexHull(projected_points)
                    areas.append(hull.volume) # 'volume' for 2D area in this context
                except Exception as e_hull:
                    self.logger.warning(f"ConvexHull failed for axis {i}: {e_hull}")
                    areas.append(0)
            
            if not any(a > 0 for a in areas): # if all areas are zero
                 self.logger.warning("PCA projected areas are all zero. Defaulting camera.")
                 best_axis_idx = 0 # Default to first principal axis
            else:
                best_axis_idx = np.argmax(areas)

            view_direction = principal_axes[:, best_axis_idx]

            bounds = mesh_for_pca.bounds
            diag_length = mesh_for_pca.length # Diagonal length of bounding box
            radius = diag_length / 2.0

            plotter.camera.focal_point = mean.tolist()
            # Position camera along the view_direction, scaled by model size
            camera_position = mean + 2.5 * diag_length * (view_direction / np.linalg.norm(view_direction))
            plotter.camera.position = camera_position.tolist()

            # Compute a view-up vector
            # Try to align view_up with global Z, unless view_direction is too close to Z
            global_up = np.array([0, 0, 1.0])
            if np.abs(np.dot(view_direction, global_up)) > 0.95: # If view_direction is (anti)parallel to Z
                global_up = np.array([0, 1.0, 0]) # Use Y instead

            view_right = np.cross(view_direction, global_up)
            view_up = np.cross(view_right, view_direction)
            plotter.camera.viewup = (view_up / np.linalg.norm(view_up)).tolist()
            
            plotter.camera.parallel_scale = radius * 0.7 # Adjust for better framing
            plotter.enable_parallel_projection()
            self.logger.info(f"PCA camera setup: FocalPoint={plotter.camera.focal_point}, Position={plotter.camera.position}, ViewUp={plotter.camera.viewup}")

        except Exception as e:
            self.logger.error(f"PCA-based camera setup failed: {e}. Using default camera reset.")
            plotter.reset_camera()
            plotter.camera.viewup = [0.0, 0.0, 1.0]


    def _calculate_derived_fields(self, mesh, field_configs):
        """Calculates derived fields and adds them to the mesh."""
        if mesh is None:
            self.logger.warning("Mesh is None, skipping derived field calculations.")
            return mesh

        # Ensure U is present for KE and U_Magnitude calculation
        if 'U' in mesh.point_data:
            U_vec = mesh.point_data['U']
            mesh.point_data['U_Magnitude'] = np.linalg.norm(U_vec, axis=1)
            # Specific Kinetic Energy J/kg = 0.5 * V^2. If total KE, multiply by mass.
            # Assuming density 1060 kg/m^3, KE per unit volume = 0.5 * rho * V^2
            mesh.point_data['KineticEnergy'] = 0.5 * 1060.0 * (U_vec[:,0]**2 + U_vec[:,1]**2 + U_vec[:,2]**2)
            self.logger.debug("Calculated U_Magnitude and KineticEnergy.")
        else:
            if any(fc['pv_array_name'] == 'U' for fc in field_configs.values()):
                 self.logger.warning("Original field 'U' not found in mesh point data. Cannot calculate U_Magnitude or KE.")


        if 'wallShearStress' in mesh.point_data:
            # Assuming wallShearStress from OpenFOAM is already a scalar magnitude (Pa)
            # If it's a vector, take np.linalg.norm(mesh.point_data['wallShearStress'], axis=1)
            mesh.point_data['WSS_Scaled'] = 1060.0 * mesh.point_data['wallShearStress'] # Original script did 1060*mag(wallShearStress)
                                                                                        # If WSS is already mag(wallShearStress), then it's 1060 * WSS_OpenFOAM
            self.logger.debug("Calculated WSS_Scaled.")
        else:
            if any(fc['pv_array_name'] == 'wallShearStress' for fc in field_configs.values()):
                self.logger.warning("Original field 'wallShearStress' not found. Cannot calculate WSS_Scaled.")

        if 'p' in mesh.point_data:
            # Convert pressure (assuming Pa from OpenFOAM) to mmHg
            # Original: p * 1060 / 133.32. This seems like p_rho / conversion_factor
            # If 'p' in OpenFOAM is kinematic pressure (p/rho), then p_dynamic = p_kinematic * rho
            # Then convert Pa to mmHg: 1 Pa = 0.00750062 mmHg
            # So, p_mmHg = (p_kinematic * 1060) * 0.00750062
            # The factor 133.32 is 1/0.00750062, so p_mmHg = (p_kinematic*1060) / 133.32 seems correct
            mesh.point_data['Pressure_Custom'] = (mesh.point_data['p'] * 1060.0) / 133.322
            self.logger.debug("Calculated Pressure_Custom (mmHg).")
        else:
            if any(fc['pv_array_name'] == 'p' for fc in field_configs.values()):
                self.logger.warning("Original field 'p' not found. Cannot calculate Pressure_Custom.")
        return mesh


    def generate_screenshots(self):
        self.logger.info(f"Starting PyVista post-processing for case: {self.casePath}")
        if not os.path.exists(self.imageDir):
            os.makedirs(self.imageDir)
            self.logger.info(f"Created image directory: {self.imageDir}")

        try:
            reader = pv.POpenFOAMReader(self.foamFile)
            reader.decompose_polyhedra = True # Important for visualizing OpenFOAM meshes correctly
            reader.patch_array_names = [prop['pv_array_name'] for prop in self.property_map.values() if 'pv_array_name' in prop]
            
            available_times = reader.time_values
            self.logger.info(f"Available time steps from reader: {available_times}")

            if not self.timeSteps: # If no specific time steps provided, use the last one
                if available_times:
                    self.timeSteps = [available_times[-1]]
                    self.logger.info(f"No specific time steps provided. Defaulting to last available time: {self.timeSteps[0]}")
                else:
                    self.logger.error("No time steps specified and no time steps found by POpenFOAMReader.")
                    return
            else: # Filter to use only available times
                valid_times = [t for t in self.timeSteps if t in available_times]
                if not valid_times:
                    self.logger.error(f"Specified time steps {self.timeSteps} not found in available times {available_times}.")
                    return
                self.timeSteps = valid_times
                self.logger.info(f"Processing specified and available time steps: {self.timeSteps}")


            plotter = pv.Plotter(off_screen=True, window_size=[1920, 1080]) # Higher resolution
            plotter.background_color = 'white'
            plotter.lighting = 'light_kit' # Adds multiple lights for better illumination

            # Setup camera using PCA based on the first time step's mesh
            if available_times:
                reader.set_active_time_value(available_times[0])
                multi_block_mesh_for_pca = reader.read()
                # Combine all blocks into a single UnstructuredGrid for PCA
                # This assumes 'internalMesh' is the primary domain.
                # If specific blocks are needed, adjust accordingly.
                if 'internalMesh' in multi_block_mesh_for_pca:
                    mesh_for_pca = multi_block_mesh_for_pca['internalMesh']
                elif multi_block_mesh_for_pca.n_blocks > 0:
                     mesh_for_pca = multi_block_mesh_for_pca.combine(merge_points=True, tolerance=1e-05) # Combine all blocks
                else:
                    mesh_for_pca = None
                
                if mesh_for_pca and mesh_for_pca.n_points > 0 :
                    self._setup_camera_pca(plotter, mesh_for_pca)
                else:
                    self.logger.warning("Could not obtain a valid mesh for PCA camera setup. Using default camera.")
                    plotter.reset_camera()
            else:
                self.logger.warning("No available time steps to set up PCA camera. Using default camera.")
                plotter.reset_camera()


            for t_idx, t in enumerate(self.timeSteps):
                self.logger.info(f"Processing time step: {t} ({t_idx+1}/{len(self.timeSteps)})")
                reader.set_active_time_value(t)
                multi_block_mesh_at_t = reader.read()

                # Primarily work with internalMesh or combine all
                if 'internalMesh' in multi_block_mesh_at_t:
                    current_mesh = multi_block_mesh_at_t['internalMesh'].copy() # Work on a copy
                elif multi_block_mesh_at_t.n_blocks > 0:
                    current_mesh = multi_block_mesh_at_t.combine(merge_points=True, tolerance=1e-05)
                else:
                    self.logger.warning(f"No data in 'internalMesh' or other blocks for time {t}. Skipping.")
                    continue
                
                if not current_mesh or current_mesh.n_points == 0:
                    self.logger.warning(f"Mesh for time {t} is empty or invalid. Skipping.")
                    continue

                current_mesh = self._calculate_derived_fields(current_mesh, self.property_map)

                for field_key in self.requested_fields_config:
                    if field_key not in self.property_map:
                        self.logger.warning(f"Configuration for field '{field_key}' not found in property_map. Skipping.")
                        continue
                    
                    prop_config = self.property_map[field_key]
                    scalar_to_plot = prop_config["derived_name"]

                    if scalar_to_plot not in current_mesh.point_data and scalar_to_plot not in current_mesh.cell_data:
                        self.logger.warning(f"Scalar '{scalar_to_plot}' for field '{prop_config['name']}' not found in mesh at time {t}. Skipping.")
                        continue
                    
                    self.logger.info(f"  Plotting field: {prop_config['name']} (scalar: {scalar_to_plot})")
                    plotter.clear_actors() # Clear previous mesh and scalar bar

                    cmap = paraview_to_matplotlib_cmap.get(prop_config["cmap_pv_preset"], "viridis")
                    
                    rescale_info = self.rescaleSettings.get(scalar_to_plot, {"rescaleToData": True})
                    clim = None
                    if not rescale_info.get("rescaleToData", True) and "rescaleRange" in rescale_info:
                        clim = rescale_info["rescaleRange"]

                    scalar_bar_title = f"{prop_config['name']} ({prop_config['unit']})"
                    sargs = dict(
                        title=scalar_bar_title,
                        title_font_size=20, # Adjusted for better readability
                        label_font_size=18, # Adjusted
                        n_labels=5,
                        italic=False,
                        bold=True,
                        shadow=True,
                        font_family='arial', # Ensure this font is available
                        vertical=True,
                        position_x=0.85, # Adjust position to avoid overlap
                        position_y=0.1,
                        width=0.1,
                        height=0.8
                    )
                    
                    representation_style = prop_config["representation_style"]
                    opacity_val = 1.0 # Default opacity

                    if representation_style == "volume":
                        # PyVista's add_volume works best with ImageData, but can try with UnstructuredGrid
                        # Let's add some opacity mapping for visual effect if it's not true volume rendering
                        if scalar_to_plot in ["U_Magnitude", "KineticEnergy"]: # Fields originally as volume
                             opacity_val = "linear_ramped" # Example opacity map for volume-like feel
                        
                        # Check if data is on cell or points for volume rendering
                        # add_volume usually expects point data for UnstructuredGrid
                        data_location = 'point_data' if scalar_to_plot in current_mesh.point_data else 'cell_data'
                        
                        if data_location == 'cell_data': # add_volume might not work well with cell data on UnstructuredGrid
                            self.logger.warning(f"Field '{scalar_to_plot}' is cell data. Volume rendering might not be optimal. Attempting surface instead for {prop_config['name']}.")
                            plotter.add_mesh(current_mesh, scalars=scalar_to_plot, cmap=cmap, clim=clim,
                                         scalar_bar_args=sargs, style='surface', show_edges=False, preference=data_location)
                        else:
                            # For actual volume rendering, mapper can be specified. Default often works.
                            # E.g. mapper='smart', mapper='gpu', mapper='fixed_point_gpu'
                            # Using opacity on add_mesh for a volume *effect* if true volume fails or is too slow
                            try:
                                plotter.add_volume(current_mesh, scalars=scalar_to_plot, cmap=cmap, clim=clim,
                                               scalar_bar_args=sargs, opacity=opacity_val, shade=True,
                                               preference=data_location) # shade=True for better depth perception
                            except Exception as e_vol:
                                self.logger.warning(f"True volume rendering for {scalar_to_plot} failed ({e_vol}). Falling back to surface with opacity.")
                                plotter.add_mesh(current_mesh, scalars=scalar_to_plot, cmap=cmap, clim=clim,
                                         scalar_bar_args=sargs, style='surface', show_edges=False, opacity=0.7, preference=data_location)


                    elif representation_style == "surface":
                        data_location = 'point_data' if scalar_to_plot in current_mesh.point_data else 'cell_data'
                        plotter.add_mesh(current_mesh, scalars=scalar_to_plot, cmap=cmap, clim=clim,
                                         scalar_bar_args=sargs, style='surface', show_edges=False, preference=data_location)
                    else: # points or other
                        data_location = 'point_data' if scalar_to_plot in current_mesh.point_data else 'cell_data'
                        plotter.add_mesh(current_mesh, scalars=scalar_to_plot, cmap=cmap, clim=clim,
                                         scalar_bar_args=sargs, style=representation_style, preference=data_location)


                    formatted_t = f"{t:.6f}".rstrip('0').rstrip('.')
                    # Use derived_name or a custom prefix for filenames to match original style
                    file_prefix = prop_config.get("prefix", prop_config["derived_name"].replace("_", "")) # Fallback prefix
                    
                    screenshotFile = os.path.join(self.imageDir, f"{file_prefix}_{formatted_t}.png")
                    plotter.screenshot(screenshotFile)
                    self.logger.info(f"    Saved screenshot: {screenshotFile}")

            plotter.close()
            self.logger.info("Screenshot generation completed.")

        except Exception as e:
            self.logger.error(f"Error during PyVista screenshot generation: {e}", exc_info=True)
        finally:
            # Remove file handler from logger if it was added
            for handler in self.logger.handlers:
                if isinstance(handler, logging.FileHandler) and handler.baseFilename == self.log_file_path:
                    handler.close()
                    self.logger.removeHandler(handler)


    def anima(self, fps=30):
        """Creates animations from screenshots using ffmpeg."""
        self.logger.info(f"Starting animation creation in: {self.imageDir}")
        
        # Determine unique prefixes from the property_map based on requested_fields_config
        processed_prefixes = set()
        for field_key in self.requested_fields_config:
            if field_key in self.property_map:
                prop_conf = self.property_map[field_key]
                prefix = prop_conf.get("prefix", prop_conf["derived_name"].replace("_", ""))
                processed_prefixes.add(prefix)

        for prefix in processed_prefixes:
            self.logger.info(f"  Creating animation for prefix: {prefix}")
            # Regex to match screenshot files for this prefix and time
            # Example: Velocity_0.1.png, Velocity_0.2.png
            pattern = re.compile(rf"{re.escape(prefix)}_(\d+\.?\d*)\.png")
            images = []
            for filename in sorted(os.listdir(self.imageDir)): # Sort to ensure chronological order
                match = pattern.match(filename)
                if match:
                    try:
                        time_val_str = match.group(1)
                        time_val = float(time_val_str)
                        images.append((time_val, filename))
                    except ValueError:
                        self.logger.warning(f"Could not parse time from filename: {filename}")

            if not images:
                self.logger.warning(f"  No images found for prefix '{prefix}'. Skipping animation.")
                continue

            # Sort images by time_val, already done by sorted(os.listdir()) if filenames are zero-padded
            # but explicit sort by parsed time is more robust.
            images.sort(key=lambda x: x[0])

            list_file_path = os.path.join(self.imageDir, f"{prefix}_files.txt")
            with open(list_file_path, "w") as lf:
                for _, filename in images:
                    lf.write(f"file '{filename}'\n")
            
            output_video = os.path.join(self.imageDir, f"{prefix}_animation.mp4") # Using mp4 for better compatibility
            # Using libx264 for mp4, mpeg4 for avi
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-r", str(fps), "-f", "concat", "-safe", "0",
                "-i", list_file_path, "-c:v", "libx264", "-preset", "medium",
                "-pix_fmt", "yuv420p", "-crf", "23", output_video
            ]
            # Alternative for AVI (like original script):
            # ffmpeg_cmd = [
            #     "ffmpeg", "-y", "-r", str(fps), "-f", "concat", "-safe", "0",
            #     "-i", list_file_path, "-c:v", "mpeg4", "-q:v", "5", output_video.replace(".mp4", ".avi")
            # ]

            try:
                self.logger.info(f"  Running ffmpeg for '{prefix}': {' '.join(ffmpeg_cmd)}")
                result = subprocess.run(ffmpeg_cmd, cwd=self.imageDir, check=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.logger.info(f"  Animation for '{prefix}' saved as '{output_video}'. STDOUT: {result.stdout}")
                if result.stderr:
                    self.logger.info(f"  FFMPEG STDERR: {result.stderr}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"  ffmpeg failed for prefix '{prefix}': {e.stderr}")
            except FileNotFoundError:
                self.logger.error("ffmpeg command not found. Please ensure ffmpeg is installed and in your system's PATH.")
            finally:
                if os.path.exists(list_file_path):
                    os.remove(list_file_path)

        self.logger.info("Animation creation process completed.")

# ------------------- MAIN for script usage ----------------------
if __name__ == "__main__":
    # --- Get parameters from environment variables (or define defaults) ---
    case_path = os.getenv("CASE_PATH", "/home/jie/AortaCFD-app/OPENFOAM/PAT1_2024_coarse/") # Default to current directory if not set
    case_type = os.getenv("CASE_TYPE", "Reconstructed") # PyVista reader usually auto-detects
    
    time_array_str = os.getenv("TIME_ARRAY", "1.2e-06, 2.64e-06") # e.g. "0.1,0.2,0.3" or "" for last
    time_array = []
    if time_array_str:
        try:
            time_array = [float(x.strip()) for x in time_array_str.split(",")]
        except ValueError:
            sys.exit(1)

    rescale_settings_str = os.getenv("RESCALE_SETTINGS", "{}")
    try:
        rescale_settings = json.loads(rescale_settings_str)
    except json.JSONDecodeError:
        rescale_settings = {}

    fields_str = os.getenv("FIELDS", "U,p,wallShearStress,KE") # Default fields to process
    fields_config = [f.strip() for f in fields_str.split(",")]

    animation_enabled = os.getenv("ANIMATION_ENABLED", "True").lower() == "true"
    fps = int(os.getenv("FPS", "24")) # Default fps
    re_animation_only = os.getenv("REANIMATION_ONLY", "False").lower() == "true"

    # --- Validate CASE_PATH ---
    if not os.path.isdir(case_path) or not os.path.exists(os.path.join(case_path, "system", "controlDict")):
        # For PyVista, it's often enough if the case directory itself is valid and contains time step folders.
        # However, controlDict is a good check.
        if not os.path.isdir(os.path.join(case_path, "0")) and \
           not any(f.replace('.', '', 1).isdigit() for f in os.listdir(case_path) if os.path.isdir(os.path.join(case_path, f))): # check for time dirs
             sys.exit(1)

    pv_script = OpenFOAMPyVista(
        casePath=str(case_path),
        caseType=str(case_type),
        timeSteps=time_array,
        fields=fields_config,
        rescaleSettings=rescale_settings
    )
    
    if re_animation_only:
        if animation_enabled:
            pv_script.anima(fps=fps)
    else:
        pv_script.generate_screenshots()
        if animation_enabled:
            pv_script.anima(fps=fps)
       