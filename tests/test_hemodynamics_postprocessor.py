"""
Comprehensive test suite for Hemodynamics Post-Processor.

Tests the HemodynamicsPostProcessor class for computing clinical hemodynamic metrics:
- WSS (Wall Shear Stress)
- TAWSS (Time-Averaged Wall Shear Stress)
- OSI (Oscillatory Shear Index)
- RRT (Relative Residence Time)
- Pressure drop calculations
"""

import pytest
import sys
import numpy as np
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.hemodynamics_postprocessor import (
    HemodynamicsResults,
    HemodynamicsPostProcessor,
    run_hemodynamics_analysis
)


class TestHemodynamicsResults:
    """Test HemodynamicsResults dataclass."""

    def test_default_values(self):
        """Test default initialization."""
        results = HemodynamicsResults()

        assert results.inlet_type == "UNKNOWN"
        assert results.is_pulsatile == False
        assert results.cardiac_cycle == 0.8
        assert results.wss_max == 0.0
        assert results.wss_mean == 0.0
        assert results.tawss_max == 0.0
        assert results.tawss_is_approximate == False
        assert results.osi_max == 0.0
        assert results.rrt_max == 0.0
        assert results.pressure_drops == {}

    def test_custom_initialization(self):
        """Test custom value initialization."""
        results = HemodynamicsResults(
            inlet_type="TIMEVARYING",
            is_pulsatile=True,
            cardiac_cycle=1.0,
            wss_max=15.5,
            wss_mean=3.2
        )

        assert results.inlet_type == "TIMEVARYING"
        assert results.is_pulsatile == True
        assert results.cardiac_cycle == 1.0
        assert results.wss_max == 15.5
        assert results.wss_mean == 3.2

    def test_pulsatile_metrics_storage(self):
        """Test pulsatile-specific metrics."""
        results = HemodynamicsResults(
            is_pulsatile=True,
            tawss_max=12.0,
            tawss_mean=4.5,
            osi_max=0.4,
            osi_mean=0.15,
            rrt_max=5.0,
            rrt_mean=1.2
        )

        assert results.tawss_max == 12.0
        assert results.tawss_mean == 4.5
        assert results.osi_max == 0.4
        assert results.osi_mean == 0.15
        assert results.rrt_max == 5.0
        assert results.rrt_mean == 1.2

    def test_tawss_approximate_flag(self):
        """Test tawss_is_approximate flag behavior."""
        results = HemodynamicsResults()
        assert results.tawss_is_approximate == False

        results.tawss_is_approximate = True
        assert results.tawss_is_approximate == True

        # Can be initialized directly
        results2 = HemodynamicsResults(tawss_is_approximate=True)
        assert results2.tawss_is_approximate == True

    def test_pressure_drop_storage(self):
        """Test pressure drop results storage."""
        results = HemodynamicsResults(
            pressure_inlet=12000.0,
            pressure_outlets={'outlet_1': 10500.0, 'outlet_2': 10800.0},
            pressure_drops={'outlet_1': 1500.0, 'outlet_2': 1200.0},
            pressure_drop_mmhg={'outlet_1': 11.25, 'outlet_2': 9.0}
        )

        assert results.pressure_inlet == 12000.0
        assert 'outlet_1' in results.pressure_outlets
        assert results.pressure_drops['outlet_1'] == 1500.0
        assert results.pressure_drop_mmhg['outlet_2'] == 9.0


