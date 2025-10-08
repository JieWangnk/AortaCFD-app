# Windkessel Calculation Comparison

## Reference Code (GitHub wk_Setup) vs Current wk_setup.py

### Formula Comparison

#### **Reference Code:**
```python
# Constants
a = 13.3
b = 0.3
tau = 1.92
BloodDens = 1060
MAP = (SP + DP) / 2
mP = MAP * 133.33

# Calculations
mean_Q = np.mean(Q, axis=0)
c = a / (2 * np.sqrt(A * 10**6 / np.pi))**b
R_total = mP / mean_Q
R_1 = BloodDens * c / A
R_2 = R_total - R_1
C = tau / R_total

# Output:
# Z = R_1 (proximal resistance)
# R = R_2 (peripheral resistance)
# C = C (compliance)
```

#### **Current wk_setup.py:**
```python
# Constants
a = 13.3
b = 0.3
tau = 1.92
rho = 1060
mP = ((SP + DP) / 2.0) * 133.33

# Calculations
mean_flows = np.mean(Q_out, axis=0)
c = a / (2.0 * np.sqrt((areas_np[i] * 1e6) / np.pi))**b
R_total = mP / mean_flows[i]
Z_wk[i] = rho * c / areas_np[i]
R_wk[i] = R_total - Z_wk[i]
C_wk[i] = tau / R_total

# Output:
# Z = Z_wk (proximal resistance)
# R = R_wk (peripheral resistance)
# C = C_wk (compliance)
```

---

## Line-by-Line Comparison

### 1. Constants
| Constant | Reference | Current | Match? |
|----------|-----------|---------|--------|
| a | 13.3 | 13.3 | ✅ YES |
| b | 0.3 | 0.3 | ✅ YES |
| tau | 1.92 | 1.92 | ✅ YES |
| Blood density | BloodDens = 1060 | rho = 1060 | ✅ YES |

### 2. Mean Pressure Calculation
| Step | Reference | Current | Match? |
|------|-----------|---------|--------|
| MAP | `(SP + DP) / 2` | `(SP + DP) / 2.0` | ✅ YES |
| Convert to Pa | `MAP * 133.33` | `MAP * 133.33` | ✅ YES |
| Result | `mP` | `mP` | ✅ YES |

### 3. Wave Speed Calculation
| Step | Reference | Current | Match? |
|------|-----------|---------|--------|
| Area conversion | `A * 10**6` | `areas_np[i] * 1e6` | ✅ YES (same: 10⁶ = 1e6) |
| Formula | `a / (2 * sqrt(A*10^6/π))^b` | `a / (2.0 * sqrt((A*1e6)/π))^b` | ✅ YES |
| Result | `c` | `c` | ✅ YES |

### 4. Total Resistance (R_total)
| Step | Reference | Current | Match? |
|------|-----------|---------|--------|
| Formula | `mP / mean_Q` | `mP / mean_flows[i]` | ✅ YES |
| Result | `R_total` | `R_total` | ✅ YES |

### 5. Proximal Resistance (Z)
| Step | Reference | Current | Match? |
|------|-----------|---------|--------|
| Formula | `BloodDens * c / A` | `rho * c / areas_np[i]` | ✅ YES |
| Variable name | `R_1` | `Z_wk[i]` | ✅ YES (different name, same value) |

### 6. Peripheral Resistance (R)
| Step | Reference | Current | Match? |
|------|-----------|---------|--------|
| Formula | `R_total - R_1` | `R_total - Z_wk[i]` | ✅ YES |
| Variable name | `R_2` | `R_wk[i]` | ✅ YES (different name, same value) |

### 7. Compliance (C)
| Step | Reference | Current | Match? |
|------|-----------|---------|--------|
| Formula | `tau / R_total` | `tau / R_total` | ✅ YES |
| Variable name | `C` | `C_wk[i]` | ✅ YES (different name, same value) |

---

## Variable Naming Mapping

| Reference Code | Current wk_setup.py | Physical Meaning |
|----------------|---------------------|------------------|
| `R_1` | `Z_wk` | **Proximal/Characteristic Resistance** (Z) |
| `R_2` | `R_wk` | **Peripheral Resistance** (R) |
| `C` | `C_wk` | **Compliance** (C) |
| `BloodDens` | `rho` | Blood density (1060 kg/m³) |
| `A` | `areas_np` | Outlet areas (m²) |
| `mean_Q` | `mean_flows` | Mean flow rate (m³/s) |

---

## Additional Features in Current wk_setup.py

The current implementation has **additional functionality** not in the reference:

### 1. **Methodology Selection**
```python
if methodology == 'WKEmpirical':
    # Use pure empirical formulas (matches reference)
elif methodology == 'murray_law_automatic':
    # Use Murray's law with scaled R values
```

