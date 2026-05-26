# Mesh Specification Guide

**Version**: 2.0
**Updated**: November 2025
**Purpose**: Mathematical mesh specification for cardiovascular CFD simulations

---

## Overview

AortaCFD uses a **geometry-adaptive mesh specification system** that automatically scales resolution based on patient anatomy. This guide explains the mathematical relationships and provides evidence-based guidance for mesh independence.

---

## 1. Mesh Resolution Specification

### Priority System (3-Level Cascade)

| Priority | Parameter | Description | Use Case |
|----------|-----------|-------------|----------|
| **1** | `target_cell_size_mm` | Absolute cell size in mm | Mesh independence studies |
| **2** | `cells_per_diameter` | Cells across reference diameter | Production simulations (RECOMMENDED) |
| **3** | Fallback | 10 cells/diameter | Initial geometry check only |

### Mathematical Formulation

#### Option 1: `cells_per_diameter` (Recommended)

The base cell size is computed from the reference vessel diameter:

```
h = D_ref / N
```

Where:
- `h` = base cell size (mm)
- `D_ref` = reference vessel diameter (mm), typically the smallest inlet/outlet
- `N` = cells_per_diameter value

**Example**: For an aorta with `D_ref = 20mm` and `cells_per_diameter = 20`:
```
h = 20mm / 20 = 1.0mm base cell size
```

#### Option 2: `target_cell_size_mm` (Absolute Control)

Bypasses geometry analysis and uses the specified cell size directly:

```json
"mesh_resolution": {
  "target_cell_size_mm": 0.6
}
```

**Use when**:
- Inlet geometry is irregular (non-circular cross-section)
- Matching specific literature values (e.g., "0.6mm elements")
- Mesh independence studies requiring fixed ratios (0.5, 0.7, 1.0, 1.4mm)

#### Option 3: `cells_across_span` with `mesh_strategy: "adaptive_span"`

The third method sizes the mesh by the number of cells **across the
local vessel lumen**, not the inlet diameter. Use this when the
geometry has branches of mixed diameter (e.g., aorta + supra-aortic
branches) — `cells_per_diameter` would under-resolve the small
branches at any reasonable bulk-cell setting.

```json
"mesh": {
  "SNAPPY_SETTINGS": {
    "mesh_strategy": "adaptive_span",
    "cells_across_span": 16,
    "surfaceRefinementLevels": [2, 2]
  }
}
```

##### Mathematical definition

snappyHexMesh's `insideSpan` refinement produces:

```
achievable_cells_across_span = blockMesh_cells × 2^span_level
```

Where:
- `blockMesh_cells` — background mesh density (cells per **reference** diameter)
- `span_level` — snappy's `insideSpan` refinement level (each level halves cell size in 3D)

The **reference diameter** is set by `geometry.reference_radius_strategy`:

| Strategy | What it picks | When to use |
|---|---|---|
| `max` (default) | Largest vessel (main aorta) | Standard aortic CFD |
| `inlet` | Inlet radius only | Inlet-dominated flows |
| `mean` | Average of all patches | Mixed-scale work |
| `min` | Smallest vessel | "Cells across span must hit target everywhere — even the smallest branch" |

##### How `cells_across_span` differs from `cells_per_diameter`

For BPM120 (main aorta ≈ 25 mm, branches ≈ 8 mm), setting `cells_per_diameter: 15` gives:

| Region | Lumen | Cell size (h) | Cells across local lumen |
|---|---|---|---|
| Main aorta | 25 mm | 25/15 ≈ 1.67 mm | **15** ✓ |
| Supra-aortic branch | 8 mm | 1.67 mm (same bulk h) | **~5** — under-resolved |

Same geometry with `cells_across_span: 16` and `reference_radius_strategy: "max"`:

