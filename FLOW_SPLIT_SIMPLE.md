# Flow Split Configuration - Simplified Approach

## Overview

The flow split configuration determines how inlet blood flow is distributed across multiple outlet boundaries. This implementation uses **Murray's law** (r³ relationship) exclusively, with an optional simple percentage specification for the main outlet.

## Murray's Law

Murray's law states that flow in vascular networks distributes proportionally to the cube of vessel radius:

```
f_i = r_i³ / Σ(r_j³)
```

This is physiologically realistic and well-validated for arterial networks.

## Configuration Options

### Option 1: Automatic Murray's Law (Default)

If `flow_split` is not specified or set to `null`, the system automatically distributes flow across **all outlets** using Murray's law:

```json
"windkessel_settings": {
  "systolic_pressure": 120,
  "diastolic_pressure": 80,
  "flow_split": null
}
```

**Example with 4 outlets:**
- Brachiocephalic (r=8mm): 24.2%
- Left Carotid (r=4mm): 3.0%
- Right Carotid (r=4mm): 3.0%
- Descending Aorta (r=12mm): 69.8%

### Option 2: Main Outlet Percentage

Specify a percentage for the **main outlet** (last outlet, typically descending/abdominal aorta). The remaining percentage is distributed among **branch outlets** using Murray's law.

```json
"windkessel_settings": {
  "systolic_pressure": 120,
  "diastolic_pressure": 80,
  "flow_split": 60
}
```

**Interpretation:**
- `flow_split: 60` → Last outlet (main aorta) gets **60%**
- Remaining **40%** is shared among first N-1 outlets (branches) by Murray's law

**Example with 4 outlets:**
- Brachiocephalic (r=8mm): 24.2% of 40% = **9.7%**
- Left Carotid (r=4mm): 3.0% of 40% = **1.2%**
- Right Carotid (r=4mm): 3.0% of 40% = **1.2%**
- Descending Aorta (main): **60.0%**

### Option 3: Manual Ratios (Advanced)

Directly specify the exact flow ratio for each outlet (must sum to 1.0):

```json
"windkessel_settings": {
  "flow_split": {
    "outlet1": 0.10,
    "outlet2": 0.05,
    "outlet3": 0.05,
    "outlet4": 0.80
  }
}
```

This bypasses all automatic calculations. Use only when you have specific clinical measurements.

## Outlet Ordering Convention

**CRITICAL:** The outlet ordering determines which outlet is considered "main":

1. **Outlet naming must follow `outlet_keywords_ordered` in config**
2. **Last outlet = main outlet** (descending/abdominal aorta)
3. **First N-1 outlets = branches** (arch vessels, renal, etc.)

Example geometry configuration:
```json
"geometry": {
  "outlet_keywords_ordered": [
    "outlet1",  // Branch 1
    "outlet2",  // Branch 2
    "outlet3",  // Branch 3
    "outlet4"   // Main outlet (descending aorta)
  ]
}
```

With `flow_split: 60`:
- Outlets 1-3: Share 40% by Murray
- Outlet 4: Gets 60%

## Clinical Guidance

### Typical Main Outlet Percentages

| Anatomy | Main Outlet | Typical % | Branch Share |
|---------|-------------|-----------|--------------|
| Full aorta | Abdominal aorta | 65-75% | 25-35% |
| Arch + thoracic | Desc. thoracic | 60-70% | 30-40% |
| Arch only | Left subclavian | 40-50% | 50-60% |

### When to Use Each Option

1. **Automatic Murray (no flow_split):**
   - Default for most cases
   - Good for exploratory studies
   - Physiologically reasonable first approximation

2. **Main outlet percentage:**
   - When you have clinical measurement or literature value for descending aorta flow
   - Simplifies specification (one number instead of N ratios)
   - Branches still follow physiology (Murray)

3. **Manual ratios:**
   - Patient-specific 4D flow MRI data available
   - Validation against specific clinical measurements
   - Research requiring exact flow split control

## Implementation Details

### Murray's Law Calculation for Branches

When using percentage mode (e.g., `flow_split: 60`):

```python
# Given 4 outlets with radii [8mm, 4mm, 4mm, 12mm]
# flow_split = 60 (main outlet = 60%)

main_outlet_fraction = 0.60
branches_fraction = 0.40

# Calculate Murray ratios for BRANCHES only (first 3)
r³_branch1 = 8³ = 512
r³_branch2 = 4³ = 64
r³_branch3 = 4³ = 64
Σr³_branches = 512 + 64 + 64 = 640

# Distribute branches_fraction (40%) by Murray
branch1 = (512/640) × 0.40 = 0.32 = 32%
branch2 = (64/640) × 0.40 = 0.04 = 4%
branch3 = (64/640) × 0.40 = 0.04 = 4%
main = 0.60 = 60%

# Total = 32% + 4% + 4% + 60% = 100% ✓
```

### Why Only Murray's Law?

**Removed methods:**
- ❌ Area-based split (A_i / ΣA_i)
- ❌ Equal split (1/N for all)

**Rationale:**
1. Murray's law is **physiologically validated** for arterial networks
2. Area-based is redundant (r² vs r³ - Murray is more accurate)
3. Equal split is non-physiological (large and small vessels get same flow)
4. Simplifies config and reduces user confusion

## Validation

The system validates:
- ✅ Flow split percentage between 0-100 (if number)
- ✅ Flow split ratios sum to 1.0 ± 0.01 (if dict)
- ✅ All outlet names in flow_split dict exist in geometry
- ✅ Radii calculated correctly from STL geometry

## Example Configurations

### Aortic Arch Model (3 branches + descending)
```json
{
  "geometry": {
    "outlet_keywords_ordered": ["outlet1", "outlet2", "outlet3", "outlet4"]
  },
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "systolic_pressure": 120,
      "diastolic_pressure": 80,
      "flow_split": 65
    }
  }
}
```
Result: outlet4 gets 65%, others share 35% by Murray.

### Full Aorta (Multiple Branches)
```json
{
  "geometry": {
    "outlet_keywords_ordered": [
      "outlet1",  // Arch vessels
      "outlet2",  // Celiac
      "outlet3",  // SMA
      "outlet4",  // Renal L
      "outlet5",  // Renal R
      "outlet6"   // Infrarenal
    ]
  },
  "outlets": {
    "windkessel_settings": {
      "flow_split": 70
    }
  }
}
```
Result: outlet6 (infrarenal) gets 70%, outlets 1-5 share 30% by Murray.

### Research Case (Manual Control)
```json
{
  "outlets": {
    "windkessel_settings": {
      "flow_split": {
        "outlet1": 0.15,
        "outlet2": 0.05,
        "outlet3": 0.05,
        "outlet4": 0.75
      }
    }
  }
}
```
Result: Exact ratios as specified (must sum to 1.0).

## Related Documentation

- [WINDKESSEL_BC_REFERENCE.md](WINDKESSEL_BC_REFERENCE.md) - Full 3EWK methodology
- [INLET_BC_CLINICAL_STRATEGY.md](INLET_BC_CLINICAL_STRATEGY.md) - Inlet boundary conditions
- Implementation: [src/aortacfd_lib/wk_setup.py](src/aortacfd_lib/wk_setup.py)