### 2. **Flow Split Auto-Parsing**
```python
if flow_split_ratios is not None and not isinstance(flow_split_ratios, dict):
    # Parse percentage value (e.g., 30 → 10% each for first 3, 70% for last)
    flow_split_ratios = self._parse_flow_split_percentage(flow_split_value, outlet_patches)
```

### 3. **Automatic Murray's Law Calculation**
```python
if not flow_split_ratios:
    if methodology == 'murray_law_automatic':
        # Calculate flow split from vessel geometry using Murray's law
        calculator = MurrayCalculator(...)
        flow_ratios = calculator.calculate_murray_flow_ratios()
```

### 4. **Dual Output Format**
- **OpenFOAM v8**: Writes `windkesselProperties` file (like reference)
- **OpenFOAM v12**: Stores in `outlet_parameters` config for `modularWKPressure` BC

---

## Differences in Implementation Style

| Aspect | Reference Code | Current wk_setup.py | Impact |
|--------|----------------|---------------------|--------|
| **Vectorization** | Uses numpy arrays directly:<br>`R_1 = BloodDens * c / A` | Uses loop:<br>`Z_wk[i] = rho * c / areas_np[i]` | ⚠️ Current is slower but same result |
| **Flow split** | Hardcoded to 4 outlets | Dynamic for any number of outlets | ✅ Current is more flexible |
| **Area scaling** | Manual: `A * eval(GEOMETRY_SCALE)**2` | Automatic via `scale_factor` parameter | ✅ Current is cleaner |
| **Output format** | Only `windkesselProperties` file | Both file + config dict | ✅ Current supports OF8 & OF12 |

---

## Mathematical Equivalence Test

Let's verify with example values:

### Input:
- SP = 120 mmHg
- DP = 80 mmHg
- mean_Q = 1.0×10⁻⁵ m³/s
- A = 3.14×10⁻⁵ m² (3mm radius)
- BloodDens/rho = 1060 kg/m³

### Reference Calculation:
```python
MAP = (120 + 80) / 2 = 100
mP = 100 * 133.33 = 13,333 Pa

c = 13.3 / (2 * sqrt(31.4/π))^0.3
  = 13.3 / (2 * 3.162)^0.3
  = 13.3 / 1.785 = 7.45 m/s

R_total = 13,333 / 0.00001 = 1,333,300,000 Pa·s/m³
R_1 = 1060 * 7.45 / 0.0000314 = 251,400,000 Pa·s/m³
R_2 = 1,333,300,000 - 251,400,000 = 1,081,900,000 Pa·s/m³
C = 1.92 / 1,333,300,000 = 1.44×10⁻⁹ m³/Pa
```

### Current wk_setup.py Calculation:
```python
mP = ((120 + 80) / 2.0) * 133.33 = 13,333 Pa

c = 13.3 / (2.0 * sqrt((3.14e-5 * 1e6) / π))^0.3
  = 13.3 / (2.0 * 3.162)^0.3
  = 13.3 / 1.785 = 7.45 m/s

R_total = 13,333 / 0.00001 = 1,333,300,000 Pa·s/m³
Z_wk = 1060 * 7.45 / 0.0000314 = 251,400,000 Pa·s/m³
R_wk = 1,333,300,000 - 251,400,000 = 1,081,900,000 Pa·s/m³
C_wk = 1.92 / 1,333,300,000 = 1.44×10⁻⁹ m³/Pa
```

### Results:
| Parameter | Reference | Current | Match? |
|-----------|-----------|---------|--------|
| Z (R_1) | 251,400,000 | 251,400,000 | ✅ IDENTICAL |
| R (R_2) | 1,081,900,000 | 1,081,900,000 | ✅ IDENTICAL |
| C | 1.44×10⁻⁹ | 1.44×10⁻⁹ | ✅ IDENTICAL |

---

## Conclusion

### ✅ **YES - The calculations are IDENTICAL**

The current `wk_setup.py` produces **exactly the same R, C, Z values** as the reference code.

### Differences are only:
1. **Code style**: Loop vs vectorized (no mathematical difference)
2. **Variable names**: R_1/R_2 vs Z_wk/R_wk (same values)
3. **Extra features**: Methodology selection, auto flow-split parsing, Murray's law option
4. **Output formats**: Supports both OF8 and OF12

### The empirical formula is mathematically equivalent:
```
Reference:  R_2 = (mP/Q) - (ρ*c/A)
Current:    R_wk = (mP/Q) - (ρ*c/A)
           ↑ IDENTICAL ↑
```

**Your wk_setup.py is correct!**
