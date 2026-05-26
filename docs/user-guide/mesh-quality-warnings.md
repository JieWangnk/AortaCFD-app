# Mesh Quality: Critical Warnings and Trade-offs

**⚠️ READ THIS BEFORE RELYING ON MESH-ADAPTIVE SYSTEM ⚠️**

---

## The Mesh-Adaptive System is a Safety Net, Not a Solution

The mesh-adaptive solver system **prevents divergence** on imperfect meshes, but **does NOT replace proper mesh generation**.

### What It Does
✅ Stabilizes solver settings based on actual mesh quality
✅ Prevents wasted time on diverging simulations
✅ Allows reasonable results on FAIR quality meshes

### What It Does NOT Do
❌ Make a poor mesh produce accurate results
❌ Replace the need for mesh refinement studies
❌ Compensate for fundamentally flawed geometry

---

## Critical Warning: Poor Mesh = Degraded Accuracy

When the system detects **POOR** or **CRITICAL** mesh quality:

### Automatic Adjustments Introduce Numerical Diffusion

| Adjustment | Stability Gain | Accuracy Cost |
|------------|----------------|---------------|
| **Laplacian**: `corrected` → `limited 0.33` | ✅ Prevents overshoot on non-orthogonal cells | ❌ Introduces diffusion, smears gradients |
| **Relaxation**: p=0.3 → 0.2 | ✅ Prevents oscillations | ❌ Slower convergence, more timesteps |
| **Tolerances**: 1e-6 → 1e-5 | ✅ Achievable on poor mesh | ❌ Less converged solution |
| **More correctors**: 2 → 4 | ✅ Better pressure-velocity coupling | ⚠️ More computational cost |

### Impact on Results

**Wall Shear Stress (WSS)**:
- Poor mesh quality → Smeared gradients near walls
- Limited schemes → Additional diffusion
- **Result**: WSS magnitude may be under-predicted by 10-30%

**Pressure Drop**:
- Non-orthogonal cells → Pressure-velocity decoupling
- Relaxation factors → Slower convergence of pressure field
- **Result**: Pressure drop may be inaccurate by 5-15%

**Flow Patterns**:
- High aspect ratio cells → Poor resolution of cross-flow
- Numerical diffusion → Smoother velocity profiles
- **Result**: Recirculation zones may be missed or smoothed

---

## Grid Convergence Index (GCI) Guidelines

