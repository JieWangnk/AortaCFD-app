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
            logs_dir = os.path.join(tmpdir, "logs")
            os.makedirs(logs_dir)
            with open(os.path.join(logs_dir, "log.checkMesh"), 'w') as f:
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


# ---------------------------------------------------------------------------
# Layer-retry logic (_parse_layer_coverage, _mesh_needs_layer_retry,
# _parse_current_nlayers, _retry_with_relaxed_layers)
#
# These tests pin the three bug fixes from fix/mesh-retry-false-positive:
#   1. substring match on "Reducing layer thickness" was firing on the
#      harmless "at 0 nodes" convergence tail and forcing zero-layer
#      retries after successful runs.
#   2. retry loop never rolled back to the best attempt — a partial
#      attempt 1 was being silently clobbered by a zero-layer attempt 4.
#   3. original_layers defaulted to 2, starving every retry from what
#      was actually a 5-layer Strategy C baseline.
# ---------------------------------------------------------------------------


# Realistic snappy log fragment — taken from the actual BPM120 run that
# first surfaced the bug. Attempt 1 produced 1.47 average layers and
# 31.6 % coverage on wall_aorta after the medial-axis solver iterated to
# convergence. The old detector saw the "Reducing layer thickness" tail
# and forced three useless retries.
_BPM120_ATTEMPT1_LOG = """\
displacementMedialAxis : Reducing layer thickness at 220 nodes where thickness to medial axis distance is large
displacementMedialAxis : Reducing layer thickness at 218 nodes where thickness to medial axis distance is large
displacementMedialAxis : Reducing layer thickness at 212 nodes where thickness to medial axis distance is large
displacementMedialAxis : Reducing layer thickness at 50 nodes where thickness to medial axis distance is large
displacementMedialAxis : Reducing layer thickness at 10 nodes where thickness to medial axis distance is large
displacementMedialAxis : Reducing layer thickness at 0 nodes where thickness to medial axis distance is large
displacementMedialAxis : Reducing layer thickness at 0 nodes where thickness to medial axis distance is large
patch      faces    layers   overall thickness
                             [m]       [%]
-----      -----    ------   ---       ---
wall_aorta 18778    1.47     0.000264  31.6

Layer mesh : cells:132196  faces:401480  points:140518
"""

# Retry #3 log — all "Reducing layer thickness at 0 nodes" because the
# iteration converged cleanly BUT with zero layers. The old detector
# still saw the substring and kept retrying.
_BPM120_RETRY3_LOG = """\
displacementMedialAxis : Reducing layer thickness at 0 nodes where thickness to medial axis distance is large
displacementMedialAxis : Reducing layer thickness at 0 nodes where thickness to medial axis distance is large
displacementMedialAxis : Reducing layer thickness at 0 nodes where thickness to medial axis distance is large
patch      faces    layers   overall thickness
                             [m]       [%]
-----      -----    ------   ---       ---
wall_aorta 18769    0        0         0
"""

_HEALTHY_MESH_LOG = """\
patch      faces    layers   overall thickness
                             [m]       [%]
-----      -----    ------   ---       ---
wall_aorta 20000    4.8      0.00045   62.0
"""

_HARD_FAILURE_LOG = """\
Illegal cells after layer addition: 124 cells
patch      faces    layers   overall thickness
                             [m]       [%]
-----      -----    ------   ---       ---
wall_aorta 18000    0        0         0
"""


