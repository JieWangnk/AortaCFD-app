# AortaCFD-app Test Strategy

## User Promises

The app makes five promises to its users:

1. **Automation** — generate a runnable OpenFOAM case without manual dictionary editing
2. **Efficient default mesh** — sensible adaptive meshing out of the box
3. **QC, not just files** — automatic post-mesh audit with clear pass/warn/fail
4. **Reproducibility** — same inputs produce same configuration choices
5. **Useful outputs** — hemodynamic metrics and reports are findable and consistent

Every test should link to at least one of these promises.

## Test Levels

### Layer A — Unit tests (2049 existing)

**Question**: Does each function do the right thing?

Coverage: excellent. 55 test files, 2106 functions across config, mesh,
boundary conditions, physics, numerics, post-processing, Windkessel, audit.

### Layer B — Integration tests (sparse — needs expansion)

**Question**: Do connected components work together?

Key integration paths to test:
- config → mesh planner → dictionary writer → correct snappyHexMeshDict
- mesh strategy routing → actual template output (span vs legacy)
- audit module → execution tasks → report written

### Layer C — End-to-end workflow tests

**Question**: Can a real user task complete start to finish?

Standard workflows:
1. Quick mesh check (case + mesh only)
2. Legacy compatibility (explicit cpd, legacy strategy)
3. Default adaptive span (no mesh params → span auto-enabled)
4. Full pipeline (case → mesh → solver → postprocess)

### Layer D — Regression benchmark tests

**Question**: Did we break what was working?

Permanent comparison set: 18 benchmark cases (G2/G3/G5 × legacy/span)
at `~/OpenFOAM/mchi4jw4-12/mesh_quality_study/aorta_benchmark/`

### Layer E — User acceptance tests

**Question**: Would a real user say this is correct?

Informal review of: error messages, report readability, output organisation.

## Acceptance Criteria

### For mesh-related updates
- [ ] All unit + integration tests pass
- [ ] Adaptive span benchmark still shows expected efficiency
- [ ] Legacy mode still works
- [ ] checkMesh passes on benchmark cases
- [ ] mesh_audit.json written correctly
- [ ] At least one real patient case runs without intervention

### For full workflow updates
- [ ] Case generation works
- [ ] Mesh works
- [ ] Solver completes on standard case
- [ ] Post-processing produces expected outputs
- [ ] No regression in reported metrics beyond tolerance

## Standard Test Cases

### A. Synthetic benchmarks (controlled)
- G2 (arch with branches)
- G3 (coarctation)
- G5 (small vessel)

### B. Real patient-style (practical)
- BPM120 (pediatric coarctation, cpd=15)
- PAT002 (adult aorta, cpd=14)
- PAT003 (infant, nested cpd=15)

### C. Failure cases (robustness)
- Missing patch labels
- Impossible config values
- Corrupted/empty STL
- Extreme span target
- Empty outlet definition

## Design Aim → Evidence Table

| Aim | User value | Test | Success |
|-----|-----------|------|---------|
| Automation | No manual dict editing | Config → case generation E2E | All required files created |
| Efficient mesh | Low waste, good quality | Span benchmark vs legacy | ≥40% blockMesh reduction, checkMesh OK |
| QC exists | Know if mesh is acceptable | Audit written + verdict correct | PASS/WARN/FAIL consistent with thresholds |
| Reproducibility | Same setup = same result | Same case twice, compare outputs | Identical planner choices + report structure |
| Useful outputs | Find results quickly | Post-processing integration test | Metrics + report files always produced |
