# WKEmpirical Methodology - Pure Empirical Formulas

## Overview
The `WKEmpirical` methodology now uses **pure empirical formulas** without any base value scaling. This calculates Windkessel parameters directly from flow data, pressure, and geometry.

## Formulas Used

### 1. Total Resistance (R_total)
**Ohm's Law for Fluids:**
```
R_total = mean_pressure / mean_flow
```

**Where:**
- `mean_pressure` = ((SP + DP) / 2) × 133.33 Pa
  - SP = systolic pressure (mmHg)
  - DP = diastolic pressure (mmHg)
  - 133.33 = mmHg to Pa conversion
- `mean_flow` = average flow rate (m³/s) for each outlet

**Units:** Pa·s/m³

---

### 2. Wave Speed (c)
**Empirical formula:**
```
c = a / (2 × √(A/π))^b
```

**Where:**
- `a` = 13.3 (empirical constant)
- `b` = 0.3 (empirical constant)
- `A` = outlet area (m²)
- Formula uses `A × 1e6` to convert m² → mm² for the empirical constants

**Units:** m/s

**Source:** This is a simplified arterial wave speed formula used in 1D blood flow modeling

---

### 3. Proximal Resistance (Z)
**Characteristic impedance:**
```
Z = ρ × c / A
```

**Where:**
- `ρ` = blood density (kg/m³) [typically 1060]
- `c` = wave speed (m/s) [from formula above]
- `A` = outlet area (m²)

**Units:**
- (kg/m³) × (m/s) / m² = kg/(m²·s) = Pa·s/m³ ✓

**Physical meaning:** Resistance to pulsatile flow in the proximal vessel segment

---

### 4. Peripheral Resistance (R)
**Remaining resistance:**
```
R = R_total - Z
if R < 0: R = 0
```

**Units:** Pa·s/m³

**Physical meaning:** Resistance of the downstream vascular bed (arterioles, capillaries)

---

### 5. Compliance (C)
**Time constant formula:**
```
C = τ / R_total
```

**Where:**
- `τ` = 1.92 (empirical time constant, seconds)
- `R_total` = total resistance (Pa·s/m³)

**Units:**
- s / (Pa·s/m³) = m³/Pa ✓

**Physical meaning:** Arterial compliance (vessel distensibility)

---

## Example Calculation

### Input:
- **Systolic pressure**: 120 mmHg
- **Diastolic pressure**: 80 mmHg
- **outlet1 mean flow**: 1.0×10⁻⁵ m³/s (10% of total)
- **outlet1 area**: 3.14×10⁻⁵ m² (π × (0.003m)² = 3mm diameter)
- **Blood density**: 1060 kg/m³

### Step-by-step:

**1. Mean pressure:**
```
mP = ((120 + 80) / 2) × 133.33 = 100 × 133.33 = 13,333 Pa
```

**2. R_total:**
```
R_total = 13,333 / (1.0×10⁻⁵) = 1,333,300,000 Pa·s/m³
```

**3. Wave speed:**
```
A_mm² = 3.14×10⁻⁵ × 1e6 = 31.4 mm²
c = 13.3 / (2 × √(31.4/π))^0.3
  = 13.3 / (2 × √9.998)^0.3
  = 13.3 / (2 × 3.162)^0.3
  = 13.3 / (6.324)^0.3
  = 13.3 / 1.785
  = 7.45 m/s
```

**4. Proximal resistance (Z):**
```
Z = 1060 × 7.45 / (3.14×10⁻⁵)
  = 7,897 / (3.14×10⁻⁵)
  = 251,400,000 Pa·s/m³
```

**5. Peripheral resistance (R):**
```
R = 1,333,300,000 - 251,400,000 = 1,081,900,000 Pa·s/m³
```

**6. Compliance (C):**
```
C = 1.92 / 1,333,300,000 = 1.44×10⁻⁹ m³/Pa
```

### Results:
- **R** = 1.08×10⁹ Pa·s/m³ (very large!)
- **C** = 1.44×10⁻⁹ m³/Pa (very small!)
- **Z** = 2.51×10⁸ Pa·s/m³ (large!)

---

## Warning: Large Values!

These empirical formulas produce **very large R values** (~1-5 billion Pa·s/m³) because:

1. **Tiny flows**: Aortic branch flows are ~10⁻⁵ m³/s
2. **R = P/Q**: Dividing pressure by tiny flow gives huge R
3. **This matches medical literature** but may cause **numerical instability** in CFD!

### Comparison:

| Method | R (Pa·s/m³) | C (m³/Pa) | Notes |
|--------|-------------|-----------|-------|
| **WKEmpirical (pure)** | 1-5 billion | 1e-9 to 1e-10 | Matches medical measurements |
| **Murray's law (scaled)** | 1,000-10,000 | 1e-6 | CFD-friendly values |
| **Literature reference** | 1-5 billion | 7.5e-10 to 4.5e-9 | Measured values |

---

## Usage in Config

```json
{
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "methodology": "WKEmpirical",
      "systolic_pressure": 120,
      "diastolic_pressure": 80,
      "flow_split": 30
    }
  }
}
```

This will now calculate R, C, Z using the **pure empirical formulas** above.

---

## Expected Behavior

**You will see VERY LARGE values:**
- R ~ 10⁸ to 10⁹ Pa·s/m³ (hundreds of millions to billions)
- C ~ 10⁻⁹ to 10⁻¹⁰ m³/Pa
- Z ~ 10⁷ to 10⁸ Pa·s/m³

**This may cause simulation instability!** If the solver crashes or timestep collapses, switch back to `murray_law_automatic` for CFD-friendly scaled values.

---

## Alternative: Murray's Law (Recommended for CFD)

```json
"methodology": "murray_law_automatic"
```

Uses R_base=1000 with flow-ratio scaling, producing stable CFD simulations.
