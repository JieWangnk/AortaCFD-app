# tests/

Regression and acceptance test suite for AortaCFD. **You don't need to run any of this to USE AortaCFD** — these tests are for contributors and CI.

For first-time users: start at the [top-level README](../README.md). For maintainers: read on.

## Running the suite

```bash
# Fast subset (default — ~30s, what CI runs on every commit)
PYTHONPATH=src pytest tests/ -q -m "not slow and not e2e and not benchmark"

# Everything except benchmarks (also fast — benchmarks need separate fixtures)
PYTHONPATH=src pytest tests/ -q -m "not benchmark"

# Benchmark validation (requires a real solver run output)
BPM120_TUTORIAL_QOI=output/BPM120/run_XXX/results/qoi_summary.json \
  pytest tests/benchmarks/ -m benchmark
```

## What's in here

Currently **2210 tests** across 70+ files. Categories by purpose:

| Category | Examples | What they validate |
|---|---|---|
| Config / schema | `test_config_schema.py`, `test_config_builder.py`, `test_config_helper.py` | User-facing config keys parse, validate, and merge correctly |
| Mesh setup | `test_mesh_setup.py`, `test_mesh_audit.py`, `test_aortic_axis_estimator.py` | Mesh dictionary generation, quality audit |
| Boundary conditions | `test_boundary_condition_setup.py`, `test_wk_setup.py`, `test_wk_setup_comprehensive.py` | Inlet/outlet BC rendering, Windkessel coefficient computation |
| Workflow | `test_workflow_manager.py`, `test_execution_tasks.py`, `test_base_task.py` | Task orchestration, dependency resolution |
| Hemodynamics | `test_hemodynamics_postprocessor.py`, `test_post_processing.py` | WSS / TAWSS / OSI / RRT computation |
| Integration (config-matrix) | `test_config_matrix.py` | End-to-end config variability — rotates one axis at a time and asserts on rendered OpenFOAM dicts |
| Benchmarks | `benchmarks/test_bpm120_benchmark.py` | Validates produced QoI outputs against reference values from Wang et al. Table 3 |
| User-promise (integration) | `test_user_promises.py` | High-level "does AortaCFD deliver on what the README promises" suite |

## Markers

- `slow` — long-running unit tests (deselected from the fast suite)
- `e2e` — end-to-end tests requiring OpenFOAM solver (deselected by default)
- `benchmark` — paper-validation tests requiring a `qoi_summary.json` fixture from a real solver run (deselected by default)
- `integration` — multi-component but no OpenFOAM (default-selected)

See `pyproject.toml` `[tool.pytest.ini_options]` for the full marker definitions.

## Related files

- [`benchmarks/expected_values.json`](../benchmarks/expected_values.json) — reference QoI values + tolerances for benchmark tests
- [`pyproject.toml`](../pyproject.toml) `[tool.pytest.ini_options]` — full marker definitions and default selection
