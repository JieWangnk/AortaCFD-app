with open("points-new", "r") as file:
    # Read the remaining lines from
    lines = file.readlines()

# Create an empty list to store the formatted coordinates
formatted_coordinates = []

# Process each line in the file
for line in lines:
    # Split the line into individual values
    values = line.strip().split()   
    
    # Check if the line has at least three values
    if len(values) >= 3:
        # Extract x, y, z coordinates from the values
        x = values[1]
        y = values[2]
        z = values[3]     
        # Append the formatted coordinates to the list
        formatted_coordinates.append(f"({x} {y} {z})")

# Write the output to a new file named "points"
with open("points", "w") as output_file:
    # Write the header
    output_file.write(str(len(lines)) + "\n")  

    # Write the formatted coordinates
    for coordinate in formatted_coordinates:
        output_file.write(coordinate + "\n")

print("Output saved to 'points' file.")
