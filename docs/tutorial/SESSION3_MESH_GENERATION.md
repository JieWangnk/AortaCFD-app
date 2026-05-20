# Session 3: Mesh Generation

**Duration:** 2 hours
**Goal:** Control mesh quality and understand mesh parameters

---

## Hour 1: snappyHexMesh Workflow (60 min)

### 1.1 The Three-Step Meshing Process (15 min)

```
blockMesh → surfaceFeatures → snappyHexMesh → checkMesh
```

1. **blockMesh**: Creates a background hex mesh (bounding box)
2. **surfaceFeatures**: Extracts edges from STL surfaces for snapping
3. **snappyHexMesh**: Carves the hex mesh to fit the STL geometry
   - Castellated mesh (remove cells outside geometry)
   - Snap (move cell vertices to surface)
   - Add layers (boundary layer cells near walls)
4. **checkMesh**: Quality assessment

```bash
# Run meshing step only
python run_patient.py BPM120 --config config_tutorial_coarse.json --steps case,mesh
# Look at the logs
cat output/BPM120/run_xxx/openfoam/logs/log.checkMesh
```

### 1.2 cells_per_diameter: The Single Control Parameter (15 min)

AortaCFD reduces the complex snappyHexMesh configuration to ONE number:

```json
"mesh": {
    "cells_per_diameter": 15
}
```

What this means:
- Measures the inlet diameter from the STL geometry
- Sets base cell size = diameter / cells_per_diameter
- Smaller cells = more accurate but slower

| cells/D | Typical cells | Use case | Run time (3 cycles) |
|---------|--------------|----------|---------------------|
| 8 | 50-200k | Quick test | Minutes |
| 12 | 300-800k | Coarse production | Hours |
| 15 | 500k-2M | Standard production | Hours-day |
| 20 | 1-3M | Fine | Day |
| 30+ | 3-10M | Mesh independence study | Days |

`cells_per_diameter` is one of three ways AortaCFD lets you size the
mesh; the other two are covered immediately below. Pick **one**.

#### The three CLI methods, side by side

Measured on a coarse U-bend pipe (`cases_input/ubend/`, 4 CPU,
mesh-only), all with `surfaceRefinementLevels: [1, 1]` and no
boundary layers so the resolution lever is isolated:

| Method | What you set | Cell count | Wall time | When to use |
|---|---|---:|---:|---|
| **A — `cells_per_diameter`** | `8` (cells across the inlet diameter) | 27,896 | 15 s | Default. Scales sensibly across paediatric / adult patients. |
| **B — `target_cell_size_mm`** | `2.0` (absolute mm, vessel-independent) | 109,826 | 22 s | Mesh-independence studies; comparing against a reference paper that quotes mm. |
| **C — `cells_across_span` + `adaptive_span`** | `12` cells across the **local** lumen span | 10,850 | 13 s | Geometries with branches of mixed diameter — each region sizes itself locally. |

All three are independent — set ONE in `mesh.*` and the others are
ignored. Method B takes priority over A if you set both, with a
warning logged.

##### B: `target_cell_size_mm` (absolute size control)

```json
"mesh": {
    "target_cell_size_mm": 1.5,
    "SNAPPY_SETTINGS": { "surfaceRefinementLevels": [1, 1] }
}
```

Bypasses geometry detection entirely. Useful for GCI studies where
you need a precise refinement ratio (e.g. divide by √2 between
levels), and for matching a paper that reports cell sizes in mm.

##### C: `cells_across_span` with `adaptive_span` strategy

```json
"mesh": {
    "SNAPPY_SETTINGS": {
        "mesh_strategy": "adaptive_span",
        "cells_across_span": 12,
        "surfaceRefinementLevels": [0, 1]
    }
}
```

Unlike A (which sizes off the **inlet** diameter), `adaptive_span`
sizes off the **local** lumen at each region of the mesh. This
matters most when the descending aorta and the supra-aortic
branches differ in diameter by 3-5×: method A under-resolves the
small branches, method C handles them automatically.

Try the three methods on `cases_input/ubend/` (single-outlet
U-bend, ~5 MB STL) — full mesh in under a minute on 4 CPU each.

### 1.3 Surface Refinement Levels (10 min)

```json
"SNAPPY_SETTINGS": {
    "surfaceRefinementLevels": [1, 1]
}
```

- `[min_level, max_level]` — controls refinement near surfaces
- `[1, 1]` = uniform (recommended for cardiovascular)
- `[1, 2]` = 8:1 volume jump at refinement boundary (can cause problems)
- `[2, 3]` = another 8:1 jump

**Rule:** Keep levels uniform `[n, n]` for aortic CFD. Resolution comes from cells_per_diameter.

### 1.4 Boundary Layers (20 min)

