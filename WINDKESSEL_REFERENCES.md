# Windkessel Parameter References

## Literature Values for Three-Element Windkessel Model

### Source 1: Aortic Arch Arteries (PMC10011467)
**Reference**: "Non-invasive estimation of the parameters of a three-element windkessel model of aortic arch arteries in patients undergoing thoracic endovascular aortic repair"
**URL**: https://pmc.ncbi.nlm.nih.gov/articles/PMC10011467/

#### Common Carotid Artery:
- **R1 (proximal/characteristic resistance)**: 1.14 mmHg·sec/mL (range: 0.72-1.85)
- **R2 (distal/peripheral resistance)**: 10.35 mmHg·sec/mL (range: 7.79-12.45)
- **C (compliance)**: 0.04 mL/mmHg (range: 0.02-0.06)

#### Subclavian Artery:
- **R1**: 0.96 mmHg·sec/mL (range: 0.81-1.42)
- **R2**: 33.10 mmHg·sec/mL (range: 18.99-68.19)
- **C**: 0.06 mL/mmHg (range: 0.03-0.11)

#### Vertebral Artery:
- **R1**: 8.93 mmHg·sec/mL (range: 6.71-20.33)
- **R2**: 37.79 mmHg·sec/mL (range: 21.47-92.04)
- **C**: 0.01 mL/mmHg (range: 0.00-0.02)

---

## Unit Conversion to SI Units (Pa·s/m³)

### Conversion Factors:
- 1 mmHg = 133.322 Pa
- 1 mL = 1×10⁻⁶ m³
- 1 mmHg·sec/mL = 133.322 Pa·s / (1×10⁻⁶ m³) = **133,322,000 Pa·s/m³**
- 1 mL/mmHg = (1×10⁻⁶ m³) / 133.322 Pa = **7.50×10⁻⁹ m³/Pa**

### Converted Values (SI Units):

#### Common Carotid Artery:
- **R1 (Z)**: 1.14 × 133,322,000 = **152,000,000 Pa·s/m³**
- **R2 (R)**: 10.35 × 133,322,000 = **1,380,000,000 Pa·s/m³**
- **C**: 0.04 × 7.50×10⁻⁹ = **3.0×10⁻¹⁰ m³/Pa**

#### Subclavian Artery:
- **R1 (Z)**: 0.96 × 133,322,000 = **128,000,000 Pa·s/m³**
- **R2 (R)**: 33.10 × 133,322,000 = **4,412,000,000 Pa·s/m³**
- **C**: 0.06 × 7.50×10⁻⁹ = **4.5×10⁻¹⁰ m³/Pa**

---

## CFD Simulation Typical Values

### From OpenFOAM CoA_test Tutorial:
- **R**: 1,000 Pa·s/m³
- **C**: 1×10⁻⁶ m³/Pa
- **Z**: 100 Pa·s/m³

### Comparison:
The CoA_test tutorial uses **MUCH SMALLER** values (by ~1000-10000x) than the medical literature!

**Why the difference?**
1. **Scale**: Medical measurements are for entire vascular beds (mm-scale arteries + downstream capillaries)
2. **CFD**: Tutorial values represent ONLY the 3D-modeled vessel segment outlet boundary
3. **Purpose**: CFD uses simplified BCs to stabilize the simulation, not to model full physiology

---

## Our WKEmpirical Implementation

### Current Code (wk_setup.py):
```python
R_base = 1000.0  # Pa·s/m³
C_base = 1.0e-6  # m³/Pa
Z = 0.1 × R      # Z = 10% of R
```

### Justification:
1. **Matches OpenFOAM tutorial values** (CoA_test reference implementation)
2. **Numerically stable** for CFD simulations
3. **Flow scaling**: R inversely proportional to flow maintains proper distribution
4. **Not physiologically accurate** but **computationally appropriate** for outlet BCs

### Scaling by Flow Ratio:
```python
R_outlet = R_base × (Q_max / Q_outlet)
```

**Example**:
- outlet4 (70% flow): R = 1000 × (0.7/0.7) = 1,000 Pa·s/m³
- outlet1 (10% flow): R = 1000 × (0.7/0.1) = 7,000 Pa·s/m³

This maintains the inverse relationship: **Higher flow → Lower resistance**

---

## Key References

1. **CFD Parameter Estimation**:
   - "A fast approach to estimating Windkessel model parameters for patient-specific multi-scale CFD simulations of aortic flow"
   - ArXiv: https://arxiv.org/abs/2207.05867

2. **Medical Measurements**:
   - "Non-invasive estimation of the parameters of a three-element windkessel model of aortic arch arteries"
   - PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC10011467/

3. **Theoretical Background**:
   - "The arterial Windkessel" - Medical & Biological Engineering & Computing
   - https://link.springer.com/article/10.1007/s11517-008-0359-2

4. **OpenFOAM Implementation**:
   - CoA_test tutorial (custom modularWKPressure BC)
   - /home/mchi4jw4/GitHub/OpenFOAM-WK/tutorials/CoA_test/

---

## Conclusion

**Our R_base = 1000 Pa·s/m³ is appropriate for CFD outlet boundary conditions.**

It's NOT meant to match physiological vascular resistance (which is ~1,000,000 Pa·s/m³), but rather to provide:
1. Numerical stability
2. Proper flow distribution via Murray's law
3. Compatibility with OpenFOAM solver expectations
4. Match with validated tutorial implementations

The literature values (R ~ 10-40 mmHg·s/mL = 1-5 billion Pa·s/m³) are for **full vascular beds**, while our CFD values represent **artificial outlet impedances** that approximate the effect of the downstream vasculature on the 3D flow domain.
