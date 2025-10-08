# Windkessel Boundary Condition Reference

## Reference Implementation
Based on: `/home/mchi4jw4/GitHub/OpenFOAM-WK/tutorials/CoA_test`

---

## Required Libraries

The Windkessel BC implementation requires **two custom libraries**:

### 1. modularWKPressure (Pressure BC)
- **Library:** `libmodularWKPressure.so`
- **Applied to:** Pressure field (`0/p`)
- **Function:** Implements 3-element Windkessel model with R, C, Z parameters

### 2. stabilizedWindkesselVelocity (Velocity BC)
- **Library:** `libstabilizedWindkesselVelocity.so`
- **Applied to:** Velocity field (`0/U`)
- **Function:** Prevents backflow divergence at outlets with stabilization

---

## Boundary Condition Setup

### Velocity Field (`0/U`)

**Outlet BC Type:** `stabilizedWindkesselVelocity`

```cpp
outlet1
{
    type                stabilizedWindkesselVelocity;
    beta                1.0;                    // Stabilization parameter
    enableStabilization true;                   // Enable backflow prevention
}
```

**Parameters:**
- `beta`: Stabilization coefficient (typically 1.0)
- `enableStabilization`: Enable/disable backflow stabilization (true/false)

### Pressure Field (`0/p`)

**Outlet BC Type:** `modularWKPressure`

```cpp
outlet1
{
    type            modularWKPressure;
    phi             phi;                        // Flux field name
    order           2;                          // Integration order (1 or 2)

    // Windkessel parameters
    R               252292956.15;               // Peripheral resistance [Pa·s/m³]
    C               1.585e-10;                  // Compliance [m³/Pa]
    Z               25229295.62;                // Proximal impedance [Pa·s/m³]

    // Initial conditions for temporal integration
    p0              10666;                      // Initial pressure [Pa]
    p_1             10666;                      // Pressure at t=-dt [Pa]
    q_1             0;                          // Flow at t=-dt [m³/s]
    q_2             0;                          // Flow at t=-2*dt [m³/s]
    q_3             0;                          // Flow at t=-3*dt [m³/s]

    value           uniform 0;
}
```

**Parameters:**
- `phi`: Name of the flux field (always "phi" for incompressible)
- `order`: Integration order (1 = Euler, 2 = 2nd-order)
- `R`: Distal/peripheral resistance (Pa·s/m³)
- `C`: Arterial compliance (m³/Pa)
- `Z`: Proximal/characteristic impedance (Pa·s/m³)
- `p0, p_1`: Historical pressure values for integration
- `q_1, q_2, q_3`: Historical flow values for higher-order schemes

---

## controlDict Configuration

Must load both libraries:

```cpp
libs
(
    "libmodularWKPressure.so"
    "libstabilizedWindkesselVelocity.so"
);
```

---

## Windkessel Parameter Calculation

### From CoA_test Default Values:
```
R = 1000 Pa·s/m³
C = 1e-06 m³/Pa
Z = 100 Pa·s/m³
```

### From AortaCFD Automatic Calculation:
Based on Murray's law and physiological parameters:

**Proximal Impedance (Z):**
```python
c = 13.3 / (2 * sqrt(A_mm²/π))^0.3    # Wave speed [m/s]
Z = ρ * c / A                          # [Pa·s/m³]
```

**Total Resistance (R):**
```python
mP = ((SP + DP)/2) * 133.33            # Mean pressure [Pa]
R_total = mP / Q_mean                  # Total resistance
R = R_total - Z                        # Peripheral resistance
```

**Compliance (C):**
```python
τ = 1.92                               # Time constant
C = τ / R_total                        # [m³/Pa]
```

Where:
- `A`: Outlet area [m²]
- `ρ`: Blood density (1060 kg/m³)
- `SP, DP`: Systolic/diastolic pressure (mmHg)
- `Q_mean`: Mean flow rate [m³/s]

---

## Common Issues

### ❌ Error: "Unknown patchField type stabilizedWindkesselVelocity"
**Cause:** Library not loaded in controlDict
**Solution:** Add `libstabilizedWindkesselVelocity.so` to libs

### ❌ Error: "Unknown patchField type modularWKPressure"
**Cause:** Library not loaded in controlDict
**Solution:** Add `libmodularWKPressure.so` to libs

### ❌ Divergence at outlets
**Cause:** `enableStabilization` is false or beta too small
**Solution:** Set `enableStabilization true` and `beta 1.0`

### ❌ Negative pressure at outlets
**Cause:** Windkessel parameters (R, C, Z) too small
**Solution:** Use Murray's law automatic calculation or increase parameters

---

## Implementation in AortaCFD

### Templates Updated:

1. **`src/templates/U.tpl`**
   - Uses `stabilizedWindkesselVelocity` for Windkessel outlets
   - Parameters: `beta`, `enableStabilization`

2. **`src/templates/p.tpl`**
   - Uses `modularWKPressure` for Windkessel outlets
   - Parameters: R, C, Z, historical values

3. **`src/templates/controlDict.tpl`**
   - Loads both required libraries when `3EWINDKESSEL` BC is used

### Config Example:

```json
{
  "boundary_conditions": {
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "methodology": "murray_law_automatic",
        "systolic_pressure": 120,
        "diastolic_pressure": 80,
        "beta": 1.0,
        "enable_stabilization": true
      }
    }
  }
}
```

---

## References

- CoA_test tutorial: `/home/mchi4jw4/GitHub/OpenFOAM-WK/tutorials/CoA_test`
- Windkessel calculator: `src/aortacfd_lib/windkessel_calculator.py`
- WK setup: `src/aortacfd_lib/wk_setup.py`

---

*Last Updated: 2025-10-05*
*Reference: CoA_test (OpenFOAM 12)*
