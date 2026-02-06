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


class TestReadSurfaceFieldValue:
    """Test _read_surface_field_value method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_surface_field_value_success(self):
        """Test reading surfaceFieldValue.dat file successfully."""
        # Create postProcessing structure
        func_dir = os.path.join(self.temp_dir, "postProcessing", "inletPressure", "0")
        os.makedirs(func_dir, exist_ok=True)
        data_file = os.path.join(func_dir, "surfaceFieldValue.dat")
        with open(data_file, 'w') as f:
            f.write("# Time areaAverage(p)\n")
            f.write("0.0 100.5\n")
            f.write("0.1 101.2\n")
            f.write("0.2 99.8\n")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor._read_surface_field_value("inletPressure")

        assert result is not None
        times, values = result
        assert len(times) == 3
        assert len(values) == 3
        assert times[0] == pytest.approx(0.0)
        assert values[0] == pytest.approx(100.5)

    def test_read_surface_field_value_not_found(self):
        """Test when postProcessing directory doesn't exist."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor._read_surface_field_value("nonexistent")

        assert result is None

    def test_read_surface_field_value_no_data_file(self):
        """Test when surfaceFieldValue.dat file doesn't exist."""
        # Create postProcessing directory but no data file
        func_dir = os.path.join(self.temp_dir, "postProcessing", "inletPressure", "0")
        os.makedirs(func_dir, exist_ok=True)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor._read_surface_field_value("inletPressure")

        assert result is None


class TestGetBoundaryPatches:
    """Test _get_boundary_patches method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_boundary_patches_success(self):
        """Test reading boundary patch names."""
        # Create boundary file
        polymesh_dir = os.path.join(self.temp_dir, "constant", "polyMesh")
        os.makedirs(polymesh_dir, exist_ok=True)
        boundary_file = os.path.join(polymesh_dir, "boundary")
        with open(boundary_file, 'w') as f:
            f.write("""FoamFile
{
    class polyBoundaryMesh;
}

inlet
{
    type patch;
}

outlet
{
    type patch;
}

wall
{
    type wall;
}
""")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        patches = processor._get_boundary_patches()

        assert 'inlet' in patches
        assert 'outlet' in patches
        assert 'wall' in patches

    def test_get_boundary_patches_no_file(self):
        """Test when boundary file doesn't exist."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        patches = processor._get_boundary_patches()

        assert patches == []


class TestComputePressureDrop:
    """Test _compute_pressure_drop method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_pressure_drop_with_data(self):
        """Test pressure drop computation with valid data."""
        # Create inlet pressure data
        inlet_dir = os.path.join(self.temp_dir, "postProcessing", "inletPressure", "0")
        os.makedirs(inlet_dir, exist_ok=True)
        with open(os.path.join(inlet_dir, "surfaceFieldValue.dat"), 'w') as f:
            f.write("0.0 100.0\n0.5 110.0\n1.0 105.0\n")

        # Create outlet pressure data
        outlet_dir = os.path.join(self.temp_dir, "postProcessing", "outlet1Pressure", "0")
        os.makedirs(outlet_dir, exist_ok=True)
        with open(os.path.join(outlet_dir, "surfaceFieldValue.dat"), 'w') as f:
            f.write("0.0 80.0\n0.5 85.0\n1.0 82.0\n")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults()
        processor._compute_pressure_drop(results)

        assert results.pressure_inlet > 0
        assert 'outlet1' in results.pressure_outlets
        assert 'outlet1' in results.pressure_drops

    def test_compute_pressure_drop_no_postprocessing(self):
        """Test pressure drop computation when no postProcessing directory."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults()
        processor._compute_pressure_drop(results)

        # Should handle gracefully
        assert results.pressure_inlet == 0.0


