"""
Test suite for performance_optimizer module.

Tests cover:
- SystemResources dataclass
- SimulationProfile dataclass
- PerformanceOptimizer class
- ResourceMonitor class
- AdaptiveTimestepping class
- create_performance_report function

Note: Tests mock psutil since it may not be available in all environments.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# Mock psutil module before importing performance_optimizer
@pytest.fixture(autouse=True)
def mock_psutil():
    """Mock psutil module for testing."""
    mock_psutil_module = MagicMock()

    # Mock virtual_memory
    mock_memory = MagicMock()
    mock_memory.total = 16 * (1024**3)  # 16GB
    mock_memory.available = 8 * (1024**3)  # 8GB available
    mock_memory.percent = 50.0
    mock_psutil_module.virtual_memory.return_value = mock_memory

    # Mock disk_usage
    mock_disk = MagicMock()
    mock_disk.free = 100 * (1024**3)  # 100GB free
    mock_psutil_module.disk_usage.return_value = mock_disk

    # Mock cpu_count
    mock_psutil_module.cpu_count.return_value = 8

    # Mock cpu_percent
    mock_psutil_module.cpu_percent.return_value = 30.0

    # Mock disk_io_counters
    mock_disk_io = MagicMock()
    mock_disk_io._asdict.return_value = {'read_bytes': 1000, 'write_bytes': 2000}
    mock_psutil_module.disk_io_counters.return_value = mock_disk_io

    # Mock net_io_counters
    mock_net_io = MagicMock()
    mock_net_io._asdict.return_value = {'bytes_sent': 500, 'bytes_recv': 600}
    mock_psutil_module.net_io_counters.return_value = mock_net_io

    sys.modules['psutil'] = mock_psutil_module

    yield mock_psutil_module

    # Cleanup
    if 'psutil' in sys.modules:
        del sys.modules['psutil']
    # Also remove the performance_optimizer module so it gets reimported fresh
    if 'aortacfd_lib.performance_optimizer' in sys.modules:
        del sys.modules['aortacfd_lib.performance_optimizer']


class TestSystemResources:
    """Test SystemResources dataclass."""

    def test_system_resources_creation(self, mock_psutil):
        """Test creating SystemResources instance."""
        from aortacfd_lib.performance_optimizer import SystemResources

        resources = SystemResources(
            cpu_cores=8,
            memory_gb=16.0,
            available_memory_gb=8.0,
            cpu_usage_percent=30.0,
            disk_space_gb=100.0
        )

        assert resources.cpu_cores == 8
        assert resources.memory_gb == 16.0
        assert resources.available_memory_gb == 8.0
        assert resources.cpu_usage_percent == 30.0
        assert resources.disk_space_gb == 100.0


class TestSimulationProfile:
    """Test SimulationProfile dataclass."""

    def test_simulation_profile_creation(self, mock_psutil):
        """Test creating SimulationProfile instance."""
        from aortacfd_lib.performance_optimizer import SimulationProfile

        profile = SimulationProfile(
            case_name="test_case",
            mesh_size=100000,
            time_steps=1000,
            convergence_time=3600.0,
            memory_usage_gb=4.0,
            cpu_efficiency=0.85,
            success_rate=0.95
        )

        assert profile.case_name == "test_case"
        assert profile.mesh_size == 100000
        assert profile.time_steps == 1000
        assert profile.convergence_time == 3600.0
        assert profile.memory_usage_gb == 4.0
        assert profile.cpu_efficiency == 0.85
        assert profile.success_rate == 0.95


class TestPerformanceOptimizerInit:
    """Test PerformanceOptimizer initialization."""

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_init(self, mock_logger, mock_psutil):
        """Test initialization with config."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer

        config = {'key': 'value'}
        optimizer = PerformanceOptimizer(config)

        assert optimizer.config == config
        assert optimizer.simulation_history == []
        assert optimizer.resource_monitor is not None


