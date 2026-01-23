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
        with patch('aortacfd_lib.post_processing.cli.check_dependencies') as mock_check:
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