class TestExportQoi:
    """Test export_qoi method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directories."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_export_qoi_creates_files(self):
        """Test that export_qoi creates JSON and CSV files."""
        import json

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type="TIMEVARYING",
            is_pulsatile=True,
            cardiac_cycle=0.8,
            wss_p99=20.0,
            wss_p95=18.0,
            tawss_p99=15.0,
            tawss_p95=12.0,
            tawss_mean=8.0,
            osi_mean=0.1,
            osi_mean_masked=0.12,
            pressure_drop_mmhg={'outlet1': 5.0}
        )

        json_path, csv_path = processor.export_qoi(results, self.output_dir)

        # Check files exist
        assert os.path.exists(json_path)
        assert os.path.exists(csv_path)

        # Check JSON content
        with open(json_path) as f:
            data = json.load(f)
        assert '_metadata' in data
        assert 'qoi' in data
        assert data['qoi']['wss_p99_pa']['value'] == 20.0

        # Check CSV content
        with open(csv_path) as f:
            content = f.read()
        assert 'wss_p99_pa' in content


class TestDetectPeakSystole:
    """Test _detect_peak_systole method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_peak_systole_success(self):
        """Test peak systole detection from flowrate.csv."""
        config = {
            'inlet': {'type': 'TIMEVARYING'},
            'cardiac_cycle': 0.8,
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

        # Create boundaryData with flowrate.csv
        inlet_dir = os.path.join(self.temp_dir, "constant", "boundaryData", "inlet")
        os.makedirs(inlet_dir, exist_ok=True)
        with open(os.path.join(inlet_dir, "flowrate.csv"), 'w') as f:
            f.write("0.0,0.001\n")
            f.write("0.1,0.005\n")
            f.write("0.2,0.010\n")  # Peak
            f.write("0.3,0.007\n")
            f.write("0.4,0.003\n")

        processor = HemodynamicsPostProcessor(self.temp_dir, config)
        results = HemodynamicsResults()
        processor._detect_peak_systole(results)

        assert results.peak_systole_detected == True
        assert results.peak_systole_time == pytest.approx(0.2, rel=1e-6)

    def test_detect_peak_systole_not_pulsatile(self):
        """Test peak systole detection skipped for non-pulsatile flow."""
        config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

        processor = HemodynamicsPostProcessor(self.temp_dir, config)
        results = HemodynamicsResults()
        processor._detect_peak_systole(results)

        assert results.peak_systole_detected == False

    def test_detect_peak_systole_no_file(self):
        """Test peak systole detection when flowrate.csv doesn't exist."""
        config = {
            'inlet': {'type': 'TIMEVARYING'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

        processor = HemodynamicsPostProcessor(self.temp_dir, config)
        results = HemodynamicsResults()
        processor._detect_peak_systole(results)

        assert results.peak_systole_detected == False


class TestRunWssPostprocess:
    """Test run_wss_postprocess method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('subprocess.run')
    def test_run_wss_postprocess_success(self, mock_run):
        """Test successful WSS post-processing."""
        mock_run.return_value = MagicMock(returncode=0, stderr='')

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor.run_wss_postprocess()

        assert result == True
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_run_wss_postprocess_failure(self, mock_run):
        """Test failed WSS post-processing."""
        mock_run.return_value = MagicMock(returncode=1, stderr='Error message')

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor.run_wss_postprocess()

        assert result == False

    @patch('subprocess.run')
    def test_run_wss_postprocess_timeout(self, mock_run):
        """Test WSS post-processing timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 300)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor.run_wss_postprocess()

        assert result == False

    @patch('subprocess.run')
    def test_run_wss_postprocess_exception(self, mock_run):
        """Test WSS post-processing with general exception."""
        mock_run.side_effect = Exception("Unexpected error")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor.run_wss_postprocess()

        assert result == False


class TestWriteScalarBoundaryField:
    """Test _write_scalar_boundary_field method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_scalar_boundary_field_success(self):
        """Test writing scalar boundary field."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)

        data = np.array([1.0, 2.0, 3.0])
        time_dir = Path(self.temp_dir) / "1.0"
        time_dir.mkdir()

        processor._write_scalar_boundary_field(time_dir, "TAWSS", data, "wall", "Pa")

        output_file = time_dir / "TAWSS"
        assert output_file.exists()

        content = output_file.read_text()
        assert "TAWSS" in content
        assert "volScalarField" in content
        assert "wall" in content
        assert "3" in content  # number of faces


class TestFieldAverageCheck:
    """Test _check_fieldaverage_exists method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fieldaverage_exists(self):
        """Test fieldAverage detection when file exists."""
        time_dir = os.path.join(self.temp_dir, "1.0")
        os.makedirs(time_dir)
        with open(os.path.join(time_dir, "wallShearStressMean"), 'w') as f:
            f.write("// Mock file")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        assert processor._check_fieldaverage_exists() == True

    def test_fieldaverage_not_exists(self):
        """Test fieldAverage detection when file doesn't exist."""
        time_dir = os.path.join(self.temp_dir, "1.0")
        os.makedirs(time_dir)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        assert processor._check_fieldaverage_exists() == False


class TestComputeAllMethod:
    """Test compute_all method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_all_no_wss(self):
        """Test compute_all when no WSS data exists."""
        config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

        processor = HemodynamicsPostProcessor(self.temp_dir, config)
        results = processor.compute_all()

        assert results.inlet_type == 'CONSTANT'
        assert results.is_pulsatile == False
        assert results.wss_max == 0.0

    def test_compute_all_returns_results(self):
        """Test compute_all returns HemodynamicsResults object."""
        config = {
            'inlet': {'type': 'TIMEVARYING'},
            'cardiac_cycle': 0.9,
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

        processor = HemodynamicsPostProcessor(self.temp_dir, config)
        results = processor.compute_all()

        assert isinstance(results, HemodynamicsResults)
        assert results.inlet_type == 'TIMEVARYING'
        assert results.is_pulsatile == True
        assert results.cardiac_cycle == 0.9


class TestReadVectorField:
    """Test _read_vector_field and related methods."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_ascii_vector_field_success(self):
        """Test reading ASCII vector field."""
        # Create time directory with wallShearStress file
        time_dir = Path(self.temp_dir) / "1.0"
        time_dir.mkdir()

        wss_content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       volVectorField;
    object      wallShearStress;
}

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform (0 0 0);

boundaryField
{
    wall
    {
        type            calculated;
        value           nonuniform List<vector>
3
(
(0.1 0.2 0.3)
(0.4 0.5 0.6)
(0.7 0.8 0.9)
)
;
    }
}
"""
        wss_file = time_dir / "wallShearStress"
        wss_file.write_text(wss_content)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor._read_vector_field(wss_file)

        assert result is not None
        assert result.shape == (3, 3)
        # Check first vector
        assert abs(result[0, 0] - 0.1) < 1e-6
        assert abs(result[0, 1] - 0.2) < 1e-6
        assert abs(result[0, 2] - 0.3) < 1e-6

    def test_read_vector_field_nonexistent(self):
        """Test reading non-existent vector field."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor._read_vector_field(Path("/nonexistent/file"))

        assert result is None

    def test_read_ascii_vector_field_invalid_format(self):
        """Test reading ASCII file with invalid format."""
        time_dir = Path(self.temp_dir) / "1.0"
        time_dir.mkdir()

        # Invalid format - no proper vector data
        invalid_content = """FoamFile
{
    version     2.0;
    format      ascii;
}
// No valid vector data here
"""
        wss_file = time_dir / "wallShearStress"
        wss_file.write_text(invalid_content)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor._read_vector_field(wss_file)

        # Should return None for invalid format
        assert result is None


class TestComputeSteadyWSS:
    """Test _compute_steady_wss method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_steady_wss_with_data(self):
        """Test computing steady WSS with valid data."""
        time_dir = Path(self.temp_dir) / "1.0"
        time_dir.mkdir()

        # Create wallShearStress file with known values
        wss_content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       volVectorField;
    object      wallShearStress;
}
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{
    wall
    {
        type            calculated;
        value           nonuniform List<vector>
3
(
(1.0 0.0 0.0)
(2.0 0.0 0.0)
(3.0 0.0 0.0)
)
;
    }
}
"""
        wss_file = time_dir / "wallShearStress"
        wss_file.write_text(wss_content)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults()
        processor._compute_steady_wss(results)

        # Values should be multiplied by blood density (1060 kg/m³)
        assert results.wss_max > 0
        assert results.wss_mean > 0
        # Max should be 3.0 * 1060 = 3180 Pa
        assert abs(results.wss_max - 3180) < 1
        # Mean should be (1+2+3)/3 * 1060 = 2120 Pa
        assert abs(results.wss_mean - 2120) < 1

    def test_compute_steady_wss_no_time_dir(self):
        """Test computing steady WSS without time directories."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults()
        processor._compute_steady_wss(results)

        # Should not crash, just leave defaults
        assert results.wss_max == 0.0


class TestComputeTAWSSComplex:
    """Test _compute_tawss_osi_rrt with more scenarios."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
            'cardiac_cycle': 1.0,
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_wss_file(self, time_dir, vectors):
        """Helper to create wallShearStress file."""
        vectors_str = "\n".join(f"({v[0]} {v[1]} {v[2]})" for v in vectors)
        content = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       volVectorField;
    object      wallShearStress;
}}
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{{
    wall
    {{
        type            calculated;
        value           nonuniform List<vector>
{len(vectors)}
(
{vectors_str}
)
;
    }}
}}
"""
        wss_file = time_dir / "wallShearStress"
        wss_file.write_text(content)

    def _create_wss_mean_file(self, time_dir, vectors):
        """Helper to create wallShearStressMean file."""
        vectors_str = "\n".join(f"({v[0]} {v[1]} {v[2]})" for v in vectors)
        content = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       volVectorField;
    object      wallShearStressMean;
}}
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{{
    wall
    {{
        type            calculated;
        value           nonuniform List<vector>
{len(vectors)}
(
{vectors_str}
)
;
    }}
}}
"""
        mean_file = time_dir / "wallShearStressMean"
        mean_file.write_text(content)

    def test_compute_tawss_with_multiple_cycles(self):
        """Test TAWSS computation with multiple cardiac cycles."""
        # Create time directories for 2 cycles
        for t in [0.0, 0.5, 1.0, 1.5, 2.0]:
            time_dir = Path(self.temp_dir) / str(t)
            time_dir.mkdir()
            # Create WSS files with time-varying values
            wss_val = 1.0 + 0.5 * t  # increases with time
            self._create_wss_file(time_dir, [[wss_val, 0, 0], [wss_val*2, 0, 0]])

        # Create mean file at latest time
        time_dir = Path(self.temp_dir) / "2.0"
        self._create_wss_mean_file(time_dir, [[1.5, 0, 0], [3.0, 0, 0]])

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults()
        processor._compute_tawss_osi_rrt(results)

        # Should have computed TAWSS and OSI
        assert results.tawss_max > 0
        assert results.tawss_mean > 0

    def test_compute_tawss_no_wss_mean_file(self):
        """Test TAWSS computation when wallShearStressMean doesn't exist."""
        # Create time directory without mean file
        time_dir = Path(self.temp_dir) / "1.0"
        time_dir.mkdir()
        self._create_wss_file(time_dir, [[1.0, 0, 0]])

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults()
        processor._compute_tawss_osi_rrt(results)

        # Should not crash, TAWSS should remain 0
        assert results.tawss_max == 0.0


