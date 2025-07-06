"""
Unit tests for WorkflowManager class.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from src.workflow.manager import WorkflowManager, AortaCFDError


class TestWorkflowManager:
    """Test the WorkflowManager class."""
    
    def test_init(self, sample_config):
        """Test WorkflowManager initialization."""
        manager = WorkflowManager(sample_config)
        
        assert manager.config == sample_config
        assert manager.context == {}
        assert len(manager.available_tasks) > 0
        
        # Check that all expected tasks are registered
        expected_tasks = [
            "create_case_structure",
            "generate_mesh_files",
            "generate_physical_properties",
            "generate_numerical_schemes",
            "generate_solver_settings",
            "generate_decompose_par_dict",
            "prepare_boundary_data",
            "generate_bc_files",
            "generate_control_dict",
            "execute_meshing",
            "execute_solver",
            "execute_post"
        ]
        
        for task in expected_tasks:
            assert task in manager.available_tasks
    
    def test_register_tasks(self, sample_config):
        """Test task registration."""
        manager = WorkflowManager(sample_config)
        
        # Verify tasks are properly registered
        assert "create_case_structure" in manager.available_tasks
        assert "execute_solver" in manager.available_tasks
        
        # Check that task classes are actual classes, not None
        for task_name, task_class in manager.available_tasks.items():
            assert task_class is not None
            assert hasattr(task_class, '__call__')  # Should be callable (class)
    
    def test_unknown_command(self, sample_config):
        """Test handling of unknown commands."""
        manager = WorkflowManager(sample_config)
        
        with pytest.raises(AortaCFDError, match="Unknown command 'invalid_command'"):
            manager.run_workflow("invalid_command")
    
    def test_case_directory_creation(self, sample_config):
        """Test case directory path creation."""
        manager = WorkflowManager(sample_config)
        
        # Mock the task execution to avoid actual task running
        with patch.object(manager, 'available_tasks', {}):
            try:
                manager.run_workflow("setup:dict")
            except AortaCFDError:
                pass  # Expected since no tasks are registered
        
        # Check that case directory path was set correctly
        expected_path = os.path.join(
            os.getcwd(), 
            "output", 
            "OPENFOAM", 
            f"{sample_config['geometry']['case_name']}_{sample_config['geometry']['refinement_level']}"
        )
        assert manager.context["case_directory"] == expected_path
    
    @patch('src.workflow.manager.logger')
    def test_successful_workflow_execution(self, mock_logger, sample_config):
        """Test successful workflow execution."""
        manager = WorkflowManager(sample_config)
        
        # Create mock task that succeeds
        mock_task_class = Mock()
        mock_task_instance = Mock()
        mock_task_instance.execute.return_value = True
        mock_task_class.return_value = mock_task_instance
        
        # Replace available tasks with our mock
        manager.available_tasks = {
            "create_case_structure": mock_task_class,
            "generate_mesh_files": mock_task_class,
            "generate_physical_properties": mock_task_class,
            "generate_numerical_schemes": mock_task_class,
            "generate_solver_settings": mock_task_class,
            "generate_decompose_par_dict": mock_task_class,
            "generate_control_dict": mock_task_class
        }
        
        # Run a simple workflow
        manager.run_workflow("setup:dict")
        
        # Verify task was called
        assert mock_task_class.called
        assert mock_task_instance.execute.called
        
        # Verify logging
        mock_logger.info.assert_called()
    
    @patch('src.workflow.manager.logger')
    def test_failed_workflow_execution(self, mock_logger, sample_config):
        """Test workflow execution with task failure."""
        manager = WorkflowManager(sample_config)
        
        # Create mock task that fails
        mock_task_class = Mock()
        mock_task_instance = Mock()
        mock_task_instance.execute.return_value = False
        mock_task_class.return_value = mock_task_instance
        
        # Replace available tasks with our mock
        manager.available_tasks = {
            "create_case_structure": mock_task_class
        }
        
        # Run workflow and expect failure
        with pytest.raises(AortaCFDError, match="Workflow aborted due to failure"):
            manager.run_workflow("setup:dict")
        
        # Verify error logging
        mock_logger.error.assert_called()
    
    def test_unregistered_task_error(self, sample_config):
        """Test error when workflow references unregistered task."""
        manager = WorkflowManager(sample_config)
        
        # Clear available tasks
        manager.available_tasks = {}
        
        with pytest.raises(AortaCFDError, match="Task .* is not registered"):
            manager.run_workflow("setup:dict")
    
    def test_context_passing(self, sample_config):
        """Test that context is properly passed between tasks."""
        manager = WorkflowManager(sample_config)
        
        # Create mock tasks that modify context
        def mock_task1_execute(context):
            context["task1_data"] = "test_value"
            return True
        
        def mock_task2_execute(context):
            # Verify context from task1 is available
            assert context["task1_data"] == "test_value"
            context["task2_data"] = "another_value"
            return True
        
        mock_task1_class = Mock()
        mock_task1_instance = Mock()
        mock_task1_instance.execute = mock_task1_execute
        mock_task1_class.return_value = mock_task1_instance
        
        mock_task2_class = Mock()
        mock_task2_instance = Mock()
        mock_task2_instance.execute = mock_task2_execute
        mock_task2_class.return_value = mock_task2_instance
        
        # Create mock task for other required tasks
        mock_task_class = Mock()
        mock_task_instance = Mock()
        mock_task_instance.execute.return_value = True
        mock_task_class.return_value = mock_task_instance
        
        # Replace available tasks
        manager.available_tasks = {
            "create_case_structure": mock_task1_class,
            "generate_mesh_files": mock_task2_class,
            "generate_physical_properties": mock_task_class,
            "generate_numerical_schemes": mock_task_class,
            "generate_solver_settings": mock_task_class,
            "generate_decompose_par_dict": mock_task_class,
            "generate_control_dict": mock_task_class
        }
        
        # Run workflow
        manager.run_workflow("setup:dict")
        
        # Verify context was shared
        assert manager.context["task1_data"] == "test_value"
        assert manager.context["task2_data"] == "another_value"
    
    def test_all_workflow_commands_defined(self, sample_config):
        """Test that all workflow commands are properly defined."""
        manager = WorkflowManager(sample_config)
        
        # List of all expected commands
        expected_commands = [
            "setup:dict",
            "setup:bc", 
            "run:mesh",
            "run:solver",
            "createCase",
            "runAll"
        ]
        
        # Mock all tasks to avoid actual execution
        mock_task_class = Mock()
        mock_task_instance = Mock()
        mock_task_instance.execute.return_value = True
        mock_task_class.return_value = mock_task_instance
        
        # Replace all tasks with mock
        for task_name in manager.available_tasks:
            manager.available_tasks[task_name] = mock_task_class
        
        # Test each command
        for command in expected_commands:
            try:
                manager.run_workflow(command)
            except Exception as e:
                pytest.fail(f"Command '{command}' failed: {e}")
    
    def test_clean_run_flag_handling(self, sample_config):
        """Test handling of clean_run flag in config."""
        # Add clean_run flag to config
        sample_config["clean_run"] = True
        
        manager = WorkflowManager(sample_config)
        
        # Create mock task that checks for clean_run flag
        def mock_task_execute(context):
            # Task should have access to the config with clean_run flag
            assert manager.config["clean_run"] is True
            return True
        
        mock_task_class = Mock()
        mock_task_instance = Mock()
        mock_task_instance.execute = mock_task_execute
        mock_task_class.return_value = mock_task_instance
        
        # Create mock task for other required tasks
        mock_other_task_class = Mock()
        mock_other_task_instance = Mock()
        mock_other_task_instance.execute.return_value = True
        mock_other_task_class.return_value = mock_other_task_instance
        
        manager.available_tasks = {
            "create_case_structure": mock_task_class,
            "generate_mesh_files": mock_other_task_class,
            "generate_physical_properties": mock_other_task_class,
            "generate_numerical_schemes": mock_other_task_class,
            "generate_solver_settings": mock_other_task_class,
            "generate_decompose_par_dict": mock_other_task_class,
            "generate_control_dict": mock_other_task_class
        }
        
        manager.run_workflow("setup:dict")
    
    def test_task_initialization_with_config(self, sample_config):
        """Test that tasks are initialized with config."""
        manager = WorkflowManager(sample_config)
        
        # Create mock task class that records initialization
        mock_task_class = Mock()
        mock_task_instance = Mock()
        mock_task_instance.execute.return_value = True
        mock_task_class.return_value = mock_task_instance
        
        manager.available_tasks = {
            "create_case_structure": mock_task_class,
            "generate_mesh_files": mock_task_class,
            "generate_physical_properties": mock_task_class,
            "generate_numerical_schemes": mock_task_class,
            "generate_solver_settings": mock_task_class,
            "generate_decompose_par_dict": mock_task_class,
            "generate_control_dict": mock_task_class
        }
        
        manager.run_workflow("setup:dict")
        
        # Verify task was initialized with config
        mock_task_class.assert_called_with(sample_config)
    
    @patch('src.workflow.manager.logger')
    def test_workflow_logging(self, mock_logger, sample_config):
        """Test proper logging during workflow execution."""
        manager = WorkflowManager(sample_config)
        
        # Create mock successful task
        mock_task_class = Mock()
        mock_task_instance = Mock()
        mock_task_instance.execute.return_value = True
        mock_task_instance.__class__.__name__ = "TestTask"
        mock_task_class.return_value = mock_task_instance
        
        manager.available_tasks = {
            "create_case_structure": mock_task_class,
            "generate_mesh_files": mock_task_class,
            "generate_physical_properties": mock_task_class,
            "generate_numerical_schemes": mock_task_class,
            "generate_solver_settings": mock_task_class,
            "generate_decompose_par_dict": mock_task_class,
            "generate_control_dict": mock_task_class
        }
        
        manager.run_workflow("setup:dict")
        
        # Check that appropriate log messages were called
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        
        # Should log workflow start and completion
        assert any("Starting workflow" in msg for msg in log_calls)
        assert any("Workflow completed successfully" in msg for msg in log_calls)
        assert any("Executing Task" in msg for msg in log_calls)


class TestWorkflowManagerIntegration:
    """Integration tests for WorkflowManager."""
    
    def test_workflow_recipes_completeness(self, sample_config):
        """Test that all workflow recipes contain valid task sequences."""
        manager = WorkflowManager(sample_config)
        
        # Get all recipes by running each command type
        recipes = {
            "setup:dict": ["create_case_structure", "generate_mesh_files", "generate_physical_properties"],
            "setup:bc": ["prepare_boundary_data", "generate_bc_files"], 
            "run:mesh": ["execute_meshing"],
            "run:solver": ["execute_solver"],
            "createCase": ["create_case_structure", "generate_mesh_files", "execute_meshing"],
            "runAll": ["create_case_structure", "generate_mesh_files", "execute_meshing", "execute_solver"]
        }
        
        for command, expected_tasks in recipes.items():
            # Mock all tasks
            mock_task_class = Mock()
            mock_task_instance = Mock()
            mock_task_instance.execute.return_value = True
            mock_task_class.return_value = mock_task_instance
            
            for task_name in manager.available_tasks:
                manager.available_tasks[task_name] = mock_task_class
            
            # Should not raise any errors
            try:
                manager.run_workflow(command)
            except Exception as e:
                pytest.fail(f"Workflow '{command}' failed: {e}")
    
    def test_task_sequence_order(self, sample_config):
        """Test that tasks are executed in the correct order."""
        manager = WorkflowManager(sample_config)
        
        execution_order = []
        
        def create_mock_task(task_name):
            def mock_execute(context):
                execution_order.append(task_name)
                return True
            
            mock_task_class = Mock()
            mock_task_instance = Mock()
            mock_task_instance.execute = mock_execute
            mock_task_class.return_value = mock_task_instance
            return mock_task_class
        
        # Replace tasks with order-tracking mocks
        for task_name in manager.available_tasks:
            manager.available_tasks[task_name] = create_mock_task(task_name)
        
        # Run a workflow
        manager.run_workflow("setup:dict")
        
        # Verify execution order (should start with case structure creation)
        assert execution_order[0] == "create_case_structure"
        assert "generate_mesh_files" in execution_order
        assert "generate_physical_properties" in execution_order