# OpenFOAM Function Objects Guide

Function objects allow you to perform calculations and data extraction **during** the simulation, without needing separate post-processing steps.

---

## Quick Start: Add Wall Shear Stress

### Method 1: Use Built-in `#includeFunc`

In your config JSON:

```json
{
  "simulation_control": {
    "end_time": 2,
    "writeInterval": 0.2,

    "controlDict": {
      "functions": [
        "wallShearStress"
      ]
    }
  }
}
```

This will add to `controlDict`:

```foam
functions
{
    #includeFunc wallShearStress
}
```

**Output:** Creates `wallShearStress` field in each time directory (e.g., `0/wallShearStress`, `0.2/wallShearStress`, etc.)

---

## Common Function Objects

### 1. Wall Shear Stress

**Purpose:** Calculate wall shear stress on all wall patches

**Config:**
```json
"functions": ["wallShearStress"]
```

**Output:**
- Field: `wallShearStress` (vector field, units: Pa)
- Magnitude: Use ParaView calculator: `mag(wallShearStress)`

**Typical Values (Aorta):**
- Peak systole: 10-70 Pa
- Low/disturbed flow: < 4 Pa (atherosclerosis risk)
- High WSS: > 70 Pa (aneurysm risk)

---

### 2. Y+ (For RANS/LES Only)

**Purpose:** Check if mesh resolution is appropriate for turbulence model

**Config:**
```json
"functions": ["yPlus"]
```

**Output:**
- Field: `yPlus` (scalar field)

**Target Values:**
- Wall-resolved RANS: y+ < 1
- Wall functions: 30 < y+ < 300
- LES: y+ < 1

**Note:** Only relevant for RANS/LES, not laminar simulations.

---

### 3. Pressure Drop

**Purpose:** Calculate pressure difference between inlet and outlets

**Config:**
```json
"functions": ["pressureDrop"]
```

**Customization:** If you need specific patches, see Method 2 below.

---

### 4. Forces and Moments

**Purpose:** Calculate forces on patches (e.g., for FSI coupling)

**Config:**
```json
"functions": ["forces"]
```

---

### 5. Streamlines

**Purpose:** Visualize flow paths

**Config:**
```json
"functions": ["streamLines"]
```

---

## Method 2: Custom Function Object Configuration

For more control, create custom function object files in `system/`:

### Example: Custom Wall Shear Stress (Specific Patches)

**File:** `system/wallShearStressCustom`

```foam
/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  12
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/

wallShearStressCustom
{
    type            wallShearStress;
    libs            ("libfieldFunctionObjects.so");

    // Write at same intervals as fields
    writeControl    writeTime;

    // Optional: specify which patches
    patches         (wall_aorta);

    // Optional: write to log
    log             true;
}

// ************************************************************************* //
```

**Then in config:**

```json
"functions": ["wallShearStressCustom"]
```

---

### Example: Time-Averaged Wall Shear Stress

**File:** `system/wallShearStressMean`

```foam
wallShearStressMean
{
    type            fieldAverage;
    libs            ("libfieldFunctionObjects.so");

    writeControl    writeTime;

    fields
    (
        wallShearStress
        {
            mean        on;
            prime2Mean  off;
            base        time;
        }
    );

    // Start averaging after initial transient
    timeStart       0.5;
}
```

**Output:** `wallShearStressMean` field with time-averaged values.

---

### Example: WSS Magnitude Statistics

**File:** `system/wallShearStressStats`

```foam
wallShearStressStats
{
    type            surfaceFieldValue;
    libs            ("libfieldFunctionObjects.so");

    writeControl    writeTime;
    log             true;

    writeFields     false;

    regionType      patch;
    name            wall_aorta;

    operation       none;

    fields
    (
        wallShearStress
    );

    // Calculate additional statistics
    writeArea       true;

    // This will log min/max/average WSS to log file
}
```

---

## Method 3: Multiple Function Objects

You can combine multiple functions:

```json
{
  "simulation_control": {
    "controlDict": {
      "functions": [
        "wallShearStress",
        "yPlus",
        "pressureDrop",
        "forces"
      ]
    }
  }
}
```

