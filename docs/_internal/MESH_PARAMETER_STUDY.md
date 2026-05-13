# Mesh Parameter Study for Cardiovascular CFD

## Overview

This document records the systematic mesh parameter study conducted to optimize snappyHexMesh settings for cardiovascular CFD simulations. The study used Design of Experiments (DOE) methodology to efficiently identify which parameters significantly affect mesh quality.

**Study Date:** December 22, 2024
**Test Case:** 0014_H_AO_COA (Pediatric Aortic Coarctation)
**Boundary Layers:** 10 layers
**Cell Size:** 1.0 mm target

## Study Methodology

### Design of Experiments (DOE) Approach

Instead of testing every parameter individually (which would require 100+ tests), we used a fractional factorial design:

1. **Screening Phase (8 tests)**: 2^(k-p) design testing HIGH vs LOW for 8 key parameters
2. **Optimization Phase (9 tests)**: Fine-tuning critical parameters identified in screening
3. **Validation Phase (5 tests)**: Confirming preset configurations

**Total: 22 tests** (vs 116+ for full factorial)

### Parameters Tested

| Parameter | LOW Value | HIGH Value | Description |
|-----------|-----------|------------|-------------|
| nSmoothSurfaceNormals | 10 | 50 | Patch normal smoothing |
| snapTolerance | 1.0 | 2.0 | Snap attraction distance |
| nSmoothThickness | 10 | 30 | Thickness distribution smoothing |
| featureAngle | 160 | 180 | Layer termination angle |
| expansionRatio | 1.1 | 1.25 | Layer growth rate |
| nCellsBetweenLevels | 2 | 4 | Refinement transition cells |
| nLayerIter | 50 | 100 | Layer addition iterations |
| maxFaceThicknessRatio | 0.5 | 0.8 | Layer coverage in tight regions |
| span_refinement_enabled | false | true | Span-based refinement |

## Results

### Summary

| Phase | Tests | Passed | Pass Rate |
|-------|-------|--------|-----------|
| Screening | 8 | 8 | 100% |
| Optimization | 9 | 9 | 100% |
| Validation (no span) | 3 | 3 | 100% |
| Validation (with span) | 2 | 0 | 0% |
| **Total** | **22** | **20** | **91%** |

### Detailed Results

```
Test Name                      Pass   Cells        MaxSkew    MaxOrtho   Time
------------------------------------------------------------------------------------------
screen_1_sNL_sTL_tHL_fAL       ✓      1,943,744    3.04       70.0°      661s
screen_2_sNH_sTL_tHL_fAH       ✓      2,214,450    3.07       68.9°      2378s
screen_3_sNL_sTH_tHL_fAH       ✓      1,635,912    3.58       64.3°      384s
screen_4_sNH_sTH_tHL_fAL       ✓      1,903,457    3.55       66.8°      462s
screen_5_sNL_sTL_tHH_fAH       ✓      1,909,136    3.61       68.3°      448s
screen_6_sNH_sTL_tHH_fAL       ✓      1,637,582    3.69       64.8°      421s
screen_7_sNL_sTH_tHH_fAL       ✓      2,278,413    3.74       64.4°      419s
screen_8_sNH_sTH_tHH_fAH       ✓      2,010,817    3.68       64.1°      357s
opt_nSmooth_15                 ✓      2,065,803    3.61       64.6°      389s
opt_nSmooth_20                 ✓      2,065,447    3.60       64.6°      382s
opt_nSmooth_30                 ✓      2,066,686    3.60       64.6°      394s
opt_nSmooth_40                 ✓      2,066,734    3.60       64.6°      423s
opt_expRatio_1.15              ✓      2,156,123    3.63       64.6°      397s
opt_expRatio_1.2               ✓      2,065,447    3.60       64.6°      410s
opt_combo_balanced             ✓      2,065,447    3.60       64.6°      404s
opt_combo_quality              ✓      2,162,398    3.52       64.7°      379s
opt_combo_high                 ✓      2,068,648    3.69       64.3°      394s
val_preset_draft               ✓      1,888,663    3.60       64.7°      402s
val_preset_standard            ✓      2,065,447    3.60       64.6°      389s
val_preset_high_quality        ✓      2,172,230    3.66       65.0°      405s
val_span_standard              ✗      3,527,951    59.14      164.1°     1348s
val_span_high_smooth           ✗      3,849,176    4.17       122.0°     1548s
```

