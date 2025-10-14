# AortaCFD: Patient-Specific Aortic Blood Flow Simulation

![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)
![Tests](https://img.shields.io/badge/tests-362%20passing-success.svg)
![Coverage](https://img.shields.io/badge/coverage-29%25-yellow.svg)
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

# 4. Run your first simulation
python run_patient.py patient1

# 5. View results
paraview output/patient1/run_*/openfoam/openfoam.foam
```

**File Structure:**
```
cases_input/patient1/          # Patient input data
├── config.json                # Simulation configuration
├── inlet.stl                  # Inlet geometry
├── outlet*.stl                # Outlet geometries
├── wall_aorta.stl             # Vessel wall
└── BPM75.csv                  # Flow data (optional)

output/patient1/               # Results
└── run_YYYYMMDD_HHMMSS/
    ├── openfoam/              # OpenFOAM case
    └── images/                # Post-processing visualizations
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
- ✅ **Comprehensive Testing** - 362 tests with CFD quality validation
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

**Basic config.json structure:**

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
    "mesh_resolution": {
      "target_cell_size_mm": 0.5
    },
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

AortaCFD includes **362 code tests** plus **CFD quality validation** with **100% pass rate**:

```bash
# Run all tests
./venv/bin/pytest tests/ test_patient1_e2e.py test_multi_patient_e2e.py

# Unit tests only (302 tests)
./venv/bin/pytest tests/unit/ -v

# Integration tests (42 tests)
./venv/bin/pytest tests/integration/ -v

# End-to-end tests (18 tests)
./venv/bin/pytest test_patient1_e2e.py test_multi_patient_e2e.py -v

# CFD quality validation (8 tests)
./venv/bin/pytest test_cfd_validation.py -v -s

# With coverage report
./venv/bin/pytest --cov=src --cov-report=html
```

**Test Coverage:**
- inlet_mapping.py: 92% ✅
- mesh_setup.py: 79% ✅
- patch_processing.py: 72% ✅
- setup_tasks.py: 56% ✅
- murray_calculator.py: 46% 🟡
- **Overall: 29%** 🟡

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
