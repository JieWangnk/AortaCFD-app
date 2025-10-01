# AortaCFD User Guide

## Overview

AortaCFD is a computational fluid dynamics (CFD) application for simulating blood flow in patient-specific aortic geometries. It automates the entire workflow from mesh generation to post-processing, providing clinically relevant hemodynamic metrics.

## Installation

### Prerequisites
- Ubuntu/Linux operating system
- OpenFOAM 12
- Python 3.8+
- 8 GB RAM (minimum), 16 GB recommended
- 10 GB free disk space

### Setup Steps

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/AortaCFD-app.git
cd AortaCFD-app
```

2. **Create Python virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

4. **Verify OpenFOAM installation:**
```bash
simpleFoam -help
```

## Quick Start

### Single Patient Analysis

Run CFD analysis for a single patient case:

```bash
python3 run_patient.py patient1                    # Complete workflow
python3 run_patient.py patient1 --step mesh        # Only meshing step
python3 run_patient.py patient1 --step case --step mesh  # Multiple steps
python3 run_patient.py --list                      # List available patients
```

### Batch Processing

Process multiple patients in parallel:

```bash
# Run all cases with default settings
python3 -m src.batch_runner --all

# Run specific cases
python3 -m src.batch_runner --cases patient1 patient2

# Dry run to preview what will be executed
python3 -m src.batch_runner --all --dry-run
```

## Input Data Structure

### Required Files

Each patient case should be organized as follows:

```
patient_case/
├── inlet.stl           # Aortic inlet surface
├── wall_aorta.stl      # Vessel wall surface
├── outlet_1.stl        # Branch outlet 1
├── outlet_2.stl        # Branch outlet 2
├── outlet_3.stl        # Branch outlet 3 (optional)
└── flow_data.csv       # Inlet flow waveform (optional)
```

### File Naming Conventions

| Surface Type | Required Naming Pattern |
|-------------|-------------------------|
| Inlet | Must contain "inlet" |
| Wall | Must contain "wall" |
| Outlets | Must contain "outlet" with number suffix |

### Flow Data Format

If providing measured flow data, use CSV format:

```csv
Time[s],Flow[ml/s]
0.0,50.0
0.1,250.0
0.2,350.0
0.3,200.0
0.4,100.0
0.5,60.0
0.6,50.0
0.7,50.0
0.8,50.0
```

If no flow data is provided, a physiological waveform will be generated automatically.

## Simulation Profiles

Available simulation profiles in `src/config/profiles/`:

| Profile | Turbulence Model | Mesh Quality | Use Case |
|---------|-----------------|--------------|----------|
| `sim_laminar_coarse` | Laminar | Coarse | Quick tests |
| `sim_laminar_medium` | Laminar | Medium | Clinical workflows |
| `sim_laminar_fine` | Laminar | Fine | Publication quality |
| `sim_rans_coarse` | k-ω SST | Coarse | Turbulent flow screening |
| `sim_rans_medium` | k-ω SST | Medium | Clinical turbulent studies |
| `sim_rans_fine` | k-ω SST | Fine | Research-grade turbulence |
| `sim_les_medium` | WALE LES | Medium | Transitional LES studies |
| `sim_les_fine` | WALE LES | Fine | Publication-grade LES |

## Usage Examples

### Basic Usage

```bash
# Run with default settings
python3 run_patient.py patient1

# Run different patient cases
python3 run_patient.py patient2        # 120 BPM case
python3 run_patient.py 0014_H_AO_COA   # Coarctation case

# Run specific workflow steps
python3 run_patient.py patient1 --step case --step mesh --step boundary

# List available patient cases
python3 run_patient.py --list
```

### Batch Processing

```bash
# Process all cases in cases_input directory
python3 -m src.batch_runner --all

# Process specific cases
python3 -m src.batch_runner --cases patient1 patient2 0014_H_AO_COA

# Limit parallel jobs
python3 -m src.batch_runner --all --max-workers 4

# Preview commands without running
python3 -m src.batch_runner --all --dry-run
```

### Advanced Options

```bash
# Run specific workflow steps
python3 run_patient.py patient1 --step mesh --step solver --step post

# Complete workflow (all steps)
python3 run_patient.py patient1 --step all

