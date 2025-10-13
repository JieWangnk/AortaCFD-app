# AortaCFD User Guide

Complete guide for running patient-specific aortic blood flow simulations with OpenFOAM 12.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Running Simulations](#running-simulations)
4. [Configuration](#configuration)
5. [Boundary Conditions](#boundary-conditions)
6. [Mesh Settings](#mesh-settings)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Run Your First Simulation

```bash
# 1. Activate environment
source venv/bin/activate

# 2. Run a quick test (~5 minutes)
python run_patient.py patient1

# 3. View results in ParaView
paraview output/patient1/run_*/openfoam/openfoam.foam
```

### File Structure

```
cases_input/patient1/          # Patient input data
├── config.json                # Simulation configuration
├── inlet.stl                  # Inlet geometry
├── outlet1.stl, outlet2.stl   # Outlet geometries
├── wall_aorta.stl             # Vessel wall
└── BPM75.csv                  # Flow data (optional)

output/patient1/               # Results
└── run_YYYYMMDD_HHMMSS/
    └── openfoam/              # Complete OpenFOAM case
```

---

## Installation

### Prerequisites

- Ubuntu 20.04+ or similar Linux
- Python 3.12
- OpenFOAM 12
- ParaView (optional, for visualization)

### Setup Steps

```bash
# 1. Clone repository
git clone https://github.com/yourusername/AortaCFD-app.git
cd AortaCFD-app

# 2. Install OpenFOAM 12
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key | apt-key add -"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt-get update
sudo apt-get install openfoam12

# Add to ~/.bashrc
echo "source /opt/openfoam12/etc/bashrc" >> ~/.bashrc
source ~/.bashrc

# 3. Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Install Windkessel BC (for 3EWK outlets)
./scripts/install_windkessel_of12.sh
```

---

## Running Simulations

### Basic Commands

```bash
# List available patients
python run_patient.py --list

# Run simulation
python run_patient.py patient1

# Use custom config
python run_patient.py patient1 --config my_config.json

# Quick test run (reduced iterations)
python run_patient.py patient1 --quick
```

### Analysis Types

| Type | Cell Size | Cells | Time | Use Case |
|------|-----------|-------|------|----------|
| `coarse` | 1.8 mm | ~1.5M | Fast | Testing, debugging |
| `medium` | 1.0 mm | ~3.5M | Moderate | Production, validation |
| `fine` | 0.6 mm | ~7M | Slow | High accuracy, research |

### Solver Types

| Type | Model | Best For | Speed |
|------|-------|----------|-------|
| `laminar` | None | Most aortic flows (Re < 2300) | Fast |
| `RANS` | k-ω SST | Turbulent regions | Medium |
| `LES` | WALE | Complex turbulence, research | Slow |

---

## Configuration

### Minimal Configuration

```json
{
  "case_name": "patient1_test",
  "simulation_settings": {
    "analysis_type": "coarse",
    "solver_type": "laminar"
  },
  "boundary_conditions": {
    "inlet": {
      "type": "CONSTANT",
      "velocity_magnitude": 0.5
    },
    "outlets": {
      "type": "ZEROGRADIENT"
    }
  },
  "simulation_control": {
    "end_time": 0.1,
    "write_interval": 0.01
  }
}
```

### Production Configuration

```json
{
  "case_name": "patient1_rans_medium",
  "simulation_settings": {
    "analysis_type": "medium",
    "solver_type": "RANS"
  },
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "BPM75.csv",
      "data_type": "flowRate",
      "profile": "womersley"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80,
        "flow_split_method": "murray"
      }
    }
  },
  "simulation_control": {
    "number_of_cycles": 3
  },
  "run_settings": {
    "solution_type": "parallel",
    "subdomains": 8
  }
}
```

---

## Boundary Conditions

### Inlet Types

#### 1. CONSTANT (Simple Testing)

```json
"inlet": {
  "type": "CONSTANT",
  "velocity_magnitude": 0.5
}
```

Or with cardiac output (L/min):

```json
"inlet": {
  "type": "CONSTANT",
  "cardiac_output": 5.0
}
```

#### 2. TIMEVARYING (Realistic Cardiac Flow)

```json
"inlet": {
  "type": "TIMEVARYING",
  "csv_file": "BPM75.csv",
  "data_type": "flowRate",
  "profile": "womersley"
}
```

CSV format (time in seconds, flow in m³/s):
```
time,flowRate
0.0,0.00015
0.01,0.00018
0.02,0.00020
```

#### 3. PARABOLIC (Laminar Validation)

```json
"inlet": {
  "type": "PARABOLIC",
  "velocity_magnitude": 0.5
}
```

### Outlet Types

#### 1. ZEROGRADIENT (Simple)

```json
"outlets": {
  "type": "ZEROGRADIENT"
}
```

#### 2. 3EWINDKESSEL (Physiological)

```json
"outlets": {
  "type": "3EWINDKESSEL",
  "windkessel_settings": {
    "systolic_pressure": 120,
    "diastolic_pressure": 80,
    "venous_pressure": 0,
    "flow_split_method": "murray",
    "pwv_method": "empirical",
    "tau": 1.8
  }
}
```

**Flow Split Methods:**
- `murray` - Murray's Law (r³) - Default
- `area` - Area-based distribution
- `equal` - Equal distribution

**Custom Flow Split:**
```json
"windkessel_settings": {
  "flow_split": {
    "outlet1": 0.40,
    "outlet2": 0.30,
    "outlet3": 0.20,
    "outlet4": 0.10
  }
}
```

**Percentage Split:**
```json
"windkessel_settings": {
  "flow_split": 40,
  "flow_split_method": "murray"
}
```
First N-1 outlets share 40% using Murray's Law, last outlet gets 60%.

---

## Mesh Settings

### Default Mesh Quality

```json
"mesh": {
  "mesh_resolution": {
    "target_cell_size_mm": 1.0
  },
  "SNAPPY_SETTINGS": {
    "nSolveIter": 300,
    "nSmoothPatch": 5,
    "tolerance": 1.0,
    "nRelaxIter": 5,
    "nFeatureSnapIter": 15,
    "implicitFeatureSnap": false,
    "explicitFeatureSnap": true,
    "multiRegionFeatureSnap": true
  }
}
```

### Boundary Layers

```json
"mesh": {
  "boundary_layers": {
    "n_surface_layers": 5,
    "expansion_ratio": 1.2,
    "final_layer_thickness": 0.0003,
    "min_thickness": 0.00001
  }
}
```

### Parallel Meshing

```json
"mesh": {
  "SNAPPY_SETTINGS": {
    "parallel": true,
    "nProcessors": 8
  }
}
```

---

## Testing

### Run Tests

```bash
# All tests (362 tests)
./venv/bin/pytest tests/ test_patient1_e2e.py test_multi_patient_e2e.py

# Unit tests only (302 tests)
./venv/bin/pytest tests/unit/ -v

# Integration tests (42 tests)
./venv/bin/pytest tests/integration/ -v

# End-to-end tests (18 tests)
./venv/bin/pytest test_patient1_e2e.py test_multi_patient_e2e.py -v

# With coverage
./venv/bin/pytest --cov=src --cov-report=html
```

### Validate Mesh Quality

```bash
# Check mesh in OpenFOAM case
cd output/patient1/run_*/openfoam
checkMesh
```

Expected output:
```
Mesh OK.
  Max non-orthogonality: < 70°
  Max skewness: < 4
  Max aspect ratio: < 100
```

---

## Troubleshooting

### Mesh Quality Issues

**Problem:** High non-orthogonality or skewness

**Solution:**
```json
"mesh": {
  "SNAPPY_SETTINGS": {
    "nSolveIter": 700,
    "tolerance": 3.0,
    "nSmoothPatch": 10
  }
}
```

### Solver Divergence

**Problem:** Simulation crashes with NaN or floating point error

**Solution 1: Reduce time step**
```json
"simulation_control": {
  "controlDict": {
    "deltaT": 1e-6,
    "maxDeltaT": 1e-4,
    "maxCo": 0.5
  }
}
```

**Solution 2: Use more robust schemes**
```json
"numerical_settings": {
  "relaxation_factors": {
    "p": 0.3,
    "U": 0.7
  }
}
```

### Slow Simulation

**Solution: Enable parallel execution**
```json
"run_settings": {
  "solution_type": "parallel",
  "subdomains": 8,
  "decomposition_method": "scotch"
}
```

### File Not Found Errors

**Problem:** Config or CSV files not found

**Solution:**
```bash
# Use full path
python run_patient.py patient1 --config cases_input/patient1/my_config.json

# Or put files in patient directory
cp my_config.json cases_input/patient1/
python run_patient.py patient1 --config my_config.json
```

### OpenFOAM Version Issues

**Problem:** Solver command not found

**Solution:**
```bash
# Ensure OpenFOAM 12 is sourced
source /opt/openfoam12/etc/bashrc

# Test solver
which foamRun
```

### Windkessel BC Not Working

**Problem:** Unknown boundary condition `modularWKPressure`

**Solution:**
```bash
# Install Windkessel BC
./scripts/install_windkessel_of12.sh

# Verify installation
ls $FOAM_USER_LIBBIN/libwindkesselConditions.so
```

---

## Advanced Usage

### Parallel Workflow

```bash
# Generate mesh in parallel
python run_patient.py patient1 --config config_parallel.json

# Monitor progress
tail -f output/patient1/run_*/openfoam/log.snappyHexMesh
tail -f output/patient1/run_*/openfoam/log.foamRun
```

### Post-Processing

```bash
# Enter OpenFOAM case directory
cd output/patient1/run_*/openfoam

# Calculate WSS
foamCalc wallShearStress

# Sample centerline data
postProcess -func sampleDict

# Visualize in ParaView
paraview openfoam.foam
```

---

## Configuration Reference

### Complete Config Structure

```json
{
  "case_name": "string",
  "simulation_settings": {
    "analysis_type": "coarse|medium|fine",
    "solver_type": "laminar|RANS|LES"
  },
  "physical_properties": {
    "density": 1060.0,
    "kinematic_viscosity": 3.3e-6
  },
  "boundary_conditions": {
    "inlet": { /* see Inlet Types */ },
    "outlets": { /* see Outlet Types */ }
  },
  "mesh": { /* see Mesh Settings */ },
  "simulation_control": {
    "end_time": 0.8,
    "write_interval": 0.01,
    "number_of_cycles": 3
  },
  "run_settings": {
    "solution_type": "serial|parallel",
    "subdomains": 8,
    "decomposition_method": "scotch|hierarchical"
  }
}
```

---

## Support

- **Documentation:** See [README.md](README.md) for project overview
- **Configuration:** See [CLAUDE.md](CLAUDE.md) for detailed implementation notes
- **Issues:** https://github.com/yourusername/AortaCFD-app/issues
- **Email:** jie.wang-2@manchester.ac.uk

---

**Version:** 1.2
**Updated:** 2025-10-13
**License:** MIT
