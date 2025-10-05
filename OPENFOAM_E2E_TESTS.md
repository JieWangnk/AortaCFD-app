# OpenFOAM E2E Tests - Quick Start Guide

Complete End-to-End testing with **OpenFOAM mesh generation and solver execution**.

---

## Overview

The E2E test suite now includes **3 new OpenFOAM execution tests**:

1. **Test 08: Mesh Execution** - Runs blockMesh, surfaceFeatures, snappyHexMesh, checkMesh
2. **Test 09: Solver Execution** - Runs foamRun for 0.01s test simulation
3. **Test 10: Result Validation** - Extracts flow rates and validates conservation

**Total Tests**: 13 tests (10 setup + 3 OpenFOAM execution)

---

## Prerequisites

### 1. OpenFOAM 12 Installation

```bash
# Check if OpenFOAM is installed
which blockMesh

# If not found, install OpenFOAM 12
# On Ubuntu:
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key | apt-key add -"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt-get update
sudo apt-get install openfoam12

# Verify installation
source /opt/openfoam12/etc/bashrc
which blockMesh
# Should return: /opt/openfoam12/platforms/linux64GccDPInt32Opt/bin/blockMesh
```

### 2. Python Environment

```bash
# Activate your virtual environment
source venv/bin/activate  # or ./venv/bin/activate

# Ensure pytest is installed
pip install pytest pytest-cov
```

---

## Running the Tests

### Option 1: Run ALL Tests (Setup + OpenFOAM)

**IMPORTANT**: Source OpenFOAM before running!

```bash
# 1. Source OpenFOAM environment
source /opt/openfoam12/etc/bashrc

# 2. Run complete E2E test
./venv/bin/pytest tests/integration/test_patient1_complete.py -v -s

# Expected time: 5-10 minutes total
# - Setup tests (1-7): ~5 seconds
# - Mesh generation (8): 2-5 minutes
# - Solver execution (9): 1-3 minutes
# - Result validation (10): 30 seconds
# - Geometry/Flow split (11-12): 2 seconds
# - Summary (13): 1 second
```

### Option 2: Run ONLY OpenFOAM Tests

If you've already run setup tests and just want to test OpenFOAM:

```bash
# Source OpenFOAM
source /opt/openfoam12/etc/bashrc

# Run only tests marked as requires_openfoam
./venv/bin/pytest tests/integration/test_patient1_complete.py -v -s -m requires_openfoam

# This runs tests 8, 9, 10 only
```

### Option 3: Run ONLY Setup Tests (No OpenFOAM)

If you don't have OpenFOAM or want to skip execution tests:

```bash
# Run all tests EXCEPT OpenFOAM tests
./venv/bin/pytest tests/integration/test_patient1_complete.py -v -s -m "not requires_openfoam"

# This runs tests 1-7, 11-13 (skips 8, 9, 10)
```

### Option 4: Run Individual Tests

```bash
# Run just mesh generation
./venv/bin/pytest tests/integration/test_patient1_complete.py::TestPatient1CompleteWorkflow::test_08_mesh_execution -v -s

# Run just solver execution
./venv/bin/pytest tests/integration/test_patient1_complete.py::TestPatient1CompleteWorkflow::test_09_solver_execution_short -v -s

# Run just result validation
./venv/bin/pytest tests/integration/test_patient1_complete.py::TestPatient1CompleteWorkflow::test_10_result_validation -v -s

# Run summary to see overall status
./venv/bin/pytest tests/integration/test_patient1_complete.py::TestPatient1CompleteWorkflow::test_13_summary -v -s
```

---

## Expected Output

### Successful Run (with OpenFOAM)

