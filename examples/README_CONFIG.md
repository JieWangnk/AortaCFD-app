# AortaCFD Configuration Guide

**Updated**: January 23, 2026
**Version**: 2.3 (MRI Inlet Support)

---

## Configuration System Overview

AortaCFD uses a **hierarchical configuration system** with a new **3-profile numerics system** for simplified and reliable CFD simulations.

### Configuration Hierarchy (Override Order)

1. **Base Defaults** ([src/config/base.py](../src/config/base.py))
   - OpenFOAM 12 settings
   - Conservative mesh quality defaults
   - Physics defaults

2. **Numerics Profile** (robust/standard/precise)
   - Predefined numerical schemes
   - Solver settings and tolerances
   - Time integration methods

3. **Case Config** (`config.json`)
   - Case-specific overrides
   - Geometry and boundary conditions
   - Mesh resolution and simulation control

4. **Command-line Arguments** (highest priority)
   - Runtime overrides
   - Quick parameter adjustments

---

## The 3-Profile System

### Profile Selection Guide

| Profile | Use Case | Accuracy | Stability | Speed | Best For |
|---------|----------|----------|-----------|-------|----------|
| **robust** | Difficult meshes | 1st order | Maximum | Fast | Poor mesh quality, debugging |
| **standard** | Production | 2nd order | High | Fast | Most simulations (recommended) |
| **precise** | LES/Validation | 2nd order | Good | Slower | Minimal diffusion, LES, convergence studies |

### Profile Characteristics

#### **robust** Profile
```json
"numerics": {
  "profile": "robust"
}
```

- **Time Integration**: Euler (1st order)
- **Convection**: Upwind (1st order, bounded)
- **Courant Number**: 1.0 (stable with 1st order schemes)
- **Relaxation**: Moderate (U: 0.7, p: 0.3, pFinal: 0.9)
- **Tolerances**: 1e-3 (relaxed for convergence)
- **Best For**:
  - Initial testing of new geometries
  - Poor mesh quality (high skewness)
  - Debugging divergence issues
  - Coarse meshes
- **Warning**: Results will have numerical diffusion - not for final results!

#### **standard** Profile (Recommended)
```json
"numerics": {
  "profile": "standard"
}
```

- **Time Integration**: Backward (2nd order)
- **Convection**: limitedLinearV (2nd order TVD bounded)
- **Courant Number**: 1.0 (normal timesteps)
- **Relaxation**: Moderate (U: 0.7, p: 0.3, pFinal: 0.9)
- **Tolerances**: 1e-6 (good accuracy)
- **Best For**:
  - Production simulations
  - Good quality meshes
  - Most clinical/research cases
  - Balanced accuracy and convergence
- **Recommended**: Default choice for most users

#### **precise** Profile
```json
"numerics": {
  "profile": "precise"
}
```

- **Time Integration**: CrankNicolson 0.9 (better phase accuracy)
- **Convection**: LUST (75% central + 25% upwind, minimal diffusion)
- **Courant Number**: 0.8 (smaller timesteps for accuracy)
- **Relaxation**: Light (U: 0.9, p: 0.5)
- **Tolerances**: 1e-8 (very tight)
- **Best For**:
  - LES simulations (LUST preserves resolved turbulence)
  - Validation studies
  - Mesh convergence studies
  - Cases requiring minimal numerical diffusion
- **Note**: Requires excellent mesh quality (ortho > 70°, skewness < 2)

---

## Example Configuration Files

### Available Examples

| File | Description | Profile | Complexity |
|------|-------------|---------|------------|
| **config_minimal.json** | Simplest working serial laminar configuration | standard | ⭐ |
| **config_standard.json** | Practical pulsatile aortic case with Windkessel outlets | standard | ⭐⭐⭐ |
| **config_full.json** | Extended reference showing the broader option set | standard | ⭐⭐⭐⭐⭐ |

---

## Quick Start Guide

### 1. Minimal Configuration

