# Internal technical references

The documents in this directory are deep-technical references — solver-internals,
profile-evidence, mesh-parameter studies. They're kept in version control for
maintainers and reviewers, but they're **not the first thing a new user needs**.

For first-time users, start with the top-level [`README.md`](../../README.md)
and the [tutorial](../tutorial/README.md).

## What's in here

| File | Purpose |
|---|---|
| `BACKFLOW_STABILIZATION_ANALYSIS.md` | Why the Windkessel backflow stabilisation (`betaT`, `betaN`) exists and how it works |
| `MESH_PARAMETER_STUDY.md` | Layer-count and cells-per-diameter parameter studies that justify the defaults |
| `MESH_SPECIFICATION_GUIDE.md` | Detailed knob-by-knob guide to mesh specification (advanced users) |
| `PIMPLE_SOLVER_SETTINGS.md` | PIMPLE algorithm settings + non-orthogonal corrector justification |
| `PROFILE_SETTINGS_EVIDENCE.md` | Evidence-based defaults for the three numerics profiles (`robust`, `standard`, `precise`) |
| `REGENERATE_NUMERICS_USAGE.md` | Mesh-adaptive regenerate-numerics workflow (experimental) |
