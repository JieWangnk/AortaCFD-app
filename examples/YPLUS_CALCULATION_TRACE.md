# Complete Trace: How finalLayerThickness is Calculated

## Your Config (config_mesh_medium.json)

```json
{
  "boundary_layers": {
    "enabled": true,
    "target_yplus": 1.0,
    "num_layers": 10,
    "expansion_ratio": 1.2,
    "estimation_method": "auto"
  }
}
```

**Key:** No `finalLayerThickness` specified → **Automatic Y+ Estimation Mode**

---

## Step-by-Step Calculation Flow

### Step 1: Trigger Check ([mesh_setup.py:627-635](../src/aortacfd_lib/mesh_setup.py#L627-L635))

```python
boundary_layer_config = self.mesh_settings.get('boundary_layers', {})
target_yplus = boundary_layer_config.get('target_yplus')  # → 1.0

if target_yplus is not None:
    self._apply_yplus_layer_sizing(...)  # ✅ Called because target_yplus=1.0
```

**Decision:** Since `target_yplus=1.0` is specified, automatic calculation is triggered.

---

### Step 2: Manual Override Check ([mesh_setup.py:668-684](../src/aortacfd_lib/mesh_setup.py#L668-L684))

```python
explicit_final_thickness = boundary_layer_config.get('finalLayerThickness')  # → None

if explicit_final_thickness is not None:
    # Skip y+ calculation (manual mode)
    return
```

**Decision:** No manual override found → **Proceed with automatic calculation**

---

### Step 3: Gather Inputs ([mesh_setup.py:686-728](../src/aortacfd_lib/mesh_setup.py#L686-L728))

#### 3a. Fluid Properties

```python
density = physics.get('blood_density') or 1060.0      # → 1060 kg/m³
viscosity = physics.get('blood_viscosity') or 0.004   # → 0.004 Pa·s (from config: nu=3.7736e-6)
nu = viscosity / density                               # → 3.77e-6 m²/s
```

**From your config:**
```json
"transport_properties": {
  "rho": 1060,
  "nu": 3.7736e-6
}
```

**Note:** `nu` is kinematic viscosity (m²/s), converted to dynamic viscosity: `μ = ν × ρ = 3.7736e-6 × 1060 = 0.004 Pa·s`

#### 3b. Flow Estimation (Auto Mode)

```python
estimation_method = boundary_layer_config.get('estimation_method')  # → "auto"

if estimation_method == 'auto':
    # Use inlet geometry
    char_length = 2.0 * inlet_radius / 1000.0  # Convert mm to m
                # = 2.0 × 5.63 / 1000 = 0.01126 m = 11.26 mm

    # Estimate velocity from typical cardiac output (5 L/min)
    inlet_area_m2 = π × (inlet_radius/1000)²
                  # = π × (5.63/1000)² = 9.95e-5 m²

    typical_flow_m3s = 8.33e-5  # 5 L/min in m³/s

    char_velocity = typical_flow_m3s / inlet_area_m2
                  # = 8.33e-5 / 9.95e-5 = 0.837 m/s
```

**Estimated from geometry:**
- Characteristic length: **11.26 mm** (inlet diameter)
- Characteristic velocity: **0.837 m/s** (from 5 L/min cardiac output)

#### 3c. Layer Parameters

```python
n_layers = snappy_settings.get('addLayer', 5)  # → 10 (from your num_layers)
expansion_ratio = snappy_settings.get('expansionRatio', 1.2)  # → 1.2 (from your config)
```

---

### Step 4: Y+ Calculation ([yplus_estimator.py:54-136](../src/aortacfd_lib/yplus_estimator.py#L54-L136))

#### 4a. Reynolds Number

```python
Re = (ρ × U × L) / μ
   = (1060 × 0.837 × 0.01126) / 0.004
   = 2496
```

**Flow regime:** Transitional (2300 < Re < 4000)

#### 4b. Friction Factor

For transitional flow, use turbulent correlation (Blasius):

```python
f = 0.316 / Re^0.25
  = 0.316 / 2496^0.25
  = 0.316 / 7.07
  = 0.0447
```

#### 4c. Friction Velocity (u_τ)

```python
u_τ = U_mean × √(f/8)
    = 0.837 × √(0.0447/8)
    = 0.837 × √0.00559
    = 0.837 × 0.0747
    = 0.0625 m/s
```

**Friction velocity:** 0.0625 m/s

#### 4d. First Layer Thickness (Δy₁)

**The core formula:**

```
y+ = (Δy × u_τ) / ν

Solving for Δy:
Δy = y+ × ν / u_τ
```

**Calculate:**

```python
delta_y1 = target_yplus × nu / u_tau
         = 1.0 × 3.77e-6 / 0.0625
         = 6.033722e-5 m
         = 0.060337 mm
```

**First layer thickness:** **0.060337 mm**

#### 4e. Total Boundary Layer Thickness

With geometric expansion:

```python
Δ_total = Δy₁ × (r^n - 1) / (r - 1)
        = 0.060337 × (1.2^10 - 1) / (1.2 - 1)
        = 0.060337 × (6.1917 - 1) / 0.2
        = 0.060337 × 25.959
        = 1.5663 mm
```

#### 4f. Verify Y+

```python
estimated_yplus = delta_y1 × u_tau / nu
                = 6.033e-5 × 0.0625 / 3.77e-6
                = 1.00 ✅
```

---

### Step 5: Unit Conversion ([mesh_setup.py:749-757](../src/aortacfd_lib/mesh_setup.py#L749-L757))

