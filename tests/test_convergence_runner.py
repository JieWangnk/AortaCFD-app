"""
Test suite for workflow convergence_runner module.

Tests cover:
- MeshConvergenceRunner class
- Richardson extrapolation
- GCI computation
- Mesh configuration generation
- Convergence analysis
"""

import pytest
import sys
import json
import tempfile
import math
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from workflow.convergence_runner import (
    MeshConvergenceRunner,
    ConvergenceStudyError,
)


class TestConvergenceStudyError:
    """Test ConvergenceStudyError exception."""

    def test_exception_can_be_raised(self):
        """Test exception can be raised and caught."""
        with pytest.raises(ConvergenceStudyError):
            raise ConvergenceStudyError("Test error")

    def test_exception_message(self):
        """Test exception carries message."""
        with pytest.raises(ConvergenceStudyError) as exc_info:
            raise ConvergenceStudyError("Custom error message")

        assert "Custom error message" in str(exc_info.value)


class TestMeshConvergenceRunnerInit:
    """Test MeshConvergenceRunner initialization."""

    def test_init_with_nonexistent_config(self):
        """Test initialization with non-existent config file."""
        with pytest.raises(ConvergenceStudyError) as exc_info:
            MeshConvergenceRunner('/nonexistent/config.json')

        assert 'not found' in str(exc_info.value)

    def test_init_with_valid_config(self):
        """Test initialization with valid config file."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {'type': 'CONSTANT'}},
            'physics': {'model': 'laminar'},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            assert runner.base_config == config
            assert runner.output_dir.exists()

    def test_init_detects_time_varying_inlet(self):
        """Test initialization warns about time-varying inlet."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {'type': 'TIMEVARYING'}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            # Should log warning but not fail
            runner = MeshConvergenceRunner(str(config_file))
            assert runner is not None


