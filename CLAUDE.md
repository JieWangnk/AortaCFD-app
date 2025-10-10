# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AortaCFD is a patient-specific cardiovascular CFD simulation pipeline for aortic blood flow analysis. It automates the full workflow from geometry to results using OpenFOAM 12 as the CFD solver, supporting advanced physiologically realistic boundary conditions including 3-element Windkessel (3EWK) models.

## Key Commands

### Running Simulations

```bash
# Activate virtual environment first
source venv/bin/activate

# Run patient-specific simulation
python run_patient.py patient1

# Quick test run (reduced iterations)
python run_patient.py patient1 --quick

# Custom configuration
python run_patient.py patient1 --config /path/to/config.json

# List available patient cases
python run_patient.py --list
```

### Testing

```bash
# All tests (362 tests)
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

### Mesh Optimization

```bash
# Stage 1: Geometry-driven mesh (novice-friendly)
python -m mesh_optim stage1 --geometry cases_input/patient1

# Stage 2: Physics-aware RANS mesh (y+ ≈ 1)
python -m mesh_optim stage2 --geometry cases_input/patient1 --model RANS

# Stage 2: Wall-resolved LES mesh
python -m mesh_optim stage2 --geometry cases_input/patient1 --model LES
```

## Architecture Overview

### Core Design Pattern: Task-Based Workflow

The codebase uses a **task orchestration architecture** managed by `WorkflowManager`:

1. **Entry Point** → `run_patient.py` parses CLI arguments
2. **Config Builder** → `src/config/builder.py` merges base + profile + case configs
3. **Workflow Manager** → `src/workflow/manager.py` orchestrates task sequences
4. **Tasks** → `src/workflow/tasks/` execute individual steps (mesh, BC, solver)
5. **Domain Logic** → `src/aortacfd_lib/` contains CFD-specific implementations
6. **Templates** → `src/templates/` Jinja2 templates for OpenFOAM dictionaries

### Configuration System (3-Layer Merge)

Configurations are built by merging three layers (in order):

1. **Base Config** (`src/config/base.py`) - Common defaults
2. **Simulation Profile** (`src/config/profiles/sim_*`) - Solver-specific settings (laminar/RANS/LES, coarse/medium/fine)
3. **Case Config** (`cases_input/<patient>/config.json`) - Patient-specific geometry, BCs, mesh settings

**Merge Function:** `deep_merge()` in `config/builder.py` recursively combines dictionaries (later values override earlier).

### Workflow Commands & Task Sequences

Workflow commands map to task sequences in `workflow/manager.py`:

- `"setup:dict"` - Generate all dictionary files (no mesh needed)
- `"setup:bc"` - Generate boundary condition files (after mesh exists)
- `"run:mesh"` - Execute meshing (blockMesh → snappyHexMesh)
- `"run:solver"` - Execute OpenFOAM solver
- `"createCase"` - Full case setup (dict + mesh + BC)
- `"runAll"` - Complete end-to-end simulation

**Usage Pattern:** Most operations use `"runAll"` for full automation.

## Critical Implementation Details

### Inlet Boundary Conditions

**Four inlet types supported** (set in `boundary_conditions.inlet.type`):

1. **TIMEVARYING** - Time series from CSV (default for patient cases)
   - Requires `csv_file` (path to flow/velocity data)
   - Requires `data_type`: `"flowRate"` or `"velocity"`
   - Requires `profile`: `"plug"`, `"parabolic"`, or `"womersley"`

2. **CONSTANT** - Steady uniform velocity (testing/steady-state)
   - Requires either `velocity` (m/s) **OR** `cardiac_output` (L/min)
   - If `cardiac_output` specified: velocity = CO / (60 × A_inlet)
   - Auto-calculates velocity vector with proper orientation

3. **PARABOLIC** - Steady Poiseuille profile (laminar validation)
   - Requires `velocity` (centerline velocity)

4. **WOMERSLEY** - Pulsatile analytic profile (research)
   - Requires CSV + `profile: "womersley"`

**Cardiac Output Feature:** For CONSTANT inlet, specify `cardiac_output: 5.0` (L/min) instead of velocity for clinical intuitiveness. Implementation in:
- `src/aortacfd_lib/utils/validation.py` (lines 921-954)
- `src/aortacfd_lib/boundary_condition_setup.py` (`_calculate_inlet_velocity_vector()`)
- `src/aortacfd_lib/wk_setup.py` (lines 73-100)

**Key Files:**
- CSV processing: `src/aortacfd_lib/inlet_mapping.py`
- BC setup: `src/aortacfd_lib/boundary_condition_setup.py`
- Validation: `src/aortacfd_lib/utils/validation.py`
- Template: `src/templates/U.tpl`
- Documentation: `INLET_BC_CLINICAL_STRATEGY.md`

### 3-Element Windkessel (3EWK) Outlet Boundary Conditions

**Clinical MAP-based methodology** (6-step protocol):

1. **MAP Calculation:** MAP = DP + (SP-DP)/3
2. **Flow Distribution:** Murray's law (r³), area-based, or user-specified
3. **Total Resistance:** R_total = (MAP - P_v) / Q̄
4. **Proximal Resistance:** R1 = ρ·c/A (from PWV)
5. **Distal Resistance:** R2 = R_total - R1
6. **Compliance:** C = τ / R2

**Configuration:**
```json
"outlets": {
  "type": "3EWINDKESSEL",
  "windkessel_settings": {
    "systolic_pressure": 120,
    "diastolic_pressure": 80,
    "venous_pressure": 0,
    "flow_split": 40,  // Percentage OR dict of ratios
    "flow_split_method": "murray",  // "murray", "area", or "equal"
    "pwv_method": "empirical",
    "tau": 1.8
  }
}
```

**Flow Split with Percentage:**
When `flow_split` is a number (e.g., 40), it means:
- First N-1 outlets share 40% using specified method (Murray/area/equal)
- Last outlet gets remaining 60%

**Implementation Location:**
- Main calculation: `src/aortacfd_lib/wk_setup.py`
- Flow split logic: `_parse_flow_split_percentage()` (lines 325-399)
- Called from: `src/workflow/tasks/setup_tasks.py` (`PrepareBoundaryDataTask`)
- Documentation: `WINDKESSEL_BC_REFERENCE.md`, `FLOW_SPLIT_EXPLANATION.md`

### Geometry Processing

**STL File Discovery:**
- Automatically detects files in `cases_input/<patient>/`
- Naming convention: `inlet.stl`, `outlet1.stl`, `outlet2.stl`, etc., `wall_aorta.stl`
- Discovery logic: `config/builder.py` (`_discover_case_config()`)

**Patch Processing:**
- Calculates areas, normals, centers from STL files
- Uses trimesh library for geometry analysis
- Implementation: `src/aortacfd_lib/utils/patch_processing.py`

**Scale Factor:** Applied consistently (default: 1e-3 for mm → m conversion)

### Mesh Generation

**Two-stage optimization:**

1. **Stage 1 (Inner Loop):** Geometry-driven quality mesh
   - Iterates on surface refinement and boundary layers
   - Target: Good orthogonality, skewness, BL coverage
   - Novice-friendly, no CFD required

2. **Stage 2 (Outer Loop):** Physics-aware QoI mesh
   - Uses Stage 1 as baseline
   - Runs CFD to validate y+, WSS, flow metrics
   - Regime-specific (Laminar/RANS/LES)
   - Production-quality meshes

**Physics-aware features:**
- Actual y+ targeting from patient velocity and geometry
- Distance-based refinement (1.5mm/3.0mm from wall)
- QoI convergence monitoring

**Implementation:** `mesh_optim/` package

## OpenFOAM 12 Specifics

**Solver Command:**
```bash
foamRun -solver incompressibleFluid
```
(Replaces deprecated `pimpleFoam`)

**Windkessel Boundary Condition:**
- Pressure outlets: `modularWKPressure` (requires custom BC library)
- Velocity outlets: `stabilizedWindkesselVelocity`
- Installation: `./scripts/install_windkessel_of12.sh`

**Template Variables:**
- `openfoam_version: "12"`
- `openfoam_major_version: 12`
- Applied in: `config/builder.py` (`_apply_openfoam_12_settings()`)

## Common Development Tasks

### Adding a New Inlet Type

1. Add type to `validation.py` (`VALID_INLET_TYPES`)
2. Implement CSV/parameter handling in `inlet_mapping.py`
3. Update template logic in `src/templates/U.tpl`
4. Add boundary condition setup in `boundary_condition_setup.py`
5. Update documentation in `INLET_BC_CLINICAL_STRATEGY.md`

### Adding a New Workflow Task

1. Create task class inheriting from `BaseTask` (`workflow/base_task.py`)
2. Implement `execute(self, context)` method
3. Register in `WorkflowManager._register_tasks()` (`workflow/manager.py`)
4. Add to appropriate workflow recipe (e.g., `"runAll"`)
5. Write tests in `tests/integration/`

### Modifying Windkessel Calculation

**Key method:** `WkSetup.execute()` in `src/aortacfd_lib/wk_setup.py`

**Calculation flow:**
1. Get inlet/outlet geometry (areas, radii)
2. Calculate mean inlet flow (from CSV or velocity/CO)
3. Determine flow split ratios (Murray/area/equal/user)
4. Calculate outlet flows: Q_i = ratio_i × Q_inlet
5. Compute R_total, R1, R2, C for each outlet
6. Write coefficients to `constant/windkesselProperties`

**When editing:** Preserve units (Pa, m³/s) and ensure flow conservation (Σf_i = 1.0)

### Config Validation

**Validation system:** `src/aortacfd_lib/utils/validation.py`

**Checks:**
- Required fields present
- Valid inlet/outlet types
- Physiological parameter ranges (density, viscosity, CO)
- File existence (STL, CSV)
- Flow split ratio sum = 1.0
- Processor counts, time stepping

**Result format:** Returns `ValidationResult` with errors/warnings

## File Organization Rules

**Input Files:** `cases_input/<patient>/`
- STL geometry files
- CSV inlet data (`BPM*.csv`)
- `config.json` (patient-specific settings)

**Output Files:** `output/<patient>/run_YYYYMMDD_HHMMSS/openfoam/`
- Complete OpenFOAM case structure
- Mesh files in `constant/polyMesh/`
- Solution fields in time directories (`0/`, `0.1/`, etc.)
- Logs: `log.*` files

**Templates:** `src/templates/`
- Jinja2 templates for OpenFOAM dictionaries
- Use `{{ variable }}` syntax
- Context variables set in task classes

**Tests:** Mirror source structure
- `tests/unit/` - Component tests
- `tests/integration/` - Workflow tests
- Root level - End-to-end tests

## Important Constraints

### Inlet Type Handling

**CRITICAL:** Different inlet types require different data processing:

- **TIMEVARYING/WOMERSLEY:** Require CSV processing via `InletMapping`
- **CONSTANT/PARABOLIC:** Skip CSV processing, calculate velocity directly

**Implementation pattern:**
```python
inlet_type = self.inlet_settings.get('type', 'TIMEVARYING').upper()
if inlet_type in ['TIMEVARYING', 'WOMERSLEY']:
    # Process CSV
    inlet_mapper = InletMapping(...)
    inlet_mapper.run()