---

## Advanced: Custom Function Objects

### Time-Averaged Quantities (For Pulsatile Flow)

**File:** `system/timeAveragedFields`

```foam
timeAveragedFields
{
    type            fieldAverage;
    libs            ("libfieldFunctionObjects.so");

    writeControl    writeTime;

    fields
    (
        U
        {
            mean        on;
            prime2Mean  on;  // For Reynolds stresses
            base        time;
        }

        p
        {
            mean        on;
            prime2Mean  off;
            base        time;
        }

        wallShearStress
        {
            mean        on;
            prime2Mean  off;
            base        time;
        }
    );

    // Average over last cardiac cycle
    timeStart       1.0;  // Start after first cycle
}
```

**Config:**
```json
"functions": ["timeAveragedFields"]
```

**Output:**
- `UMean` - Time-averaged velocity
- `UPrime2Mean` - Reynolds stress tensor
- `pMean` - Time-averaged pressure
- `wallShearStressMean` - Time-averaged WSS

---

### Oscillatory Shear Index (OSI)

For atherosclerosis prediction, calculate OSI:

**File:** `system/oscillatoryShearIndex`

```foam
oscillatoryShearIndex
{
    type            coded;
    libs            ("libutilityFunctionObjects.so");

    writeControl    writeTime;

    // This requires coding - see OpenFOAM documentation
    // OSI = 0.5 * (1 - |TAWSS_vector| / TAWSS_magnitude)

    codeWrite
    #{
        // Custom C++ code to calculate OSI
        // from time-averaged WSS
    #};
}
```

**Note:** This is advanced - consider using ParaView's Python Calculator instead.

---

## Post-Processing Function Objects

### Extract Data at Specific Locations

**File:** `system/probes`

```foam
probes
{
    type            probes;
    libs            ("libsampling.so");

    writeControl    timeStep;
    writeInterval   1;

    fields
    (
        U
        p
        wallShearStress
    );

    probeLocations
    (
        (0.01 0.0 0.0)   // Ascending aorta
        (0.02 0.0 0.0)   // Descending aorta
        (0.00 0.01 0.0)  // Branch 1
    );
}
```

**Output:** `postProcessing/probes/0/U`, `p`, etc. with time-series data

---

### Cross-Section Sampling

**File:** `system/sliceSampling`

```foam
sliceSampling
{
    type            surfaces;
    libs            ("libsampling.so");

    writeControl    writeTime;

    surfaceFormat   vtk;

    fields          (U p wallShearStress);

    interpolationScheme cellPoint;

    surfaces
    (
        zNormal
        {
            type        cuttingPlane;
            planeType   pointAndNormal;
            point       (0 0 0);
            normal      (0 0 1);
        }

        xNormal
        {
            type        cuttingPlane;
            planeType   pointAndNormal;
            point       (0 0 0);
            normal      (1 0 0);
        }
    );
}
```

**Output:** `postProcessing/sliceSampling/*/surface.vtk` files

---

## Implementation Details

### How the Template Works

