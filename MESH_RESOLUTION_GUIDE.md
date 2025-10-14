# Mesh Resolution Configuration Guide

Complete reference for controlling mesh resolution in AortaCFD simulations.

---

## Quick Start

**Recommended for beginners:** Use direct cell size specification:

```json
{
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 1.0
    }
  }
}
```

**Result:** Uniform 1mm cells throughout the domain (clinical quality).

---

## Parameter Hierarchy

AortaCFD checks mesh resolution parameters in **strict priority order**. Set **ONLY ONE** parameter per simulation to avoid confusion.

### Priority 1: `target_cell_size_mm` (HIGHEST)

**Direct specification in millimeters** - All other parameters ignored if this is set.

```json
{
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 1.0
    }
  }
}
```

- **Formula:** `cell_size = target_cell_size_mm`
- **Example:** `1.0` → 1mm cells everywhere
- **Use when:** You know exactly what cell size you want
- **Independent of:** Geometry (doesn't need reference radius)

---

### Priority 2: `blockmesh_resolution`

**Cells across diameter** - Requires reference radius from STL geometry.

```json
{
  "mesh": {
    "mesh_resolution": {
      "blockmesh_resolution": 10
    }
  }
}
```

- **Formula:** `cell_size = 2 × reference_radius / blockmesh_resolution`
- **Example:** If `reference_radius = 10mm`, resolution = 10 → `cell_size = 2mm`
- **Use when:** You want resolution relative to vessel size
- **Depends on:** `geometry.reference_radius_strategy`

**Reference Radius Strategies:**

```json
{
  "geometry": {
    "reference_radius_strategy": "min"  // or "inlet", "mean", "max"
  }
}
```

| Strategy | Radius Used | Use Case |
|----------|-------------|----------|
| `min` (default) | Smallest vessel | Ensures all branches adequately resolved |
| `inlet` | Inlet only | Inlet-dominated flows |
| `mean` | Average of all vessels | Balanced approach |
| `max` | Largest vessel | Coarsest overall mesh |

---

### Priority 3: `cells_per_diameter`

**Similar to blockmesh_resolution** but more intuitive naming.

```json
{
  "mesh": {
    "mesh_resolution": {
      "cells_per_diameter": 15
    }
  }
}
```

- **Formula:** `cell_size = 2 × reference_radius / cells_per_diameter`
- **Example:** If `reference_radius = 10mm`, cells = 15 → `cell_size = 1.33mm`
- **Use when:** You think in terms of "cells across vessel"
- **Advanced:** Can specify per-region:

```json
{
  "cells_per_diameter": {
    "branch": 15,
    "inlet": 20
  }
}
```

(Code tries `branch` first, then `inlet`)

---

### Priority 4: `refinement_levels` (LOWEST)

**Named quality levels** - Lookup table approach.

**Step 1:** Define levels in `mesh.refinement_levels`:

```json
{
  "mesh": {
    "refinement_levels": {
      "coarse": 0.002,   // 2.0 mm
      "medium": 0.001,   // 1.0 mm
      "fine": 0.0005     // 0.5 mm
    }
  }
}
```

**Step 2:** Select level in `geometry.refinement_level`:

```json
{
  "geometry": {
    "refinement_level": "medium"
  }
}
```

- **Formula:** Lookup `refinement_levels["medium"]` → `0.001m = 1.0mm`
- **Use when:** You want predefined quality presets
- **Note:** Values in **meters**, converted to mm automatically

---

### Priority 5: Default Fallback

If **none** of the above are set:

- **Default:** `1.5mm`
- **Rationale:** Validated for adult aorta (10-30mm diameter)
  - 20mm aorta → 13 cells across (adequate for laminar)
  - 5mm branch → 3 cells across (minimum for flow capture)
- **Warning:** You'll see a log warning if this is used

---

## Recommended Configurations

### Coarse (Draft Quality)

**Purpose:** Quick checks, geometry validation, debugging

```json
{
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 2.0
    }
  }
}
```

- **Cell size:** 2.0 mm
- **Expected cells:** ~100K-300K
- **Runtime:** 5-15 minutes
- **Use for:** Flow pattern visualization, testing

### Medium (Clinical Quality)

**Purpose:** Routine analysis, clinical decision support

```json
{
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 1.0
    }
  }
}
```

- **Cell size:** 1.0 mm
- **Expected cells:** ~500K-1.5M
- **Runtime:** 30-90 minutes
- **Use for:** Hemodynamic assessment, pressure gradients

### Fine (Publication Quality)

**Purpose:** Research, mesh independence, detailed WSS

```json
{
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 0.5
    }
  }
}
```

- **Cell size:** 0.5 mm
- **Expected cells:** ~2M-5M
- **Runtime:** 2-4 hours
- **Use for:** Publications, WSS gradients, validation

---

## Helper Tools

### 1. Compute Cell Size Script

Test what cell size will be used **before** running simulation:

```bash
cd examples/mesh_configs
python compute_cell_size.py ../../cases_input/patient1/config.json
```

**With reference radius override:**

```bash
python compute_cell_size.py mesh_medium.json --reference-radius 12.5
```

**Show all methods:**

```bash
python compute_cell_size.py mesh_fine.json --show-all-methods
```

### 2. Example Configs

Pre-made configurations for different quality levels:

```bash
examples/mesh_configs/
├── mesh_coarse.json   # 2.0mm - draft quality
├── mesh_medium.json   # 1.0mm - clinical quality
├── mesh_fine.json     # 0.5mm - publication quality
└── compute_cell_size.py
```

**Use example configs:**

```bash
# Copy to your case
cp examples/mesh_configs/mesh_medium.json cases_input/my_patient/mesh_config.json

# Merge with main config
python run_patient.py my_patient --config cases_input/my_patient/mesh_config.json
```

---

## Advanced Topics

### Automatic Reference Radius Calculation

When using `blockmesh_resolution` or `cells_per_diameter`, AortaCFD automatically:

1. **Analyzes STL files** - Calculates equivalent radius for each patch
2. **Selects reference** - Based on `reference_radius_strategy`
3. **Computes cell size** - Uses formula with selected radius

**Check what radius was used:**

Look for this log message during meshing:

```
[INFO] Reference branch radius for meshing: 10.234 mm
[INFO] ✓ Target cell size: 1.367 mm
[INFO]   Source: 2*R/15.0 cells (ref_radius=10.23mm)
[INFO]   Reference radius: 10.234 mm (strategy: min)
```

### Mixed Resolution (NOT RECOMMENDED)

If you accidentally set multiple parameters:

```json
{
  "mesh_resolution": {
    "target_cell_size_mm": 1.0,       // This will be used
    "cells_per_diameter": 15          // This will be IGNORED
  }
}
```

**Warning message:**

```
[INFO] Both target_cell_size_mm and cells_per_diameter provided;
       using target_cell_size_mm (highest priority)
```

**Recommendation:** Remove one parameter to avoid confusion.

###Mesh Overwrite Behavior

**Default:** SnappyHexMesh uses `-overwrite` flag (writes mesh to case directory).

**To preserve intermediate meshes:**

```json
{
  "mesh": {
    "SNAPPY_SETTINGS": {
      "overwrite": false
    }
  }
}
```

**Result:** Mesh written to separate time directories (0.001, 0.002, etc.).

---

## Validation Criteria

After meshing, run `checkMesh` to verify quality:

```bash
cd output/patient1/run_*/openfoam
checkMesh
```

**Target metrics by quality level:**

| Metric | Coarse | Medium | Fine |
|--------|--------|--------|------|
| Max non-orthogonality | < 75° | < 65° | < 60° |
| Max skewness | < 5 | < 4 | < 3 |
| Max aspect ratio | < 150 | < 100 | < 50 |
| Total cells | 100K-300K | 500K-1.5M | 2M-5M |

---

## Troubleshooting

### Problem: "Reference radius unavailable"

**Symptom:**

```
[WARNING] blockmesh_resolution provided but reference radius unavailable
```

**Cause:** STL files not found or geometry analysis failed.

**Solutions:**

1. Check STL files exist: `ls cases_input/patient1/*.stl`
2. Use `target_cell_size_mm` instead (doesn't need geometry)
3. Verify scale_factor is correct: `"scale_factor": 0.001`

### Problem: "Using default fallback"

**Symptom:**

```
[WARNING] No mesh resolution parameters found; using 1.5mm default
```

**Cause:** None of the 4 priority methods are configured.

**Solution:** Add any mesh resolution parameter (see examples above).

### Problem: Mesh too coarse/fine

**Symptom:** Simulation results poor quality or takes too long.

**Solution:** Adjust cell size:

- **Too coarse** (< 5 cells across vessel):
  - Reduce `target_cell_size_mm` from 2.0 → 1.0mm
  - Or increase `cells_per_diameter` from 5 → 15

- **Too fine** (excessive runtime):
  - Increase `target_cell_size_mm` from 0.5 → 1.0mm
  - Or decrease `cells_per_diameter` from 30 → 15

---

## Parameter Summary Table

| Parameter | Priority | Formula | Requires Geometry | Units | Example |
|-----------|----------|---------|-------------------|-------|---------|
| `target_cell_size_mm` | 1 (highest) | `size = value` | No | mm | 1.0 |
| `blockmesh_resolution` | 2 | `size = 2R / value` | Yes | dimensionless | 10 |
| `cells_per_diameter` | 3 | `size = 2R / value` | Yes | dimensionless | 15 |
| `refinement_levels` | 4 (lowest) | `size = lookup[level]` | No | m | 0.001 |
| Default | 5 (fallback) | `size = 1.5mm` | No | mm | 1.5 |

**R** = reference radius from STL geometry (strategy-dependent)

---

## Best Practices

1. ✅ **Set only ONE parameter** per simulation
2. ✅ **Use `target_cell_size_mm`** for beginners (most explicit)
3. ✅ **Test with `compute_cell_size.py`** before running full simulation
4. ✅ **Start coarse (2mm)**, then refine to medium (1mm) or fine (0.5mm)
5. ✅ **Verify mesh quality** with `checkMesh` after meshing
6. ✅ **Document which parameter** you used in your notes/paper

---

## References

- **Code:** `src/aortacfd_lib/mesh_setup.py` (lines 337-417)
- **Examples:** `examples/mesh_configs/*.json`
- **Validation:** `docs/MESH_QUALITY_GUIDE.md`
- **Reproducibility:** `REPRODUCIBILITY.md` (Section 5)

---

**Last updated:** 2025-10-14
**Maintainer:** AortaCFD Development Team