```json
"boundary_layers": {
    "enabled": true,
    "num_layers": 5,
    "expansion_ratio": 1.2,
    "final_layer_thickness": 0.4,
    "min_thickness": 0.15
}
```

Why boundary layers matter:
- WSS is computed from the velocity gradient at the wall
- Without BL cells, the first cell is too large → WSS is inaccurate
- BL cells are thin near the wall, capturing the velocity gradient

| Parameter | What it does | Typical value |
|-----------|-------------|---------------|
| `num_layers` | Number of BL cell layers | 3-10 |
| `expansion_ratio` | Each layer is this × thicker than the previous | 1.1-1.3 |
| `final_layer_thickness` | Outermost layer thickness as fraction of cell | 0.3-0.5 |
| `min_thickness` | Minimum allowed thickness (below = skip) | 0.1-0.2 |

**Exercise:** Generate two meshes — one with `num_layers: 0` (no BL) and one with `num_layers: 5`. Slice in ParaView near the wall to see the difference.

---

## Hour 2: Mesh Quality (60 min)

### 2.1 Reading checkMesh Output (20 min)

```bash
cat output/BPM120/run_xxx/openfoam/logs/log.checkMesh
```

Key metrics:
```
Max non-orthogonality = 65.2       // < 70 OK, > 75 bad
Max skewness = 3.1                 // < 4 OK, > 8 bad
Max aspect ratio = 45.3            // < 100 OK, > 1000 bad
cells: 1,993,055                   // Total cell count
```

| Metric | Good | Warning | Bad |
|--------|------|---------|-----|
| Non-orthogonality | < 60° | 60-75° | > 75° |
| Skewness | < 2 | 2-4 | > 8 |
| Aspect ratio | < 50 | 50-100 | > 1000 |

### 2.2 Mesh Quality vs Profile Selection (15 min)

Different numerical profiles tolerate different mesh quality:

| Profile | Non-ortho tolerance | Skewness tolerance |
|---------|--------------------|--------------------|
| Robust (Euler+upwind) | Any (handles bad meshes) | Any |
| Standard (backward+linearUpwind) | < 65° | < 4 |
| Precise (CN+LUST) | < 55° | < 2 |

AortaCFD warns you if the mesh is too poor for your chosen profile:
```
WARNING: mesh quality may be too poor for 'standard' profile
```

### 2.3 Exercise: Break a Mesh Intentionally (15 min)

Create a config with problematic settings:
```json
{
    "mesh": {
        "cells_per_diameter": 6,
        "SNAPPY_SETTINGS": {
            "surfaceRefinementLevels": [1, 3]
        }
    }
}
```

Run it and check:
- What does checkMesh report?
- What happens if you try to run the solver with `standard` profile?
- Switch to `robust` — does it survive?

### 2.4 Mesh Convergence Exercise (10 min)

The gold standard: run the same case on 3 mesh levels and check if results converge.

```bash
# Already done in homework — now compare:
# cpd=8:  pressure drop = ??? mmHg, TAWSS mean = ??? Pa
# cpd=12: pressure drop = ??? mmHg, TAWSS mean = ??? Pa
# cpd=16: pressure drop = ??? mmHg, TAWSS mean = ??? Pa
```

**Key insight:** Pressure converges quickly (usually cpd=12 is enough). WSS needs finer meshes (cpd=15-20).

---

### 2.5 y+ Estimation (10 min)

y+ measures how well the first cell resolves the viscous sublayer near the wall:

```
y+ = (u_τ × y) / ν
```

Where u_τ is friction velocity, y is first cell height, ν is kinematic viscosity.

| y+ | Resolution | Suitable for |
|----|-----------|-------------|
| < 1 | Wall-resolved | LES, low-Re RANS |
| 1-5 | Good | Standard RANS |
| 5-30 | Wall functions | High-Re RANS |
| > 30 | Too coarse | Not suitable |

AortaCFD estimates y+ before running the solver:
```bash
# Check y+ estimation in the setup report
grep "y+" reports/simulation_setup_report.txt
```

For laminar simulations, y+ doesn't apply — but the boundary layer still matters for WSS accuracy.

### 2.6 Regenerate-Numerics Step (5 min)

If your mesh quality is poor, you can auto-adjust the numerical schemes:

```bash
python run_patient.py BPM120 --update output/BPM120/run_xxx --steps regenerate-numerics
```

This reads the checkMesh results and adjusts fvSchemes/fvSolution to match the mesh quality. For example, if non-orthogonality is high, it may switch to more stable (but less accurate) schemes.

---

## Homework

1. Run three meshes: cpd = 8, 12, 16 on BPM120
2. Record for each: cell count, checkMesh non-orthogonality, skewness
3. If you have completed solver results, compare pressure drop and TAWSS mean
4. Plot: cell count vs pressure drop — does it converge?
5. Read: `examples/BOUNDARY_LAYER_GUIDE.md`
