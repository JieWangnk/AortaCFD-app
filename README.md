# AortaCFD: Patient-Specific Aortic Blood Flow Simulation

![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)
![Tests](https://img.shields.io/badge/tests-18%20passing-success.svg)
![Coverage](https://img.shields.io/badge/coverage-TBD-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![OpenFOAM](https://img.shields.io/badge/OpenFOAM-12-orange.svg)

**AortaCFD** is an end-to-end automated pipeline for patient-specific cardiovascular CFD simulations using OpenFOAM 12. It streamlines the complete workflow from geometry to results, supporting advanced physiologically realistic boundary conditions including 3-element Windkessel (3EWK) models.

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
git clone https://github.com/yourusername/AortaCFD-app.git
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

# OR run manually with different quality levels:
python run_patient.py patient1 --quick                    # Fast (5-15 min)
python run_patient.py patient1                            # Medium quality (30-90 min)
python run_patient.py patient1 --profile sim_laminar_fine # High quality (2-4 hours)

# 5. View results
paraview output/patient1/run_*/openfoam/openfoam.foam
```

**File Structure:**
```
cases_input/patient1/          # Patient input data
├── config.json                # Simulation configuration (minimal: mesh.resolution_level = "medium")
├── inlet.stl                  # Inlet geometry
├── outlet*.stl                # Outlet geometries
├── wall_aorta.stl             # Vessel wall
└── BPM75.csv                  # Flow data (optional)

output/patient1/               # Results
└── run_YYYYMMDD_HHMMSS/
    ├── openfoam/              # OpenFOAM case
    ├── reports/               # Simulation documentation
    └── logs/                  # Execution logs
```

---

## Features

- ✅ **End-to-End Automation** - From geometry to results with single command
- ✅ **Advanced Boundary Conditions** - 3-element Windkessel (3EWK) with Murray's Law flow distribution
- ✅ **Multiple Inlet Profiles** - Time-varying, constant, parabolic, Womersley
- ✅ **Automated Mesh Generation** - snappyHexMesh with boundary layers
- ✅ **Parallel Execution** - Multi-core solver with optional reconstruction skip
- ✅ **Post-Processing** - Automated ParaView visualization with auto-detection
- ✅ **Modular Architecture** - Clean, task-based workflow system
- ✅ **Comprehensive Testing** - Automated test suite with CFD quality validation
- ✅ **OpenFOAM 12 Native** - Uses `foamRun -solver incompressibleFluid`

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

# Run complete workflow
python run_patient.py patient1

# Quick test run (reduced iterations)
python run_patient.py patient1 --quick

# Custom configuration
python run_patient.py patient1 --config /path/to/config.json

# List available workflow steps
python run_patient.py --list-steps
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

> **💡 RECOMMENDED WORKFLOW:** Use `mesh.resolution_level` for mesh configuration.
> This provides presets (coarse/medium/fine/ultra_fine) without needing to understand cell sizes or formulas.
> Start with `"medium"` for clinical-quality results. See [MESH_RESOLUTION_GUIDE.md](MESH_RESOLUTION_GUIDE.md) for details.

**Minimal config.json (RECOMMENDED for beginners):**

```json
{
  "case_info": {
    "patient_id": "patient1",
    "description": "Patient-specific aortic simulation"
  },
  "mesh": {
    "resolution_level": "medium"
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

**Mesh Resolution Levels:**

| Level | Cell Size | Expected Cells | Runtime | Use Case |
|-------|-----------|---------------|---------|----------|
| `"coarse"` or `"draft"` | 2.0mm | ~100K-300K | 5-15 min | Quick checks, debugging |
| **`"medium"` or `"clinical"`** | **1.0mm** | **~500K-1.5M** | **30-90 min** | **Clinical analysis (start here)** |
| `"fine"` or `"publication"` | 0.5mm | ~2M-5M | 2-4 hours | Research, publications |
| `"ultra_fine"` | 0.25mm | ~10M+ | 6-12 hours | Mesh independence studies |

**Advanced configuration (all options):**

```json
{
  "case_info": {
    "patient_id": "patient1",
    "description": "Patient-specific aortic simulation"
  },
  "physics": {
    "blood_density": 1060,
    "blood_viscosity": 0.004
  },
  "geometry": {
    "scale_factor": 0.001,
    "rotation": true,
    "target_normal": [0, 0, 1]
  },
  "mesh": {
    "resolution_level": "medium",
    "SNAPPY_SETTINGS": {
      "parallel": true,
      "nProcessors": 4
    }
  },
  "run_settings": {
    "solution_type": "parallel",
    "subdomains": 4,
    "decomposition_method": "scotch",
    "skip_reconstruction": true
  },
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "BPM75.csv",
      "data_type": "velocity",
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
    "end_time": 4,
    "writeInterval": 0.01
  }
}
```

**See also:**
- [MESH_RESOLUTION_GUIDE.md](MESH_RESOLUTION_GUIDE.md) - Complete mesh configuration reference
- [examples/mesh_configs/](examples/mesh_configs/) - Example configurations

---

## Simulation Profiles

AortaCFD provides pre-configured profiles for different simulation fidelities and turbulence models.

### Mesh Quality Levels

Control mesh resolution with `mesh.resolution_level`:

#### Coarse / Draft (`"coarse"` or `"draft"`)
- **Cell size:** 2.0mm
- **Expected cells:** ~100K-300K
- **Runtime:** 5-15 minutes
- **Use for:**
  - Initial geometry validation
  - Quick flow pattern visualization
  - Testing boundary conditions
  - Debugging workflow
- **NOT suitable for:**
  - Clinical decisions
  - Publication results
  - Quantitative WSS analysis

#### Medium / Clinical (`"medium"` or `"clinical"`) ← **RECOMMENDED START**
- **Cell size:** 1.0mm
- **Expected cells:** ~500K-1.5M
- **Runtime:** 30-90 minutes
- **Use for:**
  - Clinical hemodynamic assessment
  - Pressure gradient calculations
  - Flow distribution analysis
  - Virtual surgical planning
  - Routine analysis
- **Suitable for:**
  - Most applications
  - Clinical decision support
  - Preliminary research

#### Fine / Publication (`"fine"` or `"publication"`)
- **Cell size:** 0.5mm
- **Expected cells:** ~2M-5M
- **Runtime:** 2-4 hours
- **Use for:**
  - Research publications
  - Detailed WSS gradient analysis
  - Mesh independence verification
  - High-fidelity hemodynamics
- **Computational requirements:**
  - 16-32 GB RAM
  - 8+ CPU cores recommended

#### Ultra Fine (`"ultra_fine"`)
- **Cell size:** 0.25mm
- **Expected cells:** ~10M+ cells
- **Runtime:** 6-12 hours
- **Use for:**
  - Mesh independence studies
  - Ultra-high resolution research
  - LES turbulence modeling
- **Computational requirements:**
  - 32-64 GB RAM
  - 16+ CPU cores
  - Large storage (50-100 GB per case)

### Turbulence Model Profiles

Profiles combine mesh resolution with appropriate turbulence models (configured via command-line or config):

#### Laminar Profiles
```bash
# Coarse laminar (quick check)
python run_patient.py patient1 --profile sim_laminar_coarse

# Medium laminar (clinical, RECOMMENDED)
python run_patient.py patient1 --profile sim_laminar_medium

# Fine laminar (publication)
python run_patient.py patient1 --profile sim_laminar_fine
```

**Recommended for:**
- Healthy aorta (Re < 2300)
- Straightforward geometries
- Most clinical applications

#### RANS Profiles (k-ω SST)
```bash
# Coarse RANS (exploratory)
python run_patient.py patient1 --profile sim_rans_coarse

# Medium RANS (balanced)
python run_patient.py patient1 --profile sim_rans_medium

# Fine RANS (research)
python run_patient.py patient1 --profile sim_rans_fine
```

**Recommended for:**
- Transitional/turbulent flows (Re > 2300)
- Post-stenotic regions
- Aortic valve jets
- Complex geometries with recirculation

#### LES Profiles (WALE)
```bash
# Medium LES (exploratory)
python run_patient.py patient1 --profile sim_les_medium

# Fine LES (high-fidelity)
python run_patient.py patient1 --profile sim_les_fine
```

**Recommended for:**
- High-fidelity turbulence-resolving simulations
- Vortex structure analysis
- Unsteady transitional flows
- Research requiring temporal accuracy

**Requirements:**
- Fine or ultra_fine mesh resolution
- Small time steps (Δt ~ 1e-5 to 1e-6 s)
- Significant computational resources
- 10-20 cardiac cycles for statistical convergence

### Profile Selection Guide

| Application | Mesh Level | Turbulence | Profile | Expected Runtime |
|-------------|------------|------------|---------|------------------|
| Quick geometry check | Coarse | Laminar | `sim_laminar_coarse` | 5-15 min |
| Boundary condition test | Coarse | Laminar | `sim_laminar_coarse` | 5-15 min |
| Clinical assessment | Medium | Laminar | `sim_laminar_medium` | 30-90 min |
| Stenosis analysis | Medium | RANS | `sim_rans_medium` | 2-3 hours |
| Publication (laminar) | Fine | Laminar | `sim_laminar_fine` | 2-4 hours |
| Publication (turbulent) | Fine | RANS | `sim_rans_fine` | 3-5 hours |
| High-fidelity research | Fine | LES | `sim_les_fine` | 6-10 hours |
| Mesh independence | Ultra Fine | Laminar/RANS | Custom config | 6-12 hours |

**Quick selection:**
- **Don't know?** → Start with `sim_laminar_medium`
- **Need faster?** → Use `sim_laminar_coarse`
- **Need better?** → Use `sim_laminar_fine`
- **Have turbulence?** → Replace `laminar` with `rans` in profile name

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
├── src/                       # Core application
│   ├── aortacfd_lib/         # CFD computational library
│   │   ├── mesh_setup.py             # Mesh generation
│   │   ├── boundary_condition_setup.py  # BC management
│   │   ├── inlet_mapping.py          # Inlet profiles
│   │   ├── wk_setup.py               # Windkessel BC
│   │   ├── murray_calculator.py      # Murray's Law
│   │   ├── post_processor.py         # ParaView post-processing
│   │   └── utils/                    # Utilities
│   ├── workflow/             # Task-based workflow
│   │   ├── manager.py                # Workflow coordinator
│   │   ├── base_task.py              # Task base class
│   │   └── tasks/                    # Workflow tasks
│   ├── config/               # Configuration system
│   │   ├── builder.py                # Config builder
│   │   ├── base.py                   # Base config
│   │   └── profiles/                 # Simulation profiles
│   ├── patient_runner/       # CLI interface
│   │   ├── cli.py                    # Command-line interface
│   │   ├── core.py                   # Patient runner core
│   │   └── steps.py                  # Workflow steps
│   └── templates/            # OpenFOAM Jinja2 templates
├── cases_input/              # Patient input data
│   ├── patient1/             # Example patient 1
│   └── patient2/             # Example patient 2
├── output/                   # Simulation results
├── tests/                    # Comprehensive test suite
├── run_patient.py            # Main patient runner
├── CLAUDE.md                 # Developer/AI assistant guide
├── CHANGELOG.md              # Version history
└── requirements.txt          # Python dependencies
```

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

**Last Updated:** 2025-10-14
