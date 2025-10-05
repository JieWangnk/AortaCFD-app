# OpenFOAM Binary Field Reader

## Overview

Lightweight Python module to read OpenFOAM binary field files **without external dependencies** (no PyFOAM needed!).

**Features**:
- ✅ Read binary scalar and vector fields
- ✅ Extract min/max/mean statistics
- ✅ ~300 lines of pure Python
- ✅ No external dependencies (uses only `struct` and `numpy`)
- ✅ Fast (direct binary parsing)

## Installation

**No installation needed!** Uses only Python standard library + numpy (already in requirements.txt).

## Usage

### Quick Start

```python
from openfoam_binary_reader import read_field

# Read velocity field
stats = read_field("0.1/U")

print(f"Max velocity: {stats['max']:.3f} m/s")
print(f"Mean velocity: {stats['mean']:.3f} m/s")
```

### Read at Specific Time

```python
from openfoam_binary_reader import read_field_at_time
from pathlib import Path

# Read velocity at t=0.1s
case_dir = Path("validation/output/patient1/sim_laminar_medium")
stats = read_field_at_time(case_dir, "U", 0.1)

if stats:
    print(f"Velocity statistics at t=0.1s:")
    print(f"  Min:  {stats['min']:.6e} m/s")
    print(f"  Max:  {stats['max']:.6e} m/s")
    print(f"  Mean: {stats['mean']:.6e} m/s")
    print(f"  Std:  {stats['std']:.6e} m/s")
```

### Command Line

```bash
# Direct field reading
python validation/analyzers/openfoam_binary_reader.py 0.1/U

# Output:
# Reading: 0.1/U
# Field Statistics:
#   Type:  vector
#   Size:  42186
#   Min:   4.103519e-05
#   Max:   3.066036e-02
#   Mean:  1.360976e-03
#   Std:   1.131110e-03
```

## Supported Field Types

### Vector Fields
- **U** (velocity)
- **wallShearStress**
- Any `volVectorField`

**Returns**: Magnitude statistics (scalar)

### Scalar Fields
- **p** (pressure)
- **nut** (turbulent viscosity)
- **k** (turbulent kinetic energy)
- **omega** (specific dissipation rate)
- Any `volScalarField`

**Returns**: Direct statistics

## How It Works

### OpenFOAM Binary Format

OpenFOAM binary files have two parts:

1. **ASCII Header** (FoamFile dictionary)
```
FoamFile
{
    format      binary;
    class       volVectorField;
    object      U;
}
dimensions      [0 1 -1 0 0 0 0];
internalField   nonuniform List<vector>
42186
(
```

2. **Binary Data** (after the opening parenthesis)
```
<binary double precision floats>
```

### Reading Algorithm

```python
1. Read entire file as bytes
2. Find end of ASCII header (first '}')
3. Parse header to get:
   - format: binary/ascii
   - class: volVectorField/volScalarField
   - field size (number before '(')
4. Locate binary data start (after '(')
5. Unpack binary data:
   - Vector: 3 doubles per cell (24 bytes)
   - Scalar: 1 double per cell (8 bytes)
6. Compute statistics (min/max/mean/std)
```

### Binary Data Structure

**Vector Field (U)**:
```
Cell 0: [Ux, Uy, Uz]  (3 x 8 bytes)
Cell 1: [Ux, Uy, Uz]  (3 x 8 bytes)
...
Cell N: [Ux, Uy, Uz]  (3 x 8 bytes)

Total: N x 3 x 8 bytes
```

**Scalar Field (p)**:
```
Cell 0: [p]  (1 x 8 bytes)
Cell 1: [p]  (1 x 8 bytes)
...
Cell N: [p]  (1 x 8 bytes)

Total: N x 8 bytes
```

## Integration with Validation

The binary reader is automatically used in `run_bc_validation.py`:

