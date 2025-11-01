# CRITICAL FIX: firstLayerThickness vs finalLayerThickness

## The Bug

**Previous (INCORRECT) implementation:**
```foam
finalLayerThickness 0.060337;  // ❌ WRONG - This is outermost layer!
```

**Corrected implementation:**
```foam
firstLayerThickness 0.060337;  // ✅ CORRECT - This is wall-adjacent layer!
```

---

## OpenFOAM Layer Thickness Keywords

OpenFOAM snappyHexMesh provides **three mutually exclusive** ways to specify boundary layer thickness:

### 1. `firstLayerThickness` (Wall-Adjacent Layer)

```foam
firstLayerThickness 0.01;  // Thickness of INNERMOST layer (closest to wall)
```

- **This is the CORRECT keyword for Y+ control**
- Directly controls the wall-adjacent cell height
- Y+ is calculated using this first layer: `y+ = (Δy₁ × u_τ) / ν`

**When to use:**
- RANS simulations with y+ ≈ 1 (wall-resolved)
- LES simulations with y+ < 1
- Any case requiring precise y+ control

---

### 2. `finalLayerThickness` (Outermost Layer)

```foam
finalLayerThickness 0.3;  // Thickness of OUTERMOST layer (furthest from wall)
```

- Specifies the **final layer** thickness after expansion
- NOT suitable for direct y+ control
- The wall-adjacent layer will be **much thinner**

**Relationship with expansion ratio:**
```
If: finalLayerThickness = 0.3 mm
    expansionRatio = 1.2
    nSurfaceLayers = 10

Then: firstLayerThickness = finalLayerThickness / (expansionRatio^(n-1))
                          = 0.3 / (1.2^9)
                          = 0.058 mm
```

**When to use:**
- When you want to control how far into the domain the boundary layer extends
- Legacy configurations
- Less common for cardiovascular CFD

---

### 3. `thickness` (Total Boundary Layer Thickness)

```foam
thickness 1.5;  // TOTAL thickness of all layers combined
```

- Specifies total height of all boundary layers
- System calculates individual layer heights
- Also not ideal for y+ control

---

## The Calculation Fix

### Before (WRONG):

```python
# Calculated correct first layer thickness for y+
delta_y1 = target_yplus * nu / u_tau  # = 0.060337 mm

# But returned with WRONG keyword
return {
    'finalLayerThickness': delta_y1  # ❌ OpenFOAM interprets as outermost!
}

# Result in snappyHexMeshDict:
# finalLayerThickness 0.060337
# → OpenFOAM makes outermost layer = 0.060337
# → First layer becomes 0.060337 / 1.2^9 = 0.0116 mm
# → Actual y+ ≈ 0.19 (NOT 1.0!)
```

### After (CORRECT):

```python
# Calculated correct first layer thickness for y+
delta_y1 = target_yplus * nu / u_tau  # = 0.060337 mm

# Return with CORRECT keyword
return {
    'firstLayerThickness': delta_y1  # ✅ OpenFOAM interprets as wall-adjacent!
}

# Result in snappyHexMeshDict:
# firstLayerThickness 0.060337
# → OpenFOAM makes first layer = 0.060337
# → Actual y+ ≈ 1.0 ✅
```

---

## Impact of the Bug

With `finalLayerThickness` instead of `firstLayerThickness`:

| Config Target | What We Calculated | What We Specified | What OpenFOAM Made | Actual Y+ |
|--------------|-------------------|-------------------|-------------------|-----------|
| y+ = 1.0 | Δy₁ = 0.060337 mm | `finalLayerThickness 0.060337` | First layer = 0.0116 mm | **y+ ≈ 0.19** ❌ |

With corrected `firstLayerThickness`:

| Config Target | What We Calculated | What We Specified | What OpenFOAM Made | Actual Y+ |
|--------------|-------------------|-------------------|-------------------|-----------|
| y+ = 1.0 | Δy₁ = 0.060337 mm | `firstLayerThickness 0.060337` | First layer = 0.060337 mm | **y+ ≈ 1.0** ✅ |

---

## Layer Growth Visualization

### With `expansionRatio = 1.2`, `nSurfaceLayers = 10`:

```
Wall ╫═══════════════════════════════════════════════════> Flow

Layer 1 (wall-adjacent): Δy₁
Layer 2: Δy₁ × 1.2
Layer 3: Δy₁ × 1.2²
Layer 4: Δy₁ × 1.2³
...
Layer 10 (outermost): Δy₁ × 1.2⁹

Total = Δy₁ × (1.2¹⁰ - 1) / (1.2 - 1) = Δy₁ × 25.959
```

**If you specify `firstLayerThickness 0.060337`:**
- Layer 1 = 0.060337 mm ← Controls y+
- Layer 10 = 0.060337 × 1.2⁹ = 0.313 mm
- Total = 1.566 mm