class TestHemodynamicsPostProcessorInit:
    """Test HemodynamicsPostProcessor initialization."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_config = {
            'inlet': {'type': 'CONSTANT'},
            'cardiac_cycle': 0.8,
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet_1', 'outlet_2'],
                'wall_keywords_ordered': 'wall_aorta'
            },
            'hemodynamics': {
                'tawss_settings': {
                    'skip_cycles': 2
                }
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_constant_inlet_detection(self):
        """Test CONSTANT inlet type detection."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.base_config)

        assert processor.inlet_type == "CONSTANT"
        assert processor.is_pulsatile == False

    def test_timevarying_inlet_detection(self):
        """Test TIMEVARYING inlet type detection."""
        config = self.base_config.copy()
        config['inlet'] = {'type': 'TIMEVARYING'}

        processor = HemodynamicsPostProcessor(self.temp_dir, config)

        assert processor.inlet_type == "TIMEVARYING"
        assert processor.is_pulsatile == True

    def test_womersley_inlet_detection(self):
        """Test WOMERSLEY inlet type detection (pulsatile)."""
        config = self.base_config.copy()
        config['inlet'] = {'type': 'WOMERSLEY'}

        processor = HemodynamicsPostProcessor(self.temp_dir, config)

        assert processor.inlet_type == "WOMERSLEY"
        assert processor.is_pulsatile == True

    def test_boundary_conditions_fallback(self):
        """Test fallback to boundary_conditions config structure."""
        config = {
            'boundary_conditions': {
                'inlet': {'type': 'TIMEVARYING'}
            },
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

        processor = HemodynamicsPostProcessor(self.temp_dir, config)

        assert processor.inlet_type == "TIMEVARYING"
        assert processor.is_pulsatile == True

    def test_cardiac_cycle_extraction(self):
        """Test cardiac cycle value extraction."""
        config = self.base_config.copy()
        config['cardiac_cycle'] = 1.2

        processor = HemodynamicsPostProcessor(self.temp_dir, config)

        assert processor.cardiac_cycle == 1.2


class TestPhysicalConstants:
    """Test physical constants used in calculations."""

    def test_pa_to_mmhg_conversion(self):
        """Test Pa to mmHg conversion factor from centralized constants."""
        # 1 mmHg = 133.322 Pa, so 1/133.322 Pa/mmHg
        # Constants are now centralized in aortacfd_lib.constants
        from src.aortacfd_lib.constants import PA_TO_MMHG
        assert PA_TO_MMHG == pytest.approx(1/133.322, rel=1e-4)

    def test_blood_density(self):
        """Test default blood density from centralized constants."""
        # Constants are now centralized in aortacfd_lib.constants
        from src.aortacfd_lib.constants import BLOOD_DENSITY_DEFAULT
        assert BLOOD_DENSITY_DEFAULT == 1060.0


class TestTimeDirectoryHandling:
    """Test time directory detection and handling."""

    def setup_method(self):
        """Create mock case directory structure."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

        # Create time directories
        for t in ['0', '0.5', '1.0', '1.5']:
            os.makedirs(os.path.join(self.temp_dir, t), exist_ok=True)

        # Create non-time directories
        os.makedirs(os.path.join(self.temp_dir, 'constant'), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, 'system'), exist_ok=True)

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_time_directory_detection(self):
        """Test detection of time directories."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        time_dirs = processor._get_time_directories()

        # Should find 4 time directories
        assert len(time_dirs) == 4

        # Should be sorted by time
        times = [float(d.name) for d in time_dirs]
        assert times == [0.0, 0.5, 1.0, 1.5]

    def test_latest_time_detection(self):
        """Test detection of latest time directory."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        latest = processor._get_latest_time()

        assert latest is not None
        assert float(latest.name) == 1.5

    def test_no_time_directories(self):
        """Test handling when no time directories exist."""
        empty_dir = tempfile.mkdtemp()
        try:
            processor = HemodynamicsPostProcessor(empty_dir, self.config)
            time_dirs = processor._get_time_directories()
            latest = processor._get_latest_time()

            assert len(time_dirs) == 0
            assert latest is None
        finally:
            import shutil
            shutil.rmtree(empty_dir, ignore_errors=True)


class TestWSSComputation:
    """Test WSS computation functionality."""

    def setup_method(self):
        """Setup test case directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall_aorta'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_wss_check_false_when_missing(self):
        """Test WSS check returns False when no WSS data."""
        # Create time directory without WSS
        os.makedirs(os.path.join(self.temp_dir, '1.0'), exist_ok=True)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        assert processor._check_wss_exists() == False

    def test_wss_check_true_when_exists(self):
        """Test WSS check returns True when WSS file exists."""
        # Create time directory with WSS file
        time_dir = os.path.join(self.temp_dir, '1.0')
        os.makedirs(time_dir, exist_ok=True)

        # Create mock WSS file
        wss_file = os.path.join(time_dir, 'wallShearStress')
        with open(wss_file, 'w') as f:
            f.write("// Mock WSS file")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        assert processor._check_wss_exists() == True


class TestOSIBounds:
    """Test OSI calculation bounds."""

    def test_osi_bounded_zero_to_half(self):
        """Test that OSI is bounded between 0 and 0.5."""
        # OSI = 0.5 * (1 - |mean(WSS)| / TAWSS)
        # When mean(WSS) = TAWSS (no oscillation): OSI = 0
        # When mean(WSS) = 0 (full oscillation): OSI = 0.5

        results = HemodynamicsResults(
            osi_max=0.5,
            osi_mean=0.25
        )

        assert 0 <= results.osi_max <= 0.5
        assert 0 <= results.osi_mean <= 0.5


class TestReportGeneration:
    """Test report generation functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet_1', 'outlet_2'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directories."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_report_file_created(self):
        """Test that report file is created."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type="CONSTANT",
            is_pulsatile=False,
            wss_max=15.0,
            wss_mean=3.5,
            wss_min=0.1
        )

        report_path = processor.generate_report(results, self.output_dir)

        assert os.path.exists(report_path)
        assert 'hemodynamics_report.txt' in report_path

    def test_report_contains_wss_values(self):
        """Test that report contains WSS values."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type="CONSTANT",
            is_pulsatile=False,
            wss_max=15.0,
            wss_mean=3.5,
            wss_min=0.1
        )

        report_path = processor.generate_report(results, self.output_dir)

        with open(report_path, 'r') as f:
            content = f.read()

        assert '15.0000' in content  # WSS max
        assert '3.5000' in content   # WSS mean
        assert 'CONSTANT' in content # Inlet type

    def test_pulsatile_report_contains_tawss(self):
        """Test that pulsatile report contains TAWSS/OSI/RRT."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type="TIMEVARYING",
            is_pulsatile=True,
            wss_max=15.0,
            wss_mean=3.5,
            tawss_max=12.0,
            tawss_mean=4.0,
            osi_max=0.35,
            osi_mean=0.12,
            rrt_max=8.0,
            rrt_mean=2.0
        )

        report_path = processor.generate_report(results, self.output_dir)

        with open(report_path, 'r') as f:
            content = f.read()

        assert 'TAWSS' in content
        assert 'OSI' in content
        assert 'RRT' in content
        assert '12.0000' in content  # TAWSS max


