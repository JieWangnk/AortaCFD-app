# AortaCFD Configuration Guide

**Updated**: December 3, 2025
**Version**: 2.1 (Enhanced Inlet Profiles & Mesh Quality)

---

## 📋 Configuration System Overview

AortaCFD uses a **hierarchical configuration system** with a new **3-profile numerics system** for simplified and reliable CFD simulations.

### Configuration Hierarchy (Override Order)

1. **Base Defaults** ([src/config/base.py](../src/config/base.py))
   - OpenFOAM 12 settings
   - Conservative mesh quality defaults
   - Physics defaults

2. **Numerics Profile** (robust/standard/accurate)
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

## 🎯 The 3-Profile System

### Profile Selection Guide

| Profile | Use Case | Accuracy | Stability | Speed | Best For |
|---------|----------|----------|-----------|-------|----------|
| **robust** | Difficult meshes | 1st order | Maximum | Slower | Poor mesh quality, debugging |
| **standard** | Production | 2nd order | High | Fast | Most simulations (recommended) |
| **accurate** | Validation | 2nd order | Medium | Slower | Well-resolved meshes, publications |

### Profile Characteristics

#### 🛡️ **robust** Profile
```json
"numerics": {
  "profile": "robust"
}
```

- **Time Integration**: Euler (1st order)
- **Convection**: Upwind (1st order, bounded)
- **Courant Number**: 0.5 (small timesteps)
- **Relaxation**: Heavy (U: 0.5, p: 0.2)
- **Tolerances**: 1e-5 (tight for stability)
- **Best For**:
  - Initial testing of new geometries
  - Poor mesh quality (high skewness)
  - Debugging divergence issues
  - Coarse meshes
- **⚠️ Warning**: Results will have numerical diffusion - not for final results!

#### ⚖️ **standard** Profile (Recommended)
```json
"numerics": {
  "profile": "standard"
}
```

- **Time Integration**: Backward (2nd order)
- **Convection**: linearUpwind (2nd order bounded)
- **Courant Number**: 1.0 (normal timesteps)
- **Relaxation**: Moderate (U: 0.7, p: 0.3)
- **Tolerances**: 1e-6 (good accuracy)
- **Best For**:
  - Production simulations
  - Good quality meshes
  - Most clinical/research cases
  - Balanced accuracy and convergence
- **✅ Recommended**: Default choice for most users

#### 🎯 **accurate** Profile
```json
"numerics": {
  "profile": "accurate"
}
```

- **Time Integration**: CrankNicolson 0.9 (better phase accuracy)
- **Convection**: LUST (low diffusion)
- **Courant Number**: 0.5 (small timesteps for accuracy)
- **Relaxation**: Light (U: 0.9, p: 0.7)
- **Tolerances**: 1e-8 (very tight)
- **Best For**:
  - Validation studies
  - Well-resolved meshes (fine)
  - Publications
  - Mesh convergence studies
- **⚠️ Note**: Requires good mesh quality and may be slower

---

## 📁 Example Configuration Files

### Available Examples

| File | Description | Profile | Complexity |
|------|-------------|---------|------------|
| **config_full.json** | Complete reference with ALL parameters | standard | ⭐⭐⭐⭐⭐ |
| *(To be created)* **config_minimal.json** | Simplest working configuration | standard | ⭐ |
| *(To be created)* **config_laminar.json** | Laminar flow example | standard | ⭐⭐ |
| *(To be created)* **config_rans.json** | RANS turbulence example | standard | ⭐⭐⭐ |
| *(To be created)* **config_windkessel.json** | 3-element Windkessel | standard | ⭐⭐⭐⭐ |

---

## 🚀 Quick Start Guide

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

# View available options
python run_patient.py --help
```

---

## 📊 Configuration Sections

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
  "profile": "standard",  // robust/standard/accurate
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

**Resolution Guidelines** (see [MESH_SPECIFICATION_GUIDE.md](../docs/MESH_SPECIFICATION_GUIDE.md)):

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

**Inlet Profile Options (NEW v2.1)**:
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

#### Outlet Options

**A. Zero Gradient (Simplest)**
```json
"outlets": {
  "type": "ZEROGRADIENT"
}
```

**B. Fixed Pressure**
```json
"outlets": {
  "type": "FIXEDPRESSURE",
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

---

## 🎓 Common Workflows

### Workflow 1: Simple Laminar Flow

```json
{
  "physics": {"model": "laminar"},
  "numerics": {"profile": "standard"},
  "mesh": {"cells_per_diameter": 12},
  "boundary_conditions": {
    "inlet": {"type": "CONSTANT", "velocity": 0.5},
    "outlets": {"type": "ZEROGRADIENT"}
  }
}
```

### Workflow 2: RANS with Windkessel

```json
{
  "physics": {
    "model": "RAS",
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
  "numerics": {"profile": "accurate"},
  "mesh": {"cells_per_diameter": 20},
  // Run with 12, 15, 18, 20 cells/diameter
}
```

---

## 🔬 Mesh Quality Utilities (NEW v2.1 - UNDER DEVELOPMENT)

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

## ⚙️ Advanced Configuration

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

## 🐛 Troubleshooting

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

## 📚 References

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

## ✅ Best Practices

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

**Last Updated**: December 3, 2025
**Maintained by**: AortaCFD Development Team
**Questions?**: Check test suite or open an issue

---

## 📝 Version History

### v2.1 (December 2025)
- **Enhanced Inlet Profiles**: Added `elliptical`, `wall_distance` profiles for irregular inlet geometries
- **Womersley Auto-Harmonics**: `n_harmonics: "auto"` uses FFT-based spectral energy detection
- **Initial Pressure Method**: New Windkessel option for simulation initialization
- **Boundary Layer Defaults**: Updated to 10 layers (SimVascular standard)
- **Mesh Quality Utilities**: NEW `mesh_quality.py` with tier system, GCI calculator, mass balance checker
- **Parabolic Velocity Fix**: Corrected scaling to use analytical U_max = 2*Q/A

### v2.0 (October 2025)
- 3-Profile numerics system (robust/standard/accurate)
- Complete Windkessel configuration options
- Enhanced mesh resolution controls
