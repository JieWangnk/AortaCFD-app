# Mesh Quality Guide

## Overview

This guide documents the validated mesh resolution settings for AortaCFD. All configurations have been tested and pass OpenFOAM mesh quality checks (skewness < 4.0, non-orthogonality < 70).

**Validation Date:** October 2, 2025
**OpenFOAM Version:** 12
**Test Case:** patient1 (complex aortic geometry with 4 outlets)

---

## Validated Mesh Configurations

### Summary Table

| Resolution | Cells | Skewness | Non-Ortho | Status | Use Case |
|------------|-------|----------|-----------|--------|----------|
| **COARSE** | ~8-10k | 3.62 | 60.94 | ✅ PASS | Quick tests, geometry checks |
| **MEDIUM** | ~40-50k | 3.58 | 64.63 | ✅ PASS | Standard simulations, parameter studies |
| **FINE** | ~180-200k | 3.60 | 64.98 | ✅ PASS | High-fidelity simulations, publication |

---

## Resolution Settings

### COARSE Resolution

**Purpose:** Fast meshing for geometry validation and quick parameter sweeps.

**BlockMesh Settings:**
- `target_cell_size_mm`: 1.8
- `cells_per_diameter` (inlet): 8
- `cells_per_diameter` (branch): 6

**SnappyHexMesh Settings:**
```python
{
    "maxLocalCells": 1_800_000,
    "maxGlobalCells": 2_000_000,
    "nCellsBetweenLevels": 1,
    "featureLevel": 0,                    # No feature refinement
    "surfaceRefinementLevels": [1, 1],    # Uniform level 1
    "resolveFeatureAngle": 60,            # Relaxed feature detection
    "nSmoothPatch": 3,
    "tolerance": 2.0,
    "nSolveIter": 300,
    "nRelaxIter": 5,
    "nFeatureSnapIter": 10,
    "addLayer": 0,                        # No boundary layers
}
```

**Expected Results:**
- Cells: ~8,520
- Max Skewness: 3.62
- Max Non-orthogonality: 60.94
- Mesh generation time: ~30 seconds

---

### MEDIUM Resolution

**Purpose:** Standard resolution for most CFD simulations with good balance of accuracy and computational cost.

**BlockMesh Settings:**
- `target_cell_size_mm`: 1.0
- `cells_per_diameter` (inlet): 15
- `cells_per_diameter` (branch): 12

**SnappyHexMesh Settings:**
```python
{
    "maxLocalCells": 3_800_000,
    "maxGlobalCells": 4_000_000,
    "nCellsBetweenLevels": 2,             # Smoother transitions
    "featureLevel": 0,                    # No feature refinement
    "surfaceRefinementLevels": [1, 1],    # Uniform level 1
    "resolveFeatureAngle": 60,            # Relaxed feature detection
    "nSmoothPatch": 5,                    # Increased smoothing
    "tolerance": 3.0,                     # Relaxed for robustness
    "nSolveIter": 500,                    # Increased iterations
    "nRelaxIter": 8,                      # Increased relaxation
    "nFeatureSnapIter": 10,
    "addLayer": 0,                        # No boundary layers
}
```

**Expected Results:**
- Cells: ~42,186
- Max Skewness: 3.58
- Max Non-orthogonality: 64.63
- Mesh generation time: ~2-3 minutes

---

### FINE Resolution

**Purpose:** High-fidelity simulations for detailed flow analysis and publication-quality results.

**BlockMesh Settings:**
- `target_cell_size_mm`: 0.6
- `cells_per_diameter` (inlet): 22
- `cells_per_diameter` (branch): 18

**SnappyHexMesh Settings:**
```python
{
    "maxLocalCells": 7_200_000,
    "maxGlobalCells": 7_500_000,
    "nCellsBetweenLevels": 3,             # Smoothest transitions
    "featureLevel": 0,                    # No feature refinement
    "surfaceRefinementLevels": [1, 1],    # Uniform level 1
    "resolveFeatureAngle": 60,            # Relaxed feature detection
    "nSmoothPatch": 5,                    # Increased smoothing
    "tolerance": 3.0,                     # Relaxed for robustness
    "nSolveIter": 600,                    # Maximum iterations
    "nRelaxIter": 8,                      # Increased relaxation
    "nFeatureSnapIter": 10,
    "addLayer": 0,                        # No boundary layers
}
```

**Expected Results:**
- Cells: ~184,378
- Max Skewness: 3.60
- Max Non-orthogonality: 64.98
- Mesh generation time: ~5-8 minutes

---

## Key Design Principles

### 1. **Uniform Surface Refinement**
All resolutions use `surfaceRefinementLevels: [1, 1]` (uniform) instead of variable refinement like `[1, 2]` or `[2, 2]`.

**Rationale:** Uniform refinement avoids transition zones between different refinement levels, which can create high-skewness cells.