```json
{
  "physics": {
    "model": "laminar",
    "transport_properties": {
      "rho": 1060,
      "nu": 3.7736e-6
    }
  },

  "numerics": {
    "profile": "standard"
  },

  "mesh": {
    "cells_per_diameter": 15,
    "boundary_layers": {
      "enabled": true,
      "num_layers": 5,
      "expansion_ratio": 1.2,
      "final_layer_thickness": 0.3
    }
  },

  "boundary_conditions": {
    "inlet": {
      "type": "CONSTANT",
      "cardiac_output": 5.0
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80
      }
    }
  },

  "simulation_control": {
    "end_time": 5.0,
    "writeInterval": 0.1
  }
}
```

### 2. Running a Case

```bash
# Using the patient runner
python run_patient.py CASE_NAME --config cases_input/CASE_NAME/config.json

# Prepare setup only
python run_patient.py CASE_NAME --steps case,mesh,boundary

# Re-run post-processing on an existing run
python run_patient.py --postprocess output/CASE_NAME/run_xxx

# View available options
python run_patient.py --help
```

---

## Input Data Units

AortaCFD uses **clinical-friendly units** for user input while internally converting to SI units for OpenFOAM.

### Unit Summary Table

| Parameter | User Input Unit | Internal (SI) | Notes |
|-----------|-----------------|---------------|-------|
| **cardiac_output** | L/min | m³/s | Automatic conversion |
| **flowrate** (config) | L/min | m³/s | Automatic conversion |
| **flowrate** (CSV) | **L/min** (auto-detect) | m³/s | If max > 1.0, assumes L/min |
| **velocity** | m/s | m/s | No conversion |
| **pressure** (WK) | mmHg | Pa | Automatic conversion |
| **geometry** | mm (with scale_factor=0.001) | m | Via scale_factor |
| **density (rho)** | kg/m³ | kg/m³ | SI unit |
| **viscosity (nu)** | m²/s | m²/s | SI unit |
| **time** | s | s | SI unit |

### CSV Flowrate Auto-Detection

For time-varying inlet (`TIMEVARYING`), the system automatically detects flowrate units:

```
max(flowrate) > 1.0  →  Assumes L/min  →  Converts to m³/s
max(flowrate) ≤ 1.0  →  Assumes m³/s   →  No conversion
```

**Example: Clinical flowrate CSV (L/min)**
```csv
# time (s), flowrate (L/min)
time,flowrate
0.000,0.25
0.050,2.70
0.090,3.30
0.200,0.25
0.500,0.25
```

**Log output confirms conversion:**
```
INFO: Flowrate CSV auto-detected as L/min (max=3.30)
INFO:   Converted to m³/s: max=5.500000e-05 m³/s
```

---

## Configuration Sections

### 1. **case_info** (Optional)
Metadata about the simulation case.

```json
"case_info": {
  "patient_id": "PATIENT001",
  "description": "Aortic coarctation study",
  "date": "2025-10-31"
}
```

### 2. **physics** (Required)
Physical model and fluid properties.

```json
"physics": {
  "model": "laminar",  // or "RAS", "LES"
  "transport_properties": {
    "rho": 1060,        // Density (kg/m³)
    "nu": 3.7736e-6     // Kinematic viscosity (m²/s)
  },
  "turbulence_intensity": 0.05  // For RANS/LES (5%)
}
```

**Models**:
- `laminar`: No turbulence (Re < 2300)
- `RAS`: RANS k-omega SST (Re > 4000)
- `LES`: Large Eddy Simulation WALE (advanced)

### 3. **numerics** (Required)
Numerical schemes via profile system.

```json
"numerics": {
  "profile": "standard",  // robust/standard/precise
  "max_co": 1.0,         // Override profile default
  "correctors": {
    "nOuterCorrectors": 3  // Override if needed
  }
}
```

### 4. **mesh** (Required)
Mesh generation parameters.

```json
"mesh": {
  "mesh_resolution": {
    "cells_per_diameter": 20   // RECOMMENDED: geometry-adaptive
  },
  "boundary_layers": {
    "enabled": true,
    "num_layers": 10,            // SimVascular standard (was 5)
    "expansion_ratio": 1.2,
    "final_layer_thickness": 0.3
  },
  "SNAPPY_SETTINGS": {
    "surfaceRefinementLevels": [1, 2]  // [min, max] snappy levels
  }
}
```

