import sys
from SCRIPTS.logger import Logger

class EnhancedPointsFormatter:
    def __init__(self, input_filename="points-new", output_filename="points", format_version=2, log_file="formatPoints.log"):
        self.input_filename = input_filename
        self.output_filename = output_filename
        self.format_version = format_version
        self.logger = Logger(log_file).get_logger()

    def format_coordinates(self):
        
        try:
            with open(self.input_filename, "r") as file:
                lines = file.readlines()
                
        except FileNotFoundError:
            self.logger.error(f"Input file '{self.input_filename}' not found.")
            sys.exit(1)

        formatted_coordinates = self._process_lines(lines)

        with open(self.output_filename, "w") as output_file:
            output_file.write(f"{len(formatted_coordinates)}\n")
            if self.format_version == 2:
                output_file.write("(\n")
            for coordinate in formatted_coordinates:
                output_file.write(coordinate + "\n")
            if self.format_version == 2:
                output_file.write(")\n")


    def _process_lines(self, lines):
        formatted_coordinates = []
        for line in lines:
            values = line.strip().split()
            if len(values) >= 3:
                try:
                    x, y, z = values[1], values[2], values[3]
                    formatted_coordinates.append(f"({x} {y} {z})")
                except IndexError:
                    self.logger.warning(f"Skipping malformed line: {line.strip()}")
        return formatted_coordinates

# usage in the terminal
# python formatPoints.py points-new

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python formatPoints.py <input_filename>")
        sys.exit(1)
    input_filename = sys.argv[1]
    output_filename = "points"
    formatter = EnhancedPointsFormatter(input_filename=input_filename, output_filename=output_filename)
    formatter.format_coordinates()


