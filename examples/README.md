# AortaCFD Configuration Examples

This directory contains example configuration files demonstrating various use cases and parameter combinations for AortaCFD simulations.

## Quick Start

Copy an example config to your patient directory and modify as needed:

```bash
# Copy minimal config for quick start
cp examples/config_minimal.json cases_input/my_patient/config.json

# Or copy full example to see all options
cp examples/config_full_example.json cases_input/my_patient/config.json
```

### ⚠️ Important: Profile Override Behavior

**Question: When using `--profile`, are my config.json settings replaced with defaults?**

**Answer: NO!** Your config.json settings are NEVER replaced. They always have the highest priority.

The `--profile` flag ONLY changes profile-specific settings (solver type, mesh resolution, numerical schemes). All your case-specific settings in config.json are preserved:
- ✅ Physics properties (blood_density, blood_viscosity)
- ✅ Boundary conditions (inlet type, outlet settings, pressures)
- ✅ Computational settings (max_processors, nProcessors)
- ✅ Simulation control (number_of_cycles, writeInterval)
- ✅ ALL other settings in your config.json

**Configuration Merge Priority:**
```
1. Base defaults        (lowest)
2. Profile settings
3. Fragment composition
4. Your config.json     (HIGHEST - always wins!)
```

**Example:**
```bash
# Your config.json has:
# - blood_density: 1050
# - max_processors: 16
# - systolic_pressure: 130
# - number_of_cycles: 8

python run_patient.py patient1 --profile sim_rans_fine

# Result: Uses RANS fine profile (changes solver/mesh/numerics)
#         BUT keeps ALL your settings from config.json!
#         - blood_density: 1050 ✓ (preserved)
#         - max_processors: 16 ✓ (preserved)
#         - systolic_pressure: 130 ✓ (preserved)
#         - number_of_cycles: 8 ✓ (preserved)
```

**See [profile_override_example.md](profile_override_example.md) for detailed explanation with concrete examples.**

---

## Available Examples

### 1. **config_minimal.json** - Minimal Configuration ⭐ START HERE
**Best for:** First-time users, quick testing

**Contains:**
- Only required parameters
- Default settings for everything else
- Perfect starting point for most cases

**Profile:** `sim_laminar_medium` (clinical standard, 30-60 min runtime)

**Use this when:**
- You want the simplest possible configuration
- You're testing the workflow for the first time
- Your case has standard healthy aorta geometry

```bash
# Run with minimal config
python run_patient.py patient1 --config examples/config_minimal.json
```

---

### 2. **config_laminar_medium_example.json** - Laminar Medium Resolution
**Example of:** Laminar simulation with medium mesh resolution

**Contains:**
- Laminar solver assumption (Re < 2300)
- 3EWK outlets with Murray's law
- 5 cardiac cycles
- Parallel execution (4 cores)
- Standard blood properties

**Profile:** `sim_laminar_medium` (30-60 min runtime)

**Suitable for:**
- Cases where laminar flow assumption is valid (low Re)
- Balanced accuracy vs computational cost
- Testing 3-element Windkessel setup

**Blood properties shown:**
- Density: 1060 kg/m³
- Viscosity: 0.004 Pa·s

```bash
# Run with this example
python run_patient.py patient1 --config examples/config_laminar_medium_example.json
```

---

### 3. **config_rans_turbulence.json** - RANS Turbulence Example
**Example of:** RANS k-ω SST turbulence model with medium resolution

**Contains:**
- RANS k-ω SST turbulence model
- Higher resolution (priority 18)
- 8-core parallel execution
- Example settings for transitional/turbulent flows (Re > 2300)

**Profile:** `sim_rans_medium` (2-3 hour runtime)

**May be appropriate for:**
- Flows where turbulence modeling is needed (Re > 2300)
- Cases with potential flow separation or recirculation
- Transitional flow regions

**Example settings shown:**
- Heart rate: 120 bpm
- Viscosity: 0.0037 Pa·s
- Systolic pressure: 123 mmHg
- Flow split: 70%

```bash
# Run with this example
python run_patient.py example_case --config examples/config_rans_turbulence.json
```