| Region | Lumen | Background h | snappy `insideSpan` refines locally → |
|---|---|---|---|
| Main aorta | 25 mm | 25/4 ≈ 6.25 mm (background) | × 2² = ~16 cells ✓ |
| Supra-aortic branch | 8 mm | 6.25 mm (same background) | × 2² locally → ~5 cells (with `"max"` reference) |

For the branch to also reach 16 cells across, switch to
`reference_radius_strategy: "min"` (or `"mean"`) so the background
cell is sized relative to the smallest branch.

##### Auto vs explicit `span_refinement_level`

If you omit `span_refinement_level`, `plan_span_background()` in
`src/aortacfd_lib/utils/mesh_constants.py:324` searches the
`(blockMesh_cells, span_level)` pairs that satisfy:

```
blockMesh_cells × 2^span_level ≥ cells_across_span
```

and picks the one that:
1. uses the smallest `span_level` (avoid over-cooking the bulk)
2. keeps `blockMesh_cells` near the ideal of 6 cells/D
3. minimises overshoot of the target

If you set `span_refinement_level` explicitly, the planner is
bypassed and `blockMesh_cells` is computed directly as
`⌈cells_across_span / 2^span_level⌉` (with a quality floor of 4).

##### Worked example on the U-bend test case

`cases_input/ubend/config_adaptive_span.json` exercises this path
on a single-tube geometry (27.4 mm inlet, 24.4 mm outlet, no
branches → diameter ratio ≈ 1.0). For multi-branch examples see
the workshop's BPM120 / 0014_H_AO_COA cases.

**Use when**:
- Geometry has branches with diameters spanning > 2× (aorta + supra-aortic branches; pulmonary trees; coronary networks)
- You want the SAME spatial resolution in every branch, regardless of size
- The `mesh.goal: "routine_hemodynamics"` / `"wall_sensitive"` presets you've seen — both implicitly set this strategy

---

## 2. Resolution Guidelines

### Recommended `cells_per_diameter` Values

| Category | cells/D | Typical h (mm) | Cell Count | Use Case |
|----------|---------|----------------|------------|----------|
| **Coarse** | 10-12 | 1.5-2.0 | 200k-500k | Initial exploration, fast iteration |
| **Standard** | 15-20 | 0.8-1.2 | 500k-2M | Production simulations |
| **Fine** | 25-30 | 0.5-0.7 | 2M-5M | Mesh independence, publications |

### Configuration Examples

**Coarse mesh (initial testing):**
```json
"mesh": {
  "mesh_resolution": {
    "cells_per_diameter": 12
  }
}
```

**Standard production mesh:**
```json
"mesh": {
  "mesh_resolution": {
    "cells_per_diameter": 20
  }
}
```

**Fine mesh (mesh independence study):**
```json
"mesh": {
  "mesh_resolution": {
    "cells_per_diameter": 30
  }
}
```

---

## 3. Surface Refinement Level

### Overview

The `surface_refinement_level` controls additional refinement at vessel walls through snappyHexMesh subdivision. This is **independent** of the base cell size.

### Mathematical Relationship

```
h_surface = h_base / 2^L
```

Where:
- `h_surface` = cell size at the surface (mm)
- `h_base` = base cell size from blockMesh (mm)
- `L` = surface refinement level (1, 2, or 3)

### Level Definitions

| Level | Snappy Levels | Surface Cell Size | Cell Count Factor | Use Case |
|-------|---------------|-------------------|-------------------|----------|
| **1** | [0, 1] | `h_base / 2` | 1× | Coarse simulations |
| **2** | [1, 2] | `h_base / 4` | 4× | Standard (DEFAULT) |
| **3** | [2, 3] | `h_base / 8` | 16× | Fine resolution at walls |

### Combined Resolution Example

For `cells_per_diameter = 20` and `surface_refinement_level = 2` with `D_ref = 20mm`:

```
Base cell size:    h_base = 20mm / 20 = 1.0mm
Surface cell size: h_surface = 1.0mm / 4 = 0.25mm
```

### Configuration

