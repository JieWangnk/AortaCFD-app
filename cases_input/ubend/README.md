# U-bend test case

Single-outlet U-bend pipe — a fast, simple laminar pulsatile case used
across the AortaCFD-app docs for three demos:

1. **Mesh-strategy matrix** — the canonical example for the three CLI
   mesh-resolution methods documented in the top-level
   [`README.md`](../../README.md) and
   [`docs/tutorial/SESSION3_MESH_GENERATION.md`](../../docs/tutorial/SESSION3_MESH_GENERATION.md).
2. **Single-outlet Windkessel auto-calculator** — the simplest
   geometry that exercises `wk_setup.py`'s automatic Z/C/R derivation
   (Murray's-law flow split degenerates to "100 % to the only outlet";
   the calculator still handles PWV / compliance / impedance from the
   patch geometry).
3. **Quick 1-cycle laminar pulsatile demo** — laptop-feasible
   end-to-end run with a synthesised pulsatile inflow and the
   PyVista post-processor.

The case is generated from
[`aortacfd-geomgen`](https://github.com/JieWangnk/aortacfd-geomgen)
spec `single_baseline_v2` — see `baseline_v2.json` and
`geometry.meta.json` for full provenance.

## Geometry summary

| Quantity | Value | Source |
|---|---:|---|
| Inlet diameter | **27.4 mm** | `r_ascending: 13.7` mm × 2 |
| Outlet diameter | **24.4 mm** | `r_descending: 12.2` mm × 2 |
| Arch span | 80.8 mm | `arch_R_c: 40.4` mm × 2 |
| Total length | ~253 mm | `ascending_length + descending_length` |
| Mesh bounding box (m) | `(-0.014, -0.014, -0.15)` to `(0.094, 0.014, 0.103)` | from `log.checkMesh` |

`scale_factor: 0.001` in the config converts the STL files (mm) to
the OpenFOAM internal unit (m).

## Files

| File | Purpose |
|---|---|
| `inlet.stl`, `outlet1.stl`, `wall_aorta.stl` | Split patches used by AortaCFD's mesh + BC pipeline |
| `geometry.meta.json` | Provenance from aortacfd-geomgen (spec name, seed, patch checksums) |
| `ubend_inflow.csv` | Synthesised pulsatile waveform — 5 L/min mean, 14.6 L/min peak (half-rectified sine, T=0.8 s) |
| `config.json` | **Method A — `cells_per_diameter: 15`.** Default config; `python run_patient.py ubend` picks it up with no `--config` flag. |
| `config_target_mm.json` | **Method B — `target_cell_size_mm: 2.0`.** Absolute size in mm, vessel-independent. Invoke explicitly via `--config`. |
| `config_adaptive_span.json` | **Method C — `cells_across_span: 17` with `span_refinement_level: 1`.** Local-lumen target via snappy `insideSpan`. Invoke explicitly via `--config`. |

All three configs share identical physics, boundary conditions, WK
auto-calculator path, simulation_control and run_settings — only
the `mesh` block differs. That makes them a fair head-to-head of
the three CLI mesh-resolution methods documented in
[`docs/user-guide/mesh-specification.md`](../../docs/user-guide/mesh-specification.md)
and [`docs/tutorial/SESSION3_MESH_GENERATION.md`](../../docs/tutorial/SESSION3_MESH_GENERATION.md).

### snappy `featureLevel: 1` is set in all three

The U-bend has no sharp angular features (it's a smooth synthetic
tube + 180° bend), so the snappy `features` block doesn't need the
default `max(surfaceRefinementLevels)` of edge-refinement. Pinning
`featureLevel: 1` saves cells at the patch-stitch lines without
affecting wall-resolution.

The knob comes from `src/templates/snappyHexMeshDict.tpl` and maps
1:1 to the `level` line inside snappy's `features (...)` block. For
real CT-segmented anatomy (with mesh artefacts at vessel ostia /
coarctation throats), leave it unset so it auto-tracks the max
surface-refinement level. For synthetic smooth geometries like this
one, `1` is enough.

See the [snappy-feature-level discussion in mesh-specification.md](../../docs/user-guide/mesh-specification.md)
for the full reference.

## Three demos

### Demo 1 — Mesh-strategy matrix

The three CLI methods (`cells_per_diameter`, `target_cell_size_mm`,
`cells_across_span` + `adaptive_span`) all work on this case. Measured
cell counts at 4 CPU mesh-only:

| Method | Knob | Cell count | Wall |
|---|---|---:|---:|
| A — `cells_per_diameter` | `8`, `[1,1]`, no layers | 27,896 | 15 s |
| B — `target_cell_size_mm` | `2.0`, `[1,1]`, no layers | 109,826 | 22 s |
| C — `cells_across_span` | `12`, `[0,1]`, no layers, `adaptive_span` | 10,850 | 13 s |

Reproduce the matrix by hand from the three JSON snippets in
[`docs/tutorial/SESSION3_MESH_GENERATION.md`](../../docs/tutorial/SESSION3_MESH_GENERATION.md)
— set up three `cases_input/ubend/config_mesh_*.json` files and run
`python run_patient.py ubend --config <cfg> --steps case,mesh --run-name <name>`
for each.

### Demo 2 — Single-outlet Windkessel auto-calculator

`config.json` deliberately **omits** the `outlet_parameters`
block under `boundary_conditions.outlets.windkessel_settings`. That
triggers the auto-calculation path in
[`src/aortacfd_lib/wk_setup.py`](../../src/aortacfd_lib/wk_setup.py):

1. **Inlet area** from `inlet.stl` (auto-detected).
2. **Mean inflow Q** from `ubend_inflow.csv` (≈ 5 L/min).
3. **Murray's-law flow split** → 100 % to `outlet1` (the only outlet).
4. **PWV** from outlet radius via the default Olufsen-style formula.
5. **Per-outlet R, C, Z** derived from systolic (120 mmHg) /
   diastolic (80 mmHg) targets + the above.

The derived values are logged in the run's
`openfoam/logs/log.boundary`. To override them with literature or
SimVascular RCRT values instead, re-add an `outlet_parameters` block
with explicit `{Z, C, R}` per outlet — see
[`cases_input/0014_H_AO_COA/config.json`](../0014_H_AO_COA/config.json)
for that pattern.

### Demo 3 — 1-cycle laminar pulsatile run

The full pipeline on `config.json`:

| Stage | Knob | Output |
|---|---|---|
| Mesh | `cpd: 15`, `[1, 2]`, 5 BL | ~150-200 k cells (~3 min on 4 CPU) |
| Solver | laminar, standard profile, 1 cycle = 0.8 s | 4-6 h laptop / 1-2 h HPC |
| Writes | `writeInterval: 0.016` s + `_keep_last_cycles: 1` | 50 frames of the cycle |

## Quickstart

```bash
cd ~/GitHub/AortaCFD-app
source venv/bin/activate
source /opt/openfoam12/etc/bashrc

# 1. Three-method mesh comparison (mesh-only, cheap — ~1-3 min each)
python run_patient.py ubend --steps case,mesh --run-name mesh_A
python run_patient.py ubend --config cases_input/ubend/config_target_mm.json \
    --steps case,mesh --run-name mesh_B
python run_patient.py ubend --config cases_input/ubend/config_adaptive_span.json \
    --steps case,mesh --run-name mesh_C

# Compare resulting cell counts
for run in mesh_A mesh_B mesh_C; do
    cells=$(grep -E "^cells:" output/ubend/$run/openfoam/logs/log.checkMesh | tail -1)
    echo "$run  $cells"
done

# 2. Full 1-cycle run with auto-calculated Windkessel (default Method A)
python run_patient.py ubend --run-name 1cycle_wk

# 3. Inspect the auto-derived Windkessel parameters
grep -E "PWV|outlet1.*Z|outlet1.*R|outlet1.*C" \
    output/ubend/1cycle_wk/openfoam/logs/log.boundary

# 4. Render velocity / WSS / pressure with the PyVista backend
PYTHONPATH=src python -c "
from aortacfd_lib.post_processor_pyvista import post_process
post_process('output/ubend/1cycle_wk')
"
ls output/ubend/1cycle_wk/Images/
```

## Regenerating the inflow CSV

The shipped `ubend_inflow.csv` is a synthesised half-rectified sine
calibrated for the actual 27.4 mm inlet (`r_ascending: 13.7` mm × 2).
To regenerate with different parameters:

```python
import numpy as np, pandas as pd

R_INLET_M = 0.0137                 # m — matches r_ascending in baseline_v2.json
A = np.pi * R_INLET_M**2
CO_MEAN_LPM = 5.0                  # target cardiac output, L/min
T_CYCLE = 0.8                      # s

Q_MEAN = CO_MEAN_LPM * 1e-3 / 60
Q_PEAK = Q_MEAN / 0.343            # for half-rectified sine duty
t = np.linspace(0, T_CYCLE, 81)
q = Q_PEAK * np.maximum(0, np.sin(np.pi * t / 0.4)) * (t < 0.4)
q = q + 0.05 * Q_PEAK * (t >= 0.4)
pd.DataFrame({"Time": t, "Flowrate": q}).to_csv(
    "ubend_inflow.csv", index=False, float_format="%.6e")
```

## Caveats

- The inflow is **synthetic**, not patient-measured — fine for
  testing pipeline mechanics, not for physiology claims.
- The WK auto-calculator's PWV uses a generic Olufsen-style formula
  scaled by outlet radius. For publication-quality numbers,
  override with explicit `outlet_parameters` derived from
  measurements or a tuned 1-cycle calibration loop.
- Laptop wall time for the full run (~150 k cells × 1 cycle) is
  4-6 h; not interactive. Use the mesh-only + ship-to-HPC pattern
  (see [`docs/workshop/lesson_06_hpc.md`](../../docs/workshop/lesson_06_hpc.md))
  for production runs.