class TestGetStudyId:
    """Test _get_study_id method."""

    def test_study_id_format(self):
        """Test study ID includes patient_id and timestamp."""
        config = {
            'case_info': {'patient_id': 'TEST001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))
            study_id = runner._get_study_id()

            assert 'TEST001' in study_id
            # Should contain timestamp in format YYYYMMDD_HHMMSS
            assert '_' in study_id


class TestApplySteadyBC:
    """Test _apply_steady_bc method."""

    def test_converts_time_varying_to_constant(self):
        """Test time-varying inlet is converted to constant."""
        config = {
            'case_info': {'patient_id': 'PAT001', 'cardiac_output': 5.0},
            'boundary_conditions': {
                'inlet': {'type': 'TIMEVARYING'},
                'outlets': {}
            },
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))
            result = runner._apply_steady_bc(config.copy())

            assert result['boundary_conditions']['inlet']['type'] == 'CONSTANT'
            assert 'flow_rate' in result['boundary_conditions']['inlet']

    def test_sets_fixed_pressure_outlets(self):
        """Test outlets are set to fixed pressure."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT'},
                'outlets': {'type': 'WINDKESSEL'}
            },
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))
            result = runner._apply_steady_bc(config.copy())

            assert result['boundary_conditions']['outlets']['type'] == 'FIXEDPRESSURE'


class TestApplyConvergenceNumerics:
    """Test _apply_convergence_numerics method."""

    def test_sets_accurate_profile(self):
        """Test numerics profile is set to accurate."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))
            result = runner._apply_convergence_numerics(config.copy())

            assert result['numerics']['profile'] == 'accurate'
            assert result['numerics']['_convergence_study'] is True


class TestGenerateMeshConfigs:
    """Test _generate_mesh_configs method."""

    def test_generates_three_configs(self):
        """Test three mesh configurations are generated."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {'type': 'CONSTANT'}},
            'physics': {'model': 'laminar'},
            'numerics': {},
            'mesh': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))
            configs = runner._generate_mesh_configs(10, 1.414, True)

            assert len(configs) == 3
            assert configs[0]['level'] == 'coarse'
            assert configs[1]['level'] == 'medium'
            assert configs[2]['level'] == 'fine'

    def test_cpd_refinement_ratio(self):
        """Test cells_per_diameter follows refinement ratio."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {'type': 'CONSTANT'}},
            'physics': {'model': 'laminar'},
            'numerics': {},
            'mesh': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))
            base_cpd = 10
            ratio = 2.0
            configs = runner._generate_mesh_configs(base_cpd, ratio, True)

            assert configs[0]['cpd'] == 10
            assert configs[1]['cpd'] == 20  # 10 * 2
            assert configs[2]['cpd'] == 40  # 10 * 2 * 2

    def test_config_files_created(self):
        """Test configuration files are created for each level."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {'type': 'CONSTANT'}},
            'physics': {'model': 'laminar'},
            'numerics': {},
            'mesh': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))
            configs = runner._generate_mesh_configs(10, 1.414, True)

            for cfg in configs:
                assert Path(cfg['config_file']).exists()


class TestRichardsonExtrapolation:
    """Test _richardson_extrapolation method."""

    def test_convergence_analysis(self):
        """Test Richardson extrapolation returns expected structure."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            # Test values
            phi_3 = 100.0  # Coarse
            phi_2 = 102.0  # Medium
            phi_1 = 102.5  # Fine
            r = 2.0

            result = runner._richardson_extrapolation(phi_3, phi_2, phi_1, r)

            # Verify result structure
            assert 'convergence_status' in result
            assert 'observed_order' in result
            assert 'phi_exact' in result
            assert 'gci_fine' in result
            assert 'gci_medium' in result

            # GCI values should be non-negative
            assert result['gci_fine'] >= 0
            assert result['gci_medium'] >= 0

    def test_oscillatory_convergence(self):
        """Test Richardson extrapolation with oscillatory convergence."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            # Oscillatory values
            phi_3 = 100.0
            phi_2 = 99.0
            phi_1 = 99.5
            r = 2.0

            result = runner._richardson_extrapolation(phi_3, phi_2, phi_1, r)

            assert result['convergence_status'] == 'oscillatory_convergence'

    def test_converged_solution(self):
        """Test with nearly converged solution."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            # Nearly identical values
            phi_3 = 100.0
            phi_2 = 100.0
            phi_1 = 100.0
            r = 2.0

            result = runner._richardson_extrapolation(phi_3, phi_2, phi_1, r)

            assert result['convergence_status'] == 'converged'
            assert result['gci_fine'] == 0.0

    def test_second_order_accuracy(self):
        """Test observed order for second-order accurate scheme."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            # Values following 2nd order convergence: error ~ h^2
            # With r=2, error reduces by factor of 4 each refinement
            # phi = phi_exact + C*h^2
            phi_exact = 100.0
            h_coarse = 0.04
            h_medium = 0.02
            h_fine = 0.01
            C = 100.0

            phi_3 = phi_exact + C * h_coarse**2  # 100.16
            phi_2 = phi_exact + C * h_medium**2  # 100.04
            phi_1 = phi_exact + C * h_fine**2    # 100.01
            r = 2.0

            result = runner._richardson_extrapolation(phi_3, phi_2, phi_1, r)

            # Observed order should be close to 2
            assert abs(result['observed_order'] - 2.0) < 0.5


class TestGetTimeDirectories:
    """Test _get_time_directories method."""

    def test_finds_time_dirs(self):
        """Test finding time directories."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            # Create mock case directory
            case_dir = Path(tmpdir) / 'case'
            case_dir.mkdir()
            (case_dir / '0').mkdir()
            (case_dir / '0.1').mkdir()
            (case_dir / '0.5').mkdir()
            (case_dir / '1.0').mkdir()
            (case_dir / 'constant').mkdir()  # Should be ignored

            times = runner._get_time_directories(case_dir)

            assert 0.0 in times
            assert 0.1 in times
            assert 0.5 in times
            assert 1.0 in times
            assert len(times) == 4

    def test_empty_case_dir(self):
        """Test with empty case directory."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            case_dir = Path(tmpdir) / 'empty_case'
            case_dir.mkdir()

            times = runner._get_time_directories(case_dir)

            assert times == []


class TestComputeConvergenceMetrics:
    """Test _compute_convergence_metrics method."""

    def test_computes_all_quantities(self):
        """Test convergence metrics computed for all quantities."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            quantities = {
                'coarse': {
                    'pressure_drop': 100.0,
                    'avg_velocity': 0.5,
                    'avg_wss': 1.5,
                    'peak_wss': 3.5
                },
                'medium': {
                    'pressure_drop': 102.0,
                    'avg_velocity': 0.52,
                    'avg_wss': 1.55,
                    'peak_wss': 3.6
                },
                'fine': {
                    'pressure_drop': 102.5,
                    'avg_velocity': 0.525,
                    'avg_wss': 1.57,
                    'peak_wss': 3.62
                }
            }

            metrics = runner._compute_convergence_metrics(quantities, 1.414)

            assert 'pressure_drop' in metrics
            assert 'avg_velocity' in metrics
            assert 'avg_wss' in metrics
            assert 'peak_wss' in metrics

            for qty_metrics in metrics.values():
                assert 'observed_order' in qty_metrics
                assert 'phi_exact' in qty_metrics
                assert 'gci_fine' in qty_metrics
                assert 'gci_medium' in qty_metrics


class TestComputePressureDrop:
    """Test _compute_pressure_drop method."""

    def test_no_time_dirs(self):
        """Test with no time directories."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            case_dir = Path(tmpdir) / 'case'
            case_dir.mkdir()

            result = runner._compute_pressure_drop(case_dir)

            # Should return fallback value
            assert result == 0.0


class TestComputeRepresentativeH:
    """Test _compute_representative_h method."""

    def test_fallback_value(self):
        """Test fallback h value when log not found."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            case_dir = Path(tmpdir) / 'case'
            case_dir.mkdir()

            h = runner._compute_representative_h(case_dir)

            assert h == 0.001  # Fallback value


