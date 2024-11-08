class EnhancedPointsFormatter:
	def __init__(self, input_filename="points-new", output_filename="points", format_version=2):
		self.input_filename = input_filename
		self.output_filename = output_filename
		self.format_version = format_version

	def format_coordinates(self):
		with open(self.input_filename, "r") as file:
			lines = file.readlines()

		formatted_coordinates = self._process_lines(lines)

		with open(self.output_filename, "w") as output_file:
			output_file.write(f"{len(formatted_coordinates)}\n")
			if self.format_version == 2:
				output_file.write("(\n")
			for coordinate in formatted_coordinates:
				output_file.write(coordinate + "\n")
			if self.format_version == 2:
				output_file.write(")\n")

		print(f"Output saved to '{self.output_filename}' file.")

	def _process_lines(self, lines):
		formatted_coordinates = []
		for line in lines:
			values = line.strip().split()
			if len(values) >= 3:
				x, y, z = values[1], values[2], values[3]
				formatted_coordinates.append(f"({x} {y} {z})")
		return formatted_coordinates

# usage in the terminal
# python formatPoints.py points-new

if __name__ == "__main__":
	import sys
	if len(sys.argv) < 2:
		print("Usage: python formatPoints.py <input_filename>")
		sys.exit(1)
	input_filename = sys.argv[1]
	output_filename = "points"
	formatter = EnhancedPointsFormatter(input_filename=input_filename, output_filename=output_filename)
	formatter.format_coordinates()

	
