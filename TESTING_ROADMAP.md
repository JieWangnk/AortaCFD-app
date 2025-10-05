# AortaCFD Testing Roadmap

**Date**: 2025-10-04
**Current Coverage**: 29% (353 tests passing)
**Status**: Core functionality tested, gaps remain

---

## 📊 Current Testing Status

### ✅ **What's Well Tested** (353 passing tests):

**Unit Tests** (262 tests - 100% passing):
- ✅ Config system (builder, profiles, validation)
- ✅ Mesh setup (geometry analysis, blockMesh, snappyHexMesh)
- ✅ Murray calculator (flow distribution, vessel detection)
- ✅ Inlet mapping (plug, parabolic, pulsatile profiles)
- ✅ Boundary conditions (numerical setup, fvSchemes)
- ✅ Windkessel setup (3EWK parameters, resistance/capacitance)
- ✅ Utils (file operations, security, logging)

**Integration Tests** (27 tests - 44% passing):
- ✅ Config workflow (9/9 passing)
- ⚠️ Mesh workflow (2/9 passing - needs realistic fixtures)
- ⚠️ Boundary workflow (1/9 passing - needs OpenFOAM mocks)
- ✅ Inlet mapping workflow (7/7 passing)

**E2E Tests** (4 tests - 100% passing):
- ✅ Patient1 config loading
- ✅ Geometry file existence
- ✅ Case structure creation
- ✅ Geometry analysis

**Validation Tests** (in validation/ directory):
- ✅ Level 1: Mesh quality validation
- ✅ Level 4: BC validation (inlet/outlet detection)
- ✅ Level 6: Physical results validation
- ✅ Flow split analysis (custom vs Murray)
- ✅ Flow rate extraction and validation

### ❌ **What's NOT Tested** (0% coverage):

**Critical Gaps**:
1. **Patient Runner** (0% coverage, 283 lines)
   - Main execution pipeline
   - Step orchestration
   - Error handling

2. **Execution Tasks** (11% coverage, 100 lines)
   - Mesh execution (blockMesh, snappyHexMesh, checkMesh)
   - Solver execution (foamRun)
   - Post-processing

3. **Publication Tasks** (0% coverage, 172 lines)
   - Report generation
   - Visualization
   - VTK export

4. **Parallel Processing** (0% coverage, 192 lines)
   - Multi-patient execution
   - Resource management
   - Queue handling

---

## 🎯 Testing Priorities

### **Priority 1: CRITICAL** (Must have before production)

#### 1. **End-to-End Patient Workflow** 🔴
**Status**: Partial (only setup tested, not execution)
**Gap**: No test runs full pipeline from geometry → results

**What's Needed**:
```bash
# Test complete patient workflow
test_complete_patient_workflow():
    1. Load patient1 config
    2. Create case structure
    3. Run mesh generation (blockMesh + snappyHexMesh)
    4. Apply boundary conditions
    5. Run solver (short simulation)
    6. Extract results
    7. Validate outputs
```

**Estimated Effort**: 2-3 days
**Blockers**: Need OpenFOAM installed and working

#### 2. **Mesh Execution Validation** 🔴
**Status**: 11% coverage
**Gap**: No validation of actual mesh generation

**What's Needed**:
- Test blockMesh execution
- Test snappyHexMesh execution
- Test checkMesh quality validation
- Validate mesh file outputs (polyMesh/)

**Estimated Effort**: 1 day
**Blockers**: OpenFOAM installation

#### 3. **Solver Execution & Convergence** 🔴
**Status**: 0% coverage
**Gap**: No validation that solver actually runs

**What's Needed**:
- Test foamRun execution
- Monitor convergence (residuals)
- Validate simulation completion
- Check result files (U, p fields)

**Estimated Effort**: 1-2 days
**Blockers**: OpenFOAM installation

---

### **Priority 2: IMPORTANT** (Nice to have, improves reliability)

#### 4. **Patient Runner Integration** 🟡
**Status**: 0% coverage
**Gap**: Main execution pipeline untested

