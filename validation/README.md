# CFD Quality Validation Framework

**Level 1 Validation**: Mesh quality analysis and preprocessing validation (no solver execution required)

---

## Overview

This validation framework tests **CFD quality from a user perspective**:

- ✅ Is the mesh good enough for this solver type?
- ✅ Does the configuration produce acceptable mesh quality?
- ✅ Which config should I choose for my research?
- ✅ How do laminar vs RANS vs LES compare?

**Key Feature**: Tests actual CFD quality metrics (non-orthogonality, skewness, boundary layers) without running full simulations.

---

## Quick Start

### Run Validation Suite

```bash
# Validate all configs for patient1
python validation/run_validation.py patient1

# Validate specific configs
python validation/run_validation.py patient1 --profiles sim_laminar_coarse sim_rans_medium

# Run pytest validation tests
pytest test_cfd_validation.py -v -s
```

### Output

The validation generates:

```
validation/output/patient1/
├── sim_laminar_coarse/          # Generated case directory
│   ├── constant/
│   ├── system/
│   ├── log.checkMesh            # checkMesh output (if available)
│   └── mesh_quality_report.txt  # Quality analysis report
├── sim_laminar_medium/
├── sim_rans_medium/
├── comparison_report.txt         # Side-by-side comparison
└── validation_results.json       # Machine-readable results
```

---

## Validation Tests

### Test Coverage

**6 configuration tests** (in `test_cfd_validation.py`):

1. `test_laminar_coarse_mesh_quality` - Quick low-resolution mesh
2. `test_laminar_medium_mesh_quality` - Balanced production mesh
3. `test_laminar_fine_mesh_quality` - High-resolution detailed mesh
4. `test_rans_coarse_mesh_quality` - Quick turbulence mesh
5. `test_rans_medium_mesh_quality` - Production RANS mesh
6. `test_les_medium_mesh_quality` - High-fidelity LES mesh

**2 comparison tests**:
1. `test_cell_count_increases_with_resolution` - Verify coarse < medium < fine
2. `test_solver_type_reflected_in_config` - Verify config names match solver types

---

## Mesh Quality Criteria

### Quality Metrics Checked

| Metric | Acceptable | Marginal | Poor |
|--------|-----------|----------|------|
| **Non-orthogonality** | < 65° | 65-70° | > 70° |
| **Skewness** | < 3.0 | 3.0-4.0 | > 4.0 |
| **Aspect ratio** (LES) | < 100 | 100-200 | > 200 |
| **Aspect ratio** (RANS/Laminar) | < 1000 | 1000-2000 | > 2000 |
| **Min volume** | > 0 | - | ≤ 0 |
| **Failed cells** | 0 | - | > 0 |

### Solver-Specific Requirements

**Laminar**:
- ✅ Basic quality checks
- ✅ Moderate cell counts
- ✅ No boundary layer requirements

**RANS**:
- ✅ Good quality checks
- ✅ Boundary layers required (≥3 layers)
- ✅ Layer coverage >80%

**LES**:
- ✅ Excellent quality (stricter limits)
- ✅ High cell counts (>100k for patient1)
- ✅ Low aspect ratios (<100)

---

## Example Output

### Individual Quality Report

```
======================================================================
MESH QUALITY REPORT: sim_laminar_medium
======================================================================

MESH STATISTICS:
  Points:                42,156
  Cells:                 38,924
  Faces:                121,004
  Internal Faces:        117,892

QUALITY METRICS:
  Non-orthogonality (max):    52.34  [limit: < 70]
  Skewness (max):              2.18  [limit: < 4.0]
  Aspect ratio (max):        245.3
  Volume (min):            1.23e-12
  Face area (min):         3.45e-08

BOUNDARY LAYER:
  First layer thickness: 0.000250 m
  Expansion ratio:       1.20
  Number of layers:      8
  Coverage:              94.2%

OVERALL RESULT:
  ✅ PASS - Mesh quality acceptable for LAMINAR solver

======================================================================
```

### Comparison Report

