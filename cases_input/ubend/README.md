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
| `baseline_v2.stl` | Monolithic STL — visualisation only, not consumed by the pipeline |
| `baseline_v2.json` | Generator arguments (Blender params, segment counts) |
| `geometry.meta.json` | Provenance (spec name, seed, patch checksums, generation timestamp) |
| `config_3cycle.json` | Ready-to-run 1-cycle laminar pulsatile config with WK auto-calculator |
| `ubend_inflow.csv` | Synthesised pulsatile waveform — 5 L/min mean, 14.6 L/min peak (half-rectified sine, T=0.8 s) |

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

The driver script is at `/tmp/mesh_strategy_matrix.py` (not committed;
it's a one-off testing utility) — recreate any time from the three
JSON snippets in
[`docs/tutorial/SESSION3_MESH_GENERATION.md`](../../docs/tutorial/SESSION3_MESH_GENERATION.md).

### Demo 2 — Single-outlet Windkessel auto-calculator

`config_3cycle.json` deliberately **omits** the `outlet_parameters`
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

The full pipeline on `config_3cycle.json`:

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

# 1. Mesh-only first — verify cell count before committing to the long solver run
python run_patient.py ubend \
    --config cases_input/ubend/config_3cycle.json \
    --run-name mesh_check --steps case,mesh

# 2. Full 1-cycle run with auto-calculated Windkessel
python run_patient.py ubend \
    --config cases_input/ubend/config_3cycle.json \
    --run-name 1cycle_wk

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
