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

> **Mesh-cell investigation (verified 2026-05-13):** the paper's "~1.9M cells" turned out to be a function of `cells_per_diameter`, not the `span_target` notation suggested in earlier versions of this doc. Empirical scaling on BPM120 (mesh-only runs verified on a laptop, no solver):
>
> | `cells_per_diameter` | Final cell count | Wall time (8 cores) |
> |---|---|---|
> | 15 (`config.json` default) | 246,151 | ~2 min |
> | 30 | 1,170,935 | ~9 min |
> | **40** (`config_paper_reference.json`) | **2,223,645** | ~14 min |
>
> Cells scale as `~cpd^2.25` on this geometry (tube-like, surface-driven). The default `config.json` uses **cpd=15** for fast onboarding. To reproduce the paper's Table 3 values, use **`cases_input/BPM120/config_paper_reference.json`** (`cpd=40`, ~2.2M cells — slightly over the paper's 1.9M but within typical mesh-sensitivity tolerance). The `adaptive_span` strategy with `default_cells_across_span: 16` is **not** the lever for this — it produces ~317K cells regardless of span value, because the algorithm trades blockMesh background coarseness against local span refinement.

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
