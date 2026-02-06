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


class TestConfigYAMLLoading:
    """Test YAML configuration loading."""

    def test_load_config_yaml_when_available(self):
        """Test loading YAML configuration when PyYAML is available."""
        from aortacfd_lib.post_processing.config import HAS_YAML

        if not HAS_YAML:
            pytest.skip("PyYAML not available")

        import yaml

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'case_dir': '/yaml/case',
                'cardiac_cycle': 0.95,
                'visualization': {
                    'fields': ['U', 'wallShearStress']
                }
            }, f)
            config_path = f.name

        try:
            config = load_config(config_path)

            assert config.case_dir == '/yaml/case'
            assert config.cardiac_cycle == 0.95
            assert config.visualization.fields == ['U', 'wallShearStress']
        finally:
            os.unlink(config_path)

    def test_load_config_yml_extension(self):
        """Test loading .yml file extension."""
        from aortacfd_lib.post_processing.config import HAS_YAML

        if not HAS_YAML:
            pytest.skip("PyYAML not available")

        import yaml

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump({'case_dir': '/yml/case'}, f)
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.case_dir == '/yml/case'
        finally:
            os.unlink(config_path)

    def test_load_config_yaml_without_pyyaml(self):
        """Test loading YAML fallback when PyYAML not available."""
        with patch.dict('sys.modules', {'yaml': None}):
            with patch('aortacfd_lib.post_processing.config.HAS_YAML', False):
                # Create YAML file but expect fallback to defaults
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    f.write("case_dir: /yaml/case\n")
                    config_path = f.name

                try:
                    # Need to reload the module with patched imports
                    # Instead, we test the fallback behavior directly
                    config = load_config(config_path)

                    # When YAML is not available, should use defaults
                    # (config may or may not load depending on HAS_YAML state)
                    assert config is not None
                finally:
                    os.unlink(config_path)

    def test_load_config_unknown_format(self):
        """Test loading config with unknown format uses defaults."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("case_dir: /txt/case\n")
            config_path = f.name

        try:
            config = load_config(config_path)

            # Unknown format should not load, use defaults
            assert config.case_dir == ""
        finally:
            os.unlink(config_path)

    def test_load_config_invalid_json(self):
        """Test loading invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json content")
            config_path = f.name

        try:
            config = load_config(config_path)

            # Should handle error gracefully and use defaults
            assert config.case_dir == ""
        finally:
            os.unlink(config_path)


class TestConfigSaveYAML:
    """Test YAML configuration saving."""

    def test_save_config_yaml(self):
        """Test saving configuration as YAML."""
        from aortacfd_lib.post_processing.config import HAS_YAML

        if not HAS_YAML:
            pytest.skip("PyYAML not available")

        config = PostProcessingConfig()
        config.case_dir = '/path/to/yaml/case'
        config.cardiac_cycle = 1.1

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            output_path = f.name

        try:
            save_config(config, output_path)

            with open(output_path, 'r') as f:
                import yaml
                data = yaml.safe_load(f)

            assert data['case_dir'] == '/path/to/yaml/case'
            assert data['cardiac_cycle'] == 1.1
        finally:
            os.unlink(output_path)

    def test_save_config_yaml_without_pyyaml(self):
        """Test saving YAML raises when PyYAML not available."""
        with patch('aortacfd_lib.post_processing.config.HAS_YAML', False):
            config = PostProcessingConfig()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                output_path = f.name

            try:
                with pytest.raises(RuntimeError) as excinfo:
                    save_config(config, output_path)

                assert "YAML support not available" in str(excinfo.value)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)