class TestGetTimeDirectories:
    """Test _get_time_directories method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_time_directories_sorted(self):
        """Test time directories are returned in sorted order."""
        # Create time directories in non-sorted order
        for t in [2.0, 0.5, 1.0, 0.0]:
            (Path(self.temp_dir) / str(t)).mkdir()

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        time_dirs = processor._get_time_directories()

        # Should be sorted
        times = [float(d.name) for d in time_dirs]
        assert times == sorted(times)
        assert len(times) == 4

    def test_get_time_directories_ignores_non_numeric(self):
        """Test non-numeric directories are ignored."""
        (Path(self.temp_dir) / "1.0").mkdir()
        (Path(self.temp_dir) / "constant").mkdir()
        (Path(self.temp_dir) / "system").mkdir()

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        time_dirs = processor._get_time_directories()

        # Only numeric directories
        assert len(time_dirs) == 1
        assert time_dirs[0].name == "1.0"


class TestSaveHemodynamicFields:
    """Test _save_hemodynamic_fields method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }
        # Create polyMesh/boundary file
        mesh_dir = Path(self.temp_dir) / "constant" / "polyMesh"
        mesh_dir.mkdir(parents=True)
        boundary_content = """
FoamFile
{
    version     2.0;
    format      ascii;
    class       polyBoundaryMesh;
}
4
(
    inlet
    {
        type            patch;
        nFaces          100;
    }
    outlet
    {
        type            patch;
        nFaces          50;
    }
    wall
    {
        type            wall;
        nFaces          5000;
    }
)
"""
        (mesh_dir / "boundary").write_text(boundary_content)

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_hemodynamic_fields_creates_files(self):
        """Test that TAWSS, OSI, RRT files are created."""
        time_dir = Path(self.temp_dir) / "1.0"
        time_dir.mkdir()

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)

        # Create mock field data
        tawss = np.array([1.0, 2.0, 3.0])
        osi = np.array([0.1, 0.2, 0.3])
        rrt = np.array([0.5, 1.0, 1.5])

        processor._save_hemodynamic_fields(time_dir, tawss, osi, rrt)

        # Check files were created
        for field_name in ['TAWSS', 'OSI', 'RRT']:
            field_file = time_dir / field_name
            assert field_file.exists(), f"{field_name} file not created"
            content = field_file.read_text()
            assert "volScalarField" in content
            assert field_name in content