**Resolution Guidelines** (see [MESH_SPECIFICATION_GUIDE.md](../docs/_internal/MESH_SPECIFICATION_GUIDE.md)):

| Category | cells/D | Typical Elements | Use Case |
|----------|---------|------------------|----------|
| **Coarse** | 10-12 | 200k-500k | Initial exploration |
| **Standard** | 15-20 | 500k-2M | Production (recommended) |
| **Fine** | 25-30 | 2M-5M | Mesh independence studies |

**Surface Refinement Levels** (`surfaceRefinementLevels: [min, max]`):
- **[0, 1]**: Base cell / 2 at surface (minimal)
- **[1, 2]**: Base cell / 4 at surface (DEFAULT)
- **[2, 3]**: Base cell / 8 at surface (fine)

**Alternative: Absolute cell size** (for mesh studies):
```json
"mesh_resolution": {
  "target_cell_size_mm": 0.6  // Priority 1: overrides cells_per_diameter
}
```

### 5. **geometry** (Auto-discovered)
Patch names from STL files.

```json
"geometry": {
  "inlet_keywords_ordered": "inlet",
  "outlet_keywords_ordered": ["outlet1", "outlet2"],
  "wall_keywords_ordered": "wall_aorta",
  "scale_factor": 0.001  // mm to m
}
```

**Required STL Files**:
- `inlet.stl` - Inlet patch
- `outlet*.stl` - Outlet patches (numbered)
- `wall*.stl` - Wall patches

### 6. **boundary_conditions** (Required)
Inlet, outlet, and wall boundary conditions.

#### Inlet Options

**A. Constant Flow**
```json
"inlet": {
  "type": "CONSTANT",
  "cardiac_output": 5.0  // L/min
}
```

**B. Time-Varying Flow**
```json
"inlet": {
  "type": "TIMEVARYING",
  "csv_file": "patient_flow.csv",
  "data_type": "flowrate",  // or "velocity"
  "profile": "parabolic"    // plug, parabolic, elliptical, wall_distance, womersley
}
```

**CSV File Units (Important!):**

| data_type | Expected Unit | Auto-Detection |
|-----------|---------------|----------------|
| `flowrate` | **L/min** | Yes - values > 1.0 assumed L/min, converted internally to m³/s |
| `velocity` | **m/s** | No conversion needed |

The system automatically detects flowrate units based on magnitude:
- If max(flowrate) > 1.0 → assumes **L/min** (clinical standard), converts to m³/s internally
- If max(flowrate) ≤ 1.0 → assumes **m³/s** (SI units), no conversion

**Example CSV format (flowrate in L/min):**
```csv
time,flowrate
0.000,0.25
0.100,3.30
0.200,0.50
...
```

**Inlet Type Options**:
| Type | Description | Data Required |
|------|-------------|---------------|
| `CONSTANT` | Uniform plug flow | `velocity` or `cardiac_output` |
| `PARABOLIC` | Parabolic velocity profile | `velocity` or `cardiac_output` |
| `TIMEVARYING` | Time-varying from CSV | `csv_file`, `profile` |
| `WOMERSLEY` | Womersley pulsatile profile | `csv_file`, `n_harmonics` |
| `MRI` | Pre-processed 4D flow MRI data | `file` (directory path) |

**Inlet Profile Options (for TIMEVARYING)**:
| Profile | Description | Use Case |
|---------|-------------|----------|
| `plug` | Uniform velocity | Simple/turbulent inlet |
| `parabolic` | Poiseuille (U_max = 2*U_avg) | Circular laminar inlet (recommended) |
| `elliptical` | Elliptical Poiseuille | Non-circular but regular inlets |
| `wall_distance` | Distance-to-wall based | Irregular inlets (aortic root with valve leaflets) |
| `womersley` | Pulsatile with viscous effects | High-fidelity pulsatile studies |

**C. Womersley Profile with Auto Harmonics**
```json
"inlet": {
  "type": "WOMERSLEY",
  "csv_file": "patient_flow.csv",
  "n_harmonics": "auto"  // FFT-based spectral energy detection (99% threshold)
}
```