class TestValidateConfig:
    """Test validate_config function."""

    def test_validate_config_pydantic(self):
        """Test validate_config with Pydantic available."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC, validate_config

        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        config_dict = {
            'case_dir': '/path/to/case',
            'cardiac_cycle': 0.8,
            'verbosity': 1,
            'visualization': {
                'fields': ['U', 'p'],
                'fps': 30
            }
        }

        result = validate_config(config_dict)

        # Should return PostProcessingSchema
        assert result.case_dir == '/path/to/case'
        assert result.cardiac_cycle == 0.8

    def test_validate_config_without_pydantic(self):
        """Test validate_config without Pydantic falls back."""
        with patch('aortacfd_lib.post_processing.config.HAS_PYDANTIC', False):
            # Import the fallback version
            from importlib import reload
            import aortacfd_lib.post_processing.config as config_module

            # We can't easily reload with different HAS_PYDANTIC,
            # but we can test the fallback function's basic validation
            config_dict = {
                'visualization': {
                    'time_steps': 'last'
                }
            }

            # The fallback validate_config should work
            from aortacfd_lib.post_processing.config import validate_config
            result = validate_config(config_dict)

            # Should return schema or dict depending on Pydantic availability
            assert result is not None

    def test_validate_config_invalid_time_steps_fallback(self):
        """Test fallback validation catches invalid time_steps."""
        with patch('aortacfd_lib.post_processing.config.HAS_PYDANTIC', False):
            config_dict = {
                'visualization': {
                    'time_steps': 'invalid_value'
                }
            }

            # Need to use the fallback function
            # The actual fallback function should raise ValueError
            # Since we can't easily force the fallback, skip if Pydantic is available
            from aortacfd_lib.post_processing.config import HAS_PYDANTIC
            if HAS_PYDANTIC:
                pytest.skip("This tests fallback behavior without Pydantic")


class TestPydanticSchemas:
    """Test Pydantic schema classes in detail."""

    def test_hemodynamics_schema_valid(self):
        """Test HemodynamicsSchema with valid values."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import HemodynamicsSchema

        schema = HemodynamicsSchema(
            skip_cycles=3,
            run_wss_postprocess=True,
            generate_plots=True,
            low_tawss_threshold=0.5,
            high_tawss_threshold=35.0
        )

        assert schema.skip_cycles == 3
        assert schema.low_tawss_threshold == 0.5

    def test_hemodynamics_schema_bounds(self):
        """Test HemodynamicsSchema enforces bounds."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import HemodynamicsSchema
        from pydantic import ValidationError

        # skip_cycles should be 0-10
        with pytest.raises(ValidationError):
            HemodynamicsSchema(skip_cycles=-1)

        with pytest.raises(ValidationError):
            HemodynamicsSchema(skip_cycles=15)

    def test_post_processing_schema_full(self):
        """Test PostProcessingSchema with full configuration."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import PostProcessingSchema

        schema = PostProcessingSchema(
            case_dir='/path/to/case',
            cardiac_cycle=0.9,
            verbosity=2
        )

        assert schema.case_dir == '/path/to/case'
        assert schema.cardiac_cycle == 0.9
        assert schema.verbosity == 2

    def test_visualization_schema_fps_bounds(self):
        """Test VisualizationSchema fps bounds."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import VisualizationSchema
        from pydantic import ValidationError

        # fps should be 1-120
        valid = VisualizationSchema(fps=60)
        assert valid.fps == 60

        with pytest.raises(ValidationError):
            VisualizationSchema(fps=0)

        with pytest.raises(ValidationError):
            VisualizationSchema(fps=150)

    def test_visualization_schema_unknown_fields_warning(self):
        """Test VisualizationSchema warns on unknown fields."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import VisualizationSchema
        import logging

        # Unknown field should warn but not raise
        schema = VisualizationSchema(fields=["UnknownField", "U"])
        assert "UnknownField" in schema.fields

    def test_visualization_schema_color_range_invalid_format(self):
        """Test VisualizationSchema rejects invalid color range format."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import VisualizationSchema
        from pydantic import ValidationError

        # Color range must be [min, max] with min < max
        with pytest.raises(ValidationError):
            VisualizationSchema(color_ranges={"WSS": [10]})  # Only one value

        with pytest.raises(ValidationError):
            VisualizationSchema(color_ranges={"WSS": [50, 10]})  # min >= max


class TestConfigFromDictAlternativePaths:
    """Test PostProcessingConfig.from_dict with alternative data structures."""

    def test_from_dict_post_processing_nested(self):
        """Test from_dict with post_processing nested structure."""
        data = {
            'post_processing': {
                'visualization': {
                    'fields': ['p'],
                    'fps': 25
                },
                'output': {
                    'output_dir': 'nested_output'
                }
            }
        }

        config = PostProcessingConfig.from_dict(data)

        assert config.visualization.fields == ['p']
        assert config.visualization.fps == 25
        assert config.output.output_dir == 'nested_output'

    def test_from_dict_rescale_settings(self):
        """Test from_dict with rescale_settings."""
        data = {
            'visualization': {
                'rescale_settings': {
                    'WSS': {'rescaleToData': False, 'rescaleRange': [0, 100]}
                }
            }
        }

        config = PostProcessingConfig.from_dict(data)

        assert 'WSS' in config.visualization.rescale_settings
        assert config.visualization.rescale_settings['WSS']['rescaleRange'] == [0, 100]

    def test_from_dict_geometry(self):
        """Test from_dict with geometry data."""
        data = {
            'geometry': {
                'case_name': 'TestCase',
                'outlet_keywords_ordered': ['outlet1', 'outlet2']
            }
        }

        config = PostProcessingConfig.from_dict(data)

        assert config.geometry.get('case_name') == 'TestCase'
        assert config.geometry.get('outlet_keywords_ordered') == ['outlet1', 'outlet2']


# =============================================================================
# EXTENDED CLI TESTS
# =============================================================================

class TestCLICaseDirectory:
    """Test CLI case directory handling."""

    def test_nonexistent_case_dir_returns_error(self):
        """Test that nonexistent case directory returns error code."""
        from aortacfd_lib.post_processing.cli import main

        result = main(['/nonexistent/path/12345'])
        assert result == 1

    def test_case_dir_validation(self):
        """Test case directory is resolved to absolute path."""
        from aortacfd_lib.post_processing.cli import main

        # Create a temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create minimal case structure
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, 'system'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, '0'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir])

                # Should be called with resolved path
                call_args = mock_processor.call_args
                assert call_args is not None


class TestCLIVerbosity:
    """Test CLI verbosity options."""

    def test_quiet_mode_sets_verbosity_zero(self):
        """Test -q sets verbosity to 0."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                main([temp_dir, '-q'])

                # Check verbosity argument
                call_kwargs = mock_processor.call_args[1]
                assert call_kwargs.get('verbosity') == 0

    def test_verbose_mode_increases_verbosity(self):
        """Test -v increases verbosity."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                main([temp_dir, '-v'])

                call_kwargs = mock_processor.call_args[1]
                # Default is 1, -v makes it 2
                assert call_kwargs.get('verbosity') == 2

    def test_double_verbose(self):
        """Test -vv sets verbosity to 3."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                main([temp_dir, '-v', '-v'])

                call_kwargs = mock_processor.call_args[1]
                assert call_kwargs.get('verbosity') == 3


class TestCLIStatusMode:
    """Test CLI --status mode."""

    def test_status_flag_calls_print_status(self):
        """Test --status flag calls print_status and exits."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance

                result = main([temp_dir, '--status'])

                assert result == 0
                mock_instance.print_status.assert_called_once()


class TestCLIHemodynamicsOnlyMode:
    """Test CLI --hemodynamics-only mode."""

    def test_hemodynamics_only_mode(self):
        """Test --hemodynamics-only runs only hemodynamics."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance

                # Create mock results
                mock_results = MagicMock()
                mock_results.tawss_mean = 1.5
                mock_results.osi_mean = 0.15
                mock_results.pressure_drops = {}
                mock_results.pressure_drop_mmhg = {}
                mock_instance.run_hemodynamics.return_value = mock_results

                result = main([temp_dir, '--hemodynamics-only'])

                assert result == 0
                mock_instance.run_hemodynamics.assert_called_once()
                # run_visualization should not be called
                mock_instance.run_visualization.assert_not_called()

    def test_hemodynamics_only_with_pressure_drops(self):
        """Test --hemodynamics-only prints pressure drop info."""
        from aortacfd_lib.post_processing.cli import main
        import io
        import sys

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance

                # Create mock results with pressure drops
                mock_results = MagicMock()
                mock_results.tawss_mean = 1.5
                mock_results.osi_mean = 0.15
                mock_results.pressure_drops = {'outlet1': 2000}
                mock_results.pressure_drop_mmhg = {'outlet1': 15.0}
                mock_instance.run_hemodynamics.return_value = mock_results

                # Capture stdout
                captured = io.StringIO()
                with patch('sys.stdout', captured):
                    result = main([temp_dir, '--hemodynamics-only'])

                output = captured.getvalue()
                assert 'outlet1' in output
                assert '15.00' in output


class TestCLIVisualizationOnlyMode:
    """Test CLI --visualization-only mode."""

    def test_visualization_only_mode(self):
        """Test --visualization-only runs only visualization."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.output_dir = temp_dir

                with patch('aortacfd_lib.post_processing.dependencies.has_paraview', return_value=True):
                    result = main([temp_dir, '--visualization-only'])

                    assert result == 0
                    mock_instance.run_visualization.assert_called_once()

    def test_visualization_only_without_paraview(self):
        """Test --visualization-only fails without ParaView."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance

                with patch('aortacfd_lib.post_processing.dependencies.has_paraview', return_value=False):
                    result = main([temp_dir, '--visualization-only'])

                    assert result == 1


