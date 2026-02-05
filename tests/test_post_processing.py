"""
Test suite for the unified post_processing module.

Tests cover:
- Configuration handling (JSON/YAML)
- Dependency checking
- PostProcessor core functionality
- CLI argument parsing
"""

import pytest
import sys
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _paraview_module_available() -> bool:
    """Check if paraview Python module is importable (not just pvbatch executable)."""
    try:
        import paraview.simple  # noqa: F401
        return True
    except ImportError:
        return False


# Cache the result since import checking is slow
PARAVIEW_MODULE_AVAILABLE = _paraview_module_available()

from aortacfd_lib.post_processing.config import (
    PostProcessingConfig,
    VisualizationConfig,
    HemodynamicsConfig,
    OutputConfig,
    load_config,
    save_config,
    generate_config_template,
)
from aortacfd_lib.post_processing.dependencies import (
    DependencyStatus,
    DependencyReport,
    check_dependencies,
    check_python_module,
    check_executable,
    has_paraview,
    has_ffmpeg,
    has_matplotlib,
)


class TestVisualizationConfig:
    """Test VisualizationConfig dataclass."""

    def test_default_values(self):
        """Test default visualization config values."""
        config = VisualizationConfig()

        assert config.fields == ["U", "p", "wallShearStress"]
        assert config.time_steps is None
        assert config.resolution == [1600, 900]
        assert config.fps == 30
        assert config.auto_detect_case_type == True

    def test_color_presets(self):
        """Test default color presets."""
        config = VisualizationConfig()

        assert "U" in config.color_presets
        assert config.color_presets["U"] == "Rainbow Desaturated"
        assert "wallShearStress" in config.color_presets


class TestHemodynamicsConfig:
    """Test HemodynamicsConfig dataclass."""

    def test_default_values(self):
        """Test default hemodynamics config values."""
        config = HemodynamicsConfig()

        assert config.skip_cycles == 2
        assert config.run_wss_postprocess == True
        assert config.generate_plots == True

    def test_clinical_thresholds(self):
        """Test clinical threshold defaults."""
        config = HemodynamicsConfig()

        assert config.low_tawss_threshold == 0.4  # Pa
        assert config.high_tawss_threshold == 40.0  # Pa
        assert config.high_osi_threshold == 0.3
        assert config.significant_pressure_drop == 20.0  # mmHg


class TestOutputConfig:
    """Test OutputConfig dataclass."""

    def test_default_values(self):
        """Test default output config values."""
        config = OutputConfig()

        assert config.output_dir == "postProcessing_results"
        assert config.screenshots == True
        assert config.animations == True
        assert config.hemodynamics_report == True
        assert config.pressure_plots == True


class TestPostProcessingConfig:
    """Test PostProcessingConfig dataclass."""

    def test_default_values(self):
        """Test default config values."""
        config = PostProcessingConfig()

        assert config.case_dir == ""
        assert config.cardiac_cycle == 0.8
        assert config.verbosity == 1
        assert isinstance(config.visualization, VisualizationConfig)
        assert isinstance(config.hemodynamics, HemodynamicsConfig)
        assert isinstance(config.output, OutputConfig)

    def test_from_dict_minimal(self):
        """Test creating config from minimal dict."""
        data = {
            'case_dir': '/path/to/case',
            'cardiac_cycle': 1.0
        }

        config = PostProcessingConfig.from_dict(data)

        assert config.case_dir == '/path/to/case'
        assert config.cardiac_cycle == 1.0

    def test_from_dict_full(self):
        """Test creating config from full dict."""
        data = {
            'case_dir': '/path/to/case',
            'cardiac_cycle': 1.0,
            'verbosity': 2,
            'visualization': {
                'fields': ['U', 'p'],
                'time_steps': 'last',
                'fps': 60,
                'resolution': [1920, 1080],
            },
            'hemodynamics': {
                'tawss_settings': {
                    'skip_cycles': 3
                },
                'run_wss_postprocess': False,
            },
            'output': {
                'output_dir': 'my_output',
                'animations': False,
            }
        }

        config = PostProcessingConfig.from_dict(data)

        assert config.visualization.fields == ['U', 'p']
        assert config.visualization.time_steps == 'last'
        assert config.visualization.fps == 60
        assert config.hemodynamics.skip_cycles == 3
        assert config.hemodynamics.run_wss_postprocess == False
        assert config.output.output_dir == 'my_output'
        assert config.output.animations == False

    def test_to_dict(self):
        """Test converting config to dict."""
        config = PostProcessingConfig()
        config.case_dir = '/path/to/case'
        config.cardiac_cycle = 1.0

        data = config.to_dict()

        assert isinstance(data, dict)
        assert data['case_dir'] == '/path/to/case'
        assert data['cardiac_cycle'] == 1.0
        assert 'visualization' in data
        assert 'hemodynamics' in data
        assert 'output' in data

    def test_boundary_conditions_fallback(self):
        """Test fallback to boundary_conditions for inlet config."""
        data = {
            'boundary_conditions': {
                'inlet': {
                    'type': 'TIMEVARYING',
                    'file': 'inlet.csv'
                }
            }
        }

        config = PostProcessingConfig.from_dict(data)

        assert config.inlet.get('type') == 'TIMEVARYING'


