# Boundary Layer Configuration Guide

## Overview

AortaCFD provides two approaches for controlling boundary layer meshing:

1. **Automatic Y+ Estimation** (Recommended) - System calculates layer thickness to achieve target y+
2. **Manual Control** - You specify exact layer thickness, bypassing y+ estimation

---

## Approach 1: Automatic Y+ Estimation (Recommended)

### Config Example

```json
{
  "mesh": {
    "boundary_layers": {
      "enabled": true,
      "target_yplus": 1.0,
      "num_layers": 5,
      "expansion_ratio": 1.2
    }
  }
}
```

### How It Works

1. **Estimates flow conditions** from:
   - Inlet geometry (diameter, area)
   - Typical cardiac output (5 L/min default)
   - Blood properties (density, viscosity)

2. **Calculates Reynolds number** and wall shear stress using correlations

3. **Computes `finalLayerThickness`** to achieve `target_yplus`

4. **Uses your settings**:
   - `num_layers` → `nSurfaceLayers` in snappyHexMeshDict
   - `expansion_ratio` → `expansionRatio` in snappyHexMeshDict
   - Calculated value → `finalLayerThickness` in snappyHexMeshDict

### Output in snappyHexMeshDict

```foam
layers
{
    "wall_aorta"
    {
        nSurfaceLayers 5;              // From num_layers
    }
}
expansionRatio      1.2;               // From expansion_ratio
finalLayerThickness 0.0437;            // AUTO-CALCULATED for y+=1.0
relativeSizes       false;             // Auto-set for absolute units
```

### When to Use

✅ **Best for:**
- RANS simulations (y+ ≈ 1 for wall-resolved, y+ ≈ 30-300 for wall functions)
- LES simulations (y+ < 1 required)
- Consistent y+ across different patient geometries
- Publications requiring documented y+ control

### Customization Options

You can override auto-estimation parameters:

```json
{
  "mesh": {
    "boundary_layers": {
      "target_yplus": 1.0,
      "num_layers": 5,
      "expansion_ratio": 1.2,

      "estimation_method": "user_provided",
      "characteristic_velocity": 0.8,
      "characteristic_length": 0.025
    }
  }
}
```

- `estimation_method`: `"auto"` (default) or `"user_provided"`
- `characteristic_velocity`: Flow velocity in m/s (overrides auto-estimation)
- `characteristic_length`: Reference length in m (overrides inlet diameter)

---

## Approach 2: Manual Control

### Config Example

```json
{
  "mesh": {
    "boundary_layers": {
      "enabled": true,
      "target_yplus": 1.0,
      "num_layers": 5,
      "expansion_ratio": 1.2,
      "finalLayerThickness": 0.05
    }
  }
}
```

### How It Works

1. **Y+ estimation is SKIPPED** when `finalLayerThickness` is explicitly set
2. System uses your exact value (in millimeters)
3. `target_yplus` becomes **reference only** - actual y+ will vary based on flow

### Output in snappyHexMeshDict

```foam
layers
{
    "wall_aorta"
    {
        nSurfaceLayers 5;              // From num_layers
    }
}
expansionRatio      1.2;               // From expansion_ratio
finalLayerThickness 0.05;              // YOUR EXPLICIT VALUE
relativeSizes       false;             // Assumes absolute units (mm)
```

### When to Use

✅ **Best for:**
- Testing/debugging mesh generation
- When y+ estimation fails or gives unexpected results
- Known good values from previous studies
- Complex geometries where auto-estimation is unreliable
- Quick prototyping

⚠️ **Warnings:**
- Actual y+ will vary with flow conditions
- Different vessel regions will have different y+
- You're responsible for ensuring appropriate y+ for your turbulence model

---

## Configuration Fields Reference

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `enabled` | boolean | Enable/disable boundary layers | `true` |
| `num_layers` | integer | Number of boundary layers | `5` |

### Optional Fields

| Field | Type | Units | Description | Default |
|-------|------|-------|-------------|---------|
| `target_yplus` | float | - | Target y+ value (triggers auto-calculation) | - |
| `expansion_ratio` | float | - | Growth rate between layers | `1.2` |
| `finalLayerThickness` | float | mm | **OVERRIDE**: Manual layer thickness (disables y+ calc) | - |
| `estimation_method` | string | - | `"auto"` or `"user_provided"` | `"auto"` |
| `characteristic_velocity` | float | m/s | Override auto velocity estimate | auto |
| `characteristic_length` | float | m | Override auto length estimate | auto |