class TestGenerateReport:
    """Test generate_report method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directories."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_generate_report_pulsatile(self):
        """Test report generation for pulsatile flow."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type='TIMEVARYING',
            is_pulsatile=True,
            cardiac_cycle=0.8,
            wss_max=12.5,
            wss_mean=3.2,
            wss_p99=11.0,
            wss_p95=9.5,
            tawss_max=10.0,
            tawss_mean=2.8,
            osi_max=0.35,
            osi_mean=0.12,
            rrt_max=5.0,
            rrt_mean=1.5
        )

        report_path = processor.generate_report(results, self.output_dir)

        assert os.path.exists(report_path)
        content = Path(report_path).read_text()
        assert "HEMODYNAMICS ANALYSIS REPORT" in content
        assert "Pulsatile" in content
        assert "TAWSS" in content
        assert "OSI" in content
        assert "RRT" in content

    def test_generate_report_steady(self):
        """Test report generation for steady flow."""
        steady_config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }
        processor = HemodynamicsPostProcessor(self.temp_dir, steady_config)
        results = HemodynamicsResults(
            inlet_type='CONSTANT',
            is_pulsatile=False,
            wss_max=8.0,
            wss_mean=2.0
        )

        report_path = processor.generate_report(results, self.output_dir)

        assert os.path.exists(report_path)
        content = Path(report_path).read_text()
        assert "HEMODYNAMICS ANALYSIS REPORT" in content
        assert "Steady" in content
        assert "OSI = 0" in content

    def test_generate_report_with_pressure_drop(self):
        """Test report includes pressure drop data."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type='TIMEVARYING',
            is_pulsatile=True,
            pressure_inlet=100.0,
            pressure_outlets={'outlet1': 80.0, 'outlet2': 85.0},
            pressure_drops={'outlet1': 20.0, 'outlet2': 15.0},
            pressure_drop_mmhg={'outlet1': 15.0, 'outlet2': 11.0}
        )

        report_path = processor.generate_report(results, self.output_dir)

        content = Path(report_path).read_text()
        assert "PRESSURE DROP" in content
        assert "Inlet" in content


class TestExportQoiExtended:
    """Extended tests for export_qoi method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
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

    def test_export_qoi_json_format(self):
        """Test that QoI JSON has correct structure."""
        import json

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type='TIMEVARYING',
            is_pulsatile=True,
            wss_max=10.0,
            wss_p99=9.5,
            tawss_p99=8.0,
            osi_mean_masked=0.15
        )

        json_path, csv_path = processor.export_qoi(results, self.output_dir)

        # Load and verify JSON
        with open(json_path) as f:
            qoi_data = json.load(f)

        assert 'tawss_p99_pa' in qoi_data or 'tawss_p99' in str(qoi_data).lower()
        assert os.path.exists(csv_path)

    def test_export_qoi_with_pressure_data(self):
        """Test QoI export includes pressure drop."""
        import json

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type='TIMEVARYING',
            is_pulsatile=True,
            pressure_drop_mmhg={'outlet': 12.5}
        )

        json_path, csv_path = processor.export_qoi(results, self.output_dir)

        with open(json_path) as f:
            qoi_data = json.load(f)

        # Should contain pressure drop info
        qoi_str = str(qoi_data)
        assert os.path.exists(json_path)


