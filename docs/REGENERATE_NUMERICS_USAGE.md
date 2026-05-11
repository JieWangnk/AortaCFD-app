# Regenerate Numerics Usage Guide

## Overview

The `regenerate-numerics` workflow step allows you to regenerate `fvSchemes` and `fvSolution` files **AFTER** meshing is complete. This activates the mesh-adaptive solver system, which automatically adjusts numerical schemes and solver settings based on actual mesh quality metrics from `checkMesh`.

## Why Use This Step?

**Problem**: The normal workflow generates `fvSchemes` and `fvSolution` during case setup, BEFORE meshing. The mesh-adaptive system cannot analyze mesh quality that doesn't exist yet.

**Solution**: Run `regenerate-numerics` AFTER meshing to:
1. Read actual mesh quality from `logs/log.checkMesh`
2. Classify mesh quality tier (EXCELLENT/GOOD/FAIR/POOR/CRITICAL)
3. Apply appropriate adjustments to schemes and solver settings
4. Print detailed quality report with warnings and recommendations

## Basic Usage

### Standard Workflow (Built-in)

```bash
# Normal case setup
python run_patient.py BPM120 --steps case,mesh

# Regenerate numerics with mesh-adaptive adjustments
python run_patient.py BPM120 --steps regenerate-numerics

# Continue with boundary and solver
python run_patient.py BPM120 --steps boundary,solver
```

### Using Existing Case Directory

If you have an existing case with mesh already generated:

```bash
# Regenerate numerics for an existing run directory
python run_patient.py BPM120 --update output/BPM120/run_xxx \
  --steps regenerate-numerics
```

### Complete Workflow Example

```bash
# Full workflow with mesh-adaptive system
python run_patient.py BPM120 --steps case,mesh,regenerate-numerics,boundary,solver
```

## What Happens When You Run It?

### 1. Mesh Quality Analysis

The system reads `logs/log.checkMesh` and extracts:
- Maximum skewness
- Maximum non-orthogonality
- Maximum aspect ratio

### 2. Quality Classification

Based on metrics, mesh is classified into tiers:

| Tier | Skewness | Non-Orthogonality | Typical Action |
|------|----------|-------------------|----------------|
| EXCELLENT | < 1.5 | < 60° | No adjustments needed |
| GOOD | < 2.5 | < 65° | Minor adjustments |
| FAIR | < 4.0 | < 70° | Moderate relaxation |
| POOR | < 6.0 | < 75° | Strong stabilization |
| CRITICAL | ≥ 6.0 | ≥ 75° | Maximum stabilization + warnings |

### 3. Adjustments Applied

**For POOR mesh quality (example)**:

**fvSchemes**:
- Laplacian: `Gauss linear corrected` → `Gauss linear limited corrected 0.33`
- Gradient (if ortho > 70°): `cellLimited Gauss linear 0.5` → `cellLimited Gauss linear 0.33`

**fvSolution**:
- `nOuterCorrectors`: Profile value + 2
- `nNonOrthogonalCorrectors`: Scales with orthogonality (65° → 3, 70° → 4, 75° → 5)
- Relaxation factors: Stronger (0.3 → 0.2 for pressure)
- Tolerances: Relaxed (1e-6 → 1e-5)

### 4. Quality Report

You'll see a detailed report like:

```
═══════════════════════════════════════════════════════════════
🔧 MESH-ADAPTIVE SOLVER SETTINGS
═══════════════════════════════════════════════════════════════
Mesh Quality Analysis:
  • Skewness: 5.16 (POOR - threshold 6.0)
  • Non-orthogonality: 68.3° (FAIR - threshold 70°)
  • Aspect Ratio: 12.8
  • Quality Tier: POOR

⚠️  MESH QUALITY WARNING ⚠️
The mesh-adaptive system has stabilized your solver settings,
but this introduces NUMERICAL DIFFUSION and degrades accuracy.

ACCURACY IMPACTS:
  • Wall shear stress: May be under-predicted by 10-30%
  • Pressure drops: May be inaccurate by 5-15%
  • Flow patterns: Recirculation zones may be smoothed

RECOMMENDED ACTION:
  1. REMESH with improved snappyHexMesh settings
  2. Target: Skewness <3.0, Non-orthogonality <70°
  3. See: docs/MESH_QUALITY_WARNINGS.md for guidance

The adaptive system is a SAFETY NET, not a solution.

Adjustments Applied:
  • nOuterCorrectors: 2 → 4
  • nNonOrthogonalCorrectors: 2 → 4
  • Pressure relaxation: 0.3 → 0.2
  • Laplacian scheme: limited corrected 0.33 (for ortho 68.3°)
  • Residual tolerances: Relaxed to 1e-5

Profile: standard (2nd order bounded)
═══════════════════════════════════════════════════════════════
```

## Configuration Options

### Disable Mesh-Adaptive System

If you want to disable automatic adjustments:

