# AortaCFD: Patient-Specific Aortic Blood Flow Simulation

![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)
![Tests](https://img.shields.io/badge/tests-18%20passing-success.svg)
![Coverage](https://img.shields.io/badge/coverage-TBD-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![OpenFOAM](https://img.shields.io/badge/OpenFOAM-12-orange.svg)

**AortaCFD** is an end-to-end automated pipeline for patient-specific cardiovascular CFD simulations using OpenFOAM 12. It streamlines the complete workflow from geometry to results, featuring a modular architecture with composable configuration fragments, pre-configured simulation profiles (Laminar, RANS, LES), and advanced boundary conditions including 3-element Windkessel (3EWK) models with automatic parameter calculation.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Basic Commands](#basic-commands)
  - [Workflow Steps](#workflow-steps)
  - [Configuration](#configuration)
- [Boundary Conditions](#boundary-conditions)
- [Post-Processing](#post-processing)
- [Reconstruction & Performance](#reconstruction--performance)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/JieWangnk/AortaCFD-app.git
cd AortaCFD-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Install OpenFOAM 12
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key | apt-key add -"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt-get update && sudo apt-get install openfoam12
echo "source /opt/openfoam12/etc/bashrc" >> ~/.bashrc
source ~/.bashrc

# 3. Install Windkessel BC (for 3EWK outlets)
./scripts/install_windkessel_of12.sh

# 4. Run example simulation (automated quick-start)
./run_example.sh               # Complete demonstration with patient1

# OR run manually with different profiles:
python run_patient.py patient1 --quick                    # Fast (sim_laminar_coarse, 5-15 min)
python run_patient.py patient1                            # Medium quality (30-90 min)
python run_patient.py patient1 --profile sim_laminar_fine # High quality (2-4 hours)
python run_patient.py patient1 --profile sim_rans_medium  # RANS turbulence (2-3 hours)

# 5. View results
paraview output/patient1/run_*/openfoam/openfoam.foam
```

**File Structure:**
```
cases_input/patient1/          # Patient input data
├── config.json                # Simulation configuration
├── inlet.stl                  # Inlet geometry
├── outlet*.stl                # Outlet geometries (outlet1, outlet2, ...)
├── wall_aorta.stl             # Vessel wall
└── BPM75.csv                  # Flow data (optional, for time-varying inlet)

output/patient1/               # Results
└── run_YYYYMMDD_HHMMSS/
    ├── openfoam/              # OpenFOAM case
    │   ├── 0/                 # Initial/boundary conditions
    │   ├── constant/          # Mesh, physical properties
    │   ├── system/            # Solver dictionaries
    │   ├── logs/              # Simulation logs
    │   └── processor*/        # Decomposed parallel data (or time dirs if reconstructed)
    ├── images/                # Post-processing visualizations
    ├── results/               # Extracted results
    ├── logs/                  # Workflow logs
    └── summary.json           # Run metadata
```

---

## Features

### Core Capabilities
- ✅ **End-to-End Automation** - From geometry to results with single command
- ✅ **Composable Configuration** - Fragment-based architecture for mesh resolution, solver recipes, and turbulence models
- ✅ **Pre-configured Profiles** - 8 simulation profiles (Laminar/RANS/LES × Coarse/Medium/Fine)
- ✅ **Advanced Boundary Conditions** - 3-element Windkessel (3EWK) with automatic parameter calculation
- ✅ **Multiple Inlet Profiles** - Time-varying, constant, parabolic, Womersley
- ✅ **Automated Mesh Generation** - snappyHexMesh with boundary layers and quality control
- ✅ **Y+ Based Boundary Layers** 🆕 - Automatic first layer thickness calculation from target y+ value

### Workflow & Execution
- ✅ **Modular Architecture** - Task-based workflow system with step-by-step control
- ✅ **Parallel Execution** - Multi-core meshing and solver with smart processor allocation
- ✅ **Resume Support** - Continue from existing runs with `--resume` flag
- ✅ **Flexible Steps** - Run individual workflow steps (case/mesh/boundary/solver/reconstruct/post)
- ✅ **OpenFOAM 12 Native** - Uses `foamRun -solver incompressibleFluid`

### Analysis & Visualization
- ✅ **Post-Processing** - Automated ParaView visualization with decomposed/reconstructed case detection
- ✅ **Simulation Reports** - Automated documentation generation with profile metadata
- ✅ **Windkessel Analysis** - Automatic parameter calculation with multiple PWV methods
- ✅ **Comprehensive Testing** - Automated test suite with mesh resolution validation

---

## Installation

### Prerequisites
- Ubuntu 20.04+ or similar Linux
- Python 3.12
- OpenFOAM 12
- ParaView (optional, for visualization)

### Setup
```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 2. Install OpenFOAM 12 (see Quick Start)

# 3. Install Windkessel BC for 3EWK support
./scripts/install_windkessel_of12.sh
```

---

## Usage

### Basic Commands

```bash
# List available patients
python run_patient.py --list

# Run complete workflow (default: sim_laminar_medium profile)
python run_patient.py patient1

# Quick test run (uses sim_laminar_coarse profile)
python run_patient.py patient1 --quick

# Use specific simulation profile (overrides profile in config.json)
python run_patient.py patient1 --profile sim_rans_medium
python run_patient.py patient1 --profile sim_les_fine
# Note: --profile ONLY changes solver/mesh/numerics, ALL config.json settings are preserved!

# Resume from most recent run
python run_patient.py patient1 --resume

# Custom configuration file
python run_patient.py patient1 --config /path/to/config.json

# List available workflow steps
python run_patient.py --list-steps

# List available profiles
python -c "from src.patient_runner.core import PatientCaseRunner; PatientCaseRunner().display_profile_selection()"
```

### Workflow Steps

AortaCFD provides granular control over the simulation pipeline:

```bash
# Run specific workflow steps
python run_patient.py patient1 --step mesh              # Only meshing
python run_patient.py patient1 --step solver            # Only solver
python run_patient.py patient1 --step reconstruct       # Reconstruct decomposed case
python run_patient.py patient1 --step post              # Post-processing

# Multiple steps
python run_patient.py patient1 --step case --step mesh --step boundary
```

**Available Steps:**
1. **case** - Create case structure and configuration files
2. **mesh** - Generate mesh (blockMesh, surfaceFeatures, snappyHexMesh)
3. **boundary** - Setup boundary conditions and flow data
4. **solver** - Run CFD solver (pimpleFoam/foamRun)
5. **reconstruct** - Reconstruct parallel case from processor directories
6. **post** - Execute post-processing
7. **all** - Complete workflow (default)

### Configuration

AortaCFD uses a unified `config.json` format that combines case-specific settings with simulation profiles. The configuration system features:

- **Profile-based setup**: Use `--profile` flag to override default profiles
- **Fragment composition**: Mix and match mesh resolution, solver recipes, and turbulence models
- **Smart defaults**: Minimal config required - system provides sensible defaults
- **Override hierarchy**: CLI flags > config.json > profile defaults > base defaults

**Minimal config.json (RECOMMENDED for beginners):**

```json
{
  "case_info": {
    "patient_id": "patient1",
    "description": "Patient-specific aortic simulation"
  },
  "simulation_settings": {
    "solver_type": "laminar",
    "analysis_type": "medium"
  },
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "BPM75.csv"
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

**Profile Selection Methods:**

1. **Via config.json** (shown above): `simulation_settings.solver_type` + `analysis_type`
2. **Via CLI flag**: `--profile sim_rans_medium` (overrides profile selection only)
3. **Via quick flag**: `--quick` (uses `sim_laminar_coarse`)
4. **Auto-selection**: Omit both → defaults to `sim_laminar_medium`

**⚠️ Important:** The `--profile` flag ONLY changes profile-specific settings (solver type, mesh resolution, numerical schemes). **ALL your config.json settings are preserved** (physics, boundary conditions, computational resources, etc.). Your config.json always has the highest priority. See [examples/profile_override_example.md](examples/profile_override_example.md) for detailed explanation.

**Available Simulation Profiles:**

| Profile | Solver | Analysis Level | Mesh Resolution | Runtime | Use Case |
|---------|--------|----------------|-----------------|---------|----------|
| `sim_laminar_coarse` | Laminar | Coarse | 10 (priority) | 5-10 min | Quick checks, geometry validation |
| `sim_laminar_medium` | Laminar | Medium | 15 (priority) | 30-60 min | **Clinical analysis (DEFAULT)** |
| `sim_laminar_fine` | Laminar | Fine | 20 (priority) | 2-4 hours | High-resolution laminar studies |
| `sim_rans_coarse` | RANS k-ω SST | Coarse | 16 (priority) | 1-2 hours | Fast turbulence screening |
| `sim_rans_medium` | RANS k-ω SST | Medium | 18 (priority) | 2-3 hours | Accurate turbulence simulations |
| `sim_rans_fine` | RANS k-ω SST | Fine | 22 (priority) | 3-5 hours | Research-grade turbulence |
| `sim_les_medium` | LES WALE | Medium | 20 (priority) | 3-5 hours | Transitional flow LES |
| `sim_les_fine` | LES WALE | Fine | 25 (priority) | 5-7 hours | High-fidelity LES simulations |

**Note:** Mesh resolution uses priority-based refinement (higher = finer mesh). Each profile includes appropriate solver recipes (robust/balanced/aggressive) and numerical schemes.

**Advanced configuration (all options):**

```json
{
  "case_info": {
    "patient_id": "patient1",
    "description": "Patient-specific aortic simulation",
    "reference": "Publication reference (optional)"
  },
  "simulation_settings": {
    "solver_type": "rans",
    "analysis_type": "medium"
  },
  "physics": {
    "blood_density": 1060,
    "blood_viscosity": 0.004
  },
  "geometry": {
    "scale_factor": 0.001,
    "rotation": true,
    "target_normal": [0, 0, 1],
    "inlet_keywords_ordered": "inlet",
    "outlet_keywords_ordered": ["outlet1", "outlet2", "outlet3"],
    "wall_keywords_ordered": "wall_aorta"
  },
  "computational": {
    "parallel": true,
    "max_processors": 8
  },
  "mesh": {
    "SNAPPY_SETTINGS": {
      "parallel": true,
      "nProcessors": 8
    }
  },
  "run_settings": {
    "solution_type": "parallel",
    "subdomains": 8,
    "decomposition_method": "scotch"
  },
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "BPM75.csv",
      "data_type": "flowRate",
      "profile": "plug",
      "orientation": "out"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80,
        "venous_pressure": 0,
        "flow_split": 40,
        "flow_split_method": "murray",
        "pwv_method": "empirical",
        "tau": 1.8
      }
    },
    "walls": {
      "type": "no_slip"
    }
  },
  "simulation_control": {
    "number_of_cycles": 5,
    "end_time": "auto",
    "writeInterval": 0.01
  }
}
```

**Configuration Architecture:**

The system uses a layered configuration approach:
1. **Base config** ([src/config/base.py](src/config/base.py)) - Default OpenFOAM settings
2. **Profile config** ([src/config/profiles/](src/config/profiles/)) - Profile-specific settings
3. **Fragment composition** - Mesh resolution + solver recipe fragments
4. **Case config** (`config.json`) - Patient-specific overrides

Priority: `config.json` > Fragments > Profile > Base

**Configuration Examples:**

See the [examples/](examples/) directory for complete configuration examples:
- [config_minimal.json](examples/config_minimal.json) - Minimal required parameters (⭐ start here)
- [config_laminar_medium_example.json](examples/config_laminar_medium_example.json) - Laminar medium resolution example
- [config_rans_turbulence.json](examples/config_rans_turbulence.json) - RANS turbulence modeling example
- [config_les_fine_example.json](examples/config_les_fine_example.json) - LES fine resolution example
- [config_full_example.json](examples/config_full_example.json) - Complete parameter reference

Each example includes detailed inline comments and usage notes. See [examples/README.md](examples/README.md) for detailed documentation.

---

## Mesh Resolution Guide

### Overview

AortaCFD provides multiple methods to control mesh resolution, ranging from simple presets to advanced custom sizing. The system uses a **6-level priority hierarchy** that balances ease-of-use with flexibility.

### Quick Start: Use `resolution_level` (Recommended)

For most users, simply specify a resolution preset in your config:

```json
{
  "mesh": {
    "resolution_level": "medium"
  }
}
```

**Available Presets:**

| Preset | Cell Size | Expected Cells | Runtime | Use Case |
|--------|-----------|----------------|---------|----------|
| `coarse` / `draft` | 2.0 mm | ~100K-300K | 5-15 min | Quick validation, geometry checks |
| `medium` / `clinical` | 1.0 mm | ~500K-1.5M | 30-90 min | **Clinical analysis (DEFAULT)** |
| `fine` / `publication` | 0.5 mm | ~2M-5M | 2-4 hours | High-resolution studies |
| `ultra_fine` | 0.25 mm | ~10M+ | 6-12 hours | Mesh independence studies |

**Aliases:** You can use either technical names (`coarse`, `medium`, `fine`) or intuitive names (`draft`, `clinical`, `publication`).

### Resolution Control Methods (Priority Order)

The system checks these parameters in order and uses the **first one found**:

```
Priority 1: resolution_level        (RECOMMENDED - simple presets)
    ↓
Priority 2: target_cell_size_mm     (Direct specification in mm)
    ↓
Priority 3: blockmesh_resolution    (Cells across diameter)
    ↓
Priority 4: cells_per_diameter      (Same as #3, different naming)
    ↓
Priority 5: refinement_levels       (Legacy lookup table)
    ↓
Priority 6: Default fallback        (1.0mm if nothing specified)
```

**⚠️ Best Practice:** Set **only ONE** parameter to avoid confusion. The system will warn if multiple are detected.

### Method 1: resolution_level (Recommended)

**Simplest and most common method:**

```json
{
  "mesh": {
    "resolution_level": "fine"
  }
}
```

Maps directly to cell sizes defined in [src/aortacfd_lib/utils/mesh_constants.py](src/aortacfd_lib/utils/mesh_constants.py#L9-20).

**Advantages:**
- ✅ Simple and intuitive
- ✅ Well-tested presets
- ✅ Documented runtime estimates
- ✅ Consistent across cases

### Method 2: target_cell_size_mm

**For custom cell sizes not covered by presets:**

```json
{
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 0.8
    }
  }
}
```

**Use when:** You need a specific cell size (e.g., 0.8mm) between presets.

### Method 3: blockmesh_resolution

**Geometry-based sizing (cells across vessel diameter):**

```json
{
  "mesh": {
    "mesh_resolution": {
      "blockmesh_resolution": 15
    }
  }
}
```

Cell size = `2 × reference_radius / blockmesh_resolution`

**Example:** For a 25mm diameter vessel with `blockmesh_resolution: 15`:
- Cell size = 2 × 12.5mm / 15 = 1.67mm

**Requires:** Valid geometry with measurable vessel radius.

### Method 4: cells_per_diameter

**Alternative syntax for blockmesh_resolution:**

```json
{
  "mesh": {
    "mesh_resolution": {
      "cells_per_diameter": 20
    }
  }
}
```

Supports both scalar and dict formats:
```json
{
  "cells_per_diameter": {
    "branch": 20,
    "inlet": 15
  }
}
```

### Y+ Based Boundary Layer Control 🆕

For **RANS and LES** simulations, use automatic y+ based boundary layer sizing:

```json
{
  "mesh": {
    "resolution_level": "fine",

    "boundary_layers": {
      "target_yplus": 1.0,
      "estimation_method": "auto"
    },

    "SNAPPY_SETTINGS": {
      "addLayer": 5,
      "expansionRatio": 1.2,
      "relativeSizes": false
    }
  }
}
```

**How it works:**
1. System estimates wall shear stress from flow correlations
2. Calculates `finalLayerThickness = y+ × ν / u_τ` in absolute units (meters)
3. Automatically sets `relativeSizes = false` (required for absolute sizing)

**Target y+ values:**
- **RANS k-ω SST (low-Re):** y+ ≈ 1.0 (resolves viscous sublayer)
- **LES wall-resolved:** y+ ≈ 0.5-1.0 (DNS-like near-wall)
- **Wall functions:** y+ ≈ 30-100 (log-layer modeling)

**See:** [examples/YPLUS_CALCULATOR_GUIDE.md](examples/YPLUS_CALCULATOR_GUIDE.md) for complete documentation.

### Parallelization Settings

Mesh generation (snappyHexMesh) and solver use **separate** parallelization:

```json
{
  "mesh": {
    "SNAPPY_SETTINGS": {
      "parallel": true,
      "nProcessors": 8
    }
  },
  "computational": {
    "max_processors": 8
  },
  "run_settings": {
    "solution_type": "parallel",
    "subdomains": 8,
    "decomposition_method": "scotch"
  }
}
```

**Key distinction:**
- `mesh.SNAPPY_SETTINGS.nProcessors` → snappyHexMesh parallelization
- `run_settings.subdomains` → Solver parallelization (decomposePar)
- `computational.max_processors` → Global resource limit

### Parameter Reference

**Critical parameters in `SNAPPY_SETTINGS`:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `addLayer` | int | 5 | Number of boundary layers |
| `expansionRatio` | float | 1.2 | Layer growth ratio (1.1-1.3 typical) |
| `finalLayerThickness` | float | 0.3 | Relative (if `relativeSizes=true`) or absolute (meters) |
| `minThickness` | float | 0.1 | Minimum layer thickness (prevents collapse) |
| `relativeSizes` | bool | true | `true` = relative to cell size, `false` = absolute (meters) |
| `resolveFeatureAngle` | float | 30 | Minimum angle to resolve features (≥30° recommended) |

**⚠️ Important:** When using y+ calculator, `relativeSizes` **must be `false`** and `finalLayerThickness` is auto-calculated.

### Examples

**Example 1: Simple clinical case**
```json
{
  "mesh": {
    "resolution_level": "medium"
  }
}
```
Result: 1.0mm cells, ~500K-1.5M cells, 30-90 min runtime

**Example 2: RANS with y+ control**
```json
{
  "mesh": {
    "resolution_level": "fine",
    "boundary_layers": {
      "target_yplus": 1.0,
      "estimation_method": "auto"
    },
    "SNAPPY_SETTINGS": {
      "addLayer": 5,
      "expansionRatio": 1.2,
      "relativeSizes": false
    }
  }
}
```
Result: 0.5mm cells + auto-calculated boundary layers for y+=1.0

**Example 3: Custom high-resolution**
```json
{
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 0.3
    }
  }
}
```
Result: 0.3mm cells (between fine and ultra_fine)

### Troubleshooting

**Issue:** "Multiple mesh resolution parameters detected"
**Solution:** Set only ONE parameter (prefer `resolution_level`)

**Issue:** "nSurfaceLayers 0" in generated mesh
**Solution:** Use `addLayer` not `nSurfaceLayers` in config

**Issue:** Y+ much different than target
**Solution:** Check `relativeSizes = false` when using y+ calculator

**Issue:** Mesh too coarse/fine
**Solution:** Use next preset level or `target_cell_size_mm`

---

## Simulation Profiles & Architecture

### Profile System Overview

AortaCFD uses a **composable profile architecture** that separates concerns into orthogonal fragments:

1. **Spatial Resolution** - Mesh refinement priorities (coarse=10, medium=15, fine=20, etc.)
2. **Solver Recipe** - PIMPLE control (robust/balanced/aggressive)
3. **Turbulence Model** - Laminar, RANS k-ω SST, LES WALE

Each simulation profile (`sim_*`) is a pre-configured combination of these fragments, automatically merged at runtime.

### Profile Details

#### Laminar Profiles

**`sim_laminar_coarse`** - Quick Validation
- **Solver:** Laminar
- **Resolution:** Priority 10 (coarse)
- **Recipe:** Robust (stable, first-order)
- **Max CFL:** 0.5
- **Runtime:** 5-10 minutes
- **Use for:** Geometry checks, workflow testing, BC validation

**`sim_laminar_medium`** - Clinical Standard (DEFAULT)
- **Solver:** Laminar
- **Resolution:** Priority 15 (medium)
- **Recipe:** Balanced (second-order, 2 outer correctors)
- **Max CFL:** 0.8
- **Runtime:** 30-60 minutes
- **Use for:** Clinical decision support, routine analysis, healthy aorta flows (Re < 2300)

**`sim_laminar_fine`** - High Resolution
- **Solver:** Laminar
- **Resolution:** Priority 20 (fine)
- **Recipe:** Aggressive (pure second-order, 3 outer correctors)
- **Max CFL:** 1.0
- **Runtime:** 2-4 hours
- **Use for:** Publication-quality laminar studies, mesh independence studies

#### RANS Profiles (k-ω SST Turbulence)

**`sim_rans_coarse`** - Turbulence Screening
- **Solver:** RANS k-ω SST
- **Resolution:** Priority 16 (coarse+)
- **Recipe:** Robust
- **Max CFL:** 0.7
- **Runtime:** 1-2 hours
- **Use for:** Fast turbulence screening, exploratory studies

**`sim_rans_medium`** - Accurate Turbulence
- **Solver:** RANS k-ω SST
- **Resolution:** Priority 18 (medium+)
- **Recipe:** Balanced
- **Max CFL:** 0.8
- **Runtime:** 2-3 hours
- **Use for:** Stenotic flows, post-coarctation analysis, transitional Re (2300-4000)

**`sim_rans_fine`** - Research Grade
- **Solver:** RANS k-ω SST
- **Resolution:** Priority 22 (fine+)
- **Recipe:** Aggressive
- **Max CFL:** 1.0
- **Runtime:** 3-5 hours
- **Use for:** Publication turbulence studies, detailed WSS analysis
- **Variant:** `publication` (25 priority, aggressive recipe)

#### LES Profiles (WALE Subgrid Model)

**`sim_les_medium`** - Transitional LES
- **Solver:** LES WALE
- **Resolution:** Priority 20 (fine)
- **Recipe:** Balanced
- **Max CFL:** 0.5
- **Runtime:** 3-5 hours
- **Use for:** Transitional flow studies, vortex dynamics

**`sim_les_fine`** - High-Fidelity LES
- **Solver:** LES WALE
- **Resolution:** Priority 25 (ultra-fine)
- **Recipe:** Aggressive
- **Max CFL:** 0.5
- **Runtime:** 5-7 hours
- **Use for:** Research requiring temporal accuracy, unsteady flow structures
- **Requirements:** 32+ GB RAM, 10+ cardiac cycles for convergence

### Quick Selection Guide

| Application | Profile | Runtime | Notes |
|-------------|---------|---------|-------|
| Geometry check | `sim_laminar_coarse` | 5-10 min | Use `--quick` flag |
| Clinical analysis | `sim_laminar_medium` | 30-60 min | **DEFAULT** - Start here |
| Stenosis/CoA | `sim_rans_medium` | 2-3 hours | Turbulence modeling |
| Publication (laminar) | `sim_laminar_fine` | 2-4 hours | High resolution |
| Publication (turbulent) | `sim_rans_fine` | 3-5 hours | With variants |
| Vortex dynamics | `sim_les_fine` | 5-7 hours | Temporal accuracy |

**Decision tree:**
1. **Is there turbulence?** (stenosis, Re > 2300) → Use RANS
2. **Need unsteady structures?** → Use LES
3. **Otherwise** → Use Laminar
4. **Then choose resolution:** coarse (test), medium (clinical), fine (publication)

---

## Boundary Conditions

### Inlet Types

**1. TIMEVARYING** - Time series from CSV (default)
```json
{
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "BPM75.csv",
    "data_type": "flowRate",  // or "velocity"
    "profile": "plug"         // or "parabolic", "womersley"
  }
}
```

**2. CONSTANT** - Steady uniform velocity
```json
{
  "inlet": {
    "type": "CONSTANT",
    "velocity": 0.5          // m/s
    // OR
    "cardiac_output": 5.0    // L/min (auto-calculates velocity)
  }
}
```

**3. PARABOLIC** - Steady Poiseuille profile
```json
{
  "inlet": {
    "type": "PARABOLIC",
    "velocity": 1.0          // centerline velocity
  }
}
```

**4. WOMERSLEY** - Pulsatile analytic profile
```json
{
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "flow.csv",
    "profile": "womersley"
  }
}
```

### 3-Element Windkessel (3EWK) Outlets

**Methodology:**
1. MAP Calculation: MAP = DP + (SP-DP)/3
2. Flow Distribution: Murray's law (r³), area-based, or custom
3. Total Resistance: R_total = (MAP - P_v) / Q̄
4. Proximal Resistance: R1 = ρ·c/A (from PWV)
5. Distal Resistance: R2 = R_total - R1
6. Compliance: C = τ / R2

**Configuration:**
```json
{
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "systolic_pressure": 120,
      "diastolic_pressure": 80,
      "venous_pressure": 0,
      "flow_split": 40,           // % or ratio dict
      "flow_split_method": "murray",  // "murray", "area", "equal"
      "pwv_method": "empirical",
      "tau": 1.8
    }
  }
}
```

**Flow Split Methods:**
- **murray** - Murray's Law (radius³ proportional)
- **area** - Cross-sectional area proportional
- **equal** - Equal distribution
- **custom** - User-defined ratios (dict)

**Flow Split with Percentage:**
When `flow_split` is a number (e.g., 40):
- First N-1 outlets share 40% using specified method
- Last outlet gets remaining 60%

---

## Post-Processing

### Automated Visualization

Post-processing generates screenshots and animations automatically:

```bash
# Navigate to case directory
cd output/patient1/run_*/openfoam

# Generate visualizations (auto-detects Reconstructed/Decomposed)
pvbatch ../../../../src/aortacfd_lib/post_processor.py

# Time step options
pvbatch ../../../../src/aortacfd_lib/post_processor.py . last  # Last time step only
pvbatch ../../../../src/aortacfd_lib/post_processor.py . peak  # Peak systole (max velocity)
pvbatch ../../../../src/aortacfd_lib/post_processor.py . all   # All time steps (default)
```

### Output Structure

```
output/patient1/run_*/
├── openfoam/                  # OpenFOAM case files
│   ├── 0/                     # Initial conditions
│   ├── constant/              # Mesh, properties
│   ├── system/                # Control dictionaries
│   ├── 0.001/, 0.002/, ...   # Time directories (if reconstructed)
│   ├── processor0/, ...       # Processor dirs (if decomposed)
│   └── f.foam                 # ParaView file
└── images/                    # Post-processing outputs (NEW LOCATION)
    ├── Velocity_*.png
    ├── Pressure_*.png
    ├── WSS_*.png
    ├── Velocity.avi           # Animations (if all time steps)
    ├── Pressure.avi
    ├── WSS.avi
    └── postProcessing.log
```

### Auto-Detection

The post-processor automatically detects whether your case is:
- **Reconstructed** - Time directories exist (0.001/, 0.002/, etc.)
- **Decomposed** - Only processor directories exist (processor0/, processor1/, etc.)

---

## Mesh Convergence Studies

### Automated Grid Convergence Index (GCI) Analysis

AortaCFD includes a **fully automated mesh convergence study** mode for rigorous uncertainty quantification using Richardson extrapolation and GCI methodology.

**Features:**
- ✅ Generates 3 systematically refined meshes (coarse/medium/fine)
- ✅ Automatic solution mapping via `mapFields` between levels
- ✅ Richardson extrapolation for mesh-independent solution
- ✅ Grid Convergence Index (GCI) computation
- ✅ Publication-ready convergence report

**Quick Start:**
```bash
# Run complete convergence study (fully automated)
./run_convergence_study.sh patient1

# Custom refinement ratio (default: √2)
./run_convergence_study.sh patient1 --ratio 2.0

# Custom base resolution
./run_convergence_study.sh patient1 --base-cpd 12
```

**Output:**
```
output/mesh_convergence/<patient>_<timestamp>/
├── coarse/         # 10 cells/diameter
├── medium/         # 14 cells/diameter
├── fine/           # 20 cells/diameter
├── convergence_report.md      # Publication-ready report
└── convergence_data.json      # Raw numerical data
```

**Report includes:**
- Mesh statistics (cell count, representative spacing h)
- Convergence metrics (observed order p, GCI values)
- Richardson extrapolated "exact" values
- Recommendations (converged, acceptable, refinement needed)

**Example Report Output:**
| Quantity | Coarse | Medium | Fine | Extrapolated | GCI_fine | Status |
|----------|--------|--------|------|--------------|----------|--------|
| Pressure Drop | 12.458 Pa | 11.923 Pa | 11.745 Pa | 11.685 Pa | 1.8% | ✅ Converged |
| Avg WSS | 1.523 Pa | 1.487 Pa | 1.472 Pa | 1.465 Pa | 2.4% | ✅ Converged |

**Typical Runtime:** ~6 hours (8-core workstation, laminar)

See [docs/MESH_CONVERGENCE_GUIDE.md](docs/MESH_CONVERGENCE_GUIDE.md) for complete documentation, theory, and publication guidelines.

---

## Reconstruction & Performance

### Skip Reconstruction Feature

Parallel simulations can skip the blocking `reconstructPar` step for **21% faster workflows**:

**Enable in config:**
```json
{
  "run_settings": {
    "solution_type": "parallel",
    "subdomains": 4,
    "skip_reconstruction": true  // Skip blocking reconstruction
  }
}
```

**Benefits:**
- **Faster workflow**: Solver completes → Workflow finishes immediately
- **Disk efficient**: Decomposed cases use less space
- **Flexible**: Reconstruct only when needed
- **Compatible**: ParaView reads decomposed cases directly

**Usage:**

```bash
# 1. Run simulation (skips reconstruction)
python run_patient.py patient1
# Output: processor0/, processor1/, processor2/, processor3/

# 2. Post-process decomposed case (works directly)
cd output/patient1/run_*/openfoam
pvbatch ../../../../src/aortacfd_lib/post_processor.py . last

# 3. Reconstruct later if needed (for external tools)
python run_patient.py patient1 --step reconstruct
# OR: cd output/patient1/run_*/openfoam && reconstructPar
```

**Performance Comparison (Patient1 RANS Medium, 4 cores):**

| Configuration | Solver | Reconstruction | Total | Savings |
|--------------|--------|----------------|-------|---------|
| **skip_reconstruction=false** | 45 min | 12 min | **57 min** | - |
| **skip_reconstruction=true** | 45 min | 0 min | **45 min** | **21%** |

---

## Testing

AortaCFD includes automated tests for core functionality:

```bash
# Run all tests
./venv/bin/pytest tests/ -v

# Unit tests (mesh resolution, inlet mapping, etc.)
./venv/bin/pytest tests/unit/ -v

# Integration tests (complete workflow validation)
./venv/bin/pytest tests/integration/ -v

# With coverage report
./venv/bin/pytest --cov=src --cov-report=html
```

**Current Test Suite:**
- Mesh resolution parameter hierarchy (18 tests)
- Additional tests under development

---

## Project Structure

```
AortaCFD-app/
├── src/                       # Core application source
│   ├── aortacfd_lib/         # CFD computational library
│   │   ├── mesh_setup.py             # Mesh generation (blockMesh, snappyHexMesh)
│   │   ├── boundary_condition_setup.py  # BC file generation
│   │   ├── inlet_mapping.py          # Inlet profile mapping
│   │   ├── wk_setup.py               # Windkessel BC setup
│   │   ├── windkessel_analyzer.py    # Automatic WK parameter calculation
│   │   ├── post_processor.py         # ParaView post-processing
│   │   ├── simulation_reporter.py    # Report generation
│   │   ├── simulation_report_generator.py  # Report templates
│   │   └── utils/                    # Utilities (logger, validation, security)
│   ├── workflow/             # Task-based workflow system
│   │   ├── manager.py                # Workflow orchestrator (recipes)
│   │   ├── base_task.py              # Base task class
│   │   └── tasks/
│   │       ├── setup_tasks.py        # Setup tasks (case, mesh, BC, solver config)
│   │       └── execution_tasks.py    # Execution tasks (mesh, solver, post)
│   ├── config/               # Composable configuration system
│   │   ├── builder.py                # Config builder with merge logic
│   │   ├── base.py                   # Base OpenFOAM 12 config
│   │   └── profiles/                 # Simulation profiles
│   │       ├── profile_builder.py    # Fragment composition engine
│   │       ├── fragments/            # Reusable config fragments
│   │       │   ├── resolution.py     # Mesh resolution fragments
│   │       │   ├── solver_recipe.py  # PIMPLE control fragments
│   │       │   └── turbulence.py     # Turbulence model fragments
│   │       ├── sim_laminar_*.py      # Laminar profiles (coarse/medium/fine)
│   │       ├── sim_rans_*.py         # RANS k-ω SST profiles
│   │       └── sim_les_*.py          # LES WALE profiles
│   ├── patient_runner/       # CLI and patient case management
│   │   ├── cli.py                    # Command-line interface
│   │   ├── core.py                   # PatientCaseRunner (orchestration)
│   │   └── steps.py                  # Workflow step definitions
│   └── templates/            # Jinja2 templates for OpenFOAM dictionaries
├── cases_input/              # Patient input data
│   ├── patient1/             # Example: Healthy adult aorta
│   ├── patient2/             # Example: Complex geometry
│   └── BPM120/               # Example: Pediatric coarctation (published)
├── output/                   # Simulation results (timestamped runs)
├── tests/                    # Test suite
│   ├── unit/                 # Unit tests (mesh resolution, inlet mapping)
│   └── integration/          # Integration tests (full workflows)
├── scripts/                  # Utility scripts
│   └── install_windkessel_of12.sh  # WK BC installation
├── run_patient.py            # Main patient runner entry point
├── run_example.sh            # Automated example workflow
├── README.md                 # This file
├── CHANGELOG.md              # Version history
├── CITATION.cff              # Citation metadata
└── requirements.txt          # Python dependencies
```

**Key Architecture Components:**

1. **Composable Configuration** ([src/config/](src/config/))
   - Fragment-based system for mixing mesh resolution, solver recipes, turbulence
   - Profile catalog with 8 pre-configured profiles
   - Deep-merge priority system: CLI > Config > Fragments > Profile > Base

2. **Workflow System** ([src/workflow/](src/workflow/))
   - Task-based execution with recipes (setup:dict, run:mesh, run:solver, etc.)
   - Context passing between tasks
   - Clean separation of setup vs execution

3. **Patient Runner** ([src/patient_runner/](src/patient_runner/))
   - Case validation and configuration loading
   - Profile resolution (CLI, config, fallbacks)
   - Resume support and step-by-step execution

4. **CFD Library** ([src/aortacfd_lib/](src/aortacfd_lib/))
   - OpenFOAM 12 integration
   - Automatic Windkessel parameter calculation
   - Post-processing with case type detection

---

## Troubleshooting

### Common Issues

**1. "externally-managed-environment" error**
- Always use virtual environment: `python3 -m venv venv && source venv/bin/activate`
- Never use `--break-system-packages`

**2. Mesh quality issues**
```bash
cd output/patient1/run_*/openfoam
checkMesh
# Expected: non-orthogonality < 70°, skewness < 4
```

**3. No processor directories found**
- Case may already be reconstructed
- Check: `ls output/patient1/run_*/openfoam/`

**4. Post-processing fails**
- Ensure ParaView/pvbatch is installed
- Check `caseType='auto'` in post_processor.py

**5. Windkessel BC errors**
- Install custom BC: `./scripts/install_windkessel_of12.sh`
- Verify OpenFOAM 12 environment loaded

**6. Flow split ratios don't sum to 1.0**
- Use `flow_split_method` with percentage
- Or provide custom ratios dict summing to 1.0

### Validation

```bash
# Check mesh quality
cd output/patient1/run_*/openfoam
checkMesh

# Run CFD validation tests
./venv/bin/pytest test_cfd_validation.py -v -s

# Validate configuration
python -c "from src.aortacfd_lib.utils.validation import validate_config; validate_config('cases_input/patient1/config.json')"
```

---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

Report issues at: https://github.com/yourusername/AortaCFD-app/issues

---

## License

[MIT License](LICENSE)

---

## Citation

If you use AortaCFD in your research, please cite:

```bibtex
@software{aortacfd2025,
  title={AortaCFD: Patient-Specific Aortic Blood Flow Simulation},
  author={Your Name},
  year={2025},
  url={https://github.com/yourusername/AortaCFD-app}
}
```

---

## Contact

For questions or support:
- Email: jie.wang-2@manchester.ac.uk
- Issues: https://github.com/yourusername/AortaCFD-app/issues

---

## Acknowledgments

Built with:
- OpenFOAM 12 (OpenFOAM Foundation)
- ParaView (Kitware)
- Python 3.12
- pytest, numpy, trimesh, jinja2

---

**Last Updated:** 2025-10-20

---

## Key Updates (v2.0)

### Architecture Improvements
- **Composable Configuration System**: Fragment-based architecture for orthogonal mixing of mesh resolution, solver recipes, and turbulence models
- **8 Pre-configured Profiles**: Laminar/RANS/LES × Coarse/Medium/Fine with automatic parameter tuning
- **Smart Profile Resolution**: Multiple selection methods (CLI, config, auto-fallback) with helpful error messages
- **Priority-based Mesh Refinement**: Intuitive priority values (10-25) replace complex cell size calculations

### Workflow Enhancements
- **Resume Support**: `--resume` flag continues from most recent run directory
- **Flexible Step Execution**: Run individual workflow steps (case/mesh/boundary/solver/reconstruct/post)
- **Automatic Case Detection**: Post-processor detects decomposed vs reconstructed cases
- **Improved Logging**: Comprehensive logging with profile metadata and configuration tracking

### Configuration System
- **Unified config.json Format**: Single file for all case settings
- **Deep-merge Priority**: CLI flags > config.json > fragments > profile > base
- **Automatic WK Calculation**: Windkessel parameters computed from systolic/diastolic pressures
- **Profile Metadata**: Complete tracking of applied configurations for reproducibility

### Developer Experience
- **Clean Architecture**: Clear separation of concerns (config/workflow/runner/lib)
- **Comprehensive Testing**: 18+ unit tests for mesh resolution hierarchy
- **Better Error Messages**: Helpful guidance when profiles or steps fail
- **Profile Catalog Display**: Interactive profile selection helper
