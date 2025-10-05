# AortaCFD Configuration Guide

Complete guide to configuring AortaCFD simulations.

## Quick Start

### Option 1: Use Simple Config (Recommended for Testing)
```bash
./venv/bin/python3 run_patient.py patient1 --config cases_input/patient1/config_simple_rans_coarse.json
```

### Option 2: Use Default Config
```bash
./venv/bin/python3 run_patient.py patient1
```

## Configuration Files

### 1. **config_simple_rans_coarse.json** - Minimal Example
- Simplest possible configuration for RANS coarse simulation
- Only essential settings included
- Serial execution (1 processor)
- 1 second test run
- Ideal for quick validation

### 2. **config_comprehensive.json** - Complete Reference
- **ALL** possible configuration options documented
- Extensive inline documentation with `_comment` fields
- Shows all available choices for each setting
- Includes validation ranges and usage examples
- 400+ lines covering every feature

### 3. **config.json** - Default Production Config
- Production configuration for patient1
- Optimized for realistic cardiac simulations
- Uses advanced features (LES, Windkessel)

## Configuration Structure

### Core Sections

#### 1. **case_info**
Patient identification and metadata
```json
{
  "case_info": {
    "patient_id": "patient1",
    "description": "Description of the case"
  }
}
```

#### 2. **simulation_settings**
High-level simulation type selection
```json
{
  "simulation_settings": {
    "analysis_type": "coarse|medium|fine",
    "solver_type": "laminar|RANS|LES"
  }
}
```

**Analysis Types:**
- `coarse`: 1.8mm cells (~1.5M cells) - Fast testing
- `medium`: 1.0mm cells (~3.5M cells) - Balanced quality
- `fine`: 0.6mm cells (~7M cells) - High accuracy

**Solver Types:**
- `laminar`: Direct numerical simulation (no turbulence model)
- `RANS`: Reynolds-Averaged with k-omega SST
- `LES`: Large Eddy Simulation with WALE or Smagorinsky

#### 3. **physics**
Physical properties and turbulence models
```json
{
  "physics": {
    "blood_density": 1060,           // kg/m³ (range: 1000-1200)
    "blood_viscosity": 0.004,        // Pa·s (range: 0.001-0.01)
    "simulation_type": "laminar|RAS|LES",

    // RANS-specific (when simulation_type = "RAS")
    "turbulence_model": "kOmegaSST",
    "turbulence_intensity": 0.05,    // 5% (range: 0.05-0.08)
    "turbulence_viscosity_ratio": 10.0,

    // LES-specific (when simulation_type = "LES")
    "subgrid_model": "WALE|Smagorinsky",
    "filter_width": "cubeRootVol"
  }
}
```

#### 4. **geometry**
Geometry transformation settings
```json
{
  "geometry": {
    "rotation": true,                // Auto-rotate to align inlet
    "target_normal": [0, 0, 1],      // Desired inlet direction
    "scale_factor": 0.001            // 0.001 = mm to m conversion
  }
}
```

**Auto-discovered fields** (from STL files):
- `case_name`: From patient folder name
- `wall_keywords_ordered`: From wall*.stl
- `inlet_keywords_ordered`: From inlet*.stl
- `outlet_keywords_ordered`: From outlet*.stl (sorted numerically)

#### 5. **mesh**
Mesh generation settings

**Resolution Settings:**
```json
{
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 1.0,    // Overall target cell size

      "cells_per_diameter": {
        "inlet": 15,                  // Cells across inlet diameter
        "branch": 12                  // Cells across branches
      },

      "refinement_targets_mm": {
        "background": 0.0015,
        "surface": 0.001,
        "feature": 0.0007
      }
    }
  }
}
```

**snappyHexMesh Settings:**
```json
{
  "mesh": {
    "SNAPPY_SETTINGS": {
      "parallel": true,
      "nProcessors": 4,               // Cores for meshing

      // Cell limits
      "maxLocalCells": 3800000,
      "maxGlobalCells": 4000000,

      // Quality settings
      "nCellsBetweenLevels": 2,
      "surfaceRefinementLevels": [1, 1],
      "resolveFeatureAngle": 60,

      // Iterations
      "nSmoothPatch": 5,
      "tolerance": 3.0,
      "nSolveIter": 500,
      "nRelaxIter": 8,

      // Boundary layers
      "addLayer": 0,                  // 0 = no layers

      "relaxed": {
        "maxNonOrtho": 75
      }
    }
  }
}
```