---

### 4. **config_les_fine_example.json** - LES Fine Resolution Example
**Example of:** LES WALE subgrid model with fine resolution

**Contains:**
- LES with WALE subgrid model
- Fine mesh (priority 25)
- 16-core parallel execution
- 10 cardiac cycles
- Womersley inlet profile
- Skip reconstruction option

**Profile:** `sim_les_fine` (5-7 hour runtime)

**Computational requirements:**
- **Memory:** 32+ GB RAM
- **CPU:** 16+ cores
- **Storage:** 50-100 GB per case
- **Time:** 5-10 hours per simulation

**May be appropriate for:**
- Cases requiring high temporal resolution
- Unsteady flow phenomena
- When turbulence-resolving approach is needed

**Example settings shown:**
- Max CFL: 0.5 (tighter stability requirement)
- Write interval: 0.005s (high frequency output)
- Fine boundary layers (5 layers, 1.1 expansion)

```bash
# Run with this example
python run_patient.py example_case --config examples/config_les_fine_example.json
```

---

### 5. **config_yplus_example.json** - Y+ Based Boundary Layer Control 🆕
**Example of:** Automatic first layer thickness calculation for target y+ value

**Contains:**
- Automatic y+ based boundary layer sizing
- RANS k-ω SST with y+ = 1.0 target
- Auto-estimation from geometry
- Complete workflow documentation

**Profile:** `sim_rans_medium` (2-3 hour runtime)

**Features:**
- **Automatic calculation:** Set `target_yplus`, system calculates `finalLayerThickness`
- **No manual estimation:** Uses pipe flow correlations to predict wall shear stress
- **Validation:** Logs show Re, u_τ, layer thickness, warnings
- **Post-verification:** Built-in y+ post-processing validates results

**How it works:**
1. Set `mesh.boundary_layers.target_yplus = 1.0` in config
2. System estimates flow from geometry + cardiac output (or uses your overrides)
3. Calculates: Δy₁ = y⁺ × ν / u_τ using pipe flow correlations
4. Generates mesh with calculated layer thickness
5. Post-processing verifies actual y+ matches target

**Typical targets:**
- **RANS k-ω SST:** y+ ≈ 1.0 (low-Re wall treatment)
- **LES WALE:** y+ ≈ 1.0 (wall-resolved)
- **Wall functions:** y+ ≈ 30-100 (high-Re wall treatment)

**CLI standalone calculator:**
```bash
# Calculate layer thickness manually
python -m src.aortacfd_lib.yplus_estimator \
  --target-yplus 1.0 \
  --velocity 0.5 \
  --diameter 0.025 \
  --solver-type RANS
```

```bash
# Run with y+ auto-calculation
python run_patient.py patient1 --config examples/config_yplus_example.json
```

---

### 6. **config_full_example.json** - Complete Reference
**Best for:** Understanding all available parameters

**Contains:**
- Every possible configuration parameter
- Inline comments explaining each option
- Multiple alternatives for each setting
- Value ranges and units
- Profile selection guide
- Y+ calculator documentation

**This is NOT meant to be run directly** - it's a reference document showing all possibilities.

**Use this when:**
- You need to customize advanced parameters
- You want to understand what each setting does
- You're looking for specific configuration options
- You need to see all available choices

---

## Configuration Parameter Categories

### Essential Parameters (required in all configs)

```json
{
  "case_info": { "patient_id": "...", "description": "..." },
  "simulation_settings": { "solver_type": "...", "analysis_type": "..." },
  "boundary_conditions": { ... }
}
```

### Optional Parameters (auto-configured by profiles)

- **physics** - Blood properties (uses defaults if omitted)
- **geometry** - Scaling, rotation, patch keywords
- **computational** - Parallel execution settings
- **mesh** - Advanced mesh controls
- **run_settings** - Solver execution options
- **simulation_control** - Time stepping, output frequency

---

## Parameter Selection Guide

### Choosing Solver Type

| Condition | Solver Type | Profile Example |
|-----------|-------------|-----------------|
| Healthy aorta, Re < 2300 | `laminar` | `sim_laminar_medium` |
| Stenosis, CoA, Re > 2300 | `rans` | `sim_rans_medium` |
| Unsteady vortices, research | `les` | `sim_les_fine` |