def _write_logs(case_dir, snappy_content, checkmesh_content=None):
    """Helper: drop snappy + checkMesh logs where the task methods look."""
    logs_dir = os.path.join(case_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    with open(os.path.join(logs_dir, "log.snappyHexMesh"), "w") as f:
        f.write(snappy_content)
    if checkmesh_content is not None:
        with open(os.path.join(logs_dir, "log.checkMesh"), "w") as f:
            f.write(checkmesh_content)


class TestParseLayerCoverage:
    """_parse_layer_coverage reads the final snappy summary table."""

    def test_parses_bpm120_attempt1_summary(self, tmp_path):
        log = tmp_path / "log.snappyHexMesh"
        log.write_text(_BPM120_ATTEMPT1_LOG)

        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        patches = ExecuteMeshingTask._parse_layer_coverage(str(log))
        assert "wall_aorta" in patches
        assert patches["wall_aorta"]["faces"] == 18778
        assert patches["wall_aorta"]["layers"] == pytest.approx(1.47)
        assert patches["wall_aorta"]["coverage_pct"] == pytest.approx(31.6)

    def test_parses_healthy_mesh_summary(self, tmp_path):
        log = tmp_path / "log.snappyHexMesh"
        log.write_text(_HEALTHY_MESH_LOG)

        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        patches = ExecuteMeshingTask._parse_layer_coverage(str(log))
        assert patches["wall_aorta"]["coverage_pct"] == pytest.approx(62.0)

    def test_missing_file_returns_empty_dict(self, tmp_path):
        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        patches = ExecuteMeshingTask._parse_layer_coverage(
            str(tmp_path / "nope.log")
        )
        assert patches == {}

    def test_log_without_summary_returns_empty_dict(self, tmp_path):
        log = tmp_path / "log.snappyHexMesh"
        log.write_text("some snappy output without a final layer report\n")

        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        assert ExecuteMeshingTask._parse_layer_coverage(str(log)) == {}

    def test_max_layer_coverage_picks_highest(self):
        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        patches = {
            "wall_aorta": {"coverage_pct": 31.6},
            "wall_secondary": {"coverage_pct": 0.0},
        }
        assert ExecuteMeshingTask._max_layer_coverage(patches) == 31.6

    def test_max_layer_coverage_empty_dict(self):
        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        assert ExecuteMeshingTask._max_layer_coverage({}) == 0.0


class TestMeshNeedsLayerRetry:
    """_mesh_needs_layer_retry must not false-positive on benign messages."""

    def _make_task(self, config=None):
        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        return ExecuteMeshingTask(config or {})

    def test_healthy_mesh_does_not_retry(self, tmp_path):
        _write_logs(str(tmp_path), _HEALTHY_MESH_LOG, "Mesh OK.\n")
        task = self._make_task()
        assert task._mesh_needs_layer_retry(str(tmp_path)) is False

    def test_bpm120_attempt1_does_not_retry_when_above_threshold(self, tmp_path):
        # Coverage 31.6 % beats the default threshold of 25 %, so the
        # partially-successful attempt 1 should be accepted as-is. This
        # is the exact scenario the old substring-match broke.
        _write_logs(str(tmp_path), _BPM120_ATTEMPT1_LOG, "Mesh OK.\n")
        task = self._make_task()
        assert task._mesh_needs_layer_retry(str(tmp_path)) is False

    def test_retry_when_below_threshold(self, tmp_path):
        # A run that converged cleanly but with zero layers should still
        # be retried because coverage is below threshold.
        _write_logs(str(tmp_path), _BPM120_RETRY3_LOG, "Mesh OK.\n")
        task = self._make_task()
        assert task._mesh_needs_layer_retry(str(tmp_path)) is True

    def test_retry_on_hard_failure_even_when_coverage_unknown(self, tmp_path):
        _write_logs(str(tmp_path), _HARD_FAILURE_LOG, "Mesh OK.\n")
        task = self._make_task()
        assert task._mesh_needs_layer_retry(str(tmp_path)) is True

    def test_retry_on_checkmesh_failed(self, tmp_path):
        _write_logs(
            str(tmp_path),
            _HEALTHY_MESH_LOG,
            "  non-orthogonality > 70: 42 ***FAILED***\n",
        )
        task = self._make_task()
        assert task._mesh_needs_layer_retry(str(tmp_path)) is True

    def test_no_retry_when_layers_disabled(self, tmp_path):
        _write_logs(str(tmp_path), _HARD_FAILURE_LOG, "Mesh OK.\n")
        task = self._make_task(
            {"mesh": {"SNAPPY_SETTINGS": {"addLayers": False}}}
        )
        assert task._mesh_needs_layer_retry(str(tmp_path)) is False

    def test_respects_custom_threshold(self, tmp_path):
        # With threshold raised to 40 %, the BPM120 attempt 1 result
        # (31.6 %) should now trigger a retry.
        _write_logs(str(tmp_path), _BPM120_ATTEMPT1_LOG, "Mesh OK.\n")
        task = self._make_task(
            {"mesh": {"layer_coverage_threshold": 40.0}}
        )
        assert task._mesh_needs_layer_retry(str(tmp_path)) is True

    def test_missing_snappy_log_does_not_retry(self, tmp_path):
        task = self._make_task()
        # No logs directory at all.
        assert task._mesh_needs_layer_retry(str(tmp_path)) is False


class TestParseCurrentNLayers:
    """_parse_current_nlayers reads the actual nSurfaceLayers from the dict."""

    def test_reads_five_layers(self, tmp_path):
        dict_path = tmp_path / "snappyHexMeshDict"
        dict_path.write_text(
            "addLayersControls\n"
            "{\n"
            "    nSurfaceLayers 5;\n"
            "    expansionRatio 1.2;\n"
            "}\n"
        )

        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        assert ExecuteMeshingTask._parse_current_nlayers(str(dict_path)) == 5

    def test_missing_dict_returns_zero(self, tmp_path):
        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        assert ExecuteMeshingTask._parse_current_nlayers(
            str(tmp_path / "nope")
        ) == 0

    def test_dict_without_nsurfacelayers_returns_zero(self, tmp_path):
        dict_path = tmp_path / "snappyHexMeshDict"
        dict_path.write_text("addLayers false;\n")

        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        assert ExecuteMeshingTask._parse_current_nlayers(str(dict_path)) == 0


class TestPolyMeshSnapshot:
    """_snapshot_polymesh + _restore_polymesh round-trip."""

    def _make_task(self):
        from workflow.tasks.execution_tasks import ExecuteMeshingTask
        return ExecuteMeshingTask({})

    def _make_fake_polymesh(self, case_dir, marker):
        poly = os.path.join(case_dir, "constant", "polyMesh")
        os.makedirs(poly, exist_ok=True)
        for name in ("points", "faces", "owner", "neighbour", "boundary"):
            with open(os.path.join(poly, name), "w") as f:
                f.write(f"{name}:{marker}\n")
        return poly

    def test_snapshot_creates_sibling_directory(self, tmp_path):
        case = str(tmp_path)
        self._make_fake_polymesh(case, "v1")
        task = self._make_task()
        snap = task._snapshot_polymesh(case, "attempt1")
        assert snap is not None
        assert os.path.isdir(snap)
        assert snap.endswith("polyMesh.attempt1")
        assert (Path(snap) / "points").read_text() == "points:v1\n"

    def test_snapshot_returns_none_when_source_missing(self, tmp_path):
        task = self._make_task()
        assert task._snapshot_polymesh(str(tmp_path), "attempt1") is None

    def test_restore_replaces_current_mesh(self, tmp_path):
        case = str(tmp_path)
        self._make_fake_polymesh(case, "original")
        task = self._make_task()
        snap = task._snapshot_polymesh(case, "baseline")

        # Clobber the live polyMesh with fresh content...
        self._make_fake_polymesh(case, "clobbered")
        poly = os.path.join(case, "constant", "polyMesh")
        assert (Path(poly) / "points").read_text() == "points:clobbered\n"

        # ...then restore should bring back the snapshot contents.
        assert task._restore_polymesh(case, snap) is True
        assert (Path(poly) / "points").read_text() == "points:original\n"

    def test_restore_noop_when_snapshot_missing(self, tmp_path):
        task = self._make_task()
        assert (
            task._restore_polymesh(str(tmp_path), str(tmp_path / "nope"))
            is False
        )


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

            # Create closeness files (already renamed with .stl, as _rename does before _distribute)
            closeness_files = [
                "wall_aorta.stl.closeness.internalPointCloseness",
                "wall_aorta.stl.closeness.cellPointCloseness"
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

                for f in closeness_files:
                    assert os.path.exists(os.path.join(proc_tri_dir, f))


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
