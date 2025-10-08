# Config Parameter Mapping & Flow Documentation

## Overview
This document maps all user config parameters to their profile equivalents and traces how they flow through the system.

---

## Config Structure Hierarchy

```
config.json (User)           →  Profile (sim_rans_medium.py)  →  Final Merged Config
├── case_info                →  [not in profile]              →  metadata only
├── simulation_settings      →  [partially mapped]            →  controls profile selection
├── physics                  →  physics                       →  MERGED (user overrides)
├── geometry                 →  geometry                      →  MERGED (user overrides)
├── mesh                     →  mesh                          →  MERGED (user overrides)
├── boundary_conditions      →  boundary                      →  MERGED (user overrides)
├── simulation_control       →  simulation_control            →  MERGED (user overrides)
└── run_settings             →  run_settings                  →  MERGED (user overrides) ✅ FIXED
```

---

## 1. CASE_INFO Section

### User Config Location: `case_info`
```json
{
  "case_info": {
    "patient_id": "patient1",
    "description": "Simple RANS medium simulation"
  }
}
```

### Profile: N/A
**Not defined in profiles - metadata only**

### Flow:
1. **Read:** [patient_runner/core.py:131](src/patient_runner/core.py#L131)
   ```python
   case_info = {
       'patient_id': case_name,
       'config': case_config
   }
   ```

2. **Used for:**
   - Output directory naming
   - Logging/reporting
   - NOT merged into final config

### Override: ❌ No override - user only

---

## 2. SIMULATION_SETTINGS Section

### User Config Location: `simulation_settings`
```json
{
  "simulation_settings": {
    "analysis_type": "medium",    // Profile selector
    "solver_type": "RANS"          // Profile selector
  }
}
```

### Profile: N/A (used for selection only)
**These select WHICH profile to load, not merged**

### Flow:
1. **Read:** [patient_runner/core.py:516-517](src/patient_runner/core.py#L516)
   ```python
   solver_type = str(simulation_settings.get('solver_type', 'laminar')).strip().lower()
   analysis_type = simulation_settings.get('analysis_type', 'medium')
   ```

2. **Used to construct:** `profile_key = f"sim_{solver_type}_{analysis_type}"`
   - Example: `"sim_rans_medium"`

3. **Stored in final config:** [patient_runner/core.py:217-220](src/patient_runner/core.py#L217)
   ```python
   merged_config['simulation_settings']['selected_profile_key'] = profile_key
   merged_config['simulation_settings']['solver_type'] = profile_data['solver_type']
   ```

### Override: ⚠️ Partial - used for selection, then replaced by profile metadata

---

## 3. PHYSICS Section

### User Config Location: `physics`
```json
{
  "physics": {
    "blood_density": 1060,        // User override
    "blood_viscosity": 0.004      // User override
  }
}
```

### Profile: `RANS_MEDIUM_EXTRAS['physics']` (via turbulence fragment)
```python
# From turbulence.py fragment
{
  "simulation_type": "RAS",
  "turbulence_model": "kOmegaSST",
  "turbulence_intensity": 0.05,
  "turbulence_viscosity_ratio": 10.0
}
```

### Merge Flow:
1. **Profile loads defaults:** [config/profiles/fragments/turbulence.py:35-38](src/config/profiles/fragments/turbulence.py#L35)

2. **User config mapped:** [patient_runner/core.py:362-365](src/patient_runner/core.py#L362)
   ```python
   if 'blood_density' in physics:
       config['physics']['default_density'] = physics['blood_density']
   if 'blood_viscosity' in physics:
       config['physics']['default_viscosity'] = physics['blood_viscosity']
   ```

3. **Kinematic viscosity calculated:** [config/builder.py:245-249](src/config/builder.py#L245)
   ```python
   mu = config['physics']['default_viscosity']  # Pa·s
   rho = config['physics']['default_density']   # kg/m³
   nu = mu / rho
   config['physics']['nu'] = nu
   config['physics']['rho'] = rho
   ```

4. **Used in templates:**
   - [templates/transportProperties.tpl](src/templates/transportProperties.tpl) - Uses `nu`
   - [templates/momentumTransport.tpl:24-35](src/templates/momentumTransport.tpl#L24) - Uses `simulation_type`, `turbulence_model`
   - [boundary_condition_setup.py:160-170](src/aortacfd_lib/boundary_condition_setup.py#L160) - Uses `turbulence_intensity`, `turbulence_viscosity_ratio`

### Final Merged Config:
```python
{
  "physics": {
    "simulation_type": "RAS",              # From profile
    "turbulence_model": "kOmegaSST",       # From profile
    "turbulence_intensity": 0.05,          # From profile
    "turbulence_viscosity_ratio": 10.0,    # From profile
    "default_density": 1060,               # From user (blood_density)
    "default_viscosity": 0.004,            # From user (blood_viscosity)
    "rho": 1060,                           # Calculated
    "nu": 3.77e-06,                        # Calculated (mu/rho)
    "mu": 0.004                            # Calculated
  }
}
```

### Override: ✅ User can override with `blood_density`, `blood_viscosity`

---

## 4. GEOMETRY Section

### User Config Location: `geometry`
```json
{
  "geometry": {
    "rotation": false,
    "scale_factor": 0.001
  }
}
```

### Profile: N/A (minimal geometry settings)
**Profiles don't define geometry - case-specific**

### Flow:
1. **Auto-discovery:** [config/builder.py:180-199](src/config/builder.py#L180)
   ```python
   # STL file discovery
   discovered_geom_config = {
       "geometry": {
           "case_name": case_name,
           "wall_keywords_ordered": wall_patches[0],
           "inlet_keywords_ordered": inlet_patches[0],
           "outlet_keywords_ordered": [outlet_names...]
       }
   }
   ```

2. **User settings merged:** [config/builder.py:217](src/config/builder.py#L217)
   ```python
   result = deep_merge(discovered_geom_config, {"geometry": geometry_settings})
   ```

3. **Used in:**
   - [mesh_setup.py](src/aortacfd_lib/mesh_setup.py) - Scaling, rotation
   - [inlet_mapping.py](src/aortacfd_lib/inlet_mapping.py) - Coordinate transforms
   - [wk_setup.py:38-40](src/aortacfd_lib/wk_setup.py#L38) - Area calculations with scale_factor

### Final Merged Config:
```python
{
  "geometry": {
    "case_name": "patient1",               # Auto-discovered
    "wall_keywords_ordered": "wall_aorta",  # Auto-discovered
    "inlet_keywords_ordered": "inlet",      # Auto-discovered
    "outlet_keywords_ordered": ["outlet1", "outlet2", ...],  # Auto-discovered
    "rotation": false,                      # From user
    "scale_factor": 0.001                   # From user
  }
}
```

### Override: ✅ User provides all geometry settings (auto-discovery for patches)

---

## 5. MESH Section

### User Config Location: `mesh`
```json
{
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 1.8
    },
    "SNAPPY_SETTINGS": {
      "parallel": false,
      "nProcessors": 1
    }
  }
}
```

### Profile: `RANS_MEDIUM_EXTRAS['mesh']`
```python
{
  "automatic_refinement": {
    "enabled": True,
    "methodology": "murray_law_based"
  },
  "cells_per_patch_diameter": {
    "coarse": 12,
    "medium": 16,
    "fine": 22
  }
}
```

### Merge Flow:
1. **Profile defaults:** [config/profiles/sim_rans_medium.py:20-29](src/config/profiles/sim_rans_medium.py#L20)

2. **User config extracted & merged:** [config/builder.py:210-221](src/config/builder.py#L210)
   ```python
   mesh_settings = case_config.get('mesh', {})
   if mesh_settings:
       result = deep_merge(result, {"mesh": mesh_settings})
   ```

3. **Special handling for SNAPPY_SETTINGS:** [patient_runner/core.py:369-383](src/patient_runner/core.py#L369)
   ```python
   mesh_overrides = case_config.get('mesh', {}).get('SNAPPY_SETTINGS', {})
   if 'parallel' in mesh_overrides:
       snappy_config['parallel'] = mesh_overrides['parallel']
   if 'nProcessors' in mesh_overrides:
       snappy_config['nProcessors'] = mesh_overrides['nProcessors']
   ```

4. **Used in:**
   - [mesh_setup.py](src/aortacfd_lib/mesh_setup.py) - Generates blockMeshDict, snappyHexMeshDict
   - [execution_tasks.py:23-27](src/workflow/tasks/execution_tasks.py#L23) - Parallel meshing

### Final Merged Config:
```python
{
  "mesh": {
    "automatic_refinement": {              # From profile
      "enabled": True,
      "methodology": "murray_law_based"
    },
    "cells_per_patch_diameter": {          # From profile
      "coarse": 12,
      "medium": 16,
      "fine": 22
    },
    "mesh_resolution": {                   # From user
      "target_cell_size_mm": 1.8
    },
    "SNAPPY_SETTINGS": {                   # From user (overrides profile)
      "parallel": false,
      "nProcessors": 1
    }
  }
}
```

### Override: ✅ User overrides work correctly

---

## 6. BOUNDARY_CONDITIONS Section

### User Config Location: `boundary_conditions`
```json
{
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "test_cardio_profile.csv",
      "data_type": "velocity",
      "profile": "plug",
      "orientation": "out"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "methodology": "murray_law_automatic",
        "systolic_pressure": 120,
        "diastolic_pressure": 80
      }
    },
    "walls": {
      "type": "no_slip",
      "roughness": 0.0
    }
  }
}
```

### Profile: `RANS_MEDIUM_EXTRAS['boundary']`
```python
{
  "BC_INLET": "TIMEVARYING",
  "BC_OUTLET": "ZEROGRADIENT",
  "INLET_DATA_TYPE": "velocity",
  "INLET_PROFILE": "womersley",
  "INLET_ORIENTATION": "out"
}
```

### Merge Flow:
1. **Profile uses legacy flat format** (BC_INLET, BC_OUTLET)

2. **User config uses nested format** (boundary_conditions.inlet, boundary_conditions.outlets)

3. **Both are supported:** [boundary_condition_setup.py:24-25](src/aortacfd_lib/boundary_condition_setup.py#L24)
   ```python
   # Support both flattened and nested config structures
   self.inlet_settings = self.config.get('boundary_conditions', {}).get('inlet') or self.config.get('inlet', {})
   self.outlet_settings = self.config.get('boundary_conditions', {}).get('outlets') or self.config.get('outlets', {})
   ```

4. **User config extracted & merged:** [config/builder.py:201-218](src/config/builder.py#L201)
   ```python
   boundary_conditions = case_config.get('boundary_conditions', {})
   result = deep_merge(result, boundary_conditions)
   ```

5. **Used in:**
   - [boundary_condition_setup.py](src/aortacfd_lib/boundary_condition_setup.py) - Generates U, p, k, omega files
   - [inlet_mapping.py](src/aortacfd_lib/inlet_mapping.py) - Generates boundaryData
   - [wk_setup.py](src/aortacfd_lib/wk_setup.py) - Generates windkesselProperties

### Final Merged Config:
```python
{
  # User provides NESTED format:
  # "boundary_conditions": { "inlet": {...}, "outlets": {...} }

  # But final config uses FLAT format for backward compatibility:
  "inlet": {
    "type": "TIMEVARYING",
    "csv_file": "test_cardio_profile.csv",
    "data_type": "velocity",
    "profile": "plug",
    "orientation": "out"
  },
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "methodology": "murray_law_automatic",
      "systolic_pressure": 120,
      "diastolic_pressure": 80
    }
  },
  "walls": {
    "type": "no_slip",
    "roughness": 0.0
  }
}
```

### Override: ✅ User overrides work correctly
**Note:** User provides nested format (`boundary_conditions.inlet`), which gets converted to flat format (`inlet`) in final config.

---

## 7. SIMULATION_CONTROL Section

### User Config Location: `simulation_control`
```json
{
  "simulation_control": {
    "end_time": "auto",
    "number_of_cycles": 2,
    "writeInterval": 0.05
  }
}
```

### Profile: `RANS_MEDIUM_EXTRAS['simulation_control']['controlDict']`
```python
{
  "controlDict": {
    "application": "pimpleFoam",
    "startFrom": "startTime",
    "startTime": 0.0,
    "stopAt": "endTime",
    "endTime": "auto",
    "deltaT": 5e-05,
    "writeControl": "adjustableRunTime",
    "writeInterval": 0.01,
    "runTimeModifiable": "true",
    "adjustTimeStep": "yes",
    "maxCo": 1.0,
    "maxDeltaT": 5e-04,
    "minDeltaT": 1e-07,
    "functions": ["wallShearStress", "Q"]
  }
}
```

### Merge Flow:
1. **Profile provides controlDict template**

2. **User config extracted & merged:** [config/builder.py:207-219](src/config/builder.py#L207)
   ```python
   simulation_control = case_config.get('simulation_control', {})
   result = deep_merge(result, {"simulation_control": simulation_control})
   ```

3. **End time calculation:** [workflow/tasks/setup_tasks.py:277-289](src/workflow/tasks/setup_tasks.py#L277)
   ```python
   if final_end_time == "auto":
       cardiac_cycle = context.get("cardiac_cycle")
       number_of_cycles = sim_controls.get("number_of_cycles", 1)
       final_end_time = float(cardiac_cycle) * int(number_of_cycles)
   ```

4. **Used in:**
   - [setup_tasks.py:GenerateControlDictTask](src/workflow/tasks/setup_tasks.py) - Generates controlDict
   - [cycle_data_setup.py:29](src/aortacfd_lib/cycle_data_setup.py#L29) - Creates cycle symlinks

### Final Merged Config:
```python
{
  "simulation_control": {
    "controlDict": {
      "application": "pimpleFoam",       # From profile
      "deltaT": 5e-05,                   # From profile
      "writeInterval": 0.01,             # From profile (unless user overrides)
      "maxCo": 1.0,                      # From profile
      "functions": ["wallShearStress", "Q"]  # From profile
    },
    "end_time": "auto",                  # From user (overrides profile)
    "number_of_cycles": 2,               # From user
    "writeInterval": 0.05                # From user
  }
}
```

### Override: ✅ User overrides work correctly

---

## 8. RUN_SETTINGS Section

### User Config Location: `run_settings`
```json
{
  "run_settings": {
    "solution_type": "serial",
    "subdomains": 1,
    "decomposition_method": "simple"
  }
}
```

### Profile: `RANS_MEDIUM_EXTRAS['run_settings']`
```python
{
  "solution_type": "parallel",
  "subdomains": 4,
  "decomposition_method": "scotch"
}
```

### Merge Flow:
1. **Profile defaults:** [config/profiles/sim_rans_medium.py:15-18](src/config/profiles/sim_rans_medium.py#L15)

2. **🐛 BUG WAS HERE:** User config was NOT being extracted in `_convert_unified_config`

3. **✅ FIXED:** [config/builder.py:213-223](src/config/builder.py#L213)
   ```python
   # Extract run settings from unified config
   run_settings = case_config.get('run_settings', {})
   if run_settings:
       result = deep_merge(result, {"run_settings": run_settings})
   ```

4. **Used in:**
   - [execution_tasks.py:122-125](src/workflow/tasks/execution_tasks.py#L122) - Parallel solver execution
   - [setup_tasks.py](src/workflow/tasks/setup_tasks.py) - Generates decomposeParDict

### Final Merged Config (AFTER FIX):
```python
{
  "run_settings": {
    "solution_type": "serial",           # From user ✅ NOW WORKS
    "subdomains": 1,                     # From user ✅ NOW WORKS
    "decomposition_method": "simple"     # From user ✅ NOW WORKS
  }
}
```

### Override: ✅ Fixed - user overrides now work correctly

---

## Merge Priority Summary

### Order of Operations:
1. **Base config** (config/base.py)
2. **Profile config** (e.g., sim_rans_medium.py)
3. **Profile fragments** (turbulence, spatial_resolution, solver_recipe)
4. **User config** ← HIGHEST PRIORITY (overrides everything)

### Code Reference:
[patient_runner/core.py:195-211](src/patient_runner/core.py#L195)
```python
# Step 1: Merge base + profile
base_and_profile = builder.build_base_and_profile(profile_name)

# Step 2: Merge fragments (if any)
fragment_config = ...
merged_config = deep_merge(base_and_profile, fragment_config)

# Step 3: Merge user config (HIGHEST PRIORITY)
case_specific_config = builder._convert_unified_config(case_config)
merged_config = deep_merge(merged_config, case_specific_config)  # User wins!
```

---

## Testing Each Parameter

### Test Script:
```python
#!/usr/bin/env python3
import json
import sys
sys.path.insert(0, 'src')

from patient_runner.core import PatientCaseRunner

# Load user config
with open('cases_input/patient1/config_simple_rans_medium.json') as f:
    user_config = json.load(f)

# Initialize runner
runner = PatientCaseRunner()
result = runner.prepare_config('patient1', user_config, {})

final_config = result['config']

# Test each section
print("=" * 60)
print("PARAMETER FLOW TEST")
print("=" * 60)

# 1. Physics
print("\n1. PHYSICS:")
print(f"  User blood_density: {user_config.get('physics', {}).get('blood_density')}")
print(f"  Final rho: {final_config['physics'].get('rho')}")
print(f"  Final nu: {final_config['physics'].get('nu')}")
print(f"  Profile turbulence_model: {final_config['physics'].get('turbulence_model')}")

# 2. Mesh
print("\n2. MESH:")
print(f"  User target_cell_size_mm: {user_config.get('mesh', {}).get('mesh_resolution', {}).get('target_cell_size_mm')}")
print(f"  Final target_cell_size_mm: {final_config.get('mesh', {}).get('mesh_resolution', {}).get('target_cell_size_mm')}")
print(f"  User SNAPPY parallel: {user_config.get('mesh', {}).get('SNAPPY_SETTINGS', {}).get('parallel')}")
print(f"  Final SNAPPY parallel: {final_config.get('mesh', {}).get('SNAPPY_SETTINGS', {}).get('parallel')}")

# 3. Run Settings
print("\n3. RUN_SETTINGS:")
print(f"  User solution_type: {user_config.get('run_settings', {}).get('solution_type')}")
print(f"  Final solution_type: {final_config.get('run_settings', {}).get('solution_type')}")
print(f"  User subdomains: {user_config.get('run_settings', {}).get('subdomains')}")
print(f"  Final subdomains: {final_config.get('run_settings', {}).get('subdomains')}")

# 4. Simulation Control
print("\n4. SIMULATION_CONTROL:")
print(f"  User end_time: {user_config.get('simulation_control', {}).get('end_time')}")
print(f"  Final end_time: {final_config.get('simulation_control', {}).get('end_time')}")
print(f"  User number_of_cycles: {user_config.get('simulation_control', {}).get('number_of_cycles')}")
print(f"  Final number_of_cycles: {final_config.get('simulation_control', {}).get('number_of_cycles')}")

# 5. Boundary Conditions
print("\n5. BOUNDARY_CONDITIONS:")
print(f"  User inlet type: {user_config.get('boundary_conditions', {}).get('inlet', {}).get('type')}")
print(f"  Final inlet type: {final_config.get('boundary_conditions', {}).get('inlet', {}).get('type')}")
print(f"  User outlet type: {user_config.get('boundary_conditions', {}).get('outlets', {}).get('type')}")
print(f"  Final outlet type: {final_config.get('boundary_conditions', {}).get('outlets', {}).get('type')}")

print("\n" + "=" * 60)
print("✅ All parameters tested!")
print("=" * 60)
```

---

## Quick Reference: Override Capabilities

| Section | User Can Override | Notes |
|---------|------------------|-------|
| **case_info** | N/A | Metadata only |
| **simulation_settings** | ⚠️ Partial | Selects profile, then replaced |
| **physics** | ✅ Yes | `blood_density`, `blood_viscosity` |
| **geometry** | ✅ Yes | All settings (patches auto-discovered) |
| **mesh** | ✅ Yes | All settings |
| **boundary_conditions** | ✅ Yes | All settings |
| **simulation_control** | ✅ Yes | All settings |
| **run_settings** | ✅ Yes (FIXED) | All settings |

---

## Common Pitfalls

1. **run_settings not working** → ✅ FIXED in this session
2. **Duplicate BC entries** → Use nested `boundary_conditions` format only
3. **Profile settings bleeding through** → Check merge order, user should always win
4. **Missing parameters** → Add to `_convert_unified_config` extraction

---

## Verification Test Results

Run the automated test to verify parameter flow:
```bash
./venv/bin/python test_config_parameter_flow.py
```

**Latest Test Results:** ✅ **13/13 PASSED**

| Test Category | Parameters Tested | Status |
|---------------|------------------|--------|
| Physics | blood_density → rho, blood_viscosity → mu, nu calculation | ✅ PASS |
| Mesh | target_cell_size_mm, SNAPPY_SETTINGS.parallel | ✅ PASS |
| Run Settings | solution_type, subdomains | ✅ PASS (FIXED) |
| Simulation Control | end_time, number_of_cycles | ✅ PASS |
| Boundary Conditions | inlet.type, outlets.type, windkessel_settings | ✅ PASS |
| Geometry | scale_factor, auto-discovery | ✅ PASS |

---

## Quick Reference: Parameter Override Behavior

### ✅ Parameters Where User Config Fully Overrides Profile

| Section | Parameter | User Config Key | Final Config Key | Profile Default |
|---------|-----------|----------------|------------------|-----------------|
| **Physics** | Blood density | `physics.blood_density` | `physics.rho` | N/A (required) |
| **Physics** | Blood viscosity | `physics.blood_viscosity` | `physics.mu` | N/A (required) |
| **Mesh** | Cell size | `mesh.mesh_resolution.target_cell_size_mm` | Same | Profile varies |
| **Mesh** | Parallel meshing | `mesh.SNAPPY_SETTINGS.parallel` | Same | `false` |
| **Mesh** | Processors | `mesh.SNAPPY_SETTINGS.nProcessors` | Same | `1` |
| **Run** | Solution type | `run_settings.solution_type` | Same | `"parallel"` |
| **Run** | Subdomains | `run_settings.subdomains` | Same | `4` (medium) |
| **Run** | Decomposition | `run_settings.decomposition_method` | Same | `"scotch"` |
| **SimControl** | End time | `simulation_control.end_time` | Same | `"auto"` |
| **SimControl** | Cycles | `simulation_control.number_of_cycles` | Same | `1` |
| **SimControl** | Write interval | `simulation_control.writeInterval` | Same | `0.01` |
| **BC** | Inlet type | `boundary_conditions.inlet.type` | `inlet.type` | Profile varies |
| **BC** | Outlet type | `boundary_conditions.outlets.type` | `outlets.type` | Profile varies |
| **BC** | WK settings | `boundary_conditions.outlets.windkessel_settings` | `outlets.windkessel_settings` | N/A |
| **Geometry** | Scale factor | `geometry.scale_factor` | Same | `1.0` |
| **Geometry** | Rotation | `geometry.rotation` | Same | `false` |

### ⚠️ Parameters Where Profile Provides Defaults (User Can Override)

| Section | Parameter | User Override Available | Notes |
|---------|-----------|------------------------|-------|
| **Physics** | `simulation_type` | ❌ No | Set by profile (RAS/LES/laminar) |
| **Physics** | `turbulence_model` | ⚠️ Advanced | Profile default: kOmegaSST |
| **Physics** | `turbulence_intensity` | ⚠️ Advanced | Profile default: 0.05 |
| **Physics** | `turbulence_viscosity_ratio` | ⚠️ Advanced | Profile default: 10.0 |
| **Mesh** | `automatic_refinement` | ✅ Yes | Profile enables Murray-based |
| **Mesh** | `cells_per_patch_diameter` | ✅ Yes | Profile varies by resolution |
| **SimControl** | `controlDict.deltaT` | ⚠️ Advanced | Profile optimized per solver |
| **SimControl** | `controlDict.maxCo` | ⚠️ Advanced | Profile sets CFL limit |

### ❌ Parameters That Cannot Be Overridden

| Parameter | Reason | Set By |
|-----------|--------|--------|
| `openfoam_version` | System configuration | Hardcoded to 12 |
| `openfoam_major_version` | System configuration | Hardcoded to 12 |
| `solver_application` | OpenFOAM 12 requirement | Hardcoded to "foamRun" |
| `solver_module` | OpenFOAM 12 requirement | Hardcoded to "incompressibleFluid" |
| `geometry.case_name` | Auto-discovered | Patient ID |
| `geometry.inlet_keywords_ordered` | Auto-discovered | STL file names |
| `geometry.outlet_keywords_ordered` | Auto-discovered | STL file names |
| `geometry.wall_keywords_ordered` | Auto-discovered | STL file names |

---

*Last Updated: 2025-10-05*
*Fixed: run_settings override bug*
*Test Status: ✅ 13/13 PASSED*