### Choosing Analysis Level

| Purpose | Analysis Type | Runtime | Use Case |
|---------|---------------|---------|----------|
| Quick check | `coarse` | 5-10 min | Geometry validation |
| Clinical | `medium` | 30-60 min | **Standard analysis** |
| Research | `fine` | 2-4 hours | Publications |

### Combining Solver + Analysis

The configuration maps to profiles:
- `solver_type=laminar` + `analysis_type=medium` → `sim_laminar_medium`
- `solver_type=rans` + `analysis_type=fine` → `sim_rans_fine`
- `solver_type=les` + `analysis_type=fine` → `sim_les_fine`

Or override directly:
```bash
python run_patient.py patient1 --profile sim_rans_medium
```

---

## Common Configuration Patterns

### Pattern 1: Quick Validation Run
```json
{
  "simulation_settings": { "solver_type": "laminar", "analysis_type": "coarse" },
  "simulation_control": { "number_of_cycles": 1 }
}
```
**Runtime:** ~5 minutes

---

### Pattern 2: Clinical Standard
```json
{
  "simulation_settings": { "solver_type": "laminar", "analysis_type": "medium" },
  "computational": { "parallel": true, "max_processors": 4 },
  "simulation_control": { "number_of_cycles": 5 }
}
```
**Runtime:** ~30-60 minutes

---

### Pattern 3: High-Performance Turbulence
```json
{
  "simulation_settings": { "solver_type": "rans", "analysis_type": "medium" },
  "computational": { "parallel": true, "max_processors": 8 },
  "mesh": { "SNAPPY_SETTINGS": { "nProcessors": 8 } },
  "run_settings": { "subdomains": 8 }
}
```
**Runtime:** ~2-3 hours

---

### Pattern 4: Publication Quality
```json
{
  "simulation_settings": { "solver_type": "laminar", "analysis_type": "fine" },
  "computational": { "parallel": true, "max_processors": 8 },
  "simulation_control": {
    "number_of_cycles": 10,
    "writeInterval": 0.005
  }
}
```
**Runtime:** ~4-6 hours

---

## Boundary Condition Examples

### Time-Varying Inlet (most common)
```json
"inlet": {
  "type": "TIMEVARYING",
  "csv_file": "BPM75.csv",
  "data_type": "flowRate",
  "profile": "plug"
}
```

### Constant Flow Rate
```json
"inlet": {
  "type": "CONSTANT",
  "cardiac_output": 5.0
}
```

### Windkessel Outlets with Flow Split
```json
"outlets": {
  "type": "3EWINDKESSEL",
  "windkessel_settings": {
    "systolic_pressure": 120,    // mmHg
    "diastolic_pressure": 80,     // mmHg
    "flow_split": 40,             // % (first N-1 outlets share 40%, last gets 60%)
    "flow_split_method": "murray" // Murray's law based on outlet areas
  }
}
```

**Automatic WK Coefficient Calculation:**

The system automatically calculates the 3 Windkessel parameters (R1, R2, C) from your pressure inputs:

| Parameter | Calculated From | Typical Range | Physical Meaning |
|-----------|----------------|---------------|------------------|
| **R1** (Proximal) | PWV × ρ / Area | 1×10⁵ - 5×10⁵ Pa·s/m³ | Characteristic impedance |
| **R2** (Distal) | (MAP - P_v)/Q - R1 | 1×10⁶ - 5×10⁶ Pa·s/m³ | Peripheral resistance |
| **C** (Compliance) | τ / R2 | 5×10⁻⁷ - 2×10⁻⁶ m³/Pa | Arterial compliance |

**Example output for SP=123, DP=60, flow_split=70%:**