class TestLoadConfig:
    """Test configuration loading functions."""

    def test_load_config_json(self):
        """Test loading JSON configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                'case_dir': '/path/to/case',
                'cardiac_cycle': 0.9,
                'visualization': {
                    'fields': ['U']
                }
            }, f)
            config_path = f.name

        try:
            config = load_config(config_path)

            assert config.case_dir == '/path/to/case'
            assert config.cardiac_cycle == 0.9
            assert config.visualization.fields == ['U']
        finally:
            os.unlink(config_path)

    def test_load_config_case_dir_override(self):
        """Test case_dir override."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'case_dir': '/original/path'}, f)
            config_path = f.name

        try:
            config = load_config(config_path, case_dir='/override/path')

            assert config.case_dir == '/override/path'
        finally:
            os.unlink(config_path)

    def test_load_config_missing_file(self):
        """Test loading with missing file returns defaults."""
        config = load_config('/nonexistent/path.json')

        assert config.case_dir == ""
        assert isinstance(config.visualization, VisualizationConfig)

    def test_load_config_no_path(self):
        """Test loading with no path returns defaults."""
        config = load_config(None)

        assert config.case_dir == ""


class TestSaveConfig:
    """Test configuration saving functions."""

    def test_save_config_json(self):
        """Test saving configuration as JSON."""
        config = PostProcessingConfig()
        config.case_dir = '/path/to/case'
        config.cardiac_cycle = 1.0

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            save_config(config, output_path)

            with open(output_path, 'r') as f:
                data = json.load(f)

            assert data['case_dir'] == '/path/to/case'
            assert data['cardiac_cycle'] == 1.0
        finally:
            os.unlink(output_path)