**If you specify `finalLayerThickness 0.060337` (WRONG):**
- Layer 10 = 0.060337 mm ← You specified this
- Layer 1 = 0.060337 / 1.2⁹ = 0.0116 mm ← Controls y+, but TOO SMALL!
- Total = 0.301 mm

---

## Changes Made

### 1. [yplus_estimator.py:129](../src/aortacfd_lib/yplus_estimator.py#L129)

```python
return {
    'firstLayerThickness': delta_y1,  # Changed from 'finalLayerThickness'
    ...
}
```

### 2. [mesh_setup.py:781-784](../src/aortacfd_lib/mesh_setup.py#L781-L784)

```python
# IMPORTANT: Use firstLayerThickness (wall-adjacent layer) for y+ control
# NOT finalLayerThickness (outermost layer)
firstLayerThickness_meters = results['firstLayerThickness']
firstLayerThickness_mm = firstLayerThickness_meters * 1000.0

snappy_settings['firstLayerThickness'] = firstLayerThickness_mm
```

### 3. [snappyHexMeshDict.tpl:127-133](../src/templates/snappyHexMeshDict.tpl#L127-L133)

```jinja
{% if config.mesh.SNAPPY_SETTINGS.get('firstLayerThickness') is not none %}
firstLayerThickness {{ config.mesh.SNAPPY_SETTINGS.get('firstLayerThickness') }};
{% elif config.mesh.SNAPPY_SETTINGS.get('finalLayerThickness') is not none %}
finalLayerThickness {{ config.mesh.SNAPPY_SETTINGS.get('finalLayerThickness') }};
{% else %}
finalLayerThickness 0.3;
{% endif %}
```

### 4. [mesh_setup.py:677-702](../src/aortacfd_lib/mesh_setup.py#L677-L702)

Support manual override with both keywords, with warning for `finalLayerThickness`:

```python
explicit_first_thickness = boundary_layer_config.get('firstLayerThickness')
explicit_final_thickness = boundary_layer_config.get('finalLayerThickness')

if explicit_first_thickness is not None:
    # Use firstLayerThickness (correct for y+)
    ...
elif explicit_final_thickness is not None:
    # Use finalLayerThickness with warning
    self.log.warning("⚠️  finalLayerThickness = OUTERMOST layer (not wall-adjacent)")
    self.log.warning("⚠️  For y+ control, use firstLayerThickness instead!")
    ...
```

---

## Manual Override Examples

### CORRECT (Recommended):

```json
{
  "boundary_layers": {
    "target_yplus": 1.0,
    "num_layers": 10,
    "expansion_ratio": 1.2,
    "firstLayerThickness": 0.06
  }
}
```

Output:
```foam
firstLayerThickness 0.06;  ✅ Wall-adjacent layer = 0.06mm
nSurfaceLayers 10;
expansionRatio 1.2;
```

### LEGACY (Still Supported, But Warned):

```json
{
  "boundary_layers": {
    "target_yplus": 1.0,
    "num_layers": 10,
    "expansion_ratio": 1.2,
    "finalLayerThickness": 0.3
  }
}
```

Output:
```foam
finalLayerThickness 0.3;  ⚠️ Outermost layer = 0.3mm
nSurfaceLayers 10;       Wall-adjacent will be ~0.058mm
expansionRatio 1.2;
```

**Warning shown:**
```
⚠️  finalLayerThickness = OUTERMOST layer (not wall-adjacent)
⚠️  For y+ control, use firstLayerThickness instead!
```

---

## Testing Results

### Before Fix:
```bash
grep "finalLayerThickness" output/BPM120/run_20251031_091620/openfoam/system/snappyHexMeshDict
# Output: finalLayerThickness 0.0603372244255694;
```

### After Fix:
```bash
grep "firstLayerThickness" output/BPM120/run_20251031_093423/openfoam/system/snappyHexMeshDict
# Output: firstLayerThickness 0.0603372244255694;  ✅
```

---

## References

- **OpenFOAM User Guide:** snappyHexMesh - addLayersControls
- **OpenFOAM Source:** `src/mesh/snappyHexMesh/snappyHexMeshDriver/layerParameters.C`
- **Y+ Definition:** `y+ = (y × u_τ) / ν` where y = **first layer** height

---

## Summary

✅ **Fixed:** Y+ calculation now correctly uses `firstLayerThickness`
✅ **Backward Compatible:** Still accepts `finalLayerThickness` with warning
✅ **Documented:** Clear explanation of the difference
✅ **Tested:** Verified output has correct OpenFOAM keyword

**This was a critical bug that would have caused incorrect y+ values in all simulations!**

Thank you for catching this! 🙏