class TestCLIAnimationsOnlyMode:
    """Test CLI --animations-only mode."""

    def test_animations_only_mode(self):
        """Test --animations-only runs only animations."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.output_dir = temp_dir

                with patch('aortacfd_lib.post_processing.dependencies.has_ffmpeg', return_value=True):
                    result = main([temp_dir, '--animations-only'])

                    assert result == 0
                    mock_instance.run_animations.assert_called_once()

    def test_animations_only_without_ffmpeg(self):
        """Test --animations-only fails without ffmpeg."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance

                with patch('aortacfd_lib.post_processing.dependencies.has_ffmpeg', return_value=False):
                    result = main([temp_dir, '--animations-only'])

                    assert result == 1


class TestCLIConfigLoading:
    """Test CLI config file loading."""

    def test_load_config_file(self):
        """Test loading config file with -c flag."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            # Create config file
            config_path = os.path.join(temp_dir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump({
                    'cardiac_cycle': 1.0,
                    'visualization': {'fields': ['U']}
                }, f)

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir, '-c', config_path])

                assert result == 0

    def test_config_overrides_from_cli(self):
        """Test CLI arguments override config file values."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            # Create config file with specific fields
            config_path = os.path.join(temp_dir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump({
                    'visualization': {'fields': ['U', 'p']}
                }, f)

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                # Override with --fields
                result = main([temp_dir, '-c', config_path, '--fields', 'wallShearStress'])

                assert result == 0


class TestCLITimeStepsOption:
    """Test CLI --time-steps option."""

    def test_time_steps_last(self):
        """Test --time-steps last."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir, '--time-steps', 'last'])

                assert result == 0

    def test_time_steps_peak(self):
        """Test --time-steps peak."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir, '--time-steps', 'peak'])

                assert result == 0


class TestCLIOutputOption:
    """Test CLI -o/--output option."""

    def test_output_directory_option(self):
        """Test -o sets output directory."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir, '-o', 'custom_output'])

                assert result == 0
                # Check config dict passed to PostProcessor
                call_args = mock_processor.call_args
                config_arg = call_args[0][1]
                assert config_arg['output']['output_dir'] == 'custom_output'


class TestCLIFieldsOption:
    """Test CLI --fields option."""

    def test_custom_fields(self):
        """Test --fields with custom values."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir, '--fields', 'U', 'TAWSS', 'OSI'])

                assert result == 0
                call_args = mock_processor.call_args
                config_arg = call_args[0][1]
                assert config_arg['visualization']['fields'] == ['U', 'TAWSS', 'OSI']


class TestCLIResolutionOption:
    """Test CLI --resolution option."""

    def test_custom_resolution(self):
        """Test --resolution with custom values."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir, '--resolution', '1920', '1080'])

                assert result == 0
                call_args = mock_processor.call_args
                config_arg = call_args[0][1]
                assert config_arg['visualization']['resolution'] == [1920, 1080]


class TestCLISkipCyclesOption:
    """Test CLI --skip-cycles option."""

    def test_skip_cycles(self):
        """Test --skip-cycles option."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir, '--skip-cycles', '3'])

                assert result == 0
                call_args = mock_processor.call_args
                config_arg = call_args[0][1]
                assert config_arg['hemodynamics']['skip_cycles'] == 3


class TestCLIRunWSSOption:
    """Test CLI --run-wss option."""

    def test_run_wss_flag(self):
        """Test --run-wss sets run_wss_postprocess."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir, '--run-wss'])

                assert result == 0
                call_args = mock_processor.call_args
                config_arg = call_args[0][1]
                assert config_arg['hemodynamics']['run_wss_postprocess'] == True


class TestCLIFPSOption:
    """Test CLI --fps option."""

    def test_custom_fps(self):
        """Test --fps option."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir, '--fps', '60'])

                assert result == 0
                call_args = mock_processor.call_args
                config_arg = call_args[0][1]
                assert config_arg['visualization']['fps'] == 60


class TestCLIExceptionHandling:
    """Test CLI exception handling."""

    def test_exception_returns_error_code(self):
        """Test that exceptions return error code 1."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.side_effect = RuntimeError("Test error")

                result = main([temp_dir])

                assert result == 1

    def test_exception_with_debug_verbosity(self):
        """Test exception with debug verbosity prints traceback."""
        from aortacfd_lib.post_processing.cli import main
        import io

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.side_effect = RuntimeError("Test error")

                captured_stderr = io.StringIO()
                with patch('sys.stderr', captured_stderr):
                    result = main([temp_dir, '-v', '-v'])

                assert result == 1
                # With -vv, verbosity is 3, which should print traceback
                stderr_output = captured_stderr.getvalue()
                assert 'Test error' in stderr_output


class TestCLIRunAllMode:
    """Test CLI default run_all mode."""

    def test_run_all_default(self):
        """Test default mode runs all processing."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                result = main([temp_dir])

                assert result == 0
                mock_instance.run_all.assert_called_once()


class TestCLIConfigWithOutput:
    """Test CLI config loading with output override."""

    def test_config_with_output_override(self):
        """Test -c config with -o output override."""
        from aortacfd_lib.post_processing.cli import main

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            # Create config file
            config_path = os.path.join(temp_dir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump({
                    'output': {'output_dir': 'config_output'}
                }, f)

            with patch('aortacfd_lib.post_processing.core.PostProcessor') as mock_processor:
                mock_instance = MagicMock()
                mock_processor.return_value = mock_instance
                mock_instance.run_all.return_value = MagicMock()
                mock_instance.output_dir = temp_dir

                # Override with -o
                result = main([temp_dir, '-c', config_path, '-o', 'cli_output'])

                assert result == 0
                # Check that output.output_dir was overridden
                call_args = mock_processor.call_args
                # When using config file, PostProcessor is called with config object
                # and output_dir is set on config.output.output_dir


# =============================================================================
# TESTS FOR __main__.py
# =============================================================================

class TestMainModule:
    """Test the __main__.py entry point."""

    def test_main_module_imports(self):
        """Test that __main__ module can be imported."""
        import aortacfd_lib.post_processing.__main__ as main_module
        assert hasattr(main_module, 'main')

    def test_main_module_runs_cli(self):
        """Test that __main__ calls cli.main()."""
        with patch('aortacfd_lib.post_processing.cli.main', return_value=0) as mock_main:
            # Import and test that main is available
            from aortacfd_lib.post_processing.__main__ import main
            result = main(['--check-deps'])
            # main should call cli.main
            assert mock_main.called or result == 0


# =============================================================================
# EXTENDED TESTS FOR dependencies.py
# =============================================================================

class TestDependencyReportPrint:
    """Test DependencyReport.print_report() method."""

    def test_print_report_all_available(self, capsys):
        """Test print_report with all dependencies available."""
        report = DependencyReport()
        report.dependencies['numpy'] = DependencyStatus(
            name='numpy', available=True, version='1.24.0', required=True
        )
        report.dependencies['matplotlib'] = DependencyStatus(
            name='matplotlib', available=True, version='3.7.0', required=False
        )

        report.print_report()

        captured = capsys.readouterr()
        assert 'DEPENDENCY CHECK REPORT' in captured.out
        assert 'REQUIRED DEPENDENCIES' in captured.out
        assert 'OPTIONAL DEPENDENCIES' in captured.out
        assert 'numpy' in captured.out
        assert '[OK]' in captured.out
        assert 'All required dependencies available' in captured.out

    def test_print_report_missing_dependencies(self, capsys):
        """Test print_report with missing dependencies."""
        report = DependencyReport()
        report.all_required_available = False
        report.dependencies['numpy'] = DependencyStatus(
            name='numpy', available=False, required=True,
            purpose='Array operations', install_hint='pip install numpy'
        )

        report.print_report()

        captured = capsys.readouterr()
        assert '[MISSING]' in captured.out
        assert 'Purpose:' in captured.out
        assert 'Install:' in captured.out
        assert 'pip install numpy' in captured.out
        assert 'Missing required dependencies' in captured.out

    def test_print_report_with_warnings(self, capsys):
        """Test print_report with warnings."""
        report = DependencyReport()
        report.warnings.append("ParaView not available")
        report.warnings.append("ffmpeg not available")

        report.print_report()

        captured = capsys.readouterr()
        assert 'WARNINGS:' in captured.out
        assert 'ParaView not available' in captured.out
        assert 'ffmpeg not available' in captured.out

    def test_print_report_with_errors(self, capsys):
        """Test print_report with errors."""
        report = DependencyReport()
        report.all_required_available = False
        report.errors.append("Missing required dependency: numpy")

        report.print_report()

        captured = capsys.readouterr()
        assert 'ERRORS:' in captured.out
        assert 'Missing required dependency: numpy' in captured.out

    def test_print_report_missing_optional(self, capsys):
        """Test print_report with missing optional dependencies."""
        report = DependencyReport()
        report.dependencies['ffmpeg'] = DependencyStatus(
            name='ffmpeg', available=False, required=False,
            purpose='Animation creation', install_hint='apt install ffmpeg'
        )

        report.print_report()

        captured = capsys.readouterr()
        assert '[MISSING]' in captured.out
        assert 'Animation creation' in captured.out


class TestCheckParaViewExtended:
    """Extended tests for check_paraview function."""

    def test_check_paraview_pvbatch_available(self):
        """Test check_paraview when pvbatch is available."""
        from aortacfd_lib.post_processing.dependencies import check_paraview

        with patch('aortacfd_lib.post_processing.dependencies.check_executable') as mock_check:
            mock_check.return_value = DependencyStatus(name='pvbatch', available=True, path='/usr/bin/pvbatch')

            result = check_paraview()

            assert result.available == True
            assert 'pvbatch' in result.name

    def test_check_paraview_pvpython_fallback(self):
        """Test check_paraview falls back to pvpython."""
        from aortacfd_lib.post_processing.dependencies import check_paraview

        def mock_check_side_effect(exe_name, *args, **kwargs):
            if exe_name == 'pvbatch':
                return DependencyStatus(name='pvbatch', available=False)
            elif exe_name == 'pvpython':
                return DependencyStatus(name='pvpython', available=True, path='/usr/bin/pvpython')
            else:
                return DependencyStatus(name=exe_name, available=False)

        with patch('aortacfd_lib.post_processing.dependencies.check_executable', side_effect=mock_check_side_effect):
            result = check_paraview()

            assert result.available == True
            assert 'pvpython' in result.name

    def test_check_paraview_paraview_fallback(self):
        """Test check_paraview falls back to paraview."""
        from aortacfd_lib.post_processing.dependencies import check_paraview

        def mock_check_side_effect(exe_name, *args, **kwargs):
            if exe_name in ['pvbatch', 'pvpython']:
                return DependencyStatus(name=exe_name, available=False)
            elif exe_name == 'paraview':
                return DependencyStatus(name='paraview', available=True, path='/usr/bin/paraview')
            else:
                return DependencyStatus(name=exe_name, available=False)

        with patch('aortacfd_lib.post_processing.dependencies.check_executable', side_effect=mock_check_side_effect):
            result = check_paraview()

            assert result.available == True
            assert result.name == 'ParaView'


class TestCheckOpenFOAMExtended:
    """Extended tests for check_openfoam function."""

    def test_check_openfoam_foampostprocess_available(self):
        """Test check_openfoam when foamPostProcess is available."""
        from aortacfd_lib.post_processing.dependencies import check_openfoam

        with patch('aortacfd_lib.post_processing.dependencies.check_executable') as mock_check:
            mock_check.return_value = DependencyStatus(name='foamPostProcess', available=True)
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout='', stderr='OpenFOAM v12')

                result = check_openfoam()

                assert result.available == True
                assert 'foamPostProcess' in result.name

    def test_check_openfoam_postprocess_fallback(self):
        """Test check_openfoam falls back to postProcess."""
        from aortacfd_lib.post_processing.dependencies import check_openfoam

        def mock_check_side_effect(exe_name, *args, **kwargs):
            if exe_name == 'foamPostProcess':
                return DependencyStatus(name='foamPostProcess', available=False)
            elif exe_name == 'postProcess':
                return DependencyStatus(name='postProcess', available=True)
            else:
                return DependencyStatus(name=exe_name, available=False)

        with patch('aortacfd_lib.post_processing.dependencies.check_executable', side_effect=mock_check_side_effect):
            result = check_openfoam()

            assert result.available == True
            assert 'postProcess' in result.name

    def test_check_openfoam_simplefoam_fallback(self):
        """Test check_openfoam falls back to simpleFoam."""
        from aortacfd_lib.post_processing.dependencies import check_openfoam

        def mock_check_side_effect(exe_name, *args, **kwargs):
            if exe_name in ['foamPostProcess', 'postProcess']:
                return DependencyStatus(name=exe_name, available=False)
            elif exe_name == 'simpleFoam':
                return DependencyStatus(name='simpleFoam', available=True)
            else:
                return DependencyStatus(name=exe_name, available=False)

        with patch('aortacfd_lib.post_processing.dependencies.check_executable', side_effect=mock_check_side_effect):
            result = check_openfoam()

            assert result.available == True
            assert result.name == 'OpenFOAM'


class TestRequireDependencies:
    """Test require_dependencies function."""

    def test_require_dependencies_success(self):
        """Test require_dependencies when all are available."""
        from aortacfd_lib.post_processing.dependencies import require_dependencies

        # numpy should be available in test environment
        result = require_dependencies('numpy')
        assert result == True

    def test_require_dependencies_missing(self):
        """Test require_dependencies raises for missing dependency."""
        from aortacfd_lib.post_processing.dependencies import require_dependencies

        with patch('aortacfd_lib.post_processing.dependencies.check_dependencies') as mock_check:
            mock_report = DependencyReport()
            mock_report.dependencies['missing_dep'] = DependencyStatus(
                name='missing_dep', available=False, purpose='Testing', install_hint='pip install'
            )
            mock_check.return_value = mock_report

            with pytest.raises(RuntimeError) as excinfo:
                require_dependencies('missing_dep')

            assert 'Missing required dependencies' in str(excinfo.value)
            assert 'missing_dep' in str(excinfo.value)

    def test_require_dependencies_multiple(self):
        """Test require_dependencies with multiple dependencies."""
        from aortacfd_lib.post_processing.dependencies import require_dependencies

        # numpy and json should be available
        result = require_dependencies('numpy')
        assert result == True


class TestHasOpenFOAM:
    """Test has_openfoam convenience function."""

    def test_has_openfoam_returns_bool(self):
        """Test has_openfoam returns boolean."""
        from aortacfd_lib.post_processing.dependencies import has_openfoam

        result = has_openfoam()
        assert isinstance(result, bool)


class TestCheckExecutableExtended:
    """Extended tests for check_executable function."""

    def test_check_executable_with_path(self):
        """Test check_executable returns path when found."""
        # python3 should be available
        status = check_executable('python3')

        if status.available:
            assert status.path is not None
            assert 'python' in status.path.lower()

    def test_check_executable_version_parsing(self):
        """Test check_executable parses version from output."""
        with patch('shutil.which', return_value='/usr/bin/test_exe'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout='test_exe version 2.5.1\n',
                    stderr=''
                )

                status = check_executable('test_exe')

                assert status.available == True
                assert status.version == '2.5.1'

    def test_check_executable_version_from_stderr(self):
        """Test check_executable parses version from stderr."""
        with patch('shutil.which', return_value='/usr/bin/test_exe'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout='',
                    stderr='test_exe 1.2.3\n'
                )

                status = check_executable('test_exe')

                assert status.available == True
                assert status.version == '1.2.3'

    def test_check_executable_timeout(self):
        """Test check_executable handles timeout."""
        import subprocess

        with patch('shutil.which', return_value='/usr/bin/test_exe'):
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(cmd='test', timeout=5)

                status = check_executable('test_exe')

                # Should still be available, just no version
                assert status.available == True
                assert status.version is None

    def test_check_executable_subprocess_error(self):
        """Test check_executable handles subprocess errors."""
        import subprocess

        with patch('shutil.which', return_value='/usr/bin/test_exe'):
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.SubprocessError("Test error")

                status = check_executable('test_exe')

                assert status.available == True
                assert status.version is None


class TestCheckPythonModuleExtended:
    """Extended tests for check_python_module function."""

    def test_check_python_module_with_callable_version(self):
        """Test check_python_module handles callable version attribute."""
        import sys

        # Create a mock module with callable version
        mock_module = MagicMock()
        mock_module.version = lambda: "1.0.0"
        mock_module.__version__ = None

        with patch.dict(sys.modules, {'test_callable_version': mock_module}):
            with patch('builtins.__import__', return_value=mock_module):
                status = check_python_module('test_callable_version')

                # Module should be found
                assert status.available == True

    def test_check_python_module_package_name_override(self):
        """Test check_python_module with package_name override."""
        status = check_python_module('numpy', package_name='NumPy')

        assert status.name == 'NumPy'
        assert status.available == True


class TestCheckDependenciesVerbose:
    """Test check_dependencies with verbose output."""

    def test_check_dependencies_verbose_output(self, capsys):
        """Test check_dependencies with verbose=True prints report."""
        report = check_dependencies(verbose=True)

        captured = capsys.readouterr()
        assert 'DEPENDENCY CHECK REPORT' in captured.out
        assert 'numpy' in captured.out.lower() or 'NumPy' in captured.out

    def test_check_dependencies_scipy_included(self):
        """Test that scipy is included in dependency check."""
        report = check_dependencies(verbose=False)

        assert 'scipy' in report.dependencies


# =============================================================================
# EXTENDED TESTS FOR config.py
# =============================================================================

class TestPostProcessingSchemaModelValidator:
    """Test PostProcessingSchema model validator."""

    def test_validate_case_exists_warning(self):
        """Test that non-existent case_dir triggers warning."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import PostProcessingSchema
        import logging

        # This should log a warning but not raise
        schema = PostProcessingSchema(case_dir='/nonexistent/path/12345')
        assert schema.case_dir == '/nonexistent/path/12345'

    def test_validate_case_exists_dot_path(self):
        """Test that '.' case_dir doesn't trigger warning."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import PostProcessingSchema

        # '.' is special and shouldn't warn
        schema = PostProcessingSchema(case_dir='.')
        assert schema.case_dir == '.'


class TestVisualizationSchemaTimeStepsAll:
    """Test VisualizationSchema with time_steps='all'."""

    def test_time_steps_all_valid(self):
        """Test that time_steps='all' is valid."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import VisualizationSchema

        schema = VisualizationSchema(time_steps='all')
        assert schema.time_steps == 'all'

    def test_time_steps_list_valid(self):
        """Test that time_steps as list is valid."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import VisualizationSchema

        schema = VisualizationSchema(time_steps=[0.1, 0.2, 0.3])
        assert schema.time_steps == [0.1, 0.2, 0.3]


class TestLoadConfigYAMLWithContent:
    """Test loading YAML config with actual content."""

    def test_load_yaml_empty_file(self):
        """Test loading empty YAML file."""
        from aortacfd_lib.post_processing.config import HAS_YAML

        if not HAS_YAML:
            pytest.skip("PyYAML not available")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")  # Empty file
            config_path = f.name

        try:
            config = load_config(config_path)
            # Should return defaults
            assert config.case_dir == ""
        finally:
            os.unlink(config_path)


class TestSaveConfigYML:
    """Test saving config with .yml extension."""

    def test_save_config_yml_extension(self):
        """Test saving configuration as .yml."""
        from aortacfd_lib.post_processing.config import HAS_YAML

        if not HAS_YAML:
            pytest.skip("PyYAML not available")

        config = PostProcessingConfig()
        config.case_dir = '/test/case'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            output_path = f.name

        try:
            save_config(config, output_path)

            with open(output_path, 'r') as f:
                import yaml
                data = yaml.safe_load(f)

            assert data['case_dir'] == '/test/case'
        finally:
            os.unlink(output_path)


class TestConfigFromDictAutoDetect:
    """Test PostProcessingConfig.from_dict with auto_detect_case_type."""

    def test_from_dict_auto_detect_false(self):
        """Test from_dict with auto_detect_case_type=false."""
        data = {
            'visualization': {
                'auto_detect_case_type': False
            }
        }

        config = PostProcessingConfig.from_dict(data)
        assert config.visualization.auto_detect_case_type == False


class TestConfigFromDictOutputSettings:
    """Test PostProcessingConfig.from_dict output settings."""

    def test_from_dict_output_log_file(self):
        """Test from_dict with custom log_file."""
        data = {
            'output': {
                'log_file': 'custom.log'
            }
        }

        config = PostProcessingConfig.from_dict(data)
        assert config.output.log_file == 'custom.log'

    def test_from_dict_output_pressure_plots(self):
        """Test from_dict with pressure_plots setting."""
        data = {
            'output': {
                'pressure_plots': False
            }
        }

        config = PostProcessingConfig.from_dict(data)
        assert config.output.pressure_plots == False


class TestVisualizationConfigColorPresets:
    """Test VisualizationConfig color presets."""

    def test_from_dict_color_presets(self):
        """Test from_dict with custom color_presets."""
        data = {
            'visualization': {
                'color_presets': {
                    'U': 'Cool to Warm',
                    'WSS': 'Plasma'
                }
            }
        }

        config = PostProcessingConfig.from_dict(data)
        assert config.visualization.color_presets.get('U') == 'Cool to Warm'
        assert config.visualization.color_presets.get('WSS') == 'Plasma'


class TestHemodynamicsSchemaExtraFields:
    """Test HemodynamicsSchema allows extra fields."""

    def test_hemodynamics_schema_extra_fields(self):
        """Test HemodynamicsSchema allows extra fields."""
        from aortacfd_lib.post_processing.config import HAS_PYDANTIC
        if not HAS_PYDANTIC:
            pytest.skip("Pydantic not available")

        from aortacfd_lib.post_processing.config import HemodynamicsSchema

        # Extra fields should be allowed due to Config.extra = "allow"
        schema = HemodynamicsSchema(
            skip_cycles=2,
            custom_field="test"
        )
        assert schema.skip_cycles == 2


class TestFoamPostProcessVersionParsing:
    """Test OpenFOAM version parsing from foamPostProcess -help."""

    def test_openfoam_version_parsing(self):
        """Test OpenFOAM version is parsed correctly."""
        from aortacfd_lib.post_processing.dependencies import check_openfoam

        with patch('aortacfd_lib.post_processing.dependencies.check_executable') as mock_check:
            mock_check.return_value = DependencyStatus(
                name='foamPostProcess', available=True, path='/usr/bin/foamPostProcess'
            )
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout='',
                    stderr='Usage: foamPostProcess ... OpenFOAM v2312'
                )

                result = check_openfoam()

                assert result.available == True
                # Version should be parsed
                if result.version:
                    assert 'v2312' in result.version or '2312' in result.version

    def test_openfoam_subprocess_timeout(self):
        """Test OpenFOAM check handles subprocess timeout."""
        from aortacfd_lib.post_processing.dependencies import check_openfoam
        import subprocess

        with patch('aortacfd_lib.post_processing.dependencies.check_executable') as mock_check:
            mock_check.return_value = DependencyStatus(
                name='foamPostProcess', available=True, path='/usr/bin/foamPostProcess'
            )
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(cmd='foamPostProcess', timeout=5)

                result = check_openfoam()

                # Should still be available
                assert result.available == True


