"""
Test suite for format_points utilities.

Tests cover:
- EnhancedPointsFormatter class
- format_points function
- File I/O operations
- Format version handling
"""

import pytest
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestFormatPointsFunction:
    """Test format_points utility function."""

    def test_format_empty_list(self):
        """Test formatting empty point list."""
        from aortacfd_lib.utils.format_points import format_points

        result = format_points([])

        assert result == ""

    def test_format_single_point(self):
        """Test formatting single point."""
        from aortacfd_lib.utils.format_points import format_points

        result = format_points([(1.0, 2.0, 3.0)])

        assert "1.0" in result
        assert "2.0" in result
        assert "3.0" in result

    def test_format_multiple_points(self):
        """Test formatting multiple points."""
        from aortacfd_lib.utils.format_points import format_points

        points = [(0.0, 0.0, 0.0), (1.0, 2.0, 3.0), (4.5, 5.5, 6.5)]
        result = format_points(points)

        lines = result.strip().split('\n')
        assert len(lines) == 3

    def test_format_with_precision(self):
        """Test formatting with different precision."""
        from aortacfd_lib.utils.format_points import format_points

        points = [(1.23456, 2.34567, 3.45678)]
        result = format_points(points, precision=2)

        # Should have 2 decimal places
        assert "1.23" in result

    def test_format_small_numbers(self):
        """Test formatting very small numbers."""
        from aortacfd_lib.utils.format_points import format_points

        points = [(0.0001, 0.0002, 0.0003)]
        result = format_points(points)

        # Small numbers should use appropriate precision
        assert result != ""

    def test_format_zero_values(self):
        """Test formatting zero values."""
        from aortacfd_lib.utils.format_points import format_points

        points = [(0.0, 0.0, 0.0)]
        result = format_points(points)

        assert "0.0" in result

    def test_format_invalid_point_length(self):
        """Test error on invalid point length."""
        from aortacfd_lib.utils.format_points import format_points

        with pytest.raises(ValueError) as exc_info:
            format_points([(1.0, 2.0)])  # Only 2 coordinates

        assert "3 coordinates" in str(exc_info.value)

    def test_format_very_small_numbers(self):
        """Test formatting very small non-zero numbers."""
        from aortacfd_lib.utils.format_points import format_points

        points = [(1e-7, 2e-8, 3e-9)]
        result = format_points(points)

        # Should use scientific notation for very small numbers
        assert 'e' in result.lower()


class TestEnhancedPointsFormatterInit:
    """Test EnhancedPointsFormatter initialization."""

    @patch('aortacfd_lib.utils.format_points.Logger')
    def test_init_default_values(self, mock_logger):
        """Test initialization with default values."""
        from aortacfd_lib.utils.format_points import EnhancedPointsFormatter

        formatter = EnhancedPointsFormatter()

        assert formatter.format_version == 2

    @patch('aortacfd_lib.utils.format_points.Logger')
    def test_init_custom_values(self, mock_logger):
        """Test initialization with custom values."""
        from aortacfd_lib.utils.format_points import EnhancedPointsFormatter

        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = EnhancedPointsFormatter(
                input_filename="input.txt",
                output_filename="output.txt",
                format_version=1,
                case_directory=tmpdir
            )

            assert formatter.format_version == 1
            assert "input.txt" in formatter.input_filename


class TestEnhancedPointsFormatterFormatCoordinates:
    """Test EnhancedPointsFormatter.format_coordinates method."""

    @patch('aortacfd_lib.utils.format_points.Logger')
    def test_format_coordinates_v2(self, mock_logger):
        """Test coordinate formatting with version 2."""
        from aortacfd_lib.utils.format_points import EnhancedPointsFormatter

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create input file
            input_file = os.path.join(tmpdir, "points-new")
            with open(input_file, 'w') as f:
                f.write("0 1.0 2.0 3.0\n")
                f.write("1 4.0 5.0 6.0\n")
                f.write("2 7.0 8.0 9.0\n")

            formatter = EnhancedPointsFormatter(
                input_filename="points-new",
                output_filename="points",
                format_version=2,
                case_directory=tmpdir
            )

            formatter.format_coordinates()

            # Check output file
            output_file = os.path.join(tmpdir, "points")
            assert os.path.exists(output_file)

            with open(output_file, 'r') as f:
                content = f.read()

            # Version 2 should have parentheses
            assert '(' in content
            assert ')' in content
            assert '3\n' in content  # 3 points

    @patch('aortacfd_lib.utils.format_points.Logger')
    def test_format_coordinates_v1(self, mock_logger):
        """Test coordinate formatting with version 1."""
        from aortacfd_lib.utils.format_points import EnhancedPointsFormatter

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create input file
            input_file = os.path.join(tmpdir, "points-new")
            with open(input_file, 'w') as f:
                f.write("0 1.0 2.0 3.0\n")
                f.write("1 4.0 5.0 6.0\n")

            formatter = EnhancedPointsFormatter(
                input_filename="points-new",
                output_filename="points",
                format_version=1,
                case_directory=tmpdir
            )

            formatter.format_coordinates()

            # Check output file
            output_file = os.path.join(tmpdir, "points")
            with open(output_file, 'r') as f:
                content = f.read()

            # Version 1 doesn't have outer parentheses
            # But coordinates still have inner parentheses based on _process_lines
            assert '2\n' in content  # 2 points

    @patch('aortacfd_lib.utils.format_points.Logger')
    def test_format_coordinates_missing_input(self, mock_logger):
        """Test error handling for missing input file."""
        from aortacfd_lib.utils.format_points import EnhancedPointsFormatter

        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = EnhancedPointsFormatter(
                input_filename="nonexistent.txt",
                output_filename="output.txt",
                case_directory=tmpdir
            )

            with pytest.raises(SystemExit):
                formatter.format_coordinates()


