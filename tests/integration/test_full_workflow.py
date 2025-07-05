"""
Integration tests for full AortaCFD workflow.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from config.builder import ConfigBuilder
from workflow.manager import WorkflowManager
from workflow.base_task import AortaCFDError


class TestFullWorkflowIntegration:
    """Integration tests for complete workflow execution."""
    
    @pytest.fixture
    def full_test_environment(self, temp_dir):
        """Create a complete test environment with all required files."""
        # Create CAD directory structure
        cad_dir = temp_dir / "CAD" / "test_patient"
        cad_dir.mkdir(parents=True)
        
        # Create STL files
        stl_files = ["inlet.stl", "outlet1.stl", "outlet2.stl", "wall_aorta.stl"]
        for stl_file in stl_files:
            (cad_dir / stl_file).write_text("""solid test_geometry
  facet normal 0.0 0.0 1.0
    outer loop
      vertex 0.0 0.0 0.0
      vertex 1.0 0.0 0.0
      vertex 0.0 1.0 0.0
    endloop
  endfacet
endsolid test_geometry""")
        
        # Create flow rate file
        flow_data = """Time,FlowRate
0.0,0.0
0.1,100.0
0.2,80.0
0.3,60.0
0.4,40.0
0.5,20.0
0.6,0.0
0.7,0.0
0.8,0.0
0.9,0.0
1.0,0.0"""
        (cad_dir / "inletFlowRate.csv").write_text(flow_data)
        
        # Create boundary conditions
        bc_data = """{
    "boundary_conditions": {
        "inlet": {
            "type": "flowRateInletVelocity",
            "flowRate": "table"
        },
        "outlet1": {
            "type": "fixedValue",
            "value": "uniform 0"
        },
        "outlet2": {
            "type": "fixedValue",
            "value": "uniform 0"
        },
        "wall_aorta": {
            "type": "noSlip"
        }
    }
}"""
        (cad_dir / "boundary_conditions.json").write_text(bc_data)
        
        # Create config directory
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        
        # Create profiles directory
        profiles_dir = config_dir / "profiles"
        profiles_dir.mkdir()
        
        # Create __init__.py files
        (config_dir / "__init__.py").write_text("")
        (profiles_dir / "__init__.py").write_text("")
        
        # Create base config
        base_config = '''config = {
    "physics": {
        "density": 1060.0,
        "dynamic_viscosity": 0.0035,
        "kinematic_viscosity": 3.3e-06
    },
    "solver": {
        "application": "pimpleFoam",
        "start_time": 0.0,
        "end_time": 1.0,
        "delta_t": 0.001,
        "write_interval": 0.1
    },
    "numerical": {
        "ddtSchemes": {
            "default": "Euler"
        },
        "gradSchemes": {
            "default": "Gauss linear"
        }
    }
}'''
        (config_dir / "base.py").write_text(base_config)
        
        # Create test profile
        test_profile = '''config = {
    "geometry": {
        "refinement_level": "test"
    },
    "mesh": {
        "base_cell_size": 0.001,
        "refinement_surfaces": {
            "wall_aorta": {"level": "(1 2)"},
            "inlet": {"level": "(1 2)"},
            "outlet1": {"level": "(1 2)"},
            "outlet2": {"level": "(1 2)"}
        }
    }
}'''
        (profiles_dir / "test_profile.py").write_text(test_profile)
        
        return temp_dir
    
    @patch('workflow.tasks.setup_tasks.CreateCaseStructureTask')
    @patch('workflow.tasks.setup_tasks.GenerateMeshFilesTask')
    @patch('workflow.tasks.execution_tasks.ExecuteMeshingTask')
    @patch('config.builder.importlib.import_module')
    @patch('aortacfd_lib.utils.runner.run_command')
    def test_complete_workflow_mock_execution(self, mock_run_command, mock_import, mock_meshing, mock_mesh_files,
                                            mock_case_structure, full_test_environment):
        """Test complete workflow execution with mocked tasks."""
        # Setup mock modules
        mock_base_module = Mock()
        mock_base_module.config = {
            "physics": {"density": 1060.0},
            "solver": {"application": "pimpleFoam"},
            "inlet": {
                "csv_file": "inlet_velocity.csv",
                "type": "flowRateInletVelocity",
                "flowRate": "table",
                "flowRateProfile": "laminar"
            },
            "openfoam_version": "v2306",
            "openfoam_env_path": "/opt/OpenFOAM/OpenFOAM-v2306/etc/bashrc",
            "run_settings": {
                "numberOfSubdomains": 4,
                "method": "simple",
                "simpleCoeffs": {
                    "n": "(2 2 1)",
                    "delta": "0.001"
                }
            },
            "simulation_control": {
                "end_time": 1.0,
                "controlDict": {
                    "application": "pimpleFoam",
                    "startFrom": "startTime",
                    "startTime": 0.0,
                    "stopAt": "endTime",
                    "deltaT": 1e-6,
                    "writeControl": "timeStep",
                    "writeInterval": 1,
                    "runTimeModifiable": "true",
                    "allowSystemOperations": "true",
                    "purgeWrite": 0,
                    "adjustTimeStep": "yes",
                    "maxCo": 1,
                    "functions": ["wallShearStress"]
                }
            },
            "fvSolution": {
                "solvers": {
                    "p": {
                        "solver": "GAMG",
                        "tolerance": "1e-6",
                        "relTol": "0.1",
                        "smoother": "GaussSeidel",
                        "nPreSweeps": "0",
                        "nPostSweeps": "2",
                        "cacheAgglomeration": "true",
                        "agglomerator": "faceAreaPair",
                        "nCellsInCoarsestLevel": "10",
                        "mergeLevels": "1"
                    },
                    "pFinal": {
                        "solver": "GAMG",
                        "tolerance": "1e-6",
                        "relTol": "0",
                        "smoother": "GaussSeidel",
                        "nPreSweeps": "0",
                        "nPostSweeps": "2",
                        "cacheAgglomeration": "true",
                        "agglomerator": "faceAreaPair",
                        "nCellsInCoarsestLevel": "10",
                        "mergeLevels": "1"
                    },
                    "U": {
                        "solver": "smoothSolver",
                        "smoother": "GaussSeidel",
                        "tolerance": "1e-8",
                        "relTol": "0.1",
                        "nSweeps": "1"
                    },
                    "UFinal": {
                        "solver": "smoothSolver",
                        "smoother": "GaussSeidel",
                        "tolerance": "1e-8",
                        "relTol": "0",
                        "nSweeps": "1"
                    }
                },
                "PIMPLE": {
                    "nOuterCorrectors": "2",
                    "nCorrectors": "2",
                    "nNonOrthogonalCorrectors": "1",
                    "pRefCell": "0",
                    "pRefValue": "0"
                }
            }
        }
        
        mock_profile_module = Mock()
        mock_profile_module.config = {
            "geometry": {
                "refinement_level": "test",
                "case_name": "test_patient",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2"],
                "wall_keywords_ordered": "wall_aorta"
            },
            "mesh": {
                "base_cell_size": 0.001,
                "refinement_levels": {
                    "test": 0.001,
                    "coarse": 0.002,
                    "medium": 0.001,
                    "fine": 0.0005
                },
                "SNAPPY_SETTINGS": {
                    "castellatedMesh": "true",
                    "snap": "true",
                    "addLayers": "false",
                    "maxLocalCells": 100000,
                    "maxGlobalCells": 2000000,
                    "minRefinementCells": 0,
                    "nCellsBetweenLevels": 3,
                    "resolveFeatureAngle": 30,
                    "allowFreeStandingZoneFaces": "true",
                    "nSmoothPatch": 3,
                    "tolerance": 2.0,
                    "nSolveIter": 30,
                    "nRelaxIter": 5,
                    "nFeatureSnapIter": 10,
                    "expansionRatio": 1.0,
                    "finalLayerThickness": 0.3,
                    "minThickness": 0.1,
                    "nGrow": 0,
                    "featureAngle": 60,
                    "nRelaxIter": 5,
                    "nSmoothSurfaceNormals": 1,
                    "nSmoothNormals": 3,
                    "nSmoothThickness": 10,
                    "maxFaceThicknessRatio": 0.5,
                    "maxThicknessToMedialRatio": 0.3,
                    "minMedianAxisAngle": 90,
                    "nBufferCellsNoExtrude": 0,
                    "nLayerIter": 50,
                    "nRelaxedIter": 20
                }
            }
        }
        
        mock_import.side_effect = [mock_base_module, mock_profile_module]
        
        # Setup mock tasks
        mock_tasks = [mock_case_structure, mock_mesh_files]
        for mock_task in mock_tasks:
            mock_instance = Mock()
            mock_instance.execute.return_value = True
            mock_task.return_value = mock_instance
        
        # Setup mock meshing task
        mock_meshing_instance = Mock()
        mock_meshing_instance.execute.return_value = True
        mock_meshing.return_value = mock_meshing_instance
        
        # Mock run_command to always succeed
        mock_run_command.return_value = None
        
        # Change to test directory
        original_cwd = os.getcwd()
        os.chdir(full_test_environment)
        
        try:
            # Build configuration
            builder = ConfigBuilder()
            config = builder.build("test_patient", "test_profile")
            
            # Verify config was built correctly
            assert config["geometry"]["case_name"] == "test_patient"
            assert config["physics"]["density"] == 1060.0
            assert config["mesh"]["base_cell_size"] == 0.001
            
            # Run workflow
            manager = WorkflowManager(config)
            
            # Register tasks
            manager.available_tasks = {
                "create_case_structure": mock_case_structure,
                "generate_mesh_files": mock_mesh_files,
                "generate_physical_properties": mock_case_structure,
                "generate_numerical_schemes": mock_case_structure,
                "generate_solver_settings": mock_case_structure,
                "generate_decompose_par_dict": mock_case_structure,
                "generate_control_dict": mock_case_structure,
                "execute_meshing": mock_meshing,
                "prepare_boundary_data": mock_case_structure,
                "generate_bc_files": mock_case_structure,
                "update_control_dict": mock_case_structure
            }
            
            # Test different workflow commands
            workflow_commands = ["setup:dict", "run:mesh", "createCase"]
            
            for command in workflow_commands:
                try:
                    manager.run_workflow(command)
                    # Should not raise any exceptions
                except AortaCFDError as e:
                    # Check if error is due to unregistered tasks (expected in test)
                    if "not registered" not in str(e):
                        pytest.fail(f"Unexpected error in {command}: {e}")
        
        finally:
            os.chdir(original_cwd)
    
    def test_config_integration_with_real_files(self, full_test_environment):
        """Test configuration building with real files."""
        original_cwd = os.getcwd()
        os.chdir(full_test_environment)
        
        try:
            # Test case discovery
            builder = ConfigBuilder()
            case_config = builder._discover_case_config("test_patient")
            
            # Verify case discovery
            assert case_config["geometry"]["case_name"] == "test_patient"
            assert case_config["geometry"]["wall_keywords_ordered"] == "wall_aorta"
            assert case_config["geometry"]["inlet_keywords_ordered"] == "inlet"
            assert "outlet1" in case_config["geometry"]["outlet_keywords_ordered"]
            assert "outlet2" in case_config["geometry"]["outlet_keywords_ordered"]
            
            # Verify boundary conditions were loaded
            assert "boundary_conditions" in case_config
            assert case_config["boundary_conditions"]["inlet"]["type"] == "flowRateInletVelocity"
            
        finally:
            os.chdir(original_cwd)
    
    @patch('subprocess.run')
    def test_openfoam_command_integration(self, mock_run, sample_config):
        """Test OpenFOAM command execution integration."""
        # Setup successful OpenFOAM command mock
        mock_run.return_value = Mock(
            returncode=0,
            stdout="OpenFOAM command executed successfully",
            stderr=""
        )
        
        # Test command execution through workflow
        manager = WorkflowManager(sample_config)
        
        # Create a mock task that runs OpenFOAM commands
        class MockOpenFOAMTask:
            def __init__(self, config):
                self.config = config
            
            def execute(self, context):
                # Simulate OpenFOAM command execution
                import subprocess
                result = subprocess.run(
                    ["echo", "blockMesh"],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
        
        # Replace a task with our mock
        manager.available_tasks["execute_meshing"] = MockOpenFOAMTask
        
        # Run workflow
        manager.run_workflow("run:mesh")
        
        # Verify OpenFOAM command was called
        mock_run.assert_called()
    
    def test_error_propagation_integration(self, sample_config):
        """Test error propagation through workflow."""
        manager = WorkflowManager(sample_config)
        
        # Create a task that always fails
        class FailingTask:
            def __init__(self, config):
                self.config = config
            
            def execute(self, context):
                return False  # Always fail
        
        # Replace task with failing version
        manager.available_tasks["create_case_structure"] = FailingTask
        
        # Workflow should fail and propagate error
        with pytest.raises(AortaCFDError, match="Workflow aborted"):
            manager.run_workflow("setup:dict")
    
    @patch('workflow.manager.logger')
    def test_logging_integration(self, mock_logger, sample_config):
        """Test logging integration throughout workflow."""
        manager = WorkflowManager(sample_config)

        # Create mock STL files
        case_name = sample_config["geometry"]["case_name"]
        cad_dir = os.path.join("CAD", case_name)
        os.makedirs(cad_dir, exist_ok=True)
        
        # Create empty STL files for each patch
        patches = ["inlet", "outlet1", "outlet2", "wall_aorta"]
        for patch in patches:
            stl_path = os.path.join(cad_dir, f"{patch}.stl")
            with open(stl_path, 'w') as f:
                f.write("solid test\nendsolid test\n")

        # Create mock task that logs
        class LoggingTask:
            def __init__(self, config):
                self.config = config

            def execute(self, context):
                # This would normally use the logger
                return True

        # Replace tasks with logging versions
        manager.available_tasks = {
            "create_case_structure": LoggingTask,
            "generate_mesh_files": LoggingTask,
            "generate_physical_properties": LoggingTask,
            "generate_numerical_schemes": LoggingTask,
            "generate_solver_settings": LoggingTask,
            "generate_decompose_par_dict": LoggingTask,
            "generate_control_dict": LoggingTask
        }

        # Run workflow
        manager.run_workflow("setup:dict")

        # Verify logging
        assert mock_logger.info.call_count > 0
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("Starting workflow" in msg for msg in log_messages)
        assert any("Workflow completed successfully" in msg for msg in log_messages)
    
    def test_context_sharing_integration(self, sample_config):
        """Test context sharing between tasks in workflow."""
        manager = WorkflowManager(sample_config)

        # Create necessary directories
        case_name = sample_config["geometry"]["case_name"]
        case_dir = os.path.join("OPENFOAM", f"{case_name}_{sample_config['geometry']['refinement_level']}")
        os.makedirs(os.path.join(case_dir, "constant"), exist_ok=True)
        os.makedirs(os.path.join(case_dir, "system"), exist_ok=True)
        os.makedirs(os.path.join(case_dir, "0"), exist_ok=True)

        # Create mock STL files
        cad_dir = os.path.join("CAD", case_name)
        os.makedirs(cad_dir, exist_ok=True)
        
        # Create empty STL files for each patch
        patches = ["inlet", "outlet1", "outlet2", "wall_aorta"]
        for patch in patches:
            stl_path = os.path.join(cad_dir, f"{patch}.stl")
            with open(stl_path, 'w') as f:
                f.write("solid test\nendsolid test\n")

        shared_data = {}

        # Create tasks that share context
        class ContextProducerTask:
            def __init__(self, config):
                self.config = config

            def execute(self, context):
                context["shared_value"] = "test_data"
                context["case_info"] = {
                    "name": self.config["geometry"]["case_name"],
                    "refinement": self.config["geometry"]["refinement_level"]
                }
                context["case_directory"] = case_dir
                shared_data["producer_called"] = True
                return True

        class ContextConsumerTask:
            def __init__(self, config):
                self.config = config

            def execute(self, context):
                # Verify context was shared
                assert "shared_value" in context
                assert context["shared_value"] == "test_data"
                assert "case_info" in context
                shared_data["consumer_called"] = True
                shared_data["received_data"] = context["shared_value"]
                return True

        # Replace tasks in workflow
        manager.available_tasks = {
            "create_case_structure": ContextProducerTask,
            "generate_mesh_files": ContextConsumerTask,
            "generate_physical_properties": ContextConsumerTask,
            "generate_numerical_schemes": ContextConsumerTask,
            "generate_solver_settings": ContextConsumerTask,
            "generate_decompose_par_dict": ContextConsumerTask,
            "generate_control_dict": ContextConsumerTask
        }

        # Run workflow
        manager.run_workflow("setup:dict")

        # Verify context sharing worked
        assert shared_data["producer_called"]
        assert shared_data["consumer_called"]
        assert shared_data["received_data"] == "test_data"
    
    @patch('aortacfd_lib.utils.logger.Logger')
    def test_end_to_end_workflow_simulation(self, mock_logger, full_test_environment):
        """Test end-to-end workflow simulation."""
        original_cwd = os.getcwd()
        os.chdir(full_test_environment)
        
        try:
            # Setup logger mock
            mock_logger_instance = Mock()
            mock_logger.return_value.get_logger.return_value = mock_logger_instance
            
            # Test the complete workflow pipeline
            with patch('config.builder.importlib.import_module') as mock_import:
                # Setup config modules
                mock_base = Mock()
                mock_base.config = {"physics": {"density": 1060.0}}
                mock_profile = Mock()
                mock_profile.config = {"geometry": {"refinement_level": "test"}}
                mock_import.side_effect = [mock_base, mock_profile]
                
                # Build configuration
                builder = ConfigBuilder()
                config = builder.build("test_patient", "test_profile")
                
                # Create workflow manager
                manager = WorkflowManager(config)
                
                # Mock all tasks for simulation
                mock_tasks = {}
                for task_name in manager.available_tasks:
                    mock_task_class = Mock()
                    mock_task_instance = Mock()
                    mock_task_instance.execute.return_value = True
                    mock_task_class.return_value = mock_task_instance
                    mock_tasks[task_name] = mock_task_class
                    manager.available_tasks[task_name] = mock_task_class
                
                # Run complete workflow
                manager.run_workflow("runAll")
                
                # Verify all tasks were executed
                for task_name, mock_task in mock_tasks.items():
                    if task_name in ["create_case_structure", "generate_mesh_files", 
                                   "generate_physical_properties", "execute_meshing", 
                                   "execute_solver"]:
                        assert mock_task.called, f"Task {task_name} was not called"
                
                # Verify case directory was set
                assert "case_directory" in manager.context
                assert "test_patient_test" in manager.context["case_directory"]
        
        finally:
            os.chdir(original_cwd)