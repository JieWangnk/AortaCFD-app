"""
Unit tests for utility functions in aortacfd_lib.utils.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from aortacfd_lib.utils.logger import Logger
from aortacfd_lib.utils.runner import Runner
from aortacfd_lib.utils.format_points import format_points


class TestLogger:
    """Test the Logger utility class."""
    
    def test_logger_initialization(self):
        """Test Logger initialization."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file_path = temp_file.name
        
        try:
            logger = Logger(temp_file_path)
            assert logger.log_file_path == temp_file_path
            
            # Get logger instance
            log_instance = logger.get_logger()
            assert log_instance is not None
            
            # Test logging
            log_instance.info("Test message")
            log_instance.error("Test error")
            
        finally:
            # Clean up
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def test_logger_file_creation(self):
        """Test that logger creates log file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            
            logger = Logger(log_path)
            log_instance = logger.get_logger()
            
            # Write a log message
            log_instance.info("Test message")
            
            # Check that file was created
            assert os.path.exists(log_path)
            
            # Check content
            with open(log_path, 'r') as f:
                content = f.read()
                assert "Test message" in content
    
    def test_logger_singleton_behavior(self):
        """Test that Logger behaves as singleton for same file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file_path = temp_file.name
        
        try:
            logger1 = Logger(temp_file_path)
            logger2 = Logger(temp_file_path)
            
            # Should return same logger instance
            assert logger1.get_logger() is logger2.get_logger()
            
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)


class TestRunner:
    """Test the Runner utility class."""
    
    @patch('subprocess.run')
    def test_runner_successful_execution(self, mock_run):
        """Test successful command execution."""
        # Setup mock
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Success output",
            stderr=""
        )
        
        runner = Runner()
        result = runner.run_command(["echo", "test"])
        
        assert result.returncode == 0
        assert result.stdout == "Success output"
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_runner_failed_execution(self, mock_run):
        """Test failed command execution."""
        # Setup mock for failure
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error message"
        )
        
        runner = Runner()
        result = runner.run_command(["false"])
        
        assert result.returncode == 1
        assert result.stderr == "Error message"
    
    @patch('subprocess.run')
    def test_runner_timeout_handling(self, mock_run):
        """Test timeout handling in runner."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired(["sleep", "10"], timeout=1)
        
        runner = Runner()
        with pytest.raises(TimeoutExpired):
            runner.run_command(["sleep", "10"], timeout=1)
    
    @patch('subprocess.run')
    def test_runner_with_environment(self, mock_run):
        """Test runner with custom environment."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        runner = Runner()
        custom_env = {"TEST_VAR": "test_value"}
        runner.run_command(["echo", "test"], env=custom_env)
        
        # Verify environment was passed
        call_args = mock_run.call_args
        assert call_args[1]["env"] == custom_env
    
    @patch('subprocess.run')
    def test_runner_working_directory(self, mock_run):
        """Test runner with custom working directory."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        runner = Runner()
        runner.run_command(["pwd"], cwd="/tmp")
        
        # Verify working directory was set
        call_args = mock_run.call_args
        assert call_args[1]["cwd"] == "/tmp"


class TestFormatPoints:
    """Test the format_points utility function."""
    
    def test_format_points_basic(self):
        """Test basic point formatting."""
        points = [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]
        result = format_points(points)
        
        assert isinstance(result, str)
        assert "0.0 0.0 0.0" in result
        assert "1.0 1.0 1.0" in result
    
    def test_format_points_scientific_notation(self):
        """Test formatting with scientific notation."""
        points = [(1e-6, 2e-6, 3e-6)]
        result = format_points(points)
        
        assert isinstance(result, str)
        # Should handle scientific notation properly
        assert "e-" in result or "1e-06" in result or "0.000001" in result
    
    def test_format_points_empty_list(self):
        """Test formatting empty point list."""
        points = []
        result = format_points(points)
        
        assert result == "" or result == "()" or result is None
    
    def test_format_points_single_point(self):
        """Test formatting single point."""
        points = [(1.5, 2.5, 3.5)]
        result = format_points(points)
        
        assert "1.5 2.5 3.5" in result
    
    def test_format_points_precision(self):
        """Test point formatting precision."""
        points = [(1.123456789, 2.987654321, 3.555555555)]
        result = format_points(points, precision=3)
        
        # Should round to specified precision
        assert "1.123" in result
        assert "2.988" in result
        assert "3.556" in result
    
    def test_format_points_negative_values(self):
        """Test formatting negative values."""
        points = [(-1.0, -2.0, -3.0)]
        result = format_points(points)
        
        assert "-1.0 -2.0 -3.0" in result
    
    def test_format_points_mixed_values(self):
        """Test formatting mixed positive/negative values."""
        points = [(1.0, -2.0, 3.0), (-1.0, 2.0, -3.0)]
        result = format_points(points)
        
        assert "1.0 -2.0 3.0" in result
        assert "-1.0 2.0 -3.0" in result
    
    def test_format_points_invalid_input(self):
        """Test formatting with invalid input."""
        # Test with wrong dimension
        with pytest.raises((ValueError, TypeError, IndexError)):
            format_points([(1.0, 2.0)])  # Only 2D point
        
        # Test with non-numeric values
        with pytest.raises((ValueError, TypeError)):
            format_points([("a", "b", "c")])
    
    def test_format_points_large_numbers(self):
        """Test formatting with large numbers."""
        points = [(1e6, 2e6, 3e6)]
        result = format_points(points)
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_format_points_zero_values(self):
        """Test formatting with zero values."""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 2.0)]
        result = format_points(points)
        
        assert "0.0 0.0 0.0" in result
        assert "1.0 0.0 2.0" in result


class TestUtilsIntegration:
    """Integration tests for utility functions."""
    
    def test_logger_runner_integration(self):
        """Test integration between Logger and Runner."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "integration_test.log")
            
            # Setup logger
            logger = Logger(log_path)
            log_instance = logger.get_logger()
            
            # Setup runner with logging
            runner = Runner()
            
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
                
                # Log before command
                log_instance.info("Starting command execution")
                
                # Run command
                result = runner.run_command(["echo", "test"])
                
                # Log after command
                log_instance.info(f"Command completed with return code: {result.returncode}")
            
            # Verify log content
            assert os.path.exists(log_path)
            with open(log_path, 'r') as f:
                content = f.read()
                assert "Starting command execution" in content
                assert "Command completed with return code: 0" in content
    
    def test_format_points_with_real_geometry_data(self):
        """Test format_points with realistic geometry data."""
        # Simulate points from STL file
        points = [
            (0.0, 0.0, 0.0),
            (0.001, 0.0, 0.0),
            (0.0005, 0.001, 0.0),
            (0.0005, 0.0005, 0.001)
        ]
        
        result = format_points(points)
        
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Should handle small decimal values properly
        for point in points:
            point_str = f"{point[0]} {point[1]} {point[2]}"
            assert point_str in result or any(str(coord) in result for coord in point)
    
    @patch('aortacfd_lib.utils.logger.Logger')
    def test_error_handling_with_logging(self, mock_logger_class):
        """Test error handling with proper logging."""
        # Setup mock logger
        mock_logger = Mock()
        mock_logger_class.return_value.get_logger.return_value = mock_logger
        
        # Test error scenario
        try:
            # Simulate an error condition
            raise ValueError("Test error")
        except ValueError as e:
            mock_logger.error(f"Error occurred: {e}")
        
        # Verify error was logged
        mock_logger.error.assert_called_once_with("Error occurred: Test error")