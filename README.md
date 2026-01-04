# AortaCFD: Patient-Specific Aortic Blood Flow Simulation

![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)
![Tests](https://img.shields.io/badge/tests-172%20passing-success.svg)
![Coverage](https://img.shields.io/badge/coverage-TBD-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![OpenFOAM](https://img.shields.io/badge/OpenFOAM-12-orange.svg)

**AortaCFD** is an end-to-end automated pipeline for patient-specific cardiovascular CFD simulations using OpenFOAM 12. It streamlines the complete workflow from geometry to results, featuring a simplified 3-profile numerics system (robust/standard/accurate), physics model selection (laminar/RANS/LES), and advanced boundary conditions including 3-element Windkessel (3EWK) models with automatic parameter calculation.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Basic Commands](#basic-commands)
  - [Workflow Steps](#workflow-steps)
  - [Configuration](#configuration)
- [Numerics Profiles](#numerics-profiles)
- [Boundary Conditions](#boundary-conditions)
- [Post-Processing](#post-processing)
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

# Install python3-venv if needed (Ubuntu/Debian)
sudo apt install python3.12-venv

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

# 4. List available patient cases
python run_patient.py --list

# 5. Run a simulation
python run_patient.py 0014_H_AO_COA                    # SimVascular pediatric case
python run_patient.py BPM120                            # Published pediatric case
python run_patient.py PAT002                            # Cape Town collaborator case

# 6. View results
paraview output/<patient_id>/run_*/openfoam/openfoam.foam
```

**Available Patient Cases:**
- `0014_H_AO_COA` - Pediatric aortic coarctation from SimVascular VMR
- `BPM120` - Published pediatric case (Wang et al.)
- `PAT002` - Adult aortic case from Cape Town collaborator

**File Structure:**
```
cases_input/<patient_id>/      # Patient input data
├── config.json                # Simulation configuration
├── inlet.stl                  # Inlet geometry
├── outlet*.stl                # Outlet geometries (outlet1, outlet2, ...)
├── wall_aorta.stl             # Vessel wall
└── flow_data.csv              # Flow data (optional, for time-varying inlet)

output/<patient_id>/           # Results
└── run_YYYYMMDD_HHMMSS/
    ├── openfoam/              # OpenFOAM case
    │   ├── 0/                 # Initial/boundary conditions
    │   ├── constant/          # Mesh, physical properties
    │   ├── system/            # Solver dictionaries
    │   └── logs/              # Simulation logs
    ├── results/               # Extracted results
    └── summary.json           # Run metadata
```

---

## Features

### Core Capabilities
- **End-to-End Automation** - From geometry to results with single command
- **3-Profile Numerics System** - Simple selection: `robust`, `standard`, or `accurate`
- **Physics Model Selection** - Laminar, RANS (k-ω SST), or LES (WALE)
- **Advanced Boundary Conditions** - 3-element Windkessel (3EWK) with automatic parameter calculation
- **Multiple Inlet Profiles** - Time-varying, constant, parabolic, Womersley, wall-distance
- **Automated Mesh Generation** - snappyHexMesh with boundary layers and quality control

### Workflow & Execution
- **Modular Architecture** - Task-based workflow system with step-by-step control
- **Parallel Execution** - Multi-core meshing and solver with smart processor allocation
- **Resume Support** - Continue from existing runs with `--resume` flag
- **Flexible Steps** - Run individual workflow steps (case/mesh/boundary/solver/reconstruct/post)
- **OpenFOAM 12 Native** - Uses `foamRun -solver incompressibleFluid`

### Analysis & Visualization
- **Post-Processing** - Automated ParaView visualization
- **Windkessel Analysis** - Automatic parameter calculation with Murray's law
- **Comprehensive Testing** - 172+ automated tests

---

## Installation

### Prerequisites
- Ubuntu 20.04+ or similar Linux
- Python 3.12
- OpenFOAM 12
- ParaView (optional, for visualization)

### Setup
```bash
# 0. Install python3-venv (required on Ubuntu/Debian)
sudo apt install python3.12-venv

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

# List available workflow steps
python run_patient.py --list-steps

# Run complete workflow (creates new timestamped run)
python run_patient.py BPM120

# Run with specific config file
python run_patient.py BPM120 --config config_mesh_fine.json

# Resume from most recent run
python run_patient.py BPM120 --resume
```

### Working with Existing Output Cases

A powerful feature of AortaCFD is the ability to run workflow steps on **existing output directories**. This is useful for:
- Re-running the solver after parameter changes
- Reconstructing parallel cases
- Updating boundary conditions without regenerating mesh
- Post-processing completed simulations

```bash
# Point directly to an existing output case using --update (preserves mesh!)
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653 --step solver

# Or use --case-dir for full control
python run_patient.py 0014_H_AO_COA --case-dir output/0014_H_AO_COA/testing_3M_laminar --step reconstruct

# Common workflow: update BCs and re-run solver on existing mesh
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653 --step boundary --step solver

# Reconstruct a parallel case that finished on HPC
python run_patient.py PAT002 --case-dir output/PAT002/run_20251218_142530 --step reconstruct

# Run post-processing on completed simulation
python run_patient.py BPM120 --case-dir output/BPM120/run_20251220_093653 --step post
```

**Key difference between `--update` and `--case-dir`:**
- `--update PATH`: Preserves mesh, regenerates boundary conditions and configs from current config.json
- `--case-dir PATH`: Uses case directory as-is, only runs specified steps

### Workflow Steps

AortaCFD provides granular control over the simulation pipeline:

```bash
# Run specific workflow steps (new run)
python run_patient.py BPM120 --step mesh              # Only meshing
python run_patient.py BPM120 --step solver            # Only solver
python run_patient.py BPM120 --step reconstruct       # Reconstruct decomposed case
python run_patient.py BPM120 --step post              # Post-processing

# Multiple steps in sequence
python run_patient.py BPM120 --step case --step mesh --step boundary

# Combine with --output to work on existing case
python run_patient.py BPM120 --output output/BPM120/run_20251220_093653 --step boundary --step solver
```

**Available Steps:**
| Step | Description | When to Use |
|------|-------------|-------------|
| **case** | Create case structure and configuration files | New simulation setup |
| **mesh** | Generate mesh (blockMesh, surfaceFeatures, snappyHexMesh) | Mesh generation/regeneration |
| **boundary** | Setup boundary conditions and flow data | Update BCs without re-meshing |
| **regenerate-numerics** | Regenerate fvSchemes/fvSolution with mesh-adaptive adjustments | After mesh quality check |
| **solver** | Run CFD solver (foamRun) | Run/continue simulation |
| **reconstruct** | Reconstruct parallel case from processor directories | Post-HPC processing |
| **post** | Execute post-processing | Generate results/visualizations |
| **all** | Complete workflow (default) | Fresh simulation |

### Common Use Cases

**1. Fresh simulation from scratch:**
```bash
python run_patient.py BPM120
```

**2. Test different mesh resolutions:**
```bash
python run_patient.py BPM120 --config config_mesh_coarse.json
python run_patient.py BPM120 --config config_mesh_fine.json
```

**3. Re-run solver after editing fvSolution or boundary conditions:**
```bash
# Edit the files in output/BPM120/run_*/openfoam/system/ or 0/
python run_patient.py BPM120 --case-dir output/BPM120/run_20251220_093653 --step solver
```

**4. Reconstruct HPC results locally:**
```bash
# After copying results from HPC
python run_patient.py BPM120 --case-dir output/BPM120/hpc_run --step reconstruct --step post
```

**5. Update Windkessel parameters and re-run:**
```bash
# Edit 0/p to change R, C, Z values, then:
python run_patient.py BPM120 --case-dir output/BPM120/run_20251220_093653 --step solver
```

**6. Continue from last saved timestep:**
```bash
# Modify controlDict to set startFrom latestTime, then:
python run_patient.py BPM120 --case-dir output/BPM120/run_20251220_093653 --step solver
```

**7. Generate mesh only (for manual solver runs on HPC):**
```bash
python run_patient.py BPM120 --step case --step mesh --step boundary
# Then copy output/BPM120/run_*/openfoam to HPC
```

**8. Update case with new config but keep existing mesh:**
```bash
# After modifying config.json (e.g., changed BC settings):
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653
# This regenerates 0/, system/ but preserves constant/polyMesh
```

**9. Quick mesh test with coarse settings:**
```bash
python run_patient.py BPM120 --quick --step case --step mesh
# Creates coarse mesh for geometry validation
```

**10. Run with comma-separated steps (alternative syntax):**
```bash
python run_patient.py BPM120 --steps case,mesh,boundary
# Equivalent to: --step case --step mesh --step boundary
```

### Configuration

AortaCFD uses a unified `config.json` format. The configuration system features:

- **3-Profile Numerics**: Select `robust`, `standard`, or `accurate`
- **Physics Model**: Choose `laminar`, `rans`, or `les`
- **Smart Defaults**: Minimal config required - system provides sensible defaults

**Minimal config.json:**

```json
{
  "case_info": {
    "patient_id": "my_patient",
    "description": "Patient-specific aortic simulation"
  },
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
    "cells_per_diameter": 15
  },
  "geometry": {
    "inlet_keywords_ordered": "inlet",
    "outlet_keywords_ordered": ["outlet1", "outlet2"],
    "wall_keywords_ordered": "wall_aorta",
    "scale_factor": 0.001
  },
  "boundary_conditions": {
    "inlet": {
      "type": "CONSTANT",
      "cardiac_output": 5.0,
      "profile": "parabolic"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80
      }
    },
    "walls": {
      "type": "no_slip"
    }
  },
  "simulation_control": {
    "end_time": 1.0,
    "writeInterval": 0.1
  },
  "run_settings": {
    "solution_type": "parallel",
    "subdomains": 8
  }
}
```

**Configuration Examples:**

See the [examples/](examples/) directory for complete configuration examples:
- [config_minimal.json](examples/config_minimal.json) - Bare minimum required parameters
- [config_standard.json](examples/config_standard.json) - Recommended clinical configuration
- [config_full.json](examples/config_full.json) - Complete parameter reference with all options

---

## Numerics Profiles

AortaCFD uses a simplified **3-profile numerics system** that works with ALL physics models (laminar, RANS, LES):

### Profile Overview

| Profile | Order | Stability | Use Case |
|---------|-------|-----------|----------|
| **robust** | 1st | Maximum | Debugging, poor meshes, initial testing |
| **standard** | 2nd | Good | Production runs, clinical studies (DEFAULT) |
| **accurate** | 2nd | Good* | Convergence studies, validation, LES |

*Requires good mesh quality (orthogonality > 70°, skewness < 2)

### Profile Details

**`robust`** - Maximum Stability
- Time: Euler (1st order)
- Convection: Gauss upwind (1st order, bounded)
- Use when: Debugging, poor mesh quality, initial testing
- Trade-off: Highly diffusive (damps gradients)

**`standard`** - Balanced (RECOMMENDED)
- Time: backward (2nd order implicit)
- Convection: Gauss linearUpwind (2nd order, bounded)
- Use when: Production runs, clinical studies, most RANS
- Trade-off: Good accuracy with stability

**`accurate`** - Low Diffusion
- Time: CrankNicolson 0.9 (2nd order)
- Convection: Gauss LUST (75% central + 25% upwind)
- Use when: Mesh independence studies, validation, LES
- Requirements: Good mesh quality, ~2-3x longer runtime

### Physics Models

Combine any numerics profile with any physics model:

```json
{
  "physics": {
    "model": "laminar"    // or "rans" or "les"
  },
  "numerics": {
    "profile": "standard" // or "robust" or "accurate"
  }
}
```

| Physics Model | Description | Typical Use |
|--------------|-------------|-------------|
| `laminar` | No turbulence model | Re < 2300, healthy aorta |
| `rans` | k-ω SST turbulence | Stenosis, Re > 2300 |
| `les` | WALE subgrid model | High-fidelity unsteady flows |

---

## Mesh Resolution Guide

### Recommended: `cells_per_diameter`

```json
{
  "mesh": {
    "cells_per_diameter": 15,
    "boundary_layers": {
      "enabled": true,
      "num_layers": 5,
      "expansion_ratio": 1.2,
      "final_layer_thickness": 0.3
    }
  }
}
```

**Resolution Guidelines:**

| Category | cells/D | Typical Elements | Use Case |
|----------|---------|------------------|----------|
| **Coarse** | 10-12 | 200k-500k | Initial exploration, geometry checks |
| **Standard** | 15-20 | 500k-2M | **Production simulations (RECOMMENDED)** |
| **Fine** | 25-30 | 2M-5M | Mesh independence studies, publications |

---

## Boundary Conditions

### Inlet Types

**1. CONSTANT** - Steady uniform or parabolic flow
```json
{
  "inlet": {
    "type": "CONSTANT",
    "cardiac_output": 5.0,
    "profile": "parabolic"
  }
}
```

**2. TIMEVARYING** - Time series from CSV
```json
{
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "flow_data.csv",
    "data_type": "flowrate",
    "profile": "parabolic"
  }
}
```

**Profile Options:** `plug`, `parabolic`, `womersley`, `wall_distance`, `elliptical`

### 3-Element Windkessel (3EWK) Outlets

```json
{
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "systolic_pressure": 120,
      "diastolic_pressure": 80,
      "venous_pressure": 0,
      "methodology": "murray_law_automatic",
      "tau": 1.0,

      "enable_stabilization": true,
      "stabilization_type": "simple",
      "beta": 0.5,
      "damping_factor": 1.0
    }
  }
}
```

**Automatic Parameter Calculation:**
1. MAP = DP + (SP-DP)/3
2. Flow Distribution: Murray's law (r³)
3. Total Resistance: R_total = (MAP - P_v) / Q̄
4. Proximal Resistance: R1 = ρ·c/A (from PWV)
5. Distal Resistance: R2 = R_total - R1
6. Compliance: C = τ / R2

### Backflow Stabilization

For pulsatile simulations with Windkessel BCs, backflow stabilization prevents divergence during diastole. Three methods are available:

| Method | Formula | Default β | Robustness | Notes |
|--------|---------|-----------|------------|-------|
| `simple` | `damping = beta` | 0.9 | **Highest** | Uses only beta, ignores dampingFactor |
| `fluxBased` | `damping = beta × dampingFactor` | 0.7 | Medium | FVM-consistent, uses phi field |
| `traction` | `damping = beta × dampingFactor` | 0.3 | Medium | Physics-based (Moghadam 2011) |

**Effective damping:** `V_out = (1 - damping) × V_backflow`

**Recommendations:**
- **Standard cases:** `simple` with `beta=0.5` (50% backflow reduction)
- **Challenging geometries:** `simple` with `beta=1.0` (full backflow suppression)
- **Research/validation:** `traction` with `beta=0.5`, `damping_factor=1.0`

**Example for difficult cases (50% flow split, complex geometry):**
```json
{
  "enable_stabilization": true,
  "stabilization_type": "simple",
  "beta": 1.0
}
```

---

## Post-Processing

### Automated Visualization

```bash
# Navigate to case directory
cd output/BPM120/run_*/openfoam

# View in ParaView
paraview openfoam.foam
```

### Output Structure

```
output/<patient_id>/run_*/
├── openfoam/                  # OpenFOAM case files
│   ├── 0/                     # Initial conditions
│   ├── constant/              # Mesh, properties
│   ├── system/                # Control dictionaries
│   ├── processor*/            # Parallel decomposition
│   └── openfoam.foam          # ParaView file
├── results/                   # Extracted results
└── summary.json               # Run metadata
```

---

## Testing

AortaCFD includes 172+ automated tests:

```bash
# Run all tests
./venv/bin/pytest tests/ -v

# With coverage report
./venv/bin/pytest tests/ --cov=src --cov-report=html
```

**Test Coverage:**
- Configuration system and profile loading
- Boundary condition setup (inlet/outlet/walls)
- Windkessel parameter calculations
- Murray's law flow distribution
- Wall distance profile analysis
- Y+ estimation
- Mesh resolution hierarchy

---

## Project Structure

```
AortaCFD-app/
├── src/                       # Core application source
│   ├── aortacfd_lib/         # CFD computational library
│   │   ├── mesh_setup.py             # Mesh generation
│   │   ├── boundary_condition_setup.py  # BC file generation
│   │   ├── inlet_mapping.py          # Inlet profile mapping
│   │   ├── wk_setup.py               # Windkessel BC setup
│   │   └── utils/                    # Utilities
│   ├── workflow/             # Task-based workflow system
│   │   ├── manager.py                # Workflow orchestrator
│   │   └── tasks/                    # Setup and execution tasks
│   ├── config/               # Configuration system
│   │   ├── builder.py                # Config builder
│   │   ├── base.py                   # Base OpenFOAM 12 config
│   │   ├── numerics_builder.py       # Numerics profile builder
│   │   └── profiles/numerics/        # 3 numerics profiles
│   │       ├── robust.py             # Maximum stability
│   │       ├── standard.py           # Balanced (default)
│   │       └── accurate.py           # Low diffusion
│   ├── patient_runner/       # CLI and patient case management
│   │   ├── cli.py                    # Command-line interface
│   │   ├── core.py                   # PatientCaseRunner
│   │   └── steps.py                  # Workflow step definitions
│   └── templates/            # Jinja2 templates for OpenFOAM
├── cases_input/              # Patient input data
│   ├── 0014_H_AO_COA/        # SimVascular pediatric case
│   ├── BPM120/               # Published pediatric case
│   └── PAT002/               # Cape Town collaborator case
├── output/                   # Simulation results
├── tests/                    # Test suite (172+ tests)
├── examples/                 # Configuration examples
│   ├── config_minimal.json   # Bare minimum config
│   ├── config_standard.json  # Recommended config
│   └── config_full.json      # Complete reference
├── docs/                     # Documentation
├── scripts/                  # Utility scripts
├── run_patient.py            # Main entry point
├── README.md                 # This file
└── requirements.txt          # Python dependencies
```

---

## Troubleshooting

### Common Issues

**1. "externally-managed-environment" error**
- Always use virtual environment: `python3 -m venv venv && source venv/bin/activate`

**2. Mesh quality issues**
```bash
cd output/<patient_id>/run_*/openfoam
checkMesh
# Expected: non-orthogonality < 70°, skewness < 4
```

**3. Divergence or instability**
- Use `"profile": "robust"` in numerics
- Reduce `cells_per_diameter` for initial testing
- Check mesh quality with `checkMesh`

**4. Windkessel BC errors**
- Install custom BC: `./scripts/install_windkessel_of12.sh`
- Verify OpenFOAM 12 environment loaded

**5. Missing config.json**
- Use `--config` to specify alternate config file
- Check for `config*.json` files in patient directory

---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

Report issues at: https://github.com/JieWangnk/AortaCFD-app/issues

---

## License

[MIT License](LICENSE)

---

## Citation

If you use AortaCFD in your research, please cite:

```bibtex
@software{aortacfd2025,
  title={AortaCFD: Patient-Specific Aortic Blood Flow Simulation},
  author={Wang, Jie},
  year={2025},
  url={https://github.com/JieWangnk/AortaCFD-app}
}
```

---

## Contact

For questions or support:
- Email: jie.wang-2@manchester.ac.uk
- Issues: https://github.com/JieWangnk/AortaCFD-app/issues

---

## Acknowledgments

**Technical Contributors:**
- **Jie Wang** - OpenFOAM technical advice and critical revision

**Built with:**
- OpenFOAM 12 (OpenFOAM Foundation)
- ParaView (Kitware)
- Python 3.12
- pytest, numpy, trimesh, jinja2

---

**Last Updated:** 2025-12-22