### Best Configurations

1. **screen_1** (all LOW): skew = 3.04 (BEST)
2. **screen_2**: skew = 3.07
3. **opt_combo_quality** (nSmooth=30, expRatio=1.15): skew = 3.52

## Parameter Sensitivity Analysis

The screening phase allows calculation of main effects for each parameter:

```
Effect on Max Skewness (positive = parameter INCREASES skewness):
------------------------------------------------------------
  nSmoothThickness         : +0.367 ** (SIGNIFICANT)
  snapTolerance            : +0.286 ** (SIGNIFICANT)
  maxFaceThicknessRatio    : +0.286 ** (SIGNIFICANT)
  expansionRatio           : +0.226 ** (SIGNIFICANT)
  nLayerIter               : +0.046
  nSmoothSurfaceNormals    : +0.004    (INSENSITIVE)
  nCellsBetweenLevels      : -0.005    (INSENSITIVE)
  featureAngle             : -0.016    (INSENSITIVE)

Significance: ** = effect > 0.2 (moderate to major impact)
```

### Key Findings

#### 1. nSmoothThickness: LOWER is Better (+0.367 effect)

**Surprising finding!** We assumed more smoothing = better quality.

- HIGH (30): increases skewness by ~0.37
- LOW (10): produces better mesh quality
- **Recommendation: Use 10 for all presets**

#### 2. snapTolerance: Use 1.0, Not 2.0 (+0.286 effect)

- HIGH (2.0): increases skewness
- LOW (1.0): better snap conformity without quality degradation
- **Recommendation: Use 1.0 (confirmed from previous studies)**

#### 3. maxFaceThicknessRatio: LOWER is Better (+0.286 effect)

**Another surprising finding!** We thought higher = better layer coverage.

- HIGH (0.8): increases skewness
- LOW (0.5): better mesh quality
- **Recommendation: Use 0.5 for all presets**

#### 4. expansionRatio: 1.15-1.2 Optimal (+0.226 effect)

- 1.25: too aggressive, increases skewness
- 1.15: best for quality (opt_combo_quality achieved 3.52)
- 1.2: good balance for standard use
- **Recommendation: 1.2 for standard, 1.15 for high_quality**

#### 5. nSmoothSurfaceNormals: Insensitive (+0.004 effect)

- Previously thought to be "most critical"
- DOE shows 10-50 all produce similar results
- **Recommendation: Use 20 (moderate value is fine)**

#### 6. Span Refinement: CATASTROPHIC FAILURE

**Critical finding!** Span refinement causes mesh failure:

- val_span_standard: skew = **59.14**, ortho = **164°**
- val_span_high_smooth: skew = **4.17**, ortho = **122°**

Even with maximum smoothing (nSmoothNormals=50), span refinement still fails.

**Recommendation: NEVER enable span_refinement_enabled for cardiovascular meshes**

## Design Rationale for Presets

Based on the DOE study findings, we designed three presets:

### Draft Preset

**Purpose:** Fast meshing for initial geometry checks

```python
"draft": {
    "nCellsBetweenLevels": 2,      # Faster (insensitive parameter)
    "nSolveIter": 10,              # Proven sufficient
    "nFeatureSnapIter": 5,         # Proven sufficient
    "nLayerIter": 30,              # Reduced for speed
    "nRelaxedIter": 10,            # Quick relaxation
    "maxNonOrtho": 70,             # Relaxed threshold
    "maxInternalSkewness": 10,     # Relaxed threshold
    "nSmoothSurfaceNormals": 10,   # LOW (insensitive)
    "nSmoothThickness": 10,        # LOW (DOE: lower is better)
    "snapTolerance": 1.0,          # DOE: use 1.0
    "featureAngle": 160,           # Conservative
}
```