**D. MRI Inlet (Pre-processed 4D Flow Data) - NEW v2.3**

When spatially resolved inlet velocities from 4D flow MRI are available, use the `MRI` inlet type to bypass all profile mapping and use the data directly.

```json
"inlet": {
  "type": "MRI",
  "file": "./inlet/"
}
```

**MRI Inlet Data Format:**
```
cases_input/<case>/inlet/
├── 0.000000/U      # Velocity at t=0.000s
├── 0.005700/U      # Velocity at t=0.0057s
├── 0.011300/U      # ...
├── ...
└── 0.845000/U      # Last time = cardiac cycle period
```

**How it works:**
1. **No profile mapping** - U files are already in OpenFOAM format (one velocity vector per inlet face)
2. **Auto cardiac cycle detection** - System reads max time from directory names
3. **Multi-cycle via symlinks** - CycleDataSetup creates symlinks for additional cycles
4. **Points file generated from mesh** - Ensures face ordering matches your mesh

**When to use MRI inlet:**
- 4D flow MRI data has been pre-processed to OpenFOAM format
- Inlet geometry is complex (e.g., aortic root with valve leaflets)
- Spatially-resolved velocity measurements are available
- You want to preserve patient-specific inlet flow patterns

#### Outlet Options

**A. Zero Gradient (Simplest)**
```json
"outlets": {
  "type": "zeroGradient"
}
```

**B. Fixed Pressure**
```json
"outlets": {
  "type": "fixedValue",
  "pressure_pa": 10000  // Pascals
}
```

**C. 3-Element Windkessel (Recommended)**
```json
"outlets": {
  "type": "3EWINDKESSEL",
  "windkessel_settings": {
    "systolic_pressure": 120,     // mmHg
    "diastolic_pressure": 80,     // mmHg
    "venous_pressure": 5,         // mmHg
    "tau": 1.8,                   // seconds
    "flow_split": null,           // Auto Murray's law
    "initial_pressure_method": "diastolic"  // NEW: diastolic/systolic/MAP/zero
  }
}
```

**Initial Pressure Method (NEW v2.1)**:
| Method | Description |
|--------|-------------|
| `diastolic` | Start at diastolic pressure (DEFAULT, recommended) |
| `systolic` | Start at systolic pressure (if simulation starts at peak systole) |
| `MAP` | Start at mean arterial pressure = (SBP + 2*DBP) / 3 |
| `zero` | Start at zero pressure (debugging only) |

### 7. **simulation_control** (Required)
Time control and output settings.

```json
"simulation_control": {
  "end_time": 5.0,          // seconds or cycles
  "writeInterval": 0.1,     // Output frequency
  "functions": {
    "wallShearStress": {
      "enabled": true
    }
  }
}
```

### 8. **run_settings** (Optional)
Parallel execution settings.

```json
"run_settings": {
  "solution_type": "parallel",
  "subdomains": 8,
  "decomposition_method": "scotch"
}
```

### 9. **hemodynamics** (Optional, NEW v2.2)
Runtime hemodynamic metric computation.

```json
"hemodynamics": {
  "runtime_functions": {
    "wallShearStress": true,
    "fieldAverage": "auto",
    "pressureMonitoring": true
  },
  "tawss_settings": {
    "skip_cycles": 2,
    "periodicRestart": true,
    "keep_all_cycles": true
  }
}
```

**Runtime Functions:**
| Function | Description | When Enabled |
|----------|-------------|--------------|
| `wallShearStress` | Compute WSS at wall patches | Always (default: true) |
| `fieldAverage` | Time-average WSS for TAWSS | `"auto"` = pulsatile only |
| `pressureMonitoring` | Patch-averaged pressure | Always (default: true) |

**TAWSS Settings (Pulsatile Flow Only):**
| Setting | Description | Default |
|---------|-------------|---------|
| `skip_cycles` | Skip initial cycles before averaging | 2 |
| `periodicRestart` | Restart averaging each cardiac cycle | true |
| `keep_all_cycles` | Keep per-cycle TAWSS data | true |

