# Running Realistic BC Validation with Pulsatile Flow and WSS

## Overview

This guide shows how to run CFD simulations with **realistic boundary conditions** including:
1. **Pulsatile inlet** from patient-specific flow data
2. **3-Element Windkessel (3EWK) outlets** with Murray's Law flow distribution
3. **Wall Shear Stress (WSS) extraction** for hemodynamic analysis

## Quick Start

```bash
# Source OpenFOAM (required!)
source /opt/openfoam12/etc/bashrc

# Run realistic validation with 1 cardiac cycle
./validation/run_realistic_validation.py patient1 --profile sim_laminar_medium --cycles 1.0
```

## Prerequisites

### 1. OpenFOAM Environment
```bash
# Check if OpenFOAM is sourced
which foamRun
# Should output: /opt/openfoam12/platforms/linux64GccDPInt32Opt/bin/foamRun

# If not sourced, run:
source /opt/openfoam12/etc/bashrc
```

### 2. Patient Data Files
Required in `cases_input/patient1/`:
- ✅ `config.json` - Patient configuration with realistic BCs
- ✅ `test_cardio_profile.csv` - Cardiac cycle velocity data
- ✅ `inlet.stl`, `outlet*.stl`, `wall_aorta.stl` - Geometry files

### 3. Python Environment
```bash
# Activate virtual environment
source venv/bin/activate

# Verify required packages
pip list | grep numpy
pip list | grep scipy
```

## Patient1 Realistic Configuration

### Pulsatile Inlet BC

**File**: `cases_input/patient1/test_cardio_profile.csv`

**Cardiac Cycle**: 0.8 seconds (75 BPM)

**Flow Profile**:
```
Time (s)  | Velocity (m/s) | Phase
----------|----------------|------------------
0.00      | 0.000          | Start
0.12      | 1.156          | Peak Systole ← Maximum
0.20      | 0.674          | Late Systole
0.40      | 0.054          | Diastole ← Minimum
0.60      | 0.087          | Late Diastole
0.80      | 0.025          | End Cycle
```

**Characteristics**:
- Peak systolic velocity: **1.156 m/s** (realistic for ascending aorta)
- Diastolic velocity: **0.025-0.088 m/s**
- Heart rate: **75 BPM**
- Profile type: **Plug flow** (uniform across inlet)

### 3-Element Windkessel Outlets

**Configuration** (`config.json`):
```json
{
  "outlets": {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
      "systolic_pressure": 120,      // mmHg
      "diastolic_pressure": 80,       // mmHg
      "methodology": "murray_law_automatic"
    }
  }
}
```

**How it works**:
1. **Murray's Law** calculates flow split ratios based on outlet diameters
2. **R1, R2, C** parameters computed from systolic/diastolic pressures
3. **Physiologically realistic** pressure-flow relationship at outlets

## Usage Examples

### Example 1: Quick Test (Half Cycle)

```bash
# Run 0.5 cardiac cycles (0.4 seconds)
# Good for quick validation and debugging
./validation/run_realistic_validation.py patient1 \
    --profile sim_laminar_medium \
    --cycles 0.5
```

**Output**: `validation/output_realistic/patient1/sim_laminar_medium/`

**Runtime**: ~2-5 minutes (42k cells)

**Use case**: Test workflow, debug BC setup

### Example 2: Full Cardiac Cycle

```bash
# Run 1 complete cardiac cycle (0.8 seconds)
# Captures full systolic and diastolic phases
./validation/run_realistic_validation.py patient1 \
    --profile sim_laminar_medium \
    --cycles 1.0
```

**Runtime**: ~5-10 minutes (42k cells)

**Use case**: Single-cycle hemodynamic analysis

### Example 3: Multiple Cycles (Convergence)

```bash
# Run 3 cardiac cycles (2.4 seconds)
# Allows flow to reach periodic steady state
./validation/run_realistic_validation.py patient1 \
    --profile sim_rans_medium \
    --cycles 3
```

