# Testing 3-Element Windkessel with 40% Flow Split

## Test Configuration Created

**Location:** `cases_input/patient1/config_3ewk_40percent.json`

**Key Settings:**
- **Cuff Pressures:**
  - Systolic: 120 mmHg
  - Diastolic: 80 mmHg
  - Venous: 0 mmHg
  - → **MAP = 93.3 mmHg**

- **Flow Distribution:**
  - `flow_split: 40` → 40% split among first 3 outlets (outlets 1-3), 60% to last outlet (outlet4)
  - Method: `flow_split_method: "murray"` (used only if flow_split not specified)
  - Actual distribution:
    - outlet1: 13.3% (40% / 3)
    - outlet2: 13.3% (40% / 3)
    - outlet3: 13.3% (40% / 3)
    - outlet4: 60.0% (remainder)

- **Windkessel Parameters:**
  - PWV method: Empirical (vessel-size based)
  - Tau (diastolic decay): 1.8 seconds
  - Compliance distribution: Proportional to flow split

- **Inlet BC:**
  - Type: PLUG (constant velocity)
  - Velocity: 1.0 m/s

---

## How to Run the Test

### Option 1: Complete Workflow (All Steps)

```bash
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json
```

This will execute:
1. Case setup
2. Mesh generation
3. Boundary conditions (including WK calculation)
4. Solver run
5. Post-processing

### Option 2: Step-by-Step Execution

**Step 1: Create case structure**
```bash
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json --step case
```

**Step 2: Generate mesh**
```bash
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json --step mesh
```

**Step 3: Setup boundary conditions (WK calculation happens here)**
```bash
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json --step boundary
```

**Step 4: Run solver**
```bash
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json --step solver
```

**Step 5: Post-processing**
```bash
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json --step post
```

### Option 3: Test Only Boundary Conditions (Quick Test)

To quickly test the Windkessel coefficient calculation without running full simulation:

```bash
# Run only case setup and boundary conditions
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json --step case --step boundary
```

---

## Expected Output

### During Boundary Condition Setup

You should see detailed logging like this:

```
================================================================================
Calculating 3-Element Windkessel Coefficients (Clinical Method)
================================================================================
Step 1: Pressure targets
  Systolic pressure (SP): 120 mmHg
  Diastolic pressure (DP): 80 mmHg
  Mean arterial pressure (MAP): 93.3 mmHg (12439 Pa)
  Venous pressure (P_v): 0 mmHg
  Driving pressure (MAP - P_v): 93.3 mmHg

Step 2: Flow distribution (User-specified)
  outlet1: 13.3% → mean Q = XX.XX mL/s
  outlet2: 13.3% → mean Q = XX.XX mL/s
  outlet3: 13.3% → mean Q = XX.XX mL/s
  outlet4: 60.0% → mean Q = XX.XX mL/s

Step 3: Total resistance R_total = (MAP - P_v) / Q_mean
  outlet1: R_total = X.XXe+08 Pa·s/m³ (XXX.X mmHg·s/mL)
  outlet2: R_total = X.XXe+08 Pa·s/m³ (XXX.X mmHg·s/mL)
  outlet3: R_total = X.XXe+08 Pa·s/m³ (XXX.X mmHg·s/mL)
  outlet4: R_total = X.XXe+08 Pa·s/m³ (XXX.X mmHg·s/mL)

Step 4: Proximal resistance R1 = ρ·c/A (characteristic impedance)
  outlet1: PWV = X.X m/s (empirical) → R1 = X.XXe+07 Pa·s/m³
  outlet2: PWV = X.X m/s (empirical) → R1 = X.XXe+07 Pa·s/m³
  outlet3: PWV = X.X m/s (empirical) → R1 = X.XXe+07 Pa·s/m³
  outlet4: PWV = X.X m/s (empirical) → R1 = X.XXe+07 Pa·s/m³

Step 5: Distal resistance R2 = R_total - R1
  outlet1: R2 = X.XXe+08 Pa·s/m³
  outlet2: R2 = X.XXe+08 Pa·s/m³
  outlet3: R2 = X.XXe+08 Pa·s/m³
  outlet4: R2 = X.XXe+08 Pa·s/m³

Step 6: Compliance C = tau / R2 (from diastolic decay)
  Systemic tau: 1.80 s
  R2 parallel: X.XXe+07 Pa·s/m³
  C_total: X.XXe-09 m³/Pa
  outlet1: C = X.XXe-09 m³/Pa, RC = X.XX s
  outlet2: C = X.XXe-09 m³/Pa, RC = X.XX s
  outlet3: C = X.XXe-09 m³/Pa, RC = X.XX s
  outlet4: C = X.XXe-09 m³/Pa, RC = X.XX s

================================================================================
SUMMARY: Windkessel Parameters (OpenFOAM units: Pa·s/m³, m³/Pa)
================================================================================
outlet1        : R(R2)=X.XXe+08  C=X.XXe-09  Z(R1)=X.XXe+07
outlet2        : R(R2)=X.XXe+08  C=X.XXe-09  Z(R1)=X.XXe+07
outlet3        : R(R2)=X.XXe+08  C=X.XXe-09  Z(R1)=X.XXe+07
outlet4        : R(R2)=X.XXe+08  C=X.XXe-09  Z(R1)=X.XXe+07
================================================================================
```