**Hemodynamic Metrics:**
| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **TAWSS** | mean(\|WSS\|) over cycle | Low (<0.4 Pa) → atherosclerosis risk |
| **OSI** | 0.5 × (1 - \|mean(WSS)\| / mean(\|WSS\|)) | High (>0.3) → disturbed flow |
| **RRT** | 1 / ((1 - 2×OSI) × TAWSS) | High → long particle residence |

**Note:** For CONSTANT (steady) inlet, OSI=0 and TAWSS=WSS (no time variation).

---

## Common Workflows

### Workflow 1: Simple Laminar Flow

```json
{
  "physics": {"model": "laminar"},
  "numerics": {"profile": "standard"},
  "mesh": {"cells_per_diameter": 12},
  "boundary_conditions": {
    "inlet": {"type": "CONSTANT", "velocity": 0.5},
    "outlets": {"type": "zeroGradient"}
  }
}
```

### Workflow 2: RANS with Windkessel

```json
{
  "physics": {
    "model": "rans",
    "turbulence_intensity": 0.05
  },
  "numerics": {"profile": "standard"},
  "mesh": {
    "cells_per_diameter": 15,
    "boundary_layers": {
      "num_layers": 5,
      "expansion_ratio": 1.2,
      "final_layer_thickness": 0.3
    }
  },
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "flow.csv"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80
      }
    }
  }
}
```

### Workflow 3: Convergence Study

```json
{
  "numerics": {"profile": "precise"},
  "mesh": {"cells_per_diameter": 20},
  // Run with 12, 15, 18, 20 cells/diameter
}
```

---

## Mesh Quality Controls for LES (NEW v2.2)

**IMPORTANT UPDATE (January 7, 2026)**: Default mesh quality controls have been significantly tightened to **prevent negative volume cells** in complex cardiovascular geometries, especially for LES simulations.

### The Problem

Complex cardiovascular geometries (coarctations, stenoses, bifurcations) with high curvature and narrow regions can produce cells with:
- Negative or zero volume (numerical precision issues)
- High skewness (> 4.0) causing numerical instability
- Poor non-orthogonality (> 65°) requiring excessive correctors

These issues are particularly problematic for LES simulations which require high mesh quality.

### The Solution

AortaCFD v2.2 introduces tightened mesh quality defaults in `src/config/base.py`:

| Parameter | Old Default | New Default | Purpose |
|-----------|-------------|-------------|---------|
| `minVol` | 1e-13 | **1e-18** | Prevent negative volume cells |
| `minDeterminant` | 0.001 | **0.01** | Better cell shape quality |
| `maxBoundarySkewness` | 20 | **4** | Tighter boundary skewness for WSS accuracy |
| `maxInternalSkewness` | 8 | **4** | LES-compatible skewness |
| `maxNonOrtho` | 65° | **60°** | Reduced non-orthogonality requirement |
| `nSolveIter` | 10 | **100** | More snap solver iterations |
| `nSmoothPatch` | 3 | **5** | Better surface smoothing |
| `nLayerIter` | 50 | **100** | More layer addition iterations |

### Validation Results

**Before tightening (failed):**
```
***Zero or negative cell volume detected. Minimum negative volume: -2.32238e-16
***Max skewness = 51.89, highly skew faces detected
***Number of non-orthogonality errors: 22
Failed 4 mesh checks.
```

**After tightening (passed):**
```
Min volume = 8.42909e-18. Max volume = 4.90777e-13. Cell volumes OK.
Max skewness = 2.83 OK.
Mesh non-orthogonality Max: 59.99 average: 6.10
Mesh OK.
```

### Using Mesh Quality Presets

For different use cases, select appropriate presets:

```json
"mesh": {
  "quality_preset": "high_quality"  // For LES simulations
}
```

| Preset | Use Case | Key Settings |
|--------|----------|--------------|
| `draft` | Quick testing | Relaxed thresholds, faster |
| `standard` | Production (recommended) | Balanced quality/speed |
| `high_quality` | LES/validation | Ultra-tight: minVol=1e-20, maxSkewness=2.0 |

