"""
OpenFOAM ParaView Post-Processor

This module provides automated visualization of OpenFOAM CFD results using ParaView.
It generates screenshots and animations for velocity, pressure, WSS, and hemodynamic
metrics (TAWSS, OSI, RRT).

Usage:
    # Run with pvbatch
    pvbatch post_processor.py /path/to/case last

    # Python API
    from aortacfd_lib.post_processor import OpenFOAMParaView
    processor = OpenFOAMParaView(case_path, fields=['U', 'TAWSS'])
    processor.generate_screenshots()
"""

from __future__ import annotations

import glob
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import vtk
from scipy.spatial import ConvexHull
from vtk.util.numpy_support import vtk_to_numpy

from paraview import servermanager
from paraview.simple import (
    Calculator,
    ColorBy,
    CreateView,
    GetAnimationScene,
    GetColorTransferFunction,
    GetOpacityTransferFunction,
    GetScalarBar,
    GetTimeKeeper,
    Hide,
    OpenFOAMReader,
    SaveScreenshot,
    Show,
)

import paraview.simple

paraview.simple._DisableFirstRenderCameraReset()


# =============================================================================
# CONSTANTS
# =============================================================================

BLOOD_DENSITY: float = 1060.0  # kg/m³
PA_TO_MMHG: float = 1.0 / 133.322  # Conversion factor

# Default property map for visualization fields
DEFAULT_PROPERTY_MAP: Dict[str, Dict[str, Any]] = {
    "U": {
        "name": "U",
        "derived": False,
        "prefix": "Velocity",
        "component": ("POINTS", "U", "Magnitude"),
        "preset": "Rainbow Desaturated",
        "representation": "Volume",
        "unit": "m/s",
    },
    "p": {
        "name": "Pressure",
        "derived": True,
        "prefix": "Pressure",
        "component": ("POINTS", "Pressure"),
        "preset": "Blue - Green - Orange",
        "representation": "Surface",
        "unit": "mmHg",
    },
    "wallShearStress": {
        "name": "WSS",
        "derived": True,
        "prefix": "WSS",
        "component": ("POINTS", "WSS"),
        "preset": "Viridis (matplotlib)",
        "representation": "Surface",
        "unit": "Pa",
    },
    "TAWSS": {
        "name": "TAWSS",
        "derived": False,
        "prefix": "TAWSS",
        "component": ("POINTS", "TAWSS"),
        "preset": "Viridis (matplotlib)",
        "representation": "Surface",
        "unit": "Pa",
    },
    "OSI": {
        "name": "OSI",
        "derived": False,
        "prefix": "OSI",
        "component": ("POINTS", "OSI"),
        "preset": "Cool to Warm",
        "representation": "Surface",
        "unit": "",
    },
    "RRT": {
        "name": "RRT",
        "derived": False,
        "prefix": "RRT",
        "component": ("POINTS", "RRT"),
        "preset": "Plasma (matplotlib)",
        "representation": "Surface",
        "unit": "1/Pa",
    },
    "KE": {
        "name": "KE",
        "derived": True,
        "prefix": "KE",
        "component": ("POINTS", "KE"),
        "preset": "Inferno (matplotlib)",
        "representation": "Volume",
        "unit": "Pa",
    },
}