```python
# Y+ calculator returns thickness in METERS
finalLayerThickness_meters = results['finalLayerThickness']  # = 6.033722e-5 m

# BUT mesh is in MILLIMETERS (STL, blockMesh all in mm)
# snappyHexMesh with relativeSizes=false expects values in mesh units (mm)
finalLayerThickness_mm = finalLayerThickness_meters × 1000.0
                       = 6.033722e-5 × 1000
                       = 0.060337 mm

snappy_settings['finalLayerThickness'] = finalLayerThickness_mm  # = 0.060337
snappy_settings['relativeSizes'] = False  # Use absolute units (mm)
```

---

### Step 6: Write to snappyHexMeshDict ([mesh_setup.py:649](../src/aortacfd_lib/mesh_setup.py#L649))

**Template ([snappyHexMeshDict.tpl:123](../src/templates/snappyHexMeshDict.tpl#L123)):**

```jinja
nSurfaceLayers {{ config.mesh.SNAPPY_SETTINGS.get('addLayer', 5) }};
expansionRatio {{ config.mesh.SNAPPY_SETTINGS.get('expansionRatio', 1.2) }};
finalLayerThickness {{ config.mesh.SNAPPY_SETTINGS.get('finalLayerThickness', 0.2) }};
relativeSizes {{ 'true' if config.mesh.SNAPPY_SETTINGS.get('relativeSizes', True) else 'false' }};
```

**Output:**

```foam
layers
{
    "wall_aorta"
    {
        nSurfaceLayers 10;              // From num_layers=10
    }
}
expansionRatio      1.2;                // From expansion_ratio=1.2
finalLayerThickness 0.060337;           // CALCULATED for y+=1.0
relativeSizes       false;              // Auto-set for absolute units (mm)
```

---

## Summary of Complete Calculation

### Inputs (from your config)

| Parameter | Value | Source |
|-----------|-------|--------|
| `target_yplus` | 1.0 | Your config |
| `num_layers` | 10 | Your config |
| `expansion_ratio` | 1.2 | Your config |
| `rho` | 1060 kg/m³ | Your config |
| `nu` | 3.7736e-6 m²/s | Your config |
| `estimation_method` | "auto" | Your config |

### Auto-Estimated (from geometry)

| Parameter | Value | How |
|-----------|-------|-----|
| Inlet radius | 5.63 mm | Read from STL geometry |
| Characteristic length | 11.26 mm | 2 × inlet_radius |
| Characteristic velocity | 0.837 m/s | Assuming 5 L/min cardiac output |

### Calculated (fluid mechanics)

| Parameter | Value | Formula |
|-----------|-------|---------|
| Reynolds number | 2496 | Re = ρUL/μ |
| Flow regime | Transitional | 2300 < Re < 4000 |
| Friction factor | 0.0447 | Blasius: f = 0.316/Re^0.25 |
| Friction velocity | 0.0625 m/s | u_τ = U√(f/8) |
| **First layer Δy** | **0.060337 mm** | **Δy = y+×ν/u_τ** |
| Total BL thickness | 1.5663 mm | Geometric series |

### Final Output (snappyHexMeshDict)

```foam
nSurfaceLayers 10
expansionRatio 1.2
finalLayerThickness 0.060337  ← CALCULATED VALUE
relativeSizes false
```

---

## Key Formulas Reference

### Y+ Definition
```
y+ = (y × u_τ) / ν
```
Where:
- `y` = distance from wall (first layer thickness)
- `u_τ` = friction velocity
- `ν` = kinematic viscosity

### Friction Velocity
```
u_τ = U_mean × √(f/8)
```
Where:
- `U_mean` = characteristic velocity
- `f` = Darcy friction factor

### Friction Factor Correlations

**Laminar (Re < 2300):**
```
f = 64 / Re
```

**Turbulent (Re > 4000):**
```
f = 0.316 / Re^0.25  (Blasius, Re < 100,000)
f = 0.0032 + 0.221 / Re^0.237  (Prandtl-Karman, Re > 100,000)
```

### First Layer Thickness (Solving for y)
```
y = y+ × ν / u_τ
```

### Total Boundary Layer Thickness (Geometric Series)
```
Δ_total = Δy₁ × (r^n - 1) / (r - 1)
```
Where:
- `r` = expansion_ratio
- `n` = num_layers

---

## Override Mode (Manual Control)

If you add `finalLayerThickness` to your config:

```json
{
  "boundary_layers": {
    "target_yplus": 1.0,
    "num_layers": 10,
    "expansion_ratio": 1.2,
    "finalLayerThickness": 0.08  ← MANUAL OVERRIDE
  }
}
```

**Then:**
- All above calculations are **SKIPPED**
- `finalLayerThickness = 0.08` directly
- `target_yplus` becomes documentation only
- Actual y+ will vary with flow conditions

---

## Validation & Warnings

The system also validates the calculated settings:

1. **BL thickness vs vessel size:** Warns if total BL > 50% of diameter
2. **Solver type vs Reynolds:** Warns if using laminar solver with Re > 4000
3. **Layer resolution:** Checks if first layer is too coarse/fine for cell size

See validation warnings in the log output after calculation.

---

## Customizing Auto-Estimation

You can override the velocity/length estimation:

```json
{
  "boundary_layers": {
    "target_yplus": 1.0,
    "num_layers": 10,
    "expansion_ratio": 1.2,

    "estimation_method": "user_provided",
    "characteristic_velocity": 0.6,
    "characteristic_length": 0.020
  }
}
```

This uses your specified values instead of auto-estimation from geometry.

---

## References

- Source code: [yplus_estimator.py](../src/aortacfd_lib/yplus_estimator.py)
- Mesh setup: [mesh_setup.py:651-793](../src/aortacfd_lib/mesh_setup.py#L651-L793)
- Template: [snappyHexMeshDict.tpl](../src/templates/snappyHexMeshDict.tpl)