#### 6. **boundary_conditions**
Inlet, outlet, and wall boundary conditions

**Inlet Types:**

1. **TIMEVARYING** (Cardiac profile from CSV)
```json
{
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "test_cardio_profile.csv",
    "data_type": "velocity",          // or "flow_rate"
    "profile": "womersley",           // "plug"|"parabolic"|"womersley"
    "orientation": "out"              // "in"|"out"
  }
}
```

2. **CONSTANT** (Fixed velocity)
```json
{
  "inlet": {
    "type": "CONSTANT",
    "velocity_magnitude": 0.5         // m/s
  }
}
```

**Outlet Types:**

1. **3EWINDKESSEL** (3-Element Windkessel with RCR)
```json
{
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "systolic_pressure": 120,       // mmHg
      "diastolic_pressure": 80,       // mmHg
      "methodology": "murray_law_automatic",

      // Murray's Law settings (for automatic)
      "murray_exponent": 2.39,        // 2.0-2.7 depending on vessel type
      "reference_radius_strategy": "inlet_based"
    }
  }
}
```

**Murray Exponent Values:**
- `2.0`: Large vessels (>25mm)
- `2.2`: Medium-large vessels (15-25mm)
- `2.39`: Medium/aortic vessels (8-15mm) - Default
- `2.5`: Coronary arteries (4-8mm)
- `2.7`: Small vessels (<4mm)

2. **ZEROGRADIENT** (Simplest outlet)
```json
{
  "outlets": {
    "type": "ZEROGRADIENT"
  }
}
```

3. **FLOWSPLIT** (Manual flow distribution)
```json
{
  "outlets": {
    "type": "FLOWSPLIT",
    "flow_split": [0.3, 0.25, 0.25, 0.2]  // Must sum to 1.0
  }
}
```

**Wall Conditions:**
```json
{
  "walls": {
    "type": "no_slip",                // "no_slip"|"slip"|"partial_slip"
    "roughness": 0.0                  // Wall roughness height (m)
  }
}
```

#### 7. **simulation_control**
Time control and output settings
```json
{
  "simulation_control": {
    "number_of_cycles": 5,            // Cardiac cycles (optional)
    "end_time": 4.0,                  // Seconds, or "auto"
    "writeInterval": 0.01,            // Output frequency (seconds)

    "controlDict": {
      "application": "foamRun",
      "deltaT": 1e-5,                 // Initial time step
      "adjustTimeStep": true,
      "maxCo": 1.0,                   // Courant number limit
      "maxDeltaT": 0.0002,
      "minDeltaT": 1e-7,
      "functions": ["wallShearStress"]
    }
  }
}
```

#### 8. **run_settings**
Execution and parallelization
```json
{
  "run_settings": {
    "solution_type": "parallel",      // "serial"|"parallel"
    "subdomains": 4,                  // Processors for solver
    "decomposition_method": "scotch"  // "simple"|"hierarchical"|"scotch"|"metis"
  }
}
```

**Decomposition Methods:**
- `simple`: Simple geometric decomposition
- `hierarchical`: Hierarchical decomposition
- `scotch`: Graph-based (recommended for complex geometries)
- `metis`: Graph-based alternative

#### 9. **output_settings** (Optional)
Post-processing and data export
```json
{
  "output_settings": {
    "save_frequency": 10,
    "variables": ["velocity", "pressure", "wall_shear_stress"],
    "post_processing": {
      "generate_report": true,
      "create_animations": false,
      "export_vtk": true,
      "export_csv": true
    }
  }
}
```

## Common Use Cases

### Quick Laminar Test
```json
{
  "simulation_settings": {
    "analysis_type": "coarse",
    "solver_type": "laminar"
  },
  "boundary_conditions": {
    "inlet": {"type": "CONSTANT", "velocity_magnitude": 0.5},
    "outlets": {"type": "ZEROGRADIENT"}
  },
  "simulation_control": {
    "end_time": 0.5
  }
}
```