**What's Needed**:
```python
test_patient_runner():
    - Test CLI argument parsing
    - Test step execution order
    - Test error handling and recovery
    - Test logging and reporting
```

**Estimated Effort**: 1 day

#### 5. **Realistic BC Workflow** 🟡
**Status**: Script exists, not fully tested
**Gap**: Pulsatile inlet + 3EWK outlets not validated

**What's Needed**:
- Test time-varying inlet from CSV
- Test Windkessel BC application
- Test WSS extraction
- Validate flow split accuracy

**Estimated Effort**: 1 day

#### 6. **Multi-Patient Parallel Execution** 🟡
**Status**: 0% coverage
**Gap**: Parallel processing untested

**What's Needed**:
- Test parallel patient processing
- Test resource allocation
- Test queue management
- Validate concurrent execution

**Estimated Effort**: 1-2 days

---

### **Priority 3: OPTIONAL** (Future improvements)

#### 7. **Publication & Visualization** 🟢
**Status**: 0% coverage
**Not critical for core functionality**

#### 8. **Performance Benchmarking** 🟢
**Status**: Partial (2 performance tests exist)
**Nice to have for optimization**

#### 9. **Regression Testing** 🟢
**Status**: Not implemented
**Future: Compare against baseline results**

---

## 🧪 Recommended Testing Plan

### **Phase 1: Critical Path Validation** (Week 1)

**Day 1-2: E2E Patient Workflow**
```bash
# Create comprehensive E2E test
test_patient1_complete_workflow.py:
  ✓ Setup (tested)
  ✓ Mesh generation (NEW - test blockMesh + snappyHexMesh)
  ✓ BC application (tested)
  ✓ Solver execution (NEW - test foamRun)
  ✓ Result extraction (NEW - test field reading)
  ✓ Validation (tested)
```

**Day 3: Mesh Execution**
- Test blockMesh with realistic parameters
- Test snappyHexMesh with patient geometry
- Validate mesh quality (checkMesh)
- Check polyMesh/ files

**Day 4: Solver Execution**
- Test short laminar simulation (0.1s)
- Monitor residuals
- Check convergence
- Validate result files (0.1/ directory)

**Day 5: Integration & Fixes**
- Fix any discovered issues
- Update documentation
- CI/CD integration

### **Phase 2: Patient Runner & Workflows** (Week 2)

**Day 1-2: Patient Runner**
- Test CLI parsing
- Test step orchestration
- Error handling tests
- Logging validation

**Day 3: Realistic BC Workflow**
- Pulsatile inlet testing
- 3EWK outlet validation
- WSS extraction test
- Flow split accuracy check

**Day 4-5: Parallel Execution**
- Multi-patient tests
- Resource management
- Queue handling
- Concurrent execution

### **Phase 3: Polish & Performance** (Week 3)

**Day 1-2: Fix Integration Test Failures**
- Fix 15 failing integration tests
- Update fixtures with realistic geometry
- Mock OpenFOAM utilities where needed

**Day 3-4: Performance Testing**
- Benchmark mesh generation
- Benchmark solver execution
- Memory usage profiling
- Optimization opportunities

**Day 5: Documentation & CI/CD**
- Update test documentation
- CI/CD pipeline improvements
- Coverage reporting

---

## 📋 Detailed Test Cases Needed

### **1. E2E Patient Workflow Test**

