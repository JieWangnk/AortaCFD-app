#!/usr/bin/env python3
"""
Convert OpenFOAM cellLevel (labelList) to volScalarField for ParaView visualization.

Usage:
    python convert_cellLevel_to_volScalarField.py <case_dir>

Example:
    python convert_cellLevel_to_volScalarField.py output/BPM120/gci_mesh_study/mesh2_medium/openfoam
"""

import sys
import struct
from pathlib import Path


def read_binary_label_list(filepath):
    """Read OpenFOAM binary labelList file."""
    with open(filepath, 'rb') as f:
        content = f.read()

    # Find the size (number after the header, before the '(')
    text_part = content.decode('latin-1', errors='replace')

    # Find where binary data starts (after the '(' character)
    paren_pos = content.find(b'(')
    if paren_pos == -1:
        raise ValueError("Could not find '(' in labelList file")

    # Extract size from text before '('
    header_text = text_part[:paren_pos]
    lines = header_text.strip().split('\n')
    size_line = [l.strip() for l in lines if l.strip().isdigit()]
    if not size_line:
        raise ValueError("Could not find size in labelList header")

    n_cells = int(size_line[-1])
    print(f"  Number of cells: {n_cells}")

    # Read binary integers (4 bytes each, little-endian)
    binary_start = paren_pos + 1
    labels = []

    for i in range(n_cells):
        offset = binary_start + i * 4
        value = struct.unpack('<i', content[offset:offset+4])[0]
        labels.append(value)

    return labels


def get_boundary_patches(case_dir):
    """Read boundary file to get patch names."""
    boundary_file = case_dir / 'constant' / 'polyMesh' / 'boundary'

    patches = []
    with open(boundary_file, 'r') as f:
        content = f.read()

    # Look for pattern: patch_name followed by { on next line, after the main boundary block starts
    import re
    # Find content after the main '(' that starts the boundary list
    match = re.search(r'boundary\s*\n\s*\d+\s*\n\s*\(', content)
    if match:
        boundary_content = content[match.end():]
        # Find patch names: word at start of line followed by newline and {
        patch_pattern = re.compile(r'^\s*(\w+)\s*$\s*\{', re.MULTILINE)
        patches = patch_pattern.findall(boundary_content)

    # Fallback: just look for common patch names
    if not patches:
        common_patches = ['wall_aorta', 'inlet', 'outlet1', 'outlet2', 'outlet3', 'outlet4']
        patches = [p for p in common_patches if p in content]

    return patches


def write_vol_scalar_field(filepath, cell_levels, patches):
    """Write cellLevel as volScalarField in ASCII format."""

    n_cells = len(cell_levels)

    header = f'''/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  12
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       volScalarField;
    location    "0";
    object      cellLevel;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 0 0 0 0 0 0];

internalField   nonuniform List<scalar>
{n_cells}
(
'''

    # Write internal field values
    values = '\n'.join(str(v) for v in cell_levels)

    boundary = '''
);

boundaryField
{
'''

    # Add each patch
    for patch in patches:
        boundary += f'''    {patch}
    {{
        type            calculated;
        value           uniform 0;
    }}
'''

    boundary += '''}

// ************************************************************************* //
'''

    with open(filepath, 'w') as f:
        f.write(header)
        f.write(values)
        f.write(boundary)

    print(f"  Written: {filepath}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    case_dir = Path(sys.argv[1])

    if not case_dir.exists():
        print(f"Error: Directory not found: {case_dir}")
        sys.exit(1)

    cellLevel_file = case_dir / 'constant' / 'polyMesh' / 'cellLevel'
    if not cellLevel_file.exists():
        print(f"Error: cellLevel file not found: {cellLevel_file}")
        sys.exit(1)

    print(f"Converting cellLevel for case: {case_dir}")

    # Read binary cellLevel
    print("Reading binary cellLevel...")
    cell_levels = read_binary_label_list(cellLevel_file)

    # Get boundary patches
    print("Reading boundary patches...")
    patches = get_boundary_patches(case_dir)
    print(f"  Found patches: {patches}")

    # Write as volScalarField to 0 directory
    output_file = case_dir / '0' / 'cellLevel'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("Writing volScalarField...")
    write_vol_scalar_field(output_file, cell_levels, patches)

    # Print stats
    min_level = min(cell_levels)
    max_level = max(cell_levels)
    print(f"\nDone! cellLevel range: {min_level} to {max_level}")
    print(f"\nIn ParaView:")
    print(f"  1. Open case: {case_dir}")
    print(f"  2. Select 'cellLevel' field")
    print(f"  3. Color by cellLevel with discrete colormap")


if __name__ == '__main__':
    main()
