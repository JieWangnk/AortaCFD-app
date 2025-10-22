# Profile Override Behavior - Detailed Example

## Question: When using `--profile`, are config.json settings replaced with defaults?

**Answer: NO!** Your config.json settings always have the highest priority and are preserved.

---

## Configuration Merge Priority

```
┌─────────────────────────────────────────────────────────────┐
│  Priority Level (Higher = Wins)                             │
├─────────────────────────────────────────────────────────────┤
│  1. Base Config          (Lowest)  - OpenFOAM defaults      │
│  2. Profile Config                  - Profile settings      │
│  3. Fragment Composition            - Mesh/solver fragments │
│  4. Your config.json    (HIGHEST)  - YOUR SETTINGS WIN!     │
└─────────────────────────────────────────────────────────────┘
```

---

## Concrete Example

### Your config.json
```json
{
  "case_info": {
    "patient_id": "my_patient",
    "description": "Custom case with specific settings"
  },
  "simulation_settings": {
    "solver_type": "laminar",
    "analysis_type": "medium"
  },
  "physics": {
    "blood_density": 1050,
    "blood_viscosity": 0.0035
  },
  "geometry": {
    "scale_factor": 0.001,
    "rotation": true,
    "target_normal": [1, 0, 0]
  },
  "computational": {
    "parallel": true,
    "max_processors": 16
  },
  "mesh": {
    "SNAPPY_SETTINGS": {
      "nProcessors": 16,
      "maxNonOrtho": 65
    }
  },
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "BPM90.csv",
      "profile": "parabolic"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 130,
        "diastolic_pressure": 85,
        "flow_split": 35
      }
    }
  },
  "simulation_control": {
    "number_of_cycles": 8,
    "writeInterval": 0.005
  }
}
```

---

## Scenario 1: No Override (Default Behavior)

### Command:
```bash
python run_patient.py my_patient
```

### Result:
```yaml
Profile Selected: sim_laminar_medium (from config.json)

Settings Applied:
  solver_type: laminar                    # From config.json
  analysis_level: medium                  # From config.json
  mesh_resolution_priority: 15            # From sim_laminar_medium profile
  solver_recipe: balanced                 # From sim_laminar_medium profile
  max_CFL: 0.8                           # From sim_laminar_medium profile

  blood_density: 1050                     # From config.json ✓
  blood_viscosity: 0.0035                 # From config.json ✓
  scale_factor: 0.001                     # From config.json ✓
  rotation: true                          # From config.json ✓
  target_normal: [1, 0, 0]               # From config.json ✓
  max_processors: 16                      # From config.json ✓
  nProcessors: 16                         # From config.json ✓
  maxNonOrtho: 65                        # From config.json ✓

  inlet_type: TIMEVARYING                 # From config.json ✓
  inlet_csv: BPM90.csv                    # From config.json ✓
  inlet_profile: parabolic                # From config.json ✓
  systolic_pressure: 130                  # From config.json ✓
  diastolic_pressure: 85                  # From config.json ✓
  flow_split: 35                          # From config.json ✓

  number_of_cycles: 8                     # From config.json ✓
  writeInterval: 0.005                    # From config.json ✓
```

**Conclusion:** All your config.json settings are used ✓

---

## Scenario 2: With --profile Override

### Command:
```bash
python run_patient.py my_patient --profile sim_rans_fine
```

### Result:
```yaml
Profile Selected: sim_rans_fine (from CLI override)

Settings Applied:
  solver_type: rans                       # From sim_rans_fine profile (CHANGED)
  analysis_level: fine                    # From sim_rans_fine profile (CHANGED)
  mesh_resolution_priority: 22            # From sim_rans_fine profile (CHANGED)
  solver_recipe: aggressive               # From sim_rans_fine profile (CHANGED)
  max_CFL: 1.0                           # From sim_rans_fine profile (CHANGED)

  blood_density: 1050                     # From config.json ✓ (PRESERVED!)
  blood_viscosity: 0.0035                 # From config.json ✓ (PRESERVED!)
  scale_factor: 0.001                     # From config.json ✓ (PRESERVED!)
  rotation: true                          # From config.json ✓ (PRESERVED!)
  target_normal: [1, 0, 0]               # From config.json ✓ (PRESERVED!)
  max_processors: 16                      # From config.json ✓ (PRESERVED!)
  nProcessors: 16                         # From config.json ✓ (PRESERVED!)
  maxNonOrtho: 65                        # From config.json ✓ (PRESERVED!)

  inlet_type: TIMEVARYING                 # From config.json ✓ (PRESERVED!)
  inlet_csv: BPM90.csv                    # From config.json ✓ (PRESERVED!)
  inlet_profile: parabolic                # From config.json ✓ (PRESERVED!)
  systolic_pressure: 130                  # From config.json ✓ (PRESERVED!)
  diastolic_pressure: 85                  # From config.json ✓ (PRESERVED!)
  flow_split: 35                          # From config.json ✓ (PRESERVED!)

  number_of_cycles: 8                     # From config.json ✓ (PRESERVED!)
  writeInterval: 0.005                    # From config.json ✓ (PRESERVED!)
```