```json
{
  "numerics": {
    "profile": "standard",
    "mesh_adaptive": false
  }
}
```

### Override Adjustments

You can manually override specific settings (advanced):

```json
{
  "numerics": {
    "profile": "standard",
    "mesh_adaptive": true,
    "correctors": {
      "nOuterCorrectors": 3,
      "nNonOrthogonalCorrectors": 2
    },
    "under_relaxation": {
      "p": 0.3,
      "U": 0.7
    }
  }
}
```

## When to Use regenerate-numerics

### ✅ Use When:

1. **Testing mesh refinement levels**: Compare coarse/medium/fine mesh behavior
2. **Debugging convergence issues**: Let system diagnose and apply appropriate settings
3. **Iterative mesh improvement**: Regenerate after adjusting snappyHexMesh settings
4. **Existing cases**: Apply mesh-adaptive system to old cases with meshes already generated

### ❌ Don't Use When:

1. **Fresh case setup**: Use normal `--step case` which generates initial schemes
2. **Mesh hasn't changed**: No need to regenerate if mesh quality is unchanged

## Expected Results

### BPM120 Case Study

**Before mesh-adaptive system** (fine mesh, skew 5.16):
- Stuck at 40+ PIMPLE iterations
- Poor convergence
- User manually tightened settings (made it worse)

**After regenerate-numerics**:
- Expected: 4-5 PIMPLE iterations
- Stable convergence
- System automatically relaxed settings appropriately

### Coarse vs Fine Mesh

**Coarse mesh** (174k cells, skew 2.96):
- Quality tier: GOOD
- Minimal adjustments
- Converges in 3 iterations

**Fine mesh** (3.1M cells, skew 5.16):
- Quality tier: POOR
- Strong stabilization applied
- Expected 4-5 iterations with adjusted settings

## Important Reminders

### 🚨 Safety Net, Not License for Poor Meshes

The mesh-adaptive system is a **safety net**, not a license to accept poor meshes:

1. **Always perform mesh independence studies**
2. **Target mesh quality**: Skewness < 3.0, Non-orthogonality < 70°
3. **Understand trade-offs**: Stability comes at accuracy cost
4. **Remesh if quality is poor**: Don't rely on adaptive system for production runs

### 📖 Grid Convergence Index (GCI)

Even with mesh-adaptive system, you MUST verify grid convergence:

1. Run 3 mesh levels (coarse, medium, fine)
2. Calculate GCI for key quantities (WSS, pressure drop)
3. If GCI shows divergence with refinement → **REMESH**
4. Mesh-adaptive system cannot fix fundamental meshing problems

### 📚 Further Reading

- [MESH_QUALITY_WARNINGS.md](MESH_QUALITY_WARNINGS.md) - Critical warnings and trade-offs
- Numerics profiles (`robust`, `standard`, `precise`) live under `src/config/profiles/numerics/`

## Troubleshooting

### "checkMesh log not found"

**Problem**: `logs/log.checkMesh` doesn't exist in case directory.

**Solution**:
```bash
# Run mesh step first
python run_patient.py BPM120 --steps mesh
# Then regenerate numerics
python run_patient.py BPM120 --steps regenerate-numerics
```

### "No adjustments applied"

**Problem**: Mesh quality is EXCELLENT/GOOD, no adjustments needed.

**Solution**: This is good! Your mesh is high quality. The adaptive system only adjusts for FAIR/POOR/CRITICAL meshes.

### "Still not converging"

**Problem**: Even after regenerate-numerics, solver still struggles.

**Solution**:
1. Check mesh quality tier - if CRITICAL, you MUST remesh
2. Try `"profile": "robust"` for maximum stability (1st order schemes)
3. Consider remeshing with improved snappyHexMesh settings
4. See [MESH_QUALITY_WARNINGS.md](MESH_QUALITY_WARNINGS.md) for detailed guidance

## Command Reference

```bash
# Basic regeneration
python run_patient.py PATIENT_ID --step regenerate-numerics

# With specific case directory
python run_patient.py PATIENT_ID --step regenerate-numerics --case-dir PATH

# Full workflow with regeneration
python run_patient.py PATIENT_ID \
    --step case \
    --step mesh \
    --step regenerate-numerics \
    --step boundary \
    --step solver

# Multiple cases in sequence
for case in coarse medium fine; do
    python run_patient.py BPM120 --step case --step mesh --config config_$case.json
    python run_patient.py BPM120 --step regenerate-numerics
    python run_patient.py BPM120 --step boundary --step solver
done
```

## Summary

The `regenerate-numerics` step is a powerful tool for:
- Automatically adjusting solver settings based on actual mesh quality
- Stabilizing simulations with challenging mesh quality
- Debugging convergence issues
- Testing mesh refinement strategies

**Remember**: It's a safety net for mesh quality issues, not a replacement for proper meshing. Always strive for high-quality meshes and verify grid convergence.
