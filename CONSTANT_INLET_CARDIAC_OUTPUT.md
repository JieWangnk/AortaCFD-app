# CONSTANT Inlet with Cardiac Output Specification

## Overview

You can now specify **cardiac output (CO)** directly instead of velocity for `CONSTANT` and `PARABOLIC` inlet types. This is more clinically intuitive for cardiovascular simulations.

## Usage

### Option 1: Cardiac Output (Recommended for Clinical Cases)

```json
{
  "inlet": {
    "type": "CONSTANT",
    "cardiac_output": 5.0,
    "profile": "plug",
    "orientation": "out"
  }
}
```

**Advantages:**
- ✅ Clinically intuitive (directly matches patient measurements)
- ✅ Geometry-independent specification
- ✅ Automatic velocity calculation: `v = CO / (60 × A_inlet)`

### Option 2: Velocity (Traditional)

```json
{
  "inlet": {
    "type": "CONSTANT",
    "velocity": 0.54,
    "profile": "plug",
    "orientation": "out"
  }
}
```

## Typical Cardiac Output Values

| Condition | CO (L/min) | Example Config |
|-----------|------------|----------------|
| **Resting (healthy adult)** | 4.5–5.5 | `"cardiac_output": 5.0` |
| **Light exercise** | 8–12 | `"cardiac_output": 10.0` |
| **Moderate exercise** | 12–20 | `"cardiac_output": 15.0` |
| **Heart failure** | 2.5–4.0 | `"cardiac_output": 3.5` |
| **Athletic training** | 20–30 | `"cardiac_output": 25.0` |

## Conversion

For a given inlet area **A** (automatically detected from STL):

```
velocity (m/s) = cardiac_output (L/min) / [60 × A (m²)]
```

**Example:** For ascending aorta with diameter ~14 mm (A ≈ 154 mm²):
- CO = 5.0 L/min → v ≈ 0.54 m/s
- CO = 10.0 L/min → v ≈ 1.08 m/s

## Implementation Details

### Validation
- **Required:** Either `velocity` OR `cardiac_output` (not both)
- **Priority:** If both specified, `cardiac_output` takes precedence (with warning)
- **Range check:** CO outside 2.0–30.0 L/min triggers warning

### Log Output
When using `cardiac_output`, the log will show:
```
Cardiac output: 5.00 L/min → velocity: 0.5408 m/s (inlet area: 153.74 mm²)
```

### Files Modified
1. **[validation.py](src/aortacfd_lib/utils/validation.py#L921)** — Accepts `cardiac_output` parameter
2. **[boundary_condition_setup.py](src/aortacfd_lib/boundary_condition_setup.py#L175)** — Calculates velocity from CO
3. **[wk_setup.py](src/aortacfd_lib/wk_setup.py#L75)** — Uses CO for Windkessel resistance calculations

## Example Configurations

### Resting Adult (5 L/min)
```json
{
  "boundary_conditions": {
    "inlet": {
      "type": "CONSTANT",
      "cardiac_output": 5.0,
      "profile": "plug",
      "orientation": "out"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80
      }
    }
  }
}
```

**Use case:** Resting hemodynamics, mean pressure distribution, baseline flow split.

### Exercise Stress Test (12 L/min)
```json
{
  "boundary_conditions": {
    "inlet": {
      "type": "CONSTANT",
      "cardiac_output": 12.0,
      "profile": "plug",
      "orientation": "out"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 150,
        "diastolic_pressure": 85
      }
    }
  }
}
```

**Use case:** Exercise stress test, elevated flow conditions.

### Heart Failure (3.5 L/min)
```json
{
  "boundary_conditions": {
    "inlet": {
      "type": "CONSTANT",
      "cardiac_output": 3.5,
      "profile": "plug",
      "orientation": "out"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 110,
        "diastolic_pressure": 75
      }
    }
  }
}
```

**Use case:** Reduced cardiac function, pathological flow conditions.

## Quick Start

1. **Create config file** with `cardiac_output`:
   ```bash
   cp cases_input/patient1/config_3ewk_CO5Lmin.json cases_input/patient1/my_config.json
   ```

2. **Edit** to your desired CO:
   ```json
   "cardiac_output": 5.0  // Change to your target L/min
   ```

3. **Run simulation**:
   ```bash
   python run_patient.py patient1 --config cases_input/patient1/my_config.json
   ```

4. **Check logs** for calculated velocity:
   ```
   Cardiac output: 5.00 L/min → velocity: 0.5408 m/s
   ```

## Related Documentation

- [Inlet BC Clinical Strategy](INLET_BC_CLINICAL_STRATEGY.md#L146) — Full specification
- [Windkessel BC Reference](WINDKESSEL_BC_REFERENCE.md) — Outlet boundary conditions
- [Example Config](cases_input/patient1/config_3ewk_CO5Lmin.json) — Ready-to-use template

---

**Version:** 1.0
**Date:** 2025-10-10
**Feature:** Cardiac output-based inlet specification for CONSTANT/PARABOLIC inlet types
