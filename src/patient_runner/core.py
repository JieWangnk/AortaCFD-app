"""
Core PatientCaseRunner - Clean, focused patient simulation runner
"""

import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

# Add src to path for imports
src_path = str(Path(__file__).parent.parent)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from config.builder import ConfigBuilder
from workflow.manager import WorkflowManager  
from aortacfd_lib.utils.logger import Logger


class PatientValidationError(Exception):
    """Raised when patient case validation fails."""
    pass

class PatientConfigurationError(Exception):
    """Raised when patient configuration is invalid."""
    pass

class PatientSimulationError(Exception):
    """Raised when patient simulation fails."""
    pass


class PatientCaseRunner:
    """
    Clean patient case runner for CFD simulations.
    
    Handles patient case validation, configuration, and workflow execution.
    """
    
    def __init__(self):
        self.logger = Logger("PatientCaseRunner").get_logger()
        self.cases_dir = Path('cases_input')
        self.output_dir = Path('output')
        
    def run_patient_case(self, patient_id: str, options: dict = None) -> str:
        """
        Run CFD analysis for a patient case.
        
        Args:
            patient_id: Patient identifier (e.g., 'patient1', 'patient2')
            options: Optional overrides including workflow_step
        
        Returns:
            Path to results directory
        """
        # Validate and load patient case
        case_info = self.load_patient_case(patient_id)
        
        # Prepare simulation configuration  
        sim_config = self.prepare_simulation(case_info, options)
        
        # Run the specified workflow step
        workflow_step = options.get('workflow_step', 'runAll') if options else 'runAll'
        success = self.run_workflow_step(sim_config, workflow_step)
        
        if not success:
            raise PatientSimulationError("Simulation workflow failed")
        
        # Generate results summary
        results_path = self.generate_results_summary(case_info, sim_config)
        
        return results_path
    
    def load_patient_case(self, patient_id: str) -> dict:
        """Load and validate patient case."""
        if not self._is_valid_patient_id(patient_id):
            raise PatientValidationError(f"Invalid patient ID format: {patient_id}")
            
        patient_dir = self.cases_dir / patient_id
        
        # Validate directory
        if not patient_dir.exists():
            raise PatientValidationError(f"Patient directory not found: {patient_id}")
        
        if not patient_dir.is_dir():
            raise PatientValidationError(f"Patient path is not a directory: {patient_id}")
        
        # Load configuration
        config_file = patient_dir / 'config.json'
        if not config_file.exists():
            raise PatientValidationError(f"Configuration file not found: {config_file}")
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise PatientConfigurationError(f"Invalid JSON in configuration: {e}")
        except Exception as e:
            raise PatientConfigurationError(f"Error reading configuration: {e}")
        
        # Validate required configuration keys
        required_keys = ['case_info', 'simulation_settings', 'boundary_conditions']
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise PatientConfigurationError(f"Configuration missing required keys: {missing_keys}")
        
        # Find STL files
        stl_files = list(patient_dir.glob('*.stl'))
        if not stl_files:
            raise PatientValidationError("No STL files found in patient directory")
        
        # Find flow data
        flow_files = list(patient_dir.glob('*.csv'))
        flow_data = flow_files[0] if flow_files else None
        
        return {
            'patient_id': patient_id,
            'patient_dir': patient_dir,
            'config': config,
            'stl_files': self._classify_stl_files(stl_files),
            'flow_data': flow_data
        }
    
    def prepare_simulation(self, case_info: dict, options: dict = None) -> dict:
        """Prepare simulation configuration."""
        config = case_info['config']
        
        # Determine profile
        analysis_type = config['simulation_settings']['analysis_type']
        profile_map = {
            'quick': 'sim_laminar_coarse',
            'standard': 'sim_laminar_coarse', 
            'high_resolution': 'sim_laminar_fine',
            'publication': 'sim_laminar_fine'
        }
        profile_name = profile_map.get(analysis_type, 'sim_laminar_coarse')
        
        # Override with options
        if options:
            profile_name = options.get('profile', profile_name)
        
        # Create output directory
        patient_output_dir = self.output_dir / case_info['patient_id']
        patient_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create run directory (with or without timestamp)
        if options and options.get('overwrite'):
            run_dir = patient_output_dir / "latest"
            if run_dir.exists():
                shutil.rmtree(run_dir)
            run_dir.mkdir(exist_ok=True)
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            run_dir = patient_output_dir / f"run_{timestamp}"
            run_dir.mkdir(exist_ok=True)
        
        # Build configuration
        builder = ConfigBuilder()
        merged_config = builder.build_with_case_config(
            case_name=case_info['patient_id'], 
            sim_profile_name=profile_name,
            case_config=case_info['config']
        )
        
        # Apply case-specific settings
        self._apply_config_settings(merged_config, case_info['config'])
        
        return {
            'config': merged_config,
            'profile_name': profile_name,
            'run_dir': run_dir,
            'patient_output_dir': patient_output_dir,
            'case_config': case_info['config'],
            'parallel': merged_config['mesh']['SNAPPY_SETTINGS'].get('parallel', False)
        }
    
    def run_workflow_step(self, sim_config: dict, workflow_step: str = 'runAll') -> bool:
        """Run specific workflow step."""
        try:
            manager = WorkflowManager(sim_config['config'])
            
            # Setup case directory
            run_dir = sim_config['run_dir']
            openfoam_dir = run_dir / "openfoam"
            openfoam_dir.mkdir(parents=True, exist_ok=True)
            
            # Set context
            manager.context['case_directory'] = str(openfoam_dir)
            
            # Execute workflow step
            manager.run_workflow(workflow_step)
            
            sim_config['output_directory'] = str(openfoam_dir)
            return True
            
        except Exception as e:
            self.logger.error(f"Workflow step '{workflow_step}' failed: {e}")
            return False
    
    def generate_results_summary(self, case_info: dict, sim_config: dict) -> str:
        """Generate results summary and organization."""
        run_dir = sim_config['run_dir']
        patient_id = case_info['patient_id']
        
        # Create basic results structure
        results_dir = run_dir / "results"
        logs_dir = run_dir / "logs"
        
        results_dir.mkdir(exist_ok=True)
        logs_dir.mkdir(exist_ok=True)
        
        # Copy logs if they exist
        openfoam_dir = Path(sim_config.get('output_directory', ''))
        if openfoam_dir.exists():
            openfoam_logs = openfoam_dir / "logs"
            if openfoam_logs.exists():
                shutil.copytree(openfoam_logs, logs_dir / "openfoam", dirs_exist_ok=True)
        
        # Create basic summary file
        summary = {
            'patient_id': patient_id,
            'run_directory': str(run_dir),
            'analysis_completed': datetime.now().isoformat()
        }
        
        with open(run_dir / 'summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        return str(run_dir)
    
    def list_available_patients(self) -> list:
        """List all available patient cases."""
        if not self.cases_dir.exists():
            return []
        
        patients = []
        for item in self.cases_dir.iterdir():
            if item.is_dir() and item.name.startswith('patient'):
                # Check if it has required files
                stl_files = list(item.glob('*.stl'))
                config_file = item / 'config.json'
                
                if stl_files and config_file.exists():
                    patients.append(item.name)
        
        return sorted(patients)
    
    # Helper methods
    def _is_valid_patient_id(self, patient_id: str) -> bool:
        """Validate patient ID format and safety."""
        if not patient_id or len(patient_id) > 50:
            return False
        if not patient_id.replace('_', '').replace('-', '').isalnum():
            return False
        if '..' in patient_id or '/' in patient_id or '\\\\' in patient_id:
            return False
        return True
    
    def _classify_stl_files(self, stl_files: list) -> dict:
        """Classify STL files by type."""
        classified = {}
        outlets = []
        
        for stl_file in stl_files:
            name = stl_file.stem.lower()
            
            if name == 'inlet' or 'inlet' in name:
                classified['inlet'] = stl_file
            elif name == 'wall_aorta' or 'wall' in name or 'aorta' in name:
                classified['wall_aorta'] = stl_file
            elif name.startswith('outlet') or 'outlet' in name:
                outlets.append(stl_file)
        
        # Number outlets
        for i, outlet in enumerate(sorted(outlets), 1):
            classified[f'outlet{i}'] = outlet
        
        return classified
    
    def _apply_config_settings(self, config: dict, case_config: dict):
        """Apply case-specific configuration settings."""
        # Apply physics settings
        physics = case_config.get('physics', {})
        if 'blood_density' in physics:
            config['physics']['default_density'] = physics['blood_density']
        if 'blood_viscosity' in physics:
            config['physics']['default_viscosity'] = physics['blood_viscosity']
        
        # Apply computational settings  
        comp = case_config.get('computational', {})
        if comp.get('parallel') == True:
            config['mesh']['SNAPPY_SETTINGS']['parallel'] = True
            if 'max_processors' in comp and comp['max_processors'] != 'auto':
                config['mesh']['SNAPPY_SETTINGS']['nProcessors'] = comp['max_processors']
        elif comp.get('parallel') == "auto":
            # Keep profile's parallel setting
            pass
        elif comp.get('parallel') == False:
            config['mesh']['SNAPPY_SETTINGS']['parallel'] = False