```python
def test_patient1_complete_workflow():
    """Complete patient1 simulation from start to finish"""

    # Setup
    patient_id = "patient1"
    config = load_patient_config(patient_id)
    case_dir = create_case_structure(patient_id, config)

    # Mesh generation
    run_blockmesh(case_dir)
    assert (case_dir / "constant/polyMesh/points").exists()

    run_snappyhexmesh(case_dir)
    assert (case_dir / "constant/polyMesh/boundary").exists()

    mesh_quality = run_checkmesh(case_dir)
    assert mesh_quality['max_non_orthogonality'] < 70

    # Boundary conditions
    setup_boundary_conditions(case_dir, config)
    assert (case_dir / "0/U").exists()
    assert (case_dir / "0/p").exists()

    # Run simulation (0.1s)
    run_simulation(case_dir, end_time=0.1)
    assert (case_dir / "0.1/U").exists()
    assert (case_dir / "0.1/p").exists()

    # Extract results
    velocity_stats = extract_velocity_stats(case_dir, time=0.1)
    assert 0.05 < velocity_stats['max'] < 2.0  # Realistic aortic flow

    pressure_stats = extract_pressure_stats(case_dir, time=0.1)
    assert pressure_stats is not None

    # Validation
    validation_results = run_validation(case_dir)
    assert validation_results['flow_conservation_error'] < 5.0
    assert validation_results['mesh_quality_pass'] == True

    print("✅ Complete patient1 workflow validated!")
```

### **2. Mesh Execution Tests**

```python
def test_blockmesh_execution():
    """Test blockMesh execution with realistic parameters"""
    # Setup case with blockMeshDict
    # Run blockMesh
    # Validate polyMesh/ files
    # Check cell count matches expected

def test_snappyhexmesh_execution():
    """Test snappyHexMesh with patient geometry"""
    # Setup with STL files
    # Run snappyHexMesh
    # Validate refinement
    # Check boundary layers

def test_checkmesh_validation():
    """Test checkMesh quality checks"""
    # Run checkMesh
    # Parse output
    # Validate metrics
```

### **3. Solver Execution Tests**

```python
def test_laminar_solver_execution():
    """Test laminar solver execution"""
    # Setup case
    # Run foamRun (laminar, 0.1s)
    # Monitor residuals
    # Check convergence

def test_rans_solver_execution():
    """Test RANS solver execution"""
    # Setup RANS case
    # Run foamRun (RANS, 0.1s)
    # Check turbulence fields (k, omega)

def test_solver_convergence_monitoring():
    """Test residual monitoring"""
    # Run solver with logging
    # Parse residuals
    # Validate convergence criteria
```

### **4. Flow Rate Validation Tests**

```python
def test_actual_flow_rate_extraction():
    """Test flow rate extraction from real simulation"""
    # Run simulation with surfaceFieldValue
    # Extract flow rates
    # Compare actual vs Murray vs custom
    # Validate conservation

def test_flow_split_accuracy():
    """Test if actual flow matches Murray's Law"""
    # Run simulation with Murray auto
    # Extract actual ratios
    # Compare to Murray prediction
    # Assert deviation < 10%
```

---

## 🔧 Testing Infrastructure Needed

### **1. OpenFOAM Test Environment**

**Setup**:
```bash
# Install OpenFOAM 12
source /opt/openfoam12/etc/bashrc

# Verify installation
which blockMesh
which snappyHexMesh
which foamRun
```

**Docker Alternative** (for CI/CD):
```dockerfile
FROM openfoam/openfoam12-run

COPY . /app
WORKDIR /app

RUN pip install pytest pytest-cov
CMD ["pytest", "tests/", "-v"]
```

### **2. Realistic Test Fixtures**

**Create**:
- `tests/fixtures/realistic_geometry/` - Full patient STL set
- `tests/fixtures/realistic_mesh/` - Pre-generated polyMesh
- `tests/fixtures/realistic_results/` - Baseline simulation results

### **3. OpenFOAM Mocking** (for unit tests)

```python
@pytest.fixture
def mock_openfoam_execution(monkeypatch):
    """Mock OpenFOAM execution for unit tests"""
    def mock_subprocess_run(cmd, **kwargs):
        # Return success for OpenFOAM commands
        return Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)
```

### **4. Performance Profiling**

```python
@pytest.mark.benchmark
def test_mesh_generation_performance():
    """Benchmark mesh generation time"""
    import time

    start = time.time()
    run_mesh_generation(patient1)
    elapsed = time.time() - start

    assert elapsed < 300  # Should complete in <5 min
    print(f"Mesh generation: {elapsed:.1f}s")
```