**Runtime**: ~15-30 minutes (42k cells with RANS)

**Use case**: Ensure periodic convergence, time-averaged results

### Example 4: High-Resolution LES

```bash
# Run LES with fine mesh for detailed turbulence
./validation/run_realistic_validation.py patient1 \
    --profile sim_les_fine \
    --cycles 1
```

**Runtime**: 2-4 hours (184k cells with LES)

**Use case**: Research-grade turbulence analysis

### Example 5: Without WSS (Faster)

```bash
# Disable WSS extraction to save computation time
./validation/run_realistic_validation.py patient1 \
    --profile sim_laminar_medium \
    --cycles 1 \
    --no-wss
```

**Runtime**: Slightly faster than with WSS

**Use case**: When WSS analysis is not needed

## What the Script Does

### Workflow Steps

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Load Configuration                                  │
│  ✓ Patient config.json + simulation profile                 │
│  ✓ Merge pulsatile inlet + 3EWK outlets                     │
│  ✓ Calculate end_time = num_cycles × cardiac_cycle_duration │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2-3: Create Case and Generate Mesh                     │
│  ✓ CreateCaseStructureTask                                  │
│  ✓ GenerateMeshFilesTask (blockMesh, snappyHexMesh dicts)   │
│  ✓ RunMeshGenerationTask (execute OpenFOAM mesh utilities)  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Setup Solver                                        │
│  ✓ fvSchemes, fvSolution, physicalProperties                │
│  ✓ controlDict with correct endTime                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Setup Realistic Boundary Conditions                 │
│  ✓ SetupBoundaryConditionsTask                              │
│  ✓ Pulsatile inlet: timeVaryingMappedFixedValue from CSV    │
│  ✓ 3EWK outlets: windkesselProperties with Murray's Law     │
│  ✓ No-slip walls                                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 6: Enable WSS Calculation                              │
│  ✓ Add wallShearStress function object to controlDict       │
│  ✓ Add fieldMinMax for velocity, pressure, WSS              │
│  ✓ Configure to write at each writeTime                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 7: Run Simulation                                      │
│  ✓ Execute: foamRun                                         │
│  ✓ Log to: log.foamRun                                      │
│  ✓ Monitor convergence                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 8: Extract Results and Validate                        │
│  ✓ Run BC validation script                                 │
│  ✓ Extract WSS statistics                                   │
│  ✓ Validate physical realism                                │
│  ✓ Generate JSON report                                     │
└─────────────────────────────────────────────────────────────┘
```

### Output Files

After successful run:

```
validation/output_realistic/patient1/sim_laminar_medium/
├── 0/                          # Initial conditions
│   ├── U                       # Velocity (will be overwritten by inlet BC)
│   ├── p                       # Pressure
│   └── nut (RANS/LES only)     # Turbulent viscosity
├── 0.01/, 0.02/, ... 0.8/      # Time directories (every writeInterval)
│   ├── U                       # Velocity field
│   ├── p                       # Pressure field
│   ├── phi                     # Face flux
│   ├── wallShearStress         # WSS field ← IMPORTANT
│   └── ...
├── constant/
│   ├── polyMesh/               # Mesh
│   ├── triSurface/             # STL files
│   ├── boundaryData/           # Pulsatile inlet data
│   │   └── inlet/
│   │       ├── points          # Inlet patch points
│   │       ├── 0/U, 0.01/U...  # Time-varying velocities
│   └── windkesselProperties    # 3EWK parameters ← IMPORTANT
├── system/
│   ├── controlDict             # With WSS function objects ← IMPORTANT
│   ├── fvSchemes
│   ├── fvSolution
│   ├── blockMeshDict
│   └── snappyHexMeshDict
├── log.foamRun                 # Simulation log
├── log.blockMesh
├── log.snappyHexMesh
└── postProcessing/             # Function object output
    ├── wallShearStress/
    └── fieldMinMax/