```
tests/integration/test_patient1_complete.py::TestPatient1CompleteWorkflow::test_01_config_loading
✅ Config loaded: patient1 / sim_laminar_medium
PASSED

tests/integration/test_patient1_complete.py::TestPatient1CompleteWorkflow::test_02_case_structure_creation
✅ Case structure created: 6 STL files
PASSED

... (tests 3-7)

tests/integration/test_patient1_complete.py::TestPatient1CompleteWorkflow::test_08_mesh_execution

======================================================================
MESH GENERATION (OpenFOAM)
======================================================================

🔧 Step 1: Running blockMesh...
   This creates the background hexahedral mesh
   ✅ blockMesh completed - background mesh created

🔧 Step 2: Running surfaceFeatures...
   This extracts edges and features from STL files
   ✅ surfaceFeatures completed

🔧 Step 3: Running snappyHexMesh...
   This refines mesh around geometry and creates boundary layers
   ⏱️  This may take 2-5 minutes for patient1...
   ✅ snappyHexMesh completed

🔧 Step 4: Running checkMesh...
   This validates mesh quality

📊 Mesh statistics:
   Cells:  1,234,567
   Points: 456,789
   Faces:  3,456,789
   ✅ Mesh quality: PASS

======================================================================
✅ MESH GENERATION COMPLETE
======================================================================
PASSED

tests/integration/test_patient1_complete.py::TestPatient1CompleteWorkflow::test_09_solver_execution_short

======================================================================
SOLVER EXECUTION (Short Test)
======================================================================

🔧 Setting up short test run...
   ✅ controlDict configured:
      endTime = 0.01s (very short test)
      deltaT = 1e-05s
      writeInterval = 0.01s

🔧 Running foamRun...
   Solver: incompressibleFluid (PIMPLE algorithm)
   ⏱️  Expected time: 1-3 minutes

   Progress: Simulated 1000 time steps
   Final time: 0.01s
   ✅ Solver execution completed

🔍 Checking for result files...
   ✅ Results written at time: 0.01s
      ✅ U (123,456 bytes)
      ✅ p (98,765 bytes)

======================================================================
✅ SOLVER EXECUTION COMPLETE
======================================================================
PASSED

tests/integration/test_patient1_complete.py::TestPatient1CompleteWorkflow::test_10_result_validation

======================================================================
RESULT VALIDATION (t = 0.01s)
======================================================================

📊 Detected patches: ['inlet', 'outlet1', 'outlet2', 'outlet3', 'outlet4']

🔧 Running postProcessing to extract flow rates...
   ✅ postProcessing completed

📈 Flow rates extracted:
   inlet      ← IN   3.141593e-04 m³/s
   outlet1    → OUT  1.047198e-04 m³/s
   outlet2    → OUT  3.393982e-05 m³/s
   outlet3    → OUT  1.979380e-05 m³/s
   outlet4    → OUT  1.563657e-04 m³/s

🔍 Flow conservation check:
   Inlet total:  3.141593e-04 m³/s
   Outlet total: 3.140210e-04 m³/s
   Error:        0.44%
   ✅ Conservation EXCELLENT (< 5%)

🔬 Comparing with Murray's Law predictions...

   Predicted (Murray) vs Actual:
   outlet1   : Murray=33.4%  Actual=33.3%  Δ= 0.3%
   outlet2   : Murray=10.8%  Actual=10.8%  Δ= 0.0%
   outlet3   : Murray= 6.3%  Actual= 6.3%  Δ= 0.0%
   outlet4   : Murray=49.6%  Actual=49.8%  Δ= 0.4%

======================================================================
✅ RESULT VALIDATION COMPLETE
======================================================================
PASSED

... (tests 11-12)

tests/integration/test_patient1_complete.py::TestPatient1CompleteWorkflow::test_13_summary

======================================================================
E2E TEST SUMMARY
======================================================================
Patient: patient1
Profile: sim_laminar_medium
Case directory: validation/output/patient1_complete_e2e/sim_laminar_medium

Completed stages:
  ✅ Config loading and validation
  ✅ Case structure creation
  ✅ Mesh dictionary generation
  ✅ Physical properties
  ✅ Numerical schemes
  ✅ Solver settings
  ✅ Control dictionary
  ✅ Mesh generation (OpenFOAM)
  ✅ Solver execution (t = 0.01s)
  ✅ Result validation
  ✅ Geometry analysis
  ✅ Flow split analysis

======================================================================
✅ E2E WORKFLOW TEST COMPLETE
======================================================================

PASSED

========================= 13 passed in 8m 32s =========================
```

---

## Troubleshooting

### Problem 1: "OpenFOAM not available"

**Symptom**: Tests skip with message "OpenFOAM not available - skipping mesh execution"

**Solution**:
```bash
# Make sure you sourced OpenFOAM
source /opt/openfoam12/etc/bashrc

# Verify commands are in PATH
which blockMesh
which snappyHexMesh
which foamRun

# Run tests again
./venv/bin/pytest tests/integration/test_patient1_complete.py -v -s
```

### Problem 2: blockMesh Fails

**Symptom**: Test fails with "blockMesh failed with return code 1"

**Debug**:
```bash
# Check the case directory manually
cd validation/output/patient1_complete_e2e/sim_laminar_medium

# Run blockMesh manually to see full output
blockMesh

# Check for issues in system/blockMeshDict
cat system/blockMeshDict

# Check log files
ls -ltr log.*
```

**Common causes**:
- Invalid blockMeshDict syntax
- Geometry bounds calculation error
- Missing STL files

### Problem 3: snappyHexMesh Fails

**Symptom**: Test fails during snappyHexMesh step

**Debug**:
```bash
cd validation/output/patient1_complete_e2e/sim_laminar_medium

# Run snappyHexMesh manually with more output
snappyHexMesh -overwrite

# Check the log
cat log.snappyHexMesh

# Check STL files exist
ls -l constant/triSurface/
```

**Common causes**:
- STL files have issues (non-manifold, open surfaces)
- Mesh refinement levels too aggressive
- LocationInMesh point is outside geometry

### Problem 4: Solver Fails

**Symptom**: Test fails with "Solver failed with return code 1"

