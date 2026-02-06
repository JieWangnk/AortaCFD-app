"""
Test suite for execution tasks module.

Tests cover:
- ExecuteMeshingTask
- ExecuteSolverTask
- ExecuteReconstructionTask
- ExecutePostProcessingTask
- ExecuteHemodynamicsTask
"""

import pytest
import sys
import os
import tempfile
import glob
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from workflow.base_task import ExecutionContext


class TestExecuteMeshingTask:
    """Test ExecuteMeshingTask class."""

    def test_task_initialization(self):
        """Test task initialization."""
        config = {
            'mesh': {
                'SNAPPY_SETTINGS': {
                    'parallel': False
                }
            }
        }

        from workflow.tasks.execution_tasks import ExecuteMeshingTask

        task = ExecuteMeshingTask(config)
        assert task.config == config

    def test_serial_meshing_commands(self):
        """Test serial meshing command sequence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'mesh': {
                    'SNAPPY_SETTINGS': {
                        'parallel': False
                    }
                }
            }

            from workflow.tasks.execution_tasks import ExecuteMeshingTask

            task = ExecuteMeshingTask(config)
            context = {'case_directory': tmpdir}

            # Track commands called
            commands_called = []

            def mock_run_command(config, command, case_dir, log_file):
                commands_called.append(command)

            with patch('workflow.tasks.execution_tasks.run_command', mock_run_command):
                with patch.object(task, '_check_mesh_quality', return_value="100 cells"):
                    with patch.object(task, '_create_foam_file'):
                        result = task.execute(context)

            # Should call blockMesh, surfaceFeatures, snappyHexMesh, checkMesh
            assert any('blockMesh' in str(cmd) for cmd in commands_called)
            assert any('surfaceFeatures' in str(cmd) for cmd in commands_called)
            assert any('snappyHexMesh' in str(cmd) for cmd in commands_called)
            assert any('checkMesh' in str(cmd) for cmd in commands_called)

    def test_parallel_meshing_commands(self):
        """Test parallel meshing command sequence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create system directory for decomposeParDict
            os.makedirs(os.path.join(tmpdir, "system"))
            with open(os.path.join(tmpdir, "system", "decomposeParDict"), 'w') as f:
                f.write("numberOfSubdomains  4;")

            config = {
                'mesh': {
                    'SNAPPY_SETTINGS': {
                        'parallel': True,
                        'nProcessors': 4
                    }
                },
                'run_settings': {
                    'subdomains': 8  # Different from meshing
                }
            }

            from workflow.tasks.execution_tasks import ExecuteMeshingTask

            task = ExecuteMeshingTask(config)
            context = {'case_directory': tmpdir}

            commands_called = []

            def mock_run_command(config, command, case_dir, log_file):
                commands_called.append(command)

            with patch('workflow.tasks.execution_tasks.run_command', mock_run_command):
                with patch.object(task, '_check_mesh_quality', return_value="100 cells"):
                    with patch.object(task, '_create_foam_file'):
                        with patch.object(task, '_distribute_closeness_files'):
                            with patch.object(task, '_cleanup_processor_directories'):
                                result = task.execute(context)

            # Should include parallel commands
            assert any('decomposePar' in str(cmd) for cmd in commands_called)
            assert any('mpirun' in str(cmd) for cmd in commands_called)
            assert any('reconstructPar' in str(cmd) for cmd in commands_called)

    def test_create_foam_file(self):
        """Test .foam file creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {}

            from workflow.tasks.execution_tasks import ExecuteMeshingTask

            task = ExecuteMeshingTask(config)
            task._create_foam_file(tmpdir)

            # Check .foam file was created
            foam_files = glob.glob(os.path.join(tmpdir, "*.foam"))
            assert len(foam_files) == 1

    def test_check_mesh_quality(self):
        """Test mesh quality checking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create checkMesh log
            log_content = """
Mesh stats
    cells: 123456
Max non-orthogonality = 50.0
Max skewness = 2.0
Max aspect ratio = 50.0
Mesh OK.
"""
            with open(os.path.join(tmpdir, "log.checkMesh"), 'w') as f:
                f.write(log_content)

            config = {}

            from workflow.tasks.execution_tasks import ExecuteMeshingTask

            task = ExecuteMeshingTask(config)
            result = task._check_mesh_quality(tmpdir)

            # Should return summary string
            assert "123,456 cells" in result
            assert "OK" in result

    def test_override_decompose_par_dict(self):
        """Test decomposeParDict modification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            system_dir = os.path.join(tmpdir, "system")
            os.makedirs(system_dir)

            decompose_dict = os.path.join(system_dir, "decomposeParDict")
            with open(decompose_dict, 'w') as f:
                f.write("numberOfSubdomains  4;\nn               (1 1 4);")

            config = {}

            from workflow.tasks.execution_tasks import ExecuteMeshingTask

            task = ExecuteMeshingTask(config)
            task._override_decompose_par_dict(tmpdir, 8)

            with open(decompose_dict, 'r') as f:
                content = f.read()

            assert "numberOfSubdomains  8;" in content
            assert "(1 1 8)" in content

    def test_cleanup_processor_directories(self):
        """Test processor directory cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create processor directories
            for i in range(4):
                proc_dir = os.path.join(tmpdir, f"processor{i}")
                os.makedirs(proc_dir)
                with open(os.path.join(proc_dir, "test.txt"), 'w') as f:
                    f.write("test")

            config = {}

            from workflow.tasks.execution_tasks import ExecuteMeshingTask

            task = ExecuteMeshingTask(config)
            task._cleanup_processor_directories(tmpdir)

            # Processor directories should be gone
            proc_dirs = glob.glob(os.path.join(tmpdir, "processor*"))
            assert len(proc_dirs) == 0