---

## 📊 Coverage Goals

### **Current**: 29% overall

### **Target Coverage**:

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| Config | 85% | 90% | Low (already good) |
| Mesh Setup | 78% | 85% | Low (already good) |
| Murray Calculator | 34% | 60% | Medium |
| Inlet Mapping | 60% | 75% | Medium |
| **Patient Runner** | **0%** | **80%** | **HIGH** |
| **Execution Tasks** | **11%** | **80%** | **HIGH** |
| Workflow Manager | 18% | 60% | Medium |
| **Overall** | **29%** | **70%** | **HIGH** |

---

## ✅ Success Criteria

### **Minimum Viable Testing** (before v1.0 release):

1. ✅ **E2E workflow test passes** - Complete patient1 simulation validated
2. ✅ **Mesh generation tested** - blockMesh + snappyHexMesh working
3. ✅ **Solver execution tested** - foamRun completes successfully
4. ✅ **Flow validation working** - Actual flow matches Murray < 10%
5. ✅ **Patient runner tested** - Main CLI executes without errors
6. ✅ **60%+ coverage** - Critical paths covered

### **Production Ready** (v1.0+):

1. ✅ All critical paths tested (80%+ coverage)
2. ✅ Multi-patient parallel execution validated
3. ✅ Regression tests in place
4. ✅ CI/CD pipeline automated
5. ✅ Performance benchmarks established

---

## 🚀 Quick Start: Next Testing Steps

### **Immediate Actions** (This Week):

1. **Day 1: Setup OpenFOAM Test Environment**
   ```bash
   source /opt/openfoam12/etc/bashrc
   cd validation/
   ./run_simulation_validation.py patient1 --profiles sim_laminar_medium --time 0.1
   ```

2. **Day 2: Create E2E Test**
   ```bash
   # Create test_patient1_complete.py
   # Test full workflow: geometry → mesh → solve → validate
   pytest test_patient1_complete.py -v
   ```

3. **Day 3: Test Mesh Execution**
   ```bash
   # Test actual OpenFOAM mesh generation
   pytest test_mesh_execution.py -v
   ```

4. **Day 4: Test Solver Execution**
   ```bash
   # Test foamRun with monitoring
   pytest test_solver_execution.py -v
   ```

5. **Day 5: Integration & Documentation**
   ```bash
   # Fix issues, update docs
   pytest tests/ --cov=src --cov-report=html
   ```

---

## 📚 Resources

**Existing Tests**:
- `tests/unit/` - 262 unit tests (100% passing)
- `tests/integration/` - 27 integration tests (44% passing)
- `test_patient1_e2e.py` - 4 E2E tests (100% passing)
- `validation/` - Validation scripts (working)

**Documentation**:
- `TESTING.md` - Testing guide
- `validation/README.md` - Validation framework
- `FLOW_VALIDATION_INDEX.md` - Flow validation docs

**Tools**:
- pytest - Test framework
- pytest-cov - Coverage reporting
- pytest-xdist - Parallel testing
- pytest-benchmark - Performance testing

---

## 🎯 Summary

### **What's Done**: ✅
- Unit tests for core libraries (262 tests)
- Config and setup workflows tested
- Flow validation framework complete
- Geometry analysis validated

### **What's Needed**: ❌
1. **E2E workflow test** (highest priority)
2. **Mesh execution validation**
3. **Solver execution validation**
4. **Patient runner testing**
5. **Parallel processing testing**

### **Estimated Timeline**:
- **Week 1**: Critical path (E2E, mesh, solver) - 5 days
- **Week 2**: Patient runner & workflows - 5 days
- **Week 3**: Polish & performance - 5 days
- **Total**: 3 weeks to 70% coverage

### **Next Step**:
Create `test_patient1_complete.py` for E2E workflow validation!

---

**Status**: 📋 Roadmap Complete
**Next**: Execute Phase 1 testing plan