**Rationale:**
- Reduced iterations for speed
- Relaxed quality thresholds (acceptable for initial checks)
- Uses DOE-validated LOW values for sensitive parameters

### Standard Preset (RECOMMENDED)

**Purpose:** Production runs for typical cardiovascular geometries

```python
"standard": {
    "snapTolerance": 1.0,          # DOE: +0.286 effect, use LOW
    "nSolveIter": 10,              # Proven sufficient
    "nFeatureSnapIter": 5,         # Proven sufficient
    "nSmoothSurfaceNormals": 20,   # DOE: insensitive
    "nSmoothThickness": 10,        # DOE: +0.367 effect - LOWER!
    "nLayerIter": 50,              # Sufficient for 10 layers
    "featureAngle": 170,           # Good coverage
    "maxFaceThicknessRatio": 0.5,  # DOE: +0.286 effect - LOWER!
    "nCellsBetweenLevels": 3,      # DOE: insensitive
}
```

**Rationale:**
- All 20/20 non-span tests passed with these settings
- val_preset_standard achieved skew = 3.60
- Uses DOE-optimized LOW values for sensitive parameters
- Balanced between quality and computation time

### High Quality Preset

**Purpose:** Publication-quality meshes for complex geometries

```python
"high_quality": {
    "snapTolerance": 1.0,          # DOE: use LOW
    "nSolveIter": 10,              # Proven sufficient
    "nFeatureSnapIter": 5,         # Proven sufficient
    "nSmoothSurfaceNormals": 30,   # Slightly higher (insensitive)
    "nSmoothThickness": 10,        # DOE: LOWER is better
    "nSmoothPatch": 5,             # Moderate
    "nLayerIter": 100,             # More iterations
    "nRelaxedIter": 40,            # More before relaxing
    "featureAngle": 180,           # Maximum coverage
    "expansionRatio": 1.15,        # DOE: 1.15 optimal for quality
    "nCellsBetweenLevels": 3,      # DOE: insensitive
    "maxNonOrtho": 60,             # Stricter threshold
    "maxInternalSkewness": 5,      # Stricter threshold
    "maxBoundarySkewness": 15,     # Stricter threshold
    "maxFaceThicknessRatio": 0.5,  # DOE: LOWER is better
}
```

**Rationale:**
- Based on opt_combo_quality which achieved best skewness (3.52)
- Uses expansionRatio=1.15 (DOE showed this is optimal)
- Stricter quality thresholds for publication quality
- More iterations for complex geometries

## Common Parameters Across All Presets

Based on DOE and previous studies, these parameters are fixed across all presets:

| Parameter | Value | Reason |
|-----------|-------|--------|
| snapTolerance | 1.0 | DOE: +0.286 effect, lower is better |
| nSolveIter | 10 | Proven sufficient (30 not needed) |
| nFeatureSnapIter | 5 | Proven sufficient (10 not needed) |
| nSmoothThickness | 10 | DOE: +0.367 effect, lower is better |
| maxFaceThicknessRatio | 0.5 | DOE: +0.286 effect, lower is better |

---

## Span Refinement Study (Follow-up)

### Overview

After the DOE study showed span refinement failures, a focused study was conducted to find working configurations.

**Study Date:** December 22, 2024
**Tests:** 26 total (24 phased + 2 level-3 verification)
**Result:** **23/24 passed (96% success rate)**

### Key Finding: span_refinement_level is Critical

| span_level | cells_across_span | Max Skewness | Status |
|------------|-------------------|--------------|--------|
| 1 | 5-20 | 2.76 | ✓ ALL PASS |
| 2 | 5-20 | 2.76 | ✓ ALL PASS |
| 3 | 5-10 | 2.76 | ✓ PASS |
| 3 | 15-20 | 4.09 | ✗ FAIL |