**Evidence:** When MEDIUM used `[1, 2]`, skewness was 7.98 ❌. With `[1, 1]`, skewness is 3.58 ✅.

### 2. **No Feature Edge Refinement**
All resolutions use `featureLevel: 0` (disabled).

**Rationale:** Feature edge refinement combined with moderate blockMesh resolution creates problematic cells at feature intersections.

**Evidence:** When FINE used `featureLevel: 1` with `[2, 2]` refinement, skewness was 7.24 ❌. With `featureLevel: 0`, skewness is 3.60 ✅.

### 3. **Progressive Smoothing for Finer Meshes**
Finer meshes require more smoothing iterations to achieve quality:

| Resolution | nSolveIter | nCellsBetweenLevels | nSmoothPatch |
|------------|------------|---------------------|--------------|
| COARSE     | 300        | 1                   | 3            |
| MEDIUM     | 500        | 2                   | 5            |
| FINE       | 600        | 3                   | 5            |

**Rationale:** Finer blockMesh creates more cells and more complex refinement patterns, requiring more iterations to resolve quality issues.

### 4. **No Boundary Layers (Yet)**
All resolutions currently have `addLayer: 0` (boundary layers disabled).

**Rationale:** Adding boundary layers while maintaining mesh quality requires careful tuning. Current focus is on robust volume mesh.

**Future Work:** Once volume mesh is stable, boundary layers can be added with:
- `nSurfaceLayers`: 2-3
- `expansionRatio`: 1.1-1.2
- `finalLayerThickness`: 0.3-0.5

### 5. **Resolution Control via BlockMesh Only**
The three resolutions use **identical snappyHexMesh settings** (refinement levels, feature detection), with resolution controlled purely by blockMesh cell size:

- COARSE: 1.8 mm
- MEDIUM: 1.0 mm
- FINE: 0.6 mm

**Rationale:** This ensures consistent mesh quality across resolutions. Higher refinement in snappyHexMesh creates quality issues.

---

## Mesh Quality Metrics

### OpenFOAM checkMesh Criteria

| Metric | Acceptable | Excellent | Critical |
|--------|------------|-----------|----------|
| **Max Skewness** | < 4.0 | < 3.0 | > 8.0 fails |
| **Max Non-orthogonality** | < 70° | < 65° | > 75° fails |
| **Min Face Area** | > 0 | > 1e-6 | = 0 fails |
| **Min Volume** | > 0 | > 1e-6 | = 0 fails |
| **Aspect Ratio** | Solver-dependent | < 10 | > 100 problematic |

### Solver-Specific Recommendations

**Laminar Solver:**
- Max non-orthogonality: < 70° ✅
- Max skewness: < 4.0 ✅
- All validated meshes suitable

**RANS Turbulence Models:**
- Max non-orthogonality: < 70° ✅
- Max skewness: < 4.0 ✅
- y+ requirements: 30-300 (wall functions) or < 1 (resolved)
- Boundary layers recommended but not required

**LES (Large Eddy Simulation):**
- Max non-orthogonality: < 65° (stricter) ⚠️
- Max skewness: < 3.0 (stricter) ⚠️
- Requires boundary layers with y+ < 1
- May need FINE or finer resolution

---

## Validation Process

### Test Geometry
- **Patient:** patient1
- **Type:** Complex aortic geometry
- **Inlets:** 1
- **Outlets:** 4
- **Branches:** Multiple curved branches with varying diameters

### Validation Workflow

1. **Generate Mesh:**
   ```bash
   python validation/run_validation.py patient1 --profiles sim_laminar_coarse
   ```

2. **Check Quality Metrics:**
   - Automated checkMesh analysis
   - Skewness, non-orthogonality, aspect ratio
   - Failed cells count

3. **Iterate Settings:**
   - If skewness > 4.0: Increase `nSolveIter`, `tolerance`
   - If non-ortho > 70: Increase `nCellsBetweenLevels`, `nSmoothPatch`
   - If aspect ratio > 20: Adjust blockMesh resolution

4. **Validate Across Resolutions:**
   - Test all three resolutions (COARSE, MEDIUM, FINE)
   - Ensure consistent quality metrics

---

## Troubleshooting

### High Skewness (> 4.0)

**Symptoms:** checkMesh reports "highly skew faces detected"

**Causes:**
1. Variable surface refinement `[1, 2]` or `[2, 2]` creating transition zones
2. Feature edge refinement (`featureLevel > 0`) with moderate blockMesh
3. Insufficient smoothing iterations (`nSolveIter` too low)

**Solutions:**
1. ✅ Use uniform refinement: `surfaceRefinementLevels: [1, 1]`
2. ✅ Disable feature refinement: `featureLevel: 0`
3. ✅ Increase smoothing: `nSolveIter: 500-600`
4. ✅ Relax tolerance: `tolerance: 2.5-3.0`
5. ✅ Add buffer cells: `nCellsBetweenLevels: 2-3`

