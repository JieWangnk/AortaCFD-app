# Inlet BC — Clinical Strategy & Specification (AortaCFD)

**Purpose:** Single-source-of-truth for inlet boundary condition configuration in cardiovascular CFD simulations, with emphasis on physiological fidelity, numerical robustness, and reproducibility.

---

## 0) Design Philosophy

**Optimized for:**

* **Physiology first** — Match measured inflow waveform (phase and mean cardiac output)
* **Numerical robustness** — Avoid spurious secondary flows and backflow instabilities at ascending aorta
* **Reproducibility** — One JSON schema, explicit units, automatic checks, templated audit logs
* **LES-ready** — Compatible with Large Eddy Simulation for coarctation of the aorta (CoA) studies

---

## 1) Allowed Inlet Types (Canonical Names)

Use **exactly** these four types (strictly validated):

| Type | Description | Use Case |
|------|-------------|----------|
| `TIMEVARYING` | Time series from CSV with chosen spatial profile | **Default for patient cases** |
| `CONSTANT` | Steady uniform velocity | Simple testing, steady-state benchmarks |
| `PARABOLIC` | Steady analytic Poiseuille profile | Laminar straight-tube validation |
| `WOMERSLEY` | Pulsatile analytic Womersley (Fourier + ν) | Research on radial phase dynamics |

> **Note:** Previously "PLUG" was incorrectly used as a type. It is a **profile**, not a type.
> The `type` field specifies **temporal behavior** (time-varying vs constant).
> The `profile` field specifies **spatial distribution** (plug vs parabolic vs womersley).

---

## 2) Decision Tree

### Step 1: Do you have an inlet time series?

**YES — from Doppler/4D-flow MRI/PC-MRI:**

→ Use `type: "TIMEVARYING"`

* **Data are volumetric flow rate Q(t):** set `data_type: "flowRate"`
* **Data are mean or centreline velocity u(t):** set `data_type: "velocity"`
* **Profile choice:**
  * **Aorta** (α ≳ 10 at rest; often plug-like): `profile: "plug"` ✓ **Robust default**
  * **Want radial dynamics:** `profile: "womersley"` (requires `physics.nu`)
  * **Low Re, long straight tube:** `profile: "parabolic"`

**NO — synthetic/testing:**

* **Steady test:** `type: "CONSTANT"` with `profile: "plug"`
* **Laminar benchmark:** `type: "PARABOLIC"`
* **Analytic pulsatile:** `type: "WOMERSLEY"` with synthetic CSV

### Step 2: Womersley Number Check

The Womersley number (α) determines profile suitability:

```
α = R √(ω/ν)
where ω = 2π/T (angular frequency)
```

| α Range | Flow Regime | Recommended Profile |
|---------|-------------|---------------------|
| α < 1 | Quasi-steady | `parabolic` acceptable |
| 1 ≤ α ≤ 10 | Transitional | `womersley` captures phase lag |
| α > 10 | High-frequency (proximal aorta) | `plug` (near-flat) |

**Auto-computed when `physics.nu` and CSV period are provided.**

---

## 3) JSON Schema

### Minimal Required Fields

```json
{
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "patient_inlet_Q.csv",
      "data_type": "flowRate",
      "profile": "plug",
      "orientation": "auto"
    }
  },
  "physics": {
    "nu": 3.5e-6,
    "rho": 1060
  }
}
```

### Complete Schema with All Options

```json
{
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "aortic_inlet.csv",
      "data_type": "flowRate",
      "profile": "plug",
      "orientation": "auto",

      "period": 0.86,

      "filter": {
        "method": "cubic",
        "target_dt": 0.005,
        "fourier_harmonics": 12
      },

      "scaling": {
        "target_CO": 4.8,
        "enforce_zero_diastolic": false
      }
    }
  },
  "physics": {
    "nu": 3.5e-6,
    "rho": 1060
  }
}
```

### Optional Parameters Explained

**`period` (float, seconds):**
- Cardiac cycle period for periodicity checks and resampling
- Helps enforce first==last continuity for `timeVaryingMappedFixedValue`
- Example: `0.86` for 70 bpm heart rate

