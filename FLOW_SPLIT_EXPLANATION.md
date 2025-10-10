# Flow Split Configuration Explained

## Overview

The `flow_split` parameter controls how inlet flow is distributed among outlets. It works in conjunction with `flow_split_method` to provide flexible, physiologically-motivated flow partitioning.

---

## Configuration Options

### Option 1: Automatic (No `flow_split` specified)

```json
"windkessel_settings": {
  "flow_split_method": "murray"
}
```

**Result:** All outlets share 100% of flow according to the method:
- **Murray's law:** `f_i = r_i³ / Σ(r³)`
- **Area-based:** `f_i = A_i / Σ(A)`
- **Equal:** `f_i = 1/N`

### Option 2: Dictionary (Explicit per-outlet)

```json
"windkessel_settings": {
  "flow_split": {
    "outlet1": 0.15,
    "outlet2": 0.25,
    "outlet3": 0.20,
    "outlet4": 0.40
  }
}
```

**Result:** Exact fractions as specified (must sum to 1.0).

### Option 3: Percentage (Grouped distribution)

```json
"windkessel_settings": {
  "flow_split": 40,
  "flow_split_method": "murray"
}
```

**Result:**
- **First N-1 outlets** share 40% using Murray's law
- **Last outlet** gets remaining 60%

---

## How Percentage Split Works (NEW BEHAVIOR)

### Previous Behavior ❌ (Incorrect)

```
flow_split = 40 → outlets 1-3 each get 40%/3 = 13.33% (EQUAL)
                  outlet4 gets 60%
```

**Problem:** Ignores `flow_split_method` and geometry!

### New Behavior ✅ (Correct)

```
flow_split = 40, flow_split_method = "murray"

Step 1: Calculate Murray's law within first group (outlets 1-3)
  r1³ = 27, r2³ = 64, r3³ = 8  (example)
  Σr³ = 99

  Within group fractions:
  outlet1: 27/99 = 0.273
  outlet2: 64/99 = 0.646
  outlet3: 8/99  = 0.081

Step 2: Scale to 40% total allocation
  outlet1: 0.273 × 0.40 = 0.109 (10.9%)
  outlet2: 0.646 × 0.40 = 0.258 (25.8%)
  outlet3: 0.081 × 0.40 = 0.032 (3.2%)
  outlet4: 0.60 (60%)
```

**Respects both the percentage split AND the physiological distribution method!**

---

## Detailed Examples

### Example 1: Murray's Law with 40% Split

**Config:**
```json
{
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "systolic_pressure": 120,
      "diastolic_pressure": 80,
      "flow_split": 40,
      "flow_split_method": "murray"
    }
  }
}
```

**Assuming outlet radii:**
- outlet1: 3 mm → r³ = 27
- outlet2: 4 mm → r³ = 64
- outlet3: 2 mm → r³ = 8
- outlet4: 5 mm (gets remainder)

**Calculation:**
```
First group (outlets 1-3):
  Total r³ = 27 + 64 + 8 = 99

  outlet1: (27/99) × 0.40 = 0.109 → 10.9%
  outlet2: (64/99) × 0.40 = 0.258 → 25.8%
  outlet3: (8/99) × 0.40 = 0.032 → 3.2%

Last outlet:
  outlet4: 0.60 → 60.0%

Total: 10.9% + 25.8% + 3.2% + 60.0% = 100.0% ✓
```

**Interpretation:** Smaller branch vessels (outlets 1-3) collectively get 40% distributed by vessel size. Main descending aorta (outlet4) gets 60%.

---

### Example 2: Area-Based with 30% Split

**Config:**
```json
{
  "windkessel_settings": {
    "flow_split": 30,
    "flow_split_method": "area"
  }
}
```

**Assuming outlet areas:**
- outlet1: 28 mm²
- outlet2: 50 mm²
- outlet3: 12 mm²
- outlet4: (gets remainder)

**Calculation:**
```
First group (outlets 1-3):
  Total A = 28 + 50 + 12 = 90 mm²

  outlet1: (28/90) × 0.30 = 0.093 → 9.3%
  outlet2: (50/90) × 0.30 = 0.167 → 16.7%
  outlet3: (12/90) × 0.30 = 0.040 → 4.0%

Last outlet:
  outlet4: 0.70 → 70.0%
```

---

### Example 3: Equal Split with 25% Split

**Config:**
```json
{
  "windkessel_settings": {
    "flow_split": 25,
    "flow_split_method": "equal"
  }
}
```

**Calculation:**
```
First group (outlets 1-3):
  Each: 25% / 3 = 8.33%

Last outlet:
  outlet4: 75.0%
```

---

## Clinical Interpretation

### Why Use Percentage Split?

**Scenario:** Coarctation of the aorta (CoA) with multiple arch branches

- **Ascending → arch vessels** (carotid, subclavian): Small branches, collectively ~30-40% of CO
- **Descending aorta**: Main vessel, ~60-70% of CO

**Configuration:**
```json
{
  "flow_split": 35,           // Arch vessels get 35%
  "flow_split_method": "murray"  // Distributed by vessel size
}
```

This models:
1. **Physiological constraint:** Total arch flow ≈ 35% (measured or literature)
2. **Anatomical detail:** Individual branch distribution by Murray's law
3. **Main vessel:** Descending aorta automatically gets remainder

### When to Use Each Method

| Method | When to Use | Example |
|--------|-------------|---------|
| **murray** | Natural branching, physiology-based | Aortic arch branches |
| **area** | Artificial grafts, bypass | Synthetic conduits |
| **equal** | Unknown anatomy, symmetric | Simplified models |

---

## Validation

The system validates:
- ✅ `flow_split_method` is one of: `murray`, `area`, `equal`
- ✅ Percentage `flow_split` is between 0-100
- ✅ Dictionary `flow_split` sums to 1.0 (within tolerance)
- ✅ All outlet names match geometry

---

## Implementation Details

**File:** [src/aortacfd_lib/wk_setup.py](src/aortacfd_lib/wk_setup.py#L325)

**Method:** `_parse_flow_split_percentage()`

**Algorithm:**
```python
1. Split outlets into two groups:
   - First N-1 outlets (e.g., outlets 1-3)
   - Last outlet (e.g., outlet4)

2. Within first group, apply method:
   - murray: f_i = r_i³ / Σ(r³)
   - area: f_i = A_i / Σ(A)
   - equal: f_i = 1/(N-1)

3. Scale first group to percentage:
   final_f_i = group_f_i × (percentage/100)

4. Last outlet gets remainder:
   final_f_last = 1 - (percentage/100)
```

---

## Migration from Old Behavior

**Old configs with `flow_split` as percentage:**

```json
"flow_split": 40  // Previously: equal 13.3% for each of first 3
```

**New behavior with same config:**

```json
"flow_split": 40,
"flow_split_method": "murray"  // Now: Murray's law for first 3
```

**Result:** More physiologically accurate, respects vessel geometry.

**To get old equal behavior explicitly:**

```json
"flow_split": 40,
"flow_split_method": "equal"
```

---

## Summary

✅ **Percentage + Method** = Grouped physiological distribution
✅ **Murray's law** respects vessel geometry within groups
✅ **Flexible grouping** (N-1 vs 1) for clinical scenarios
✅ **Backward compatible** with explicit dictionary specification

---

**Version:** 2.0
**Date:** 2025-10-10
**Feature:** Percentage split now respects `flow_split_method`