### High Non-Orthogonality (> 70°)

**Symptoms:** checkMesh reports "non-orthogonality check FAILED"

**Causes:**
1. Boundary layers with poor settings
2. Too aggressive refinement near curved surfaces
3. Insufficient patch smoothing

**Solutions:**
1. ✅ Increase patch smoothing: `nSmoothPatch: 4-5`
2. ✅ Disable boundary layers temporarily: `addLayer: 0`
3. ✅ Increase relaxation: `nRelaxIter: 6-8`

### Failed Cells

**Symptoms:** checkMesh reports "Failed X mesh checks"

**Causes:**
1. Inverted cells (negative volume)
2. Zero-area faces
3. Extreme aspect ratios

**Solutions:**
1. ✅ Check STL geometry for errors
2. ✅ Increase `nCellsBetweenLevels`
3. ✅ Relax `tolerance`
4. ✅ Ensure proper `locationInMesh` point

---

## Performance Characteristics

### Mesh Generation Time

| Resolution | BlockMesh | SurfaceFeatures | SnappyHexMesh | Total |
|------------|-----------|-----------------|---------------|-------|
| COARSE     | < 1s      | ~2s             | ~25s          | ~30s  |
| MEDIUM     | < 1s      | ~5s             | ~90s          | ~2min |
| FINE       | ~2s       | ~15s            | ~300s         | ~6min |

*Times measured on standard workstation (4 cores, 16GB RAM)*

### Simulation Cost Estimates

**Laminar Solver (1 cardiac cycle = 1 second):**

| Resolution | Cells | Time/Iteration | Iterations | Total Time |
|------------|-------|----------------|------------|------------|
| COARSE     | 8.5k  | 0.1s           | 10,000     | ~15 min    |
| MEDIUM     | 42k   | 0.5s           | 10,000     | ~1.5 hours |
| FINE       | 184k  | 2.0s           | 10,000     | ~6 hours   |

**RANS Solver (5 cycles for convergence):**

| Resolution | Cells | Time/Iteration | Total Time (est.) |
|------------|-------|----------------|-------------------|
| COARSE     | 8.5k  | 0.15s          | ~2 hours          |
| MEDIUM     | 42k   | 0.75s          | ~10 hours         |
| FINE       | 184k  | 3.0s           | ~40 hours         |

---

## Best Practices

### For New Geometries

1. **Start with COARSE** to validate geometry and boundary conditions
2. **Check mesh visually** in ParaView before running simulations
3. **Run checkMesh manually** to confirm quality metrics
4. **Test solver stability** with a few time steps before full simulation

### For Parameter Studies

1. **Use MEDIUM** for most parameter variations
2. **Reserve FINE** for final validation and publication
3. **Document mesh independence** by comparing MEDIUM vs FINE results

### For Complex Geometries

1. **Increase `nCellsBetweenLevels`** (2-3) for smoother transitions
2. **Increase `nSolveIter`** (500-800) for better quality
3. **Consider splitting geometry** into regions if quality issues persist

---

## Future Improvements

### Short-term (Next Release)

- [ ] Add boundary layer support with validated settings
- [ ] Test RANS and LES profiles
- [ ] Validate on additional patient geometries
- [ ] Document parallel meshing for FINE resolution

### Medium-term

- [ ] Adaptive mesh refinement in high-gradient regions
- [ ] Automatic mesh quality optimization
- [ ] Wall-resolved LES mesh settings (y+ < 1)
- [ ] Mesh convergence index (MCI) calculations

### Long-term

- [ ] Machine learning for optimal mesh parameter selection
- [ ] Multi-resolution zonal meshing
- [ ] Hex-dominant meshing for improved quality

---

## References

### OpenFOAM Documentation
- [checkMesh User Guide](https://www.openfoam.com/documentation/user-guide/4-mesh-generation-and-conversion/4.4-mesh-checking)
- [snappyHexMesh User Guide](https://www.openfoam.com/documentation/user-guide/4-mesh-generation-and-conversion/4.3-mesh-generation-with-snappyhexmesh)

### CFD Best Practices
- Roache, P.J. (1998). "Verification of Codes and Calculations." AIAA Journal, 36(5), 696-702.
- ASME V&V 20-2009: Standard for Verification and Validation in Computational Fluid Dynamics and Heat Transfer

### AortaCFD-Specific
- [Testing Guide](../TESTING.md)
- [CFD Validation Summary](../CFD_VALIDATION_SUMMARY.md)
- [Resolution Settings Source Code](../src/config/profiles/fragments/resolution.py)

---

## Version History

| Version | Date | Changes | Validated By |
|---------|------|---------|--------------|
| 1.0 | 2025-10-02 | Initial validated settings for laminar solver | Claude + User |

---

**Questions or Issues?** Please open an issue on the [GitHub repository](https://github.com/yourusername/AortaCFD-app/issues).