**`filter` (object):**
- `method`: `"cubic"` | `"linear"` | `"fourier"`
- `target_dt`: Write-out stride for boundaryData (e.g., 0.005 = 5 ms)
- `fourier_harmonics`: Number of harmonics if using Fourier reconstruction

**`scaling` (object):**
- `target_CO`: Target cardiac output in L/min (overrides raw mean)
- `enforce_zero_diastolic`: Clip negative diastolic values (not recommended for aorta)

**`cardiac_output` (float, L/min):** *(CONSTANT/PARABOLIC only)*
- **Alternative to `velocity`**: Specify desired cardiac output directly
- More clinically intuitive than velocity
- Automatically calculates velocity from: `v = CO / (60 × A_inlet)`
- Typical values:
  - Resting adult: 4.5–5.5 L/min
  - Light exercise: 8–12 L/min
  - Moderate exercise: 12–20 L/min
- **Example:**
  ```json
  "inlet": {
    "type": "CONSTANT",
    "cardiac_output": 5.0,  // L/min (resting)
    "profile": "plug",
    "orientation": "out"
  }
  ```

**Priority:** If both `velocity` and `cardiac_output` are specified, `cardiac_output` takes precedence (with warning).

---

## 4) CSV Contract (Hard Rules)

### Units

| Column | Unit | Description |
|--------|------|-------------|
| `time` | seconds [s] | Monotonically increasing |
| `velocity` | m/s | If `data_type: "velocity"` |
| `flowRate` | m³/s | If `data_type: "flowRate"` |

### Format

**With header (case-insensitive):**
```csv
time,velocity
0.0,0.5
0.01,0.8
0.02,1.2
```

**Without header:**
```csv
0.0,0.5
0.01,0.8
0.02,1.2
```

### Requirements

✓ **Monotonic time** (no duplicates; app will sort and de-duplicate with warning)
✓ **At least one full cycle**
✓ **Two cycles recommended** for robust Fourier smoothing
✓ **Explicit units** in column headers or documentation

---

## 5) Geometry & Area (Non-Circular Robustness)

**Do NOT assume circular inlet.**

* Compute **polygonal area** from inlet mesh patch points:
  `constant/boundaryData/<inlet>/points`
* For `data_type: "flowRate"`:
  ```
  v_avg(t) = Q(t) / A_mesh
  ```
* For `PARABOLIC` type:
  * Use **equivalent radius**: `R_eq = √(A/π)`
  * Interpret `velocity` as **centerline** velocity:
    ```
    v(r) = v_max (1 - (r/R_eq)²)
    v_max = 2 × v_avg
    ```

**Validation:** QC module logs both `A_mesh` and `R_eq` for audit trail.

---

## 6) Orientation (Bulletproof Auto-Detection)

Default: `"orientation": "auto"`

### Algorithm

1. **Area-weighted normal** (`n_hat`) of inlet patch
2. **Flow direction** (`d_vec`):
   ```
   d_vec = centroid(outlets) - centroid(inlet)
   ```
3. **Alignment check:**
   ```
   if dot(n_hat, d_vec) < 0:
       flip_sign = True
   ```
4. **Logging:** dot product, chosen sign, bulk direction

### Manual Override

Set `"orientation": "in"` or `"out"` to override.

**Warning:** App logs disagreement when manual setting contradicts auto-detection.

---

## 7) OpenFOAM Mapping (Unambiguous)

| JSON `type` | JSON `profile` | `0/U` BC | boundaryData |
|-------------|----------------|----------|--------------|
| `TIMEVARYING` | `plug`/`parabolic`/`womersley` | `timeVaryingMappedFixedValue` | `U` files per time |
| `CONSTANT` | `plug` | `fixedValue uniform (vx vy vz)` | None |
| `PARABOLIC` | `parabolic` | `fixedValue nonuniform` | Optional (t=0) |
| `WOMERSLEY` | `womersley` | `timeVaryingMappedFixedValue` | Analytic synthesis |