---

## Configuration Options Explained

### Flow Split: 40%

The parameter `"flow_split": 40` means:
- First 3 outlets (outlet1, outlet2, outlet3) share 40% of total flow equally
- Each gets: 40% / 3 = 13.33%
- Last outlet (outlet4) gets: 100% - 40% = 60%

### Alternative Flow Split Options

**Option A: Murray's Law (automatic)**
```json
{
  "flow_split": null,
  "flow_split_method": "murray"
}
```
Calculates flow split as `f_i = r_i³ / Σr_j³` based on outlet radii.

**Option B: Area-based**
```json
{
  "flow_split": null,
  "flow_split_method": "area"
}
```
Calculates flow split as `f_i = A_i / ΣA_j` based on outlet areas.

**Option C: Explicit ratios**
```json
{
  "flow_split": {
    "outlet1": 0.20,
    "outlet2": 0.15,
    "outlet3": 0.25,
    "outlet4": 0.40
  }
}
```
Directly specify the flow fraction for each outlet (must sum to 1.0).

---

## Validation Checks

After the simulation completes, verify:

1. **Mean outlet pressures ≈ MAP (93.3 mmHg / 12439 Pa)**
   - Check: `postProcessing/` output or ParaView

2. **Mass conservation:**
   - Sum of outlet flows ≈ inlet flow

3. **Pressure waveform:**
   - Pulse pressure reasonable
   - Diastolic decay time constant ≈ 1.8s

---

## Troubleshooting

### If WK calculation fails:

1. **Check outlet areas are extracted:**
   - Ensure STL files exist: `outlet1.stl`, `outlet2.stl`, etc.
   - Check scale_factor is correct (0.001 = mm to m)

2. **Check inlet flow data:**
   - For PLUG inlet: velocity × inlet_area = flow rate
   - Default: 1.0 m/s × inlet_area

3. **Check configuration syntax:**
   - Ensure all JSON is valid
   - Check that `outlet_keywords_ordered` matches STL filenames

### If simulation diverges:

1. **Reduce time step:**
   ```json
   "initial_deltaT": 1e-5,
   "maxDeltaT": 1e-4
   ```

2. **Reduce maxCo:**
   ```json
   "maxCo": 0.2
   ```

3. **Check mesh quality:**
   - Run: `checkMesh` in the case directory
   - Look for high aspect ratio or non-orthogonality

---

## Where to Find Results

After successful run:
- **Case directory:** `output/patient1_3ewk_40pct/`
- **Mesh:** `output/patient1_3ewk_40pct/constant/polyMesh/`
- **Boundary conditions:** `output/patient1_3ewk_40pct/0/` (p, U files)
- **Results:** `output/patient1_3ewk_40pct/0.01/`, `0.02/`, etc.
- **Post-processing:** `output/patient1_3ewk_40pct/postProcessing/`
- **Logs:** Check terminal output or log files

---

## Quick Start Command

```bash
# Test only Windkessel calculation (no simulation)
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json --step case --step boundary

# Full simulation (will take time)
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json
```