As warned in CFD best practices (https://cfd.university):

> **If a solution shows oscillatory or monotonic divergence as the mesh is refined, you need to revisit the meshing step.**

### What This Means

If you observe:
```
Coarse mesh (skew 2.5): WSS = 5.2 Pa
Medium mesh (skew 4.0): WSS = 4.8 Pa  ← Decreasing (monotonic)
Fine mesh (skew 5.8):   WSS = 4.1 Pa  ← Still decreasing

OR

Coarse mesh (skew 2.5): Pressure drop = 8 mmHg
Medium mesh (skew 4.0): Pressure drop = 12 mmHg  ← Increasing
Fine mesh (skew 5.8):   Pressure drop = 7 mmHg   ← Oscillating!
```

**This is NOT mesh independence.** This indicates:
1. Mesh quality degrading with refinement
2. Numerical schemes becoming more diffusive
3. Underlying mesh generation problem

**Action Required**: Fix snappyHexMesh settings, not solver settings.

---

## Numerical Scheme Trade-offs

From Wolf Dynamics CFD Tips (https://wolfdynamics.com):

> **First-order schemes are bounded and stable but diffusive, whereas second-order methods are accurate but may be oscillatory.**

### What the Mesh-Adaptive System Does

#### GOOD Quality Mesh
```python
Laplacian: "Gauss linear corrected"  # 2nd order, accurate
Gradient: "cellLimited Gauss linear 1.0"  # Minimal limiting
Convection: "linearUpwind"  # 2nd order bounded
```
**Result**: Full 2nd order accuracy maintained

#### FAIR Quality Mesh
```python
Laplacian: "Gauss linear limited corrected 0.5"  # Partial limiting
Gradient: "cellLimited Gauss linear 1.0"  # Same
Convection: "linearUpwind"  # Same
```
**Trade-off**: Slight diffusion near non-orthogonal cells (<5% error)

#### POOR Quality Mesh
```python
Laplacian: "Gauss linear limited corrected 0.33"  # Heavy limiting
Gradient: "cellLimited Gauss linear 0.5"  # Tighter limiting
Convection: "linearUpwind" or "upwind"  # May downgrade to 1st order
```
**Trade-off**: Significant diffusion (10-30% error possible)

#### CRITICAL Quality Mesh
```python
# System recommends switching to 'robust' profile
Convection: "upwind"  # 1st order (highly diffusive)
Laplacian: "limited 0.33"
Gradient: "cellLimited 0.5"
```
**Trade-off**: Results may only be qualitatively correct

---

## When to REMESH Instead of Relying on Adaptive System

### Mandatory Remeshing Scenarios

1. **Wall Shear Stress (WSS) Studies**
   - If skewness >3.0 near walls
   - WSS is highly sensitive to near-wall gradients
   - Diffusive schemes corrupt WSS predictions

2. **Pressure Drop Calculations**
   - If non-orthogonality >70° in narrow regions
   - Pressure-velocity coupling degrades
   - Results may vary by 15%+

3. **Recirculation or Separation**
   - If aspect ratio >50 in regions of interest
   - Flow patterns require good cross-flow resolution
   - Numerical diffusion smooths recirculation

4. **Publication or Clinical Decisions**
   - If mesh quality is FAIR or worse
   - Reviewers will question results from poor meshes
   - Grid independence cannot be demonstrated

### Acceptable Use of Adaptive System

1. **Initial Testing**
   - Exploring new geometries
   - Quick feasibility studies
   - Debugging boundary conditions

2. **Comparative Studies**
   - Comparing multiple geometries with similar mesh quality
   - Trends may be reliable even if absolute values are not

3. **GOOD Quality Meshes**
   - Minor adjustments (1-2 extra correctors) are acceptable
   - Accuracy impact <2%

---

## How to Improve Mesh Quality

If your mesh falls into POOR or CRITICAL tier, **FIX THE MESH** before trusting results:

### snappyHexMesh Quality Improvements

```python
# Increase surface smoothing
"nSmoothSurfaceNormals": 20,  # Was 10 → More smoothing
"nSmoothPatch": 8,  # Was 5
"nSmoothScale": 6,  # Was 4

# Gentler layer growth
"expansionRatio": 1.1,  # Was 1.2 → Less aggressive
"finalLayerThickness": 0.15,  # Was 0.3 → More gradual

# Skip problematic features during layering
"featureAngle": 170,  # Was 150° → Skip sharp edges
"maxFaceThicknessRatio": 0.2,  # Was 0.3 → Thinner ratio

# More quality iterations
"nRelaxIter": 40,  # Was 20 → More flexibility
"nLayerIter": 50,  # Allow more attempts

# Tighter quality thresholds
"maxInternalSkewness": 3.0,  # Reject cells > 3.0
"maxNonOrtho": 65,  # Tighten threshold
```

### Target Metrics for Reliable Results

| Application | Max Skew | Max Ortho | Max Aspect | Profile |
|-------------|----------|-----------|------------|---------|
| **Wall Shear Stress** | <2.0 | <60° | <30 | accurate |
| **Pressure Drop** | <2.5 | <65° | <50 | standard |
| **Flow Patterns** | <3.0 | <70° | <100 | standard |
| **Screening Studies** | <4.0 | <75° | <150 | robust OK |

---

## Verification Requirements

Even with mesh-adaptive adjustments, you MUST perform:

### 1. Grid Convergence Study

Run at minimum **3 mesh levels** with constant refinement ratio (√2 or 2):

```
Coarse:  N cells
Medium:  2N cells (or 2.83N with √2 ratio)
Fine:    4N cells (or 5.66N with √2 ratio)
```

**Calculate GCI** (Grid Convergence Index):
```python
# Richardson extrapolation
p = ln((f_coarse - f_medium) / (f_medium - f_fine)) / ln(r)
# Should get p ≈ 2 for 2nd order methods

GCI_fine = (1.25 * |ε_fine|) / (r^p - 1)
# Should be < 5% for acceptable discretization error
```

**If GCI fails or p < 1**: Your mesh has problems beyond what the adaptive system can fix.

### 2. Mesh Independence Criteria

For each quantity of interest (WSS, pressure drop, flow rate):

```
|Q_fine - Q_medium| / Q_medium < 5%  # Medium-fine difference
|Q_medium - Q_coarse| / Q_coarse < 10%  # Coarse-medium difference
```

**If not satisfied**: Either refine mesh OR accept limited accuracy.

### 3. Quality Metric Trends

Plot skewness, non-orthogonality vs mesh refinement:

```
Coarse:  Skew = 2.0, Ortho = 60°  ✅ Good
Medium:  Skew = 2.3, Ortho = 62°  ✅ Acceptable (slight increase)
Fine:    Skew = 5.1, Ortho = 65°  ❌ BAD (large jump)
```

**If quality degrades significantly with refinement**: Fix mesh generation, don't just use adaptive system.

---

## Configuration: Advanced Controls

### Override Quality Thresholds

For power users who want to customize when adjustments activate:

```json
{
  "numerics": {
    "profile": "standard",
    "mesh_adaptive": true,
    "mesh_adaptive_thresholds": {
      "skewness": {
        "good": 2.0,
        "fair": 3.5,
        "poor": 5.0,
        "critical": 7.0
      },
      "non_orthogonality": {
        "good": 60,
        "fair": 68,
        "poor": 73,
        "critical": 78
      }
    }
  }
}
```

**Warning**: Changing these requires understanding of numerical schemes and mesh quality impacts.

### Override Specific Adjustments

Force specific corrector/relaxation values regardless of mesh quality:

```json
{
  "numerics": {
    "profile": "standard",
    "mesh_adaptive": true,
    "mesh_adaptive_overrides": {
      "max_outer_correctors": 3,  # Cap at 3 even for poor mesh
      "min_p_relaxation": 0.25,  # Don't go below 0.25
      "force_limited_laplacian": false  # Don't use limited schemes
    }
  }
}
```

### Disable for Specific Use Cases

```json
{
  "numerics": {
    "profile": "accurate",
    "mesh_adaptive": false,  # Disable for publication runs
    "justification": "Mesh quality verified with GCI study, using exact schemes for reproducibility"
  }
}
```

---

## Profile Interaction with Mesh-Adaptive System

### How Profiles and Adaptive System Interact

The adaptive system **layers on top** of baseline profiles:

```python
# Profile defines baseline
Profile: "standard"
  → Baseline: 2nd order bounded schemes
  → nOuterCorrectors: 2
  → p relaxation: 0.3

# Mesh-adaptive adjusts FROM baseline
Mesh Quality: POOR
  → nOuterCorrectors: 2 → 4  # Increase from baseline
  → p relaxation: 0.3 → 0.2  # Strengthen from baseline
  → Laplacian: corrected → limited 0.33  # Downgrade from baseline
```

### Profile-Specific Behavior

#### "robust" Profile
- **Baseline**: Already very stable (1st order, heavy relaxation)
- **Adaptive**: Minimal further adjustment needed
- **Use when**: Mesh quality POOR/CRITICAL

#### "standard" Profile
- **Baseline**: 2nd order bounded, moderate settings
- **Adaptive**: Significant adjustment for POOR meshes
- **Use when**: Mesh quality GOOD/FAIR

#### "accurate" Profile
- **Baseline**: High accuracy (LUST, CrankNicolson)
- **Adaptive**: If mesh POOR, downgrades toward "standard"
- **Use when**: Mesh quality EXCELLENT/GOOD ONLY
- **Warning**: If mesh POOR, system may warn to switch to "standard"

### Recommended Strategy

```python
if mesh_quality == "EXCELLENT":
    use profile "accurate"  # Full high-accuracy schemes
elif mesh_quality == "GOOD":
    use profile "standard"  # Adaptive makes minor tweaks
elif mesh_quality == "FAIR":
    use profile "standard"  # Adaptive makes moderate adjustments
elif mesh_quality == "POOR":
    use profile "robust"    # 1st order baseline, adaptive fine-tunes
    # AND/OR: REMESH!
else:  # CRITICAL
    ERROR: "Mesh quality too poor, REMESH REQUIRED"
```

---

## Literature References

1. **Grid Convergence Index**:
   - Roache, P.J. (1998). "Verification of Codes and Calculations." AIAA Journal 36(5):696-702
   - CFD University: https://cfd.university

2. **Mesh Quality Effects**:
   - Wolf Dynamics CFD Tips: https://wolfdynamics.com/wiki/tipsandtricks.pdf
   - CFD Support: "Mesh quality check" - https://www.cfdsupport.com

3. **Numerical Schemes**:
   - OpenFOAM User Guide v12+, Sections 4.4-4.5: Numerical Schemes
   - Jasak, H. (1996). "Error Analysis for FVM." PhD Thesis, Imperial College

4. **Verification & Validation**:
   - ASME V&V 20-2009: Standard for Verification and Validation in CFD
   - Oberkampf & Roy (2010). "Verification and Validation in Scientific Computing"

---

## Summary: Use the Mesh-Adaptive System Responsibly

✅ **DO Use It For:**
- Initial testing and debugging
- Preventing divergence on FAIR quality meshes
- Comparative studies with consistent mesh quality
- Understanding which mesh areas need refinement

❌ **DON'T Rely On It For:**
- Compensating for fundamentally poor meshes
- Avoiding proper mesh refinement studies
- Publication-quality results without GCI verification
- Clinical decisions based on POOR quality meshes

### The Right Approach

1. **Generate best possible mesh** - use snappyHexMesh best practices
2. **Let adaptive system stabilize** - if quality FAIR or better
3. **Perform GCI study** - verify grid independence
4. **If mesh quality POOR** - REMESH, don't just adjust numerics
5. **Document everything** - mesh quality, adaptive adjustments, GCI results

**Remember**: The mesh-adaptive system helps you converge, but only a good mesh gives you accurate results.
