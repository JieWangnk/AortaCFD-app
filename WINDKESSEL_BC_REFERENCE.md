# Windkessel Boundary Condition Reference

## Overview

AortaCFD uses **3-element Windkessel (3EWK)** boundary conditions at all outlets to simulate physiologically realistic downstream vascular resistance and compliance.

The implementation uses a **clinical MAP-based methodology** derived from cuff blood pressure measurements.

---

## Clinical Method (6-Step Protocol)

### Step 1: Calculate MAP from Cuff Pressures

**Mean Arterial Pressure (MAP):**
```
MAP = DP + (SP - DP) / 3
```

**Where:**
- SP = Systolic pressure (mmHg, e.g., 120)
- DP = Diastolic pressure (mmHg, e.g., 80)
- P_v = Venous/back pressure (mmHg, typically 0-5)

**Driving pressure:** `MAP - P_v`

---

### Step 2: Flow Distribution

Choose one method to split inlet flow among outlets:

**A. Murray's Law (default):**
```
f_i = r_i³ / Σ(r_j³)
```
Based on vessel radius cubed (physiologically realistic for minimizing work).

**B. Area-based:**
```
f_i = A_i / Σ(A_j)
```
Proportional to outlet cross-sectional area.

**C. User-specified:**
Provide explicit flow split ratios or percentage.

**Then:**
```
Q̄_i = f_i · Q̄_inlet
```

---

### Step 3: Total (DC) Resistance

**Ohm's law for fluids:**
```
R_total,i = (MAP - P_v) / Q̄_i
```

**Units:** Pa·s/m³ (or mmHg·s/mL)

---

### Step 4: Proximal Resistance (R1)

**Characteristic impedance from Pulse Wave Velocity:**
```
R1,i = Z_c = ρ · c_i / A_i
```

**Where:**
- ρ = Blood density (1060 kg/m³)
- c_i = Pulse wave velocity (PWV):
  - Large vessels (arch/thoracic): 4-6 m/s
  - Medium vessels (abdominal): 5-7 m/s
  - Small vessels (branches): 6-8 m/s
- A_i = Outlet area (m²)

**Fallback:** If PWV unknown, use `R1 = 0.1-0.2 × R_total`

---

### Step 5: Distal Resistance (R2)

```
R2,i = R_total,i - R1,i
```

If R2 < 0, adjust: `R1 = 0.1 × R_total, R2 = 0.9 × R_total`

---

### Step 6: Compliance (C)

**From diastolic decay time constant:**
```
τ = R2 · C  →  C_i = τ / R2,i
```

**Systemic tau:** 1.5-2.0 seconds (typical)

**Distribution options:**
- **Proportional:** `C_i = f_i × C_total` where `C_total = τ / R_parallel`
- **Uniform:** Same tau for all outlets

---

## Configuration Parameters

### Required (in `windkessel_settings`):

```json
{
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "systolic_pressure": 120,
      "diastolic_pressure": 80
    }
  }
}
```

### Optional Parameters:

```json
{
  "windkessel_settings": {
    "systolic_pressure": 120,
    "diastolic_pressure": 80,
    "venous_pressure": 0,
    "flow_split_method": "murray",
    "flow_split": null,
    "pwv_method": "empirical",
    "pwv": null,
    "tau": 1.8,
    "compliance_distribution": "proportional"
  }
}
```

**Parameters:**
- `venous_pressure` (mmHg): Back pressure, 0-5 typical (default: 0)
- `flow_split_method`: `"murray"` | `"area"` | `"equal"` (default: `"murray"`)
- `flow_split`: User-specified ratios (dict) or percentage (number), overrides method
- `pwv_method`: `"empirical"` | `"fallback"` (default: `"empirical"`)
- `pwv` (m/s): User-specified PWV value (overrides empirical)
- `tau` (s): Diastolic decay time constant (default: 1.8)
- `compliance_distribution`: `"proportional"` | `"uniform"` (default: `"proportional"`)

---

## Expected Parameter Values

**Typical ranges (Clinical Method):**
- **R_total**: 10⁸-10⁹ Pa·s/m³ (depends on flow split)
- **R1 (Z)**: 10⁶-10⁸ Pa·s/m³ (depends on PWV and area)
- **R2 (R)**: R_total - R1
- **C**: 10⁻⁹-10⁻⁸ m³/Pa (depends on tau and R2)

**Unit conversions:**
- 1 mmHg·s/mL = 1.333×10⁸ Pa·s/m³
- 1 mL/mmHg = 7.5×10⁻⁹ m³/Pa

---

## OpenFOAM Boundary Condition Setup

### Required Libraries

The Windkessel BC requires **two custom OpenFOAM libraries**:

1. **modularWKPressure** - Pressure BC
   - Library: `libmodularWKPressure.so`
   - Applied to: `0/p`
   - Source: https://github.com/JieWangnk/OpenFOAM-WK

2. **stabilizedWindkesselVelocity** - Velocity BC
   - Library: `libstabilizedWindkesselVelocity.so`
   - Applied to: `0/U`

### controlDict

```cpp
libs
(
    "libmodularWKPressure.so"
    "libstabilizedWindkesselVelocity.so"
);
```

### Velocity Field (0/U)

```cpp
outlet1
{
    type                stabilizedWindkesselVelocity;
    beta                1.0;
    enableStabilization true;
}
```

### Pressure Field (0/p)

```cpp
outlet1
{
    type            modularWKPressure;
    phi             phi;
    order           2;

    // Windkessel parameters (calculated automatically)
    R               1.08e9;      // R2 (distal resistance)
    C               1.44e-9;     // Compliance
    Z               2.51e8;      // R1 (proximal resistance)

    // Initial conditions
    p0              10666;
    p_1             10666;
    q_1             0;
    q_2             0;
    q_3             0;

    value           uniform 0;
}
```

---

## Scientific References

### Key Citations for Methods Section

1. **MAP Formula:**
   - Nichols WW, O'Rourke MF. *McDonald's Blood Flow in Arteries: Theoretical, Experimental and Clinical Principles*. 6th ed. London: Hodder Arnold; 2005.

2. **DC Resistance Allocation (R_total = (MAP-P_v)/Q̄):**
   - Westerhof N, Lankhaar JW, Westerhof BE. The arterial Windkessel. *Med Biol Eng Comput*. 2009;47(2):131-141. doi:10.1007/s11517-008-0359-2

3. **Characteristic Impedance (R1 = ρc/A):**
   - Westerhof et al. 2009 (above)
   - Milnor WR. *Hemodynamics*. 2nd ed. Baltimore: Williams & Wilkins; 1989.

4. **Compliance and Diastolic Decay (τ = R2·C):**
   - Stergiopulos N, Westerhof BE, Westerhof N. Total arterial inertance as the fourth element of the windkessel model. *Am J Physiol*. 1999;276(1):H81-H88.
   - Stergiopulos N, Meister JJ, Westerhof N. Determinants of stroke volume and systolic and diastolic aortic pressure. *Am J Physiol*. 1996;270(6):H2050-H2059.

5. **Murray's Law Flow Distribution:**
   - Murray CD. The physiological principle of minimum work: I. The vascular system and the cost of blood volume. *Proc Natl Acad Sci USA*. 1926;12(3):207-214.
   - Recent applications in patient-specific aortic CFD:
     - Bonfanti M, et al. *Ann Biomed Eng*. 2019;47:2683-2699.
     - Pirola S, et al. *J Biomech*. 2019;94:75-85.
     - Armour CH, et al. *Front Cardiovasc Med*. 2022;9:869625.

---

## Quick Validation Checks

After a short simulation run (1-2 cardiac cycles):

1. **Mean pressures near MAP?**
   - Check if outlet pressures ≈ MAP (validates R_total calculation)

2. **Pulse pressure reasonable?**
   - Check if (P_systolic - P_diastolic) ≈ cuff pulse pressure
   - If too high/low, tune C (compliance)

3. **Upstroke not over-damped?**
   - Check pressure waveform rise time
   - If too slow, increase R1 (prefer empirical PWV over fallback)

4. **Diastolic decay matches tau?**
   - Check exponential decay during diastole
   - Should match specified tau value

---

## Example Configuration

```json
{
  "geometry": {
    "case_name": "patient1",
    "inlet_keywords_ordered": "inlet",
    "outlet_keywords_ordered": ["outlet1", "outlet2", "outlet3", "outlet4"]
  },
  "inlet": {
    "csv_file": "inlet_flow.csv",
    "data_type": "flowRate"
  },
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "systolic_pressure": 130,
      "diastolic_pressure": 85,
      "venous_pressure": 2,
      "flow_split_method": "murray",
      "pwv_method": "empirical",
      "tau": 1.8,
      "compliance_distribution": "proportional"
    }
  },
  "physics": {
    "rho": 1060
  }
}
```

This will automatically:
1. Calculate MAP = 85 + (130-85)/3 = 100 mmHg
2. Distribute flow using Murray's law (r³)
3. Calculate R_total = (MAP-2)/Q̄ for each outlet
4. Estimate R1 from empirical PWV
5. Calculate R2 = R_total - R1
6. Distribute compliance proportionally with tau = 1.8s

---

## Notes

- All parameters are calculated **automatically** from cuff pressures and outlet geometry
- Flow split defaults to Murray's law if not specified
- PWV defaults to empirical vessel-size-based values
- Method is patient-specific and physiologically realistic
- Values suitable for clinical CFD simulations
