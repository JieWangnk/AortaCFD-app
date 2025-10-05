"""
OpenFOAM Binary Field Reader

Lightweight parser for OpenFOAM binary field files (no external dependencies).
Supports scalar and vector fields in binary format.

Based on OpenFOAM binary format specification:
- Header: ASCII FoamFile dictionary
- Data: Binary array after "internalField"

Usage:
    from openfoam_binary_reader import read_field

    # Read velocity field
    data = read_field("0.1/U")
    print(f"Min: {data['min']}, Max: {data['max']}, Mean: {data['mean']}")
"""

import struct
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import numpy as np


class OpenFOAMBinaryReader:
    """Read OpenFOAM binary field files"""

    def __init__(self, field_path: Path):
        self.field_path = Path(field_path)
        self.header = {}
        self.field_class = None
        self.field_type = None
        self.dimensions = None

    def read(self) -> Optional[Dict]:
        """
        Read binary field file and return statistics.

        Returns:
            Dict with 'min', 'max', 'mean', 'data_type', 'size'
        """
        if not self.field_path.exists():
            return None

        try:
            with open(self.field_path, 'rb') as f:
                content = f.read()

            # Parse header (ASCII part)
            header_end = self._find_header_end(content)
            if header_end < 0:
                return None

            header = content[:header_end].decode('ascii', errors='ignore')
            self._parse_header(header)

            # Check if binary format
            if 'binary' not in header.lower():
                # Try ASCII parsing as fallback
                return self._parse_ascii_field(header)

            # Find internalField section
            internal_field_start = self._find_internal_field(content, header_end)
            if internal_field_start < 0:
                return None

            # Read binary data
            data = self._read_binary_data(content, internal_field_start)

            if data is not None:
                return self._compute_statistics(data)

        except Exception as e:
            print(f"    ⚠️  Binary read error for {self.field_path.name}: {e}")

        return None

    def _find_header_end(self, content: bytes) -> int:
        """Find end of ASCII header"""
        # Look for end of FoamFile dictionary
        header_str = content[:10000].decode('ascii', errors='ignore')

        # Find closing of FoamFile block
        matches = list(re.finditer(r'\}', header_str))
        if matches:
            # First closing brace after FoamFile
            return matches[0].end()

        return -1

    def _parse_header(self, header: str):
        """Extract field metadata from header"""
        # Get field class
        if match := re.search(r'class\s+(\w+);', header):
            self.field_class = match.group(1)

        # Determine field type from class
        if 'Vector' in self.field_class:
            self.field_type = 'vector'
        elif 'Scalar' in self.field_class:
            self.field_type = 'scalar'
        else:
            self.field_type = 'unknown'

        # Get dimensions
        if match := re.search(r'dimensions\s+\[([\d\s-]+)\];', header):
            dims = match.group(1).strip().split()
            self.dimensions = [int(d) for d in dims]

    def _find_internal_field(self, content: bytes, start_pos: int) -> int:
        """Find start of internalField binary data"""
        # Look for "internalField" keyword
        internal_field = b'internalField'
        pos = content.find(internal_field, start_pos)

        if pos < 0:
            return -1

        # Skip past keyword and whitespace to find data start
        pos += len(internal_field)

        # Look for size indicator (number before opening parenthesis)
        # Format: "internalField   nonuniform List<vector> \n12345\n("
        section = content[pos:pos+200].decode('ascii', errors='ignore')

        # Find the number indicating list size
        if match := re.search(r'(\d+)\s*\(', section):
            size_pos = pos + match.start()
            data_start = pos + match.end()
            return data_start

        return -1

    def _read_binary_data(self, content: bytes, start_pos: int) -> Optional[np.ndarray]:
        """Read binary field data"""
        try:
            # Find size from just before start_pos
            section = content[start_pos-100:start_pos].decode('ascii', errors='ignore')
            if match := re.search(r'(\d+)\s*\($', section):
                size = int(match.group(1))
            else:
                return None

            # Binary data starts after '('
            data_pos = start_pos

            if self.field_type == 'vector':
                # Each vector: 3 doubles (24 bytes)
                num_bytes = size * 3 * 8
                data_bytes = content[data_pos:data_pos + num_bytes]

                # Unpack as doubles
                fmt = f'{size * 3}d'
                values = struct.unpack(fmt, data_bytes)

                # Reshape to vectors
                data = np.array(values).reshape(size, 3)

                # Compute magnitude
                return np.linalg.norm(data, axis=1)

            elif self.field_type == 'scalar':
                # Each scalar: 1 double (8 bytes)
                num_bytes = size * 8
                data_bytes = content[data_pos:data_pos + num_bytes]

                # Unpack as doubles
                fmt = f'{size}d'
                values = struct.unpack(fmt, data_bytes)

                return np.array(values)

        except Exception as e:
            print(f"    ⚠️  Binary unpack error: {e}")

        return None

    def _parse_ascii_field(self, content: str) -> Optional[Dict]:
        """Fallback: parse ASCII format field"""
        try:
            # Look for internalField with uniform value
            if match := re.search(r'internalField\s+uniform\s+\(([^)]+)\)', content):
                values_str = match.group(1).strip()
                values = [float(x) for x in values_str.split()]

                if len(values) == 3:  # Vector
                    mag = np.linalg.norm(values)
                    return {
                        'min': mag,
                        'max': mag,
                        'mean': mag,
                        'data_type': 'vector_uniform',
                        'size': 1
                    }
                else:  # Scalar
                    val = values[0]
                    return {
                        'min': val,
                        'max': val,
                        'mean': val,
                        'data_type': 'scalar_uniform',
                        'size': 1
                    }

            # Look for nonuniform List
            if 'nonuniform' in content:
                # This would need more complex parsing
                # For now, return None to trigger other methods
                pass

        except Exception as e:
            print(f"    ⚠️  ASCII parse error: {e}")

        return None

    def _compute_statistics(self, data: np.ndarray) -> Dict:
        """Compute min/max/mean statistics"""
        return {
            'min': float(np.min(data)),
            'max': float(np.max(data)),
            'mean': float(np.mean(data)),
            'std': float(np.std(data)),
            'data_type': self.field_type,
            'size': len(data)
        }


