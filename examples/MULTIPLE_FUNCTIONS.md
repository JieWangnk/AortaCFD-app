# Using Multiple Function Objects

## Quick Answer

**YES!** You can add multiple function objects in an array:

```json
{
  "simulation_control": {
    "controlDict": {
      "functions": [
        "wallShearStress",
        "yPlus"
      ]
    }
  }
}
```

---

## What Gets Generated

### In controlDict:

```foam
functions
{
    #includeFunc wallShearStress
    #includeFunc yPlus
}
```

Both functions execute **simultaneously** at each `writeTime`.

---

## wallShearStress + yPlus Together

### When to Use This Combination

| Simulation Type | wallShearStress | yPlus | Reason |
|----------------|-----------------|-------|---------|
| **Laminar** | ✅ Always | ⚠️ Optional | yPlus not really meaningful for laminar (will be ~0) |
| **RANS** | ✅ Recommended | ✅ Essential | Need yPlus to verify mesh quality for turbulence |
| **LES** | ✅ Recommended | ✅ Essential | Need yPlus < 1 for wall-resolved LES |

### For Your BPM120 Case (Laminar)

```json
{
  "physics": {
    "model": "laminar"  // ← Laminar flow
  },

  "simulation_control": {
    "controlDict": {
      "functions": [
        "wallShearStress",  // ✅ Useful: Shows wall shear distribution
        "yPlus"             // ⚠️ Will show near-zero (not meaningful for laminar)
      ]
    }
  }
}
```

**Result:** Both fields will be calculated, but `yPlus` won't provide much value for laminar flow.

---

## What Each Function Does

### 1. wallShearStress

**Type:** Vector field (Pa)

**Definition:**
```
τ_w = μ × (∂u/∂y)|_wall
```

**Output:**
- `wallShearStress.x`, `.y`, `.z` components
- Magnitude: `|τ_w|`

**Always useful for cardiovascular simulations** (laminar, RANS, or LES)

---

### 2. yPlus

**Type:** Scalar field (dimensionless)

**Definition:**
```
y+ = (y × u_τ) / ν

where:
  y = wall distance
  u_τ = friction velocity = √(τ_w / ρ)
  ν = kinematic viscosity
```

**Interpretation:**

| y+ Value | Mesh Quality | Suitable For |
|----------|--------------|--------------|
| **< 1** | Wall-resolved | RANS (SST, k-ω), LES |
| **1-5** | Buffer layer | Transition region |
| **30-300** | Log layer | Wall functions (RANS only) |
| **> 300** | Too coarse | Poor turbulence resolution |

**For laminar flow:**
- Turbulence is **not** modeled
- u_τ ≈ 0 → y+ ≈ 0 everywhere
- **Not meaningful** to check

---

## Output Structure

With both functions:

```
output/BPM120/run_XXX/openfoam/
├── 0/
│   ├── wallShearStress    ← Initial (zero) field
│   └── yPlus              ← Initial (zero) field
├── 0.1/
│   ├── U
│   ├── p
│   ├── wallShearStress    ← WSS at t=0.1
│   └── yPlus              ← y+ at t=0.1
├── 0.2/
│   ├── wallShearStress    ← WSS at t=0.2
│   └── yPlus              ← y+ at t=0.2
...
```

Both fields written at each `writeInterval` (0.1s in this example).

---

## Common Combinations

### For Cardiovascular Laminar Flow

```json
"functions": [
  "wallShearStress"
]
```

**Rationale:** yPlus not needed for laminar

---

### For RANS Turbulence (Wall-Resolved)

```json
"functions": [
  "wallShearStress",
  "yPlus"
]
```

**Usage:**
1. Check `yPlus < 1` on walls → Good mesh
2. Analyze `wallShearStress` for hemodynamics

---

### For Complete Flow Analysis

```json
"functions": [
  "wallShearStress",
  "yPlus",
  "vorticity",
  "Q"
]
```

**Advanced:** Includes vorticity and Q-criterion for flow structures

---

## Complete Example: 5 Functions at Once

```json
{
  "simulation_control": {
    "end_time": 2.0,
    "writeInterval": 0.1,

    "controlDict": {
      "functions": [
        "wallShearStress",
        "yPlus",
        "vorticity",
        "Q",
        "Lambda2"
      ]
    }
  }
}
```

