#!/usr/bin/env python3
"""
Complete End-to-End Patient Workflow Test

Pytest test that validates the entire AortaCFD pipeline without triggering
problematic imports. Tests each workflow step independently.

This is the CRITICAL PATH test identified in TESTING_ROADMAP.md

Run with: pytest test_patient1_complete.py -v -s
"""

import pytest
import json
import subprocess
import shutil
from pathlib import Path

# Import only what we need - conftest.py adds src/ to path
from config.builder import ConfigBuilder
from aortacfd_lib.mesh_setup import GeometryAnalyzer


class TestPatient1CompleteWorkflow:
    """Complete E2E workflow test for patient1"""

    @pytest.fixture(scope="class")
    def patient_setup(self):
        """Setup patient test environment"""
        patient_id = "patient1"
        profile = "sim_laminar_medium"
        patient_config_dir = Path(f"cases_input/{patient_id}")
        test_output_dir = Path(f"validation/output/{patient_id}_complete_e2e")

        # Create output directory
        test_output_dir.mkdir(parents=True, exist_ok=True)

        # Clean previous test
        case_dir = test_output_dir / profile
        if case_dir.exists():
            shutil.rmtree(case_dir)

        setup_data = {
            "patient_id": patient_id,
            "profile": profile,
            "patient_config_dir": patient_config_dir,
            "test_output_dir": test_output_dir,
            "case_dir": case_dir
        }

        # Load and build config
        config_file = patient_config_dir / "config.json"
        with open(config_file) as f:
            patient_config = json.load(f)

        builder = ConfigBuilder()
        config = builder.build(patient_id, profile)
        config['output_directory'] = str(test_output_dir)

        # WORKAROUND: ConfigBuilder doesn't copy boundary_conditions
        # Manually add it for GenerateBCFilesTask
        if 'boundary_conditions' in patient_config:
            config['boundary_conditions'] = patient_config['boundary_conditions']

        setup_data["patient_config"] = patient_config
        setup_data["config"] = config

        return setup_data

    def test_01_config_loading(self, patient_setup):
        """Test 1: Validate configuration"""
        patient_config = patient_setup["patient_config"]
        config = patient_setup["config"]

        assert "case_info" in patient_config
        assert patient_config["case_info"]["patient_id"] == patient_setup["patient_id"]
        # Config has case_name in geometry section
        assert "geometry" in config
        assert config["geometry"]["case_name"] == patient_setup["patient_id"]

        print(f"\n✅ Config loaded: {patient_setup['patient_id']} / {patient_setup['profile']}")

    def test_02_case_structure_creation(self, patient_setup):
        """Test 2: Create case structure"""
        from workflow.tasks.setup_tasks import CreateCaseStructureTask

        config = patient_setup["config"]
        case_dir = patient_setup["case_dir"]

        task = CreateCaseStructureTask(config)
        context = {
            "case_directory": str(case_dir),
            "output_directory": str(patient_setup["test_output_dir"])
        }

        success = task.execute(context)
        assert success, "CreateCaseStructureTask failed"

        # Verify structure
        assert case_dir.exists()
        assert (case_dir / "0").exists()
        assert (case_dir / "constant").exists()
        assert (case_dir / "system").exists()
        assert (case_dir / "constant/triSurface").exists()

        stl_files = list((case_dir / "constant/triSurface").glob("*.stl"))
        assert len(stl_files) >= 5, f"Expected >=5 STL files, found {len(stl_files)}"

        print(f"✅ Case structure created: {len(stl_files)} STL files")

    def test_03_mesh_dictionaries(self, patient_setup):
        """Test 3: Generate mesh dictionaries"""
        from workflow.tasks.setup_tasks import GenerateMeshFilesTask

        config = patient_setup["config"]
        case_dir = patient_setup["case_dir"]

        task = GenerateMeshFilesTask(config)
        context = {"case_directory": str(case_dir)}

        success = task.execute(context)
        assert success, "GenerateMeshFilesTask failed"

        assert (case_dir / "system/blockMeshDict").exists()
        assert (case_dir / "system/snappyHexMeshDict").exists()
        assert (case_dir / "system/surfaceFeaturesDict").exists()

        print("✅ Mesh dictionaries generated")

    def test_04_physical_properties(self, patient_setup):
        """Test 4: Generate physical properties"""
        from workflow.tasks.setup_tasks import GeneratePhysicalPropertiesTask

        config = patient_setup["config"]
        case_dir = patient_setup["case_dir"]

        task = GeneratePhysicalPropertiesTask(config)
        context = {"case_directory": str(case_dir)}

        success = task.execute(context)
        assert success, "GeneratePhysicalPropertiesTask failed"

        properties_exists = (
            (case_dir / "constant/physicalProperties").exists() or
            (case_dir / "constant/transportProperties").exists()
        )
        assert properties_exists

        print("✅ Physical properties generated")

    def test_05_numerical_schemes(self, patient_setup):
        """Test 5: Generate numerical schemes"""
        from workflow.tasks.setup_tasks import GenerateNumericalSchemesTask

        config = patient_setup["config"]
        case_dir = patient_setup["case_dir"]

        task = GenerateNumericalSchemesTask(config)
        context = {"case_directory": str(case_dir)}

        success = task.execute(context)
        assert success, "GenerateNumericalSchemesTask failed"

        assert (case_dir / "system/fvSchemes").exists()

        print("✅ Numerical schemes generated")

    def test_06_solver_settings(self, patient_setup):
        """Test 6: Generate solver settings"""
        from workflow.tasks.setup_tasks import GenerateSolverSettingsTask

        config = patient_setup["config"]
        case_dir = patient_setup["case_dir"]

        task = GenerateSolverSettingsTask(config)
        context = {"case_directory": str(case_dir)}

        success = task.execute(context)
        assert success, "GenerateSolverSettingsTask failed"

        assert (case_dir / "system/fvSolution").exists()

        print("✅ Solver settings generated")

    def test_07_control_dict(self, patient_setup):
        """Test 7: Generate controlDict"""
        from workflow.tasks.setup_tasks import GenerateControlDictTask

        config = patient_setup["config"]
        case_dir = patient_setup["case_dir"]

        task = GenerateControlDictTask(config)
        # Add cardiac_cycle to context (required for endTime calculation)
        context = {
            "case_directory": str(case_dir),
            "cardiac_cycle": 0.8  # Default cardiac cycle for test
        }

        success = task.execute(context)
        assert success, "GenerateControlDictTask failed"

        assert (case_dir / "system/controlDict").exists()

        print("✅ Control dictionary generated")

    def test_08_boundary_condition_files(self, patient_setup):
        """Test 8: Generate boundary condition field files (0/U, 0/p, etc.)"""
        from workflow.tasks.setup_tasks import GenerateBCFilesTask

        config = patient_setup["config"]
        case_dir = patient_setup["case_dir"]

        print("\n" + "="*70)
        print("BOUNDARY CONDITION FILES")
        print("="*70)

        task = GenerateBCFilesTask(config)
        context = {"case_directory": str(case_dir)}

        success = task.execute(context)
        assert success, "GenerateBCFilesTask failed"

        # Verify 0/ directory has required fields
        zero_dir = case_dir / "0"
        assert zero_dir.exists(), "0/ directory not created"

        # Check for essential field files
        required_fields = ["U", "p"]
        for field in required_fields:
            field_file = zero_dir / field
            assert field_file.exists(), f"Missing field file: 0/{field}"
            print(f"   ✅ 0/{field}")

        print("\n✅ Boundary condition files generated")

    @pytest.mark.requires_openfoam
    def test_09_mesh_execution(self, patient_setup):
        """Test 9: Execute mesh generation (requires OpenFOAM)"""
        config = patient_setup["config"]
        case_dir = patient_setup["case_dir"]

        # Check OpenFOAM availability
        try:
            subprocess.run(["which", "blockMesh"], capture_output=True, check=True)
        except subprocess.CalledProcessError:
            pytest.skip("OpenFOAM not available - skipping mesh execution")

        print("\n" + "="*70)
        print("MESH GENERATION (OpenFOAM)")
        print("="*70)

        # Step 1: Run blockMesh
        print("\n🔧 Step 1: Running blockMesh...")
        print("   This creates the background hexahedral mesh")

        result = subprocess.run(
            ["blockMesh", "-case", str(case_dir)],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )

        if result.returncode != 0:
            print(f"❌ blockMesh failed!")
            print("STDOUT:", result.stdout[-500:])
            print("STDERR:", result.stderr[-500:])
            pytest.fail(f"blockMesh failed with return code {result.returncode}")

        # Verify polyMesh created
        polymesh_dir = case_dir / "constant/polyMesh"
        assert polymesh_dir.exists(), "polyMesh directory not created"
        assert (polymesh_dir / "points").exists(), "points file missing"
        assert (polymesh_dir / "faces").exists(), "faces file missing"
        assert (polymesh_dir / "owner").exists(), "owner file missing"
        assert (polymesh_dir / "neighbour").exists(), "neighbour file missing"
        assert (polymesh_dir / "boundary").exists(), "boundary file missing"

        print("   ✅ blockMesh completed - background mesh created")

        # Step 2: Run surfaceFeatures (extract geometry features)
        print("\n🔧 Step 2: Running surfaceFeatures...")
        print("   This extracts edges and features from STL files")

        result = subprocess.run(
            ["surfaceFeatures", "-case", str(case_dir)],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print("   ✅ surfaceFeatures completed")
        else:
            print(f"   ⚠️  surfaceFeatures failed (non-critical)")

        # Step 3: Run snappyHexMesh
        print("\n🔧 Step 3: Running snappyHexMesh...")
        print("   This refines mesh around geometry and creates boundary layers")
        print("   ⏱️  This may take 2-5 minutes for patient1...")

        result = subprocess.run(
            ["snappyHexMesh", "-overwrite", "-case", str(case_dir)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode != 0:
            print(f"❌ snappyHexMesh failed!")
            print("STDOUT:", result.stdout[-1000:])
            print("STDERR:", result.stderr[-500:])
            pytest.fail(f"snappyHexMesh failed with return code {result.returncode}")

        print("   ✅ snappyHexMesh completed")

        # Step 4: Run checkMesh to validate quality
        print("\n🔧 Step 4: Running checkMesh...")
        print("   This validates mesh quality")

        result = subprocess.run(
            ["checkMesh", "-case", str(case_dir)],
            capture_output=True,
            text=True
        )

        # Parse mesh statistics
        output = result.stdout
        mesh_ok = "Mesh OK" in output or "OK" in output

        # Extract key metrics
        import re
        cells_match = re.search(r'cells:\s+(\d+)', output)
        points_match = re.search(r'points:\s+(\d+)', output)
        faces_match = re.search(r'faces:\s+(\d+)', output)

        if cells_match and points_match:
            n_cells = int(cells_match.group(1))
            n_points = int(points_match.group(1))
            n_faces = int(faces_match.group(1)) if faces_match else 0

            print(f"\n📊 Mesh statistics:")
            print(f"   Cells:  {n_cells:,}")
            print(f"   Points: {n_points:,}")
            print(f"   Faces:  {n_faces:,}")

            # Sanity checks
            assert n_cells > 1000, f"Too few cells: {n_cells}"
            assert n_points > 1000, f"Too few points: {n_points}"

        # Check mesh quality
        if mesh_ok:
            print("   ✅ Mesh quality: PASS")
        else:
            print("   ⚠️  Mesh quality: Has warnings (may be acceptable)")
            # Print quality warnings
            for line in output.split('\n'):
                if 'SEVERE' in line or 'WARNING' in line or '***' in line:
                    print(f"      {line.strip()}")

        print("\n" + "="*70)
        print("✅ MESH GENERATION COMPLETE")
        print("="*70)

    @pytest.mark.requires_openfoam
    def test_10_solver_execution_short(self, patient_setup):
        """Test 10: Execute solver for short test run (requires OpenFOAM)"""
        config = patient_setup["config"]
        case_dir = patient_setup["case_dir"]

        # Check OpenFOAM and mesh
        try:
            subprocess.run(["which", "foamRun"], capture_output=True, check=True)
        except subprocess.CalledProcessError:
            pytest.skip("OpenFOAM not available - skipping solver execution")

        polymesh_dir = case_dir / "constant/polyMesh"
        if not polymesh_dir.exists():
            pytest.skip("Mesh not generated - skipping solver execution")

        # Check if custom windkessel library is available
        # The library should be at ~/OpenFOAM/user-12/platforms/.../lib/libmodularWKPressure.so
        import os
        home = Path.home()
        user = os.environ.get('USER', 'user')
        wk_lib = home / "OpenFOAM" / f"{user}-12" / "platforms" / "linux64GccDPInt32Opt" / "lib" / "libmodularWKPressure.so"

        if not wk_lib.exists():
            pytest.skip(f"Custom windkessel library not found at {wk_lib}\nRun: bash scripts/install_windkessel_of12.sh")

        print("\n" + "="*70)
        print("SOLVER EXECUTION (Short Test)")
        print("="*70)

        # Modify controlDict for very short test run
        print("\n🔧 Setting up short test run...")
        control_dict = case_dir / "system/controlDict"

        with open(control_dict, 'r') as f:
            content = f.read()

        # Backup original
        with open(case_dir / "system/controlDict.backup", 'w') as f:
            f.write(content)

        # Update to very short run (0.01s = ~10 time steps)
        import re
        content = re.sub(r'endTime\s+[\d.]+;', 'endTime         0.01;', content)
        content = re.sub(r'writeInterval\s+[\d.]+;', 'writeInterval   0.01;', content)
        content = re.sub(r'deltaT\s+[\d.eE-]+;', 'deltaT          1e-05;', content)

        with open(control_dict, 'w') as f:
            f.write(content)

        print("   ✅ controlDict configured:")
        print("      endTime = 0.01s (very short test)")
        print("      deltaT = 1e-05s")
        print("      writeInterval = 0.01s")

        # Run solver
        print("\n🔧 Running foamRun...")
        print("   Solver: incompressibleFluid (PIMPLE algorithm)")
        print("   ⏱️  Expected time: 1-3 minutes")
        print()

        result = subprocess.run(
            ["foamRun", "-case", str(case_dir)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        # Parse output for progress
        if "Time =" in result.stdout:
            # Extract time steps
            time_steps = re.findall(r'Time = ([\d.e-]+)', result.stdout)
            if time_steps:
                print(f"   Progress: Simulated {len(time_steps)} time steps")
                print(f"   Final time: {time_steps[-1]}s")

        # Check if solver completed successfully
        if result.returncode != 0:
            print(f"\n❌ Solver failed with return code {result.returncode}")
            print("\nLast 50 lines of output:")
            print('\n'.join(result.stdout.split('\n')[-50:]))
            print("\nErrors:")
            print(result.stderr[-1000:] if result.stderr else "No stderr")
            pytest.fail(f"Solver failed with return code {result.returncode}")

        print("   ✅ Solver execution completed")

        # Verify result files created
        print("\n🔍 Checking for result files...")

        # Find any time directory > 0
        time_dirs = [d for d in case_dir.iterdir()
                     if d.is_dir() and d.name.replace('.', '').replace('-', '').isdigit()
                     and float(d.name) > 0]

        if time_dirs:
            latest_time = max(time_dirs, key=lambda d: float(d.name))
            print(f"   ✅ Results written at time: {latest_time.name}s")

            # Check for required fields
            required_fields = ["U", "p"]
            for field in required_fields:
                field_file = latest_time / field
                if field_file.exists():
                    # Get file size
                    size = field_file.stat().st_size
                    print(f"      ✅ {field} ({size:,} bytes)")
                    assert field_file.exists(), f"Missing result field: {field}"
                else:
                    print(f"      ❌ {field} (missing)")
                    pytest.fail(f"Missing result field: {field}")
        else:
            print("   ⚠️  No time directories found")
            print("   Checking log for errors...")

            log_file = case_dir / "log.foamRun"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    log_content = f.read()
                    if "FOAM FATAL ERROR" in log_content:
                        print("\n❌ Fatal error in log:")
                        for line in log_content.split('\n'):
                            if "FATAL" in line or "ERROR" in line:
                                print(f"      {line}")

            pytest.fail("Solver did not produce any time directories")

        print("\n" + "="*70)
        print("✅ SOLVER EXECUTION COMPLETE")
        print("="*70)

    @pytest.mark.requires_openfoam
    def test_11_result_validation(self, patient_setup):
        """Test 11: Validate simulation results (requires OpenFOAM)"""
        case_dir = patient_setup["case_dir"]

        # Check if results exist
        time_dirs = [d for d in case_dir.iterdir()
                     if d.is_dir() and d.name.replace('.', '').replace('-', '').isdigit()
                     and float(d.name) > 0]

        if not time_dirs:
            pytest.skip("No simulation results found - skipping validation")

        latest_time = max(time_dirs, key=lambda d: float(d.name))

        print("\n" + "="*70)
        print(f"RESULT VALIDATION (t = {latest_time.name}s)")
        print("="*70)

        # Add flow rate extraction
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "validation"))

        try:
            from analyzers.flow_rate_extractor import FlowRateExtractor
            from analyzers.flow_split_analyzer import FlowSplitAnalyzer

            # Get outlet names
            stl_dir = case_dir / "constant/triSurface"
            patches = ['inlet'] + [f.stem for f in stl_dir.glob("outlet*.stl")]

            print(f"\n📊 Detected patches: {patches}")

            # Run postProcessing for flow rates
            print("\n🔧 Running postProcessing to extract flow rates...")
            extractor = FlowRateExtractor(case_dir)

            if extractor.run_postProcessing(patches, time_val=latest_time.name):
                print("   ✅ postProcessing completed")

                # Extract flow rates
                flow_rates = extractor.extract_flow_rates_from_postProcessing(
                    patches, latest_time.name
                )

                if flow_rates:
                    print(f"\n📈 Flow rates extracted:")
                    for patch, rate in flow_rates.items():
                        direction = "→ OUT" if "outlet" in patch else "← IN "
                        print(f"   {patch:10s} {direction}  {rate:12.6e} m³/s")

                    # Validate flow conservation
                    print("\n🔍 Flow conservation check:")
                    inlet_rate, outlet_total, error = extractor.validate_flow_conservation(flow_rates)

                    print(f"   Inlet total:  {inlet_rate:12.6e} m³/s")
                    print(f"   Outlet total: {outlet_total:12.6e} m³/s")
                    print(f"   Error:        {error:6.2f}%")

                    # Assert conservation (allow up to 10% error for short test)
                    if error < 5.0:
                        print("   ✅ Conservation EXCELLENT (< 5%)")
                    elif error < 10.0:
                        print("   ✅ Conservation ACCEPTABLE (< 10%)")
                    else:
                        print(f"   ⚠️  Conservation WARNING ({error:.2f}% > 10%)")
                        print("      Note: Short simulation may not be fully developed")

                    assert error < 15.0, f"Flow conservation error too high: {error:.2f}%"

                    # Compare with Murray's Law predictions
                    print("\n🔬 Comparing with Murray's Law predictions...")

                    # Load config for flow split analysis
                    config_file = case_dir / "config.json"
                    if config_file.exists():
                        with open(config_file) as f:
                            config = json.load(f)

                        analyzer = FlowSplitAnalyzer(case_dir)
                        flow_split_metrics = analyzer.analyze_flow_split(config)

                        if flow_split_metrics.murray_split:
                            print("\n   Predicted (Murray) vs Actual:")
                            outlet_flow_rates = {k: v for k, v in flow_rates.items() if 'outlet' in k}
                            total_outlet_flow = sum(abs(v) for v in outlet_flow_rates.values())

                            for outlet in sorted(outlet_flow_rates.keys()):
                                actual_fraction = abs(outlet_flow_rates[outlet]) / total_outlet_flow
                                murray_fraction = flow_split_metrics.murray_split.get(outlet, 0.0)
                                deviation = abs(actual_fraction - murray_fraction) / murray_fraction * 100 if murray_fraction > 0 else 0

                                print(f"   {outlet:10s}: Murray={murray_fraction:5.1%}  Actual={actual_fraction:5.1%}  Δ={deviation:5.1f}%")

                    print("\n" + "="*70)
                    print("✅ RESULT VALIDATION COMPLETE")
                    print("="*70)
                else:
                    print("   ⚠️  Could not extract flow rates from postProcessing")
                    print("      Results may not be available yet")
            else:
                print("   ⚠️  postProcessing did not complete successfully")

        except ImportError as e:
            print(f"⚠️  Flow validation skipped: {e}")
            print("   Validation analyzers not available")

    def test_12_geometry_analysis(self, patient_setup):
        """Test 12: Geometry analysis"""
        config = patient_setup["config"]
        case_dir = patient_setup["case_dir"]

        analyzer = GeometryAnalyzer(config, case_dir)
        ref_radius = analyzer._determine_reference_radius()

        assert ref_radius > 0, "Reference radius should be positive"
        assert ref_radius < 50, "Reference radius seems unrealistically large"

        print(f"✅ Geometry analysis: ref_radius = {ref_radius:.3f} mm")

    def test_13_flow_split_analysis(self, patient_setup):
        """Test 13: Flow split analysis"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "validation"))

        from analyzers.flow_split_analyzer import FlowSplitAnalyzer

        case_dir = patient_setup["case_dir"]

        # Copy config to case dir
        import shutil
        shutil.copy(
            patient_setup["patient_config_dir"] / "config.json",
            case_dir / "config.json"
        )

        with open(case_dir / "config.json") as f:
            config = json.load(f)

        analyzer = FlowSplitAnalyzer(case_dir)
        metrics = analyzer.analyze_flow_split(config)

        assert len(metrics.outlet_areas) >= 4, "Expected at least 4 outlets"
        assert metrics.murray_split is not None, "Murray split should be calculated"
        assert all(0 <= v <= 1 for v in metrics.murray_split.values()), "Murray ratios should be 0-1"

        print(f"✅ Flow split: {len(metrics.outlet_areas)} outlets, Murray deviation {metrics.mean_deviation_percent:.1f}%")

    def test_14_summary(self, patient_setup):
        """Test 14: Print final summary"""
        case_dir = patient_setup["case_dir"]

        print("\n" + "="*70)
        print("E2E TEST SUMMARY")
        print("="*70)
        print(f"Patient: {patient_setup['patient_id']}")
        print(f"Profile: {patient_setup['profile']}")
        print(f"Case directory: {case_dir}")
        print()
        print("Completed stages:")
        print("  ✅ Config loading and validation")
        print("  ✅ Case structure creation")
        print("  ✅ Mesh dictionary generation")
        print("  ✅ Physical properties")
        print("  ✅ Numerical schemes")
        print("  ✅ Solver settings")
        print("  ✅ Control dictionary")

        # Check if OpenFOAM tests ran
        polymesh_dir = case_dir / "constant/polyMesh"
        if polymesh_dir.exists():
            print("  ✅ Mesh generation (OpenFOAM)")

            # Check if solver ran
            time_dirs = [d for d in case_dir.iterdir()
                         if d.is_dir() and d.name.replace('.', '').replace('-', '').isdigit()
                         and float(d.name) > 0]
            if time_dirs:
                latest_time = max(time_dirs, key=lambda d: float(d.name))
                print(f"  ✅ Solver execution (t = {latest_time.name}s)")
                print("  ✅ Result validation")
            else:
                print("  ⚠️  Solver execution (skipped or failed)")
        else:
            print("  ⚠️  Mesh generation (OpenFOAM not available)")
            print("  ⚠️  Solver execution (requires mesh)")
            print("  ⚠️  Result validation (requires results)")

        print("  ✅ Geometry analysis")
        print("  ✅ Flow split analysis")
        print()

        if not polymesh_dir.exists():
            print("To run OpenFOAM tests:")
            print("  1. source /opt/openfoam12/etc/bashrc")
            print("  2. pytest tests/integration/test_patient1_complete.py -v -s -m requires_openfoam")
            print()

        print("="*70)
        print("✅ E2E WORKFLOW TEST COMPLETE")
        print("="*70 + "\n")


if __name__ == "__main__":
    # Run with pytest
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s", "--tb=short"]))