class TestExecuteSolverTask:
    """Test ExecuteSolverTask class."""

    def test_serial_solver(self):
        """Test serial solver execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'run_settings': {
                    'solution_type': 'serial'
                },
                'simulation_control': {
                    'controlDict': {
                        'application': 'foamRun'
                    }
                }
            }

            from workflow.tasks.execution_tasks import ExecuteSolverTask

            task = ExecuteSolverTask(config)
            context = {'case_directory': tmpdir}

            commands_called = []

            def mock_run_command(config, command, case_dir, log_file):
                commands_called.append(command)

            with patch('workflow.tasks.execution_tasks.run_command', mock_run_command):
                result = task.execute(context)

            # Should call solver directly
            assert any('foamRun' in str(cmd) for cmd in commands_called)
            # Should NOT call decomposePar for serial
            assert not any('decomposePar' in str(cmd) for cmd in commands_called)

    def test_parallel_solver(self):
        """Test parallel solver execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'run_settings': {
                    'solution_type': 'parallel',
                    'subdomains': 4,
                    'skip_reconstruction': False,
                    'cleanup_processors': False  # Don't cleanup in test
                },
                'simulation_control': {
                    'controlDict': {
                        'application': 'foamRun'
                    }
                }
            }

            from workflow.tasks.execution_tasks import ExecuteSolverTask

            task = ExecuteSolverTask(config)
            context = {'case_directory': tmpdir}

            commands_called = []

            def mock_run_command(config, command, case_dir, log_file):
                commands_called.append(command)

            with patch('workflow.tasks.execution_tasks.run_command', mock_run_command):
                result = task.execute(context)

            # Should call decomposePar and mpirun
            assert any('decomposePar' in str(cmd) for cmd in commands_called)
            assert any('mpirun' in str(cmd) for cmd in commands_called)
            assert any('reconstructPar' in str(cmd) for cmd in commands_called)

    def test_parallel_solver_skip_reconstruction(self):
        """Test parallel solver with skip_reconstruction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                'run_settings': {
                    'solution_type': 'parallel',
                    'subdomains': 4,
                    'skip_reconstruction': True
                },
                'simulation_control': {
                    'controlDict': {
                        'application': 'foamRun'
                    }
                }
            }

            from workflow.tasks.execution_tasks import ExecuteSolverTask

            task = ExecuteSolverTask(config)
            context = {'case_directory': tmpdir}

            commands_called = []

            def mock_run_command(config, command, case_dir, log_file):
                commands_called.append(command)

            with patch('workflow.tasks.execution_tasks.run_command', mock_run_command):
                result = task.execute(context)

            # Should NOT call reconstructPar
            assert not any('reconstructPar' in str(cmd) for cmd in commands_called)
            # Context should mark case as decomposed
            assert context.get('case_decomposed') is True

    def test_solver_failure_handling(self):
        """Test solver failure handling."""
        config = {
            'run_settings': {
                'solution_type': 'serial'
            },
            'simulation_control': {
                'controlDict': {
                    'application': 'foamRun'
                }
            }
        }

        from workflow.tasks.execution_tasks import ExecuteSolverTask
        from aortacfd_lib.utils.runner import CommandExecutionError

        task = ExecuteSolverTask(config)
        context = {'case_directory': '/tmp/test'}

        def mock_run_command_fail(config, command, case_dir, log_file):
            raise CommandExecutionError("Solver failed")

        with patch('workflow.tasks.execution_tasks.run_command', mock_run_command_fail):
            result = task.execute(context)

        assert result is False


class TestExecuteReconstructionTask:
    """Test ExecuteReconstructionTask class."""

    def test_reconstruction_no_processor_dirs(self):
        """Test reconstruction when no processor directories exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {'run_settings': {}}

            from workflow.tasks.execution_tasks import ExecuteReconstructionTask

            task = ExecuteReconstructionTask(config)
            context = {'case_directory': tmpdir}

            # Should return True (nothing to reconstruct)
            result = task.execute(context)
            assert result is True

    def test_reconstruction_with_processor_dirs(self):
        """Test reconstruction with processor directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create processor directories
            for i in range(4):
                os.makedirs(os.path.join(tmpdir, f"processor{i}"))

            config = {'run_settings': {}}

            from workflow.tasks.execution_tasks import ExecuteReconstructionTask

            task = ExecuteReconstructionTask(config)
            context = {'case_directory': tmpdir}

            commands_called = []

            def mock_run_command(config, command, case_dir, log_file):
                commands_called.append(command)

            with patch('workflow.tasks.execution_tasks.run_command', mock_run_command):
                result = task.execute(context)

            # Should call reconstructPar
            assert any('reconstructPar' in str(cmd) for cmd in commands_called)
            assert context.get('case_decomposed') is False


class TestExecutePostProcessingTask:
    """Test ExecutePostProcessingTask class."""

    def test_pvbatch_not_found(self):
        """Test behavior when pvbatch is not found."""
        config = {
            'post_processing': {}
        }

        from workflow.tasks.execution_tasks import ExecutePostProcessingTask

        task = ExecutePostProcessingTask(config)
        context = {'case_directory': '/tmp/test'}

        with patch('shutil.which', return_value=None):
            result = task.execute(context)

        assert result is False

    def test_pvbatch_from_config(self):
        """Test using pvbatch path from config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock pvbatch executable
            pvbatch_path = os.path.join(tmpdir, "pvbatch")
            with open(pvbatch_path, 'w') as f:
                f.write("#!/bin/bash\necho test")
            os.chmod(pvbatch_path, 0o755)

            # Create mock script
            script_dir = os.path.join(tmpdir, "src", "aortacfd_lib")
            os.makedirs(script_dir)
            script_path = os.path.join(script_dir, "post_processor.py")
            with open(script_path, 'w') as f:
                f.write("# mock script")

            config = {
                'post_processing': {
                    'pvbatch_exe': pvbatch_path
                }
            }

            from workflow.tasks.execution_tasks import ExecutePostProcessingTask

            task = ExecutePostProcessingTask(config)
            context = {'case_directory': tmpdir}

            # Change to tmpdir so script path works
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                commands_called = []

                def mock_run_command(config, command, case_dir, log_file):
                    commands_called.append(command)

                with patch('workflow.tasks.execution_tasks.run_command', mock_run_command):
                    result = task.execute(context)

                # Should have called pvbatch
                if result:
                    assert any(pvbatch_path in str(cmd) for cmd in commands_called)
            finally:
                os.chdir(original_cwd)