```json
"mesh": {
  "mesh_resolution": {
    "cells_per_diameter": 20
  },
  "surface_refinement_level": 2
}
```

---

## 4. Mesh Independence Studies

### Published Literature Ranges

Based on cardiovascular CFD literature, mesh-independent solutions typically require:

| Application | Element Count | Reference |
|-------------|---------------|-----------|
| Aortic arch | 500k - 2M | Morbiducci et al. (2013) |
| Coarctation | 1M - 5M | Arzani & Shadden (2015) |
| Aneurysm | 225k - 5M | Cebral et al. (2005) |
| Coronary | 1M - 3M | Sankaran et al. (2012) |

### Convergence Metrics

Mesh independence is typically verified when these quantities change by <5% between successive refinements:

| Quantity | Typical Convergence | Clinical Relevance |
|----------|--------------------|--------------------|
| **WSS (Wall Shear Stress)** | 2-5% | Endothelial cell response |
| **TAWSS (Time-Averaged WSS)** | 3-5% | Atherosclerosis risk |
| **OSI (Oscillatory Shear Index)** | 5-10% | Flow reversal indicator |
| **Pressure Drop** | 1-3% | Hemodynamic severity |
| **Peak Velocity** | 2-5% | Flow characterization |

### Recommended Mesh Independence Protocol

**Step 1: Coarse mesh (baseline)**
```json
"mesh_resolution": {"cells_per_diameter": 12}
```

**Step 2: Medium mesh**
```json
"mesh_resolution": {"cells_per_diameter": 18}
```

**Step 3: Fine mesh**
```json
"mesh_resolution": {"cells_per_diameter": 25}
```

**Step 4: Compute Grid Convergence Index (GCI)**

```
GCI = F_s * |ε| / (r^p - 1)
```

Where:
- `F_s` = safety factor (1.25 for 3+ grids)
- `ε` = relative error between grids
- `r` = refinement ratio (typically √2 or 2)
- `p` = observed order of convergence

### Sample Mesh Independence Results

| Mesh | cells/D | Elements | TAWSS (Pa) | Change | Pressure Drop (Pa) | Change |
|------|---------|----------|------------|--------|-------------------|--------|
| M1 | 12 | 250k | 0.82 | - | 1250 | - |
| M2 | 18 | 850k | 0.91 | 11.0% | 1180 | 5.6% |
| M3 | 25 | 2.1M | 0.94 | 3.3% | 1155 | 2.1% |
| M4 | 30 | 3.5M | 0.95 | 1.1% | 1150 | 0.4% |

**Conclusion**: Mesh M3 (25 cells/D, ~2M elements) achieves mesh independence for this geometry.

---

## 5. Branch Resolution Validation

For aortic geometries with multiple outlets (arch branches), ensure adequate resolution in small vessels.

### Minimum Resolution Requirement

Each branch should have at least **6-8 cells across the diameter** for reliable flow predictions.

### Automatic Validation

AortaCFD automatically validates branch resolution and warns if under-resolved:

```
Branch resolution range:
  Smallest: D=5.2mm → 5.2 cells (⚠️ WARNING: < 6)
  Largest:  D=18.5mm → 18.5 cells (✓)
```

### Addressing Under-Resolution

If small branches are under-resolved, increase `cells_per_diameter`:

```json
"mesh_resolution": {
  "cells_per_diameter": 30  // Increased from 20
}
```

Or use `target_cell_size_mm` for finer control:

```json
"mesh_resolution": {
  "target_cell_size_mm": 0.5  // Ensures all branches resolved
}
```

---

## 6. Memory and Performance Considerations

### Cell Count Estimation

Approximate total cell count:

```
N_total ≈ N_bg × 0.25 × (1 + 0.3 × (8^L - 1))
```

Where:
- `N_bg` = background grid cells (from blockMesh)
- `L` = maximum surface refinement level
- Factor 0.25 accounts for cells outside the geometry

### Memory Requirements