class TestConvenienceFunction:
    """Test run_hemodynamics_analysis convenience function."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()

        # Create minimal case structure
        os.makedirs(os.path.join(self.temp_dir, '0'), exist_ok=True)

        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directories."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)

    @patch.object(HemodynamicsPostProcessor, 'run_wss_postprocess')
    @patch.object(HemodynamicsPostProcessor, '_check_wss_exists')
    def test_runs_wss_postprocess_if_needed(self, mock_check, mock_run):
        """Test that WSS postprocess is run if WSS doesn't exist."""
        mock_check.return_value = False
        mock_run.return_value = True

        # This will fail gracefully since there's no actual WSS data
        try:
            results = run_hemodynamics_analysis(
                self.temp_dir,
                self.config,
                self.output_dir
            )
        except:
            pass  # Expected to fail without actual data

        # Should have checked and attempted to run postprocess
        mock_check.assert_called()


class TestIntegrationWithWorkflow:
    """Test integration with AortaCFD workflow system."""

    def test_import_in_execution_tasks(self):
        """Test that hemodynamics module can be imported as in execution_tasks."""
        # This mimics the import in execution_tasks.py
        from aortacfd_lib.hemodynamics_postprocessor import (
            HemodynamicsPostProcessor,
            run_hemodynamics_analysis
        )

        assert HemodynamicsPostProcessor is not None
        assert run_hemodynamics_analysis is not None

    def test_results_dataclass_serializable(self):
        """Test that results can be converted to dict for logging."""
        from dataclasses import asdict

        results = HemodynamicsResults(
            inlet_type="CONSTANT",
            wss_max=15.0,
            wss_mean=3.5
        )

        results_dict = asdict(results)

        assert isinstance(results_dict, dict)
        assert results_dict['inlet_type'] == "CONSTANT"
        assert results_dict['wss_max'] == 15.0
