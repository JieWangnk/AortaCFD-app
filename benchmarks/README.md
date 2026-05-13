# AortaCFD Benchmark Cases

Quick validation cases to verify your installation produces correct results.

## Quick validation (~1 hour on 4 cores, ~20 min on 8 cores)

```bash
python run_patient.py BPM120 --config cases_input/BPM120/config_tutorial_coarse.json --steps all
```

This runs 1 cardiac cycle on a coarse mesh (~110K cells, cpd=12, 4 cores).

### Expected outputs (BPM120 coarse, standard profile)

| Metric | Expected | Tolerance |
|--------|----------|-----------|
| Mesh cells | ~110K | cpd=12 with 3 boundary layers |
| Simulation completes | 1 cycle (0.5s) | Must not diverge |
| P_sys / P_dia | ~140 / 65 mmHg | Reasonable systolic/diastolic range |
| Peak systolic ΔP (inlet→outlet4) | ~44 mmHg | +/-20% (coarse mesh, 1 cycle) |
| postProcessing | `inletPressure/`, `outlet*Pressure/`, `wallShearStress/` | Files must exist |
| Wall time | ~1.7 hrs (4 cores) | Hardware dependent |

Note: 1-cycle results differ from 3-cycle production values because the Windkessel
capacitor has not fully equilibrated. This is expected and not a failure.

## Production benchmark (~4 hours on 32 cores)

```bash
python run_patient.py BPM120 --steps all
```

**To reproduce the paper-reference mesh:**

```bash
python run_patient.py BPM120 --config cases_input/BPM120/config_paper_reference.json --steps all
```

### Expected outputs (BPM120 standard, paper reference)

| Metric | Expected | Source |
|--------|----------|--------|
| Pressure drop (cycle-avg) | 11.26 mmHg | Standard profile, Table 3 in Wang et al. |
| TAWSS p99 | 14.12 Pa | Standard profile, Table 3 |
| P_sys / P_dia | ~142 / 65 mmHg | Windkessel 120/80 target |

> **Mesh-cell investigation (verified 2026-05-13):** the paper's "~1.9M cells" is achievable via two orthogonal levers — `cells_per_diameter` (bulk uniform refinement) and `surfaceRefinementLevels` (near-wall refinement). Empirical scan on BPM120 (mesh-only runs verified on a laptop, no solver):
>
> | `cells_per_diameter` | `surfaceRefinementLevels` | Final cells | Mesh character |
> |---|---|---|---|
> | 15 (`config.json` default) | [1, 2] | 246,151 | coarse everywhere — fast smoke test |
> | **15** | **[2, 3]** (`config_paper_reference.json`) | **1,100,339** | **coarse bulk + fine near walls — physically meaningful for WSS/coarctation** |
> | 30 | [1, 2] | 1,170,935 | uniform finer (bulk-heavy) |
> | 40 | [1, 2] | 2,223,645 | uniform much finer (bulk-heavy) |
>
> The two levers produce **fundamentally different mesh character at similar cell counts:**
> - `cpd=30` + `[1, 2]` ≈ `cpd=15` + `[2, 3]` ≈ 1.1-1.2M cells
> - But `[2, 3]` puts cells *where they matter* (boundary layer, coarctation throat) while `cpd=30` distributes them uniformly across the bulk. For cardiovascular CFD this matters a lot — WSS sensitivity is dominated by near-wall resolution, not bulk resolution.
>
> **To reproduce the paper-reference mesh:** use `cases_input/BPM120/config_paper_reference.json` (cpd=15 + `[2, 3]` → ~1.1M cells). Slightly below the paper's 1.9M cell count but the more physically meaningful interpretation of the paper's intent.
>
> The `adaptive_span` strategy with `default_cells_across_span: 16` is **not** the relevant lever — it produces ~241-317K cells regardless of span value because the algorithm trades blockMesh background coarseness against local span refinement.

### Scheme sensitivity (paper values, change one line in JSON)

Run the same case with `"profile": "robust"` and `"profile": "precise"`:

| Profile | Pressure drop | TAWSS p99 | Wall-clock (200 cores) |
|---------|--------------|-----------|------------------------|
| Robust | 10.82 mmHg | 17.88 Pa | 23.5 hrs |
| Standard | 11.26 mmHg | 14.12 Pa | 29.0 hrs |
| Precise | 11.32 mmHg | 13.99 Pa | 33.8 hrs |

**Variability between profiles:**
- Pressure drop: max deviation **3.9 %** (robust vs standard). Half-range / mean = ±2.2 %.
- TAWSS p99: max deviation **26.6 %** (robust gives a sharper resolved peak at the coarctation throat due to first-order numerical diffusion). Half-range / mean = ±12.7 %.

> The TAWSS spread is the larger one and is what scheme sensitivity actually means here — the same simulation gives a 26 %-different TAWSS p99 depending on numerics profile, even though pressure drop is stable to ±4 %. Use `standard` for clinical comparison; `precise` for LES; `robust` only for debugging convergence. Don't compare TAWSS across profiles without flagging this.

## Multi-case portability

```bash
python run_patient.py 0014_H_AO_COA --steps all
python run_patient.py VOL04 --steps all
```

These cases use different anatomies, inlet types (CSV vs MRI-mapped), and outlet configurations. All should complete from a single JSON config without manual OpenFOAM editing.

## What these benchmarks prove

- The pipeline installs and runs correctly on your system
- Mesh generation, boundary conditions, and solver produce physically reasonable outputs
- Profile switching works (single-line config change)
- Results are within the documented sensitivity bounds

## What these benchmarks do NOT prove

- Mesh independence for YOUR geometry (run your own convergence study)
- Accuracy of automated Windkessel for YOUR anatomy (verify against clinical data)
- WSS accuracy (carries +/-14-32% combined sensitivity; see paper)