class TestEnhancedPointsFormatterProcessLines:
    """Test EnhancedPointsFormatter._process_lines method."""

    @patch('aortacfd_lib.utils.format_points.Logger')
    def test_process_valid_lines(self, mock_logger):
        """Test processing valid input lines."""
        from aortacfd_lib.utils.format_points import EnhancedPointsFormatter

        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = EnhancedPointsFormatter(case_directory=tmpdir)

            lines = [
                "0 1.0 2.0 3.0\n",
                "1 4.0 5.0 6.0\n",
            ]

            result = formatter._process_lines(lines)

            assert len(result) == 2
            assert "(1.0 2.0 3.0)" in result[0]
            assert "(4.0 5.0 6.0)" in result[1]

    @patch('aortacfd_lib.utils.format_points.Logger')
    def test_process_lines_skips_invalid(self, mock_logger):
        """Test that invalid lines are skipped."""
        from aortacfd_lib.utils.format_points import EnhancedPointsFormatter

        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = EnhancedPointsFormatter(case_directory=tmpdir)

            lines = [
                "0 1.0 2.0 3.0\n",  # Valid
                "1 2.0 3.0\n",  # Invalid (only 3 values)
                "2 4.0 5.0 6.0\n",  # Valid
            ]

            result = formatter._process_lines(lines)

            # Should only have 2 valid entries
            assert len(result) == 2

    @patch('aortacfd_lib.utils.format_points.Logger')
    def test_process_empty_lines(self, mock_logger):
        """Test processing empty line list."""
        from aortacfd_lib.utils.format_points import EnhancedPointsFormatter

        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = EnhancedPointsFormatter(case_directory=tmpdir)

            result = formatter._process_lines([])

            assert result == []

    @patch('aortacfd_lib.utils.format_points.Logger')
    def test_process_lines_with_whitespace(self, mock_logger):
        """Test processing lines with extra whitespace."""
        from aortacfd_lib.utils.format_points import EnhancedPointsFormatter

        with tempfile.TemporaryDirectory() as tmpdir:
            formatter = EnhancedPointsFormatter(case_directory=tmpdir)

            lines = [
                "  0   1.0   2.0   3.0  \n",
            ]

            result = formatter._process_lines(lines)

            assert len(result) == 1
            assert "(1.0 2.0 3.0)" in result[0]


class TestFormatPointsEdgeCases:
    """Test edge cases for format_points function."""

    def test_negative_coordinates(self):
        """Test formatting negative coordinates."""
        from aortacfd_lib.utils.format_points import format_points

        points = [(-1.0, -2.0, -3.0)]
        result = format_points(points)

        assert "-1.0" in result
        assert "-2.0" in result
        assert "-3.0" in result

    def test_mixed_positive_negative(self):
        """Test formatting mixed positive and negative values."""
        from aortacfd_lib.utils.format_points import format_points

        points = [(1.0, -2.0, 3.0)]
        result = format_points(points)

        assert "1.0" in result
        assert "-2.0" in result
        assert "3.0" in result

    def test_large_numbers(self):
        """Test formatting large numbers."""
        from aortacfd_lib.utils.format_points import format_points

        points = [(1000000.0, 2000000.0, 3000000.0)]
        result = format_points(points)

        assert result != ""

    def test_list_of_lists(self):
        """Test formatting list of lists."""
        from aortacfd_lib.utils.format_points import format_points

        points = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        result = format_points(points)

        lines = result.strip().split('\n')
        assert len(lines) == 2


class TestFormatterIntegration:
    """Integration tests for the formatter."""

    @patch('aortacfd_lib.utils.format_points.Logger')
    def test_full_workflow(self, mock_logger):
        """Test complete format workflow."""
        from aortacfd_lib.utils.format_points import EnhancedPointsFormatter

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create realistic input file
            input_content = """0 0.001 0.002 0.003
1 0.004 0.005 0.006
2 0.007 0.008 0.009
3 0.010 0.011 0.012
"""
            input_file = os.path.join(tmpdir, "points-new")
            with open(input_file, 'w') as f:
                f.write(input_content)

            formatter = EnhancedPointsFormatter(
                input_filename="points-new",
                output_filename="points",
                format_version=2,
                case_directory=tmpdir
            )

            formatter.format_coordinates()

            # Verify output
            output_file = os.path.join(tmpdir, "points")
            assert os.path.exists(output_file)

            with open(output_file, 'r') as f:
                output_content = f.read()

            # Check format
            assert output_content.startswith('4')  # 4 points
            assert '(' in output_content
            assert ')' in output_content


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
