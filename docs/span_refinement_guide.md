# Span-Based Refinement for Aortic Coarctation

## Overview

Span-based refinement ensures adequate mesh resolution across narrow vessel regions, critical for aortic coarctation simulations where accurate pressure gradient calculation is essential.

## Features Implemented

### 1. Closeness Calculation
- **Template**: `surfaceFeaturesDict.tpl`
- **Purpose**: Calculates distance fields for span-based refinement
- **Activation**: Set `span_refinement_enabled: true` in mesh settings

### 2. Span-Based Refinement Regions
- **Template**: `snappyHexMeshDict.tpl`
- **Purpose**: Guarantees minimum cells across vessel diameter
- **Mode**: `insideSpan` for internal flow regions

### 3. Coarctation Configuration
- **File**: `boundary_conditions_coarctation.json`
- **Purpose**: Complete setup for coarctation analysis
- **Features**: High-resolution mesh + Research-based Windkessel

## Configuration Parameters

### Mesh Settings
```json
"mesh": {
  "SNAPPY_SETTINGS": {
    "span_refinement_enabled": true,        // Enable span refinement
    "span_refinement_distance": 500,        // Max distance from wall (in mesh units)
    "span_refinement_level": 3,             // Refinement level (0-4)
    "cells_across_span": 30,                // Minimum cells across diameter
    "surfaceRefinementLevels": [3, 4],      // Higher surface resolution
    "resolveFeatureAngle": 20               // Capture fine geometric features
  }
}
```

## Clinical Benefits

### For Coarctation Analysis
1. **Pressure Gradient**: Accurate ΔP across stenosis
2. **Velocity Jets**: High-resolution flow acceleration
3. **Wall Shear Stress**: Precise WSS calculation
4. **Flow Patterns**: Post-stenotic recirculation
5. **Turbulence**: Transitional flow capture

### Recommended Settings by Stenosis Severity

#### Mild Coarctation (50-70% stenosis)
- `cells_across_span`: 20
- `span_refinement_level`: 2
- `surfaceRefinementLevels`: [2, 3]

#### Moderate Coarctation (70-85% stenosis)  
- `cells_across_span`: 30
- `span_refinement_level`: 3
- `surfaceRefinementLevels`: [3, 4]

#### Severe Coarctation (>85% stenosis)
- `cells_across_span`: 40
- `span_refinement_level`: 4
- `surfaceRefinementLevels`: [4, 5]

## Usage

### 1. Enable Span Refinement
```bash
# Copy coarctation template
cp data/CAD/PAT1_2024/boundary_conditions_coarctation.json data/CAD/PAT1_2024/boundary_conditions.json

# Run simulation with span refinement
python app.py runAll --case PAT1_2024 --profile sim_laminar_fine --openfoam-version 12
```

### 2. Monitor Mesh Quality
```bash
# Check mesh statistics
tail logs/log.checkMesh

# Verify span refinement worked
grep -i "span" logs/log.snappyHexMesh
```

### 3. Post-Processing Focus Areas
- **Pressure**: Monitor pressure drop across coarctation
- **Velocity**: Track jet velocities and acceleration
- **WSS**: Analyze wall shear stress patterns
- **Turbulence**: Check for flow instabilities

## Expected Mesh Characteristics

### Cell Count Impact
- **Standard mesh**: ~2M cells
- **With span refinement**: ~8-15M cells
- **Computational cost**: 3-5x increase
- **Accuracy gain**: Significant for pressure gradients

### Quality Metrics
- **Aspect Ratio**: <10 in refined regions
- **Skewness**: <0.8 near stenosis
- **Non-orthogonality**: <70°

## Clinical Validation

### Key Metrics to Validate
1. **Peak Velocity**: Compare with Doppler ultrasound
2. **Pressure Gradient**: Validate against catheterization
3. **Flow Patterns**: Match with 4D Flow MRI
4. **WSS Distribution**: Correlate with known patterns

### Typical Coarctation Results
- **Peak velocity**: 3-6 m/s (severe cases)
- **Pressure drop**: 20-80 mmHg
- **Jet angle**: 15-30° post-stenosis
- **Recirculation length**: 2-5 diameters

## Troubleshooting

### Common Issues
1. **Mesh too coarse**: Increase `cells_across_span`
2. **Convergence problems**: Reduce time step
3. **Memory issues**: Reduce `maxGlobalCells`
4. **Long runtime**: Use parallel processing

### Performance Tips
1. **Use parallel meshing**: Enable in SNAPPY_SETTINGS
2. **Optimize cell count**: Balance accuracy vs. speed
3. **Monitor convergence**: Check residuals frequently
4. **Use adaptive time stepping**: For stability

## Research Applications

This implementation enables:
- **Clinical studies**: Patient-specific coarctation analysis
- **Device testing**: Stent/balloon optimization
- **Surgical planning**: Pre-operative flow assessment
- **Hemodynamics research**: Fundamental flow studies

## References

Based on OpenFOAM User Guide span-based refinement methodology and cardiovascular CFD best practices.