---

## Mesh Quality Utilities (NEW v2.1 - UNDER DEVELOPMENT)

AortaCFD now includes advanced mesh quality validation tools in `src/aortacfd_lib/utils/mesh_quality.py`.

### Mesh Quality Tier System

The mesh quality analyzer classifies meshes into tiers based on multiple metrics:

| Tier | Max Skewness | Max Non-Ortho | Max Aspect Ratio | Status |
|------|-------------|---------------|------------------|--------|
| **EXCELLENT** | < 1.5 | < 55° | < 20 | Production ready |
| **GOOD** | < 2.5 | < 65° | < 30 | Acceptable for most cases |
| **FAIR** | < 4.0 | < 70° | < 50 | May need robust profile |
| **POOR** | < 6.0 | < 75° | < 100 | Requires mesh improvement |
| **CRITICAL** | ≥ 6.0 | ≥ 75° | ≥ 100 | Simulation will likely fail |

### Grid Convergence Index (GCI)

For mesh independence studies, use Richardson extrapolation:

```python
from aortacfd_lib.utils.mesh_quality import GridConvergenceIndex

gci = GridConvergenceIndex()
result = gci.calculate(
    phi_values=[1.234, 1.256, 1.289],  # Results from fine, medium, coarse
    cell_counts=[2000000, 800000, 300000]  # Cell counts
)
print(f"GCI_fine: {result['gci_fine']:.2%}")  # e.g., 1.5%
print(f"Extrapolated value: {result['phi_extrapolated']:.4f}")
```

### Mass Balance Checker

Verify flow conservation at boundaries:

```python
from aortacfd_lib.utils.mesh_quality import MassBalanceChecker

checker = MassBalanceChecker()
result = checker.check(
    inlet_flow=100.0,  # mL/s
    outlet_flows={'outlet1': 15.0, 'outlet2': 15.0, 'outlet3': 10.0, 'outlet4': 60.0}
)
print(f"Mass balanced: {result['is_balanced']}")  # True if < 1% imbalance
```

---

## Advanced Configuration

### Custom Relaxation Factors

```json
"numerics": {
  "profile": "standard",
  "relaxation_factors": {
    "p": 0.2,  // More conservative pressure relaxation
    "U": 0.6   // More conservative velocity relaxation
  }
}
```

### Volume Refinement

```json
"mesh": {
  "volume_refinement": {
    "enabled": true,
    "regions": [{
      "name": "arch",
      "type": "box",
      "min": [-0.02, -0.02, 0.00],
      "max": [0.02, 0.02, 0.05],
      "level": 2
    }]
  }
}
```

### Manual Flow Split

```json
"windkessel_settings": {
  "flow_split": {
    "outlet1": 0.15,  // 15%
    "outlet2": 0.15,  // 15%
    "outlet3": 0.10,  // 10%
    "outlet4": 0.60   // 60% (main outlet)
  }
}
```

---

## Troubleshooting

### Problem: Simulation Diverges

**Solution**:
1. Switch to `"profile": "robust"`
2. Reduce `cells_per_diameter` (try 10-12)
3. Disable boundary layers temporarily
4. Check mesh quality with `checkMesh`

### Problem: Boundary Layer Collapse

**Solution**:
1. Reduce `num_layers` (try 3)
2. Increase `final_layer_thickness` (try 0.4-0.5)
3. Reduce `expansion_ratio` (try 1.15)
4. Check mesh with `maxBoundarySkewness < 8`

### Problem: Slow Convergence

**Solution**:
1. Adjust relaxation factors (lower = more stable)
2. Reduce `max_co` (try 0.5)
3. Increase correctors in PIMPLE
4. Check residuals - may need more iterations

### Problem: Unphysical Results

**Solution**:
1. Verify inlet/outlet flow conservation
2. Check Windkessel parameters (realistic pressures?)
3. Run longer (3-5 cardiac cycles)
4. Validate mesh quality

---

## References

### File Locations
- **Base Config**: `src/config/base.py`
- **Profiles**: `src/config/profiles/numerics/`
- **Templates**: `src/templates/`
- **Examples**: `examples/`