| Cell Count | RAM Required | Parallel Cores |
|------------|--------------|----------------|
| 500k | 2-4 GB | 2-4 |
| 1M | 4-8 GB | 4-8 |
| 2M | 8-16 GB | 8-12 |
| 5M | 16-32 GB | 12-24 |
| 10M | 32-64 GB | 24-48 |

### BlockMesh Size Warnings

AortaCFD warns when background meshes become large:

| Estimated Cells | Warning Level | Action |
|-----------------|---------------|--------|
| < 10M | OK | Proceed |
| 10M - 25M | Large | Consider parallel meshing |
| 25M - 50M | Very Large | May cause OOM on workstations |
| > 50M | Huge | Use HPC cluster |

---

## 7. Complete Configuration Example

```json
{
  "mesh": {
    "mesh_resolution": {
      "cells_per_diameter": 20
    },

    "surface_refinement_level": 2,

    "boundary_layers": {
      "enabled": true,
      "num_layers": 5,
      "expansion_ratio": 1.2,
      "final_layer_thickness": 0.3,
      "min_thickness": 0.1
    },

    "quality_controls": {
      "maxNonOrtho": 65,
      "maxBoundarySkewness": 8,
      "maxInternalSkewness": 4
    }
  }
}
```

---

## 8. Troubleshooting

### Problem: Mesh too large (OOM)

**Solutions**:
1. Reduce `cells_per_diameter` (try 15 instead of 20)
2. Reduce `surface_refinement_level` (try 1 instead of 2)
3. Enable parallel meshing with more subdomains

### Problem: Small branches under-resolved

**Solutions**:
1. Increase `cells_per_diameter` to 25-30
2. Use `target_cell_size_mm` for absolute control
3. Accept coarser resolution in branches if not clinically relevant

### Problem: Conflicting parameters

If both `target_cell_size_mm` and `cells_per_diameter` are set, `target_cell_size_mm` takes priority. AortaCFD will warn about this conflict.

---

## 9. References

### Key Literature

1. **Morbiducci U, et al.** (2013). "Inflow boundary conditions for image-based computational hemodynamics." *Ann Biomed Eng*, 41(1):42-58.

2. **Arzani A, Shadden SC.** (2015). "Characterization of the transport topology in patient-specific abdominal aortic aneurysm models." *Phys Fluids*, 27:031901.

3. **Cebral JR, et al.** (2005). "Characterization of cerebral aneurysms for assessing risk of rupture by using patient-specific computational hemodynamics models." *AJNR*, 26(10):2550-2559.

4. **Sankaran S, et al.** (2012). "Patient-specific multiscale modeling of blood flow for coronary artery bypass graft surgery." *Ann Biomed Eng*, 40(10):2228-2242.

5. **Roache PJ.** (1994). "Perspective: A method for uniform reporting of grid refinement studies." *J Fluids Eng*, 116(3):405-413.

### OpenFOAM Documentation

- [snappyHexMesh User Guide](https://doc.cfd.direct/openfoam/user-guide-v12/snappyhexmesh)
- [Mesh Quality Guidelines](https://doc.cfd.direct/openfoam/user-guide-v12/mesh-quality)

---

## 10. Quick Reference Card

### Resolution Guidelines
```
Coarse:   cells_per_diameter = 10-12  (200k-500k cells)
Standard: cells_per_diameter = 15-20  (500k-2M cells)
Fine:     cells_per_diameter = 25-30  (2M-5M cells)
```

### Surface Refinement
```
Level 1: h_surface = h_base / 2   (minimal refinement)
Level 2: h_surface = h_base / 4   (DEFAULT)
Level 3: h_surface = h_base / 8   (fine resolution)
```

### Mesh Independence
```
TAWSS convergence:    < 5% change between refinements
Pressure convergence: < 3% change between refinements
Minimum branches:     6-8 cells across diameter
```

---

**Last Updated**: November 2025
**Maintainer**: AortaCFD Development Team
