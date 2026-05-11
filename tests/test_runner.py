"""
Test suite for utils/runner.py module.

Tests cover:
- Runner class initialization and run_command method
- run_command function with OpenFOAM environment sourcing
- Error handling
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestRunnerClass:
    """Test Runner class."""

    def test_runner_initialization(self):
        """Test Runner class initialization."""
        from aortacfd_lib.utils.runner import Runner

        runner = Runner()
        assert runner is not None

    @patch("aortacfd_lib.utils.runner.subprocess.run")
    def test_run_command_basic(self, mock_run):
        """Test run_command method with basic arguments."""
        from aortacfd_lib.utils.runner import Runner

        mock_run.return_value = MagicMock(returncode=0, stdout="output")

        runner = Runner()
        result = runner.run_command(["echo", "hello"])

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["echo", "hello"]

    @patch("aortacfd_lib.utils.runner.subprocess.run")
    def test_run_command_with_timeout(self, mock_run):
        """Test run_command method with timeout."""
        from aortacfd_lib.utils.runner import Runner

        mock_run.return_value = MagicMock(returncode=0)

        runner = Runner()
        runner.run_command(["ls"], timeout=30)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 30

    @patch("aortacfd_lib.utils.runner.subprocess.run")
    def test_run_command_with_cwd(self, mock_run):
        """Test run_command method with working directory."""
        from aortacfd_lib.utils.runner import Runner

        mock_run.return_value = MagicMock(returncode=0)

        runner = Runner()
        runner.run_command(["pwd"], cwd="/tmp")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == "/tmp"

    @patch("aortacfd_lib.utils.runner.subprocess.run")
    def test_run_command_with_env(self, mock_run):
        """Test run_command method with custom environment."""
        from aortacfd_lib.utils.runner import Runner

        mock_run.return_value = MagicMock(returncode=0)

        custom_env = {"PATH": "/usr/bin", "HOME": "/home/test"}
        runner = Runner()
        runner.run_command(["env"], env=custom_env)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"] == custom_env

    @patch("aortacfd_lib.utils.runner.subprocess.run")
    def test_run_command_capture_output(self, mock_run):
        """Test run_command method captures output by default."""
        from aortacfd_lib.utils.runner import Runner

        mock_run.return_value = MagicMock(returncode=0)

        runner = Runner()
        runner.run_command(["echo", "test"])

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True


class TestRunCommandFunction:
    """Test run_command function with OpenFOAM environment."""

    def test_run_command_missing_env_path_raises(self, tmp_path):
        """Test that missing openfoam_env_path raises ValueError."""
        from aortacfd_lib.utils.runner import run_command

        config = {}  # No openfoam_env_path

        with pytest.raises(ValueError, match="openfoam_env_path"):
            run_command(config, ["blockMesh"], str(tmp_path), "log.blockMesh")

    @patch("aortacfd_lib.utils.runner.subprocess.run")
    def test_run_command_success(self, mock_run, tmp_path):
        """Test successful command execution."""
        from aortacfd_lib.utils.runner import run_command

        mock_run.return_value = MagicMock()

        config = {"openfoam_env_path": "/opt/openfoam/etc/bashrc"}
        run_command(config, ["blockMesh"], str(tmp_path), "log.blockMesh")

        # Check that bash -c was called
        call_args = mock_run.call_args
        assert call_args[0][0][0] == "bash"
        assert call_args[0][0][1] == "-c"
        # Check command includes source and blockMesh
        assert "source" in call_args[0][0][2]
        assert "blockMesh" in call_args[0][0][2]

    @patch("aortacfd_lib.utils.runner.subprocess.run")
    def test_run_command_creates_logs_dir(self, mock_run, tmp_path):
        """Test that command creates logs directory."""
        from aortacfd_lib.utils.runner import run_command

        mock_run.return_value = MagicMock()

        config = {"openfoam_env_path": "/opt/openfoam/etc/bashrc"}
        run_command(config, ["checkMesh"], str(tmp_path), "log.checkMesh")

        logs_dir = tmp_path / "logs"
        assert logs_dir.exists()

    @patch("aortacfd_lib.utils.runner.subprocess.run")
    def test_run_command_with_args(self, mock_run, tmp_path):
        """Test command with multiple arguments."""
        from aortacfd_lib.utils.runner import run_command

        mock_run.return_value = MagicMock()

        config = {"openfoam_env_path": "/opt/openfoam/etc/bashrc"}
        run_command(
            config,
            ["snappyHexMesh", "-overwrite", "-dict", "system/snappyHexMeshDict"],
            str(tmp_path),
            "log.snappyHexMesh",
        )

        call_args = mock_run.call_args
        assert "snappyHexMesh -overwrite -dict system/snappyHexMeshDict" in call_args[0][0][2]

    @patch("aortacfd_lib.utils.runner.subprocess.run")
    def test_run_command_failure_raises(self, mock_run, tmp_path):
        """Test that command failure raises CommandExecutionError."""
        from aortacfd_lib.utils.runner import run_command, CommandExecutionError

        mock_run.side_effect = subprocess.CalledProcessError(1, "blockMesh")

        config = {"openfoam_env_path": "/opt/openfoam/etc/bashrc"}

        with pytest.raises(CommandExecutionError, match="failed"):
            run_command(config, ["blockMesh"], str(tmp_path), "log.blockMesh")

    @patch("aortacfd_lib.utils.runner.subprocess.run")
    def test_run_command_bash_not_found_raises(self, mock_run, tmp_path):
        """Test that missing bash raises FileNotFoundError."""
        from aortacfd_lib.utils.runner import run_command

        mock_run.side_effect = FileNotFoundError("bash not found")

        config = {"openfoam_env_path": "/opt/openfoam/etc/bashrc"}

        with pytest.raises(FileNotFoundError):
            run_command(config, ["blockMesh"], str(tmp_path), "log.blockMesh")


class TestCommandExecutionError:
    """Test CommandExecutionError exception."""

    def test_exception_creation(self):
        """Test CommandExecutionError can be created with message."""
        from aortacfd_lib.utils.runner import CommandExecutionError

        error = CommandExecutionError("Test error")
        assert str(error) == "Test error"

    def test_exception_inheritance(self):
        """Test CommandExecutionError inherits from Exception."""
        from aortacfd_lib.utils.runner import CommandExecutionError

        assert issubclass(CommandExecutionError, Exception)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
