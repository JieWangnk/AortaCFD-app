# Regenerate Numerics - Practical Example

## Quick Reference

```bash
# Step 1: Create case and generate mesh
python run_patient.py BPM120 --steps case,mesh

# Step 2: Regenerate numerics with mesh-adaptive adjustments
python run_patient.py BPM120 --steps regenerate-numerics

# Step 3: Continue with simulation
python run_patient.py BPM120 --steps boundary,solver
```

## BPM120 Case Study - Before and After

### Problem

BPM120 case with fine mesh (3.1M cells) was stuck in convergence:
- 40+ PIMPLE iterations per time step
- Poor convergence behavior
- User had manually tightened tolerances thinking "more cells = tighter settings"

**Actual problem**: Fine mesh had WORSE quality than coarse mesh!
- Fine mesh: skewness 5.16, non-orthogonality 68.3°
- Coarse mesh: skewness 2.96, non-orthogonality 65°

### Solution: Mesh-Adaptive System

The counter-intuitive truth: **Poor mesh needs LOOSER settings, not tighter**.

#### Step-by-Step Fix

1. **Generate mesh normally**:
```bash
python run_patient.py BPM120 --config cases_input/BPM120/config_mesh_fine.json \
    --steps case,mesh
```

2. **Regenerate numerics** (activates mesh-adaptive system):
```bash
python run_patient.py BPM120 --steps regenerate-numerics
```

3. **Review quality report** in terminal output:
```
═══════════════════════════════════════════════════════════════
MESH-ADAPTIVE SOLVER SETTINGS
═══════════════════════════════════════════════════════════════
Mesh Quality Analysis:
  • Skewness: 5.16 (POOR - threshold 6.0)
  • Non-orthogonality: 68.3° (FAIR - threshold 70°)
  • Quality Tier: POOR

Adjustments Applied:
  • nOuterCorrectors: 2 → 4
  • nNonOrthogonalCorrectors: 2 → 4
  • Pressure relaxation: 0.3 → 0.2
  • Laplacian scheme: limited corrected 0.33
═══════════════════════════════════════════════════════════════
```

4. **Run simulation**:
```bash
python run_patient.py BPM120 --steps boundary,solver
```

#### Expected Results

**Before mesh-adaptive adjustments**:
```
PIMPLE: iteration 1
    Initial residual: 2.1e-3
PIMPLE: iteration 10
    Initial residual: 1.8e-3
PIMPLE: iteration 20
    Initial residual: 1.5e-3
... [stuck, not converging]
PIMPLE: iteration 40+
```

**After mesh-adaptive adjustments**:
```
PIMPLE: iteration 1
    Initial residual: 2.1e-3
PIMPLE: iteration 2
    Initial residual: 5.2e-4
PIMPLE: iteration 3
    Initial residual: 1.1e-4
PIMPLE: iteration 4
    Initial residual: 8.3e-6  [CONVERGED]
```

## Comparison: Coarse vs Fine Mesh

### Coarse Mesh (174k cells)

```bash
python run_patient.py BPM120 --config cases_input/BPM120/config_mesh_coarse.json \
    --steps case,mesh,regenerate-numerics
```

**Quality Report**:
```
Mesh Quality Analysis:
  • Skewness: 2.96 (GOOD)
  • Non-orthogonality: 65° (GOOD)
  • Quality Tier: GOOD

Adjustments Applied:
  • Minor non-orthogonal corrector adjustment: 2 → 3
  • No other adjustments needed
```

**Convergence**: 3 PIMPLE iterations (excellent!)

### Fine Mesh (3.1M cells)

```bash
python run_patient.py BPM120 --config cases_input/BPM120/config_mesh_fine.json \
    --steps case,mesh,regenerate-numerics
```

**Quality Report**:
```
Mesh Quality Analysis:
  • Skewness: 5.16 (POOR)
  • Non-orthogonality: 68.3° (FAIR)
  • Quality Tier: POOR

 MESH QUALITY WARNING 
[Detailed warnings about accuracy impacts]

Adjustments Applied:
  • nOuterCorrectors: 2 → 4
  • nNonOrthogonalCorrectors: 2 → 4
  • Pressure relaxation: 0.3 → 0.2
  • Laplacian scheme: limited corrected 0.33
```

**Convergence**: 4-5 PIMPLE iterations (acceptable with warnings)

## Workflow Integration Examples

### Example 1: Test Multiple Mesh Levels

```bash
#!/bin/bash
# Test mesh convergence with automatic adaptation

for level in coarse medium fine; do
    echo "=== Testing $level mesh ==="

    # Generate case and mesh
    python run_patient.py BPM120 \
        --config cases_input/BPM120/config_mesh_$level.json \
        --steps case,mesh

    # Apply mesh-adaptive adjustments
    python run_patient.py BPM120 --steps regenerate-numerics

    # Run simulation
    python run_patient.py BPM120 --steps boundary,solver

    # Extract results
    echo "Completed $level mesh"
done

# Compare results and calculate GCI
python scripts/calculate_gci.py
```

### Example 2: Update Existing Case

If you have an old case with mesh already generated:

```bash
# Point to existing case directory
python run_patient.py BPM120 --update output/BPM120/run_xxx \
  --steps regenerate-numerics
```

This will:
1. Read existing `logs/log.checkMesh`
2. Analyze mesh quality
3. Regenerate `system/fvSchemes` and `system/fvSolution` with appropriate adjustments
4. Print quality report

### Example 3: Iterative Mesh Improvement

