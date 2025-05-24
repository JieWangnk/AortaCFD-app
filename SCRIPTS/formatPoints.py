import os
import sys
from SCRIPTS.logger import Logger

class EnhancedPointsFormatter:
    def __init__(self, input_filename="points-new", output_filename="points", format_version=2, log_file="formatPoints.log", case_directory="."):
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
            if len(values) >= 3:
                try:
                    x, y, z = values[1], values[2], values[3]
                    formatted_coordinates.append(f"({x} {y} {z})")
                except IndexError:
                    self.logger.warning(f"Skipping malformed line: {line.strip()}")
            else:
                self.logger.warning(f"Skipping invalid line (not enough values): {line.strip()}")
        return formatted_coordinates

# Usage in the terminal
# python formatPoints.py points-new

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python formatPoints.py <input_filename> [case_directory]")
        sys.exit(1)

    input_filename = sys.argv[1]
    case_directory = sys.argv[2] if len(sys.argv) > 2 else "."
    output_filename = "points"

    # Initialize the formatter
    formatter = EnhancedPointsFormatter(
        input_filename=input_filename,
        output_filename=output_filename,
        format_version=2,  # Default to format version 2
        case_directory=case_directory
    )

    # Format the coordinates
    formatter.format_coordinates()