class TestGetCellCount:
    """Test _get_cell_count method."""

    def test_parses_checkmesh_log(self):
        """Test cell count parsing from checkMesh log."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            case_dir = Path(tmpdir) / 'case'
            case_dir.mkdir()

            # Create mock checkMesh log
            log_content = """
Checking mesh...
    cells: 500000
    faces: 1500000
    points: 600000
Mesh OK.
"""
            log_file = case_dir / 'log.checkMesh'
            log_file.write_text(log_content)

            cell_count = runner._get_cell_count(case_dir)

            assert cell_count == 500000

    def test_fallback_cell_count(self):
        """Test fallback cell count when log not found."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            case_dir = Path(tmpdir) / 'case'
            case_dir.mkdir()

            cell_count = runner._get_cell_count(case_dir)

            assert cell_count == 1000000  # Fallback value


class TestGenerateConvergenceReport:
    """Test _generate_convergence_report method."""

    def test_creates_report_file(self):
        """Test report file is created."""
        config = {
            'case_info': {'patient_id': 'PAT001'},
            'boundary_conditions': {'inlet': {}},
            'physics': {},
            'numerics': {}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f)

            runner = MeshConvergenceRunner(str(config_file))

            mesh_configs = [
                {'level': 'coarse', 'cpd': 10, 'label': 'Mesh 3 (Coarse)'},
                {'level': 'medium', 'cpd': 14, 'label': 'Mesh 2 (Medium)'},
                {'level': 'fine', 'cpd': 20, 'label': 'Mesh 1 (Fine)'}
            ]

            simulation_results = [
                {'level': 'coarse', 'case_dir': '/tmp/coarse', 'success': True},
                {'level': 'medium', 'case_dir': '/tmp/medium', 'success': True},
                {'level': 'fine', 'case_dir': '/tmp/fine', 'success': True}
            ]

            quantities = {
                'coarse': {
                    'pressure_drop': 100.0, 'avg_velocity': 0.5,
                    'avg_wss': 1.5, 'peak_wss': 3.5,
                    'cell_count': 100000, 'h_representative': 0.002
                },
                'medium': {
                    'pressure_drop': 102.0, 'avg_velocity': 0.52,
                    'avg_wss': 1.55, 'peak_wss': 3.6,
                    'cell_count': 200000, 'h_representative': 0.0014
                },
                'fine': {
                    'pressure_drop': 102.5, 'avg_velocity': 0.525,
                    'avg_wss': 1.57, 'peak_wss': 3.62,
                    'cell_count': 400000, 'h_representative': 0.001
                }
            }

            convergence_metrics = {
                'pressure_drop': {
                    'observed_order': 2.0, 'phi_exact': 102.8,
                    'gci_fine': 1.5, 'gci_medium': 3.0,
                    'convergence_ratio': 0.5, 'convergence_status': 'monotonic_convergence'
                },
                'avg_velocity': {
                    'observed_order': 2.0, 'phi_exact': 0.53,
                    'gci_fine': 1.0, 'gci_medium': 2.0,
                    'convergence_ratio': 0.5, 'convergence_status': 'monotonic_convergence'
                },
                'avg_wss': {
                    'observed_order': 2.0, 'phi_exact': 1.58,
                    'gci_fine': 1.2, 'gci_medium': 2.4,
                    'convergence_ratio': 0.5, 'convergence_status': 'monotonic_convergence'
                },
                'peak_wss': {
                    'observed_order': 2.0, 'phi_exact': 3.65,
                    'gci_fine': 1.1, 'gci_medium': 2.2,
                    'convergence_ratio': 0.5, 'convergence_status': 'monotonic_convergence'
                }
            }

            report_path = runner._generate_convergence_report(
                mesh_configs, simulation_results, quantities, convergence_metrics
            )

            assert report_path.exists()
            assert report_path.suffix == '.md'

            # Check JSON data file
            json_file = runner.output_dir / 'convergence_data.json'
            assert json_file.exists()


class TestMain:
    """Test main function for CLI."""

    @patch('workflow.convergence_runner.MeshConvergenceRunner')
    def test_main_with_args(self, mock_runner_class):
        """Test main function with command line arguments."""
        from workflow.convergence_runner import main

        mock_runner = MagicMock()
        mock_runner.run_convergence_study.return_value = {
            'study_dir': '/tmp/study',
            'report': '/tmp/report.md'
        }
        mock_runner_class.return_value = mock_runner

        with patch('sys.argv', ['convergence_runner', '/path/to/config.json']):
            with patch('builtins.print'):
                main()

        mock_runner_class.assert_called_once_with('/path/to/config.json')
        mock_runner.run_convergence_study.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