```bash
#!/bin/bash
# Iteratively improve mesh quality

iteration=1
max_skewness=10.0

while (( $(echo "$max_skewness > 3.0" | bc -l) )); do
    echo "=== Mesh iteration $iteration ==="

    # Adjust snappyHexMesh settings
    python scripts/adjust_snappy_settings.py --iteration $iteration

    # Generate mesh
    python run_patient.py BPM120 --steps case,mesh

    # Analyze with mesh-adaptive system
    python run_patient.py BPM120 --steps regenerate-numerics

    # Extract skewness from log
    max_skewness=$(grep "Max skewness" logs/log.checkMesh | awk '{print $4}')

    echo "Current max skewness: $max_skewness"
    iteration=$((iteration + 1))

    if [ $iteration -gt 5 ]; then
        echo "Max iterations reached. Review geometry or meshing strategy."
        break
    fi
done
```

## Configuration Examples

### Example 1: Disable Mesh-Adaptive System

If you want manual control:

**config.json**:
```json
{
  "geometry": {
    "case_name": "BPM120",
    "refinement_level": "medium"
  },
  "physics": {
    "model": "laminar"
  },
  "numerics": {
    "profile": "standard",
    "mesh_adaptive": false,
    "correctors": {
      "nOuterCorrectors": 2,
      "nCorrectors": 2,
      "nNonOrthogonalCorrectors": 3
    }
  }
}
```

### Example 2: Override Specific Settings

Let mesh-adaptive system adjust most settings, but override specific values:

**config.json**:
```json
{
  "numerics": {
    "profile": "standard",
    "mesh_adaptive": true,
    "correctors": {
      "nOuterCorrectors": 3
    },
    "under_relaxation": {
      "p": 0.25
    }
  }
}
```

The system will:
1. Apply mesh-adaptive adjustments
2. Override `nOuterCorrectors` to 3 (ignoring adaptive value)
3. Override pressure relaxation to 0.25 (ignoring adaptive value)
4. Keep all other adaptive adjustments

### Example 3: Profile Switching Based on Quality

Use robust profile for poor meshes:

**config_robust.json**:
```json
{
  "numerics": {
    "profile": "robust",
    "mesh_adaptive": true
  }
}
```

If mesh quality is POOR/CRITICAL:
- Start with `robust` profile (1st order, maximum stability)
- Mesh-adaptive system applies additional stabilization
- Simulation should converge, but with reduced accuracy

## Interpreting Results

### Check System/FvSchemes Changes

**Before regenerate-numerics** (`system/fvSchemes`):
```c++
laplacianSchemes
{
    default         Gauss linear corrected;
}
```

**After regenerate-numerics** (POOR quality mesh):
```c++
laplacianSchemes
{
    default         Gauss linear limited corrected 0.33;
}
```

### Check System/FvSolution Changes

**Before regenerate-numerics** (`system/fvSolution`):
```c++
PIMPLE
{
    nOuterCorrectors         2;
    nCorrectors              2;
    nNonOrthogonalCorrectors 2;
}

relaxationFactors
{
    fields
    {
        p               0.3;
    }
}
```

**After regenerate-numerics** (POOR quality mesh):
```c++
PIMPLE
{
    nOuterCorrectors         4;  // +2 for POOR mesh
    nCorrectors              2;
    nNonOrthogonalCorrectors 4;  // Scaled with ortho 68°
}

relaxationFactors
{
    fields
    {
        p               0.2;  // Stronger relaxation
    }
}
```

## Troubleshooting

### Issue: "No adjustments applied"

**Diagnosis**: Mesh quality is GOOD or EXCELLENT.

**Action**: This is actually good news! Your mesh is high quality and doesn't need stabilization adjustments. Continue with simulation.

### Issue: Still Not Converging

**Diagnosis**: Check quality tier in report. If CRITICAL:

**Action**:
1. **REMESH** - adaptive system cannot fix fundamentally poor mesh
2. Try these snappyHexMesh improvements:
   - Reduce surface refinement levels
   - Increase feature angle (60° → 90°)
   - Reduce boundary layers (5 → 3)
   - Increase minThickness (0.05 → 0.1)

### Issue: Results Don't Match Reference

**Diagnosis**: If using POOR mesh with strong stabilization:

**Action**: You're experiencing numerical diffusion trade-off:
- Wall shear stress under-predicted by 10-30%
- Pressure drops inaccurate by 5-15%
- **Must REMESH for accurate results**

See [MESH_QUALITY_WARNINGS.md](../docs/MESH_QUALITY_WARNINGS.md) for details.

## Key Takeaways

1. **Run regenerate-numerics AFTER meshing** to activate adaptive system
2. **Poor mesh needs LOOSER settings**, not tighter (counter-intuitive!)
3. **Adaptive system is safety net**, not license for poor meshes
4. **Always verify grid convergence** with GCI studies
5. **Remesh if quality is poor** - don't rely on stabilization for production

## Further Reading

- [REGENERATE_NUMERICS_USAGE.md](../docs/_internal/REGENERATE_NUMERICS_USAGE.md) - Complete usage guide
- [MESH_QUALITY_WARNINGS.md](../docs/MESH_QUALITY_WARNINGS.md) - Critical warnings
- [MESH_ADAPTIVE_SOLVER_SYSTEM.md](../docs/MESH_ADAPTIVE_SOLVER_SYSTEM.md) - Technical details
- [MESH_ADAPTIVE_INTEGRATION.md](../docs/MESH_ADAPTIVE_INTEGRATION.md) - Integration guide
