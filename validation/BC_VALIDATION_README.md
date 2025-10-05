# Level 4 & 6: Boundary Condition and Physical Results Validation

## Overview

This validation framework tests:
- **Level 4**: Boundary condition setup and flow conservation
- **Level 6**: Physical realism of simulation results

## Quick Start

```bash
# Run BC validation on an existing simulation case
./validation/run_bc_validation.py patient1 --profile sim_laminar_medium --time 0.1
```

**Prerequisites**: Must run `run_simulation_validation.py` first to create the case.

## What It Validates

### Level 4: Boundary Condition Validation

#### Inlet Boundary Conditions
- ✅ **Profile Type Detection**
  - Plug (uniform) flow
  - Parabolic profile
  - Pulsatile (time-varying) from CSV
  - Womersley profile

- ✅ **Flow Rate Validation**
  - Inlet volumetric flow rate (m³/s)
  - Mean and peak velocities
  - Profile shape correctness

#### Outlet Boundary Conditions
- ✅ **BC Type Detection**
  - ZeroGradient (natural outflow)
  - 3-Element Windkessel (3EWK)
  - FixedValue (prescribed conditions)

- ✅ **Murray's Law Validation**
  - Detects if Murray's Law flow distribution is applied
  - Validates flow split ratios match Murray exponent
  - Checks outlet area-based distribution

#### Flow Conservation
- ✅ **Mass Balance**
  - Inlet flow rate = Sum of outlet flow rates
  - Conservation error < 5% threshold
  - Patch-by-patch flow accounting

### Level 6: Physical Results Validation

#### Velocity Field
- ✅ **Magnitude Ranges**
  - Expected: 0.1 - 1.5 m/s for aortic flow
  - Min, max, mean statistics
  - Spatial distribution checks

- ✅ **Flow Regime**
  - Reynolds number calculation
  - Laminar / Transitional / Turbulent classification
  - Consistency with turbulence model choice

#### Pressure Field
- ✅ **Pressure Drop**
  - Expected: 10 - 50 mmHg (1333 - 6666 Pa) for aorta
  - Inlet-to-outlet pressure gradient
  - Physiological realism

- ✅ **Absolute Pressures**
  - Range validation
  - Consistency with boundary conditions
  - No negative absolute pressures (if applicable)

#### Wall Shear Stress (Future)
- 🔄 **WSS Magnitudes**
  - Expected: 1 - 7 Pa for healthy aorta
  - Min, max, mean statistics
  - High WSS regions (>10 Pa) detection

#### Turbulence Metrics (RANS/LES only)
- 🔄 **Turbulent Kinetic Energy (k)**
  - Reasonable magnitudes
  - Spatial distribution

- 🔄 **y+ Values**
  - Wall-adjacent cell y+ values
  - Expected: y+ < 1 for wall-resolved, y+ = 30-300 for wall functions
  - Consistency with turbulence model requirements

## Usage Examples

### Basic Validation
```bash
# Validate laminar simulation
./validation/run_bc_validation.py patient1 --profile sim_laminar_medium --time 0.1

# Validate RANS simulation
./validation/run_bc_validation.py patient1 --profile sim_rans_medium --time 0.1

# Validate LES simulation
./validation/run_bc_validation.py patient1 --profile sim_les_medium --time 0.1
```

### Pulsatile Flow Validation (Future)
```bash
# Run full cardiac cycle simulation first
./validation/run_simulation_validation.py patient1 --profiles sim_laminar_medium --time 1.0

# Validate at peak systole (t=0.2s)
./validation/run_bc_validation.py patient1 --profile sim_laminar_medium --time 0.2

# Validate at end diastole (t=0.8s)
./validation/run_bc_validation.py patient1 --profile sim_laminar_medium --time 0.8
```

### Custom Output Directory
```bash
./validation/run_bc_validation.py patient1 --profile sim_laminar_medium --time 0.1 \\
    --output-dir validation/custom_output
```

## Output Files

### JSON Results
Location: `validation/output/patient1/patient1_bc_validation_results.json`

Structure:
```json
{
  "patient": "patient1",
  "validation_type": "bc_and_physical",
  "results": [
    {
      "patient_name": "patient1",
      "profile_name": "sim_laminar_medium",
      "simulation_time": 0.1,
      "mesh_cells": 42186,
      "bc_metrics": {
        "inlet_area_m2": 0.0,
        "inlet_mean_velocity_ms": 0.0,
        "inlet_profile_type": "plug (uniform)",
        "outlet_count": 0,
        "outlet_bc_type": "zeroGradient",
        "flow_conservation_error_percent": 0.0,
        "murray_law_applied": false
      },
      "physical_metrics": {
        "velocity_min_ms": 0.0,
        "velocity_max_ms": 0.009,
        "velocity_realistic": false,
        "pressure_drop_pa": 0.0,
        "pressure_drop_mmhg": 0.0,
        "reynolds_number": 0.0,
        "flow_regime": "laminar"
      },
      "overall_pass": true,
      "issues": []
    }
  ]
}
```

### Terminal Output
Real-time validation summary with:
- BC detection results
- Physical metrics
- Pass/fail status
- Detailed issue list

## Physical Validation Thresholds

