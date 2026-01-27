# AortaCFD Examples and User Guide

**Version**: 2.0 (3-Profile System)
**Last Updated**: October 31, 2025

---

## 📚 Quick Navigation

- [Configuration Guide](#configuration-guide) - Complete configuration reference
- [Boundary Layers](#boundary-layer-configuration) - Y+ and mesh layers
- [Function Objects](#function-objects) - Wall shear stress, post-processing
- [Troubleshooting](#troubleshooting) - Common issues and solutions
- [Example Configurations](#example-configurations) - Working examples

---

## 🚀 Quick Start

### 1. Minimal Working Configuration

Create `cases_input/MY_CASE/config.json`:

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
      "target_yplus": 1.0,
      "num_layers": 5,
      "expansion_ratio": 1.2
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

### 2. Required Geometry Files

Place in `cases_input/MY_CASE/`:
- `inlet.stl` - Inlet surface
- `outlet1.stl`, `outlet2.stl`, ... - Outlet surfaces
- `wall_aorta.stl` (or `wall.stl`) - Wall surfaces

### 3. Run Simulation

```bash
python run_patient.py MY_CASE --config cases_input/MY_CASE/config.json
```

---

## ⚙️ Configuration Guide

### 🎯 The 3-Profile System

| Profile | Time | Convection | Use Case | Best For |
|---------|------|------------|----------|----------|
| **robust** | Euler (1st) | Upwind (1st) | Difficult meshes | Poor quality, debugging |
| **standard** ⭐ | Backward (2nd) | limitedLinearV (2nd) | Production | Most cases (recommended) |
| **precise** | CrankNicolson | LUST | Validation | LES, minimal diffusion |

**Select profile in config:**
```json
"numerics": {
  "profile": "standard"
}
```

### 📐 Mesh Resolution Guidelines

| Level | cells_per_diameter | Cell Size (25mm vessel) | Use Case |
|-------|-------------------|------------------------|----------|
| Coarse | 8-10 | ~2.5-3 mm | Initial testing |
| Medium | 12-15 | ~1.7-2 mm | **Production** |
| Fine | 18-20 | ~1.25-1.4 mm | Convergence studies |
| Very Fine | 25+ | <1 mm | Publications |

**Configuration:**
```json
"mesh": {
  "cells_per_diameter": 15
}
```

---

## 🌊 Boundary Layer Configuration

### Automatic Y+ Control (Recommended)

System calculates layer thickness automatically to achieve target y+:

```json
"boundary_layers": {
  "enabled": true,
  "target_yplus": 1.0,
  "num_layers": 5,
  "expansion_ratio": 1.2
}
```

**How it works:**
1. Estimates Reynolds number from inlet geometry
2. Calculates wall shear stress
3. Computes first layer thickness for target y+
4. Generates appropriate snappyHexMesh settings

**Y+ Targets by Physics Model:**

| Model | Target y+ | Recommended Layers | Expansion Ratio |
|-------|-----------|-------------------|-----------------|
| Laminar | N/A (use manual) | 5 | 1.2 |
| RANS (wall-resolved) | 1-5 | 5-8 | 1.15-1.2 |
| RANS (wall functions) | 30-100 | 3-5 | 1.3-1.5 |
| LES | <1 | 8-10 | 1.1-1.15 |

### Manual Layer Control

Specify exact thickness (bypasses Y+ calculation):

```json
"boundary_layers": {
  "enabled": true,
  "num_layers": 5,
  "expansion_ratio": 1.2,
  "finalLayerThickness": 0.1
}
```

**When to use manual:**
- Laminar simulations (y+ not applicable)
- Known good values from previous studies
- Debugging mesh issues
- Y+ estimation unreliable for geometry

### Boundary Layer Quality Guidelines

**✅ Good Layer Quality:**
- 90%+ patches achieve target layer count
- Layers grow smoothly without collapse
- maxBoundarySkewness < 8
- Aspect ratio reasonable (<20:1)

**⚠️ Signs of Layer Problems:**
- < 50% success rate
- High boundary skewness (>10)
- Layers collapse near features
- Very thin layers (<10% cell size)

**Solutions for Layer Collapse:**

1. **Reduce number of layers**
   ```json
   "num_layers": 3  // Instead of 5 or 10
   ```

2. **Gentler expansion ratio**
   ```json
   "expansion_ratio": 1.15  // Instead of 1.2
   ```

3. **Increase target y+** (if acceptable)
   ```json
   "target_yplus": 5.0  // Instead of 1.0
   ```

4. **For fine meshes (>16 cells/diameter):**
   - Use fewer layers (3-5)
   - Higher expansion ratio (1.3-1.5)
   - Finer background mesh provides resolution

**Mesh Resolution vs. Layers:**

| cells_per_diameter | Recommended num_layers | expansion_ratio | Note |
|-------------------|----------------------|-----------------|------|
| 8 (coarse) | 8-10 | 1.2 | Need more layers |
| 12 (medium) | 5-7 | 1.2-1.25 | Balanced |
| 16 (fine) | 3-5 | 1.3-1.5 | Background mesh helps |
| 20+ (very fine) | 2-3 | 1.5-1.8 | Minimal layers needed |

---

## 📊 Function Objects

Function objects compute quantities during simulation (not post-processing).

### Built-in Functions

Add to your config:

```json
"simulation_control": {
  "controlDict": {
    "functions": [
      "wallShearStress",
      "yPlus",
      "forces"
    ]
  }
}
```

### Wall Shear Stress (WSS)

**Purpose:** Calculate wall shear stress on wall patches

**Configuration:**
```json
"functions": ["wallShearStress"]
```

**Output:**
- Field: `wallShearStress` (vector field, Pa)
- Written each `writeInterval`
- View in ParaView: Use `mag(wallShearStress)` for magnitude

**Physiological Values (Aorta):**
- Normal: 10-20 Pa (time-averaged)
- Peak systolic: 40-70 Pa
- Low/disturbed: <4 Pa (atherosclerosis risk)
- High WSS: >70 Pa (aneurysm risk)

**Clinical Indices:**
- **OSI** (Oscillatory Shear Index): Directional changes
- **TAWSS** (Time-Averaged WSS): Average over cycle
- **RRT** (Relative Residence Time): Blood residence

### Y+ Monitoring

**Purpose:** Check boundary layer resolution (RANS/LES only)

**Configuration:**
```json
"functions": ["yPlus"]
```

**Target Values:**
- Wall-resolved RANS: y+ < 1-5
- Wall functions: 30 < y+ < 300
- LES: y+ < 1

**Note:** Only relevant for turbulent models, not laminar.

### Custom Function Objects

For advanced post-processing:

```json
"controlDict": {
  "functions_custom": {
    "myProbe": {
      "type": "probes",
      "libs": ["\"libsampling.so\""],
      "fields": ["p", "U"],
      "probeLocations": [
        [0.01, 0.01, 0.03],
        [0.02, 0.00, 0.05]
      ],
      "writeControl": "timeStep",
      "writeInterval": 1
    }
  }
}
```

---

## 🔧 Boundary Conditions

### Inlet Boundary Conditions

#### 1. Constant Flow (Simplest)

```json
"inlet": {
  "type": "CONSTANT",
  "cardiac_output": 5.0
}
```
- Specify cardiac output in L/min
- System calculates velocity from inlet area
- Uniform plug flow profile

#### 2. Time-Varying Flow (Realistic)

```json
"inlet": {
  "type": "TIMEVARYING",
  "csv_file": "patient_flow.csv",
  "data_type": "flowrate"
}
```

**CSV Format:**
```
time(s),flowrate(mL/s)
0.0,100
0.1,120
0.2,150
...
```

**Data types:**
- `"flowrate"`: Flow rate in mL/s
- `"velocity"`: Velocity in m/s

#### 3. Parabolic Profile

```json
"inlet": {
  "type": "PARABOLIC",
  "velocity": 0.5
}
```
- Parabolic velocity profile (Poiseuille)
- Good for laminar pipe flow

#### 4. Womersley Profile (Advanced)

```json
"inlet": {
  "type": "WOMERSLEY",
  "csv_file": "flow.csv",
  "womersley_number": 10
}
```
- Pulsatile analytical profile
- Accounts for inertial effects

### Outlet Boundary Conditions

#### 1. Zero Gradient (Simplest)

```json
"outlets": {
  "type": "ZEROGRADIENT"
}
```
- Natural outflow
- No backflow prevention
- Best for high-velocity outlets

#### 2. Fixed Pressure

```json
"outlets": {
  "type": "FIXEDPRESSURE",
  "pressure_pa": 10000
}
```
- Fixed pressure value in Pascals
- Simple but may not be physiological

#### 3. 3-Element Windkessel (Recommended)

```json
"outlets": {
  "type": "3EWINDKESSEL",
  "windkessel_settings": {
    "systolic_pressure": 120,
    "diastolic_pressure": 80,
    "venous_pressure": 5,
    "tau": 1.8,
    "flow_split": null
  }
}
```

**Parameters:**
- `systolic_pressure`: mmHg (typical adult: 110-130)
- `diastolic_pressure`: mmHg (typical adult: 70-85)
- `venous_pressure`: mmHg (typical: 0-5)
- `tau`: Diastolic decay time in seconds (1.5-2.5)
- `flow_split`: `null` = auto Murray's law

**Flow Distribution:**

**Automatic (Murray's Law):**
```json
"flow_split": null
```
- Distributes flow by vessel radius³
- Physiologically realistic
- Recommended for most cases

**Manual Specification:**
```json
"flow_split": {
  "outlet1": 0.15,
  "outlet2": 0.15,
  "outlet3": 0.10,
  "outlet4": 0.60
}
```
- Must sum to 1.0
- Use for specific clinical scenarios

**Percentage (branches):**
```json
"flow_split": 40
```
- First N-1 outlets share 40% (by area)
- Last outlet gets 60% (main vessel)

---

## 🔍 Troubleshooting

### Simulation Diverges

**Symptoms:**
- Residuals increase exponentially
- Courant number explodes
- NaN values in fields

**Solutions:**
1. Use `robust` profile
   ```json
   "numerics": {"profile": "robust"}
   ```

2. Reduce Courant number
   ```json
   "numerics": {"max_co": 0.5}
   ```

3. Increase relaxation (lower values)
   ```json
   "numerics": {
     "relaxation_factors": {
       "p": 0.2,
       "U": 0.5
     }
   }
   ```

4. Check mesh quality: `checkMesh -allTopology`

### Boundary Layers Collapse

**Symptoms:**
- <50% layer coverage
- High skewness warnings
- Thin, distorted cells near walls

**Solutions:**
1. **Reduce layers**: `"num_layers": 3`
2. **Gentler ratio**: `"expansion_ratio": 1.15`
3. **Coarser mesh**: Reduce `cells_per_diameter`
4. **Manual control**: Specify `finalLayerThickness` directly

### Unrealistic Results

**Check:**
1. **Mass conservation**: Inlet flow = Sum of outlet flows
2. **Pressure levels**: Reasonable mmHg values
3. **Velocity magnitudes**: <2 m/s for aorta
4. **Residuals**: Decreasing steadily
5. **Number of cycles**: Run 3-5 cycles minimum

### Slow Convergence

**Solutions:**
1. Adjust PIMPLE correctors
   ```json
   "numerics": {
     "correctors": {
       "nOuterCorrectors": 5,
       "nCorrectors": 3
     }
   }
   ```

2. Tighter tolerances may actually help
   ```json
   "residual_control": {
     "p": 1e-7,
     "U": 1e-7
   }
   ```

3. Reduce timestep if Courant too high

### Mesh Quality Issues

**Run diagnostic:**
```bash
checkMesh -allTopology -allGeometry
```

**Key metrics:**
- maxNonOrtho: Should be <65°
- maxBoundarySkewness: Should be <8
- maxInternalSkewness: Should be <3

**If quality poor:**
1. Reduce surface refinement: `[1, 1]` instead of `[2, 3]`
2. Increase feature angle: `60°` instead of `30°`
3. Improve STL geometry (smoother surfaces)
4. Use `robust` mesh settings from base.py

---

## 📝 Example Configurations

### Example 1: Simple Laminar Flow

**Use case:** Basic steady flow, no turbulence

```json
{
  "physics": {
    "model": "laminar",
    "transport_properties": {"rho": 1060, "nu": 3.7736e-6}
  },
  "numerics": {"profile": "standard"},
  "mesh": {
    "cells_per_diameter": 12,
    "boundary_layers": {"enabled": false}
  },
  "boundary_conditions": {
    "inlet": {"type": "CONSTANT", "velocity": 0.5},
    "outlets": {"type": "ZEROGRADIENT"}
  },
  "simulation_control": {"end_time": 10, "writeInterval": 1}
}
```

### Example 2: RANS with Windkessel

**Use case:** Turbulent flow, physiological outlets

```json
{
  "physics": {
    "model": "RAS",
    "transport_properties": {"rho": 1060, "nu": 3.7736e-6},
    "turbulence_intensity": 0.05
  },
  "numerics": {"profile": "standard"},
  "mesh": {
    "cells_per_diameter": 15,
    "boundary_layers": {
      "enabled": true,
      "target_yplus": 1.0,
      "num_layers": 5,
      "expansion_ratio": 1.2
    }
  },
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "flow.csv",
      "data_type": "flowrate"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80,
        "tau": 1.8
      }
    }
  },
  "simulation_control": {
    "end_time": 5,
    "writeInterval": 0.1,
    "controlDict": {
      "functions": ["wallShearStress", "yPlus"]
    }
  }
}
```

### Example 3: Convergence Study / LES

**Use case:** Mesh independence verification or LES simulations

```json
{
  "numerics": {"profile": "precise"},
  "mesh": {
    "cells_per_diameter": 20,
    "boundary_layers": {
      "target_yplus": 0.5,
      "num_layers": 3,
      "expansion_ratio": 1.5
    }
  }
}
```

Run with: 12, 15, 18, 20 cells/diameter and compare results.

---

## 📚 Additional Resources

### Documentation Files

- **[config_full.json](config_full.json)** - Complete parameter reference
- **[README_CONFIG.md](README_CONFIG.md)** - Detailed configuration guide
- **[../TEST_SUITE_SUMMARY.md](../TEST_SUITE_SUMMARY.md)** - Test coverage report

### Source Code References

- **Config System**: `src/config/`
- **Y+ Estimator**: `src/aortacfd_lib/yplus_estimator.py`
- **Windkessel**: `src/aortacfd_lib/wk_setup.py`
- **Boundary Conditions**: `src/aortacfd_lib/boundary_condition_setup.py`
- **Mesh Setup**: `src/aortacfd_lib/mesh_setup.py`

### Numerics Profiles

- **robust**: `src/config/profiles/numerics/robust.py`
- **standard**: `src/config/profiles/numerics/standard.py`
- **precise**: `src/config/profiles/numerics/precise.py`

### Post-Processing

- **Module**: `src/aortacfd_lib/post_processing/`
- **Hemodynamics**: `src/aortacfd_lib/hemodynamics_postprocessor.py`
- **Visualization**: `src/aortacfd_lib/post_processor.py`

---

## 🎓 Best Practices

### 1. Start Simple
- Begin with `standard` profile
- Use medium resolution (12-15 cells/diameter)
- Enable basic boundary layers
- Add complexity incrementally

### 2. Validate Mesh
- Always run `checkMesh` before simulation
- Check layer quality (>80% success rate)
- Verify maxBoundarySkewness < 8
- Review mesh in ParaView

### 3. Monitor Simulation
- Watch residuals (should decrease)
- Check Courant number (should be stable)
- Verify mass conservation
- Monitor peak/average values

### 4. Post-Processing
- Run 3-5 cardiac cycles for pulsatile flow
- Time-average results over last cycle
- Extract WSS, pressure distributions
- Compare with literature values

**Using the workflow:**
```bash
# Run post-processing step on existing case
python run_patient.py BPM120 --case-dir output/BPM120/run_* --step post

# Or include in full workflow (post runs automatically)
python run_patient.py BPM120
```

### 5. Documentation
- Record all parameter choices
- Document convergence criteria
- Note any issues and solutions
- Keep simulation log files

---

## ⚖️ Profile Selection Decision Tree

```
Start
│
├─ Is mesh quality poor? (skewness >10, non-ortho >70)
│  └─ YES → Use "robust" profile
│
├─ LES simulation or need minimal numerical diffusion?
│  └─ YES → Use "precise" profile (requires fine mesh, ortho >70°)
│
└─ Everything else → Use "standard" profile ⭐ (recommended)
```

---

## 📞 Getting Help

### Check These First:
1. Mesh quality: `checkMesh -allTopology`
2. Residuals: Are they decreasing?
3. Mass balance: Inlet = Σ(outlets)?
4. Boundary layers: >80% success?

### Common Error Messages:

**"Maximum number of iterations exceeded"**
→ Reduce relaxation factors or max_co

**"Boundary layer collapse"**
→ Reduce num_layers or increase expansion_ratio

**"Negative initial temperature"**
→ Check Windkessel pressure values (mmHg not Pa)

**"Floating point exception"**
→ Usually divergence; use robust profile

---

**Last Updated**: October 31, 2025
**Version**: 2.0 (3-Profile System)
**Maintained by**: AortaCFD Development Team

For more help, see detailed guides in this directory or check test suite documentation.