elif inlet_type in ['CONSTANT', 'PARABOLIC']:
    # Calculate from velocity or cardiac_output
    mean_Q_inlet = calculate_from_velocity_or_CO()
```

**Files that check inlet type:**
- `src/workflow/tasks/setup_tasks.py` (lines 147-169)
- `src/aortacfd_lib/wk_setup.py` (lines 65-102)
- `src/aortacfd_lib/boundary_condition_setup.py` (`_calculate_inlet_velocity_vector()`)

### Flow Split Method Consistency

When `flow_split` is a percentage AND `flow_split_method` is specified:
- MUST apply the method (Murray/area/equal) within first N-1 outlets
- Do NOT default to equal distribution
- Implementation: `wk_setup.py` `_parse_flow_split_percentage()` lines 325-399

### Configuration Merge Order

**MUST respect merge order:** base → profile → case
- Later configs override earlier ones
- Profile-level mesh settings can be overridden by case-level `mesh` key
- Document this when modifying config system

## Documentation References

**Boundary Conditions:**
- `INLET_BC_CLINICAL_STRATEGY.md` - Complete inlet BC specification
- `WINDKESSEL_BC_REFERENCE.md` - 3EWK clinical methodology
- `CONSTANT_INLET_CARDIAC_OUTPUT.md` - Cardiac output-based inlet
- `FLOW_SPLIT_EXPLANATION.md` - Flow split percentage with methods

**Setup & Testing:**
- `README.md` - Main project documentation
- `TESTING.md` - Test suite organization and guidelines
- `QUICKSTART.md` - Fast reference for daily usage
- `SETUP_ENVIRONMENT.md` - Installation guide

**Mesh Quality:**
- `docs/MESH_QUALITY_GUIDE.md` - Validated mesh settings
- `docs/MESH_VALIDATION_RESULTS.md` - Quality metrics
- `validation/README.md` - CFD validation framework

## Git Status Context

Currently on branch: `intelConfig`

**Recent commits focus:**
- Intelligent configuration system
- Workflow API development
- Core architecture for case configuration

**Modified files in this session:**
- `README.md` - Documentation updates
- `config/builder.py` - Configuration system
- `workflow/manager.py` - Workflow orchestration
- New files: `api_server.py`, `workflow_api.py` (untracked)

## Python Environment

**Version:** Python 3.12
**Dependencies:** See `requirements.txt`
**Virtual Environment:** Always use `venv/` (activate with `source venv/bin/activate`)

**Key packages:**
- numpy - Numerical computations
- trimesh - Geometry processing
- jinja2 - Template rendering
- pytest - Testing framework
