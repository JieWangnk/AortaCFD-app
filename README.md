# AortaCFD: Patient-Specific Aortic Blood Flow Simulation

![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)
![Tests](https://img.shields.io/badge/tests-172%20passing-success.svg)
![Coverage](https://img.shields.io/badge/coverage-TBD-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![OpenFOAM](https://img.shields.io/badge/OpenFOAM-12-orange.svg)

**AortaCFD** is an end-to-end automated pipeline for patient-specific cardiovascular CFD simulations using OpenFOAM 12. It streamlines the complete workflow from geometry to results, featuring a simplified 3-profile numerics system (robust/standard/precise), physics model selection (laminar/RANS/LES), and advanced boundary conditions including 3-element Windkessel (3EWK) models with automatic parameter calculation.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Basic Commands](#basic-commands)
  - [Workflow Steps](#workflow-steps)
  - [Batch Execution](#batch-execution)
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
- **3-Profile Numerics System** - Simple selection: `robust`, `standard`, or `precise`
- **Physics Model Selection** - Laminar, RANS (k-ω SST), or LES (WALE)
- **Advanced Boundary Conditions** - 3-element Windkessel (3EWK) with automatic parameter calculation
- **Multiple Inlet Profiles** - Time-varying, constant, parabolic, Womersley, wall-distance
- **Automated Mesh Generation** - snappyHexMesh with boundary layers and quality control

### Workflow & Execution
- **Modular Architecture** - Task-based workflow system with step-by-step control
- **Batch Execution** - Parallel multi-case runner (`run_batch.py`) with multiprocessing support
- **Multi-Config Support** - Run same patient with different settings (mesh convergence studies)
- **Parallel Execution** - Multi-core meshing and solver with smart processor allocation
- **Update Mode** - Update existing cases with `--update` flag (preserves mesh, regenerates BCs)
- **Flexible Steps** - Run individual workflow steps (case/mesh/boundary/solver/reconstruct/hemodynamics/post)
- **HPC Integration** - SLURM job array script generation
- **OpenFOAM 12 Native** - Uses `foamRun -solver incompressibleFluid`
- **Clean Console Output** - Minimal output by default, `--verbose` for detailed logs

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

# Run complete workflow (output: output/BPM120/run_YYYYMMDD_HHMMSS/)
python run_patient.py BPM120

# Custom run name (output: output/BPM120/my_test/)
python run_patient.py BPM120 --run-name my_test

# Run with specific config file
python run_patient.py BPM120 --config config_mesh_fine.json

# Show detailed output (default is clean/minimal)
python run_patient.py BPM120 --verbose
```

**CLI Options:**
| Flag | Short | Description |
|------|-------|-------------|
| `--list` | `-l` | List available patient cases |
| `--list-steps` | | List all workflow steps |
| `--steps STEPS` | `-s` | Run specific steps (comma-separated) |
| `--step STEP` | | Run specific step (can use multiple times) |
| `--config PATH` | `-c` | Use custom config JSON file |
| `--profile NAME` | | Override simulation profile |
| `--quick` | | Quick test mode (coarse mesh) |
| `--run-name NAME` | `-n` | Custom run folder name |
| `--update PATH` | `-u` | Update existing case (preserves mesh) |
| `--postprocess PATH` | `-p` | Standalone post-processing on existing run |
| `--verbose` | `-v` | Show detailed log output |

### Working with Existing Output Cases

The `--update` flag allows you to work with **existing output directories**. This is useful for:
- Re-running the solver after parameter changes
- Reconstructing parallel cases
- Updating boundary conditions without regenerating mesh
- Post-processing completed simulations

```bash
# Update existing case (preserves mesh, regenerates case+boundary by default)
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653

# Update and run solver on existing mesh
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653 --steps solver

# Update BCs and re-run solver
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653 --steps boundary,solver

# Reconstruct a parallel case that finished on HPC
python run_patient.py PAT002 --update output/PAT002/run_20251218_142530 --steps reconstruct

# Run post-processing on completed simulation
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653 --steps post

# Standalone post-processing (re-compute hemodynamics and export QoIs)
python run_patient.py --postprocess output/BPM120/run_20251220_093653
```

**How `--update` works:**
- Preserves the existing mesh in `constant/polyMesh`
- Default steps: `case,boundary` (regenerates config files and BCs)
- Use `--steps` to override and run specific steps only
- Looks for `polyMesh` in `<path>/constant/` or `<path>/openfoam/constant/`

### Workflow Steps

AortaCFD provides granular control over the simulation pipeline:

```bash
# Run specific workflow steps (new run)
python run_patient.py BPM120 --steps mesh              # Only meshing
python run_patient.py BPM120 --steps solver            # Only solver
python run_patient.py BPM120 --steps reconstruct       # Reconstruct decomposed case
python run_patient.py BPM120 --steps hemodynamics      # Compute TAWSS, OSI, RRT
python run_patient.py BPM120 --steps post              # Post-processing

# Multiple steps (comma-separated)
python run_patient.py BPM120 --steps case,mesh,boundary

# Or use --step multiple times
python run_patient.py BPM120 --step case --step mesh --step boundary

# Combine with --update to work on existing case
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653 --steps boundary,solver
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
| **hemodynamics** | Compute WSS, TAWSS, OSI, RRT, pressure drop | After solver completes |
| **post** | Execute ParaView visualization | Generate screenshots/images |
| **all** | Complete workflow (default) | Fresh simulation |

### Common Use Cases

**1. Fresh simulation from scratch:**
```bash
python run_patient.py BPM120
```

**2. Custom output folder name:**
```bash
python run_patient.py BPM120 --run-name mesh_study_fine
# Output: output/BPM120/mesh_study_fine/
```

**3. Test different mesh resolutions:**
```bash
python run_patient.py BPM120 --config config_mesh_coarse.json --run-name coarse
python run_patient.py BPM120 --config config_mesh_fine.json --run-name fine
```

**4. Re-run solver after editing fvSolution or boundary conditions:**
```bash
# Edit the files in output/BPM120/run_*/openfoam/system/ or 0/
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653 --steps solver
```

**5. Reconstruct HPC results locally:**
```bash
# After copying results from HPC
python run_patient.py BPM120 --update output/BPM120/hpc_run --steps reconstruct,hemodynamics,post
```

**6. Update Windkessel parameters and re-run:**
```bash
# Edit 0/p to change R, C, Z values, then:
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653 --steps solver
```

**7. Continue from last saved timestep:**
```bash
# Modify controlDict to set startFrom latestTime, then:
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653 --steps solver
```

**8. Generate mesh only (for manual solver runs on HPC):**
```bash
python run_patient.py BPM120 --steps case,mesh,boundary --run-name hpc_prep
# Then copy output/BPM120/hpc_prep/openfoam to HPC
```

**9. Update case with new config but keep existing mesh:**
```bash
# After modifying config.json (e.g., changed BC settings):
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653
# This regenerates 0/, system/ but preserves constant/polyMesh
```

**10. Quick mesh test with coarse settings:**
```bash
python run_patient.py BPM120 --quick --steps case,mesh
# Creates coarse mesh for geometry validation
```

**11. Run with verbose output for debugging:**
```bash
python run_patient.py BPM120 --verbose
# Shows detailed log output instead of clean summaries
```

**12. Standalone post-processing (re-compute hemodynamics):**
```bash
python run_patient.py --postprocess output/BPM120/run_20251220_093653
# Re-runs hemodynamics analysis on existing simulation
# Outputs:
#   results/qoi_summary.json    - Structured QoI data with metadata
#   results/qoi_summary.csv     - Flat CSV for spreadsheets
#   reports/hemodynamics_report.txt - Human-readable report
```

### Batch Execution

AortaCFD includes `run_batch.py` for parallel execution of multiple cases or configuration variants using `multiprocessing`.

**Use Cases:**
- Run multiple patients in parallel
- Compare mesh resolutions (same patient, different `cells_per_diameter`)
- Parameter studies (e.g., varying Windkessel parameters)
- HPC job array generation

#### Basic Batch Execution

```bash
# Run multiple patients in parallel (2 workers)
python run_batch.py --cases PAT002 BPM120 0014_H_AO_COA -w 2

# Discover and run all valid cases in cases_input/
python run_batch.py --discover -w 4

# Run specific workflow step
python run_batch.py --cases PAT002 BPM120 -s mesh -w 2

# Dry run (see what would execute)
python run_batch.py --cases PAT002 BPM120 --dry-run
```

#### Multi-Config Runs (Same Patient, Different Settings)

For mesh convergence studies or parameter exploration, run the same patient with multiple config files:

```bash
# Create config variants
# cases_input/PAT002/config.json         (original)
# cases_input/PAT002/config_mesh10.json  (cells_per_diameter: 10)
# cases_input/PAT002/config_mesh12.json  (cells_per_diameter: 12)
# cases_input/PAT002/config_mesh14.json  (cells_per_diameter: 14)

# Run all variants in parallel
python run_batch.py --config-list \
  PAT002:config_mesh10.json \
  PAT002:config_mesh12.json \
  PAT002:config_mesh14.json \
  -w 2
```

**Output organization:**
```
output/
├── PAT002_mesh10/run_20260130_150505/    # 10 cells/diameter
├── PAT002_mesh12/run_20260130_150505/    # 12 cells/diameter
└── PAT002_mesh14/run_20260130_150506/    # 14 cells/diameter
```

Each variant gets a separate output directory (e.g., `PAT002_mesh10`) to prevent collision.

#### SLURM Job Array Generation

For HPC clusters with SLURM, generate a job array script:

```bash
# Generate SLURM script (doesn't execute locally)
python run_batch.py --cases PAT002 BPM120 -s all --slurm

# Creates: batch_job_array.sh
# Submit to SLURM: sbatch batch_job_array.sh
```

The generated script uses `--array=0-N` to parallelize across nodes.

#### Multi-Step Workflows

Run multiple workflow steps sequentially per case:

```bash
# Run setup + mesh + boundary in sequence
python run_batch.py --cases PAT002 -s case,mesh,boundary -w 1
```

#### Batch Options

| Flag | Description | Example |
|------|-------------|---------|
| `--cases` | List of patient IDs | `--cases PAT002 BPM120` |
| `--config-list` | Patient:config pairs | `--config-list PAT002:config_mesh10.json` |
| `--discover` | Auto-discover valid cases | `--discover` |
| `-w, --workers` | Parallel workers (default: 1) | `-w 4` |
| `-s, --steps` | Workflow steps (comma-separated) | `-s case,mesh,boundary` |
| `--slurm` | Generate SLURM job array script | `--slurm` |
| `--dry-run` | Show plan without execution | `--dry-run` |

#### Batch Summary

After execution, view the summary:

```bash
cat output/batch_summary.json
```

```json
{
  "total": 3,
  "succeeded": 3,
  "failed": 0,
  "results": [
    {
      "case_id": "PAT002_mesh10",
      "status": "success",
      "runtime": 0.8,
      "output": "output/PAT002_mesh10/run_20260130_150505"
    }
  ]
}
```

Individual logs are saved per case: `output/<case_id>/batch_<case_id>.log`

### Configuration

AortaCFD uses a unified `config.json` format. The configuration system features:

- **3-Profile Numerics**: Select `robust`, `standard`, or `precise`
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
| **standard** | 2nd | High | Production runs, clinical studies (DEFAULT) |
| **precise** | 2nd | Good* | LES, validation, minimal diffusion |

*Requires good mesh quality (orthogonality > 70°, skewness < 2)

### Profile Details

**`robust`** - Maximum Stability
- Time: Euler (1st order)
- Convection: Gauss upwind (1st order, bounded)
- Relaxation: U: 0.7, p: 0.3, pFinal: 0.9
- Use when: Debugging, poor mesh quality, initial testing
- Trade-off: Highly diffusive (damps gradients)

**`standard`** - Balanced (RECOMMENDED)
- Time: backward (2nd order implicit)
- Convection: Gauss limitedLinearV (2nd order, TVD bounded)
- Relaxation: U: 0.7, p: 0.3, pFinal: 0.9
- Use when: Production runs, clinical studies, Windkessel outlets
- Trade-off: Good accuracy with high stability

**`precise`** - Minimal Diffusion
- Time: CrankNicolson 0.9 (2nd order)
- Convection: Gauss LUST (75% central + 25% upwind)
- Relaxation: U: 0.9, p: 0.5
- Use when: LES simulations, final validation, minimal diffusion required
- Requirements: Good mesh quality, ~2-3x longer runtime

### Physics Models

Combine any numerics profile with any physics model:

```json
{
  "physics": {
    "model": "laminar"    // or "rans" or "les"
  },
  "numerics": {
    "profile": "standard" // or "robust" or "precise"
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
      "betaT": 0.3,
      "betaN": 0.0
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

For pulsatile simulations with Windkessel BCs, backflow stabilization prevents divergence during diastole. The implementation uses a **two-parameter directional approach** (`betaT`, `betaN`) based on Esmaily Moghadam et al. (2011).

**Two-Parameter Formulation:**

| Parameter | Direction | Default | Effect |
|-----------|-----------|---------|--------|
| `betaT` | Tangential | **0.3** | Suppresses vortices during backflow |
| `betaN` | Normal | **0.0** | Controls normal velocity damping |

> **Important:** `betaN = 0` preserves the Windkessel pressure-flow coupling. Only increase `betaN` for severe instabilities.

**Tensor formulation:**
```
F = H(-φ) × [βN·n⊗n + βT·(I - n⊗n)]
```
where H(-φ) activates stabilization only during backflow.

**Configuration:**
```json
{
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "enable_stabilization": true,
      "betaT": 0.3,
      "betaN": 0.0
    }
  }
}
```

**Recommendations:**
- **Standard cases:** `betaT=0.3`, `betaN=0.0` (recommended default)
- **Mild instabilities:** Increase `betaT` to 0.5
- **Severe backflow:** Add small `betaN=0.05` as last resort

See [OpenFOAM-WK](https://github.com/JieWangnk/OpenFOAM-WK) for detailed documentation.

---

## Post-Processing

AortaCFD includes comprehensive post-processing for visualization and hemodynamic analysis.

### Quick Usage (Workflow Integration)

```bash
# Run post-processing as part of workflow
python run_patient.py BPM120 --steps post

# Run post-processing on existing case
python run_patient.py BPM120 --update output/BPM120/run_20251220_093653 --steps post

# Include post-processing in full workflow
python run_patient.py BPM120  # post-processing runs automatically at end
```

### Standalone Post-Processing (Advanced)

For running post-processing outside the workflow:

```bash
# ParaView visualization (screenshots/animations)
pvbatch src/aortacfd_lib/post_processor.py output/BPM120/run_*/openfoam all

# Check post-processing dependencies
python -m aortacfd_lib.post_processing --check-deps
```

### Hemodynamic Metrics

The hemodynamics module computes clinical metrics from CFD results for cardiovascular assessment.

#### Overview

| Metric | Description | Unit | Clinical Threshold |
|--------|-------------|------|-------------------|
| **TAWSS** | Time-averaged wall shear stress | Pa | Low <0.4 Pa: Atherogenic risk |
| **OSI** | Oscillatory shear index | - | High >0.3: Thrombus risk |
| **RRT** | Relative residence time | 1/Pa | High >10: Particle trapping |
| **ΔP** | Pressure drop | mmHg | >20 mmHg: Significant coarctation |

#### Mathematical Formulas

The hemodynamic indices are computed using standard definitions from literature (He & Ku 1996, Himburg et al. 2004):

**TAWSS (Time-Averaged Wall Shear Stress):**
```
TAWSS = (1/T) ∫₀ᵀ |τ_w(t)| dt = mean(|WSS|)
```
Where τ_w is the wall shear stress vector and T is the cardiac cycle period.

**OSI (Oscillatory Shear Index):**
```
OSI = 0.5 × (1 - |mean(τ_w)| / TAWSS)
    = 0.5 × (1 - |∫τ_w dt| / ∫|τ_w| dt)
```
OSI ranges from 0 (unidirectional flow) to 0.5 (fully oscillatory flow).

**RRT (Relative Residence Time):**
```
RRT = 1 / ((1 - 2×OSI) × TAWSS)
```
RRT indicates the residence time of particles near the wall.

#### Clinical Interpretation

| Metric | Normal Range | Abnormal | Clinical Implication |
|--------|--------------|----------|---------------------|
| TAWSS | 1-7 Pa | <0.4 Pa | Atherosclerosis-prone regions |
| TAWSS | 1-7 Pa | >40 Pa | Endothelial damage risk |
| OSI | <0.1 | >0.3 | Disturbed flow, platelet activation |
| RRT | <1 Pa⁻¹ | >10 Pa⁻¹ | Particle/thrombus accumulation |

#### Example Output

```
HEMODYNAMICS ANALYSIS REPORT
======================================================================
TAWSS Maximum: 143.75 Pa    Mean: 16.41 Pa
OSI Maximum:   0.45         Mean: 0.0087
RRT Maximum:   6.67 Pa⁻¹    Mean: 0.18 Pa⁻¹

Pressure Drop (Inlet → Outlets):
  → outlet1: 29.85 mmHg
  → outlet2: 29.85 mmHg
```

#### Visualization

TAWSS, OSI, and RRT are saved as OpenFOAM scalar fields and can be visualized in ParaView:

```json
{
  "visualization": {
    "fields": ["TAWSS", "OSI", "RRT"],
    "time_steps": [2.5],
    "color_ranges": {
      "TAWSS": [0, 50],
      "OSI": [0, 0.5],
      "RRT": [0, 10]
    }
  }
}
```

### Requirements for TAWSS/OSI/RRT

**Important:** TAWSS, OSI, and RRT require specific runtime configuration. These metrics **cannot be computed after the simulation** if not enabled beforehand.

#### Required Configuration

Add to your `config.json`:

```json
{
  "hemodynamics": {
    "runtime_functions": {
      "wallShearStress": true,
      "fieldAverage": true
    },
    "tawss_settings": {
      "skip_cycles": 2
    }
  }
}
```

#### What Each Setting Does

| Setting | Purpose | What Happens If Missing |
|---------|---------|------------------------|
| `wallShearStress: true` | Computes WSS at each time step | No WSS data (can run `foamPostProcess` after) |
| `fieldAverage: true` | Computes time-averaged fields during runtime | **TAWSS/OSI/RRT unavailable** |
| `skip_cycles: 2` | Skips initial transient cycles | Uses all cycles (may include startup artifacts) |

#### Minimum Simulation Duration

For TAWSS/OSI/RRT, you need at least `skip_cycles + 1` complete cardiac cycles:

```
Example: cardiac_cycle = 0.5s, skip_cycles = 2
Minimum end_time = (2 + 1) × 0.5s = 1.5s
Recommended: 4-5 cycles for converged statistics
```

#### If fieldAverage Was Not Enabled

If you ran a simulation without `fieldAverage: true`, you will see:
```
WARNING: fieldAverage data not found. TAWSS/OSI/RRT not computed.
```

**Solution:** Re-run the simulation with `fieldAverage` enabled. There is no way to compute proper time-averaged metrics after the fact.

#### References

- He, X., & Ku, D. N. (1996). Pulsatile flow in the human left coronary artery bifurcation. *Journal of Biomechanical Engineering*, 118(1), 74-82.
- Himburg, H. A., et al. (2004). Spatial comparison between wall shear stress measures and porcine arterial endothelial permeability. *American Journal of Physiology*, 286(5), H1916-H1922.
- Malek, A. M., et al. (1999). Hemodynamic shear stress and its role in atherosclerosis. *JAMA*, 282(21), 2035-2042.

### Python API (For Custom Scripts)

```python
from aortacfd_lib.hemodynamics_postprocessor import (
    HemodynamicsPostProcessor,
    run_hemodynamics_analysis
)

# Run hemodynamics analysis
config = {
    'inlet': {'type': 'TIMEVARYING'},
    'cardiac_cycle': 0.8,
    'geometry': {
        'inlet_keywords_ordered': 'inlet',
        'outlet_keywords_ordered': ['outlet_1', 'outlet_2'],
        'wall_keywords_ordered': 'wall_aorta'
    }
}

results = run_hemodynamics_analysis(
    case_dir="output/BPM120/run_*/openfoam",
    config=config,
    output_dir="output/BPM120/run_*/reports"
)
print(f"TAWSS mean: {results.tawss_mean:.4f} Pa")
print(f"OSI mean: {results.osi_mean:.4f}")
```

### Customizing Visualization

Add a `visualization` section to your `config.json` to control fields, time steps, and color ranges:

```json
{
  "visualization": {
    "fields": ["U", "p", "wallShearStress", "TAWSS"],
    "time_steps": [0.5, 1.0, 1.5, 2.0],
    "color_ranges": {
      "WSS": [0, 50],
      "TAWSS": [0, 30]
    }
  }
}
```

#### Available Options

| Option | Description | Example |
|--------|-------------|---------|
| `fields` | Fields to visualize | `["U", "wallShearStress", "TAWSS", "OSI", "RRT"]` |
| `time_steps` | Specific times to capture (reduces computation) | `[0.5, 1.0, 1.5]` |
| `color_ranges` | Fixed color ranges (others auto-scale) | `{"WSS": [0, 50]}` |

#### Available Fields

| Field | Description | Notes |
|-------|-------------|-------|
| `U` | Velocity | Volume rendering |
| `p` | Pressure | Surface rendering |
| `wallShearStress` | Instantaneous WSS | Surface rendering |
| `TAWSS` | Time-averaged WSS | Requires hemodynamics post-processing first |
| `OSI` | Oscillatory Shear Index | Requires hemodynamics post-processing first |
| `RRT` | Relative Residence Time | Requires hemodynamics post-processing first |

**Note:** TAWSS, OSI, and RRT fields are generated by the hemodynamics post-processor. Run `--step post` to create them before visualization.

#### Color Range Examples

| Field | Unit | Default | Clinical Threshold |
|-------|------|---------|-------------------|
| `WSS` | Pa | `[0, 50]` | Low <0.4 Pa (atherogenic) |
| `TAWSS` | Pa | `[0, 50]` | Low <0.4 Pa (atherogenic) |
| `OSI` | - | `[0, 0.5]` | High >0.3 (oscillatory flow) |
| `RRT` | 1/Pa | `[0, 10]` | High >10 (particle trapping) |
| `U` | m/s | auto | - |
| `Pressure` | Pa | auto | - |

### Manual Visualization

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
├── postProcessing_results/    # Post-processing output
│   ├── images/                # Screenshots and animations
│   ├── hemodynamics_report.txt
│   └── pressure_drop_timeseries.png
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
│   │   ├── hemodynamics_postprocessor.py  # TAWSS/OSI/RRT
│   │   ├── post_processor.py         # ParaView visualization
│   │   ├── post_processing/          # Unified post-processing module
│   │   │   ├── __init__.py           # Package exports
│   │   │   ├── core.py               # PostProcessor class
│   │   │   ├── config.py             # Configuration handling
│   │   │   ├── dependencies.py       # Dependency checking
│   │   │   └── cli.py                # Command-line interface
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
│   │       └── precise.py            # Minimal diffusion
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
├── run_patient.py            # Single case runner (main entry point)
├── run_batch.py              # Batch/parallel multi-case runner
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

**Last Updated:** 2026-02-05
