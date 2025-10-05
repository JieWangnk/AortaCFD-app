# Mesh Settings Quick Reference

## TL;DR - Use These Settings

All three resolutions **PASS** mesh quality validation (skewness < 4.0, non-ortho < 70°).

```python
# COARSE: Fast testing (8k cells, ~30 sec)
target_cell_size_mm: 1.8
surfaceRefinementLevels: [1, 1]
featureLevel: 0
nSolveIter: 300
tolerance: 2.0
nCellsBetweenLevels: 1

# MEDIUM: Standard simulations (42k cells, ~2 min)
target_cell_size_mm: 1.0
surfaceRefinementLevels: [1, 1]
featureLevel: 0
nSolveIter: 500
tolerance: 3.0
nCellsBetweenLevels: 2

# FINE: High-fidelity (184k cells, ~6 min)
target_cell_size_mm: 0.6
surfaceRefinementLevels: [1, 1]
featureLevel: 0
nSolveIter: 600
tolerance: 3.0
nCellsBetweenLevels: 3
```

---

## Key Principles

✅ **DO:**
- Use uniform refinement `[1, 1]`
- Disable feature edges (`featureLevel: 0`)
- Use relaxed `resolveFeatureAngle: 60°`
- Increase iterations for finer meshes (300→500→600)
- Increase buffer cells for finer meshes (1→2→3)

❌ **DON'T:**
- Use variable refinement `[1, 2]` or `[2, 2]` → causes high skewness
- Enable feature edges with moderate blockMesh → quality issues
- Use sharp feature angle 30° → problematic cells

---

## Validation Results

| Resolution | Cells | Skewness | Non-Ortho | Time | Status |
|------------|-------|----------|-----------|------|--------|
| COARSE | 8,520 | 3.62 | 60.94 | 30s | ✅ PASS |
| MEDIUM | 42,186 | 3.58 | 64.63 | 2min | ✅ PASS |
| FINE | 184,378 | 3.60 | 64.98 | 6min | ✅ PASS |

---

## Full Documentation

- **Complete Guide:** [MESH_QUALITY_GUIDE.md](MESH_QUALITY_GUIDE.md)
- **Validation Results:** [MESH_VALIDATION_RESULTS.md](MESH_VALIDATION_RESULTS.md)
- **Source Code:** [../src/config/profiles/fragments/resolution.py](../src/config/profiles/fragments/resolution.py)