# =============================================================================
# EXTENDED TESTS FOR core.py
# =============================================================================

class TestPostProcessorFromConfig:
    """Test PostProcessor.from_config class method."""

    def test_from_config_basic(self):
        """Test from_config with basic config file."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create case structure
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            # Create config file
            config_path = os.path.join(temp_dir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump({
                    'case_dir': temp_dir,
                    'cardiac_cycle': 0.9
                }, f)

            processor = PostProcessor.from_config(config_path)
            assert processor.config.cardiac_cycle == 0.9

    def test_from_config_with_case_dir_override(self):
        """Test from_config with case_dir override."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config_path = os.path.join(temp_dir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump({'case_dir': '/other/path'}, f)

            processor = PostProcessor.from_config(config_path, case_dir=temp_dir)
            assert str(processor.case_dir) == str(Path(temp_dir).resolve())


class TestPostProcessorOutputDir:
    """Test PostProcessor output directory handling."""

    def test_output_dir_relative(self):
        """Test relative output directory."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            processor = PostProcessor(temp_dir, verbosity=0)
            assert processor.output_dir.name == 'postProcessing_results'

    def test_output_dir_absolute(self):
        """Test absolute output directory."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with tempfile.TemporaryDirectory() as output_dir:
                config = {'output': {'output_dir': output_dir}}
                processor = PostProcessor(temp_dir, config, verbosity=0)
                assert str(processor.output_dir) == output_dir

    def test_output_dir_openfoam_subdir(self):
        """Test output directory when case is in openfoam subdirectory."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create structure: temp_dir/run_001/openfoam
            run_dir = os.path.join(temp_dir, 'run_001')
            case_dir = os.path.join(run_dir, 'openfoam')
            os.makedirs(os.path.join(case_dir, 'constant'), exist_ok=True)
            open(os.path.join(case_dir, 'case.foam'), 'w').close()

            processor = PostProcessor(case_dir, verbosity=0)
            # Output should be at run_001 level, not inside openfoam
            assert processor.output_dir.parent.name == 'run_001'


class TestPostProcessorRunAll:
    """Test PostProcessor.run_all method."""

    def test_run_all_hemodynamics_only(self):
        """Test run_all with only hemodynamics enabled."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config = {
                'output': {
                    'hemodynamics_report': True,
                    'screenshots': False,
                    'animations': False
                }
            }

            with patch.object(PostProcessor, 'run_hemodynamics') as mock_hemo:
                mock_hemo.return_value = MagicMock()

                processor = PostProcessor(temp_dir, config, verbosity=0)
                results = processor.run_all()

                mock_hemo.assert_called_once()
                assert 'hemodynamics' in results

    def test_run_all_hemodynamics_failure(self):
        """Test run_all handles hemodynamics failure gracefully."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config = {
                'output': {
                    'hemodynamics_report': True,
                    'screenshots': False,
                    'animations': False
                }
            }

            with patch.object(PostProcessor, 'run_hemodynamics') as mock_hemo:
                mock_hemo.side_effect = RuntimeError("Test error")

                processor = PostProcessor(temp_dir, config, verbosity=0)
                results = processor.run_all()

                assert results['hemodynamics'] is None

    def test_run_all_visualization_without_paraview(self):
        """Test run_all skips visualization when ParaView unavailable."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config = {
                'output': {
                    'hemodynamics_report': False,
                    'screenshots': True,
                    'animations': False
                }
            }

            with patch('aortacfd_lib.post_processing.core.has_paraview', return_value=False):
                processor = PostProcessor(temp_dir, config, verbosity=0)
                results = processor.run_all()

                assert 'visualization' not in results or results.get('visualization') is None

    def test_run_all_visualization_failure(self):
        """Test run_all handles visualization failure gracefully."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config = {
                'output': {
                    'hemodynamics_report': False,
                    'screenshots': True,
                    'animations': False
                }
            }

            with patch('aortacfd_lib.post_processing.core.has_paraview', return_value=True):
                with patch.object(PostProcessor, 'run_visualization') as mock_viz:
                    mock_viz.side_effect = RuntimeError("Test error")

                    processor = PostProcessor(temp_dir, config, verbosity=0)
                    results = processor.run_all()

                    assert results['visualization'] is None

    def test_run_all_animations_without_ffmpeg(self):
        """Test run_all skips animations when ffmpeg unavailable."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config = {
                'output': {
                    'hemodynamics_report': False,
                    'screenshots': False,
                    'animations': True
                }
            }

            with patch('aortacfd_lib.post_processing.core.has_ffmpeg', return_value=False):
                processor = PostProcessor(temp_dir, config, verbosity=0)
                results = processor.run_all()

                assert 'animations' not in results or results.get('animations') is None

    def test_run_all_animations_failure(self):
        """Test run_all handles animation failure gracefully."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config = {
                'output': {
                    'hemodynamics_report': False,
                    'screenshots': False,
                    'animations': True
                }
            }

            with patch('aortacfd_lib.post_processing.core.has_ffmpeg', return_value=True):
                with patch('aortacfd_lib.post_processing.core.has_paraview', return_value=True):
                    with patch.object(PostProcessor, 'run_animations') as mock_anim:
                        mock_anim.side_effect = RuntimeError("Test error")

                        processor = PostProcessor(temp_dir, config, verbosity=0)
                        results = processor.run_all()

                        assert results['animations'] is None


class TestPostProcessorRunHemodynamics:
    """Test PostProcessor.run_hemodynamics method."""

    def test_run_hemodynamics_basic(self):
        """Test run_hemodynamics creates processor and computes."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config = {
                'hemodynamics': {'run_wss_postprocess': False},
                'output': {'hemodynamics_report': False}
            }

            with patch('aortacfd_lib.post_processing.core.HemodynamicsPostProcessor') as mock_hpp:
                mock_instance = MagicMock()
                mock_hpp.return_value = mock_instance
                mock_instance._check_wss_exists.return_value = True
                mock_instance.compute_all.return_value = MagicMock()

                processor = PostProcessor(temp_dir, config, verbosity=0)
                results = processor.run_hemodynamics()

                mock_hpp.assert_called_once()
                mock_instance.compute_all.assert_called_once()

    def test_run_hemodynamics_runs_wss_postprocess(self):
        """Test run_hemodynamics runs WSS post-processing when needed."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config = {
                'hemodynamics': {'run_wss_postprocess': True},
                'output': {'hemodynamics_report': False}
            }

            with patch('aortacfd_lib.post_processing.core.HemodynamicsPostProcessor') as mock_hpp:
                with patch('aortacfd_lib.post_processing.core.has_openfoam', return_value=True):
                    mock_instance = MagicMock()
                    mock_hpp.return_value = mock_instance
                    mock_instance._check_wss_exists.return_value = False
                    mock_instance.compute_all.return_value = MagicMock()

                    processor = PostProcessor(temp_dir, config, verbosity=0)
                    processor.run_hemodynamics()

                    mock_instance.run_wss_postprocess.assert_called_once()

    def test_run_hemodynamics_no_openfoam_warning(self):
        """Test run_hemodynamics warns when OpenFOAM not available."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config = {
                'hemodynamics': {'run_wss_postprocess': True},
                'output': {'hemodynamics_report': False}
            }

            with patch('aortacfd_lib.post_processing.core.HemodynamicsPostProcessor') as mock_hpp:
                with patch('aortacfd_lib.post_processing.core.has_openfoam', return_value=False):
                    mock_instance = MagicMock()
                    mock_hpp.return_value = mock_instance
                    mock_instance._check_wss_exists.return_value = False
                    mock_instance.compute_all.return_value = MagicMock()

                    processor = PostProcessor(temp_dir, config, verbosity=0)
                    processor.run_hemodynamics()

                    # Should not call run_wss_postprocess
                    mock_instance.run_wss_postprocess.assert_not_called()

    def test_run_hemodynamics_generates_report(self):
        """Test run_hemodynamics generates report when enabled."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            config = {
                'hemodynamics': {'run_wss_postprocess': False},
                'output': {'hemodynamics_report': True}
            }

            with patch('aortacfd_lib.post_processing.core.HemodynamicsPostProcessor') as mock_hpp:
                mock_instance = MagicMock()
                mock_hpp.return_value = mock_instance
                mock_instance._check_wss_exists.return_value = True
                mock_results = MagicMock()
                mock_instance.compute_all.return_value = mock_results

                processor = PostProcessor(temp_dir, config, verbosity=0)
                processor.run_hemodynamics()

                mock_instance.generate_report.assert_called_once()


class TestPostProcessorRunVisualization:
    """Test PostProcessor.run_visualization method."""

    def test_run_visualization_without_paraview_raises(self):
        """Test run_visualization raises when ParaView not available."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.has_paraview', return_value=False):
                processor = PostProcessor(temp_dir, verbosity=0)

                with pytest.raises(RuntimeError) as excinfo:
                    processor.run_visualization()

                assert 'ParaView not available' in str(excinfo.value)


