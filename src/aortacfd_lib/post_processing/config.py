"""
Configuration handling for post-processing.

Supports JSON and YAML configuration files with sensible defaults.
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

# Try to import YAML support
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class VisualizationConfig:
    """Configuration for ParaView visualization."""

    # Fields to visualize
    fields: List[str] = field(default_factory=lambda: ["U", "p", "wallShearStress"])

    # Time step selection: 'all', 'last', 'peak', or list of floats
    time_steps: Union[str, List[float], None] = None

    # Output resolution
    resolution: List[int] = field(default_factory=lambda: [1600, 900])

    # Frame rate for animations
    fps: int = 30

    # Auto-detect case type (Reconstructed/Decomposed)
    auto_detect_case_type: bool = True

    # Color presets for each field
    color_presets: Dict[str, str] = field(default_factory=lambda: {
        "U": "Rainbow Desaturated",
        "p": "Blue - Green - Orange",
        "wallShearStress": "Viridis (matplotlib)",
        "KE": "Inferno (matplotlib)"
    })

    # Rescale settings per field: {"field": {"rescaleToData": True, "rescaleRange": [min, max]}}
    rescale_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class HemodynamicsConfig:
    """Configuration for hemodynamic metrics computation."""

    # Number of cardiac cycles to skip for TAWSS averaging
    skip_cycles: int = 2

    # Run wallShearStress post-processing if not found
    run_wss_postprocess: bool = True

    # Generate pressure drop plots
    generate_plots: bool = True

    # Clinical thresholds for reporting
    low_tawss_threshold: float = 0.4  # Pa
    high_tawss_threshold: float = 40.0  # Pa
    high_osi_threshold: float = 0.3
    significant_pressure_drop: float = 20.0  # mmHg


@dataclass
class OutputConfig:
    """Configuration for output files."""

    # Output directory (relative to case or absolute)
    output_dir: str = "postProcessing_results"

    # Generate screenshots
    screenshots: bool = True

    # Generate animations (requires ffmpeg)
    animations: bool = True

    # Generate hemodynamics report
    hemodynamics_report: bool = True

    # Generate pressure plots
    pressure_plots: bool = True

    # Log file name
    log_file: str = "postProcessing.log"


@dataclass
class PostProcessingConfig:
    """Complete post-processing configuration."""

    # Case directory
    case_dir: str = ""

    # Visualization settings
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)

    # Hemodynamics settings
    hemodynamics: HemodynamicsConfig = field(default_factory=HemodynamicsConfig)

    # Output settings
    output: OutputConfig = field(default_factory=OutputConfig)

    # Inlet configuration (for hemodynamics)
    inlet: Dict[str, Any] = field(default_factory=dict)

    # Geometry configuration (patch names)
    geometry: Dict[str, Any] = field(default_factory=dict)

    # Cardiac cycle duration (seconds)
    cardiac_cycle: float = 0.8

    # Verbosity level: 0=quiet, 1=normal, 2=debug
    verbosity: int = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PostProcessingConfig':
        """Create configuration from dictionary."""
        config = cls()

        # Top-level settings
        config.case_dir = data.get('case_dir', config.case_dir)
        config.cardiac_cycle = data.get('cardiac_cycle', config.cardiac_cycle)
        config.verbosity = data.get('verbosity', config.verbosity)
        config.inlet = data.get('inlet', data.get('boundary_conditions', {}).get('inlet', {}))
        config.geometry = data.get('geometry', {})

        # Visualization settings
        viz = data.get('visualization', data.get('post_processing', {}).get('visualization', {}))
        if viz:
            config.visualization.fields = viz.get('fields', config.visualization.fields)
            config.visualization.time_steps = viz.get('time_steps', config.visualization.time_steps)
            config.visualization.resolution = viz.get('resolution', config.visualization.resolution)
            config.visualization.fps = viz.get('fps', config.visualization.fps)
            config.visualization.auto_detect_case_type = viz.get('auto_detect_case_type', True)
            config.visualization.color_presets = viz.get('color_presets', config.visualization.color_presets)
            config.visualization.rescale_settings = viz.get('rescale_settings', {})

        # Hemodynamics settings
        hemo = data.get('hemodynamics', {})
        tawss = hemo.get('tawss_settings', {})
        if hemo or tawss:
            config.hemodynamics.skip_cycles = tawss.get('skip_cycles', config.hemodynamics.skip_cycles)
            config.hemodynamics.run_wss_postprocess = hemo.get('run_wss_postprocess', True)
            config.hemodynamics.generate_plots = hemo.get('generate_plots', True)

        # Output settings
        out = data.get('output', data.get('post_processing', {}).get('output', {}))
        if out:
            config.output.output_dir = out.get('output_dir', config.output.output_dir)
            config.output.screenshots = out.get('screenshots', True)
            config.output.animations = out.get('animations', True)
            config.output.hemodynamics_report = out.get('hemodynamics_report', True)
            config.output.pressure_plots = out.get('pressure_plots', True)
            config.output.log_file = out.get('log_file', config.output.log_file)

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'case_dir': self.case_dir,
            'cardiac_cycle': self.cardiac_cycle,
            'verbosity': self.verbosity,
            'inlet': self.inlet,
            'geometry': self.geometry,
            'visualization': {
                'fields': self.visualization.fields,
                'time_steps': self.visualization.time_steps,
                'resolution': self.visualization.resolution,
                'fps': self.visualization.fps,
                'auto_detect_case_type': self.visualization.auto_detect_case_type,
                'color_presets': self.visualization.color_presets,
                'rescale_settings': self.visualization.rescale_settings,
            },
            'hemodynamics': {
                'skip_cycles': self.hemodynamics.skip_cycles,
                'run_wss_postprocess': self.hemodynamics.run_wss_postprocess,
                'generate_plots': self.hemodynamics.generate_plots,
            },
            'output': {
                'output_dir': self.output.output_dir,
                'screenshots': self.output.screenshots,
                'animations': self.output.animations,
                'hemodynamics_report': self.output.hemodynamics_report,
                'pressure_plots': self.output.pressure_plots,
                'log_file': self.output.log_file,
            }
        }


def load_config(config_path: Union[str, Path, None] = None,
                case_dir: Optional[str] = None) -> PostProcessingConfig:
    """
    Load post-processing configuration from file.

    Supports JSON and YAML formats. Falls back to defaults if no file provided.

    Args:
        config_path: Path to configuration file (JSON or YAML)
        case_dir: Override case directory

    Returns:
        PostProcessingConfig instance

    Examples:
        >>> config = load_config("postprocess.yaml")
        >>> config = load_config("config.json", case_dir="/path/to/case")
        >>> config = load_config()  # Use defaults
    """
    config_data = {}

    if config_path:
        config_path = Path(config_path)
        if config_path.exists():
            suffix = config_path.suffix.lower()

            try:
                with open(config_path, 'r') as f:
                    if suffix in ['.yaml', '.yml']:
                        if not HAS_YAML:
                            logger.warning("YAML support not available. Install PyYAML: pip install pyyaml")
                            logger.info("Falling back to defaults")
                        else:
                            config_data = yaml.safe_load(f) or {}
                            logger.info(f"Loaded configuration from {config_path}")
                    elif suffix == '.json':
                        config_data = json.load(f)
                        logger.info(f"Loaded configuration from {config_path}")
                    else:
                        logger.warning(f"Unknown config format: {suffix}. Supported: .json, .yaml, .yml")
            except Exception as e:
                logger.error(f"Failed to load config from {config_path}: {e}")
        else:
            logger.warning(f"Config file not found: {config_path}")

    # Create config from data
    config = PostProcessingConfig.from_dict(config_data)

    # Override case_dir if provided
    if case_dir:
        config.case_dir = case_dir

    return config


def save_config(config: PostProcessingConfig, output_path: Union[str, Path]) -> None:
    """
    Save configuration to file.

    Args:
        config: PostProcessingConfig instance
        output_path: Output file path (JSON or YAML based on extension)
    """
    output_path = Path(output_path)
    suffix = output_path.suffix.lower()

    config_dict = config.to_dict()

    with open(output_path, 'w') as f:
        if suffix in ['.yaml', '.yml']:
            if not HAS_YAML:
                raise RuntimeError("YAML support not available. Install PyYAML: pip install pyyaml")
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        else:
            json.dump(config_dict, f, indent=2)

    logger.info(f"Saved configuration to {output_path}")


# Default configuration template (JSON format - consistent with AortaCFD)
DEFAULT_CONFIG_TEMPLATE = """{
  "_doc": "AortaCFD Post-Processing Configuration",

  "case_dir": ".",
  "cardiac_cycle": 0.8,
  "verbosity": 1,

  "visualization": {
    "fields": ["U", "p", "wallShearStress"],
    "time_steps": "all",
    "resolution": [1600, 900],
    "fps": 30,
    "auto_detect_case_type": true
  },

  "hemodynamics": {
    "skip_cycles": 2,
    "run_wss_postprocess": true,
    "generate_plots": true
  },

  "output": {
    "output_dir": "postProcessing_results",
    "screenshots": true,
    "animations": true,
    "hemodynamics_report": true,
    "pressure_plots": true
  }
}
"""


def generate_config_template(output_path: Union[str, Path] = "postprocess_config.json") -> str:
    """
    Generate a configuration template file.

    Args:
        output_path: Path for the template file

    Returns:
        Path to generated template
    """
    output_path = Path(output_path)
    output_path.write_text(DEFAULT_CONFIG_TEMPLATE)
    logger.info(f"Generated configuration template: {output_path}")
    return str(output_path)