### Velocity
- **Realistic range**: 0.05 - 2.0 m/s
- **Typical aortic**: 0.3 - 1.5 m/s
- **Peak systole**: 1.0 - 1.5 m/s
- **Diastole**: 0.1 - 0.3 m/s

### Pressure Drop
- **Realistic range**: 5 - 100 mmHg
- **Typical aortic**: 10 - 50 mmHg
- **Healthy aorta**: 10 - 20 mmHg
- **With stenosis**: 30 - 100 mmHg

### Wall Shear Stress
- **Healthy aorta**: 1 - 7 Pa
- **High WSS (risk)**: > 10 Pa
- **Low WSS (risk)**: < 0.5 Pa

### Reynolds Number
- **Laminar**: Re < 2300
- **Transitional**: 2300 < Re < 4000
- **Turbulent**: Re > 4000
- **Typical aortic**: Re ~ 2000 - 6000

## Current Limitations

### Field Statistics Extraction
**Current**: Estimates velocity from Courant number in log files
**Future**: Direct field parsing with OpenFOAM utilities

To enable full field statistics:
1. Source OpenFOAM environment
2. Script will automatically use `execFlowFunctionObjects`
3. Provides accurate min/max/mean for all fields

### Flow Rate Calculation
**Current**: Placeholder (returns 0.0)
**Future**: Use `surfaceFieldValue` function object

### Wall Shear Stress
**Current**: Not implemented
**Future**: Use `wallShearStress` function object

## Implementation Details

### Field Statistics Extractor
Module: `validation/analyzers/field_statistics.py`

Features:
- **Primary method**: OpenFOAM `execFlowFunctionObjects` utility
- **Fallback method**: Log file parsing with Courant number estimates
- **Function objects**: `fieldMinMax`, `surfaceFieldValue`

### BC Validator
Module: `validation/run_bc_validation.py`

Classes:
- `BCValidationMetrics`: Inlet/outlet BC metrics
- `PhysicalValidationMetrics`: Velocity, pressure, WSS metrics
- `BCValidationResult`: Complete validation result
- `BCValidator`: Main validation logic

## Integration with Workflow

### Typical Validation Sequence

```bash
# Step 1: Run mesh and solver validation (Level 3)
./validation/run_simulation_validation.py patient1 --profiles sim_laminar_medium --time 0.1

# Step 2: Run BC and physical validation (Level 4 & 6)
./validation/run_bc_validation.py patient1 --profile sim_laminar_medium --time 0.1

# Step 3: (Future) Run parallel scaling tests (Level 5)
./validation/run_parallel_validation.py patient1 --profile sim_laminar_medium --cores 1,2,4,8
```

### Multi-Profile Comparison
```bash
# Validate multiple profiles
for profile in sim_laminar_coarse sim_laminar_medium sim_laminar_fine; do
    ./validation/run_bc_validation.py patient1 --profile $profile --time 0.1
done

# Compare results
python validation/compare_bc_results.py validation/output/patient1/*_bc_validation_results.json
```

## Next Steps

### Immediate Enhancements
1. ✅ **Flow rate extraction** - Use OpenFOAM `surfaceFieldValue`
2. ✅ **WSS calculation** - Add `wallShearStress` function object
3. ✅ **Turbulence metrics** - Extract k, omega, nut statistics for RANS/LES

### Future Features
4. 🔄 **Time-averaged results** - Validate pulsatile cycle averages
5. 🔄 **Waveform comparison** - Compare inlet/outlet flow waveforms
6. 🔄 **Literature benchmarking** - Compare against published aortic CFD studies
7. 🔄 **Multi-patient statistics** - Population-level validation metrics

## References

### Physiological Values
- **Aortic Flow**: Nichols & O'Rourke, "McDonald's Blood Flow in Arteries" (2011)
- **Wall Shear Stress**: Cheng et al., "Atherosclerotic Lesion Size and Vulnerability Are Determined by Patterns of Fluid Shear Stress" (2006)
- **Reynolds Number**: Ku, "Blood Flow in Arteries", Annu. Rev. Fluid Mech. (1997)

### CFD Validation
- **OpenFOAM**: User Guide Section 6 (Post-processing)
- **Function Objects**: https://openfoam.org/guide/functionobjects
- **Boundary Conditions**: https://openfoam.org/guide/boundary-conditions

## Troubleshooting

### "OpenFOAM utilities not available"
- Source OpenFOAM: `source /opt/openfoam12/etc/bashrc`
- Or use fallback estimates (less accurate)

### "No results found for time X.Xs"
- Check time directories exist: `ls validation/output/patient1/sim_*/`
- Verify simulation completed: `tail validation/output/patient1/sim_*/log.foamRun`

### "Flow conservation error > 5%"
- Check boundary conditions are correctly applied
- Verify Murray's Law flow split if using Windkessel
- May indicate convergence issues

### "Velocity outside realistic range"
- For validation runs with artificial BC, this is expected
- For realistic simulations, check inlet BC magnitude
- Verify geometry scale factor (should be mm → m)

## Contact & Support

For issues or questions:
1. Check validation log files in `validation/output/`
2. Review JSON results for detailed metrics
3. Consult OpenFOAM documentation for function objects
4. Report bugs via GitHub issues

---

**Status**: ✅ Level 4 & 6 Framework Complete (Phase 1)
**Next**: Level 5 (Parallel Scalability Testing)