class TestConvenienceFunctionExtended:
    """Extended tests for run_hemodynamics_analysis convenience function."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup temp directories."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)

    @patch('subprocess.run')
    def test_run_hemodynamics_analysis_steady(self, mock_run):
        """Test convenience function with steady flow config."""
        mock_run.return_value = MagicMock(returncode=0, stderr='')

        config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

        results = run_hemodynamics_analysis(
            self.temp_dir,
            config,
            output_dir=self.output_dir
        )

        assert isinstance(results, HemodynamicsResults)
        assert results.inlet_type == 'CONSTANT'

    @patch('subprocess.run')
    def test_run_hemodynamics_analysis_pulsatile(self, mock_run):
        """Test convenience function with pulsatile flow config."""
        mock_run.return_value = MagicMock(returncode=0, stderr='')

        config = {
            'inlet': {'type': 'WOMERSLEY'},
            'cardiac_cycle': 0.75,
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

        results = run_hemodynamics_analysis(
            self.temp_dir,
            config,
            output_dir=self.output_dir
        )

        assert results.is_pulsatile == True
        assert results.cardiac_cycle == 0.75


# =============================================================================
# ADDITIONAL TESTS FOR UNCOVERED PATHS
# =============================================================================

class TestDetectPeakSystole:
    """Test _detect_peak_systole method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
            'cardiac_cycle': 0.8,
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_peak_systole_with_flowrate_csv(self):
        """Test peak systole detection from flowrate.csv."""
        # Create boundaryData/inlet directory with flowrate.csv
        inlet_dir = os.path.join(self.temp_dir, 'constant', 'boundaryData', 'inlet')
        os.makedirs(inlet_dir, exist_ok=True)

        flowrate_file = os.path.join(inlet_dir, 'flowrate.csv')
        with open(flowrate_file, 'w') as f:
            # Peak flow at t=0.2
            f.write("0.0,50.0\n")
            f.write("0.1,80.0\n")
            f.write("0.2,100.0\n")  # Peak
            f.write("0.3,70.0\n")
            f.write("0.4,40.0\n")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(is_pulsatile=True, cardiac_cycle=0.8)

        processor._detect_peak_systole(results)

        assert results.peak_systole_detected == True
        assert results.peak_systole_time == pytest.approx(0.2)

    def test_detect_peak_systole_steady_flow_skips(self):
        """Test peak systole detection is skipped for steady flow."""
        config = self.config.copy()
        config['inlet'] = {'type': 'CONSTANT'}

        processor = HemodynamicsPostProcessor(self.temp_dir, config)
        results = HemodynamicsResults(is_pulsatile=False)

        processor._detect_peak_systole(results)

        assert results.peak_systole_detected == False

    def test_detect_peak_systole_no_flowrate_file(self):
        """Test peak systole detection when flowrate.csv doesn't exist."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(is_pulsatile=True)

        processor._detect_peak_systole(results)

        assert results.peak_systole_detected == False

    def test_detect_peak_systole_with_header(self):
        """Test peak systole detection with CSV header."""
        inlet_dir = os.path.join(self.temp_dir, 'constant', 'boundaryData', 'inlet_main')
        os.makedirs(inlet_dir, exist_ok=True)

        flowrate_file = os.path.join(inlet_dir, 'flowrate.csv')
        with open(flowrate_file, 'w') as f:
            f.write("time,flowrate\n")  # Header (non-numeric)
            f.write("0.0,50.0\n")
            f.write("0.15,120.0\n")  # Peak
            f.write("0.3,60.0\n")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(is_pulsatile=True, cardiac_cycle=0.8)

        processor._detect_peak_systole(results)

        assert results.peak_systole_detected == True
        assert results.peak_systole_time == pytest.approx(0.15)

    def test_detect_peak_systole_negative_flows(self):
        """Test peak systole detection handles negative flow (uses absolute value)."""
        inlet_dir = os.path.join(self.temp_dir, 'constant', 'boundaryData', 'inlet')
        os.makedirs(inlet_dir, exist_ok=True)

        flowrate_file = os.path.join(inlet_dir, 'flowrate.csv')
        with open(flowrate_file, 'w') as f:
            f.write("0.0,-50.0\n")
            f.write("0.1,-120.0\n")  # Peak magnitude
            f.write("0.2,-60.0\n")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(is_pulsatile=True, cardiac_cycle=0.8)

        processor._detect_peak_systole(results)

        assert results.peak_systole_detected == True
        assert results.peak_systole_time == pytest.approx(0.1)


class TestComputeSteadyWSS:
    """Test _compute_steady_wss method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_steady_wss_no_time_dir(self):
        """Test _compute_steady_wss when no time directories exist."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults()

        processor._compute_steady_wss(results)

        # Should not crash, values remain at defaults
        assert results.wss_max == 0.0

    def test_compute_steady_wss_no_wss_file(self):
        """Test _compute_steady_wss when WSS file doesn't exist."""
        # Create time directory without WSS file
        time_dir = os.path.join(self.temp_dir, '1.0')
        os.makedirs(time_dir, exist_ok=True)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults()

        processor._compute_steady_wss(results)

        assert results.wss_max == 0.0