class TestAnalyzeSystemResources:
    """Test analyze_system_resources method."""

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_analyze_resources(self, mock_logger, mock_psutil):
        """Test system resource analysis."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer

        optimizer = PerformanceOptimizer({})
        resources = optimizer.analyze_system_resources()

        assert resources.cpu_cores == 8
        assert resources.memory_gb == 16.0
        assert resources.available_memory_gb == 8.0
        assert resources.disk_space_gb == 100.0


class TestOptimizeMeshParameters:
    """Test optimize_mesh_parameters method."""

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_optimize_mesh_simple_geometry(self, mock_logger, mock_psutil):
        """Test mesh optimization for simple geometry."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer

        optimizer = PerformanceOptimizer({})
        params = optimizer.optimize_mesh_parameters(geometry_complexity=0.2)

        assert 'regionRefinementLevel' in params
        assert 'surfaceRefinementLevels' in params
        assert 'nCellsBetweenLevels' in params
        assert 'parallel' in params
        assert 'nProcessors' in params

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_optimize_mesh_complex_geometry(self, mock_logger, mock_psutil):
        """Test mesh optimization for complex geometry."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer

        optimizer = PerformanceOptimizer({})
        params_simple = optimizer.optimize_mesh_parameters(geometry_complexity=0.2)
        params_complex = optimizer.optimize_mesh_parameters(geometry_complexity=0.9)

        # Complex geometry should have higher refinement
        assert params_complex['surfaceRefinementLevels'][1] >= params_simple['surfaceRefinementLevels'][1]


class TestOptimizeSolverParameters:
    """Test optimize_solver_parameters method."""

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_optimize_solver_medium_case(self, mock_logger, mock_psutil):
        """Test solver optimization for medium case."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer

        optimizer = PerformanceOptimizer({})
        params = optimizer.optimize_solver_parameters(case_size="medium")

        assert 'nOuterCorrectors' in params
        assert 'nCorrectors' in params
        assert 'relaxationFactors' in params
        assert 'deltaT' in params
        assert params['deltaT'] == 0.0005

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_optimize_solver_coarse_case(self, mock_logger, mock_psutil):
        """Test solver optimization for coarse case."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer

        optimizer = PerformanceOptimizer({})
        params = optimizer.optimize_solver_parameters(case_size="coarse")

        assert params['deltaT'] == 0.001

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_optimize_solver_fine_case(self, mock_logger, mock_psutil):
        """Test solver optimization for fine case."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer

        optimizer = PerformanceOptimizer({})
        params = optimizer.optimize_solver_parameters(case_size="fine")

        assert params['deltaT'] == 0.0001


class TestPredictSimulationTime:
    """Test predict_simulation_time method."""

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_predict_no_history(self, mock_logger, mock_psutil):
        """Test prediction without history uses conservative estimate."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer

        optimizer = PerformanceOptimizer({})
        time_estimate = optimizer.predict_simulation_time(mesh_size=100000, time_steps=1000)

        # Should use base estimate
        expected = 100000 * 1000 * 1e-6
        assert time_estimate == expected

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_predict_with_history(self, mock_logger, mock_psutil):
        """Test prediction with simulation history."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer, SimulationProfile

        optimizer = PerformanceOptimizer({})

        # Add simulation history
        optimizer.simulation_history.append(
            SimulationProfile(
                case_name="past_case",
                mesh_size=100000,
                time_steps=1000,
                convergence_time=100.0,
                memory_usage_gb=4.0,
                cpu_efficiency=0.8,
                success_rate=1.0
            )
        )

        time_estimate = optimizer.predict_simulation_time(mesh_size=100000, time_steps=500)

        # Should use historical data
        assert time_estimate > 0