### Realistic Cardiac Simulation
```json
{
  "simulation_settings": {
    "analysis_type": "medium",
    "solver_type": "laminar"
  },
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "cardiac_profile.csv",
      "profile": "womersley"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80,
        "methodology": "murray_law_automatic"
      }
    }
  },
  "simulation_control": {
    "number_of_cycles": 5
  }
}
```

### Turbulent Flow Study
```json
{
  "simulation_settings": {
    "analysis_type": "fine",
    "solver_type": "RANS"
  },
  "physics": {
    "simulation_type": "RAS",
    "turbulence_model": "kOmegaSST",
    "turbulence_intensity": 0.05
  },
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 0.6
    }
  }
}
```

## Validation Ranges

### Physics
- Blood density: 1000-1200 kg/m³ (normal ~1060)
- Blood viscosity: 0.001-0.01 Pa·s (normal ~0.004)
- Turbulence intensity: 0.05-0.08 (5-8%)

### Numerical
- maxCo: 0.1-2.0 (recommend < 1.0 for stability)
- maxDeltaT: > 0 seconds
- minDeltaT: > 0 seconds

### Execution
- Mesh processors: 1-128
- Solver processors: 1-128
- End time: > 0 seconds

## Configuration Format Support

The system supports **both** config formats:

1. **Nested format** (in config.json):
```json
{
  "boundary_conditions": {
    "inlet": { ... },
    "outlets": { ... }
  }
}
```

2. **Flattened format** (after ConfigBuilder merge):
```json
{
  "inlet": { ... },
  "outlets": { ... }
}
```

Both formats are validated and work correctly.

## Command Line Usage

### Basic Usage
```bash
# Use default config.json
./venv/bin/python3 run_patient.py patient1

# Use custom config
./venv/bin/python3 run_patient.py patient1 --config path/to/config.json
```

### Step-by-Step Execution
```bash
# Run only mesh generation
./venv/bin/python3 run_patient.py patient1 --steps mesh

# Run mesh and boundary conditions
./venv/bin/python3 run_patient.py patient1 --steps mesh,boundary

# Run specific steps
./venv/bin/python3 run_patient.py patient1 --steps case,mesh,boundary,solver
```

### List Available Steps
```bash
./venv/bin/python3 run_patient.py patient1 --list-steps
```

## Troubleshooting

### Config File Not Found
**Error:** `Custom configuration file not found`

**Solution:** Use full path or path relative to project root:
```bash
./venv/bin/python3 run_patient.py patient1 --config cases_input/patient1/my_config.json
```

### Boundary Condition Validation Failed
**Error:** `No boundary_conditions section found`

**Solution:** Ensure config has either:
- Nested: `"boundary_conditions": { "inlet": {...}, "outlets": {...} }`
- Or flattened: `"inlet": {...}, "outlets": {...}` at root level

### Mesh Quality Issues
**Warning:** `Mesh quality issues detected`

**Solutions:**
1. Increase mesh resolution: `"target_cell_size_mm": 1.0` → `0.8`
2. Increase snappy iterations: `"nSolveIter": 500` → `700`
3. Use coarser quality thresholds: `"maxNonOrtho": 75` → `80`

### Solver Divergence
**Error:** Solver crashes or produces NaN values

**Solutions:**
1. Reduce maxCo: `"maxCo": 1.0` → `0.5`
2. Reduce initial time step: `"deltaT": 1e-5` → `1e-6`
3. Use more robust schemes (switch to `sim_*_coarse` profile)
4. Check boundary conditions are physically realistic

## Reference Files

1. **[config_comprehensive.json](cases_input/patient1/config_comprehensive.json)**
   - Complete reference with all options
   - Extensive documentation
   - Use as template for custom configs

2. **[config_simple_rans_coarse.json](cases_input/patient1/config_simple_rans_coarse.json)**
   - Minimal working example
   - Quick testing
   - Starting point for modifications

3. **[config.json](cases_input/patient1/config.json)**
   - Production configuration
   - Optimized settings
   - Realistic cardiac simulation

## Next Steps

1. Review [config_comprehensive.json](cases_input/patient1/config_comprehensive.json) for all available options
2. Copy [config_simple_rans_coarse.json](cases_input/patient1/config_simple_rans_coarse.json) and modify for your needs
3. Test with quick simulation: `end_time: 0.5`, `analysis_type: "coarse"`
4. Scale up to production settings once validated

---

**Generated by AortaCFD Development Team**
