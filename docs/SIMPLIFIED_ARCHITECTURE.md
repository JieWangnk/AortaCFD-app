# Simplified Architecture Guide

This document describes the simplified architecture introduced in the `refactor/simplified-architecture` branch.

## Goals

The simplified architecture aims to:

1. **Make code easier to trace** - Clear data flow, no hidden state
2. **Reduce complexity** - Functions instead of classes where appropriate
3. **Single source of truth** - Centralized registries for settings
4. **Better organization** - Split large files into focused modules

## New Module Structure

```
src/
├── config/
│   ├── accessor.py         # Config helper class (NEW)
│   ├── generator.py        # Config template generator (NEW)
│   ├── builder.py          # Original config builder
│   └── ...
│
├── registry/               # Centralized settings (NEW)
│   ├── __init__.py
│   ├── numerics.py         # Numerical schemes, solver settings
│   ├── physics.py          # Blood properties, constants
│   └── mesh.py             # Mesh quality thresholds
│
├── writers/                # Simple file writers (NEW)
│   ├── __init__.py
│   ├── fv_schemes.py
│   ├── fv_solution.py
│   ├── control_dict.py
│   ├── transport_properties.py
│   └── decompose_par_dict.py
│
├── inlet/                  # Split from inlet_mapping.py (NEW)
│   ├── __init__.py
│   ├── profiles.py         # Velocity profiles
│   ├── csv_reader.py       # CSV parsing
│   └── mapping.py          # Point mapping
│
├── windkessel/             # Split from wk_setup.py (NEW)
│   ├── __init__.py
│   ├── circuit.py          # Circuit calculations
│   ├── murray.py           # Murray's law
│   └── writer.py           # File generation
│
├── workflow/
│   ├── steps.py            # Functions, not classes (NEW)
│   ├── simple_runner.py    # Simplified workflow (NEW)
│   └── ...
│
└── aortacfd_lib/           # Original modules (unchanged)
```

## Key Improvements

### 1. Config Accessor (`src/config/accessor.py`)

**Before:**
```python
# Repeated everywhere, hard to trace
inlet = self.config.get('boundary_conditions', {}).get('inlet') or self.config.get('inlet', {})
```

**After:**
```python
from src.config.accessor import Config

cfg = Config(raw_config)
inlet = cfg.inlet  # Handles both nested and flat
profile = cfg.profile
is_windkessel = cfg.is_windkessel
```

### 2. Registry (`src/registry/`)

**Before:** Settings scattered across multiple files
- `config/base.py`
- `config/profiles/numerics/*.py`
- `aortacfd_lib/template_context.py`

**After:** Single source of truth
```python
from src.registry import get_numerics, get_schemes, BLOOD_PROPERTIES

# Get all numerical settings for a profile
settings = get_numerics('standard')

# Get just the schemes
schemes = get_schemes('standard')
print(schemes['ddt'])  # 'backward'
print(schemes['div_phi_U'])  # 'Gauss limitedLinearV 1'

# Blood properties
nu = BLOOD_PROPERTIES['kinematic_viscosity']
```

### 3. Simple Writers (`src/writers/`)

**Before:** Classes with complex inheritance
```python
writer = FvSchemesWriter(config=self.config, case_directory=case_dir)
writer.write_fvSchemes_file()
```

**After:** Simple functions
```python
from src.writers import write_fv_schemes

write_fv_schemes(config, case_dir)
```

### 4. Workflow Steps (`src/workflow/steps.py`)

**Before:** Task classes
```python
class GenerateNumericalSchemesTask(Task):
    def execute(self, context: dict) -> bool:
        writer = FvSchemesWriter(...)
        writer.write_fvSchemes_file()
        return True
```

**After:** Simple functions
```python
def generate_fv_schemes_step(config, case_dir):
    write_fv_schemes(config, case_dir)
    return True
```

### 5. Split Large Modules

**inlet_mapping.py (45KB)** → `src/inlet/`
- `profiles.py` - Velocity profile calculations
- `csv_reader.py` - CSV file parsing
- `mapping.py` - Point mapping logic

**wk_setup.py (50KB)** → `src/windkessel/`
- `circuit.py` - Windkessel circuit calculations
- `murray.py` - Murray's law flow splitting
- `writer.py` - File I/O

## Usage Examples

### Quick Start
```python
from src.workflow.simple_runner import run_setup

# Run with config file
case_dir = run_setup('cases_input/PAT001/config.json')

# Or run with just a profile (uses defaults)
from src.workflow.simple_runner import run_with_profile
case_dir = run_with_profile('PAT001', profile='standard')
```

### Generate Config Template
```python
from src.config.generator import generate_config, save_config_template

# Generate a complete config for standard profile
config = generate_config('standard', case_name='MY_CASE')

# Save as template
save_config_template('standard', 'cases_input/NEW_CASE/config.json')
```