class TestOptimizeParallelization:
    """Test optimize_parallelization method."""

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_optimize_small_mesh(self, mock_logger, mock_psutil):
        """Test parallelization for small mesh."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer

        optimizer = PerformanceOptimizer({})
        decomposition = optimizer.optimize_parallelization(mesh_size=100000)

        assert 'numberOfSubdomains' in decomposition
        assert 'method' in decomposition
        assert decomposition['numberOfSubdomains'] >= 1

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_optimize_large_mesh(self, mock_logger, mock_psutil):
        """Test parallelization for large mesh."""
        from aortacfd_lib.performance_optimizer import PerformanceOptimizer

        optimizer = PerformanceOptimizer({})
        decomposition = optimizer.optimize_parallelization(mesh_size=1000000)

        assert decomposition['numberOfSubdomains'] > 1


class TestResourceMonitor:
    """Test ResourceMonitor class."""

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_monitor_init(self, mock_logger, mock_psutil):
        """Test monitor initialization."""
        from aortacfd_lib.performance_optimizer import ResourceMonitor

        monitor = ResourceMonitor()

        assert monitor.monitoring is False

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_start_stop_monitoring(self, mock_logger, mock_psutil):
        """Test starting and stopping monitoring."""
        from aortacfd_lib.performance_optimizer import ResourceMonitor

        monitor = ResourceMonitor()

        monitor.start_monitoring(interval=10.0)
        assert monitor.monitoring is True

        monitor.stop_monitoring()
        assert monitor.monitoring is False

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_get_current_usage(self, mock_logger, mock_psutil):
        """Test getting current resource usage."""
        from aortacfd_lib.performance_optimizer import ResourceMonitor

        monitor = ResourceMonitor()
        usage = monitor.get_current_usage()

        assert 'cpu_percent' in usage
        assert 'memory_percent' in usage
        assert 'memory_used_gb' in usage
        assert 'timestamp' in usage

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_check_resource_limits(self, mock_logger, mock_psutil):
        """Test resource limit checking."""
        from aortacfd_lib.performance_optimizer import ResourceMonitor

        monitor = ResourceMonitor()

        # Set thresholds that should not trigger warnings
        thresholds = {'cpu_percent': 95, 'memory_percent': 95}
        warnings = monitor.check_resource_limits(thresholds)

        assert isinstance(warnings, list)


class TestAdaptiveTimestepping:
    """Test AdaptiveTimestepping class."""

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_init(self, mock_logger, mock_psutil):
        """Test initialization."""
        from aortacfd_lib.performance_optimizer import AdaptiveTimestepping

        stepper = AdaptiveTimestepping(initial_dt=0.001)

        assert stepper.dt == 0.001
        assert stepper.dt_min == 0.0001
        assert stepper.dt_max == 0.01
        assert stepper.convergence_history == []

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_adjust_timestep_good_convergence(self, mock_logger, mock_psutil):
        """Test timestep adjustment for good convergence."""
        from aortacfd_lib.performance_optimizer import AdaptiveTimestepping

        stepper = AdaptiveTimestepping(initial_dt=0.001)

        # Simulate improving residuals (decreasing trend)
        residuals_seq = [
            {'p': 1e-3, 'U': 1e-3},
            {'p': 5e-4, 'U': 5e-4},
            {'p': 1e-4, 'U': 1e-4},
        ]

        for residuals in residuals_seq:
            stepper.adjust_timestep(residuals)

        # With good convergence (decreasing trend), dt should increase
        # Note: need at least 3 points for trend analysis
        assert stepper.dt >= 0.001

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_adjust_timestep_poor_convergence(self, mock_logger, mock_psutil):
        """Test timestep adjustment for poor convergence."""
        from aortacfd_lib.performance_optimizer import AdaptiveTimestepping

        stepper = AdaptiveTimestepping(initial_dt=0.001)

        # Simulate worsening residuals (increasing trend)
        residuals_seq = [
            {'p': 1e-4, 'U': 1e-4},
            {'p': 5e-4, 'U': 5e-4},
            {'p': 1e-3, 'U': 1e-3},
        ]

        for residuals in residuals_seq:
            stepper.adjust_timestep(residuals)

        # With poor convergence, dt should decrease
        assert stepper.dt <= 0.001

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_timestep_limits(self, mock_logger, mock_psutil):
        """Test timestep respects min/max limits."""
        from aortacfd_lib.performance_optimizer import AdaptiveTimestepping

        stepper = AdaptiveTimestepping(initial_dt=0.001)

        # Try to force very low timestep
        for _ in range(20):
            stepper.adjust_timestep({'p': 1.0, 'U': 1.0})  # High residuals

        assert stepper.dt >= stepper.dt_min

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_convergence_history_limit(self, mock_logger, mock_psutil):
        """Test convergence history is limited to 10 entries."""
        from aortacfd_lib.performance_optimizer import AdaptiveTimestepping

        stepper = AdaptiveTimestepping(initial_dt=0.001)

        # Add more than 10 entries
        for i in range(15):
            stepper.adjust_timestep({'p': 1e-4, 'U': 1e-4})

        assert len(stepper.convergence_history) <= 10


class TestCreatePerformanceReport:
    """Test create_performance_report function."""

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_create_report_structure(self, mock_logger, mock_psutil):
        """Test performance report structure."""
        from aortacfd_lib.performance_optimizer import (
            PerformanceOptimizer, create_performance_report
        )

        optimizer = PerformanceOptimizer({})
        report = create_performance_report(
            optimizer,
            simulation_time=3600.0,
            final_residuals={'p': 1e-5, 'U': 1e-6}
        )

        assert 'simulation_time' in report
        assert 'final_residuals' in report
        assert 'system_resources' in report
        assert 'resource_efficiency' in report
        assert 'recommendations' in report

        assert report['simulation_time'] == 3600.0

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_create_report_recommendations(self, mock_logger, mock_psutil):
        """Test performance report generates recommendations."""
        from aortacfd_lib.performance_optimizer import (
            PerformanceOptimizer, create_performance_report
        )

        optimizer = PerformanceOptimizer({})

        # With poor convergence residuals
        report = create_performance_report(
            optimizer,
            simulation_time=3600.0,
            final_residuals={'p': 1e-2, 'U': 1e-2}  # Poor convergence
        )

        # Should have recommendations about poor convergence
        assert any('convergence' in r.lower() for r in report['recommendations'])

    @patch('aortacfd_lib.performance_optimizer.Logger')
    def test_create_report_empty_residuals(self, mock_logger, mock_psutil):
        """Test performance report with empty residuals."""
        from aortacfd_lib.performance_optimizer import (
            PerformanceOptimizer, create_performance_report
        )

        optimizer = PerformanceOptimizer({})
        report = create_performance_report(
            optimizer,
            simulation_time=3600.0,
            final_residuals={}
        )

        # Should handle empty residuals gracefully
        assert report['resource_efficiency']['convergence_quality'] == 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
