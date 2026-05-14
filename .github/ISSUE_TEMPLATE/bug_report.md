---
name: Bug report
about: Something is wrong with AortaCFD. Help us reproduce it.
title: '[bug] '
labels: bug
assignees: ''
---

## Summary

<!-- One sentence: what's broken and why it matters. -->

## Environment

- AortaCFD version: <!-- `python run_patient.py --version` -->
- OpenFOAM version: <!-- `echo $WM_PROJECT_VERSION` — must be 12 -->
- Python version: <!-- `python --version` -->
- OS: <!-- Ubuntu 22.04 / macOS 14 / etc. -->

Paste the full `python run_patient.py --doctor` output here:

```
<paste here>
```

## Reproduction

Minimal config that triggers the bug. **Please base on one of the shipped sample cases** (`BPM120`, `0014_H_AO_COA`, `VOL04`) if you can — debugging your custom case is much harder.

```bash
# Exact commands you ran
python run_patient.py BPM120 --steps case,mesh
```

```json
// Relevant config snippet — at minimum the inlet, outlets, and physics blocks
```

## What happened

<!-- Paste the error message, or describe the wrong output. -->

For solver errors, the first 20 lines of `output/<patient>/run_XXX/openfoam/logs/log.solver` are most useful:

```
<paste here>
```

## What you expected

<!-- What should AortaCFD have produced instead? -->

## Additional context

- Is this geometry-specific? (Severe coarctations behave very differently from healthy aortas — many solver-side issues are geometry pathology, not bugs.)
- Did this work in an earlier version? Which?
- Have you successfully run the canonical sample cases?
