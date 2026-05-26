# AortaCFD

![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)
![Tests](https://img.shields.io/badge/tests-2263%20passing-success.svg)
![OpenFOAM](https://img.shields.io/badge/OpenFOAM-12-orange.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
[![DOI](https://zenodo.org/badge/826315242.svg)](https://doi.org/10.5281/zenodo.20184620)

Automated OpenFOAM 12 workflow for patient-specific aortic CFD. Takes case
geometry (STL patches) and a JSON config, builds the OpenFOAM case,
generates the mesh, applies inlet and outlet boundary conditions, runs
the solver, and exports hemodynamic quantities of interest (TAWSS, OSI,
RRT, pressure drop) with run reports.

```bash
# 60-second quick start (assumes Python 3.10+, OpenFOAM 12, and Blender are installed)
git clone https://github.com/JieWangnk/AortaCFD-app.git && cd AortaCFD-app
python3 -m venv venv && source venv/bin/activate && pip install -e .
source /opt/openfoam12/etc/bashrc
bash scripts/install_windkessel_of12.sh   # build the modularWKPressure BC

python run_patient.py BPM120              # ships with the repo — pediatric coarctation reference case
```

## Documentation

| What you want to do | Where to go |
|---|---|
| Configure a run (every key explained, with examples) | [`docs/user-guide/configuration.md`](docs/user-guide/configuration.md) |
| Tune the mesh (cells/D, target size, span) | [`docs/user-guide/mesh-specification.md`](docs/user-guide/mesh-specification.md) |
| Add boundary layers (auto y+ or manual) | [`docs/user-guide/boundary-layers.md`](docs/user-guide/boundary-layers.md) |
| Read mesh-quality caveats before trusting results | [`docs/user-guide/mesh-quality-warnings.md`](docs/user-guide/mesh-quality-warnings.md) |
| Regenerate numerics from existing mesh quality | [`docs/user-guide/regenerate-numerics.md`](docs/user-guide/regenerate-numerics.md) |
| Learn the pipeline end-to-end on one canonical patient | [`docs/tutorial/`](docs/tutorial/README.md) — 9-session course |
| Run parametric studies / cohorts | [`docs/workshop/`](docs/workshop/README.md) — 6 lessons + cheat sheet |
| Pick a starter config | [`examples/`](examples/README.md) — `golden_base`, `standard`, `minimal`, `full`, `per_outlet` |

---

## Requirements

- Linux (Ubuntu 20.04+)
- Python 3.10 / 3.11 / 3.12
- OpenFOAM 12 (Foundation version, not ESI)
- ParaView (optional, for visualization)

## Installation

```bash
git clone https://github.com/JieWangnk/AortaCFD-app.git
cd AortaCFD-app

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .                  # runtime
pip install -e ".[dev]"           # add tests + linting (optional)
```

### OpenFOAM 12

Install OpenFOAM 12 from the Foundation:

```bash
# Ubuntu 22.04 example — see openfoam.org for other distros
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key > /etc/apt/trusted.gpg.d/openfoam.asc"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt-get update && sudo apt-get install -y openfoam12
source /opt/openfoam12/etc/bashrc
```

If OpenFOAM lives elsewhere, point at it with `AORTACFD_OPENFOAM_BASHRC` or the Foundation's own `FOAM_BASHRC`.

### Windkessel boundary condition

The `3EWINDKESSEL` outlet BC is a custom library that must be compiled once after OpenFOAM is installed:

```bash
bash scripts/install_windkessel_of12.sh
```

The script builds the BC into `$FOAM_USER_LIBBIN`. Skipping it makes the solver fail at startup with `unknown patch type modularWKPressure`.

---

## Case Layout

Each case lives under `cases_input/<case_id>/`. To run your own data,
create a directory with the same layout:

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

STLs are in millimetres; the workflow scales to metres via `scale_factor: 0.001`
in config. STL naming must match `geometry.*_keywords_ordered` in `config.json`.

### Sample cases shipped with the repo

| Case | Description | Inlet | Outlets |
|---|---|---|---|
| `BPM120` | Pediatric aortic coarctation, published reference (Wang et al.) | TIMEVARYING from CSV | 4 × 3EWindkessel |
| `0014_H_AO_COA` | Pediatric coarctation from SimVascular Vascular Model Repository | TIMEVARYING from CSV | 5 × 3EWindkessel |
| `VOL04` | Healthy adult aorta; demonstrates `MAPPED_PROFILE` inlet | `MAPPED_PROFILE` | 4 × 3EWindkessel |
| `ubend` | Single-outlet synthetic U-bend; demonstrates the Windkessel auto-calculator (Murray's law) | TIMEVARYING from synthesised CSV | 1 × 3EWindkessel |

All four run out of the box with `python run_patient.py <case_id>`.

---

## Quick Start

```bash
# List available cases
python run_patient.py --list

# Run a complete case
python run_patient.py BPM120

# Custom output folder, custom config
python run_patient.py BPM120 --run-name baseline_standard --config config_mesh_fine.json

# Coarse-mesh smoke test
python run_patient.py BPM120 --quick

# Re-run post-processing on an existing run
python run_patient.py --postprocess output/BPM120/run_xxx

# Show every workflow step + dependency
python run_patient.py --list-steps
```

## Workflow steps

AortaCFD breaks the simulation into named steps. Run them individually, in
combinations, or all together (default):

| Step | Description |
|------|-------------|
| `case` | Create case structure, scale geometry, write OpenFOAM dictionaries |
| `mesh` | Run blockMesh, surfaceFeatures, snappyHexMesh, checkMesh |
| `boundary` | Prepare inlet flow data, set up outlet BCs, write `0/` files |
| `regenerate-numerics` | Rewrite `fvSchemes`/`fvSolution` based on mesh quality |
| `solver` | Run `foamRun` (parallel decomposition if configured) |
| `reconstruct` | Reconstruct parallel case from processor directories |
| `postprocess` | Compute hemodynamic metrics (TAWSS, OSI, RRT) and export QoIs |
| `paraview` | Render velocity / WSS / pressure PNGs |

```bash
python run_patient.py BPM120 --steps case,mesh,boundary    # stop before solver
python run_patient.py BPM120 --update output/BPM120/run_xxx --steps boundary,solver
```

Approximate runtimes for BPM120 on 8 cores: `case` <5 s, `mesh --quick` 5-15 min,
`mesh` production 20-60 min, `solver` 0.5-3 h per cycle, `postprocess` 1-5 min.

---

## Minimal config

```json
{
  "case_info": {"patient_id": "MY_CASE"},
  "physics":   {"model": "laminar"},
  "numerics":  {"profile": "standard"},
  "mesh":      {"goal": "routine_hemodynamics"},
  "geometry": {
    "inlet_keywords_ordered": "inlet",
    "outlet_keywords_ordered": ["outlet1", "outlet2"],
    "wall_keywords_ordered": "wall_aorta",
    "scale_factor": 0.001
  },
  "boundary_conditions": {
    "inlet":  {"type": "CONSTANT", "cardiac_output": 5.0, "profile": "parabolic"},
    "outlets": {"type": "3EWINDKESSEL",
                "windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}},
    "walls":  {"type": "no_slip"}
  },
  "simulation_control": {"end_time": 1.0},
  "run_settings":       {"solution_type": "serial"}
}
```

Full reference (every key, every option, troubleshooting) lives in
[`docs/user-guide/configuration.md`](docs/user-guide/configuration.md).
Pick a starter from [`examples/`](examples/README.md).

---

## Mesh sizing — pick one method

| Method | Knob | Best for |
|---|---|---|
| Goal preset (default) | `mesh.goal: "pressure_fast" / "routine_hemodynamics" / "wall_sensitive"` | New users; sensible defaults |
| Anatomy-adaptive | `mesh.cells_per_diameter: 15` | Scales sensibly across patient sizes |
| Absolute | `mesh.target_cell_size_mm: 1.5` | Mesh-independence studies |
| Span-targeted | `mesh.SNAPPY_SETTINGS.cells_across_span: 12` + `mesh_strategy: "adaptive_span"` | Branched geometries with mixed diameters |

Detailed comparison, validation table, and tuning guidance:
[`docs/user-guide/mesh-specification.md`](docs/user-guide/mesh-specification.md).

---

## Batch execution

```bash
python run_batch.py                                           # all cases in cases_input/
python run_batch.py --cases BPM120 0014_H_AO_COA --workers 2  # selected, limited parallelism
python run_batch.py --config-list MY_CASE:config_mesh10.json MY_CASE:config_mesh14.json  # mesh sweep
python run_batch.py --slurm --cluster-conf scripts/hpc/csf3.conf    # generate SLURM array
```

QoIs from the current batch are aggregated into `output/cohort_comparison.csv`.
HPC tokens and SLURM templates: [`scripts/hpc/README.md`](scripts/hpc/README.md).

### Reset working tree

```bash
make clean-all                  # dry-run: shows what would be removed
make clean-all CONFIRM=yes      # actually removes output/, caches, build artefacts
```

Preserves `cases_input/`, the venv, and the source — only regenerable artefacts are removed.

---

## Output

```text
output/<case_id>/<run_name>/
├── openfoam/                    OpenFOAM case directory (mesh, fields, logs)
├── reports/
│   ├── merged_config.json       Full runtime configuration (reproducibility)
│   ├── mesh_audit.json          Post-mesh QC (quality, resolution proxy, verdict)
│   ├── simulation_setup_report.txt
│   └── inlet_audit.json         Inlet BC audit trail
├── results/
│   ├── qoi_summary.json         Hemodynamic QoIs (structured)
│   └── qoi_summary.csv          Hemodynamic QoIs (flat)
└── summary.json
```

QoI definitions: `pressure_drop_mean_mmhg`, `tawss_p99_pa`, `tawss_p95_pa`,
`wss_p99_pa`, `osi_mean_masked`, `rrt_p99_per_pa`, `rrt_p95_per_pa`.
Percentiles (p99, p95) are preferred over `max` because max WSS is
sensitive to mesh-topology artefacts.

---

## Testing

```bash
pytest tests/ -q -m "not slow and not e2e and not benchmark"   # fast subset (~30 s)
pytest tests/ -q                                                # everything except marked-slow
pytest tests/ --cov=src --cov-report=html                       # with coverage
```

See [`tests/README.md`](tests/README.md) for marker definitions and test categories.

---

## Project structure

```text
AortaCFD-app/
├── src/                         CFD library + workflow + CLI
├── tests/                       2263 tests
├── docs/                        User guide + tutorial + workshop
├── examples/                    Config templates
├── cases_input/                 Patient case data (STL + config)
├── output/                      Simulation results (generated)
├── scripts/                     Utility + HPC scripts
├── run_patient.py               Single-case entry point
└── run_batch.py                 Batch / parallel runner
```

---

## Citation

If you use AortaCFD in academic work, please cite both the software (via
the Zenodo DOI for the version you used) and any peer-reviewed paper
this repository underlies. The Zenodo concept DOI in the badge always
resolves to the latest archived version; pin a specific version's DOI
in your bibliography:

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

GitHub's "Cite this repository" button reads [`CITATION.cff`](CITATION.cff)
and offers ready-to-paste APA / BibTeX.

## Contributing

Bug reports, feature requests, and pull requests welcome. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for dev-environment setup,
test/lint commands, and PR conventions; [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
for community guidelines.

## Contact

- Email: jie.wang-2@manchester.ac.uk
- Issues: https://github.com/JieWangnk/AortaCFD-app/issues

## License

[MIT License](LICENSE)