**Debug**:
```bash
cd validation/output/patient1_complete_e2e/sim_laminar_medium

# Check if mesh exists
ls constant/polyMesh/

# Run solver manually
foamRun

# Check log
cat log.foamRun | tail -100

# Check for common issues
checkMesh
```

**Common causes**:
- Mesh quality too poor (high non-orthogonality)
- Boundary conditions not properly set
- Time step too large (try reducing deltaT)

### Problem 5: Flow Conservation Error Too High

**Symptom**: Test passes but conservation error > 5%

**Explanation**: For very short simulations (0.01s), flow may not be fully developed. This is acceptable for testing.

**If error > 15%**: This indicates a real problem
- Check mesh quality (checkMesh)
- Verify boundary conditions in 0/ directory
- Check for leaks (visualize in ParaView)

---

## Test Configuration

### Simulation Parameters (Short Test)

```python
endTime = 0.01s          # Very short test (vs 4s full simulation)
deltaT = 1e-05s          # 10 microsecond time step
writeInterval = 0.01s    # Write only at end
maxCo = 1.0              # Courant number limit
```

### Mesh Settings (Medium Resolution)

```python
target_cell_size = 1.0 mm
cells_per_diameter = 15 (inlet), 12 (branches)
refinement_levels = [1, 1] (surface)
```

### Expected Mesh Size

- **Cells**: ~500,000 to 2,000,000 (depends on geometry)
- **Points**: ~200,000 to 800,000
- **Generation time**: 2-5 minutes

### Expected Solver Time

- **Time steps**: ~1000 steps (0.01s / 1e-05s)
- **Execution time**: 1-3 minutes
- **Iterations/step**: 2-5 (PIMPLE algorithm)

---

## Customizing the Tests

### Change Simulation Time

Edit `test_09_solver_execution_short` in `test_patient1_complete.py`:

```python
# Current: 0.01s test
content = re.sub(r'endTime\s+[\d.]+;', 'endTime         0.01;', content)

# Change to 0.1s (longer but more stable)
content = re.sub(r'endTime\s+[\d.]+;', 'endTime         0.1;', content)
```

### Change Mesh Resolution

Edit patient1 config or create a new profile:

```json
{
  "mesh": {
    "mesh_resolution": {
      "target_cell_size_mm": 0.5,  // Finer mesh (was 1.0)
      "cells_per_diameter": {
        "inlet": 20,   // More cells (was 15)
        "branch": 16   // More cells (was 12)
      }
    }
  }
}
```

### Test Different Patients

```bash
# Create a new test class for patient2
# Copy test_patient1_complete.py
# Change patient_id in fixture:

@pytest.fixture(scope="class")
def patient_setup(self):
    patient_id = "patient2"  # Changed from patient1
    profile = "sim_laminar_medium"
    ...
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests with OpenFOAM

on: [push, pull_request]

jobs:
  e2e-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install OpenFOAM 12
        run: |
          sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key | apt-key add -"
          sudo add-apt-repository http://dl.openfoam.org/ubuntu
          sudo apt-get update
          sudo apt-get install -y openfoam12

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run E2E Tests
        run: |
          source /opt/openfoam12/etc/bashrc
          pytest tests/integration/test_patient1_complete.py -v --cov=src
```

---

## Performance Benchmarks

Expected times on typical workstation (8-core CPU, 16GB RAM):

| Test Stage | Time | Details |
|------------|------|---------|
| Setup (1-7) | ~5s | Dict generation |
| blockMesh | ~2s | Background mesh |
| surfaceFeatures | ~5s | Feature extraction |
| snappyHexMesh | 2-5min | Mesh refinement |
| checkMesh | ~5s | Quality check |
| foamRun (0.01s) | 1-3min | Solver execution |
| postProcessing | ~10s | Flow rate extraction |
| **Total** | **5-10min** | Complete workflow |

**Optimization tips**:
- Use parallel meshing: Set `nProcessors` in config
- Reduce mesh resolution for faster testing
- Use `sim_laminar_coarse` profile instead of `medium`

---

## Next Steps

1. **Run the tests** following instructions above
2. **Check results** in `validation/output/patient1_complete_e2e/`
3. **Visualize in ParaView** (optional):
   ```bash
   cd validation/output/patient1_complete_e2e/sim_laminar_medium
   touch case.foam
   paraview case.foam
   ```
4. **Run with different profiles**:
   ```bash
   # Edit patient_setup fixture to use different profile
   profile = "sim_laminar_fine"  # Higher resolution
   ```

---

## Questions?

- **Test documentation**: See [E2E_TEST_COMPLETE.md](E2E_TEST_COMPLETE.md)
- **General testing**: See [TESTING.md](TESTING.md)
- **OpenFOAM issues**: Check OpenFOAM documentation at https://www.openfoam.com/
- **Report bugs**: Create issue with test output and error messages

---

**Test File**: `tests/integration/test_patient1_complete.py`
**Total Tests**: 13 (10 setup + 3 OpenFOAM execution)
**Expected Time**: 5-10 minutes with OpenFOAM
**Status**: ✅ Ready to run!