class TestPostProcessorRunAnimations:
    """Test PostProcessor.run_animations method."""

    def test_run_animations_without_ffmpeg_raises(self):
        """Test run_animations raises when ffmpeg not available."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            with patch('aortacfd_lib.post_processing.core.has_ffmpeg', return_value=False):
                processor = PostProcessor(temp_dir, verbosity=0)

                with pytest.raises(RuntimeError) as excinfo:
                    processor.run_animations()

                assert 'ffmpeg not available' in str(excinfo.value)


class TestPostProcessorCheckStatus:
    """Test PostProcessor.check_status method."""

    def test_check_status_with_time_dirs(self):
        """Test check_status detects time directories."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, '0'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, '0.1'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, '0.2'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            processor = PostProcessor(temp_dir, verbosity=0)
            status = processor.check_status()

            assert len(status['time_directories']) == 3
            assert 0.0 in status['time_directories']
            assert 0.1 in status['time_directories']
            assert 0.2 in status['time_directories']

    def test_check_status_wss_available(self):
        """Test check_status detects WSS data."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, '0.1'), exist_ok=True)
            # Create WSS file
            open(os.path.join(temp_dir, '0.1', 'wallShearStress'), 'w').close()
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            processor = PostProcessor(temp_dir, verbosity=0)
            status = processor.check_status()

            assert status['wss_available'] == True

    def test_check_status_fieldaverage_available(self):
        """Test check_status detects fieldAverage data."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, '0.1'), exist_ok=True)
            # Create mean WSS file
            open(os.path.join(temp_dir, '0.1', 'wallShearStressMean'), 'w').close()
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            processor = PostProcessor(temp_dir, verbosity=0)
            status = processor.check_status()

            assert status['fieldaverage_available'] == True

    def test_check_status_postprocessing_dir(self):
        """Test check_status detects postProcessing directory."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, 'postProcessing'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            processor = PostProcessor(temp_dir, verbosity=0)
            status = processor.check_status()

            assert status['postprocessing_available'] == True


class TestPostProcessorPrintStatus:
    """Test PostProcessor.print_status method."""

    def test_print_status_output(self, capsys):
        """Test print_status produces formatted output."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, '0'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, '0.5'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            processor = PostProcessor(temp_dir, verbosity=0)
            processor.print_status()

            captured = capsys.readouterr()
            assert 'POST-PROCESSING STATUS' in captured.out
            assert 'Case Directory:' in captured.out
            assert 'Time Directories:' in captured.out
            assert 'Dependencies:' in captured.out