# Available workflow steps:
# case     - Create case structure and configuration files
# mesh     - Generate mesh (blockMesh, surfaceFeatures, snappyHexMesh)
# boundary - Setup boundary conditions and flow data
# solver   - Run CFD solver (pimpleFoam/foamRun)
# post     - Execute post-processing
# all      - Complete workflow (default)
```

## Output Structure

Results are organized as follows:

```
output/PAT001/
├── case_info.json           # Case metadata
├── mesh/
│   ├── mesh_quality.log     # Mesh statistics
│   └── constant/polyMesh/   # OpenFOAM mesh
├── simulation/
│   ├── convergence.log      # Solver convergence
│   └── [time_directories]/  # Solution fields
├── postProcessing/
│   ├── outlet_flow/         # Flow rate data
│   ├── pressure_drop/       # Pressure metrics
│   └── wall_shear_stress/   # WSS distribution
├── results/
│   ├── hemodynamics.json    # Computed metrics
│   ├── figures/             # Visualization plots
│   └── report.html          # Summary report
└── logs/
    └── workflow.log         # Execution log
```

## Key Metrics

The following hemodynamic metrics are computed:

| Metric | Description | Clinical Significance |
|--------|-------------|----------------------|
| **TAWSS** | Time-averaged wall shear stress | Low values (<0.4 Pa) indicate risk regions |
| **OSI** | Oscillatory shear index | High values (>0.3) indicate disturbed flow |
| **Pressure Drop** | Inlet to outlet pressure difference | Indicates stenosis severity |
| **Flow Distribution** | Outlet flow percentages | Assesses branch perfusion |
| **Reynolds Number** | Flow regime indicator | >4000 suggests turbulent flow |
| **Womersley Number** | Pulsatility parameter | Characterizes unsteady effects |

## Performance Optimization

### Parallel Processing

The application automatically detects available CPU cores and runs in parallel:

```bash
# Override automatic detection
export OMP_NUM_THREADS=8
python3 run_patient.py patient1
```

### Memory Management

For systems with limited RAM:

```bash
# Batch processing with limited workers
python3 -m src.batch_runner --all --max-workers 2

# Single case with controlled resources
export OMP_NUM_THREADS=2
python3 run_patient.py patient1
```

## Troubleshooting

### Common Issues

**"No STL files found"**
- Verify file extensions are `.stl` or `.STL`
- Check file path is correct
- Ensure files follow naming conventions

**"Mesh generation failed"**
- Check STL files are watertight (closed surfaces)
- Verify STL files are in ASCII or binary format
- Reduce mesh refinement level

**"Simulation diverged"**
- Use smaller time step (modify in profile)
- Switch to more stable numerical schemes
- Check boundary conditions are physical

**"Out of memory"**
- Use coarse mesh profile
- Reduce number of parallel processes
- Close other applications

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Set environment variable
export AORTACFD_DEBUG=1
python3 run_patient.py patient1

# Check log files in the output directory
tail -f output/patient1/logs/workflow.log
```

## Configuration

### Custom Profiles

Create custom simulation profiles in `src/config/profiles/`:

```python
# src/config/profiles/my_custom_profile.py
from src.config.base import BaseConfig

class MyCustomProfile(BaseConfig):
    # Mesh settings
    mesh_scale = 0.001  # Convert mm to m
    refinement_level = 3

    # Solver settings
    turbulence_model = "kOmegaSST"
    end_time = 2.0  # seconds
    time_step = 0.001

    # Boundary conditions
    inlet_type = "flowRateInletVelocity"
    outlet_type = "windkessel"
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AORTACFD_DEBUG` | Enable debug logging | 0 |
| `OMP_NUM_THREADS` | Number of parallel threads | Auto-detect |
| `FOAM_RUN` | OpenFOAM case directory | Current directory |

## Best Practices

1. **Geometry Preparation**
   - Ensure STL surfaces are manifold (watertight)
   - Remove small features < 0.5 mm
   - Smooth sharp edges that may cause mesh issues

2. **Mesh Quality**
   - Start with coarse mesh for initial tests
   - Check mesh quality metrics before running simulation
   - Refine mesh in regions of interest (bifurcations, stenoses)

3. **Simulation Settings**
   - Use at least 2 cardiac cycles for periodic solution
   - Save results at 100 Hz for accurate post-processing
   - Monitor residuals for convergence

4. **Validation**
   - Compare outlet flow splits with clinical data
   - Verify pressure drops are physiological
   - Check mass conservation < 1% error

## Support

For issues and questions:
- Check the [README.md](README.md) for detailed documentation
- Review example cases in `cases_input/`:
  - `patient1` - Complex aortic geometry with multiple branches (75 BPM)
  - `patient2` - Multi-branch aortic geometry case (120 BPM)
  - `0014_H_AO_COA` - Coarctation of aorta case with multiple outlets (60 BPM)
- Submit issues on GitHub repository

## Citation

If you use AortaCFD in your research, please cite:

```bibtex
@software{aortacfd2024,
  title = {AortaCFD: Automated Patient-Specific Aortic Flow Simulation},
  author = {Your Name},
  year = {2024},
  url = {https://github.com/yourusername/AortaCFD-app}
}
```