```python
from analyzers.openfoam_binary_reader import read_field_at_time

# In _parse_vector_field_stats():
stats = read_field_at_time(case_dir, "U", time_val)

# Returns:
{
    'min': 4.1e-05,
    'max': 0.0307,
    'mean': 0.00136,
    'std': 0.00113,
    'data_type': 'vector',
    'size': 42186
}
```

## Comparison with Alternatives

### vs PyFOAM
| Feature | Binary Reader | PyFOAM |
|---------|--------------|--------|
| **Size** | ~300 lines | ~50,000 lines |
| **Dependencies** | numpy only | Many |
| **Install** | Copy file | pip install PyFOAM |
| **Speed** | Fast | Slow |
| **Scope** | Field reading | Complete toolkit |

### vs OpenFOAM Utilities
| Feature | Binary Reader | postProcess |
|---------|--------------|-------------|
| **Language** | Python | C++ |
| **Requires OF** | No | Yes |
| **Integration** | Easy | Subprocess |
| **Speed** | Fast | Fastest |

## Validation Results

### Before Binary Reader
```
Max Velocity:            0.000 m/s  ✗
Pressure Drop:           0.0 Pa     ✗
```

### After Binary Reader
```
Max Velocity:            0.031 m/s  ✓
Mean Velocity:           0.001 m/s  ✓
Pressure Drop:           0.006 Pa   ✓
Reynolds Number:         10         ✓
```

## Example: Read Multiple Fields

```python
from pathlib import Path
from openfoam_binary_reader import read_field_at_time

case_dir = Path("validation/output/patient1/sim_laminar_medium")
time = 0.1

# Read all fields
fields = {
    'velocity': read_field_at_time(case_dir, "U", time),
    'pressure': read_field_at_time(case_dir, "p", time),
    'wss': read_field_at_time(case_dir, "wallShearStress", time)
}

# Print summary
for name, stats in fields.items():
    if stats:
        print(f"{name:12s}: max={stats['max']:.3e}, mean={stats['mean']:.3e}")
```

**Output**:
```
velocity    : max=3.066e-02, mean=1.361e-03
pressure    : max=4.203e-03, mean=6.342e-06
wss         : max=2.145e-01, mean=3.782e-02
```

## Troubleshooting

### "Failed to read field"
- Check file exists and is binary format
- Try with ASCII format (reader has fallback)
- Check OpenFOAM version compatibility

### "Unpack error"
- Field may be in different binary format
- Try re-running with `writeFormat ascii;` in controlDict
- Check field dimensions match expectations

### Wrong Statistics
- Verify field type (vector vs scalar)
- Check units and scale factors
- Compare with ParaView visualization

## Advanced Usage

### Custom Statistics
```python
from openfoam_binary_reader import OpenFOAMBinaryReader
import numpy as np

reader = OpenFOAMBinaryReader("0.1/U")
stats = reader.read()

if stats:
    # Access raw data if needed
    # (modify _compute_statistics to return data array)

    # Custom calculations
    percentile_95 = np.percentile(data, 95)
    print(f"95th percentile: {percentile_95:.3e}")
```

### Read Boundary Fields
```python
# Currently reads internalField only
# For boundaries, use OpenFOAM utilities:

import subprocess
result = subprocess.run(
    ["foamDictionary", "-entry", "boundaryField.inlet.value", "0.1/U"],
    capture_output=True, text=True
)
print(result.stdout)
```

## Future Enhancements

1. ✅ Read internalField (scalar/vector) - **DONE**
2. 🔄 Read boundaryField values
3. 🔄 Support tensor fields
4. 🔄 Read zone/patch-specific data
5. 🔄 Handle compressed binary format

## References

- OpenFOAM Binary Format: [OpenFOAM User Guide](https://www.openfoam.com/documentation/user-guide)
- Python struct module: [Python Docs](https://docs.python.org/3/library/struct.html)
- Alternative: [PyFOAM](https://github.com/ICE-QTM/PyFoam)

---

**Status**: ✅ Working
**Tested**: OpenFOAM 12 binary format
**Dependencies**: Python 3.8+, numpy
**License**: Same as AortaCFD project
