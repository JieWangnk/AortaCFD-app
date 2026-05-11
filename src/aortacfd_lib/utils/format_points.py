import os
import sys
from .logger import Logger


class EnhancedPointsFormatter:
    def __init__(
        self,
        input_filename="points-new",
        output_filename="points",
        format_version=2,
        log_file="formatPoints.log",
        case_directory=".",
    ):
        """
        A class to format points from an input file into a specific format for OpenFOAM.

        Format Versions:
        ----------------
        - **Version 1**: Outputs coordinates without parentheses.
            Example:
            ```
            3
            0.1 0.2 0.3
            0.4 0.5 0.6
            0.7 0.8 0.9
            ```

        - **Version 2**: Outputs coordinates enclosed in parentheses and includes opening/closing parentheses in the file.
            Example:
            ```
            3
            (
            (0.1 0.2 0.3)
            (0.4 0.5 0.6)
            (0.7 0.8 0.9)
            )
            ```
        """
        self.input_filename = os.path.join(case_directory, input_filename)
        self.output_filename = os.path.join(case_directory, output_filename)
        self.format_version = format_version
        self.logger = Logger(log_file).get_logger()

    def format_coordinates(self):
        """
        Reads the input file, formats the coordinates, and writes them to the output file.
        """

        # Check if the input file exists
        if not os.path.exists(self.input_filename):
            self.logger.error(f"Input file '{self.input_filename}' not found.")
            sys.exit(1)

        try:
            with open(self.input_filename, "r") as file:
                lines = file.readlines()
        except Exception as e:
            self.logger.error(f"Error reading input file '{self.input_filename}': {e}")
            sys.exit(1)

        # Process and format the lines
        formatted_coordinates = self._process_lines(lines)

        # Write the formatted coordinates to the output file
        try:
            with open(self.output_filename, "w") as output_file:
                output_file.write(f"{len(formatted_coordinates)}\n")
                if self.format_version == 2:
                    output_file.write("(\n")  # Format version 2 includes parentheses
                for coordinate in formatted_coordinates:
                    output_file.write(coordinate + "\n")
                if self.format_version == 2:
                    output_file.write(")\n")
        except Exception as e:
            self.logger.error(f"Error writing to output file '{self.output_filename}': {e}")
            sys.exit(1)

    def _process_lines(self, lines):
        """
        Processes the lines from the input file and formats them into coordinates.
        """
        formatted_coordinates = []
        for line in lines:
            values = line.strip().split()
            if len(values) >= 4:  # Ensure there are at least 4 values
                try:
                    x, y, z = values[1], values[2], values[3]
                    formatted_coordinates.append(f"({x} {y} {z})")
                except Exception as e:
                    self.logger.warning(f"Error processing line '{line.strip()}': {e}")
            else:
                self.logger.warning(f"Skipping invalid line (not enough values): {line.strip()}")
        return formatted_coordinates


# Usage in the terminal
# python formatPoints.py points-new


def format_points(points, precision=1):
    """
    Simple utility function to format a list of 3D points for testing.

    Args:
        points: List of tuples (x, y, z)
        precision: Number of decimal places (default=1)

    Returns:
        Formatted string representation of points
    """
    if not points:
        return ""

    formatted_lines = []
    for point in points:
        if len(point) != 3:
            raise ValueError("Each point must have exactly 3 coordinates")

        x, y, z = point
        # Format each coordinate based on its value
        formatted_coords = []
        for val in (x, y, z):
            if abs(val) == 0:
                formatted_coords.append("0.0")
            elif abs(val) < 1e-5:
                # Use scientific notation for very small non-zero numbers
                formatted_coords.append(f"{val:.1e}")
            elif abs(val) < 1e-3:
                # Use fixed-point notation with more precision for small numbers
                formatted_coords.append(f"{val:.6f}")
            else:
                # Use fixed-point notation for regular numbers
                formatted_coords.append(f"{val:.{precision}f}")

        formatted_lines.append(" ".join(formatted_coords))

    return "\n".join(formatted_lines)
