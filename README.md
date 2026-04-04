# AortaCFD

![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)
![Tests](https://img.shields.io/badge/tests-2086%20passing-success.svg)
![OpenFOAM](https://img.shields.io/badge/OpenFOAM-12-orange.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

AortaCFD is an automated OpenFOAM 12 workflow for patient-specific aortic CFD. It takes case geometry (STL patches) and a JSON config, builds the OpenFOAM case, generates the mesh, applies inlet and outlet boundary conditions, runs the solver, and exports hemodynamic quantities of interest with run reports.

The project is designed for practical case execution rather than manual OpenFOAM case assembly. A typical workflow is:

1. Place STL patches and a config under `cases_input/<case_id>/`
2. Run `run_patient.py` for a single case or `run_batch.py` for multiple cases
3. Review `reports/` and `results/` under `output/<case_id>/<run_name>/`

---

## Requirements

- Linux (Ubuntu 20.04+)
- Python 3.12
- OpenFOAM 12 (Foundation version)
- ParaView (optional, for visualization)

## Installation

```bash
git clone https://github.com/JieWangnk/AortaCFD-app.git
cd AortaCFD-app

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

OpenFOAM 12 must be sourced before running the workflow:

```bash
source /opt/openfoam12/etc/bashrc
```

If you plan to use 3-element Windkessel outlets, install the custom boundary condition:

```bash
./scripts/install_windkessel_of12.sh
```

---

## Case Layout

Each case lives under `cases_input/<case_id>/`.

```text
cases_input/<case_id>/
├── config.json
├── inlet.stl
├── outlet1.stl
├── outlet2.stl
├── ...
├── wall_aorta.stl
└── flowrate.csv          (optional, for pulsatile inlet)
```

STL files should be in millimetres. The workflow scales them to metres using the `scale_factor` in config (typically `0.001`). STL naming must match the `geometry` keywords in `config.json`.

---

## Quick Start

```bash
# List available cases
python run_patient.py --list

# Run a complete case
python run_patient.py BPM120

# Custom output folder
python run_patient.py BPM120 --run-name baseline_standard

# Different config
python run_patient.py BPM120 --config config_mesh_fine.json

# Show available steps
python run_patient.py --list-steps
```

---

## Workflow Steps

AortaCFD breaks the simulation into discrete steps that can be run individually or together.

| Step | Description |
|------|-------------|
| `case` | Create case structure, scale geometry, write OpenFOAM dictionaries |
| `mesh` | Run blockMesh, surfaceFeatures, snappyHexMesh, checkMesh |
| `boundary` | Prepare inlet flow data, set up outlet BCs, write 0/ files |
| `regenerate-numerics` | Rewrite fvSchemes/fvSolution based on mesh quality |
| `solver` | Run foamRun (with parallel decomposition if configured) |
| `reconstruct` | Reconstruct parallel case from processor directories |
| `postprocess` | Compute hemodynamic metrics (TAWSS, OSI, RRT) and export QoIs |
| `paraview` | Run ParaView visualization |

```bash
# Run selected steps
python run_patient.py BPM120 --steps case,mesh,boundary
python run_patient.py BPM120 --steps solver
python run_patient.py BPM120 --steps postprocess

# Update existing run (preserves mesh, regenerates BCs)
python run_patient.py BPM120 --update output/BPM120/run_xxx
python run_patient.py BPM120 --update output/BPM120/run_xxx --steps boundary,solver

# Standalone post-processing on a completed run
python run_patient.py --postprocess output/BPM120/run_xxx
```

---

## Configuration

AortaCFD uses a single `config.json` per case. The configuration system has three layers:

1. **Base defaults** (OpenFOAM 12 settings, built-in)
2. **Numerics profile** (robust / standard / precise)
3. **Case config** (your `config.json` overrides)

### Minimal Config

```json
{
  "case_info": {
    "patient_id": "MY_CASE"
  },
  "physics": {
    "model": "laminar",
    "transport_properties": { "rho": 1060, "nu": 3.7736e-6 }
  },
  "numerics": {
    "profile": "standard"
  },
  "mesh": {
    "goal": "routine_hemodynamics"
  },
  "geometry": {
    "inlet_keywords_ordered": "inlet",
    "outlet_keywords_ordered": ["outlet1", "outlet2"],
    "wall_keywords_ordered": "wall_aorta",
    "scale_factor": 0.001
  },
  "boundary_conditions": {
    "inlet": { "type": "CONSTANT", "cardiac_output": 5.0, "profile": "parabolic" },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": { "systolic_pressure": 120, "diastolic_pressure": 80 }
    },
    "walls": { "type": "no_slip" }
  },
  "simulation_control": { "end_time": 1.0, "writeInterval": 0.1 },
  "run_settings": { "solution_type": "parallel", "subdomains": 8 }
}
```

See `examples/` for ready-to-use templates:
- `config_minimal.json` -- smallest working config
- `config_standard.json` -- pulsatile Windkessel workflow
- `config_full.json` -- complete parameter reference

---

## Numerics Profiles

Three profiles control the discretisation scheme, solver tolerances, and relaxation.

| Profile | Order | Stability | Use Case |
|---------|-------|-----------|----------|
| `robust` | 1st | Maximum | Initial testing, poor meshes, debugging |
| `standard` | 2nd | High | Production runs (recommended default) |
| `precise` | 2nd | Good | LES, validation studies, minimal diffusion |

Any profile works with any physics model (`laminar`, `rans`, `les`). See **Physics Model Selection** below for guidance on which model to use.

**robust** -- Euler time, upwind convection. Highly diffusive but will not diverge.

**standard** -- backward time, limitedLinearV convection. Good accuracy with bounded stability.

**precise** -- backward time, LUST convection. Requires good mesh quality (orthogonality > 70 deg, skewness < 2).

---

## Physics Model Selection

Laminar is the recommended default for most aortic cases. Aortic Reynolds numbers are typically 500-4000 (transitional), and published aortic CFD increasingly uses laminar simulations up to Re ~4000.

| Model | When to use | Mesh requirements |
|-------|-------------|-------------------|
| `laminar` | Re < 4000 (most aortic cases) | Standard mesh quality |
| `rans` | Re > 5000 (severe stenosis, mechanical valve, high cardiac output) | Non-ortho < 65 deg, skewness < 4, uniform refinement levels |
| `les` | Time-resolved turbulence needed (jet breakdown, vortex dynamics) | Non-ortho < 55 deg, skewness < 2, y+ < 1, CFL < 0.5 |

AortaCFD warns automatically when RANS or LES is selected but conditions are unfavourable (low Re, poor mesh quality, refinement level jumps). These warnings appear during config build and after meshing.

Key risks with turbulence models on aortic meshes:
- **k-omega SST** may over-predict eddy viscosity in predominantly laminar flow (Re < 4000), artificially increasing dissipation
- The k production term `P_k = nut * |S|^2` amplifies mesh-induced velocity gradient errors at refinement boundaries
- **LES** with hard backflow stabilisation (Heaviside step) causes nut blowup from velocity gradient discontinuities — AortaCFD auto-disables this for LES

---

## Mesh Resolution

AortaCFD defaults to **adaptive span-based meshing**: a coarse blockMesh background with OpenFOAM 12's `insideSpan` refinement to guarantee minimum cells across the vessel lumen everywhere. This replaces the legacy `cells_per_diameter` approach, reducing blockMesh waste by 80-96% while maintaining or improving mesh quality.

### Mesh goal presets (recommended)

The simplest way to control meshing is through `mesh_goal`:

```json
{
  "mesh": {
    "goal": "routine_hemodynamics"
  }
}
```

| Goal | Lumen resolution | Layers | Use case |
|------|-----------------|--------|----------|
| `pressure_fast` | 10 cells across span | Off | Quick screening, pressure gradient |
| `routine_hemodynamics` | 16 cells across span | 3 layers (standard) | Production patient-specific runs |
| `wall_sensitive` | 22 cells across span | 3 layers (standard) | WSS, OSI, near-wall indices |

### Direct control

For explicit control, set `cells_across_span` directly:

```json
{
  "mesh": {
    "SNAPPY_SETTINGS": {
      "cells_across_span": 16,
      "surfaceRefinementLevels": [1, 2]
    }
  }
}
```

Final cell count depends on geometry size and complexity — the same `cells_across_span` produces different cell counts on different anatomies. The app reports achieved resolution and cell counts in the post-mesh audit.

### Boundary layers

Layers are configured through `boundary_layers` or inherited from the goal preset:

```json
{
  "mesh": {
    "boundary_layers": {
      "enabled": true,
      "num_layers": 3,
      "expansion_ratio": 1.2,
      "final_layer_thickness": 0.3
    }
  }
}
```

Layer coverage on patient-specific vascular geometry is typically 20-50% under standard quality controls, concentrated on lower-curvature wall segments. For WSS-sensitive studies, verify coverage in the mesh audit report.

### Legacy mode

The old `cells_per_diameter` approach is still supported:

```json
{
  "mesh": {
    "cells_per_diameter": 15,
    "SNAPPY_SETTINGS": {
      "mesh_strategy": "legacy_surface"
    }
  }
}
```

### Post-mesh audit

After meshing, AortaCFD writes `reports/mesh_audit.json` with:
- checkMesh quality metrics (maxNonOrtho, maxSkewness)
- achieved cells-across-lumen proxy at inlet and each outlet
- verdict: `pass`, `warn`, or `fail` based on OpenFOAM quality thresholds

---

## Inlet Boundary Conditions

| Type | Description | Data Source |
|------|-------------|------------|
| `CONSTANT` | Steady flow | `cardiac_output`, `flowrate`, or `velocity` in config |
| `TIMEVARYING` | Pulsatile from CSV | `csv_file` with time and flow columns |
| `WOMERSLEY` | Analytical pulsatile | Computed from flow waveform |
| `MRI` | Patient-specific 4D flow | Pre-processed OpenFOAM boundary data |

Profile options: `plug`, `parabolic`, `womersley`, `wall_distance`

The workflow writes an inlet audit report (`reports/inlet_audit.json`) documenting the derived flow rate, velocity, inlet geometry, Womersley number, and profile recommendation.

## Outlet Boundary Conditions

### 3-Element Windkessel (3EWK)

The default outlet model. Parameters are computed automatically from blood pressure and outlet geometry using Murray's law:

```json
{
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "systolic_pressure": 120,
      "diastolic_pressure": 80
    }
  }
}
```

Automatic calculation:
1. MAP = DBP + (SBP - DBP) / 3
2. Flow split via Murray's law (proportional to outlet radius cubed)
3. Total resistance R = (MAP - P_venous) / mean_flow
4. Proximal impedance Z = rho * PWV / A
5. Compliance C = tau / R

For pulsatile simulations, backflow stabilisation prevents divergence during diastole:

```json
{
  "windkessel_settings": {
    "enable_stabilization": true,
    "betaT": 0.3,
    "betaN": 0.0
  }
}
```

`betaN = 0` preserves Windkessel pressure-flow coupling. Only increase for severe instabilities.

---

## Hemodynamic Metrics

The `postprocess` step computes clinical hemodynamic indices from the simulation results.

| Metric | Unit | Description |
|--------|------|-------------|
| TAWSS | Pa | Time-averaged wall shear stress |
| OSI | - | Oscillatory shear index (0 = unidirectional, 0.5 = fully oscillatory) |
| RRT | 1/Pa | Relative residence time |
| Pressure drop | mmHg | Inlet-to-outlet pressure difference |

Formulas:
- TAWSS = (1/T) integral |tau_w(t)| dt
- OSI = 0.5 * (1 - |mean(tau_w)| / TAWSS)
- RRT = 1 / ((1 - 2*OSI) * TAWSS)

TAWSS/OSI/RRT require runtime field averaging. Add to config:

```json
{
  "hemodynamics": {
    "runtime_functions": { "wallShearStress": true, "fieldAverage": true },
    "tawss_settings": { "skip_cycles": 2 }
  }
}
```

Minimum simulation duration: (skip_cycles + 1) * cardiac_cycle_period.

### QoI Export

Post-processing exports percentile-based quantities of interest:

| QoI | Unit | Description |
|-----|------|-------------|
| `pressure_drop_mean_mmhg` | mmHg | Cycle-averaged pressure drop |
| `tawss_p99_pa` | Pa | 99th percentile TAWSS |
| `tawss_p95_pa` | Pa | 95th percentile TAWSS |
| `wss_p99_pa` | Pa | 99th percentile peak systolic WSS |
| `osi_mean_masked` | - | Mean OSI where TAWSS > 0.5 Pa |

Percentiles (p99, p95) are used instead of maximum values because max WSS is sensitive to mesh topology artifacts at refinement boundaries and corner cells. Percentiles provide robust descriptors that converge with mesh refinement.

Output files:
- `results/qoi_summary.json` -- structured with metadata and definitions
- `results/qoi_summary.csv` -- flat format for spreadsheets

---

## Batch Execution

`run_batch.py` runs multiple cases in parallel using Python multiprocessing.

```bash
# Run all discovered cases
python run_batch.py