class TestExecuteHemodynamicsTask:
    """Test ExecuteHemodynamicsTask class."""

    def test_hemodynamics_creates_reports_dir(self):
        """Test that hemodynamics task creates reports directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "openfoam")
            os.makedirs(case_dir)

            config = {}

            from workflow.tasks.execution_tasks import ExecuteHemodynamicsTask

            task = ExecuteHemodynamicsTask(config)
            context = {'case_directory': case_dir}

            # Mock the analysis function (imported inside execute)
            mock_results = Mock()
            mock_results.wss_mean = 0.5
            mock_results.wss_max = 2.0
            mock_results.inlet_type = 'CONSTANT'
            mock_results.is_pulsatile = False
            mock_results.tawss_mean = 0
            mock_results.tawss_max = 0
            mock_results.osi_mean = 0
            mock_results.osi_max = 0
            mock_results.rrt_mean = 0
            mock_results.rrt_max = 0
            mock_results.pressure_drop_mmhg = {}

            with patch('aortacfd_lib.hemodynamics_postprocessor.run_hemodynamics_analysis', return_value=mock_results):
                result = task.execute(context)

            # Reports directory should exist
            reports_dir = os.path.join(tmpdir, "reports")
            assert os.path.exists(reports_dir)

    def test_hemodynamics_basic_instantiation(self):
        """Test basic task instantiation."""
        config = {}

        from workflow.tasks.execution_tasks import ExecuteHemodynamicsTask

        task = ExecuteHemodynamicsTask(config)
        assert task.config == config

    def test_hemodynamics_pulsatile_output(self):
        """Test output formatting for pulsatile flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "openfoam")
            os.makedirs(case_dir)

            config = {}

            from workflow.tasks.execution_tasks import ExecuteHemodynamicsTask

            task = ExecuteHemodynamicsTask(config)
            context = {'case_directory': case_dir}

            mock_results = Mock()
            mock_results.wss_mean = 0.5
            mock_results.wss_max = 2.0
            mock_results.inlet_type = 'TIMEVARYING'
            mock_results.is_pulsatile = True
            mock_results.tawss_mean = 0.4
            mock_results.tawss_max = 1.8
            mock_results.osi_mean = 0.15
            mock_results.osi_max = 0.45
            mock_results.rrt_mean = 2.5
            mock_results.rrt_max = 8.0
            mock_results.pressure_drop_mmhg = {'outlet1': 5.2, 'outlet2': 3.1}

            with patch('aortacfd_lib.hemodynamics_postprocessor.run_hemodynamics_analysis', return_value=mock_results):
                result = task.execute(context)

            assert result is True


class TestMeshDistribution:
    """Test mesh distribution helper functions."""

    def test_distribute_closeness_files(self):
        """Test closeness file distribution to processor directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create triSurface directory with closeness files
            tri_surface_dir = os.path.join(tmpdir, "constant", "triSurface")
            os.makedirs(tri_surface_dir)

            # Create closeness files
            closeness_files = [
                "wall_aorta.closeness.internalPointCloseness",
                "wall_aorta.closeness.cellPointCloseness"
            ]
            for f in closeness_files:
                with open(os.path.join(tri_surface_dir, f), 'w') as fh:
                    fh.write("test")

            config = {}

            from workflow.tasks.execution_tasks import ExecuteMeshingTask

            task = ExecuteMeshingTask(config)
            task._distribute_closeness_files(tmpdir, 2)

            # Check files were distributed
            for i in range(2):
                proc_tri_dir = os.path.join(tmpdir, f"processor{i}", "constant", "triSurface")
                assert os.path.exists(proc_tri_dir)

                # Check files exist with .stl added
                for f in closeness_files:
                    # Files should have .stl inserted
                    expected_file = f.replace(".closeness.", ".stl.closeness.")
                    assert os.path.exists(os.path.join(proc_tri_dir, expected_file))


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