### Documentation
- **Full Config**: [config_full.json](config_full.json)
- **Test Suite**: [TEST_SUITE_SUMMARY.md](../TEST_SUITE_SUMMARY.md)
- **Numerics Profiles**: `src/config/profiles/numerics/__init__.py`

### Key Modules
- Config Builder: `src/config/builder.py`
- Y+ Estimator: `src/aortacfd_lib/yplus_estimator.py`
- Windkessel Setup: `src/aortacfd_lib/wk_setup.py`
- Boundary Conditions: `src/aortacfd_lib/boundary_condition_setup.py`

---

## Best Practices

1. **Start Simple**: Use `standard` profile with moderate resolution
2. **Validate Mesh**: Always run `checkMesh` before simulation (use tier system for guidance)
3. **Check Conservation**: Monitor mass flow rate at inlet/outlets (use MassBalanceChecker)
4. **Use Windkessel**: More physiologically realistic than fixed pressure
5. **Run Multiple Cycles**: 3-5 cycles for pulsatile flow
6. **Monitor Residuals**: Should decrease steadily
7. **Validate Results**: Compare with literature/clinical data
8. **Document Changes**: Keep notes on parameter adjustments
9. **Use Parabolic Profile**: For circular laminar inlets, `profile: "parabolic"` gives correct U_max = 2*U_avg
10. **Boundary Layers**: Use 10 layers (SimVascular standard) with 1.2 expansion ratio
11. **Mesh Independence**: Run GCI study with 3 mesh levels before final results

---

**Last Updated**: January 23, 2026
**Maintained by**: AortaCFD Development Team
**Questions?**: Check test suite or open an issue

---

## Version History

### v2.3 (January 2026)
- **MRI Inlet Support**: NEW `type: "MRI"` for pre-processed 4D flow MRI inlet data
  - Direct use of OpenFOAM-format velocity data (no profile mapping)
  - Auto-detection of cardiac cycle from time directory names
  - Multi-cycle support via symbolic links
  - Bypasses CSV processing and velocity profile interpolation

### v2.2 (January 2026)
- **Hemodynamics Module**: NEW runtime hemodynamics computation (WSS, TAWSS, OSI, RRT, pressure drop)
- **Flowrate Unit Auto-Detection**: CSV flowrate data auto-detected as L/min if max > 1.0, converted to m³/s internally
- **Input Data Units Section**: Added comprehensive documentation of all input units
- **fieldAverage Auto Mode**: `"auto"` enables time-averaging only for pulsatile flow
- **TAWSS Settings**: Configurable skip_cycles, periodicRestart, keep_all_cycles for convergence analysis
- **Pressure Monitoring**: Area-averaged pressure at all patches for pressure drop calculation
- **Mesh Quality Controls for LES**: Tightened defaults to prevent negative volume cells
  - `minVol`: 1e-13 → 1e-18 (prevent negative volumes)
  - `minDeterminant`: 0.001 → 0.01 (better cell quality)
  - `maxBoundarySkewness`: 20 → 4 (WSS accuracy)
  - `maxInternalSkewness`: 8 → 4 (LES compatibility)
  - `nSolveIter`: 10 → 100 (more snap iterations)
  - Validated: 4.7M cell mesh passes checkMesh with zero negative volumes

### v2.1 (December 2025)
- **Enhanced Inlet Profiles**: Added `elliptical`, `wall_distance` profiles for irregular inlet geometries
- **Womersley Auto-Harmonics**: `n_harmonics: "auto"` uses FFT-based spectral energy detection
- **Initial Pressure Method**: New Windkessel option for simulation initialization
- **Boundary Layer Defaults**: Updated to 10 layers (SimVascular standard)
- **Mesh Quality Utilities**: NEW `mesh_quality.py` with tier system, GCI calculator, mass balance checker
- **Parabolic Velocity Fix**: Corrected scaling to use analytical U_max = 2*Q/A

### v2.0 (October 2025)
- 3-Profile numerics system (robust/standard/precise)
- Complete Windkessel configuration options
- Enhanced mesh resolution controls
