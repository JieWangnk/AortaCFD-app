# Boundary Layer Collapse Problem & Solutions

## The Problem You Discovered

You correctly identified that **the same firstLayerThickness (0.060 mm) gives different layer counts** across mesh resolutions:

| Config | cells_per_D | firstLayerThickness | Target Layers | **Actual Layers** | Success Rate |
|--------|-------------|---------------------|---------------|-------------------|--------------|
| Coarse | 4 | 0.060 mm | 10 | **5.01** | 50% |
| Medium | 8 | 0.060 mm | 10 | **~7?** | ~70%? |
| Fine | 16 | 0.060 mm | 10 | **0.053** | 0.5% ❌ |

###The Root Cause

**The y+ calculation gives the SAME layer thickness for all meshes**, but the **background cell size changes dramatically**:

| Config | Background Cell Size | firstLayerThickness | Ratio (layer/cell) | Result |
|--------|---------------------|---------------------|-------------------|---------|
| Coarse | 0.93 mm | 0.060 mm | **6.5%** | Severe collapse |
| Medium | 0.47 mm | 0.060 mm | **13%** | Partial collapse |
| Fine | 0.23 mm | 0.060 mm | **26%** | Complete failure |

**OpenFOAM's snappyHexMesh has difficulty adding layers when:**
- First layer << background cell size (typically needs > 30-50%)
- Geometry has tight spaces
- Surface curvature is high

---

## Why This Happens

### 1. Y+ Calculation is Resolution-Independent

```python
firstLayerThickness = y+ × ν / u_τ
                    = 1.0 × 3.77e-6 / 0.0625
                    = 0.060 mm

# Same for ALL mesh resolutions!
```

The physics (y+=1.0 for wall-resolved RANS) demands this specific thickness, **regardless of mesh resolution**.

### 2. Background Mesh Changes with Resolution

```
Coarse (4 cells/D):  cell_size = 3.72mm / 4  = 0.93 mm
Medium (8 cells/D):  cell_size = 3.72mm / 8  = 0.47 mm
Fine   (16 cells/D): cell_size = 3.72mm / 16 = 0.23 mm
```

### 3. snappyHexMesh Layer Addition Mechanics

snappyHexMesh tries to:
1. Extrude surface inward by `firstLayerThickness`
2. Check if new layer fits without violating quality metrics
3. If quality check fails → **shrink or skip layer**

When `firstLayerThickness` << `cell_size`:
- Extrusion creates very small, thin cells
- Quality checks fail (high aspect ratio, skewness)
- snappyHexMesh gives up and collapses layers

---

## Solutions

### Solution 1: Adaptive firstLayerThickness (Recommended)

**Scale layer thickness with mesh resolution** while maintaining approximate y+ target:

```json
{
  "boundary_layers": {
    "enabled": true,
    "target_yplus": 1.0,
    "num_layers": 5,
    "expansion_ratio": 1.3,

    "_adaptive_mode": true,
    "min_layer_to_cell_ratio": 0.3
  }
}
```

**Implementation:**
```python
# In mesh_setup.py
background_cell_size = vessel_diameter / cells_per_diameter
min_layer_thickness = background_cell_size * 0.3  # 30% of cell size

firstLayerThickness = max(
    yplus_calculated_thickness,  # 0.060 mm
    min_layer_thickness           # Ensures > 30% of cell size
)
```

**Result:**
| Config | Calculated | Min Required | **Actual Used** | Layers | y+ |
|--------|-----------|--------------|-----------------|--------|-----|
| Coarse | 0.060 mm | 0.279 mm | **0.279 mm** | ~10 | ~5 |
| Medium | 0.060 mm | 0.140 mm | **0.140 mm** | ~10 | ~2 |
| Fine | 0.060 mm | 0.070 mm | **0.070 mm** | ~10 | ~1.2 |

**Trade-off:** y+ increases slightly for coarser meshes, but layers are successfully added.

---

### Solution 2: Resolution-Dependent Layer Count

Keep `firstLayerThickness` from y+, but **reduce layer count** for finer meshes:

```json
{
  "mesh": {
    "cells_per_diameter": 16,

    "boundary_layers": {
      "target_yplus": 1.0,
      "num_layers": 3,        // ← Reduce from 10 to 3 for fine mesh
      "expansion_ratio": 1.5,  // ← Increase to maintain coverage
      "estimation_method": "auto"
    }
  }
}
```

**Recommended layer counts:**

| cells_per_D | num_layers | expansion_ratio | Total BL thickness |
|-------------|------------|-----------------|-------------------|
| 4 (coarse) | 10 | 1.2 | 1.57 mm |
| 8 (medium) | 7 | 1.25 | 1.21 mm |
| 12 | 5 | 1.3 | 0.97 mm |
| 16 (fine) | 3 | 1.5 | 0.73 mm |
| 20+ (very fine) | 2 | 1.8 | 0.53 mm |

**Rationale:** Finer meshes naturally have better near-wall resolution from background cells.

---

### Solution 3: Increase minThickness

Allow snappyHexMesh more flexibility:

```json
{
  "mesh": {
    "boundary_layers": {
      "target_yplus": 1.0,
      "num_layers": 10,
      "expansion_ratio": 1.2,

      "SNAPPY_OVERRIDES": {
        "minThickness": 0.01,  // ← Increase from 0.001
        "nRelaxIter": 10,      // ← More relaxation iterations
        "nSmoothSurfaceNormals": 10
      }
    }
  }
}
```

**Effect:** Allows more aggressive layer shrinking before giving up.

---

### Solution 4: Profile-Based Configuration

Use different configs for different mesh resolutions:

**config_mesh_coarse.json:**
```json
{
  "mesh": {
    "cells_per_diameter": 4,
    "boundary_layers": {
      "target_yplus": 5.0,    // ← Relax y+ for coarse
      "num_layers": 5,
      "expansion_ratio": 1.3,
      "firstLayerThickness": 0.25  // ← Manual override
    }
  }
}
```

**config_mesh_fine.json:**
```json
{
  "mesh": {
    "cells_per_diameter": 16,
    "boundary_layers": {
      "target_yplus": 1.0,    // ← Strict y+ for fine
      "num_layers": 3,
      "expansion_ratio": 1.5
      // Auto-calculate firstLayerThickness
    }
  }
}
```

---

### Solution 5: Two-Stage Meshing (Advanced)

For very fine meshes, use surface refinement instead of boundary layers:

```json
{
  "mesh": {
    "cells_per_diameter": 16,

    "boundary_layers": {
      "enabled": false  // ← Disable layers
    },

    "surface_refinement": {
      "levels": [3, 4]  // ← Aggressive surface refinement
    },

    "wall_refinement": {
      "distance": 0.5,  // mm
      "levels": 3       // Refine near wall
    }
  }
}
```

Then rely on background mesh refinement for near-wall resolution.

---

## Recommended Implementation

### For Your BPM120 Case

I recommend **Solution 2** (Resolution-Dependent Layer Count) as it's simplest:

**config_mesh_coarse.json:**
```json
{
  "mesh": {
    "cells_per_diameter": 4,
    "boundary_layers": {
      "enabled": true,
      "target_yplus": 1.0,
      "num_layers": 10,      // ← Many layers for coarse mesh
      "expansion_ratio": 1.2
    }
  }
}
```

**config_mesh_medium.json:**
```json
{
  "mesh": {
    "cells_per_diameter": 8,
    "boundary_layers": {
      "enabled": true,
      "target_yplus": 1.0,
      "num_layers": 6,       // ← Fewer layers
      "expansion_ratio": 1.25
    }
  }
}
```

**config_mesh_fine.json:**
```json
{
  "mesh": {
    "cells_per_diameter": 16,
    "boundary_layers": {
      "enabled": true,
      "target_yplus": 1.0,
      "num_layers": 3,       // ← Even fewer layers
      "expansion_ratio": 1.5  // ← Larger expansion for coverage
    }
  }
}
```

---

## Why Can't We Keep the Same y+ Everywhere?

### You asked: "What if we can't keep the yplus?"

**Answer: You CAN keep approximate y+, but must adapt the strategy:**

### Option A: Accept Variable y+ (Mesh Convergence Study)

| Mesh | firstLayerThickness | Expected y+ | Use Case |
|------|---------------------|-------------|----------|
| Coarse | 0.25 mm | ~4 | Quick iteration |
| Medium | 0.12 mm | ~2 | Verification |
| Fine | 0.06 mm | ~1 | Final result |

This is **normal for mesh convergence studies** - you're checking if results converge as mesh refines AND y+ approaches target.

### Option B: Target y+ Only on Finest Mesh

```json
// coarse/medium: Use manual layers for robustness
"firstLayerThickness": 0.2  // y+ ≈ 3

// fine: Use y+ calculation for accuracy
"target_yplus": 1.0  // firstLayerThickness ≈ 0.06
```

---

## Diagnostic: Check Your Current Mesh

```bash
# Check layer addition success
grep "wall_aorta.*layers" output/BPM120/run_*/openfoam/logs/log.snappyHexMesh

# Expected output (GOOD):
# wall_aorta 18816    9.8      1.543     98.5
#                     ^^^                ^^^^
#                     layers             success %

# Your output (BAD):
# wall_aorta 312577   0.053    0.0037    0.236
#                     ^^^^                ^^^^^
#                     failure!            0.2% success!
```

---

## Quick Fix for Your Current Issue

### For config_mesh_fine.json:

**Change from:**
```json
{
  "boundary_layers": {
    "target_yplus": 1.0,
    "num_layers": 10,
    "expansion_ratio": 1.2
  }
}
```

**To:**
```json
{
  "boundary_layers": {
    "target_yplus": 1.0,
    "num_layers": 3,        // ← Reduce layers
    "expansion_ratio": 1.5,  // ← Increase expansion
    "firstLayerThickness": 0.08  // ← Manual override (slightly larger)
  }
}
```

Or even simpler - **don't rely on y+ auto-calculation for very fine meshes**:

```json
{
  "boundary_layers": {
    "enabled": true,
    "num_layers": 3,
    "expansion_ratio": 1.5,
    "firstLayerThickness": 0.12,  // ← Manual: 50% of cell size (0.23mm)
    "_comment": "Manual layer thickness for fine mesh robustness"
  }
}
```

---

## Summary

### Your Question: Why different layer counts?

**Answer:** The y+ calculation gives **fixed thickness** (0.060mm), but background cell size **varies 4x** between coarse (0.93mm) and fine (0.23mm). snappyHexMesh fails when layers are too thin relative to cells.

### What to do?

1. **For mesh convergence:** Accept that coarser meshes have higher y+ (~3-5) and finer meshes hit y+ target (~1)
2. **For robust meshing:** Reduce `num_layers` as you refine mesh (10 → 6 → 3)
3. **For fine mesh:** Consider manual `firstLayerThickness` = 30-50% of cell size

### Best Practice for Cardiovascular CFD

```
Coarse (draft):     num_layers=5,  firstLayerThickness=0.2mm   (y+~3)
Medium (standard):  num_layers=6,  target_yplus=2.0            (y+~2)
Fine (publication): num_layers=4,  target_yplus=1.0            (y+~1)
```

The goal is **successful layer addition** first, exact y+=1.0 second!