### Pressure and Turbulence

**`0/p` at inlet:**
```cpp
inlet
{
    type    zeroGradient;
}
```

**LES turbulence (if applicable):**
```cpp
inlet
{
    // k: low turbulence intensity (1-5% of bulk)
    type    fixedValue;
    value   uniform 0.001;
}
```

---

## 8) Time Handling & Write-Out

* **Internal timestep:** Solver-driven (adaptive or fixed)
* **boundaryData stride:** Controlled by `filter.target_dt` (5-10 ms recommended)
* **Resampling:** If CSV's native Δt is coarse, use cubic/Fourier interpolation
* **Periodicity:** When `period` is given, enforce first==last continuity

---

## 9) Backflow & Stability (Aorta-Specific)

* **Allow physiological backflow:** Don't clip negative velocities in diastole
* **Optional limiter:** `min_velocity = -0.3 × v_max_systolic` (configurable)
* **Inlet extension:** Add 2-3 diameter straight cylinder upstream to de-sensitize to profile mismatches

---

## 10) Golden Defaults (Drop-In)

If user provides only CSV + patient name:

```json
{
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "<patient>_inlet.csv",
    "data_type": "flowRate",
    "profile": "plug",
    "orientation": "auto",
    "filter": {
      "method": "cubic",
      "target_dt": 0.005
    }
  },
  "physics": {
    "nu": 3.5e-6,
    "rho": 1060
  }
}
```

**Rationale:** Typical α in proximal aorta, stable for LES, minimal assumptions.

---

## 11) Automated QC Checks (Audit Trail)

Every case generates an `inlet_audit.json` and `inlet_qc_report.txt`:

### Logged Metrics

✓ **Geometry:** `A_mesh`, `R_eq`, centroid, normal
✓ **Waveform:** Cycle period, mean flow/velocity, peak systolic, backflow fraction
✓ **Womersley:** α, recommended profile vs actual
✓ **Scaling:** Original vs target CO, scale factor
✓ **Orientation:** Dot product, flip decision
✓ **Filtering:** Method, Δt, number of output timesteps
✓ **Warnings & errors:** Validation flags

### Example Audit Output

```
================================================================================
INLET BOUNDARY CONDITION AUDIT REPORT
================================================================================

GEOMETRY:
  Inlet area: 314.16 mm²
  Equivalent radius: 10.00 mm
  Center: [0.000, 0.000, 0.100]
  Normal: [0.000, 0.000, 1.000]

CONFIGURATION:
  Type: TIMEVARYING
  Profile: plug
  CSV file: patient12_inlet_Q.csv
  Data type: flowRate

WAVEFORM STATISTICS:
  Number of points: 86
  Detected period: 0.857 s (70.0 bpm)
  Mean flow: 83.33 mL/s (5.00 L/min)
  Peak systolic: 250.00 mL/s
  Backflow fraction: 12.8%

WOMERSLEY ANALYSIS:
  Kinematic viscosity (ν): 3.50e-06 m²/s
  Womersley number (α): 12.35
  Recommended profile: plug (high-frequency, near-flat)

ORIENTATION:
  Method: automatic detection
  Dot product (n·d): 0.987
  Normal flipped: No

SCALING:
  Target CO: 5.20 L/min
  Original mean flow: 5.00 L/min
  Scale factor: 1.0400

================================================================================
```

---

## 12) Corrected Examples

### Example A: Patient-Specific (Robust Default)

```json
{
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "patient12_inlet_Q.csv",
    "data_type": "flowRate",
    "profile": "plug",
    "orientation": "auto",
    "period": 0.95,
    "filter": {
      "method": "cubic",
      "target_dt": 0.01
    },
    "scaling": {
      "target_CO": 5.2
    }
  },
  "physics": {
    "nu": 3.5e-6,
    "rho": 1060
  }
}
```

### Example B: Analytic Womersley