# Default color ranges for each field
DEFAULT_COLOR_RANGES: Dict[str, List[float]] = {
    "U": [0, 1],
    "KE": [0, 100],
    "WSS": [0, 50],
    "TAWSS": [0, 50],
    "OSI": [0, 0.5],
    "RRT": [0, 10],
    "Pressure": [0, 20],
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_all_points_from_multiblock(mb_dataset: vtk.vtkMultiBlockDataSet) -> Optional[np.ndarray]:
    """
    Recursively collect all points from a vtkMultiBlockDataSet.

    Args:
        mb_dataset: VTK multi-block dataset to extract points from

    Returns:
        NumPy array of all points (N x 3), or None if no points found
    """
    points_list = []
    for i in range(mb_dataset.GetNumberOfBlocks()):
        block = mb_dataset.GetBlock(i)
        if block is not None:
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
    return None


def hide_all_scalar_bars(render_view: Any, array_names: List[str]) -> None:
    """
    Hide all scalar bars for the specified arrays in the render view.

    Args:
        render_view: ParaView render view object
        array_names: List of array names whose scalar bars should be hidden
    """
    for array_name in array_names:
        ctf = GetColorTransferFunction(array_name)
        if ctf is not None:
            scalar_bar = GetScalarBar(ctf, render_view)
            if scalar_bar is not None:
                scalar_bar.Visibility = 0


def check_ffmpeg_available() -> bool:
    """
    Check if ffmpeg is available for animation generation.

    Returns:
        True if ffmpeg is available, False otherwise
    """
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# =============================================================================
# MAIN CLASS
# =============================================================================


class OpenFOAMParaView:
    """
    OpenFOAM ParaView post-processor for generating CFD visualizations.

    This class handles automated visualization of OpenFOAM simulation results,
    including velocity fields, pressure, wall shear stress, and derived
    hemodynamic metrics (TAWSS, OSI, RRT).

    Attributes:
        case_path: Path to OpenFOAM case directory
        case_type: 'Reconstructed' or 'Decomposed'
        image_dir: Directory for saving screenshots and animations
        fields: List of fields to visualize
        time_steps: Time steps to process
        property_map: Mapping of field names to visualization properties
        rescale_settings: Color range settings per field

    Example:
        >>> processor = OpenFOAMParaView(
        ...     case_path="/path/to/case",
        ...     fields=['U', 'TAWSS', 'OSI'],
        ...     time_steps='last'
        ... )
        >>> processor.generate_screenshots()
    """

    def __init__(
        self,
        case_path: Union[str, Path],
        case_type: str = "auto",
        time_steps: Optional[Union[str, List[float]]] = None,
        fields: Optional[List[str]] = None,
        rescale_settings: Optional[Dict[str, Dict[str, Any]]] = None,
        resolution: Tuple[int, int] = (1600, 900),
    ) -> None:
        """
        Initialize OpenFOAM ParaView post-processor.

        Args:
            case_path: Path to OpenFOAM case directory
            case_type: Case type - 'Reconstructed', 'Decomposed', or 'auto'
            time_steps: Time selection:
                - None: All available time steps (default)
                - 'last': Only the last time step
                - 'peak': Peak systole (maximum velocity)
                - List[float]: Specific time values
            fields: Fields to visualize. Default: ['U', 'p', 'wallShearStress']
            rescale_settings: Per-field color range settings
            resolution: Output image resolution (width, height)

        Raises:
            FileNotFoundError: If case_path doesn't exist
            ValueError: If invalid case_type specified
        """
        self.case_path = str(case_path)
        self.resolution = resolution

        # Setup logging
        self._setup_logging()

        # Validate case path
        if not os.path.exists(self.case_path):
            raise FileNotFoundError(f"Case directory not found: {self.case_path}")

        # Auto-detect case type
        if case_type == "auto":
            self.case_type = self._detect_case_type()
            self.logger.info(f"Auto-detected case type: {self.case_type}")
        elif case_type in ("Reconstructed", "Decomposed"):
            self.case_type = case_type
        else:
            raise ValueError(f"Invalid case_type: {case_type}. Use 'auto', 'Reconstructed', or 'Decomposed'")

        self.foam_file = os.path.join(self.case_path, "f.foam")

        # Place images directory at run level
        run_dir = os.path.dirname(os.path.abspath(self.case_path))
        self.image_dir = os.path.join(run_dir, "images")
        os.makedirs(self.image_dir, exist_ok=True)

        self.time_steps = time_steps
        self.fields = fields if fields else ["U", "p", "wallShearStress"]

        # Initialize property map (can be extended via config)
        self.property_map = DEFAULT_PROPERTY_MAP.copy()

        # Initialize rescale settings
        self.rescale_settings = self._build_rescale_settings(rescale_settings)

        # ParaView pipeline objects (set during generate_screenshots)
        self._render_view = None
        self._foam_reader = None
        self._final_display = None

    def _setup_logging(self) -> None:
        """Configure logging for post-processing."""
        self.logger = logging.getLogger("AortaCFD.PostProcessor")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _build_rescale_settings(
        self, custom_settings: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build rescale settings from defaults and custom overrides.

        Args:
            custom_settings: User-provided rescale settings

        Returns:
            Complete rescale settings dictionary
        """
        # Start with defaults: WSS/TAWSS/OSI/RRT use fixed ranges, others auto-scale
        settings = {
            "U": {"rescaleToData": True, "rescaleRange": DEFAULT_COLOR_RANGES["U"]},
            "KE": {"rescaleToData": True, "rescaleRange": DEFAULT_COLOR_RANGES["KE"]},
            "WSS": {"rescaleToData": False, "rescaleRange": DEFAULT_COLOR_RANGES["WSS"]},
            "TAWSS": {"rescaleToData": False, "rescaleRange": DEFAULT_COLOR_RANGES["TAWSS"]},
            "OSI": {"rescaleToData": False, "rescaleRange": DEFAULT_COLOR_RANGES["OSI"]},
            "RRT": {"rescaleToData": False, "rescaleRange": DEFAULT_COLOR_RANGES["RRT"]},
            "Pressure": {"rescaleToData": True, "rescaleRange": DEFAULT_COLOR_RANGES["Pressure"]},
        }

        if custom_settings:
            settings.update(custom_settings)

        return settings

    def _detect_case_type(self) -> str:
        """
        Auto-detect whether the case is Reconstructed or Decomposed.

        Returns:
            'Reconstructed' if time directories exist in case root,
            'Decomposed' if only processor directories exist
        """
        processor_dirs = glob.glob(os.path.join(self.case_path, "processor*"))
        has_processors = len(processor_dirs) > 0

        time_dirs = []
        for item in os.listdir(self.case_path):
            item_path = os.path.join(self.case_path, item)
            if os.path.isdir(item_path):
                try:
                    float(item)
                    if item != "0":
                        time_dirs.append(item)
                except ValueError:
                    pass

        has_time_dirs = len(time_dirs) > 0

        if has_time_dirs:
            return "Reconstructed"
        elif has_processors:
            return "Decomposed"
        else:
            return "Reconstructed"

    def _setup_render_view(self) -> Tuple[Any, Any, Any]:
        """
        Create OpenFOAM reader and render view.

        Returns:
            Tuple of (foam_reader, render_view, initial_display)
        """
        self.logger.info("Setting up ParaView render view...")

        foam_reader = OpenFOAMReader(FileName=self.foam_file)
        foam_reader.CaseType = self.case_type + " Case"
        foam_reader.MeshRegions = ["internalMesh"]
        # Interpolate cell fields to points so the Point-Data Calculator can
        # reference U/p/wallShearStress. This was ON by default in ParaView 5.x
        # but OFF in 6.x, where the reader otherwise exposes only cell arrays and
        # every Calculator expression fails with "Undefined symbol". Setting it
        # explicitly is a no-op on 5.x and the fix on 6.x.
        if hasattr(foam_reader, "Createcelltopointfiltereddata"):
            foam_reader.Createcelltopointfiltereddata = 1

        render_view = CreateView("RenderView")
        render_view.ViewSize = list(self.resolution)

        foam_display = Show(foam_reader, render_view)
        foam_display.SetScalarBarVisibility(render_view, False)
        render_view.Update()

        return foam_reader, render_view, foam_display

    def _configure_camera_pca(self, foam_reader: Any, render_view: Any) -> None:
        """
        Configure camera using PCA-based orientation for optimal viewing angle.

        Uses Principal Component Analysis to find the viewing direction that
        shows the maximum projected area of the geometry.

        Args:
            foam_reader: OpenFOAM reader object
            render_view: ParaView render view
        """
        self.logger.info("Configuring camera orientation (PCA-based)...")

        try:
            data = servermanager.Fetch(foam_reader)
            pts = None

            if hasattr(data, "GetPoints") and data.GetPoints() is not None:
                pts = vtk_to_numpy(data.GetPoints().GetData())
            elif isinstance(data, vtk.vtkMultiBlockDataSet):
                pts = get_all_points_from_multiblock(data)

            if pts is None or len(pts) == 0:
                raise ValueError("No points found in dataset for camera PCA")

            # Compute PCA
            mean = np.mean(pts, axis=0)
            centered = pts - mean
            cov = np.cov(centered, rowvar=False)
            eigvals, eigvecs = np.linalg.eigh(cov)
            sorted_indices = np.argsort(eigvals)[::-1]
            eigenvectors = [eigvecs[:, sorted_indices[i]] for i in range(3)]

            # Find axis with maximum projected area
            areas = []
            for i, vec in enumerate(eigenvectors):
                other_indices = [j for j in range(3) if j != i]
                basis = np.column_stack([eigenvectors[j] for j in other_indices])
                projected_points = pts.dot(basis)
                try:
                    hull = ConvexHull(projected_points)
                    areas.append(hull.volume)
                except Exception:
                    areas.append(0)

            best_index = np.argmax(areas)
            best_axis = eigenvectors[best_index]

            # Compute camera distance
            info = foam_reader.GetDataInformation()
            bounds = info.GetBounds()
            xmin, xmax, ymin, ymax, zmin, zmax = bounds
            radius = max(xmax - xmin, ymax - ymin, zmax - zmin) / 2.0

            # Set camera position
            render_view.CameraFocalPoint = mean.tolist()
            camera_position = mean + 5 * radius * best_axis
            render_view.CameraPosition = camera_position.tolist()

            # Compute view-up vector
            arbitrary = np.array([0, 1, 0])
            if np.allclose(best_axis, arbitrary) or np.allclose(best_axis, -arbitrary):
                arbitrary = np.array([1, 0, 0])
            view_up = np.cross(best_axis, arbitrary)
            norm = np.linalg.norm(view_up)
            if norm > 0:
                view_up /= norm
            else:
                view_up = np.array([0, 0, 1])

            render_view.CameraViewUp = view_up.tolist()
            render_view.CameraParallelScale = radius

            self.logger.info(f"PCA camera: axis={best_index}, area={areas[best_index]:.2f}")

        except Exception as e:
            self.logger.warning(f"PCA camera failed: {e}. Using default camera.")
            render_view.ResetCamera()
            render_view.CameraViewUp = [0.0, 0.0, 1.0]

    def _create_calculator_pipeline(self, source: Any) -> Any:
        """
        Create chained Calculator filters for derived fields.

        Creates calculators for:
        - KE: Kinetic energy (0.5 * rho * |U|^2)
        - WSS: Wall shear stress magnitude (rho * |tau_w|)
        - TAWSS: Time-averaged WSS from fieldAverage
        - Pressure: Converted to mmHg

        Args:
            source: Input source (OpenFOAM reader)

        Returns:
            Final calculator in the pipeline chain
        """
        self.logger.info("Creating calculator pipeline for derived fields...")

        # KE = 0.5 * rho * |U|^2
        calc_ke = Calculator(Input=source)
        calc_ke.ResultArrayName = "KE"
        calc_ke.Function = f"0.5*{BLOOD_DENSITY}*(U_X^2 + U_Y^2 + U_Z^2)"

        # WSS = rho * |wallShearStress|
        calc_wss = Calculator(Input=calc_ke)
        calc_wss.ResultArrayName = "WSS"
        calc_wss.Function = f"{BLOOD_DENSITY}*mag(wallShearStress)"

        # TAWSS from wallShearStressMean
        calc_tawss = Calculator(Input=calc_wss)
        calc_tawss.ResultArrayName = "TAWSS"
        calc_tawss.Function = f"{BLOOD_DENSITY}*mag(wallShearStressMean)"

        # Pressure in mmHg
        calc_p = Calculator(Input=calc_tawss)
        calc_p.ResultArrayName = "Pressure"
        calc_p.Function = f"p*{BLOOD_DENSITY}/{1/PA_TO_MMHG:.2f}"

        return calc_p

    def _build_property_list(self) -> List[Dict[str, Any]]:
        """
        Build visualization properties list from fields and rescale settings.

        Returns:
            List of property dictionaries for visualization
        """
        properties = []
        for field in self.fields:
            if field in self.property_map:
                prop = self.property_map[field]
                rescale = self.rescale_settings.get(prop["name"], {"rescaleToData": True, "rescaleRange": [0, 1]})
                properties.append(
                    {
                        "name": prop["name"],
                        "component": prop["component"],
                        "preset": prop["preset"],
                        "representation": prop["representation"],
                        "filePrefix": prop["prefix"],
                        "unit": prop["unit"],
                        "rescaleToData": rescale.get("rescaleToData", True),
                        "rescaleRange": rescale.get("rescaleRange", [0, 1]),
                    }
                )
        return properties

    def _prepare_time_steps(self, available_times: List[float], foam_reader: Any, render_view: Any) -> List[float]:
        """
        Resolve time step selection to actual time values.

        Args:
            available_times: List of available time steps from case
            foam_reader: OpenFOAM reader for peak velocity detection
            render_view: Render view for updates

        Returns:
            List of resolved time steps to process
        """
        if not self.time_steps:
            # Default: all available times
            if available_times:
                self.logger.info(f"Using all {len(available_times)} time steps")
                return list(available_times)
            else:
                self.logger.info("No time steps found, using 0.0")
                return [0.0]

        elif self.time_steps == "last":
            if available_times:
                last_time = max(available_times)
                self.logger.info(f"Using last time step: {last_time:.6f}")
                return [last_time]
            return [0.0]

        elif self.time_steps == "peak":
            return self._find_peak_systole(available_times, foam_reader, render_view)

        elif isinstance(self.time_steps, (list, tuple)):
            self.logger.info(f"Using user-specified time steps: {self.time_steps}")
            return list(self.time_steps)

        else:
            self.logger.warning(f"Invalid time_steps: {self.time_steps}. Using last.")
            if available_times:
                return [max(available_times)]
            return [0.0]

    def _find_peak_systole(self, available_times: List[float], foam_reader: Any, render_view: Any) -> List[float]:
        """
        Find the time step with maximum velocity (peak systole).

        Args:
            available_times: List of available time steps
            foam_reader: OpenFOAM reader
            render_view: Render view

        Returns:
            List containing single peak systole time step
        """
        if not available_times:
            return [0.0]

        self.logger.info("Finding peak systole (maximum velocity)...")

        animation_scene = GetAnimationScene()
        time_keeper = GetTimeKeeper()

        max_vel = 0
        peak_time = available_times[0]

        for t in available_times:
            animation_scene.AnimationTime = t
            time_keeper.Time = t
            render_view.Update()

            try:
                data = servermanager.Fetch(foam_reader)
                if hasattr(data, "GetPointData"):
                    u_array = data.GetPointData().GetArray("U")
                    if u_array:
                        u_data = vtk_to_numpy(u_array)
                        vel_mag = np.linalg.norm(u_data, axis=1).max()
                        if vel_mag > max_vel:
                            max_vel = vel_mag
                            peak_time = t
            except Exception:
                pass

        self.logger.info(f"Peak systole at t={peak_time:.6f} (max velocity: {max_vel:.4f} m/s)")
        return [peak_time]

    def _render_and_save(
        self, render_view: Any, display: Any, properties: List[Dict[str, Any]], time_steps: List[float]
    ) -> None:
        """
        Render and save screenshots for all time steps and properties.

        Args:
            render_view: ParaView render view
            display: Display object for the final pipeline
            properties: List of visualization properties
            time_steps: List of time steps to render
        """
        animation_scene = GetAnimationScene()
        time_keeper = GetTimeKeeper()
        array_list = [prop["name"] for prop in properties]

        total_screenshots = len(time_steps) * len(properties)
        self.logger.info(f"Rendering {total_screenshots} screenshots...")

        for t in time_steps:
            animation_scene.AnimationTime = t
            time_keeper.Time = t
            render_view.Update()

            for prop in properties:
                # Hide previous scalar bars
                hide_all_scalar_bars(render_view, array_list)

                # Color by field
                ColorBy(display, prop["component"])
                display.SetRepresentationType(prop["representation"])

                # Configure color transfer function
                lut = GetColorTransferFunction(prop["name"])
                pwf = GetOpacityTransferFunction(prop["name"])
                lut.ApplyPreset(self._resolve_preset(prop["preset"]), True)

                render_view.Update()

                # Apply rescale settings
                if prop["rescaleToData"]:
                    display.RescaleTransferFunctionToDataRange(False, True)
                else:
                    lut.RescaleTransferFunction(*prop["rescaleRange"])
                    pwf.RescaleTransferFunction(*prop["rescaleRange"])

                # Configure scalar bar
                self._configure_scalar_bar(render_view, display, lut, prop)

                render_view.Update()

                # Save screenshot
                formatted_t = f"{t:.6f}".rstrip("0").rstrip(".")
                screenshot_file = os.path.join(self.image_dir, f"{prop['filePrefix']}_{formatted_t}.png")
                SaveScreenshot(
                    screenshot_file,
                    render_view,
                    ImageResolution=list(self.resolution),
                    OverrideColorPalette="WhiteBackground",
                    TransparentBackground=0,
                )

                self.logger.debug(f"Saved: {screenshot_file}")

    def _configure_scalar_bar(self, render_view: Any, display: Any, lut: Any, prop: Dict[str, Any]) -> None:
        """
        Configure the scalar bar (color legend) appearance.

        Args:
            render_view: ParaView render view
            display: Display object
            lut: Color lookup table
            prop: Property dictionary with name and unit
        """
        display.SetScalarBarVisibility(render_view, True)
        scalar_bar = GetScalarBar(lut, render_view)

        if scalar_bar:
            scalar_bar.WindowLocation = "Any Location"
            scalar_bar.Position = [0.02, 0.25]
            scalar_bar.ScalarBarLength = 0.5
            scalar_bar.ScalarBarThickness = 16
            scalar_bar.Orientation = "Vertical"

            unit_str = f" ({prop['unit']})" if prop["unit"] else ""
            scalar_bar.Title = f"{prop['name']}{unit_str}"
            scalar_bar.TitleBold = 1
            scalar_bar.TitleFontSize = 16
            scalar_bar.LabelBold = 1
            scalar_bar.LabelFontSize = 14
            scalar_bar.AddRangeLabels = 1
            scalar_bar.RangeLabelFormat = "%.2f"
            scalar_bar.Visibility = 1

    def _resolve_preset(self, name: str) -> str:
        """Map a colormap preset name to one available in the running ParaView.

        ParaView 6.x dropped the " (matplotlib)" suffix from the Viridis/Plasma/
        Inferno/Magma/Cividis presets, and ``ApplyPreset`` raises on an unknown
        name. Resolve against the actual preset list so the same config works on
        both 5.x and 6.x; fall back to the requested name (ApplyPreset will warn)
        when nothing matches.
        """
        if getattr(self, "_available_presets", None) is None:
            presets = servermanager.vtkSMTransferFunctionPresets.GetInstance()
            self._available_presets = {presets.GetPresetName(i) for i in range(presets.GetNumberOfPresets())}
        avail = self._available_presets
        if name in avail:
            return name
        stripped = name.replace(" (matplotlib)", "")
        if stripped in avail:  # 6.x: "Viridis (matplotlib)" -> "Viridis"
            return stripped
        suffixed = f"{name} (matplotlib)"
        if suffixed in avail:  # 5.x: bare "Viridis" -> "Viridis (matplotlib)"
            return suffixed
        logging.getLogger(__name__).warning("Colormap preset %r not found in this ParaView; using as-is", name)
        return name

    def generate_screenshots(self) -> None:
        """
        Generate visualization screenshots for all configured fields and time steps.

        This is the main entry point that orchestrates the visualization pipeline:
        1. Setup render view and OpenFOAM reader
        2. Configure camera using PCA
        3. Create calculator pipeline for derived fields
        4. Render and save screenshots

        Screenshots are saved to: {run_directory}/images/
        """
        self.logger.info(f"Starting post-processing for: {self.case_path}")

        # Setup pipeline
        foam_reader, render_view, foam_display = self._setup_render_view()
        self._foam_reader = foam_reader
        self._render_view = render_view

        # Configure camera
        self._configure_camera_pca(foam_reader, render_view)

        # Create calculator pipeline
        final_calc = self._create_calculator_pipeline(foam_reader)
        final_display = Show(final_calc, render_view)
        Hide(foam_reader, render_view)
        render_view.Update()
        self._final_display = final_display

        # Build properties and time steps
        properties = self._build_property_list()

        time_keeper = GetTimeKeeper()
        available_times = list(time_keeper.TimestepValues) if time_keeper else []
        time_steps = self._prepare_time_steps(available_times, foam_reader, render_view)

        # Render and save
        self._render_and_save(render_view, final_display, properties, time_steps)

        self.logger.info(f"Screenshots saved to: {self.image_dir}")

    def create_animations(self, fps: int = 30) -> None:
        """
        Create animations from generated screenshots.

        Requires ffmpeg to be installed. Creates one animation per field.

        Args:
            fps: Frames per second for the animation
        """
        if not check_ffmpeg_available():
            self.logger.warning("ffmpeg not found. Animation generation skipped.")
            return

        self.logger.info("Creating animations...")

        for field in self.fields:
            if field not in self.property_map:
                continue

            prefix = self.property_map[field]["prefix"]
            pattern = re.compile(rf"{re.escape(prefix)}_(\d+\.?\d*)\.png")

            # Find matching images
            images = []
            for filename in os.listdir(self.image_dir):
                match = pattern.match(filename)
                if match:
                    time_step = float(match.group(1))
                    images.append((time_step, filename))

            if not images:
                self.logger.warning(f"No images found for '{prefix}'. Skipping.")
                continue

            # Sort by time
            images.sort(key=lambda x: x[0])

            # Create file list for ffmpeg
            list_file = os.path.join(self.image_dir, f"{prefix}_files.txt")
            with open(list_file, "w") as lf:
                for _, filename in images:
                    lf.write(f"file '{filename}'\n")

            # Run ffmpeg
            output_video = os.path.join(self.image_dir, f"{prefix}.avi")
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-r",
                str(fps),
                "-i",
                list_file,
                "-c:v",
                "mpeg4",
                "-q:v",
                "5",
                output_video,
            ]

            try:
                subprocess.run(ffmpeg_cmd, check=True, cwd=self.image_dir, capture_output=True, text=True)
                self.logger.info(f"Animation saved: {output_video}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"ffmpeg failed for '{prefix}': {e.stderr}")
            finally:
                if os.path.exists(list_file):
                    os.remove(list_file)

        self.logger.info("Animation creation completed.")

    # Backwards compatibility alias
    def anima(self, fps: int = 30) -> None:
        """Legacy alias for create_animations(). Use create_animations() instead."""
        self.create_animations(fps)

    def load_custom_fields(self, config: Dict[str, Any]) -> None:
        """
        Load custom field definitions from configuration.

        Allows users to extend the property_map with custom fields defined
        in config.json without modifying the source code.

        Args:
            config: Configuration dictionary containing 'visualization.custom_fields'

        Example config:
            {
                "visualization": {
                    "custom_fields": {
                        "helicity": {
                            "name": "Helicity",
                            "derived": true,
                            "formula": "U_X*vorticity_X + U_Y*vorticity_Y + U_Z*vorticity_Z",
                            "preset": "Diverging Blue-Red",
                            "representation": "Volume",
                            "unit": "m/s²"
                        }
                    }
                }
            }
        """
        custom_fields = config.get("visualization", {}).get("custom_fields", {})

        for name, props in custom_fields.items():
            self.property_map[name] = {
                "name": props.get("name", name),
                "derived": props.get("derived", True),
                "prefix": props.get("name", name),
                "component": ("POINTS", props.get("name", name)),
                "preset": props.get("preset", "Rainbow Desaturated"),
                "representation": props.get("representation", "Surface"),
                "unit": props.get("unit", ""),
                "formula": props.get("formula"),
            }
            self.logger.info(f"Loaded custom field: {name}")


# =============================================================================
# PYTHON API
# =============================================================================


def post_process(
    case_path: Union[str, Path],
    fields: Optional[List[str]] = None,
    time_steps: Optional[Union[str, List[float]]] = None,
    color_ranges: Optional[Dict[str, List[float]]] = None,
    create_animation: bool = False,
    fps: int = 30,
) -> None:
    """
    Python API for post-processing OpenFOAM cases.

    Convenience function for running post-processing without editing JSON config.

    Args:
        case_path: Path to OpenFOAM case directory
        fields: Fields to visualize. Default: ['U', 'p', 'wallShearStress']
        time_steps: Time selection - None (all), 'last', 'peak', or list
        color_ranges: Per-field color ranges, e.g., {'WSS': [0, 50]}
        create_animation: Whether to create animations
        fps: Animation frames per second

    Example:
        >>> post_process(
        ...     "/path/to/case",
        ...     fields=['U', 'TAWSS'],
        ...     time_steps='last',
        ...     color_ranges={'WSS': [0, 50]}
        ... )
    """
    # Build rescale settings from color_ranges
    rescale_settings = None
    if color_ranges:
        rescale_settings = {}
        for field, range_vals in color_ranges.items():
            rescale_settings[field] = {"rescaleToData": False, "rescaleRange": range_vals}

    processor = OpenFOAMParaView(
        case_path=case_path, fields=fields, time_steps=time_steps, rescale_settings=rescale_settings
    )

    processor.generate_screenshots()

    if create_animation:
        processor.create_animations(fps=fps)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Main execution when running with pvbatch.

    Usage:
        pvbatch post_processor.py /path/to/case [time_option]

    Time options:
        all   - All available time steps (default)
        last  - Only the last time step
        peak  - Peak systole (maximum velocity)
    """
    import sys

    # Parse case path
    if len(sys.argv) > 1:
        case_path = sys.argv[1]
    elif "CASE_PATH" in os.environ:
        case_path = os.environ["CASE_PATH"]
    else:
        case_path = os.getcwd()

    print("[INFO] OpenFOAM Post-Processing with ParaView")
    print(f"[INFO] Case path: {case_path}")

    # Validate case
    if not os.path.exists(case_path):
        print(f"[ERROR] Case directory not found: {case_path}")
        sys.exit(1)

    foam_files = [f for f in os.listdir(case_path) if f.endswith(".foam")]
    if not foam_files:
        print(f"[ERROR] No .foam file found in {case_path}")
        sys.exit(1)

    print(f"[INFO] Found {foam_files[0]}")

    # Load config
    run_dir = os.path.dirname(os.path.abspath(case_path))
    config_path = os.path.join(run_dir, "reports", "merged_config.json")

    viz_config = {}
    rescale_settings = None
    config_time_steps = None
    config_fields = None

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                full_config = json.load(f)
            viz_config = full_config.get("visualization", {})

            config_time_steps = viz_config.get("time_steps")
            config_fields = viz_config.get("fields")

            color_ranges = viz_config.get("color_ranges", {})
            if color_ranges:
                rescale_settings = {}
                field_map = {
                    "U": "U",
                    "velocity": "U",
                    "WSS": "WSS",
                    "wss": "WSS",
                    "TAWSS": "TAWSS",
                    "tawss": "TAWSS",
                    "OSI": "OSI",
                    "osi": "OSI",
                    "RRT": "RRT",
                    "rrt": "RRT",
                    "Pressure": "Pressure",
                    "pressure": "Pressure",
                    "KE": "KE",
                }

                for field in ["U", "WSS", "TAWSS", "OSI", "RRT", "Pressure", "KE"]:
                    user_range = None
                    for key, mapped in field_map.items():
                        if mapped == field and key in color_ranges:
                            user_range = color_ranges[key]
                            break

                    if user_range:
                        rescale_settings[field] = {"rescaleToData": False, "rescaleRange": user_range}
                        print(f"[INFO] {field}: fixed range {user_range}")
                    else:
                        rescale_settings[field] = {
                            "rescaleToData": True,
                            "rescaleRange": DEFAULT_COLOR_RANGES.get(field, [0, 1]),
                        }
                        print(f"[INFO] {field}: auto-scale")
        except Exception as e:
            print(f"[WARNING] Could not load config: {e}")

    # Parse CLI time option
    time_option = config_time_steps
    if time_option is None and len(sys.argv) > 2:
        time_arg = sys.argv[2].lower()
        if time_arg == "last":
            time_option = "last"
        elif time_arg == "peak":
            time_option = "peak"
        elif time_arg == "all":
            time_option = None

    fields_to_use = config_fields if config_fields else ["U", "p", "wallShearStress"]

    try:
        processor = OpenFOAMParaView(
            case_path=case_path,
            case_type="auto",
            time_steps=time_option,
            fields=fields_to_use,
            rescale_settings=rescale_settings,
        )

        print("[INFO] Generating visualizations...")
        processor.generate_screenshots()

        print(f"[INFO] Screenshots saved to: {processor.image_dir}")
        print("[INFO] Post-processing completed successfully!")

        if time_option is None:
            try:
                print("[INFO] Creating animations...")
                processor.create_animations(fps=30)
                print("[INFO] Animations created successfully!")
            except Exception as e:
                print(f"[WARNING] Could not create animations: {e}")
        else:
            print("[INFO] Skipping animation (single time step mode)")

    except Exception as e:
        print(f"[ERROR] Post-processing failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
