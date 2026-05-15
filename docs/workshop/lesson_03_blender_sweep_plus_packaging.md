# Lesson 3 — Sweep + package

Goal: generate 10 synthetic aortas varying coarctation severity, then
stamp a default `config.json` on each so they are ready for
`run_patient.py`. ~10 minutes (mostly Blender start-up × 10).

## Block A: 10 cases varying coarctation severity

```bash
cd ~/GitHub/aortacfd-geomgen
python cli.py --spec specs/sweep_severity.json --output /tmp/gen_sweep
```

Output:

```
/tmp/gen_sweep/
  sev_001/ ... sev_010/      # 10 case folders, severity 0.0 → 0.9
    inlet.stl
    outlet1..4.stl
    wall_aorta.stl
    geometry.meta.json
  sweep_manifest.csv         # case_id, status, severity, all other params
  sweep_severity.json        # copy of the spec
```

Inspect the manifest:

```bash
cat /tmp/gen_sweep/sweep_manifest.csv
```

Each row tells you the parameter values for that case.

## Block B: stamp a config template on every case

```bash
cd ~/GitHub/AortaCFD-app
python -m scripts.package_cases /tmp/gen_sweep \
    --config-template examples/templates/config_workshop_quick.json \
    --output cases_input/sweep_demo
```

Now `cases_input/sweep_demo/sev_001..010/` each contain:

- The split STL patches (inherited from Block A)
- `geometry.meta.json` (from Block A)
- `config.json` (from the template, with `outlet_keywords_ordered` auto-set to match the STLs)
- `case.meta.json` (combines geometry meta + packaging meta; Block D reads this)

Sanity check:

```bash
python run_patient.py --list | grep sev_
ls cases_input/sweep_demo/sev_001/
```

The case is now runnable:

```bash
python run_patient.py sev_001 --quick --steps case,mesh   # mesh-only check
```

## Three template options shipped

| Template | Use when |
|---|---|
| `config_workshop_quick.json` | Laptop / workstation demos. Robust numerics, no boundary layers, 1 cycle, ~30 min/case with `--quick`. |
| `config_sweep_default.json` | Production sweeps. Standard numerics, 2-layer BL, 3 cycles, ~hours/case. |
| `config_les_precise.json` | LES research. WALE subgrid, precise numerics, 5-layer BL, days/case on HPC. |

For lesson 4 the workshop-quick template is right; switch to
sweep-default when you're ready for production-quality runs.

## Customising the template per case

If you want per-case overrides (e.g. scale inlet flow rate by inlet
diameter), edit the template after Block B runs, or write your own
template-stamper. The packaged `case.meta.json` carries all the
parameters in `params.<name>` — your custom script can read those and
patch `config.json` accordingly.

## Next

Lesson 4 runs the 10 cases in parallel locally with
`run_batch.py --workers N`.
