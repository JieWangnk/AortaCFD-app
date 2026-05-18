# AortaCFD

![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)
![Tests](https://img.shields.io/badge/tests-2210%20passing-success.svg)
![OpenFOAM](https://img.shields.io/badge/OpenFOAM-12-orange.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
[![DOI](https://zenodo.org/badge/826315242.svg)](https://doi.org/10.5281/zenodo.20184620)

> **Citing this work:** every tagged release gets an archived snapshot + DOI on Zenodo (auto-published from this repo's GitHub Releases). See [`CITATION.cff`](CITATION.cff) for the current version, or click the DOI badge above for all versions.

## How to cite

If you use AortaCFD in academic work, please cite both the software (via the Zenodo DOI for the version you used) and any peer-reviewed paper this repository underlies. A BibTeX entry generated from [`CITATION.cff`](CITATION.cff):

```bibtex
@software{Wang_AortaCFD_2026,
  author  = {Wang, Jie},
  title   = {{AortaCFD: Patient-Specific Aortic Blood Flow Simulation}},
  version = {1.4.1},
  year    = {2026},
  url     = {https://github.com/JieWangnk/AortaCFD-app},
  doi     = {10.5281/zenodo.20184620}
}
```

GitHub's "Cite this repository" button (top right) reads `CITATION.cff` and offers ready-to-paste APA / BibTeX. The badge above uses the Zenodo concept DOI (always resolves to the latest archived version); the BibTeX entry pins to the v1.4.1 DOI specifically.

## Contributing

Bug reports, feature requests, and pull requests welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for dev-environment setup, test/lint commands, and PR conventions; [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for community guidelines.

---

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
pip install -e .                  # runtime
pip install -e ".[dev]"           # runtime + test/lint/security tools
```

`pip install -r requirements.txt` also works — it's a thin shim over `pip install -e .`. Dependencies are declared in `pyproject.toml` (see `CHANGELOG.md` for recent changes).

Verify the install:

```bash
python run_patient.py --version       # → AortaCFD 1.4.1
python run_patient.py --list          # → 0014_H_AO_COA, BPM120, VOL04
```

Run `python run_patient.py --doctor` after install — it checks Python version, importable deps, sample STLs, OpenFOAM sourced, and disk space.

### Installing OpenFOAM 12

OpenFOAM 12 (Foundation version, **not** ESI) must be installed and sourced for the `mesh`, `solver`, and `reconstruct` steps. The `case` and `postprocess` steps work without it — useful for config sanity-checks.

**Ubuntu / Debian** (recommended; uses Foundation's apt repository):

```bash
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key > /etc/apt/trusted.gpg.d/openfoam.asc"
sudo add-apt-repository "deb http://dl.openfoam.org/ubuntu $(lsb_release -cs) main"
sudo apt update
sudo apt install openfoam12
```

**macOS** — Foundation OpenFOAM 12 is not pre-built for macOS; use Docker:

```bash
docker pull openfoamorg/openfoam12-ubuntu:latest
docker run -it -v $(pwd):/case openfoamorg/openfoam12-ubuntu bash
```

**Other distros / from source** — see the official guide: <https://openfoam.org/download/>

Then source it before running the OpenFOAM-dependent steps:

```bash
source /opt/openfoam12/etc/bashrc
```

### HPC / non-default OpenFOAM installs

On HPC clusters where OpenFOAM is sourced from a non-default location, point the workflow at the right `bashrc` via either env variable (checked in this order):

```bash
export OPENFOAM_ENV_PATH=/opt/openfoam12/etc/bashrc      # preferred
# or honour Foundation's own variable:
export foamDotFile=/share/apps/openfoam/12/etc/bashrc
```

`run_patient.py` and `run_batch.py` pick these up automatically — no config edit needed.

### Install the Windkessel boundary condition (required for all three canonical cases)

All three sample cases (`BPM120`, `0014_H_AO_COA`, `VOL04`) use 3-element Windkessel outlets, which depend on a small custom boundary-condition library (`modularWKPressure`) compiled against your OpenFOAM 12 install. Run this once after sourcing OpenFOAM:

```bash
source /opt/openfoam12/etc/bashrc
./scripts/install_windkessel_of12.sh
```

The script builds the BC into `$FOAM_USER_LIBBIN`. If you skip this step, the solver will fail at startup with `unknown patch type modularWKPressure`. If you're only running the `case` step (config sanity-check) you can defer this; you'll need it before any `--steps mesh` or beyond.

---

## Case Layout

Each case lives under `cases_input/<case_id>/`. To run your own data, just create a new directory with the same layout.

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

### Sample cases shipped with the repo

| Case | Description | Inlet | Outlets |
|---|---|---|---|
| `BPM120` | Pediatric aortic coarctation, published reference (Wang et al.) | TIMEVARYING from CSV waveform | 4 × 3EWindkessel |
| `0014_H_AO_COA` | Pediatric coarctation from SimVascular Vascular Model Repository | TIMEVARYING from CSV waveform | 5 × 3EWindkessel |
| `VOL04` | Healthy adult aorta; demonstrates `MAPPED_PROFILE` inlet (pre-mapped per-face velocity snapshots — could be 4D MRI, Doppler, 1D-model output, etc.) | `MAPPED_PROFILE` | 4 × 3EWindkessel |

All three are usable out of the box with `python run_patient.py <case_id>`. Use them as templates for your own patient data — just replace the STLs and flow waveform.

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

# Fast smoke-test run (coarse mesh, shortened simulation time)
python run_patient.py BPM120 --quick

# Update an existing run (re-uses the mesh; requires a completed `mesh` step
# in the target directory)
python run_patient.py BPM120 --update output/BPM120/run_xxx
python run_patient.py BPM120 --update output/BPM120/run_xxx --steps boundary,solver

# Standalone post-processing on a completed run
python run_patient.py --postprocess output/BPM120/run_xxx
```

**Approximate runtimes** for BPM120 (pediatric coarctation, 4-outlet geometry) on 8 cores:

| Step | Time |
|------|------|
| `case` | <5 s |
| `mesh` (`--quick`, ~110k cells) | 5–15 min |
| `mesh` (production, 800k–2M cells) | 20–60 min |
| `solver` (1 cardiac cycle, standard profile) | 0.5–3 h |
| `postprocess` | 1–5 min |

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

AortaCFD defaults to **adaptive span-based meshing**: a coarse blockMesh background with OpenFOAM 12's `insideSpan` refinement to guarantee minimum cells across the vessel lumen. This reduces blockMesh waste by 80-96% versus legacy `cells_per_diameter` while maintaining mesh quality. All defaults are evidence-backed from a 114-case HPC study on patient-specific geometries.

### Configuration levels (simple → advanced)

#### Level 1 — Goal preset (recommended)

```json
{ "mesh": { "goal": "routine_hemodynamics" } }
```

| Goal | Span target | Layers | Surface | Use case |
|------|------------|--------|---------|----------|
| `pressure_fast` | 10 | Off | [0, 1] | Quick screening, pressure gradient |
| `routine_hemodynamics` | 16 | 2 layers | [2, 2] | Production patient-specific runs |
| `wall_sensitive` | 22 | 2 layers | [2, 2] | WSS, OSI, near-wall indices |

#### Level 2 — Explicit resolution

```json
{ "mesh": { "span_target": 20 } }
```

#### Level 3 — Resolution + wall treatment

```json
{ "mesh": { "span_target": 20, "layers": { "mode": "standard" } } }
```

Layer modes: `off` (no layers), `standard` (2 layers, OF-typical quality settings).

#### Level 4 — Fine-tuned layers

```json
{
  "mesh": {
    "span_target": 20,
    "layers": {
      "enabled": true,
      "num_layers": 2,
      "expansion_ratio": 1.2,
      "final_layer_thickness": 0.3
    }
  }
}
```

#### Level 5 — Legacy mode

```json
{ "mesh": { "mode": "legacy", "cells_per_diameter": 15 } }
```

#### Level 6 — Expert (raw OpenFOAM)

```json
{
  "mesh": {
    "SNAPPY_SETTINGS": {
      "cells_across_span": 20,
      "surfaceRefinementLevels": [2, 2],
      "resolveFeatureAngle": 25,
      "maxNonOrtho": 65,
      "parallel": true,
      "nProcessors": 16
    }
  }
}
```

Explicit settings always override presets. `SNAPPY_SETTINGS` maps directly to snappyHexMesh parameters.

### Mesh design rules (from HPC study)

These defaults are based on a 114-case study across BPM120 (coarctation), PAT002 (adult aorta), and VOL04 (large aorta):

- **2 layers instead of 3**: gives higher wall coverage (99.7% vs 47% on PAT002, 29% vs 23% on VOL04)
- **Surface refinement [2, 2]** when layers enabled: [0, 1] gives 0% layer coverage
- **`nRelaxedIter = 0`**: relaxing quality controls from the first layer iteration (timing is not the bottleneck)
- **`finalLayerThickness = 0.3`**: sweet spot — thinner (0.1) gives 0%, thicker (0.6) gives 7%
- **Relaxed thresholds 75/200/12**: moderate relaxation (70/100/8) gives identical results to strict — stronger relaxation needed for any improvement

Layer coverage on patient-specific geometry is geometry-dependent:

| Geometry type | Expected coverage (2 layers) | Notes |
|--------------|------------------------------|-------|
| Moderate complexity | ~100% | PAT002: 99.7% with checkMesh OK |
| Large adult aorta | ~29% | VOL04: coverage limited by arch curvature |
| Coarctation | ~30% | BPM120: additional skewness from stenosis |

### Post-mesh audit

After meshing, AortaCFD writes `reports/mesh_audit.json`:
- checkMesh quality metrics (maxNonOrtho, maxSkewness)
- achieved cells-across-lumen proxy at inlet and each outlet
- verdict: `pass` (ortho<65, skew<4), `warn` (65-70), or `fail` (>70)

---

## Inlet Boundary Conditions

| Type | Description | Data Source |
|------|-------------|------------|
| `CONSTANT` | Steady flow | `cardiac_output`, `flowrate`, or `velocity` in config |
| `TIMEVARYING` | Pulsatile from CSV waveform — pipeline computes spatial profile | `csv_file` with time and flow columns |
| `WOMERSLEY` | Analytical pulsatile from Fourier-decomposed CSV | Computed from flow waveform |
| `MAPPED_PROFILE` | User-supplied pre-mapped per-face per-timestep data (4D MRI, Doppler, 1D model, synthetic — any source) | Directory of OpenFOAM `timeVaryingMappedFixedValue` snapshots; pointed to by `file` or `source_dir` |

> **Note on renaming (v1.2.0):** `MAPPED_PROFILE` was previously called `MRI`. The old name still works but emits a `DeprecationWarning`; it will be removed in v2.0. The path is unchanged — the rename only reflects that this branch consumes pre-mapped boundary data regardless of source modality.

Profile options (computed by `TIMEVARYING` / `CONSTANT`): `plug`, `parabolic`, `womersley`, `wall_distance`, `elliptical`. `MAPPED_PROFILE` doesn't use these — the spatial profile is whatever the source file provides.

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

### Mixed outlet types (per-outlet BC, v1.4.0)

Real cardiovascular configs sometimes need different BC types on different outlets — e.g. three branches modelled with Windkessel plus one outlet pinned to a clinical reference pressure. v1.4.0 supports this directly:

```json
{
  "outlets": {
    "type": "3EWINDKESSEL",                 // default for unspecified outlets
    "windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80},
    "per_outlet": {
      "outlet1": {                          // override: pressure-anchor at IVC reference
        "type": "fixedValue",
        "pressure_mmHg": 80
      },
      "outlet4": {                          // override: zero-gradient for sensitivity study
        "type": "zeroGradient"
      }
      // outlet2, outlet3 inherit the default 3EWINDKESSEL
    }
  }
}
```

Each outlet's effective type resolves in this order (later wins):
1. The default `outlets.type` (applies to outlets not named in `per_outlet`)
2. The `per_outlet[<name>]` override (if present)

**Validator:** unknown outlet names (typos against `geometry.outlet_keywords_ordered`), unknown types, or Windkessel-typed overrides without `windkessel_settings` are rejected at config-build time.

**Windkessel processing:** when only a subset of outlets is Windkessel-typed, `wk_setup` operates only on that subset — Murray's-law flow distribution is computed across the Windkessel outlets only, not over-distributing inlet flow to outlets that aren't pressure-driven.

**Allowed types** for `outlets.type` and `outlets.per_outlet[*].type`:
`3EWINDKESSEL`, `2EWINDKESSEL`, `fixedValue`, `fixedPressure`, `resistance`, `zeroGradient`.

### zeroGradient outlets — steady inlets only

`zeroGradient` outlets do not provide a pressure reference, so the pressure field is only well-posed when the inlet itself is steady. v1.2.0 enforces this at config-build time:

| Inlet | `outlets.type: zeroGradient` |
|---|---|
| `CONSTANT`, `PARABOLIC` | ✅ allowed (pressure field finds equilibrium) |
| `TIMEVARYING`, `WOMERSLEY`, `MAPPED_PROFILE` | ❌ rejected — use `3EWINDKESSEL` or `fixedPressure` |

For steady inlets, you can optionally pin one outlet to a fixed pressure (helps convergence and gives a clinically meaningful reference). The recommended way from v1.4.0 is the per-outlet block above; the legacy `pressure_anchor` shorthand still works but emits a `DeprecationWarning`:

```json
{
  "outlets": {
    "type": "zeroGradient",
    "pressure_anchor": {                   // DEPRECATED in v1.4.0
      "outlet": "outlet1",                 // or "auto" → first outlet patch
      "pressure_mmHg": 80
    }
  }
}
```

Recommended v1.4.0 equivalent (same behaviour, no warning, scales to multiple anchors):

```json
{
  "outlets": {
    "type": "zeroGradient",
    "per_outlet": {
      "outlet1": {"type": "fixedValue", "pressure_mmHg": 80}
    }
  }
}
```

`pressure_anchor` is scheduled for removal in v2.0.

> **Why not allow `pressure_anchor` with a pulsatile inlet?** We tried — empirically, on BPM120's severe pediatric coarctation, even one outlet pinned to 80 mmHg with three unanchored zeroGradient siblings still diverges during systole (FPE in `correctPressure` at t≈0.020s). The single-anchor textbook rule that works on benign geometries doesn't survive coarctation-grade pressure gradients. For pulsatile arterial flows, use `3EWINDKESSEL` (recommended) or `fixedPressure`.

> **Known limitation — zeroGradient outlets on severe-stenosis geometries:** Even the *steady* `CONSTANT` + `zeroGradient` + `pressure_anchor` combination is fragile on BPM120's severe pediatric coarctation. We observed `PIMPLE: Not converged` followed by adaptive-`deltaT` collapse to underflow at t≈0.001 s, regardless of numerics tuning (we tried `nOuterCorrectors` 3→8, `max_co` 1.0→0.5, inlet velocity 0.5→0.2 m/s — none survived more than a fraction of a millisecond). The GAMG pressure solver can't reliably handle the matrix conditioning when an outlet is pressure-unconstrained on this geometry. **Use Windkessel outlets for severe-stenosis cases** (verified to converge across all numerics profiles).

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
| `rrt_p99_per_pa` | 1/Pa | 99th percentile relative residence time |
| `rrt_p95_per_pa` | 1/Pa | 95th percentile relative residence time |

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
python run_batch.py --cases 0014_H_AO_COA BPM120 --workers 2

# Mesh convergence study (same patient, different configs)
python run_batch.py \
  --config-list 0014_H_AO_COA:config_mesh10.json 0014_H_AO_COA:config_mesh12.json 0014_H_AO_COA:config_mesh14.json \
  --workers 2

# Dry run
python run_batch.py --cases 0014_H_AO_COA BPM120 --dry-run
```

After a batch completes, QoIs from the current batch are aggregated into `output/cohort_comparison.csv`.

### Resetting the app

When you're done with a study (or before starting a fresh one) and want to reclaim disk space:

```bash
make clean-all                  # dry-run: shows what would be removed, with sizes
make clean-all CONFIRM=yes      # actually removes output/, caches, build artefacts
```

The reset preserves `cases_input/`, the venv, and the repo source — only regenerable artefacts are removed. Add `INCLUDE_VENV=yes` to also delete `venv/` (rare; rebuild with `make install`).

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

AortaCFD includes 2168 automated tests covering configuration, boundary conditions, meshing, mesh audit, hemodynamics, and workflow integration.

```bash
# Run all tests
PYTHONPATH=src pytest tests/ -v

# With coverage
PYTHONPATH=src pytest tests/ --cov=src --cov-report=html

# Skip slow/OpenFOAM-dependent tests
PYTHONPATH=src pytest tests/ -m "not slow and not e2e"
```

## Documentation

- `CHANGELOG.md` — release notes and migration guide across versions
- `docs/` — deeper technical notes (mesh specification, PIMPLE settings, backflow stabilisation, numerics evidence)
- `docs/tutorial/` — step-by-step tutorial cases
- `examples/` — ready-to-run config templates (`config_minimal.json`, `config_standard.json`, `config_full.json`)
- `benchmarks/README.md` — expected outputs for reference cases

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

If you use AortaCFD in academic work, please cite via `CITATION.cff`.

```bibtex
@software{aortacfd,
  title={AortaCFD: Patient-Specific Aortic Blood Flow Simulation},
  author={Wang, Jie},
  year={2026},
  version={1.1.1},
  url={https://github.com/JieWangnk/AortaCFD-app}
}
```

## Contact

- Email: jie.wang-2@manchester.ac.uk
- Issues: https://github.com/JieWangnk/AortaCFD-app/issues

## License

[MIT License](LICENSE)