```

## Extracting Wall Shear Stress

### Method 1: From Field Files

**Location**: `<time_dir>/wallShearStress`

**Using ParaView**:
```bash
# Open case in ParaView
paraview --data=validation/output_realistic/patient1/sim_laminar_medium/

# Load wallShearStress field
# Apply Calculator: mag(wallShearStress)
# Color by WSS magnitude
# Export data or screenshots
```

**Using Python (PyFOAM or custom)**:
```python
from pathlib import Path
import numpy as np

# Read wallShearStress field (OpenFOAM binary format)
# For now, use OpenFOAM utilities - see Method 2
```

### Method 2: From Function Object Logs

**Location**: `postProcessing/fieldMinMax/<time>/fieldMinMax.dat`

**Extract WSS statistics**:
```bash
# Get min/max WSS at each time
grep wallShearStress postProcessing/fieldMinMax/*/fieldMinMax.dat

# Example output:
# wallShearStress: min = (0.1 0.05 0.02) max = (5.2 3.1 2.8)
```

### Method 3: Using foamDictionary

```bash
cd validation/output_realistic/patient1/sim_laminar_medium

# Get WSS dimensions
foamDictionary -entry dimensions 0.8/wallShearStress

# Output: [1 -1 -2 0 0 0 0]  (Pa = kg/(m·s²))
```

### Method 4: Programmatic Extraction (Automated)

The `run_realistic_validation.py` script automatically extracts WSS statistics:

```python
wss_stats = {
    "min": 0.5,   # Pa
    "max": 6.5,   # Pa
    "mean": 2.8,  # Pa
    "time": 0.8   # s
}
```

## Interpreting Results

### Pulsatile Flow Validation

**Check**:
1. ✅ Inlet velocity matches CSV profile
2. ✅ Flow accelerates during systole (t=0-0.2s)
3. ✅ Flow decelerates during diastole (t=0.2-0.8s)
4. ✅ Periodic convergence (if multiple cycles)

**Validation**:
```bash
# Check inlet flow rate over time
grep "inlet" postProcessing/surfaceFieldValue/*/surfaceFieldValue.dat

# Should see pulsatile pattern matching CSV
```

### 3EWK Outlet Validation

**Check**:
1. ✅ Flow conservation: sum(outlet_flows) ≈ inlet_flow
2. ✅ Murray's Law ratios applied correctly
3. ✅ Pressure waves realistic (no spurious oscillations)

**Validation**:
```bash
# Check windkesselProperties
cat constant/windkesselProperties

# Should see:
# - flow_split ratios for each outlet
# - R1, R2, C values
# - Computed from Murray's Law
```

### WSS Validation

**Healthy Aorta Ranges** (literature):
- **Ascending aorta**: 1.0 - 7.0 Pa
- **Descending aorta**: 0.5 - 4.0 Pa
- **Branches**: 1.0 - 10.0 Pa (higher in bifurcations)

**Pathological**:
- **High WSS** (>10 Pa): Risk of endothelial damage
- **Low WSS** (<0.5 Pa): Risk of atherosclerosis
- **Oscillatory WSS**: Indicator of disturbed flow

**Our Results Should Show**:
```
Peak Systole (t=0.12s):  WSS = 4-8 Pa   ← Higher
Diastole (t=0.4s):       WSS = 0.5-2 Pa ← Lower
Time-Averaged:           WSS = 2-4 Pa   ← TAWSS
```

## Troubleshooting

### Issue 1: "foamRun not found"

**Problem**: OpenFOAM not in PATH

**Solution**:
```bash
source /opt/openfoam12/etc/bashrc
./validation/run_realistic_validation.py patient1 --profile sim_laminar_medium --cycles 1
```

### Issue 2: "No such file or directory: test_cardio_profile.csv"

**Problem**: Patient CSV file missing or wrong path

**Solution**:
```bash
# Check file exists
ls cases_input/patient1/test_cardio_profile.csv