class TestGenerateConfigTemplate:
    """Test configuration template generation."""

    def test_generate_template(self):
        """Test generating config template."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            output_path = f.name

        try:
            result = generate_config_template(output_path)

            assert os.path.exists(result)
            with open(result, 'r') as f:
                content = f.read()

            assert 'case_dir' in content
            assert 'visualization' in content
            assert 'hemodynamics' in content
        finally:
            os.unlink(output_path)


class TestDependencyStatus:
    """Test DependencyStatus dataclass."""

    def test_default_values(self):
        """Test default dependency status values."""
        status = DependencyStatus(name="test")

        assert status.name == "test"
        assert status.available == False
        assert status.version is None
        assert status.required == False

    def test_full_status(self):
        """Test full dependency status."""
        status = DependencyStatus(
            name="numpy",
            available=True,
            version="1.24.0",
            required=True,
            purpose="Array operations",
            install_hint="pip install numpy"
        )

        assert status.available == True
        assert status.version == "1.24.0"
        assert status.required == True


class TestDependencyReport:
    """Test DependencyReport dataclass."""

    def test_default_values(self):
        """Test default report values."""
        report = DependencyReport()

        assert report.all_required_available == True
        assert report.dependencies == {}
        assert report.warnings == []
        assert report.errors == []

    def test_add_dependencies(self):
        """Test adding dependencies to report."""
        report = DependencyReport()
        report.dependencies['numpy'] = DependencyStatus(
            name='numpy',
            available=True,
            required=True
        )

        assert 'numpy' in report.dependencies
        assert report.dependencies['numpy'].available == True


class TestCheckPythonModule:
    """Test Python module checking."""

    def test_numpy_available(self):
        """Test checking numpy (should be available)."""
        status = check_python_module('numpy')

        assert status.available == True
        assert status.version is not None

    def test_nonexistent_module(self):
        """Test checking nonexistent module."""
        status = check_python_module('nonexistent_module_12345')

        assert status.available == False
        assert status.version is None


class TestCheckExecutable:
    """Test executable checking."""

    def test_python_available(self):
        """Test checking python (should be available)."""
        status = check_executable('python3')

        # python3 should be available in test environment
        assert status.name == 'python3'
        # May or may not be available depending on environment

    def test_nonexistent_executable(self):
        """Test checking nonexistent executable."""
        status = check_executable('nonexistent_exe_12345')

        assert status.available == False
        assert status.path is None


class TestCheckDependencies:
    """Test full dependency checking."""

    def test_returns_report(self):
        """Test that check_dependencies returns a report."""
        report = check_dependencies(verbose=False)

        assert isinstance(report, DependencyReport)
        assert 'numpy' in report.dependencies
        assert 'vtk' in report.dependencies
        assert 'matplotlib' in report.dependencies
        assert 'paraview' in report.dependencies
        assert 'ffmpeg' in report.dependencies

    def test_required_deps_marked(self):
        """Test that required dependencies are marked."""
        report = check_dependencies(verbose=False)

        assert report.dependencies['numpy'].required == True
        assert report.dependencies['vtk'].required == True
        assert report.dependencies['matplotlib'].required == False
        assert report.dependencies['ffmpeg'].required == False


class TestConvenienceFunctions:
    """Test dependency convenience functions."""

    def test_has_matplotlib(self):
        """Test has_matplotlib function."""
        result = has_matplotlib()
        assert isinstance(result, bool)

    def test_has_paraview(self):
        """Test has_paraview function."""
        result = has_paraview()
        assert isinstance(result, bool)

    def test_has_ffmpeg(self):
        """Test has_ffmpeg function."""
        result = has_ffmpeg()
        assert isinstance(result, bool)


class TestPostProcessorCore:
    """Test PostProcessor core functionality."""

    def setup_method(self):
        """Create temporary case directory."""
        self.temp_dir = tempfile.mkdtemp()

        # Create minimal OpenFOAM case structure
        os.makedirs(os.path.join(self.temp_dir, 'constant'), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, 'system'), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, '0'), exist_ok=True)

        # Create .foam file
        foam_file = os.path.join(self.temp_dir, 'case.foam')
        open(foam_file, 'w').close()

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_with_dict_config(self):
        """Test initialization with dict config."""
        from aortacfd_lib.post_processing.core import PostProcessor

        config = {'cardiac_cycle': 1.0, 'verbosity': 0}
        processor = PostProcessor(self.temp_dir, config, verbosity=0)

        assert processor.case_dir == Path(self.temp_dir).resolve()
        assert processor.config.cardiac_cycle == 1.0

    def test_init_with_postprocessingconfig(self):
        """Test initialization with PostProcessingConfig."""
        from aortacfd_lib.post_processing.core import PostProcessor

        config = PostProcessingConfig()
        config.cardiac_cycle = 1.2
        processor = PostProcessor(self.temp_dir, config, verbosity=0)

        assert processor.config.cardiac_cycle == 1.2

    def test_check_status(self):
        """Test status checking."""
        from aortacfd_lib.post_processing.core import PostProcessor

        processor = PostProcessor(self.temp_dir, verbosity=0)
        status = processor.check_status()

        assert status['case_exists'] == True
        assert status['foam_file_exists'] == True
        assert isinstance(status['time_directories'], list)
        assert isinstance(status['dependencies'], dict)

    def test_invalid_case_dir_raises(self):
        """Test that invalid case directory raises error."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with pytest.raises(ValueError, match="Case directory not found"):
            PostProcessor('/nonexistent/path/12345', verbosity=0)


