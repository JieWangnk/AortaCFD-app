---
name: Feature request
about: Suggest a new capability or enhancement
title: '[feature] '
labels: enhancement
assignees: ''
---

## What problem are you trying to solve?

<!-- Describe the cardiovascular CFD problem, not the implementation idea. "I need to model X" rather than "AortaCFD should do Y". -->

## What have you tried with the existing config?

AortaCFD ships ~50 user-facing config keys. Many "I wish AortaCFD could X" turn out to already be doable. Before requesting a new feature, please check:

- [ ] The relevant section of [README](../../README.md) (especially Inlet BC, Outlet BC, Numerics Profiles, Mesh Resolution)
- [ ] The example configs under `examples/`
- [ ] The technical-reference docs under `docs/_internal/` (mesh, PIMPLE, profile evidence)
- [ ] The shipped sample cases under `cases_input/` — sometimes the right config is already there

If none of those covered it, describe what you tried and where it fell short.

## Proposed approach (optional)

<!-- If you have an implementation idea, sketch it. New config keys? New BC type? New CLI flag? Linked to which existing module? -->

## Alternatives considered

<!-- Are there workarounds users could use today? Is this something better handled in a downstream tool (e.g. inlet-mapping-toolkit, ccta-coronary-pipeline)? -->

## Scope

- [ ] Single-config behaviour change (e.g. a new `outlets.type`)
- [ ] New CLI flag
- [ ] New module or workflow step
- [ ] Other

Reminder: AortaCFD's scope is automated case generation + solver orchestration + hemodynamic post-processing. Mesh generation upstream (CCTA → STL) and ML surrogate downstream belong to the sister projects in this workspace.