**Conclusion:**
- ✅ Profile-related settings changed (solver, mesh, numerics)
- ✅ ALL your config.json settings are PRESERVED!

---

## What --profile Actually Changes

### Profile-Controlled Settings (can be overridden by --profile):
1. **Solver type** (laminar/RANS/LES)
2. **Turbulence model** (if applicable)
3. **Mesh resolution priority** (10, 15, 20, 22, 25)
4. **Solver recipe** (robust/balanced/aggressive)
5. **Numerical schemes** (ddtSchemes, gradSchemes, etc.)
6. **PIMPLE control** (nOuterCorrectors, residual controls)
7. **Max Courant number** (maxCo)

### Config.json-Controlled Settings (NEVER overridden by --profile):
1. **Physics properties** (blood_density, blood_viscosity)
2. **Geometry settings** (scale_factor, rotation, target_normal)
3. **Computational resources** (max_processors, nProcessors, subdomains)
4. **Boundary conditions** (inlet type, outlet settings, pressures)
5. **Simulation control** (number_of_cycles, writeInterval, end_time)
6. **Mesh quality controls** (maxNonOrtho, maxSkewness)
7. **Custom settings** (any patient-specific parameters)

---

## Key Takeaways

### ✅ What You Should Know:

1. **config.json always wins** - Your settings are NEVER replaced
2. **--profile only changes profile-specific settings** (solver type, mesh resolution, numerics)
3. **Safe to experiment** - Try different profiles without losing your settings
4. **Best practice**: Set physics/BC in config.json, use --profile for quality level

### ❌ Common Misconceptions:

1. ~~"--profile replaces my config"~~ → **FALSE!** Your config is preserved
2. ~~"I need separate configs for each profile"~~ → **FALSE!** One config works for all
3. ~~"--profile changes my boundary conditions"~~ → **FALSE!** BCs are never touched

---

## Practical Workflow

### Step 1: Create config.json with your case settings
```json
{
  "case_info": { "patient_id": "patient1" },
  "physics": { "blood_density": 1050, "blood_viscosity": 0.0035 },
  "boundary_conditions": { /* your BCs */ },
  "simulation_control": { "number_of_cycles": 5 }
}
```

### Step 2: Run with different profiles WITHOUT changing config
```bash
# Quick check
python run_patient.py patient1 --profile sim_laminar_coarse

# Clinical analysis
python run_patient.py patient1 --profile sim_laminar_medium

# High quality
python run_patient.py patient1 --profile sim_laminar_fine

# Turbulence modeling (if stenosis)
python run_patient.py patient1 --profile sim_rans_medium
```

**All runs use the SAME config.json!** Only the simulation quality/solver changes.

---

## Advanced: Deep Merge Behavior

The system uses **deep_merge** which means:

### If profile has:
```python
{'mesh': {'SNAPPY_SETTINGS': {'parallel': True, 'nProcessors': 4}}}
```

### And config.json has:
```python
{'mesh': {'SNAPPY_SETTINGS': {'nProcessors': 16, 'maxNonOrtho': 65}}}
```

### Final result:
```python
{
  'mesh': {
    'SNAPPY_SETTINGS': {
      'parallel': True,      # From profile
      'nProcessors': 16,     # From config.json (overrides profile's 4)
      'maxNonOrtho': 65      # From config.json (not in profile)
    }
  }
}
```

**Key point:** Only the specific conflicting keys are overridden, not entire sections!

---

## Testing This Yourself

### Test 1: See what profile uses
```bash
# Run with --profile and check the log
python run_patient.py patient1 --profile sim_rans_fine 2>&1 | grep -A 5 "Configuration prepared"
```

You'll see:
```
✅ Configuration prepared - Profile: sim_rans_fine
   Blood density: 1050 (from your config)
   Blood viscosity: 0.0035 (from your config)
   Processors: 16 (from your config)
```

### Test 2: Compare runs
```bash
# Run 1: laminar coarse
python run_patient.py patient1 --profile sim_laminar_coarse --step case
cat output/patient1/run_*/openfoam/system/fvSchemes

# Run 2: rans fine (same config.json!)
python run_patient.py patient1 --profile sim_rans_fine --step case
cat output/patient1/run_*/openfoam/system/fvSchemes

# Notice: fvSchemes changes (profile-controlled)
# But: transportProperties, boundary conditions stay the same (config.json-controlled)
```

---

## Summary

**When you use `--profile`:**
- ✅ Profile settings change (solver, mesh, numerics)
- ✅ Your config.json settings are PRESERVED
- ✅ Deep merge ensures no data loss
- ✅ Safe to experiment with different profiles

**You can think of it like:**
- config.json = "What to simulate" (your case specifics)
- --profile = "How to simulate it" (quality/method)

They work together, with your config.json always taking priority for case-specific settings!