def read_field(field_path: Path) -> Optional[Dict]:
    """
    Convenience function to read a field file.

    Args:
        field_path: Path to OpenFOAM field file (e.g., "0.1/U")

    Returns:
        Dict with statistics or None if failed
    """
    reader = OpenFOAMBinaryReader(field_path)
    return reader.read()


def read_field_at_time(case_dir: Path, field_name: str, time: float) -> Optional[Dict]:
    """
    Read field at specific time.

    Args:
        case_dir: Case directory
        field_name: Field name (U, p, etc.)
        time: Time value

    Returns:
        Dict with statistics or None if failed
    """
    # Find closest time directory
    time_dirs = []
    for item in case_dir.iterdir():
        if item.is_dir() and item.name.replace('.', '', 1).replace('-', '', 1).isdigit():
            try:
                t = float(item.name)
                time_dirs.append((t, item))
            except ValueError:
                continue

    if not time_dirs:
        return None

    # Find closest
    time_dirs.sort(key=lambda x: abs(x[0] - time))
    time_dir = time_dirs[0][1]

    field_path = time_dir / field_name
    if not field_path.exists():
        return None

    return read_field(field_path)


# Example usage
if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python openfoam_binary_reader.py <field_file>")
        print("Example: python openfoam_binary_reader.py 0.1/U")
        sys.exit(1)

    field_path = Path(sys.argv[1])

    print(f"Reading: {field_path}")
    stats = read_field(field_path)

    if stats:
        print(f"\nField Statistics:")
        print(f"  Type:  {stats['data_type']}")
        print(f"  Size:  {stats['size']}")
        print(f"  Min:   {stats['min']:.6e}")
        print(f"  Max:   {stats['max']:.6e}")
        print(f"  Mean:  {stats['mean']:.6e}")
        print(f"  Std:   {stats['std']:.6e}")
    else:
        print("Failed to read field")