**Generated controlDict:**
```foam
functions
{
    #includeFunc wallShearStress
    #includeFunc yPlus
    #includeFunc vorticity
    #includeFunc Q
    #includeFunc Lambda2
}
```

**Output:** 5 additional fields at each time step

---

## Available Built-in Functions

### Field Calculations

| Function | Type | Description |
|----------|------|-------------|
| `wallShearStress` | Vector | Wall shear stress |
| `yPlus` | Scalar | Wall distance in viscous units |
| `vorticity` | Vector | Vorticity (curl of velocity) |
| `Q` | Scalar | Q-criterion (vortex identification) |
| `Lambda2` | Scalar | Lambda2 criterion (vortex cores) |
| `enstrophy` | Scalar | Enstrophy (vorticity magnitude squared) |
| `grad(p)` | Vector | Pressure gradient |
| `grad(U)` | Tensor | Velocity gradient |
| `CourantNo` | Scalar | Courant number field |

### Forces and Statistics

| Function | Output | Description |
|----------|--------|-------------|
| `forces` | Log file | Forces on patches |
| `forceCoeffs` | Log file | Lift/drag coefficients |
| `pressureDrop` | Log file | Pressure difference |

### Sampling and Probes

| Function | Output | Description |
|----------|--------|-------------|
| `probes` | Time series | Point data extraction |
| `surfaces` | VTK files | Plane/surface sampling |
| `streamLines` | VTK files | Streamline visualization |

To use these, add them to the `functions` array!

---

## Performance Impact

### Computational Cost

Each function adds:
- **Calculation time:** ~1-5% overhead per function
- **Storage:** Additional fields at each time step

**Example:**
- `wallShearStress` only: +2% runtime, +10% disk space
- `wallShearStress` + `yPlus`: +4% runtime, +20% disk space
- 5 functions: +10% runtime, +50% disk space

**Generally negligible** for typical simulations.

---

## Testing Multiple Functions

Update your config:

```json
{
  "simulation_control": {
    "controlDict": {
      "functions": [
        "wallShearStress",
        "yPlus"
      ]
    }
  }
}
```

Run:
```bash
python run_patient.py BPM120 --config ./cases_input/BPM120/config_mesh_fine.json
```

Check output:
```bash
ls output/BPM120/run_*/openfoam/0.1/
# Should show both wallShearStress and yPlus
```

---

## Visualization in ParaView

**With multiple fields:**

1. Load `case.foam`
2. In **Properties**, select all fields:
   - ✅ `wallShearStress`
   - ✅ `yPlus`
   - ✅ `U`
   - ✅ `p`
3. Click **Apply**

**Switch between fields:**
- Use **Color by** dropdown to switch visualization
- Can display multiple simultaneously using **Split View**

---

## Custom Function Objects

If you need more control, create custom function files:

**File:** `system/wallShearStressCustom`

```foam
wallShearStressCustom
{
    type            wallShearStress;
    libs            ("libfieldFunctionObjects.so");

    patches         (wall_aorta);  // Specific patches only
    log             true;          // Write to log

    executeControl  timeStep;
    executeInterval 10;            // Every 10 timesteps
    writeControl    writeTime;     // Write with fields
}
```

**Then:**
```json
"functions": ["wallShearStressCustom", "yPlus"]
```

This mixes built-in `#includeFunc` with custom definitions.

---

## Summary

### ✅ Yes, You Can Use Multiple Functions!

```json
"functions": ["wallShearStress", "yPlus"]
```

### Generated Output:

```foam
functions
{
    #includeFunc wallShearStress
    #includeFunc yPlus
}
```

### For Your Laminar Case:

**Recommended:**
```json
"functions": ["wallShearStress"]
```

**Optional (includes yPlus but not very useful for laminar):**
```json
"functions": ["wallShearStress", "yPlus"]
```

### No Limit:

You can add as many as you want:
```json
"functions": ["wallShearStress", "yPlus", "vorticity", "Q", "Lambda2"]
```

All will execute simultaneously at each `writeTime`! 🎯
