# Quick Start: OpenFOAM E2E Tests

**ONE-PAGE GUIDE** - Copy-paste these commands to run complete E2E tests

---

## Setup (One-time)

```bash
# 1. Install OpenFOAM 12 (if not installed)
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key | apt-key add -"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt-get update
sudo apt-get install openfoam12

# 2. Verify installation
source /opt/openfoam12/etc/bashrc
which blockMesh  # Should show: /opt/openfoam12/.../blockMesh
```

---

## Run Tests

### Complete E2E Test (Recommended)

```bash
# Source OpenFOAM (do this every time in new terminal)
source /opt/openfoam12/etc/bashrc

# Run complete test (5-10 minutes)
./venv/bin/pytest tests/integration/test_patient1_complete.py -v -s

# Expected: 13 tests passing
```

### Only OpenFOAM Tests (Skip Setup)

```bash
source /opt/openfoam12/etc/bashrc
./venv/bin/pytest tests/integration/test_patient1_complete.py -v -s -m requires_openfoam
```

### Only Setup Tests (No OpenFOAM)

```bash
# No OpenFOAM needed
./venv/bin/pytest tests/integration/test_patient1_complete.py -v -s -m "not requires_openfoam"
```

---

## What You'll See

```
test_01_config_loading              ✅ PASSED (1s)
test_02_case_structure_creation     ✅ PASSED (1s)
test_03_mesh_dictionaries           ✅ PASSED (1s)
test_04_physical_properties         ✅ PASSED (1s)
test_05_numerical_schemes           ✅ PASSED (1s)
test_06_solver_settings             ✅ PASSED (1s)
test_07_control_dict                ✅ PASSED (1s)
test_08_mesh_execution              ✅ PASSED (3-5 min) <- OpenFOAM
test_09_solver_execution_short      ✅ PASSED (1-3 min) <- OpenFOAM
test_10_result_validation           ✅ PASSED (30s)     <- OpenFOAM
test_11_geometry_analysis           ✅ PASSED (1s)
test_12_flow_split_analysis         ✅ PASSED (1s)
test_13_summary                     ✅ PASSED (1s)

========================= 13 passed in 8m 32s =========================
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "OpenFOAM not available" | `source /opt/openfoam12/etc/bashrc` |
| "blockMesh failed" | Check `validation/output/.../log.blockMesh` |
| "snappyHexMesh failed" | Check STL files in `constant/triSurface/` |
| "Solver failed" | Run `checkMesh` to verify mesh quality |
| High conservation error (>15%) | Increase simulation time in test |

---

## File Locations

- **Test file**: `tests/integration/test_patient1_complete.py`
- **Results**: `validation/output/patient1_complete_e2e/sim_laminar_medium/`
- **Mesh**: `validation/output/.../constant/polyMesh/`
- **Solution**: `validation/output/.../0.01/` (U, p fields)

---

## View Results in ParaView

```bash
cd validation/output/patient1_complete_e2e/sim_laminar_medium
touch case.foam
paraview case.foam
```

---

## Next Steps After Tests Pass

1. ✅ **Check summary** - Run `test_13_summary` to see what executed
2. ✅ **View results** - Open in ParaView to visualize flow
3. ✅ **Run different profiles** - Try `sim_laminar_fine` for higher resolution
4. ✅ **Extend simulation** - Increase endTime to 0.1s or 1.0s for more realistic results

---

**Full Documentation**: [OPENFOAM_E2E_TESTS.md](OPENFOAM_E2E_TESTS.md)
**Need help?** Check [E2E_TEST_COMPLETE.md](E2E_TEST_COMPLETE.md)
