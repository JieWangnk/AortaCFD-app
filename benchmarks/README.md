# AortaCFD Benchmark Cases

Quick validation cases to verify your installation produces correct results.

## Quick validation (~5 min on 8 cores)

```bash
python run_patient.py BPM120 --config cases_input/BPM120/config_tutorial_coarse.json --steps all
```

### Expected outputs (BPM120 coarse, standard profile)

| Metric | Expected | Tolerance |
|--------|----------|-----------|
| Mesh cells | 30K-50K | Depends on geometry adaptive planner |
| Simulation completes | 3 cycles (1.5s) | Must not diverge |
| Pressure drop (cycle-avg) | ~11 mmHg | +/-20% (coarse mesh) |
| TAWSS computed | Yes | Check `output/BPM120/*/openfoam/postProcessing/wallShearStress/` |

## Production benchmark (~4 hours on 32 cores)

```bash
python run_patient.py BPM120 --steps all
```

### Expected outputs (BPM120 standard, 1.9M cells)

| Metric | Expected | Source |
|--------|----------|--------|
| Mesh cells | ~1.9M | Span target 16, 5 boundary layers |
| Pressure drop (cycle-avg) | 11.26 mmHg | Standard profile, Table 3 in paper |
| TAWSS p99 | 14.12 Pa | Standard profile |
| P_sys / P_dia | ~142 / 65 mmHg | Windkessel 120/80 target |

### Scheme sensitivity (change one line in JSON)

Run the same case with `"profile": "robust"` and `"profile": "precise"`:

| Profile | Pressure drop | TAWSS p99 | Wall-clock (200 cores) |
|---------|--------------|-----------|------------------------|
| Robust | 10.82 mmHg | 17.88 Pa | 23.5 hrs |
| Standard | 11.26 mmHg | 14.12 Pa | 29.0 hrs |
| Precise | 11.32 mmHg | 13.99 Pa | 33.8 hrs |

Pressure varies +/-2.2%. TAWSS varies +/-14%. This is expected.

## Multi-case portability

```bash
python run_patient.py PAT002 --steps all
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
