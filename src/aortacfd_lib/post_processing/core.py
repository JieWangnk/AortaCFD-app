"""
Core PostProcessor class for unified post-processing.

Combines visualization and hemodynamics into a single interface.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .config import PostProcessingConfig, load_config
from .dependencies import check_dependencies, has_paraview, has_ffmpeg, has_openfoam

# Import hemodynamics processor
from ..hemodynamics_postprocessor import (
    HemodynamicsPostProcessor,
    HemodynamicsResults,
)

logger = logging.getLogger(__name__)


class PostProcessor:
    """
    Unified post-processor for OpenFOAM CFD simulations.

    Provides a single interface for:
    - ParaView-based visualization (screenshots, animations)
    - Hemodynamic metrics (TAWSS, OSI, RRT, pressure drop)
    - Report generation

    Usage:
        # From configuration file
        processor = PostProcessor.from_config("postprocess.yaml", case_dir="/path/to/case")
        processor.run_all()

        # From dictionary
        processor = PostProcessor(case_dir="/path/to/case", config={"cardiac_cycle": 0.8})
        results = processor.run_hemodynamics()
        processor.run_visualization()

        # Minimal usage
        processor = PostProcessor(case_dir="/path/to/case")
        processor.run_all()
    """

    def __init__(
        self,
        case_dir: Union[str, Path],
        config: Optional[Union[PostProcessingConfig, Dict[str, Any]]] = None,
        verbosity: int = 1,
    ):
        """
        Initialize PostProcessor.

        Args:
            case_dir: Path to OpenFOAM case directory
            config: Configuration (PostProcessingConfig, dict, or None for defaults)
            verbosity: 0=quiet, 1=normal, 2=debug
        """
        self.case_dir = Path(case_dir).resolve()

        # Handle configuration
        if isinstance(config, PostProcessingConfig):
            self.config = config
        elif isinstance(config, dict):
            config["case_dir"] = str(self.case_dir)
            self.config = PostProcessingConfig.from_dict(config)
        else:
            self.config = PostProcessingConfig()
            self.config.case_dir = str(self.case_dir)

        # Override verbosity if provided
        if verbosity is not None:
            self.config.verbosity = verbosity

        # Setup logging
        self._setup_logging()

        # Verify case directory exists
        if not self.case_dir.exists():
            raise ValueError(f"Case directory not found: {self.case_dir}")

        # Initialize output directory
        self.output_dir = self._get_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Check dependencies
        self.dep_report = check_dependencies(verbose=(verbosity >= 2))

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"PostProcessor initialized for: {self.case_dir}")

    @classmethod
    def from_config(cls, config_path: Union[str, Path], case_dir: Optional[str] = None) -> "PostProcessor":
        """
        Create PostProcessor from configuration file.

        Args:
            config_path: Path to configuration file (JSON or YAML)
            case_dir: Optional override for case directory

        Returns:
            PostProcessor instance
        """
        config = load_config(config_path, case_dir)
        return cls(case_dir=case_dir or config.case_dir or ".", config=config)

    def _setup_logging(self) -> None:
        """Configure logging based on verbosity."""
        level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}.get(self.config.verbosity, logging.INFO)

        logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    def _get_output_dir(self) -> Path:
        """Get output directory path."""
        output_path = self.config.output.output_dir

        if os.path.isabs(output_path):
            return Path(output_path)

        # Check if case_dir is inside a run directory structure
        # e.g., output/patient/run_xxx/openfoam -> output to run_xxx level
        if self.case_dir.name == "openfoam":
            return self.case_dir.parent / output_path
        else:
            return self.case_dir / output_path

    def run_all(self) -> Dict[str, Any]:
        """
        Run all post-processing tasks.

        Returns:
            Dictionary with all results
        """
        results = {}

        self.logger.info("=" * 60)
        self.logger.info("Starting complete post-processing pipeline")
        self.logger.info("=" * 60)

        # 1. Run hemodynamics analysis
        if self.config.output.hemodynamics_report:
            self.logger.info("Running hemodynamics analysis...")
            try:
                results["hemodynamics"] = self.run_hemodynamics()
            except Exception as e:
                self.logger.error(f"Hemodynamics analysis failed: {e}")
                results["hemodynamics"] = None

        # 2. Run visualization (if ParaView available)
        if self.config.output.screenshots and has_paraview():
            self.logger.info("Running visualization...")
            try:
                results["visualization"] = self.run_visualization()
            except Exception as e:
                self.logger.error(f"Visualization failed: {e}")
                results["visualization"] = None
        elif not has_paraview():
            self.logger.warning("ParaView not available - skipping visualization")

        # 3. Create animations (if ffmpeg available)
        if self.config.output.animations and has_ffmpeg() and has_paraview():
            self.logger.info("Creating animations...")
            try:
                results["animations"] = self.run_animations()
            except Exception as e:
                self.logger.error(f"Animation creation failed: {e}")
                results["animations"] = None
        elif not has_ffmpeg():
            self.logger.warning("ffmpeg not available - skipping animations")

        self.logger.info("=" * 60)
        self.logger.info(f"Post-processing complete. Output: {self.output_dir}")
        self.logger.info("=" * 60)

        return results

    def run_hemodynamics(self) -> HemodynamicsResults:
        """
        Run hemodynamics analysis.

        Returns:
            HemodynamicsResults with TAWSS, OSI, RRT, pressure drop
        """
        # Create config dict for hemodynamics processor
        config_dict = {
            "inlet": self.config.inlet,
            "geometry": self.config.geometry,
            "cardiac_cycle": self.config.cardiac_cycle,
            "hemodynamics": {"tawss_settings": {"skip_cycles": self.config.hemodynamics.skip_cycles}},
        }

        processor = HemodynamicsPostProcessor(str(self.case_dir), config_dict)

        # Run WSS post-processing if needed
        if self.config.hemodynamics.run_wss_postprocess and not processor._check_wss_exists():
            if has_openfoam():
                self.logger.info("Running wallShearStress post-processing...")
                processor.run_wss_postprocess()
            else:
                self.logger.warning(
                    "OpenFOAM not available - cannot run WSS post-processing. " "Source OpenFOAM environment and retry."
                )

        # Compute all metrics
        results = processor.compute_all()

        # Generate report
        if self.config.output.hemodynamics_report:
            processor.generate_report(results, str(self.output_dir))

        return results

    def run_visualization(self) -> Dict[str, Any]:
        """
        Run ParaView visualization.

        NOTE: This method should be called via pvbatch for full functionality.
        When called from regular Python, it will attempt to use ParaView's
        Python bindings if available.

        Returns:
            Dictionary with visualization results
        """
        if not has_paraview():
            raise RuntimeError(
                "ParaView not available. Run with pvbatch:\n"
                "  pvbatch -m aortacfd_lib.post_processing.visualization /path/to/case"
            )

        # Import visualization module
        try:
            from ..post_processor import OpenFOAMParaView
        except ImportError as e:
            raise RuntimeError(f"Failed to import visualization module: {e}")

        # Prepare rescale settings
        rescale_settings = self.config.visualization.rescale_settings or {}

        # Create visualizer
        visualizer = OpenFOAMParaView(
            casePath=str(self.case_dir),
            caseType="auto" if self.config.visualization.auto_detect_case_type else "Reconstructed",
            timeSteps=self.config.visualization.time_steps,
            fields=self.config.visualization.fields,
            rescaleSettings=rescale_settings if rescale_settings else None,
        )

        # Override image directory to our output directory
        visualizer.imageDir = str(self.output_dir / "images")
        os.makedirs(visualizer.imageDir, exist_ok=True)

        # Generate screenshots
        visualizer.generate_screenshots()

        return {
            "image_dir": visualizer.imageDir,
            "fields": self.config.visualization.fields,
            "time_steps": visualizer.timeSteps,
        }

    def run_animations(self, fps: Optional[int] = None) -> Dict[str, Any]:
        """
        Create animations from screenshots.

        Args:
            fps: Frames per second (default from config)

        Returns:
            Dictionary with animation results
        """
        if not has_ffmpeg():
            raise RuntimeError("ffmpeg not available - cannot create animations")

        fps = fps or self.config.visualization.fps

        try:
            from ..post_processor import OpenFOAMParaView
        except ImportError as e:
            raise RuntimeError(f"Failed to import visualization module: {e}")

        # Create visualizer just for animation
        visualizer = OpenFOAMParaView(
            casePath=str(self.case_dir), timeSteps=None, fields=self.config.visualization.fields
        )
        visualizer.imageDir = str(self.output_dir / "images")

        # Create animations
        visualizer.anima(fps=fps)

        return {"fps": fps, "output_dir": visualizer.imageDir}

    def check_status(self) -> Dict[str, Any]:
        """
        Check post-processing status and available data.

        Returns:
            Dictionary with status information
        """
        status = {
            "case_dir": str(self.case_dir),
            "case_exists": self.case_dir.exists(),
            "foam_file_exists": False,
            "time_directories": [],
            "wss_available": False,
            "fieldaverage_available": False,
            "postprocessing_available": False,
            "dependencies": {},
        }

        # Check for .foam file
        foam_files = list(self.case_dir.glob("*.foam"))
        status["foam_file_exists"] = len(foam_files) > 0

        # Check time directories
        time_dirs = []
        for item in self.case_dir.iterdir():
            if item.is_dir():
                try:
                    time_val = float(item.name)
                    time_dirs.append(time_val)
                except ValueError:
                    pass
        status["time_directories"] = sorted(time_dirs)

        # Check for WSS data
        for t in status["time_directories"]:
            wss_file = self.case_dir / str(t) / "wallShearStress"
            if wss_file.exists():
                status["wss_available"] = True
                break

        # Check for fieldAverage data
        for t in status["time_directories"]:
            mean_file = self.case_dir / str(t) / "wallShearStressMean"
            if mean_file.exists():
                status["fieldaverage_available"] = True
                break

        # Check for postProcessing directory
        postproc_dir = self.case_dir / "postProcessing"
        status["postprocessing_available"] = postproc_dir.exists()

        # Dependency status
        for name, dep in self.dep_report.dependencies.items():
            status["dependencies"][name] = dep.available

        return status

    def print_status(self) -> None:
        """Print formatted status report."""
        status = self.check_status()

        print("\n" + "=" * 60)
        print("POST-PROCESSING STATUS")
        print("=" * 60)

        print(f"\nCase Directory: {status['case_dir']}")
        print(f"  Exists: {'Yes' if status['case_exists'] else 'No'}")
        print(f"  .foam file: {'Yes' if status['foam_file_exists'] else 'No'}")

        print(f"\nTime Directories: {len(status['time_directories'])}")
        if status["time_directories"]:
            print(f"  Range: {status['time_directories'][0]:.6f} - {status['time_directories'][-1]:.6f}")

        print("\nData Availability:")
        print(f"  WSS fields: {'Yes' if status['wss_available'] else 'No'}")
        print(f"  fieldAverage (TAWSS/OSI): {'Yes' if status['fieldaverage_available'] else 'No'}")
        print(f"  postProcessing data: {'Yes' if status['postprocessing_available'] else 'No'}")

        print("\nDependencies:")
        for name, available in status["dependencies"].items():
            status_str = "[OK]" if available else "[MISSING]"
            print(f"  {status_str:10} {name}")

        print("\n" + "=" * 60)