### Legacy Compatibility

These field names are also supported for backward compatibility:

- `n_surface_layers` → `num_layers`
- Both are accepted, `num_layers` is preferred

---

## Decision Tree

```
Do you want automatic y+ control?
│
├─ YES → Use Approach 1 (Automatic Y+ Estimation)
│   │
│   ├─ Set target_yplus (e.g., 1.0 for RANS wall-resolved)
│   ├─ Set num_layers (e.g., 5-10 for cardiovascular)
│   ├─ Set expansion_ratio (e.g., 1.2)
│   └─ DON'T set finalLayerThickness (leave it out!)
│
└─ NO → Use Approach 2 (Manual Control)
    │
    ├─ Set num_layers
    ├─ Set expansion_ratio
    ├─ Set finalLayerThickness explicitly (in mm)
    └─ target_yplus is optional (documentation only)
```

---

## Examples by Use Case

### RANS Wall-Resolved (y+ ≈ 1)

```json
{
  "boundary_layers": {
    "enabled": true,
    "target_yplus": 1.0,
    "num_layers": 5,
    "expansion_ratio": 1.2
  }
}
```

### RANS Wall Functions (y+ ≈ 30-300)

```json
{
  "boundary_layers": {
    "enabled": true,
    "target_yplus": 50,
    "num_layers": 3,
    "expansion_ratio": 1.5
  }
}
```

### LES (y+ < 1)

```json
{
  "boundary_layers": {
    "enabled": true,
    "target_yplus": 0.5,
    "num_layers": 8,
    "expansion_ratio": 1.15
  }
}
```

### Laminar (no y+ requirement, but good resolution)

```json
{
  "boundary_layers": {
    "enabled": true,
    "num_layers": 5,
    "expansion_ratio": 1.2,
    "finalLayerThickness": 0.1
  }
}
```
*Note: For laminar, y+ concept doesn't apply. Manual control is fine.*

---

## Understanding the Log Output

### Automatic Y+ Estimation

```
============================================================
Y+ BASED BOUNDARY LAYER CALCULATION
============================================================
Target y+:                  1.00
Characteristic velocity:    0.543 m/s
Characteristic length:      18.60 mm
Reynolds number:            2847 (Transitional)
Friction velocity (u_τ):    0.0289 m/s
------------------------------------------------------------
Calculated finalLayerThickness: 0.043728 mm (converted from 4.373e-05 m)
Number of layers:               5
Expansion ratio:                1.2
Total BL thickness:             0.2843 mm
Estimated y+:                   1.00
Note: Values converted to mm (mesh units) for snappyHexMesh with relativeSizes=false
============================================================
```

### Manual Override

```
============================================================
MANUAL BOUNDARY LAYER CONTROL (Y+ Estimation SKIPPED)
============================================================
Using explicit finalLayerThickness: 0.05
Target y+ (1.0) is for REFERENCE only - actual y+ will vary
============================================================
```

---

## Troubleshooting

### Issue: Boundary layers are collapsing

**Try:**
1. Reduce `num_layers` (e.g., 3 instead of 5)
2. Reduce `expansion_ratio` (e.g., 1.15 instead of 1.2)
3. Use manual control with larger `finalLayerThickness`

### Issue: Y+ estimation gives unrealistic values

**Try:**
1. Override velocity/length estimates:
   ```json
   "estimation_method": "user_provided",
   "characteristic_velocity": 0.5,
   "characteristic_length": 0.020
   ```

2. Switch to manual control if auto-estimation isn't reliable for your geometry

### Issue: Y+ too high in final simulation

**Try:**
1. Reduce `target_yplus` (e.g., from 1.0 to 0.5)
2. Increase `num_layers` for better resolution
3. Verify flow conditions match estimation assumptions

---

## See Also

- [boundary_layer_yplus_auto.json](boundary_layer_yplus_auto.json) - Full example with auto y+
- [boundary_layer_manual.json](boundary_layer_manual.json) - Full example with manual control
- [YPlusEstimator](../src/aortacfd_lib/yplus_estimator.py) - Source code for y+ calculations
- [mesh_setup.py](../src/aortacfd_lib/mesh_setup.py) - Boundary layer implementation