### Access Config Values
```python
from src.config.accessor import Config

cfg = Config(raw_config)

# Geometry
print(cfg.case_name)
print(cfg.scale_factor)
print(cfg.inlet_patch_name)

# Physics
print(cfg.simulation_type)  # 'laminar', 'rans', 'les'
print(cfg.nu)  # Kinematic viscosity
print(cfg.rho)  # Density

# Boundary conditions
print(cfg.inlet_type)  # 'CONSTANT', 'TIMEVARYING', etc.
print(cfg.outlet_type)  # 'zeroGradient', '3EWINDKESSEL', etc.
print(cfg.is_windkessel)  # True/False
```

### Use Registry Directly
```python
from src.registry import (
    get_numerics,
    get_schemes,
    BLOOD_PROPERTIES,
    MESH_QUALITY_TIERS,
)

# Numerical settings
numerics = get_numerics('standard')
print(numerics['schemes']['ddt'])  # 'backward'
print(numerics['pimple']['nOuterCorrectors'])  # 30

# Physics
print(BLOOD_PROPERTIES['density'])  # 1060.0

# Mesh quality
print(MESH_QUALITY_TIERS['good']['maxSkewness'])  # 0.7
```

### Velocity Profiles
```python
from src.inlet import create_profile, ParabolicProfile
import numpy as np

center = np.array([0, 0, 0])
radius = 0.01
normal = np.array([1, 0, 0])

profile = create_profile('parabolic', center, radius, normal)

# Calculate velocity at a point
point = np.array([0, 0.005, 0])
mean_velocity = 0.5  # m/s
velocity = profile.calculate(point, mean_velocity)
```

### Windkessel Calculations
```python
from src.windkessel import calculate_3element_params, write_windkessel_properties

# Calculate parameters for one outlet
params = calculate_3element_params(
    mean_pressure=13332.2,  # 100 mmHg in Pa
    mean_flow=2e-5,         # m³/s
    cardiac_cycle=0.8,
    outlet_name='outlet1',
)

print(f"R1: {params.R1:.3e}")
print(f"R2: {params.R2:.3e}")
print(f"C:  {params.C:.3e}")
print(f"tau: {params.tau:.3f}s")
```

## Migration Guide

### For Physics/Numerical Changes

1. **Find the setting in the registry:**
   ```python
   # src/registry/numerics.py
   SCHEMES = {
       'standard': {
           'ddt': 'backward',
           'div_phi_U': 'Gauss limitedLinearV 1',
           ...
       }
   }
   ```

2. **Modify in one place** - Changes automatically apply everywhere

3. **Add new profiles** by adding to the registry dictionaries

### For Adding New Features

1. **Create focused module** in appropriate package
2. **Export from package `__init__.py`**
3. **Add to workflow steps** as a function
4. **Update simple_runner** if needed

## Comparison: Old vs New

| Aspect | Old Architecture | New Architecture |
|--------|------------------|------------------|
| Config access | `config.get('a', {}).get('b')` | `cfg.property_name` |
| Numerical settings | Scattered in 3+ files | `src/registry/numerics.py` |
| File writers | Classes with inheritance | Simple functions |
| Workflow tasks | Task classes | Step functions |
| inlet_mapping.py | 45KB monolithic | 3 focused modules |
| wk_setup.py | 50KB monolithic | 3 focused modules |

## Backward Compatibility

The new modules are **additive** - the original code in `src/aortacfd_lib/` is unchanged. You can:

1. Use new simplified modules for new features
2. Gradually migrate existing code
3. Keep using original modules where needed

## Files Created

```
src/config/accessor.py          - Config accessor class
src/config/generator.py         - Config template generator
src/registry/__init__.py        - Registry package init
src/registry/numerics.py        - Numerical settings
src/registry/physics.py         - Physical constants
src/registry/mesh.py            - Mesh quality settings
src/writers/__init__.py         - Writers package init
src/writers/header.py           - OpenFOAM header utility
src/writers/fv_schemes.py       - fvSchemes writer
src/writers/fv_solution.py      - fvSolution writer
src/writers/control_dict.py     - controlDict writer
src/writers/transport_properties.py - Transport properties writer
src/writers/decompose_par_dict.py - decomposeParDict writer
src/inlet/__init__.py           - Inlet package init
src/inlet/profiles.py           - Velocity profiles
src/inlet/csv_reader.py         - CSV parser
src/inlet/mapping.py            - Point mapping
src/windkessel/__init__.py      - Windkessel package init
src/windkessel/circuit.py       - Circuit calculations
src/windkessel/murray.py        - Murray's law
src/windkessel/writer.py        - Windkessel file writer
src/workflow/steps.py           - Workflow step functions
src/workflow/simple_runner.py   - Simplified workflow runner
docs/SIMPLIFIED_ARCHITECTURE.md - This documentation
```