```
======================================================================
CFD VALIDATION COMPARISON REPORT
Patient: patient1
Date: 2025-10-02 14:32:15
======================================================================

SUMMARY TABLE:
----------------------------------------------------------------------
Profile                   Solver     Cells       Quality
----------------------------------------------------------------------
sim_laminar_coarse        laminar       12,456   ✅ PASS
sim_laminar_medium        laminar       38,924   ✅ PASS
sim_laminar_fine          laminar      125,678   ✅ PASS
sim_rans_coarse           rans          24,512   ✅ PASS
sim_rans_medium           rans          67,834   ✅ PASS
sim_les_medium            les          245,123   ✅ PASS
----------------------------------------------------------------------

RECOMMENDATIONS:
----------------------------------------------------------------------
✅ 6 configuration(s) passed quality checks:
   - sim_laminar_coarse (laminar)
   - sim_laminar_medium (laminar)
   - sim_laminar_fine (laminar)
   - sim_rans_coarse (rans)
   - sim_rans_medium (rans)
   - sim_les_medium (les)

======================================================================
```

---

## What Gets Validated

### ✅ Level 1 Validation (Current)

**No OpenFOAM solver execution required**

- [x] Case structure creation
- [x] Geometry file copying
- [x] Mesh dictionary generation (blockMesh, snappyHexMesh, surfaceFeatures)
- [x] Mesh quality metrics (if checkMesh available)
- [x] Boundary layer analysis
- [x] Config consistency checks
- [x] Cell count comparisons
- [x] Solver type validation

**Runtime**: ~2-5 minutes per config (fast!)

### ⏭️ Level 2 Validation (Future)

**Requires OpenFOAM + short solver runs**

- [ ] Actual mesh generation (blockMesh + snappyHexMesh execution)
- [ ] checkMesh quality validation
- [ ] Short solver runs (10-50 iterations)
- [ ] Residual convergence analysis
- [ ] Solver stability checks

**Runtime**: ~10-20 minutes per config

### ⏭️ Level 3 Validation (Future)

**Requires full simulation execution**

- [ ] Complete cardiac cycle simulation
- [ ] Post-processing (WSS, pressure, velocity)
- [ ] Physical result validation
- [ ] Murray's Law flow distribution accuracy
- [ ] Publication-quality result comparison

**Runtime**: ~1-4 hours per config

---

## Usage Examples

### Example 1: Test Single Config

```bash
# Run validation tests for just one config
pytest test_cfd_validation.py::TestPatient1MeshQuality::test_laminar_medium_mesh_quality -v -s
```

### Example 2: Compare Laminar Configs

```bash
# Validate only laminar configs
python validation/run_validation.py patient1 --profiles sim_laminar_coarse sim_laminar_medium sim_laminar_fine
```

### Example 3: Quick Quality Check

```bash
# Test if configs generate valid meshes
pytest test_cfd_validation.py::TestConfigurationComparison -v
```

### Example 4: CI/CD Integration

```bash
# Fast validation in CI/CD (pytest only, no checkMesh)
pytest test_cfd_validation.py -v --tb=short
```

---

## Directory Structure

```
validation/
├── README.md                    # This file
├── run_validation.py            # Standalone validation runner
├── analyzers/
│   ├── __init__.py
│   └── mesh_quality_analyzer.py # Mesh quality analysis module
├── configs/                     # (Future) Custom validation configs
└── output/                      # Validation outputs
    └── patient1/
        ├── sim_laminar_coarse/
        ├── sim_laminar_medium/
        ├── comparison_report.txt
        └── validation_results.json
```

---

## API Usage

### Programmatic Validation

```python
from pathlib import Path
from validation.analyzers import analyze_mesh_quality

# Analyze mesh quality for a case
case_dir = Path("output/patient1_laminar_medium")
metrics, passed, issues = analyze_mesh_quality(case_dir, solver_type="laminar")

print(f"Cells: {metrics.num_cells:,}")
print(f"Non-orthogonality: {metrics.max_non_orthogonality:.2f}")
print(f"Quality: {'✅ PASS' if passed else '❌ FAIL'}")

if issues:
    print("Issues:")
    for issue in issues:
        print(f"  - {issue}")
```

### Generate Quality Report

```python
from validation.analyzers import MeshQualityAnalyzer

analyzer = MeshQualityAnalyzer(case_dir)
report = analyzer.generate_quality_report(solver_type="rans")
print(report)
```

---

## Integration with CI/CD

The validation tests run automatically in GitHub Actions:

```yaml
# In .github/workflows/tests.yml
- name: Run CFD validation tests
  run: |
    pytest test_cfd_validation.py -v --tb=short
```

**Benefits**:
- ✅ Catch mesh quality regressions automatically
- ✅ Ensure all configs produce valid meshes
- ✅ Validate config changes before merging
- ✅ Fast (~5-10 min total for all configs)

---

## User Perspective: Choosing a Config

### "Which config should I use?"