# Check config.json points to correct file
grep csv_file cases_input/patient1/config.json
```

### Issue 3: Simulation diverges or crashes

**Problem**: Numerical instability with pulsatile flow

**Solutions**:
1. **Reduce time step**:
   - Edit `config.json`: `"initial_deltaT": 1e-4`
   - Or reduce `maxCo` to 0.3

2. **Use more robust solver**:
   - Try `sim_laminar_medium` before `sim_les_fine`
   - RANS/LES need smaller time steps

3. **Check inlet orientation**:
   - Verify inlet normal points INTO domain
   - Check `"orientation": "out"` in config.json

### Issue 4: WSS field not created

**Problem**: wallShearStress function object not working

**Check**:
```bash
# Verify function object in controlDict
grep -A10 "wallShearStress" system/controlDict

# Check OpenFOAM log for errors
grep -i "wallshear\|function" log.foamRun
```

**Solution**:
- Ensure `libs ("libfieldFunctionObjects.so");` is loaded
- Check patch name is correct: `patches (wall_aorta);`

### Issue 5: "Murray's Law failed"

**Problem**: Outlet areas couldn't be calculated

**Check**:
```bash
# Verify outlet STL files exist
ls cases_input/patient1/outlet*.stl

# Check log for geometry errors
grep -i "outlet\|murray" log.foamRun
```

**Solution**:
- Verify outlet STL files are valid
- Check scale_factor in config.json (should be 0.001 for mm→m)

## Advanced Usage

### Custom Cardiac Cycle

Create your own `custom_flow.csv`:
```csv
time,velocity
0.00,0.0
0.10,0.8
0.20,1.2
0.30,0.5
...
```

Update `config.json`:
```json
{
  "inlet": {
    "csv_file": "custom_flow.csv"
  }
}
```

### Multiple Simulation Profiles Comparison

```bash
#!/bin/bash
# Compare laminar vs RANS vs LES

for profile in sim_laminar_medium sim_rans_medium sim_les_medium; do
    echo "Running $profile..."
    ./validation/run_realistic_validation.py patient1 \
        --profile $profile \
        --cycles 1.0
done

# Compare WSS results
python analyze_wss_comparison.py validation/output_realistic/patient1/
```

### Extract Time-Averaged WSS (TAWSS)

```bash
# Use OpenFOAM's temporalAverage function object
# Add to controlDict:

temporalAverageWSS
{
    type            temporalAverage;
    libs            ("libfieldFunctionObjects.so");
    fields          (wallShearStress);
    writeControl    writeTime;
}

# Run simulation
# TAWSS will be in: <time>/temporalAverage(wallShearStress)
```

## References

### Pulsatile Flow
- **Womersley Number**: α = R√(ω/ν), where ω = 2π/T
- **Typical aortic**: α ≈ 10-20
- **Profile**: More plug-like at high α

### 3-Element Windkessel
- **R1** (Proximal resistance): Flow resistance
- **C** (Compliance): Arterial elasticity
- **R2** (Distal resistance): Peripheral resistance
- **Equation**: P(t) = Q(t)×R1 + (1/C)∫Q dt + R2×Q_distal

### Murray's Law
- **Relationship**: D³ ∝ Q (optimal branching)
- **Exponent**: Typically 2.0-3.0 (2.7-3.0 for optimal)
- **Application**: Q_i / Q_total = (D_i / D_ref)^n

### Wall Shear Stress
- **Definition**: τ = μ(∂u/∂y)|wall
- **Units**: Pa (Pascals) = N/m²
- **Physiological**: 1-7 Pa in healthy aorta
- **TAWSS**: Time-averaged over cardiac cycle

## Next Steps

1. ✅ **Run realistic validation** - Complete workflow working
2. ✅ **Extract WSS** - Function objects configured
3. 🔄 **Time-averaged results** - Add temporalAverage
4. 🔄 **OSI calculation** - Oscillatory Shear Index
5. 🔄 **Comparison with literature** - Benchmark against studies

---

**Status**: ✅ Realistic BC Validation Ready
**Documentation**: Complete
**Example**: patient1 with pulsatile flow + 3EWK + WSS
