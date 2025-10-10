# Inlet Boundary Condition Configuration Guide

Complete mapping of how inlet BC is configured through JSON files in AortaCFD.

---

## Overview

Inlet boundary conditions are configured in the JSON file under `boundary_conditions.inlet` or just `inlet` (both supported).

**Code Flow:**
```
JSON config → ConfigBuilder → BoundaryConditionSetup → InletMapping → OpenFOAM 0/U file
```

---

## JSON Configuration Structure

### Location in JSON

```json
{
  "boundary_conditions": {
    "inlet": {
      // Inlet configuration here
    }
  }
}
```

**Or simplified:**
```json
{
  "inlet": {
    // Inlet configuration here
  }
}
```

---

## Inlet BC Types

There are 4 valid inlet types defined in [src/aortacfd_lib/utils/validation.py:749](src/aortacfd_lib/utils/validation.py#L749):
- `TIMEVARYING` - Time-varying BC from CSV file
- `CONSTANT` - Constant velocity BC
- `PARABOLIC` - Parabolic velocity profile
- `WOMERSLEY` - Womersley pulsatile profile

### 1. TIMEVARYING (Pulsatile Flow from CSV)

**Use case:** Cardiac cycle with time-varying velocity/flow rate

```json
{
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "test_cardio_profile.csv",
    "data_type": "velocity",
    "profile": "plug",
    "orientation": "out"
  }
}
```

**Parameters:**

| Parameter | Type | Required | Options | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | `"TIMEVARYING"` | Inlet type |
| `csv_file` | string | Yes | filename | CSV file in patient folder |
| `data_type` | string | Yes | `"velocity"` \| `"flowRate"` | Data interpretation |
| `profile` | string | Yes | `"plug"` \| `"parabolic"` \| `"womersley"` | Velocity profile shape |
| `orientation` | string | No | `"in"` \| `"out"` \| `"auto"` | Flow direction (default: `"auto"`) |

**CSV File Format:**
```csv
time,velocity
0.0,0.5
0.01,0.8
0.02,1.2
...
```

Or without header:
```csv
0.0,0.5
0.01,0.8
0.02,1.2
```

**CSV Location:**
- Must be in: `cases_input/{patient_name}/{csv_file}`
- Gets copied to: `{case_dir}/constant/boundaryData/{inlet_patch}/`

---

### 2. CONSTANT (Constant Uniform Velocity)

**Use case:** Simple steady-state flow or testing

```json
{
  "inlet": {
    "type": "CONSTANT",
    "velocity": 1.0,
    "profile": "plug",
    "orientation": "out"
  }
}
```

**Parameters:**

| Parameter | Type | Required | Options | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | `"CONSTANT"` | Inlet type (constant in time) |
| `velocity` | number | Yes | > 0 | Constant velocity magnitude (m/s) |
| `profile` | string | Yes | `"plug"` \| `"parabolic"` | Velocity profile shape |
| `orientation` | string | No | `"in"` \| `"out"` \| `"auto"` | Flow direction (default: `"auto"`) |

---

### 3. PARABOLIC (Poiseuille Flow)

**Use case:** Fully developed laminar flow

```json
{
  "inlet": {
    "type": "PARABOLIC",
    "velocity": 1.0,
    "profile": "parabolic",
    "orientation": "out"
  }
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | Yes | `"PARABOLIC"` |
| `velocity` | number | Yes | Centerline velocity (m/s) |
| `profile` | string | Yes | `"parabolic"` |
| `orientation` | string | No | Flow direction |

**Velocity Profile:**
```
v(r) = v_max * (1 - (r/R)²)
where v_max = 2 * v_avg
```

---

### 4. WOMERSLEY (Pulsatile with Frequency Effects)

**Use case:** High-frequency pulsatile flow with inertial effects

```json
{
  "inlet": {
    "type": "WOMERSLEY",
    "csv_file": "cardiac_flow.csv",
    "data_type": "velocity",
    "profile": "womersley",
    "orientation": "out"
  },
  "physics": {
    "nu": 3.77e-6
  }
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | Yes | `"WOMERSLEY"` |
| `csv_file` | string | Yes | Time-varying data |
| `data_type` | string | Yes | `"velocity"` or `"flowRate"` |
| `profile` | string | Yes | `"womersley"` |
| `nu` | number | Yes | Kinematic viscosity (m²/s) in `physics` section |

**Requires:**
- `physics.nu` (kinematic viscosity) for Womersley number calculation

**Womersley Profile:**
```
α = R * sqrt(ω / ν)  (Womersley number)
ω = 2π / T  (angular frequency)
v(r,t) = Re[v₀ * (1 - J₀(z)/J₀(z₀)) * e^(iωt)]
```

---

## Configuration Parameters Details

### `data_type`

How to interpret the CSV data:

**`"velocity"`:**
- CSV column 2 is velocity magnitude (m/s)
- Applied directly to profile

**`"flowRate"`:**
- CSV column 2 is volumetric flow rate (m³/s)
- Converted to velocity: `v = Q / A`
- Where A = π * R² (inlet area)

---

### `profile`

Spatial velocity distribution:

**`"plug"` (Uniform):**
```
v(r) = v₀  (constant everywhere)
```

**`"parabolic"` (Poiseuille):**
```
v(r) = v_centerline * (1 - (r/R)²)
v_centerline = 2 * v_avg
```

**`"womersley"` (Frequency-dependent):**
```
Complex Bessel function profile
Accounts for inertial effects at high frequency
```

---

### `orientation`

Flow direction relative to surface normal:

**`"out"`:**
- Flow in positive normal direction
- Normal points OUT of inlet surface
- Multiplier: +1.0

**`"in"`:**
- Flow in negative normal direction
- Normal points INTO inlet surface
- Multiplier: -1.0

**`"auto"` (Recommended):**
- Automatically detects correct direction
- Uses outlet positions to determine flow direction
- Calculates: inlet_center → average(outlet_centers)
- Flips normal if it points opposite to flow

**Auto-detection logic:**
```python
# Vector from inlet to outlets
flow_direction = avg_outlet_center - inlet_center

# Check alignment
dot_product = inlet_normal · flow_direction

if dot_product < 0:
    flip_normal = True  # Normal points outward
else:
    flip_normal = False  # Normal points inward
```

---

## Code Flow: JSON → OpenFOAM

### Step 1: JSON Configuration
**File:** `cases_input/patient1/config.json`
```json
{
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "flow.csv",
    "data_type": "velocity",
    "profile": "plug",
    "orientation": "auto"
  }
}
```

### Step 2: Config Builder
**File:** [src/config/builder.py](src/config/builder.py)
- Reads JSON
- Merges with defaults
- Validates configuration
- Detects inlet patch name from STL files

### Step 3: Inlet Mapping
**File:** [src/aortacfd_lib/inlet_mapping.py](src/aortacfd_lib/inlet_mapping.py)

**Key methods:**
- `run()` - Main orchestration
- `_read_csv_file()` - Load time-series data
- `_read_points_file()` - Load inlet mesh points
- `_determine_inward_direction()` - Auto-detect orientation
- `_generate_time_data()` - Apply profile and write time directories

**Process:**
1. Calculate inlet geometry (center, radius, normal)
2. Read CSV time-series data
3. Read inlet boundary points from mesh
4. Determine flow direction (auto or manual)
5. For each time step:
   - Apply velocity profile (plug/parabolic/womersley)
   - Calculate velocity vectors at each point
   - Write to `constant/boundaryData/{inlet}/{time}/U`

### Step 4: Boundary Condition Setup
**File:** [src/aortacfd_lib/boundary_condition_setup.py](src/aortacfd_lib/boundary_condition_setup.py)

- Renders Jinja2 template for `0/U`
- Sets inlet BC type based on configuration:
  - TIMEVARYING → `timeVaryingMappedFixedValue`
  - PLUG → `fixedValue uniform (vx vy vz)`
  - Others → appropriate OpenFOAM BC type

### Step 5: OpenFOAM Files Generated

**`0/U` file:**
```cpp
inlet
{
    type    timeVaryingMappedFixedValue;
    offset  (0 0 0);
    setAverage off;
}
```

**`constant/boundaryData/inlet/` structure:**
```
constant/boundaryData/inlet/
├── points             # Inlet mesh points
├── 0.000000/
│   └── U             # Velocity at t=0
├── 0.010000/
│   └── U             # Velocity at t=0.01
└── ...
```

---

## Examples

### Example 1: Cardiac Cycle (Realistic)

```json
{
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "aortic_flow_waveform.csv",
    "data_type": "velocity",
    "profile": "plug",
    "orientation": "auto"
  }
}
```

**CSV (aortic_flow_waveform.csv):**
```csv
time,velocity
0.0,0.2
0.1,0.5
0.15,1.2
0.2,0.8
0.4,0.3
0.6,0.2
0.8,0.2
```

### Example 2: Steady Flow Testing

```json
{
  "inlet": {
    "type": "PLUG",
    "velocity": 0.5,
    "profile": "plug",
    "orientation": "out"
  }
}
```

### Example 3: Developed Laminar Flow

```json
{
  "inlet": {
    "type": "PARABOLIC",
    "velocity": 1.0,
    "profile": "parabolic",
    "orientation": "auto"
  }
}
```

### Example 4: High-Frequency Pulsatile

```json
{
  "inlet": {
    "type": "WOMERSLEY",
    "csv_file": "high_freq_pulse.csv",
    "data_type": "flowRate",
    "profile": "womersley",
    "orientation": "auto"
  },
  "physics": {
    "nu": 3.77e-6,
    "rho": 1060
  }
}
```

---

## Validation & Debugging

### Check Inlet Configuration

```bash
# After case setup, check generated files
ls constant/boundaryData/inlet/

# Check points file
head constant/boundaryData/inlet/points

# Check first time directory
ls constant/boundaryData/inlet/0.000000/
cat constant/boundaryData/inlet/0.000000/U | head -20

# Check 0/U boundary condition
grep -A 5 "inlet" 0/U
```

### Common Issues

**Problem: "Points file not found"**
```
Solution: Run mesh generation before boundary condition setup
```

**Problem: "CSV file not found"**
```
Solution: Ensure CSV is in cases_input/{patient_name}/
```

**Problem: "Flow direction reversed"**
```
Solution:
- Use "orientation": "auto"
- Or manually set "in" vs "out"
- Check with ParaView: velocity should point into domain
```

**Problem: "Womersley requires nu"**
```
Solution: Add to physics section:
  "physics": {
    "nu": 3.77e-6
  }
```

---

## Template Variables (Advanced)

The inlet configuration can access these variables in templates:

```python
context = {
    "inlet_patch": "inlet",           # Detected from STL
    "inlet_settings": {...},           # Your inlet config
    "physics_settings": {...},         # Physics properties
    "openfoam_version": "12",         # OpenFOAM version
}
```

---

## Quick Reference Table

| Type | Steady/Transient | Profile Options | Data Source | Use Case |
|------|------------------|-----------------|-------------|----------|
| TIMEVARYING | Transient | plug, parabolic, womersley | CSV file | Cardiac cycle, realistic flow |
| PLUG | Steady | plug | config value | Simple testing, steady flow |
| PARABOLIC | Steady | parabolic | config value | Developed laminar flow |
| WOMERSLEY | Transient | womersley | CSV file | High-frequency pulsatile |

---

## Related Files

- **Inlet mapping logic:** [src/aortacfd_lib/inlet_mapping.py](src/aortacfd_lib/inlet_mapping.py)
- **BC setup:** [src/aortacfd_lib/boundary_condition_setup.py](src/aortacfd_lib/boundary_condition_setup.py)
- **Config builder:** [src/config/builder.py](src/config/builder.py)
- **U template:** [src/templates/U.tpl](src/templates/U.tpl)
- **Example configs:** [cases_input/patient1/](cases_input/patient1/)

---

## Summary

✅ **Supported Types:** TIMEVARYING, PLUG, PARABOLIC, WOMERSLEY
✅ **Profiles:** plug, parabolic, womersley
✅ **Data Types:** velocity, flowRate
✅ **Orientation:** auto (recommended), in, out
✅ **Auto-detection:** Determines flow direction from geometry

For outlet BC configuration, see [WINDKESSEL_BC_REFERENCE.md](WINDKESSEL_BC_REFERENCE.md)