# Specific cases with limited parallelism
python run_batch.py --cases PAT002 PAT003 --workers 2

# Mesh convergence study (same patient, different configs)
python run_batch.py \
  --config-list PAT002:config_mesh10.json PAT002:config_mesh12.json PAT002:config_mesh14.json \
  --workers 2

# Dry run
python run_batch.py --cases PAT002 BPM120 --dry-run
```

After a batch completes, QoIs from the current batch are aggregated into `output/cohort_comparison.csv`.

---

## Output Structure

```text
output/<case_id>/<run_name>/
├── openfoam/                    OpenFOAM case directory
│   ├── 0/                       Boundary conditions
│   ├── constant/                Mesh, transport properties
│   ├── system/                  Solver dictionaries
│   └── logs/                    Simulation logs
├── reports/
│   ├── merged_config.json       Full runtime configuration (reproducibility)
│   ├── mesh_audit.json          Post-mesh QC (quality, resolution proxy, verdict)
│   ├── simulation_setup_report.txt
│   └── inlet_audit.json         Inlet BC audit trail
├── results/
│   ├── qoi_summary.json         Hemodynamic QoIs
│   └── qoi_summary.csv
└── summary.json
```

---

## Testing

AortaCFD includes 2086 automated tests covering configuration, boundary conditions, meshing, mesh audit, hemodynamics, and workflow integration.

```bash
# Run all tests
./venv/bin/pytest tests/ -v

