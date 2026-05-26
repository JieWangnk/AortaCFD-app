# AortaCFD examples

Runnable `config.json` templates you copy into a new case folder. For the
field-by-field reference, see [`docs/user-guide/configuration.md`](../docs/user-guide/configuration.md).

## Configuration tiers

| Config | Profile | Outlets | Inlet | Purpose |
|--------|---------|---------|-------|---------|
| [`config_golden_base.json`](config_golden_base.json) | robust (1st order) | zeroGradient | CONSTANT | Prove geometry + mesh work. Will always converge. |
| [`config_standard.json`](config_standard.json) | standard (2nd order) | 3EWINDKESSEL | TIMEVARYING | Production hemodynamics with pulsatile flow. |
| [`config_minimal.json`](config_minimal.json) | standard | zeroGradient | CONSTANT | Smallest working config (for CI / smoke tests). |
| [`config_per_outlet.json`](config_per_outlet.json) | standard | mixed | TIMEVARYING | Demonstrates `outlets.per_outlet` (v1.4.0+) mixed BC types. |
| [`config_full.json`](config_full.json) | any | any | any | Reference showing every available parameter. |

Workshop / sweep templates live under [`templates/`](templates/):

| Template | Purpose |
|---|---|
| [`templates/config_workshop_quick.json`](templates/config_workshop_quick.json) | Minimal mesh, 1 cycle, robust numerics — designed for laptop demos |
| [`templates/config_workshop_quick_resistance.json`](templates/config_workshop_quick_resistance.json) | Same as above but with resistance outlets (no Windkessel ODE startup) |
| [`templates/config_sweep_default.json`](templates/config_sweep_default.json) | Production-quality config used by `scripts/package_cases.py` for parametric sweeps |
| [`templates/config_les_precise.json`](templates/config_les_precise.json) | LES with `precise` numerics profile and wall-resolved mesh |

## Recommended workflow for a new case

1. Start with `config_golden_base.json` — verify mesh and geometry converge with the cheapest settings.
2. Once that runs, switch to `config_standard.json` — add Windkessel, pulsatile flow, hemodynamics.
3. Consult `config_full.json` when you need an advanced setting; the field reference is in [`docs/user-guide/configuration.md`](../docs/user-guide/configuration.md).

## Fastest way to start

```bash
mkdir -p cases_input/MY_CASE
# Drop in inlet.stl, outlet1.stl, ..., wall_aorta.stl
cp examples/config_minimal.json cases_input/MY_CASE/config.json
# Edit case_info.patient_id, geometry.*_keywords_ordered, boundary_conditions, simulation_control
python run_patient.py MY_CASE --run-name first_test
```

## Case template

[`case_template/`](case_template/) carries one complete case (config + STLs + inflow CSV)
so you can `cp -r examples/case_template cases_input/my_first_case` and run it
without provisioning anything else.

## Where the deep docs live

| Topic | File |
|---|---|
| Every config key, examples, units | [`docs/user-guide/configuration.md`](../docs/user-guide/configuration.md) |
| Mesh resolution: cells/D, target size, span | [`docs/user-guide/mesh-specification.md`](../docs/user-guide/mesh-specification.md) |
| Boundary layers (auto y+ or manual) | [`docs/user-guide/boundary-layers.md`](../docs/user-guide/boundary-layers.md) |
| Regenerating numerics from mesh quality | [`docs/user-guide/regenerate-numerics.md`](../docs/user-guide/regenerate-numerics.md) |
| Mesh-quality warnings (must read before trusting results) | [`docs/user-guide/mesh-quality-warnings.md`](../docs/user-guide/mesh-quality-warnings.md) |