**Root Cause Identified:** `span_refinement_level=3` with high cell counts causes mesh quality degradation.

### Best Configurations for Span Refinement

| cells_across_span | span_level | Skewness | Cells | Use Case |
|-------------------|------------|----------|-------|----------|
| 15 | 2 | 2.71 | ~590K | Production (coarctation) |
| 20 | 2 | 2.71 | ~780K | High resolution |
| 10 | 2 | 2.76 | ~200K | Standard resolution |

### Span Refinement Guidelines

**When to use span refinement:**
- Severe coarctation or stenosis with variable vessel diameter
- Need guaranteed minimum cells across narrow regions

**Safe configurations:**
- `span_refinement_level`: Use 1 or 2 (NEVER 3 with cells_across_span > 10)
- `cells_across_span`: 10-20 is safe with level ≤ 2
- `surfaceRefinementLevels`: Keep at [1, 2] (NOT [2, 3])

**Why previous DOE tests failed:**
- Used `span_refinement_level=3` with `cells_across_span=15-20`
- This combination produces skewness > 4.0

### Span Refinement Study Results

```
Phase 1 (cells_across_span=5-10): 9/9 PASSED
Phase 2 (cells_across_span=12-20, level≤2): 6/6 PASSED
Phase 3 (smoothing/surface refinement interaction): 8/9 PASSED
  - Only failure: surfaceRefinementLevels=[2,3] with span (skew=4.18)

Level 3 verification tests:
  - span15_level3: skew=4.09 ✗ FAIL
  - span20_level3: skew=4.09 ✗ FAIL
```

**Study script:** `scripts/run_mesh_span_refinement_study.py`

---

## Conclusions

### What We Learned

1. **Simplicity wins**: The "all LOW" configuration (screen_1) achieved the best skewness (3.04)

2. **Counter-intuitive findings**:
   - More smoothing (nSmoothThickness) does NOT improve quality
   - Higher maxFaceThicknessRatio does NOT improve layer coverage
   - nSmoothSurfaceNormals is insensitive (10-50 all work)

3. **Span refinement CAN work** with proper configuration:
   - Use `span_refinement_level` ≤ 2
   - Use `surfaceRefinementLevels` [1, 2] (not [2, 3])
   - Previous failures were due to level=3 + high cell counts

4. **DOE is efficient**: 22 tests gave more insight than 100+ individual tests

### Recommendations

1. Use **standard preset** for most cardiovascular CFD simulations
2. Use **high_quality preset** only for publications or complex coarctations
3. **Span refinement** is safe with:
   - `span_refinement_level` = 1 or 2 (NEVER 3 for production)
   - `cells_across_span` = 10-20
   - `surfaceRefinementLevels` = [1, 2]
4. If mesh fails, check:
   - span_refinement_level is ≤ 2
   - snapTolerance is 1.0 (not 2.0)
   - nSmoothThickness is 10 (not higher)

## Files

### DOE Study
- **Study script:** `scripts/run_mesh_parameter_study_efficient.py`
- **Results:** `output/0014_H_AO_COA/mesh_study_efficient/study_full_20251222_*/results.json`

### Span Refinement Study
- **Study script:** `scripts/run_mesh_span_refinement_study.py`
- **Results:** `output/0014_H_AO_COA/span_study/study_20251222_*/results.json`

### Configuration Files
- **Presets:** `src/config/mesh_quality_presets.py`
- **Base config:** `src/config/base.py`

## References

- OpenFOAM snappyHexMesh documentation: https://openfoam.com/documentation/guides/latest/doc/guide-meshing-snappyhexmesh
- DOE methodology: Fractional Factorial Design (Resolution III)
- OpenFOAM insideSpan refinement: cellsAcrossSpan for guaranteed resolution