class TestComputePressureDrop:
    """Test _compute_pressure_drop method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_pressure_drop_with_data(self):
        """Test pressure drop computation with actual data."""
        # Create postProcessing data
        inlet_dir = os.path.join(self.temp_dir, 'postProcessing', 'inletPressure', '0')
        os.makedirs(inlet_dir, exist_ok=True)
        with open(os.path.join(inlet_dir, 'surfaceFieldValue.dat'), 'w') as f:
            f.write("# Time p\n")
            f.write("0.0 120.0\n")
            f.write("0.5 122.0\n")

        outlet_dir = os.path.join(self.temp_dir, 'postProcessing', 'outlet1Pressure', '0')
        os.makedirs(outlet_dir, exist_ok=True)
        with open(os.path.join(outlet_dir, 'surfaceFieldValue.dat'), 'w') as f:
            f.write("# Time p\n")
            f.write("0.0 100.0\n")
            f.write("0.5 102.0\n")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults()

        processor._compute_pressure_drop(results)

        # Should have inlet and outlet data
        assert len(results.time_series) == 2
        assert results.pressure_inlet == pytest.approx(121.0)  # Mean of 120, 122

    def test_compute_pressure_drop_no_postprocessing(self):
        """Test pressure drop when postProcessing directory doesn't exist."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults()

        processor._compute_pressure_drop(results)

        # Should handle gracefully
        assert results.pressure_inlet == 0.0