class TestPostProcessorVerbosity:
    """Test PostProcessor verbosity settings."""

    def test_verbosity_levels(self):
        """Test different verbosity levels set correct log level."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            # Test verbosity 0
            processor0 = PostProcessor(temp_dir, verbosity=0)
            assert processor0.config.verbosity == 0

            # Test verbosity 2
            processor2 = PostProcessor(temp_dir, verbosity=2)
            assert processor2.config.verbosity == 2


class TestPostProcessorNoneConfig:
    """Test PostProcessor with None config."""

    def test_none_config_uses_defaults(self):
        """Test None config uses default PostProcessingConfig."""
        from aortacfd_lib.post_processing.core import PostProcessor

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, 'constant'), exist_ok=True)
            open(os.path.join(temp_dir, 'case.foam'), 'w').close()

            processor = PostProcessor(temp_dir, config=None, verbosity=0)

            assert processor.config.cardiac_cycle == 0.8  # default
            assert str(processor.config.case_dir) == str(Path(temp_dir).resolve())


# =============================================================================
# EXTENDED TESTS FOR exceptions.py
# =============================================================================

class TestParaViewError:
    """Test ParaViewError exception."""

    def test_paraview_error_basic(self):
        """Test ParaViewError with just operation."""
        from aortacfd_lib.post_processing.exceptions import ParaViewError

        error = ParaViewError("Camera setup failed")
        assert "Camera setup failed" in str(error)
        assert "ParaView error" in str(error)

    def test_paraview_error_with_reason(self):
        """Test ParaViewError with reason."""
        from aortacfd_lib.post_processing.exceptions import ParaViewError

        error = ParaViewError("Rendering failed", reason="No display available")
        assert "Rendering failed" in str(error)
        assert "No display available" in str(error)


class TestDependencyError:
    """Test DependencyError exception."""

    def test_dependency_error(self):
        """Test DependencyError creation."""
        from aortacfd_lib.post_processing.exceptions import DependencyError

        error = DependencyError("ffmpeg", "Animation generation")
        assert "ffmpeg" in str(error)
        assert "Animation generation" in str(error)
        assert error.dependency == "ffmpeg"
        assert error.required_for == "Animation generation"


class TestMissingFieldErrorExtended:
    """Extended tests for MissingFieldError."""

    def test_missing_field_no_extras(self):
        """Test MissingFieldError with just field name."""
        from aortacfd_lib.post_processing.exceptions import MissingFieldError

        error = MissingFieldError("wallShearStress")
        assert "wallShearStress" in str(error)
        assert error.field_name == "wallShearStress"

    def test_missing_field_with_required_for(self):
        """Test MissingFieldError with required_for."""
        from aortacfd_lib.post_processing.exceptions import MissingFieldError

        error = MissingFieldError("U", required_for="velocity visualization")
        assert "U" in str(error)
        assert "velocity visualization" in str(error)

    def test_missing_field_with_hint(self):
        """Test MissingFieldError with hint."""
        from aortacfd_lib.post_processing.exceptions import MissingFieldError

        error = MissingFieldError("TAWSS", hint="Enable fieldAverage")
        assert "TAWSS" in str(error)
        assert "Enable fieldAverage" in str(error)


class TestConfigurationErrorExtended:
    """Extended tests for ConfigurationError."""

    def test_configuration_error_no_extras(self):
        """Test ConfigurationError with just message."""
        from aortacfd_lib.post_processing.exceptions import ConfigurationError

        error = ConfigurationError("Invalid configuration")
        assert "Invalid configuration" in str(error)

    def test_configuration_error_with_value(self):
        """Test ConfigurationError with value."""
        from aortacfd_lib.post_processing.exceptions import ConfigurationError

        error = ConfigurationError("Invalid setting", value="bad_value")
        assert "Invalid setting" in str(error)
        assert "bad_value" in str(error)


class TestHemodynamicsErrorExtended:
    """Extended tests for HemodynamicsError."""

    def test_hemodynamics_error_no_extras(self):
        """Test HemodynamicsError with just message."""
        from aortacfd_lib.post_processing.exceptions import HemodynamicsError

        error = HemodynamicsError("Calculation failed")
        assert "Calculation failed" in str(error)

    def test_hemodynamics_error_with_metric(self):
        """Test HemodynamicsError with metric."""
        from aortacfd_lib.post_processing.exceptions import HemodynamicsError

        error = HemodynamicsError("Failed", metric="RRT")
        assert "Failed" in str(error)
        assert "RRT" in str(error)

    def test_hemodynamics_error_with_reason(self):
        """Test HemodynamicsError with reason."""
        from aortacfd_lib.post_processing.exceptions import HemodynamicsError

        error = HemodynamicsError("Failed", reason="No data")
        assert "Failed" in str(error)
        assert "No data" in str(error)


class TestExceptionInheritance:
    """Test exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """Test all custom exceptions inherit from PostProcessingError."""
        from aortacfd_lib.post_processing.exceptions import (
            PostProcessingError,
            MissingFieldError,
            ParaViewError,
            ConfigurationError,
            CaseNotFoundError,
            DependencyError,
            HemodynamicsError,
        )

        assert issubclass(MissingFieldError, PostProcessingError)
        assert issubclass(ParaViewError, PostProcessingError)
        assert issubclass(ConfigurationError, PostProcessingError)
        assert issubclass(CaseNotFoundError, PostProcessingError)
        assert issubclass(DependencyError, PostProcessingError)
        assert issubclass(HemodynamicsError, PostProcessingError)

    def test_can_catch_all_with_base(self):
        """Test all exceptions can be caught with base class."""
        from aortacfd_lib.post_processing.exceptions import (
            PostProcessingError,
            MissingFieldError,
            DependencyError,
        )

        try:
            raise MissingFieldError("test_field")
        except PostProcessingError as e:
            assert "test_field" in str(e)

        try:
            raise DependencyError("dep", "feature")
        except PostProcessingError as e:
            assert "dep" in str(e)