```json
{
  "inlet": {
    "type": "WOMERSLEY",
    "csv_file": "u_mean_cycle.csv",
    "data_type": "velocity",
    "profile": "womersley",
    "orientation": "auto",
    "period": 0.86,
    "filter": {
      "method": "fourier",
      "fourier_harmonics": 10,
      "target_dt": 0.005
    }
  },
  "physics": {
    "nu": 3.5e-6
  }
}
```

### Example C: Steady with Cardiac Output (Resting Physiology)

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

**Note:** Specifying `cardiac_output` (L/min) is more clinically intuitive than `velocity`. The velocity is automatically calculated from CO and inlet area.

### Example C2: Steady Uniform Test (Velocity Specified)

```json
{
  "inlet": {
    "type": "CONSTANT",
    "velocity": 0.50,
    "profile": "plug",
    "orientation": "out"
  }
}
```

### Example D: Steady Parabolic Benchmark

```json
{
  "inlet": {
    "type": "PARABOLIC",
    "velocity": 1.2,
    "profile": "parabolic",
    "orientation": "auto"
  }
}
```

---

## 13) Type-Profile Compatibility Matrix

### Inlet Type Compatibility

| Type | Allowed Profiles | Required Params | Optional Params |
|------|------------------|-----------------|-----------------|
| `TIMEVARYING` | `plug`, `parabolic`, `womersley` | `csv_file`, `data_type`, `profile` | `period`, `filter`, `scaling` |
| `CONSTANT` | `plug`, `parabolic` | `velocity` OR `cardiac_output`, `profile` | `orientation` |
| `PARABOLIC` | `parabolic` | `velocity` OR `cardiac_output`, `profile` | `orientation` |
| `WOMERSLEY` | `womersley` | `csv_file`, `data_type`, `profile`, `physics.nu` | `period`, `filter` |

**Strict validation:** Incompatible type-profile combinations will **fail** at config validation stage.

### Inlet-Outlet Compatibility

| Inlet Type | Outlet Type | Status | Physical Behavior |
|------------|-------------|--------|-------------------|
| `TIMEVARYING` | `3EWINDKESSEL` | ✅ **Recommended** | Full RCR dynamics: pulsatile compliance, realistic diastolic decay |
| `TIMEVARYING` | `ZEROGRADIENT` | ✅ OK | Simpler, but may have stability issues |
| `CONSTANT` | Simple Resistance | ✅ **Recommended** | Mean hemodynamics: R_i = (MAP - P_v) / Q̄_i (what RCR reduces to at DC) |
| `CONSTANT` | `FIXEDVALUE` (pressure) | ✅ OK | Clean steady-state solution; geometry determines flow split |
| `CONSTANT` | `3EWINDKESSEL` | ⚠️ **Warning** | Valid but collapses to R1+R2 at steady state; C inactive, use simple R instead |
| `CONSTANT` | `ZEROGRADIENT` | ⚠️ **Warning** | May cause stability issues; consider pressure outlets |

**Key insight for steady-state:** CONSTANT inlet + 3-WK is allowed but the capacitor is open-circuit at DC, reducing to pure resistance R_total = R1 + R2. **Preferred approach:** Use simple resistance outlets R_i = (MAP - P_v) / Q̄_i, which is exactly what RCR reduces to at steady state.

---

## 14) Implementation Notes (High Impact, Low Effort)

### Validation Layer

* Disallow `profile="plug"` with `type="PARABOLIC"` (mutual exclusivity)
* Enforce `physics.nu` when `profile="womersley"` or `type="WOMERSLEY"`
* Warn if `period` differs >2% from detected dominant period

### Area Computation

* Compute from *written* `points` file (triangulate polygon)
* Cache in case metadata for reproducibility

### Fourier Resampler

* Estimate dominant heart rate from FFT
* Rebuild waveform with N harmonics
* Ensure end-point continuity (first == last)

### Orientation

* Use **area-weighted** normal
* Auto-flip with logged evidence (dot product)

### Turbulence Initialization

* Optional `inlet_turbulence` block for `TI`, `L_ref`
* Default: `zeroGradient` for LES

---