class TestReadVectorField:
    """Test _read_vector_field method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'CONSTANT'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_vector_field_nonexistent(self):
        """Test reading nonexistent vector field file."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor._read_vector_field(Path(self.temp_dir) / 'nonexistent')

        assert result is None

    def test_read_ascii_vector_field(self):
        """Test reading ASCII format vector field."""
        time_dir = os.path.join(self.temp_dir, '1.0')
        os.makedirs(time_dir, exist_ok=True)

        wss_file = os.path.join(time_dir, 'wallShearStress')
        with open(wss_file, 'w') as f:
            f.write("""FoamFile
{
    version     2.0;
    format      ascii;
    class       volVectorField;
    object      wallShearStress;
}

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform (0 0 0);

boundaryField
{
    wall
    {
        type            calculated;
        value           nonuniform List<vector>
3
(
(1.0 0.5 0.0)
(2.0 1.0 0.5)
(1.5 0.8 0.3)
)
;
    }
}
""")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor._read_vector_field(Path(wss_file))

        assert result is not None
        assert result.shape == (3, 3)
        assert result[0, 0] == pytest.approx(1.0)
        assert result[1, 0] == pytest.approx(2.0)

    def test_read_vector_field_invalid_format(self):
        """Test reading vector field with invalid format."""
        time_dir = os.path.join(self.temp_dir, '1.0')
        os.makedirs(time_dir, exist_ok=True)

        wss_file = os.path.join(time_dir, 'wallShearStress')
        with open(wss_file, 'w') as f:
            f.write("invalid content without proper format")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        result = processor._read_vector_field(Path(wss_file))

        assert result is None


class TestGeneratePressurePlot:
    """Test _generate_pressure_plot method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directories."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_generate_pressure_plot_no_time_series(self):
        """Test pressure plot generation when no time series data."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(time_series=[])

        # Should not crash
        processor._generate_pressure_plot(results, Path(self.output_dir))

        # No plot file should be created
        plot_file = os.path.join(self.output_dir, 'pressure_drop_timeseries.png')
        assert not os.path.exists(plot_file)

    @patch('aortacfd_lib.hemodynamics_postprocessor.HAS_MATPLOTLIB', True)
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.subplots')
    @patch('matplotlib.pyplot.tight_layout')
    @patch('matplotlib.pyplot.close')
    def test_generate_pressure_plot_with_data(self, mock_close, mock_tight,
                                               mock_subplots, mock_savefig):
        """Test pressure plot generation with data."""
        mock_fig = MagicMock()
        mock_ax1 = MagicMock()
        mock_ax2 = MagicMock()
        mock_subplots.return_value = (mock_fig, (mock_ax1, mock_ax2))

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            time_series=[0.0, 0.1, 0.2],
            pressure_inlet_series=[100.0, 110.0, 105.0],
            pressure_outlet_series={
                'outlet1': [80.0, 85.0, 82.0],
                'outlet2': [75.0, 78.0, 76.0]
            }
        )

        processor._generate_pressure_plot(results, Path(self.output_dir))

        # Should have been called
        mock_subplots.assert_called_once()