| Outlet | Area (mm²) | Flow % | R1 (Pa·s/m³) | R2 (Pa·s/m³) | C (m³/Pa) |
|--------|-----------|--------|--------------|--------------|-----------|
| outlet1 | 145 | 24.5% | 2.37e5 | 2.13e6 | 7.04e-7 |
| outlet2 | 118 | 17.5% | 2.96e5 | 2.07e6 | 7.24e-7 |
| outlet3 | 96 | 13.3% | 3.64e5 | 2.00e6 | 7.48e-7 |
| outlet4 | 88 | 44.7% | 3.97e5 | 1.97e6 | 7.61e-7 |

See [windkessel_parameters_example.md](windkessel_parameters_example.md) for detailed calculation methodology.

### Custom Flow Split Ratios
```json
"outlets": {
  "type": "3EWINDKESSEL",
  "windkessel_settings": {
    "systolic_pressure": 120,
    "diastolic_pressure": 80,
    "flow_split": {
      "outlet1": 0.4,
      "outlet2": 0.3,
      "outlet3": 0.2,
      "outlet4": 0.1
    }
  }
}
```

---

## Tips and Best Practices

### 1. Start Simple
- Begin with `config_minimal.json`
- Add parameters only when needed
- Let profiles handle most settings

### 2. Incremental Refinement
1. Run `coarse` first to validate geometry
2. Move to `medium` for actual analysis
3. Use `fine` only for publications

### 3. Parallel Execution
- Match mesh and solver processors: `mesh.SNAPPY_SETTINGS.nProcessors = run_settings.subdomains`
- Use powers of 2: 2, 4, 8, 16
- Don't exceed available CPU cores

### 4. Memory Management
- `coarse`: 4-8 GB
- `medium`: 8-16 GB
- `fine`: 16-32 GB
- LES: 32-64 GB

### 5. Validation Workflow
```bash
# 1. Quick geometry check
python run_patient.py patient1 --quick

# 2. Run actual simulation
python run_patient.py patient1 --config examples/config_laminar_clinical.json

# 3. Resume if needed
python run_patient.py patient1 --resume --step solver
```

---

## Modifying Examples

### Step 1: Copy example
```bash
cp examples/config_laminar_clinical.json cases_input/patient1/config.json
```

### Step 2: Edit key parameters
```json
{
  "case_info": {
    "patient_id": "patient1",  // Change this
    "heart_rate": 75           // Adjust if needed
  },
  "boundary_conditions": {
    "inlet": {
      "csv_file": "BPM75.csv"  // Match your flow data
    },
    "outlets": {
      "windkessel_settings": {
        "systolic_pressure": 120,  // Patient-specific BP
        "diastolic_pressure": 80
      }
    }
  }
}
```

### Step 3: Run simulation
```bash
python run_patient.py patient1
```

---

## Troubleshooting

### Config validation failed
```bash
# Check JSON syntax
python -c "import json; json.load(open('config.json'))"

# Validate against schema (if available)
python -c "from src.aortacfd_lib.utils.validation import validate_config; validate_config('config.json')"
```

### Profile not found
- Check `simulation_settings.solver_type` and `analysis_type`
- Valid combinations: `laminar|rans|les` × `coarse|medium|fine`
- Or use `--profile` flag to override

### Memory issues
- Reduce `analysis_type` from `fine` to `medium`
- Decrease `simulation_control.number_of_cycles`
- Lower `run_settings.subdomains`

---

## Additional Resources

- **Main README:** [../README.md](../README.md)
- **Profile Details:** See main README "Simulation Profiles & Architecture" section
- **Workflow Steps:** Run `python run_patient.py --list-steps`
- **Available Profiles:** Run `python -c "from src.patient_runner.core import PatientCaseRunner; PatientCaseRunner().display_profile_selection()"`

---

## Example Comparison Table

| Example | Solver | Resolution | Cores | Runtime | Best For |
|---------|--------|------------|-------|---------|----------|
| minimal | Laminar | Medium (15) | Auto | 30-60 min | First-time users |
| laminar_clinical | Laminar | Medium (15) | 4 | 30-60 min | Clinical analysis |
| rans_turbulence | RANS | Medium (18) | 8 | 2-3 hours | Stenosis/CoA |
| les_research | LES | Fine (25) | 16 | 5-7 hours | Research/Publications |

---

**Need help?** Open an issue or see the main README troubleshooting section.