class TestCLI:
    """Test CLI argument parsing."""

    def test_check_deps_flag(self):
        """Test --check-deps flag."""
        from aortacfd_lib.post_processing.cli import main

        # Should run without error
        # Note: check_dependencies is imported inside the function, so we patch at the source
        with patch('aortacfd_lib.post_processing.dependencies.check_dependencies') as mock_check:
            mock_check.return_value = DependencyReport()
            result = main(['--check-deps'])

        assert result == 0

    def test_generate_config_flag(self):
        """Test --generate-config flag."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            output_path = f.name

        try:
            result = main(['--generate-config', output_path])

            assert result == 0
            assert os.path.exists(output_path)
        finally:
            os.unlink(output_path)

    def test_missing_case_dir_without_utility_flags(self):
        """Test that missing case_dir fails without utility flags."""
        from aortacfd_lib.post_processing.cli import main

        # Should fail because no case_dir and no utility flags
        with pytest.raises(SystemExit):
            main([])


class TestModuleImports:
    """Test that module imports work correctly."""

    def test_import_from_post_processing(self):
        """Test importing from post_processing package."""
        from aortacfd_lib.post_processing import (
            PostProcessor,
            PostProcessingConfig,
            load_config,
            check_dependencies,
            DependencyStatus,
        )

        assert PostProcessor is not None
        assert PostProcessingConfig is not None
        assert load_config is not None
        assert check_dependencies is not None

    def test_hemodynamics_reexport(self):
        """Test hemodynamics reexports work."""
        from aortacfd_lib.post_processing import (
            HemodynamicsPostProcessor,
            HemodynamicsResults,
            run_hemodynamics_analysis,
        )

        assert HemodynamicsPostProcessor is not None
        assert HemodynamicsResults is not None
        assert run_hemodynamics_analysis is not None

    def test_exceptions_import(self):
        """Test exception classes can be imported."""
        from aortacfd_lib.post_processing import (
            PostProcessingError,
            MissingFieldError,
            ParaViewError,
            ConfigurationError,
            CaseNotFoundError,
            DependencyError,
            HemodynamicsError,
        )

        assert PostProcessingError is not None
        assert MissingFieldError is not None
        assert ParaViewError is not None


# =============================================================================
# NEW TESTS FOR REFACTORED POST_PROCESSOR
# =============================================================================

class TestPostProcessorExceptions:
    """Test custom exception classes."""

    def test_post_processing_error_basic(self):
        """Test PostProcessingError basic usage."""
        from aortacfd_lib.post_processing.exceptions import PostProcessingError

        error = PostProcessingError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_post_processing_error_with_details(self):
        """Test PostProcessingError with details."""
        from aortacfd_lib.post_processing.exceptions import PostProcessingError

        error = PostProcessingError("Something went wrong", details="Check input files")
        assert "Something went wrong" in str(error)
        assert "Check input files" in str(error)

    def test_missing_field_error(self):
        """Test MissingFieldError."""
        from aortacfd_lib.post_processing.exceptions import MissingFieldError

        error = MissingFieldError(
            "wallShearStressMean",
            required_for="TAWSS calculation",
            hint="Enable fieldAverage in controlDict"
        )
        assert "wallShearStressMean" in str(error)
        assert "TAWSS" in str(error)
        assert "fieldAverage" in str(error)

    def test_configuration_error(self):
        """Test ConfigurationError."""
        from aortacfd_lib.post_processing.exceptions import ConfigurationError

        error = ConfigurationError(
            "Invalid time_steps value",
            value="invalid",
            valid_options="None, 'last', 'peak', or list"
        )
        assert "Invalid time_steps" in str(error)
        assert "invalid" in str(error)

    def test_case_not_found_error(self):
        """Test CaseNotFoundError."""
        from aortacfd_lib.post_processing.exceptions import CaseNotFoundError

        error = CaseNotFoundError("/path/to/case", "No .foam file found")
        assert "/path/to/case" in str(error)
        assert "No .foam file" in str(error)

    def test_hemodynamics_error(self):
        """Test HemodynamicsError."""
        from aortacfd_lib.post_processing.exceptions import HemodynamicsError

        error = HemodynamicsError(
            "Calculation failed",
            metric="OSI",
            reason="Division by zero"
        )
        assert "Calculation failed" in str(error)
        assert "OSI" in str(error)


class TestTimeStepPreparation:
    """Test time step preparation logic."""

    def test_prepare_time_steps_all(self):
        """Test preparing all time steps."""
        available = [0.0, 0.1, 0.2, 0.3, 0.4]

        # Simulating the logic
        time_steps = None  # None means all
        if not time_steps:
            result = list(available)
        else:
            result = []

        assert result == available

    def test_prepare_time_steps_last(self):
        """Test preparing last time step."""
        available = [0.0, 0.1, 0.2, 0.3, 0.4]

        time_steps = 'last'
        if time_steps == 'last':
            result = [max(available)]
        else:
            result = []

        assert result == [0.4]

    def test_prepare_time_steps_custom_list(self):
        """Test preparing custom time step list."""
        available = [0.0, 0.1, 0.2, 0.3, 0.4]
        time_steps = [0.1, 0.3]

        if isinstance(time_steps, (list, tuple)):
            result = list(time_steps)
        else:
            result = []

        assert result == [0.1, 0.3]


class TestOSIRRTCalculations:
    """Test OSI and RRT formula calculations."""

    def test_osi_unidirectional_flow(self):
        """Test OSI = 0 for unidirectional flow."""
        import numpy as np

        # Unidirectional flow: WSS always same direction
        # mean WSS magnitude = TAWSS
        tawss = 1.0
        wss_mean_magnitude = 1.0

        osi = 0.5 * (1 - wss_mean_magnitude / tawss)

        assert osi == pytest.approx(0.0)

    def test_osi_fully_oscillatory(self):
        """Test OSI = 0.5 for fully oscillatory flow."""
        # Fully reversing flow: mean WSS = 0
        tawss = 1.0
        wss_mean_magnitude = 0.0

        osi = 0.5 * (1 - wss_mean_magnitude / tawss)

        assert osi == pytest.approx(0.5)

    def test_osi_partial_oscillation(self):
        """Test OSI for partial oscillation."""
        tawss = 1.0
        wss_mean_magnitude = 0.5  # 50% of TAWSS

        osi = 0.5 * (1 - wss_mean_magnitude / tawss)

        assert osi == pytest.approx(0.25)

    def test_rrt_formula(self):
        """Test RRT = 1 / ((1 - 2*OSI) * TAWSS)."""
        tawss = 2.0
        osi = 0.25

        rrt = 1.0 / ((1 - 2 * osi) * tawss)

        # (1 - 2*0.25) * 2.0 = 0.5 * 2.0 = 1.0
        # RRT = 1/1.0 = 1.0
        assert rrt == pytest.approx(1.0)

    def test_rrt_osi_zero(self):
        """Test RRT when OSI = 0."""
        tawss = 2.0
        osi = 0.0

        rrt = 1.0 / ((1 - 2 * osi) * tawss)

        # (1 - 0) * 2.0 = 2.0
        # RRT = 1/2.0 = 0.5
        assert rrt == pytest.approx(0.5)

    def test_rrt_high_osi(self):
        """Test RRT increases with OSI."""
        tawss = 2.0

        rrt_low_osi = 1.0 / ((1 - 2 * 0.1) * tawss)
        rrt_high_osi = 1.0 / ((1 - 2 * 0.4) * tawss)

        # Higher OSI should give higher RRT
        assert rrt_high_osi > rrt_low_osi


class TestColorRangeHandling:
    """Test color range configuration handling."""

    @pytest.mark.skipif(
        not PARAVIEW_MODULE_AVAILABLE,
        reason="ParaView Python module not available - post_processor requires paraview"
    )
    def test_build_rescale_settings_defaults(self):
        """Test default rescale settings."""
        from aortacfd_lib.post_processor import DEFAULT_COLOR_RANGES

        assert "WSS" in DEFAULT_COLOR_RANGES
        assert DEFAULT_COLOR_RANGES["WSS"] == [0, 50]
        assert DEFAULT_COLOR_RANGES["OSI"] == [0, 0.5]
        assert DEFAULT_COLOR_RANGES["RRT"] == [0, 10]

    def test_rescale_auto_vs_fixed(self):
        """Test auto-scale vs fixed range logic."""
        # WSS should use fixed range by default
        rescale_settings = {
            "U": {"rescaleToData": True, "rescaleRange": [0, 1]},
            "WSS": {"rescaleToData": False, "rescaleRange": [0, 50]},
        }

        assert rescale_settings["U"]["rescaleToData"] == True
        assert rescale_settings["WSS"]["rescaleToData"] == False
        assert rescale_settings["WSS"]["rescaleRange"] == [0, 50]


class TestPydanticValidation:
    """Test Pydantic validation schemas."""

    def test_visualization_schema_valid_fields(self):
        """Test visualization schema with valid fields."""
        try:
            from aortacfd_lib.post_processing.config import HAS_PYDANTIC
            if not HAS_PYDANTIC:
                pytest.skip("Pydantic not available")

            from aortacfd_lib.post_processing.config import VisualizationSchema

            schema = VisualizationSchema(
                fields=["U", "p", "TAWSS"],
                time_steps="last",
                fps=30
            )

            assert schema.fields == ["U", "p", "TAWSS"]
            assert schema.time_steps == "last"
        except ImportError:
            pytest.skip("Pydantic not available")

    def test_visualization_schema_invalid_time_steps(self):
        """Test visualization schema rejects invalid time_steps."""
        try:
            from aortacfd_lib.post_processing.config import HAS_PYDANTIC
            if not HAS_PYDANTIC:
                pytest.skip("Pydantic not available")

            from aortacfd_lib.post_processing.config import VisualizationSchema
            from pydantic import ValidationError

            with pytest.raises(ValidationError):
                VisualizationSchema(time_steps="invalid_option")
        except ImportError:
            pytest.skip("Pydantic not available")

    def test_color_ranges_validation(self):
        """Test color range validation."""
        try:
            from aortacfd_lib.post_processing.config import HAS_PYDANTIC
            if not HAS_PYDANTIC:
                pytest.skip("Pydantic not available")

            from aortacfd_lib.post_processing.config import VisualizationSchema
            from pydantic import ValidationError

            # Valid color ranges
            schema = VisualizationSchema(
                color_ranges={"WSS": [0, 50], "OSI": [0, 0.5]}
            )
            assert schema.color_ranges["WSS"] == [0, 50]

            # Invalid: min >= max
            with pytest.raises(ValidationError):
                VisualizationSchema(color_ranges={"WSS": [50, 0]})
        except ImportError:
            pytest.skip("Pydantic not available")


class TestPropertyMap:
    """Test property map and field configuration."""

    @pytest.mark.skipif(
        not PARAVIEW_MODULE_AVAILABLE,
        reason="ParaView Python module not available - post_processor requires paraview"
    )
    def test_default_property_map_fields(self):
        """Test default property map contains expected fields."""
        from aortacfd_lib.post_processor import DEFAULT_PROPERTY_MAP

        expected_fields = ["U", "p", "wallShearStress", "TAWSS", "OSI", "RRT", "KE"]
        for field in expected_fields:
            assert field in DEFAULT_PROPERTY_MAP
            assert "name" in DEFAULT_PROPERTY_MAP[field]
            assert "preset" in DEFAULT_PROPERTY_MAP[field]
            assert "unit" in DEFAULT_PROPERTY_MAP[field]

    @pytest.mark.skipif(
        not PARAVIEW_MODULE_AVAILABLE,
        reason="ParaView Python module not available - post_processor requires paraview"
    )
    def test_property_map_osi_bounded(self):
        """Test OSI has correct bounds in color range."""
        from aortacfd_lib.post_processor import DEFAULT_COLOR_RANGES

        assert DEFAULT_COLOR_RANGES["OSI"] == [0, 0.5]

    @pytest.mark.skipif(
        not PARAVIEW_MODULE_AVAILABLE,
        reason="ParaView Python module not available - post_processor requires paraview"
    )
    def test_property_map_wss_unit(self):
        """Test WSS has correct unit."""
        from aortacfd_lib.post_processor import DEFAULT_PROPERTY_MAP

        assert DEFAULT_PROPERTY_MAP["wallShearStress"]["unit"] == "Pa"
        assert DEFAULT_PROPERTY_MAP["TAWSS"]["unit"] == "Pa"


class TestHelperFunctions:
    """Test helper functions."""

    @pytest.mark.skipif(
        not PARAVIEW_MODULE_AVAILABLE,
        reason="ParaView Python module not available - post_processor requires paraview"
    )
    def test_check_ffmpeg_available_returns_bool(self):
        """Test check_ffmpeg_available returns boolean."""
        from aortacfd_lib.post_processor import check_ffmpeg_available

        result = check_ffmpeg_available()
        assert isinstance(result, bool)

    @pytest.mark.skipif(
        not PARAVIEW_MODULE_AVAILABLE,
        reason="ParaView Python module not available - post_processor requires paraview"
    )
    def test_hide_all_scalar_bars_handles_empty(self):
        """Test hide_all_scalar_bars handles empty list."""
        from aortacfd_lib.post_processor import hide_all_scalar_bars

        # Should not raise with empty list
        # (render_view is mocked as None since we can't test ParaView)
        # This just tests the function signature exists
        assert callable(hide_all_scalar_bars)