## 15) User Checklist (Quick Reference)

✓ CSV in `cases_input/<patient>/` with correct units & header
✓ JSON uses **one of four** `type` values
✓ For transient, set `period` if known
✓ `profile` consistent with `type` and physiology (plug default for aorta)
✓ `physics.nu` present for Womersley
✓ Run mesh first (to write inlet `points`) before BC generation
✓ Inspect logs: area, α, scaling, orientation, boundaryData count
✓ Open ParaView: check vectors at inlet (direction and magnitude)

---

## 16) Steady-State with Windkessel Outlets

### Physical Behavior

When using `CONSTANT` inlet with `3EWINDKESSEL` outlets:

**At DC (constant flow), the capacitor C is open-circuit → no flow through C.**

* Total afterload collapses to: **R_total = R1 + R2** (pure resistance)
* **R1 (characteristic impedance)** only matters for transients/waves
* With no pulsatility, it becomes a **single resistance** outlet

### Three Defensible Options

#### Option 1: Simple Resistance Outlets (Mean Hemodynamics)

Use resistance-only outlets:

```
R_i = (MAP - P_v) / Q̄_i
```

Where:
* MAP from cuff SP/DP: `MAP = DP + (SP - DP)/3`
* P_v ≈ 0–5 mmHg (venous pressure)
* Q̄_i is mean flow (split by Murray r³ or area)

**This is exactly what RCR reduces to at steady state.**

Config example:
```json
{
  "inlet": {
    "type": "CONSTANT",
    "velocity": 0.5,
    "profile": "plug"
  },
  "outlets": {
    "type": "FIXEDVALUE",
    "pressure": 13332
  }
}
```

#### Option 2: Fixed Pressure Outlets

Set all outlets near MAP; geometry determines flow split naturally.

**Common when you only care about pressure field and can accept whatever flow split the geometry induces.**

#### Option 3: Synthesize Mild Pulsation (Utilize 3-WK Dynamics)

Keep 3-WK but create synthetic inlet waveform:

```json
{
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "synthetic_sinusoid_70bpm.csv",
    "data_type": "velocity",
    "profile": "plug"
  },
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "systolic_pressure": 120,
      "diastolic_pressure": 80,
      "flow_split_method": "murray"
    }
  }
}
```

Then set Windkessel parameters:
* **R1 ≈ ρc/A** (or 10–20% of R_total)
* **R2 = R_total - R1** where `R_total = (MAP - P_v) / Q̄_i`
* **τ = 1.5–2.0 s** (systemic diastolic decay time)
* **C = τ / R2**

This gives **realistic diastolic decay** and avoids unphysical perfectly steady system.

### Practical Notes for Constant Inlet + 3-WK

⚠️ **Long start-up transient** while C charges
* Ramp the inlet velocity (0 → v_target over 0.5–1.0 s)
* Initialize pressure field near MAP to speed convergence

⚠️ **If using truly steady RANS solver:**
* Pure resistance or fixed pressure outlets are cleaner
* No benefit to 3-WK without time-dependent terms

---

## 17) Why This Works for LES CoA Pipeline

* **LES-friendly:** Plug inflow with short straight extension prevents artificial swirl
* **Physiology-faithful:** Time-series preserves systolic peak, diastolic tail, reverse flow
* **Auditable:** Every assumption (area, α, scaling, period) is printed and version-controlled

---

## Related Documentation

* **Validation rules:** [src/aortacfd_lib/utils/validation.py:749](src/aortacfd_lib/utils/validation.py#L749)
* **QC module:** [src/aortacfd_lib/inlet_qc.py](src/aortacfd_lib/inlet_qc.py)
* **Implementation:** [src/aortacfd_lib/inlet_mapping.py](src/aortacfd_lib/inlet_mapping.py)
* **Outlet BCs:** [WINDKESSEL_BC_REFERENCE.md](WINDKESSEL_BC_REFERENCE.md)

---

**Version:** 1.0
**Last Updated:** 2025-10-10
**Status:** Production-ready for LES cardiovascular CFD
