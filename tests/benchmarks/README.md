# tests/benchmarks/

Pytest tests that **validate AortaCFD's QoIs against reference values** from
[`benchmarks/expected_values.json`](../../benchmarks/expected_values.json) at
the repo root. Deselected from the default suite by the `benchmark` marker —
they need a real `qoi_summary.json` produced by a full solver run.

Not to be confused with:

- **`benchmarks/`** (repo root) — the **reference data** and a user-facing
  "what to expect when you run BPM120" README. The single source of truth for
  expected QoI values; this directory only consumes it.
- **`examples/`** — JSON config templates to copy when creating a new case.
- **`docs/tutorial/`** — long-form teaching content for one canonical patient.
- **`docs/workshop/`** — parametric-study walkthrough.

## Running

```bash
# Tutorial-coarse benchmark (1 cycle, ~110K cells, ~1h45m on 8 cores)
python run_patient.py BPM120 --config cases_input/BPM120/config_tutorial_coarse.json --steps all
BPM120_TUTORIAL_QOI=output/BPM120/run_YYYYMMDD_HHMMSS/results/qoi_summary.json \
  pytest tests/benchmarks/ -m benchmark -v

# Production benchmark (3 cycles, ~1.1M cells, HPC-only)
BPM120_QOI=output/BPM120/run_YYYYMMDD_HHMMSS/results/qoi_summary.json \
  pytest tests/benchmarks/ -m benchmark -v
```

## What's checked

All tolerances and reference values live in
[`../../benchmarks/expected_values.json`](../../benchmarks/expected_values.json)
— update that file if the reference run changes, not this README.

| Test | QoI | Reference fixture |
|---|---|---|
| `test_pressure_drop_within_tolerance` | `pressure_drop_mean_mmhg` | `cases.BPM120.production_standard` |
| `test_tawss_p99_within_tolerance` | `tawss_p99_pa` | `cases.BPM120.production_standard` |
| `test_qoi_summary_is_complete` | all QoIs non-zero | `cases.BPM120.production_standard` |
| `test_tutorial_pressure_drop_mean` | `pressure_drop_mean_mmhg` | `cases.BPM120.tutorial_coarse` |
| `test_tutorial_wss_p99` | `wss_p99_pa` | `cases.BPM120.tutorial_coarse` |
| `test_tutorial_outlet4_pressure_drop` | `per_outlet_pressure_drop_mmhg.outlet4` | `cases.BPM120.tutorial_coarse` |

If a QoI drifts beyond tolerance, the test fails — **investigate** before
bumping the expected value in `expected_values.json`.