# With coverage
./venv/bin/pytest tests/ --cov=src --cov-report=html
```

---

## Project Structure

```text
AortaCFD-app/
├── src/
│   ├── aortacfd_lib/            CFD library (mesh, BCs, hemodynamics, post-processing)
│   ├── config/                  Configuration system (builder, profiles, schema)
│   ├── workflow/                Task-based workflow manager
│   ├── patient_runner/          CLI and case runner
│   └── templates/               Jinja2 templates for OpenFOAM dictionaries
├── cases_input/                 Patient case data (STL + config)
├── output/                      Simulation results (generated)
├── tests/                       Test suite
├── examples/                    Configuration templates
├── docs/                        Technical documentation
├── scripts/                     Utility and HPC scripts
├── run_patient.py               Single-case entry point
└── run_batch.py                 Batch/parallel runner
```

---

## Citation

If you use AortaCFD in academic work, see `CITATION.cff`.

```bibtex
@software{aortacfd2025,
  title={AortaCFD: Patient-Specific Aortic Blood Flow Simulation},
  author={Wang, Jie},
  year={2025},
  url={https://github.com/JieWangnk/AortaCFD-app}
}
```

## Contact

- Email: jie.wang-2@manchester.ac.uk
- Issues: https://github.com/JieWangnk/AortaCFD-app/issues

## License

[MIT License](LICENSE)