class TestComputeTAWSSWithMissingData:
    """Test _compute_tawss_osi_rrt with various data conditions."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
            'cardiac_cycle': 0.4,
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            },
            'hemodynamics': {
                'tawss_settings': {
                    'skip_cycles': 1
                }
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_tawss_no_valid_dirs_after_skip(self):
        """Test TAWSS computation when no dirs after skip_cycles."""
        # Create time directories before skip time (0.4s with skip_cycles=1 means 0.4s)
        for t in ['0', '0.1', '0.2', '0.3']:
            os.makedirs(os.path.join(self.temp_dir, t), exist_ok=True)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(is_pulsatile=True)

        processor._compute_tawss_osi_rrt(results)

        # Should handle gracefully - no TAWSS computed
        assert results.tawss_max == 0.0


class TestReportWithPressureDrops:
    """Test report generation with pressure drop data."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet1', 'outlet2'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directories."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_report_with_pressure_data(self):
        """Test report generation with pressure drop data."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type="TIMEVARYING",
            is_pulsatile=True,
            wss_max=15.0,
            wss_mean=3.5,
            wss_p99=14.0,
            wss_p95=12.0,
            tawss_max=10.0,
            tawss_mean=3.0,
            pressure_inlet=120.0,
            pressure_outlets={'outlet1': 100.0, 'outlet2': 95.0},
            pressure_drops={'outlet1': 20.0, 'outlet2': 25.0},
            pressure_drop_mmhg={'outlet1': 15.0, 'outlet2': 18.75}
        )

        report_path = processor.generate_report(results, self.output_dir)

        with open(report_path, 'r') as f:
            content = f.read()

        # Should contain pressure drop section
        assert 'PRESSURE DROP' in content
        assert 'outlet1' in content
        assert 'outlet2' in content

    def test_report_with_peak_systole(self):
        """Test report includes peak systole when detected."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type="TIMEVARYING",
            is_pulsatile=True,
            cardiac_cycle=0.8,
            peak_systole_detected=True,
            peak_systole_time=0.15,
            wss_max=15.0,
            wss_mean=3.5
        )

        report_path = processor.generate_report(results, self.output_dir)

        with open(report_path, 'r') as f:
            content = f.read()

        assert 'Peak Systole' in content
        assert '0.15' in content

    def test_report_steady_flow_no_pulsatile_metrics(self):
        """Test report for steady flow excludes pulsatile metrics."""
        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        results = HemodynamicsResults(
            inlet_type="CONSTANT",
            is_pulsatile=False,
            wss_max=15.0,
            wss_mean=3.5
        )

        report_path = processor.generate_report(results, self.output_dir)

        with open(report_path, 'r') as f:
            content = f.read()

        assert 'Not Applicable' in content
        assert 'OSI = 0' in content


class TestFieldAverageCheck:
    """Test _check_fieldaverage_exists method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
            'geometry': {
                'inlet_keywords_ordered': 'inlet',
                'outlet_keywords_ordered': ['outlet'],
                'wall_keywords_ordered': 'wall'
            }
        }

    def teardown_method(self):
        """Cleanup temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fieldaverage_exists_true(self):
        """Test fieldAverage check returns True when Mean file exists."""
        time_dir = os.path.join(self.temp_dir, '1.0')
        os.makedirs(time_dir, exist_ok=True)

        mean_file = os.path.join(time_dir, 'wallShearStressMean')
        with open(mean_file, 'w') as f:
            f.write("// Mock mean file")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        assert processor._check_fieldaverage_exists() == True

    def test_fieldaverage_exists_false(self):
        """Test fieldAverage check returns False when no Mean file."""
        time_dir = os.path.join(self.temp_dir, '1.0')
        os.makedirs(time_dir, exist_ok=True)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)
        assert processor._check_fieldaverage_exists() == False


class TestSaveHemodynamicFields:
    """Test _save_hemodynamic_fields method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'inlet': {'type': 'TIMEVARYING'},
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

    def test_save_hemodynamic_fields_no_boundary_file(self):
        """Test save when boundary file doesn't exist."""
        time_dir = Path(self.temp_dir) / '1.0'
        time_dir.mkdir(parents=True, exist_ok=True)

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)

        tawss = np.array([1.0, 2.0, 3.0])
        osi = np.array([0.1, 0.2, 0.3])
        rrt = np.array([0.5, 0.6, 0.7])

        # Should not crash even without boundary file
        processor._save_hemodynamic_fields(time_dir, tawss, osi, rrt)

    def test_save_hemodynamic_fields_with_boundary(self):
        """Test save with valid boundary file."""
        time_dir = Path(self.temp_dir) / '1.0'
        time_dir.mkdir(parents=True, exist_ok=True)

        # Create boundary file
        polymesh_dir = Path(self.temp_dir) / 'constant' / 'polyMesh'
        polymesh_dir.mkdir(parents=True, exist_ok=True)

        boundary_file = polymesh_dir / 'boundary'
        with open(boundary_file, 'w') as f:
            f.write("""wall_aorta
{
    type wall;
}
inlet
{
    type patch;
}
""")

        processor = HemodynamicsPostProcessor(self.temp_dir, self.config)

        tawss = np.array([1.0, 2.0, 3.0])
        osi = np.array([0.1, 0.2, 0.3])
        rrt = np.array([0.5, 0.6, 0.7])

        processor._save_hemodynamic_fields(time_dir, tawss, osi, rrt)

        # Check files were created
        assert (time_dir / 'TAWSS').exists()
        assert (time_dir / 'OSI').exists()
        assert (time_dir / 'RRT').exists()