From [controlDict.tpl:64-71](../src/templates/controlDict.tpl#L64-L71):

```jinja
{% if config.simulation_control.controlDict.get('functions', []) %}
functions
{
    {% for func in config.simulation_control.controlDict.get('functions', []) %}
    #includeFunc {{ func }}
    {% endfor %}
}
{% endif %}
```

**This means:**
1. If you specify `functions: ["wallShearStress"]`
2. Template generates: `#includeFunc wallShearStress`
3. OpenFOAM includes built-in function definition from `$FOAM_ETC/caseDicts/postProcessing/`

---

## Complete Example Config

```json
{
  "case_info": {
    "patient_id": "BPM120_full_analysis"
  },

  "physics": {
    "model": "laminar",
    "transport_properties": {
      "rho": 1060,
      "nu": 3.7736e-6
    }
  },

  "numerics": {
    "profile": "standard"
  },

  "mesh": {
    "cells_per_diameter": 12,
    "boundary_layers": {
      "enabled": true,
      "target_yplus": 1.0,
      "num_layers": 8,
      "expansion_ratio": 1.2
    }
  },

  "geometry": {
    "inlet_keywords_ordered": "inlet",
    "outlet_keywords_ordered": ["outlet1", "outlet2", "outlet3", "outlet4"],
    "wall_keywords_ordered": "wall_aorta",
    "scale_factor": 0.001
  },

  "boundary_conditions": {
    "inlet": {
      "type": "CONSTANT",
      "flowrate": 4.7,
      "profile": "plug"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80,
        "venous_pressure": 0,
        "methodology": "murray_law_automatic",
        "tau": 1.0
      }
    },
    "walls": {
      "type": "no_slip"
    }
  },

  "simulation_control": {
    "end_time": 3.0,
    "number_of_cycles": 3,
    "writeInterval": 0.05,

    "controlDict": {
      "functions": [
        "wallShearStress",
        "pressureDrop",
        "forces"
      ]
    }
  },

  "run_settings": {
    "solution_type": "parallel",
    "subdomains": 8,
    "decomposition_method": "scotch"
  }
}
```

---

## Visualization in ParaView

### Load Results

1. Open `case.foam` file in ParaView
2. In **Properties** panel, select fields to load:
   - ✅ `wallShearStress`
   - ✅ `U`
   - ✅ `p`
3. Click **Apply**

### Calculate WSS Magnitude

1. Select your data in **Pipeline Browser**
2. **Filters → Calculator**
3. **Result Array Name:** `WSS_magnitude`
4. **Formula:** `mag(wallShearStress)`
5. Click **Apply**

### Visualize on Surface

1. **Filters → Extract Surface**
2. Apply **Color** by `WSS_magnitude`
3. Adjust **Color Map** (Rainbow, Cool to Warm, etc.)

### Time-Averaged WSS

1. **Filters → Temporal Statistics**
2. Select `WSS_magnitude`
3. Choose **Average** operation
4. Apply and visualize `WSS_magnitude_average`

---

## Common Issues

### Function not found

**Error:** `Unknown function type wallShearStress`

**Solution:** OpenFOAM 12 uses `#includeFunc`. Check your OpenFOAM version:
```bash
foamVersion
```

For older versions, use Method 2 with explicit function definitions.

### Missing library

**Error:** `libfieldFunctionObjects.so: cannot open shared object file`

**Solution:** Ensure OpenFOAM environment is sourced:
```bash
source /opt/openfoam12/etc/bashrc
```

### Empty fields

**Problem:** `wallShearStress` field is all zeros

**Causes:**
1. Simulation hasn't started yet (check time directories)
2. No wall patches detected (check `constant/polyMesh/boundary`)
3. Laminar flow with very low Re (WSS is very small)

---

## References

- **OpenFOAM User Guide:** Function Objects
- **Built-in Functions:** `$FOAM_ETC/caseDicts/postProcessing/`
- **Source Code:** `src/functionObjects/`

---

## Quick Reference Table

| Function | Purpose | Output Field | When to Use |
|----------|---------|--------------|-------------|
| `wallShearStress` | Wall shear stress | `wallShearStress` (vector, Pa) | Always (cardiovascular) |
| `yPlus` | Mesh quality for turbulence | `yPlus` (scalar) | RANS/LES only |
| `pressureDrop` | Pressure difference | Log file | Stenosis analysis |
| `forces` | Forces on patches | Log file + `forces.dat` | FSI coupling |
| `fieldAverage` | Time averaging | `*Mean` fields | Pulsatile flow |
| `surfaces` | Extract planes/surfaces | VTK files | Detailed visualization |
| `probes` | Point data | Time-series files | Specific location tracking |
| `streamLines` | Flow pathlines | `streamLines` | Flow visualization |

---

## Summary

**Simplest way to add WSS:**

```json
{
  "simulation_control": {
    "controlDict": {
      "functions": ["wallShearStress"]
    }
  }
}
```

Run simulation → Load in ParaView → Done! ✅