**For quick prototyping**:
→ `sim_laminar_coarse` (fastest, lowest resolution)

**For production laminar simulations**:
→ `sim_laminar_medium` (balanced quality/speed)

**For detailed laminar analysis**:
→ `sim_laminar_fine` (highest resolution, publication-ready)

**For turbulent flow (Re > 2300)**:
→ `sim_rans_medium` (production RANS with boundary layers)

**For research/high-fidelity turbulence**:
→ `sim_les_medium` (wall-resolved LES, most accurate)

### "How do I know the mesh is good enough?"

Run validation:
```bash
pytest test_cfd_validation.py::TestPatient1MeshQuality::test_laminar_medium_mesh_quality -v -s
```

Look for:
- ✅ `PASS` in quality report
- ✅ Non-orthogonality < 70°
- ✅ No failed cells
- ✅ Boundary layers present (for RANS/LES)

---

## Troubleshooting

### "checkMesh not found"

The validation works even without OpenFOAM installed:
- ✅ Mesh files are generated
- ✅ Config validation passes
- ⚠️ Quality metrics skipped (checkMesh unavailable)

To enable full validation:
```bash
# Source OpenFOAM
source /opt/openfoam12/etc/bashrc
pytest test_cfd_validation.py -v -s
```

### "Mesh quality failed"

If tests fail with quality issues:

1. **Check which metric failed**:
   ```
   - Non-orthogonality 75.2 > 70 (poor quality)
   ```

2. **Adjust mesh parameters** in profile:
   ```python
   # In src/config/profiles/sim_laminar_medium.py
   "target_cell_size_mm": 2.0  # Increase for better quality
   ```

3. **Re-run validation**:
   ```bash
   pytest test_cfd_validation.py -v -s
   ```

### "Tests too slow"

To run only essential tests:
```bash
# Test just one config
pytest test_cfd_validation.py -k "test_laminar_medium" -v

# Skip quality analysis (fast config validation only)
pytest test_cfd_validation.py::TestConfigurationComparison -v
```

---

## Future Enhancements

### Planned Features

- [ ] **Level 2 validation** with actual mesh generation
- [ ] **Mesh convergence study** (coarse → medium → fine)
- [ ] **y+ validation** for RANS/LES (requires solver)
- [ ] **Performance benchmarking** (mesh time, memory usage)
- [ ] **Multi-patient comparison** (patient1 vs patient2 mesh quality)
- [ ] **Custom quality criteria** (user-defined thresholds)
- [ ] **HTML reports** with visualizations
- [ ] **Automatic mesh optimization** suggestions

---

## References

### OpenFOAM Mesh Quality Guidelines

- **Non-orthogonality**: https://www.openfoam.com/documentation/user-guide/4-mesh-generation-and-conversion/4.4-mesh-quality
- **Mesh checks**: `checkMesh -help`
- **snappyHexMesh**: https://doc.cfd.direct/openfoam/user-guide-v12/snappyhexmesh

### CFD Best Practices

- **RANS y+ requirements**: 30 < y+ < 300 (wall functions) or y+ < 1 (low-Re)
- **LES y+ requirements**: y+ < 1 (wall-resolved)
- **Aspect ratio**: < 100 for LES, < 1000 for RANS/laminar

---

## Contributing

To add new validation tests:

1. Add test method to `test_cfd_validation.py`
2. Follow naming convention: `test_<solver>_<resolution>_<aspect>`
3. Use `_run_preprocessing()` helper for setup
4. Assert CFD quality criteria with clear error messages
5. Add docstring explaining user perspective

Example:
```python
def test_rans_fine_mesh_quality(self):
    """
    Validate high-resolution RANS mesh.

    User perspective: "I want publication-quality RANS results."
    CFD expectation: Excellent quality, fine boundary layers, y+ < 1.
    """
    case_dir = self._run_preprocessing("sim_rans_fine")
    # ... assertions ...
```

---

## Summary

**What this framework provides**:

✅ **Fast validation** (~2-5 min per config)
✅ **CFD quality metrics** (non-orthogonality, skewness, etc.)
✅ **User perspective** (which config for my research?)
✅ **Automated testing** (CI/CD integration)
✅ **No solver required** (Level 1 validation)
✅ **Comparison reports** (side-by-side config analysis)

**Perfect for**:
- 👨‍🔬 Researchers choosing simulation configs
- 🔧 Developers testing mesh generation changes
- 📊 Quality assurance before running expensive simulations
- 📈 Comparing different solver/resolution trade-offs
