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

from config.builder import ConfigBuilder, deep_merge
from config.numerics_builder import NumericsBuilder
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
    
    def load_patient_case(self, patient_id: str, config_path: str | None = None) -> dict:
        """Load and validate patient case.

        Args:
            patient_id: Directory name under cases_input.
            config_path: Optional override path to a configuration JSON.
        """
        if not self._is_valid_patient_id(patient_id):
            raise PatientValidationError(f"Invalid patient ID format: {patient_id}")
            
        patient_dir = self.cases_dir / patient_id
        
        # Validate directory
        if not patient_dir.exists():
            raise PatientValidationError(f"Patient directory not found: {patient_id}")
        
        if not patient_dir.is_dir():
            raise PatientValidationError(f"Patient path is not a directory: {patient_id}")
        
        # Load configuration
        if config_path:
            config_file = Path(config_path).expanduser()
            # If not absolute and doesn't exist, try relative to patient directory
            if not config_file.is_absolute() and not config_file.is_file():
                config_file = patient_dir / config_path
            if not config_file.is_file():
                raise PatientValidationError(f"Custom configuration file not found: {config_path}\n"
                                            f"Searched in:\n"
                                            f"  - {Path(config_path).expanduser().absolute()}\n"
                                            f"  - {patient_dir / config_path}")
        else:
            config_file = patient_dir / 'config.json'
            if not config_file.exists():
                raise PatientValidationError(f"Configuration file not found: {config_file}")
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            # Store the config file path for later use (e.g., finding inlet CSV)
            config['_config_file_path'] = str(config_file.resolve())
        except json.JSONDecodeError as e:
            raise PatientConfigurationError(f"Invalid JSON in configuration: {e}")
        except Exception as e:
            raise PatientConfigurationError(f"Error reading configuration: {e}")
        
        # Optional sanity check: ensure patient_id aligns if present in config
        config_patient_id = config.get('case_info', {}).get('patient_id')
        if config_path and config_patient_id and config_patient_id != patient_id:
            self.logger.warning(
                "Custom config patient_id (%s) does not match CLI patient (%s)",
                config_patient_id,
                patient_id,
            )

        # Validate required configuration keys
        # Support both old (simulation_settings) and new (physics + numerics) systems
        has_old_system = 'simulation_settings' in config
        has_new_system = 'physics' in config and 'numerics' in config

        if not has_old_system and not has_new_system:
            raise PatientConfigurationError(
                "Configuration must have either:\n"
                "  OLD SYSTEM: 'simulation_settings' key, OR\n"
                "  NEW SYSTEM: 'physics' and 'numerics' keys\n"
                "See examples/ directory for new config format."
            )

        # Always require case_info and boundary_conditions
        required_keys = ['case_info', 'boundary_conditions']
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise PatientConfigurationError(f"Configuration missing required keys: {missing_keys}")

        # Require NEW format (physics/numerics/mesh)
        if has_old_system:
            raise PatientConfigurationError(
                "OLD config format (simulation_settings) is no longer supported.\n"
                "All configs have been migrated to NEW format (physics/numerics/mesh).\n"
                "Backup of old format saved as: *.json.OLD_FORMAT_BACKUP"
            )

        if not has_new_system:
            raise PatientConfigurationError(
                "Configuration missing NEW format keys: 'physics', 'numerics', 'mesh'.\n"
                "See examples/ directory for config templates."
            )

        # Mark that config uses new system
        config['_uses_new_system'] = True

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
            'config_file': str(config_file.resolve()),
            'stl_files': self._classify_stl_files(stl_files),
            'flow_data': flow_data
        }
    
    def prepare_simulation(self, case_info: dict, options: dict = None) -> dict:
        """
        Prepare simulation configuration using new numerics system.

        All configs (old and new format) are converted to use the new system.
        Old configs are automatically converted in load_patient_case().
        """
        config = case_info['config']

        # All configs now use new system (conversion happens in load_patient_case)
        if config.get('physics') and config.get('numerics'):
            self.logger.info("✨ Using NEW numerics system (physics/numerics/mesh)")
            return self._prepare_simulation_new_system(case_info, options)
        else:
            raise PatientConfigurationError(
                "Config missing physics/numerics keys. "
                "This should have been converted in load_patient_case()."
            )

    def _prepare_simulation_new_system(self, case_info: dict, options: dict = None) -> dict:
        """
        Prepare simulation using NEW numerics system (physics/numerics/mesh).

        This method builds configuration using NumericsBuilder for explicit scheme control,
        bypassing the old ProfileComposer and hardcoded scheme templates.

        Args:
            case_info: Patient case information from load_patient_case()
            options: Optional runtime overrides

        Returns:
            Simulation configuration dictionary with same structure as old system
        """
        config = case_info['config'].copy()

        # Prepare output directories
        patient_output_dir = self.output_dir / case_info['patient_id']
        patient_output_dir.mkdir(parents=True, exist_ok=True)

        # Check if we're resuming from an existing case directory
        if options and options.get('case_dir'):
            case_dir_path = Path(options['case_dir'])
            if case_dir_path.name == 'openfoam':
                run_dir = case_dir_path.parent
            else:
                run_dir = case_dir_path
            self.logger.info(f"Resuming: using existing run directory: {run_dir}")
        elif options and options.get('overwrite'):
            run_dir = patient_output_dir / "latest"
            if run_dir.exists():
                shutil.rmtree(run_dir)
            run_dir.mkdir(exist_ok=True)
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            run_dir = patient_output_dir / f"run_{timestamp}"
            run_dir.mkdir(exist_ok=True)

        # Build numerics configuration from profile
        numerics_builder = NumericsBuilder()
        try:
            numerics_config = numerics_builder.build(config)
            profile_name = config.get('numerics', {}).get('profile', 'standard')
            self.logger.info(f"✅ Loaded numerics profile: {profile_name}")
        except Exception as e:
            raise PatientConfigurationError(f"Failed to build numerics: {e}")

        # Merge base configuration
        builder = ConfigBuilder()

        # Load base config only (no old profiles)
        base_config = builder._load_python_profile('.base', package='src.config')

        # Start with base
        merged_config = {}
        merged_config = deep_merge(merged_config, base_config)

        # Convert and apply case-specific config
        case_specific_config = builder._convert_unified_config(
            case_name=case_info['patient_id'],
            case_config=config
        )
        merged_config = deep_merge(merged_config, case_specific_config)

        # Apply OpenFOAM 12 settings and validation
        merged_config = builder._apply_openfoam_12_settings(merged_config)
        builder._validate_physical_parameters(merged_config)

        # Apply numerics from new system
        merged_config['schemes'] = numerics_config

        # Extract fvSolution settings from numerics (PIMPLE, relaxation, etc.)
        if 'solvers' in numerics_config:
            merged_config['fvSolution'] = numerics_config['solvers']

        # Extract time stepping settings for controlDict
        if 'time_stepping' in numerics_config:
            time_step_settings = numerics_config['time_stepping']
            merged_config.setdefault('simulation_control', {})
            merged_config['simulation_control'].setdefault('controlDict', {})

            # Set initial deltaT and time stepping controls
            merged_config['simulation_control']['controlDict']['deltaT'] = time_step_settings.get('max_delta_t', 0.0001)
            merged_config['simulation_control']['controlDict']['adjustTimeStep'] = 'yes' if time_step_settings.get('adjustable_time_step', True) else 'no'
            merged_config['simulation_control']['controlDict']['maxCo'] = time_step_settings.get('max_co', 1.0)
            merged_config['simulation_control']['controlDict']['maxDeltaT'] = time_step_settings.get('max_delta_t', 0.001)

            # Add other standard controlDict settings
            merged_config['simulation_control']['controlDict']['startFrom'] = 'startTime'
            merged_config['simulation_control']['controlDict']['startTime'] = 0
            merged_config['simulation_control']['controlDict']['stopAt'] = 'endTime'
            merged_config['simulation_control']['controlDict']['writeControl'] = 'adjustableRunTime'
            merged_config['simulation_control']['controlDict']['writeFormat'] = 'binary'
            merged_config['simulation_control']['controlDict']['writePrecision'] = 6
            merged_config['simulation_control']['controlDict']['writeCompression'] = 'off'
            merged_config['simulation_control']['controlDict']['timeFormat'] = 'general'
            merged_config['simulation_control']['controlDict']['timePrecision'] = 6
            merged_config['simulation_control']['controlDict']['runTimeModifiable'] = 'true'

        # Add physics settings (use deep_merge to preserve mapped nu/rho/mu from _apply_openfoam_12_settings)
        if 'physics' not in merged_config:
            merged_config['physics'] = {}
        merged_config['physics'] = deep_merge(merged_config['physics'], config['physics'])

        # Add simulation_type for backward compatibility with BC generation
        # BC setup expects 'simulation_type' with values 'laminar', 'RAS', 'LES'
        # New system uses 'model' with values 'laminar', 'rans', 'les'
        model_to_sim_type = {
            'laminar': 'laminar',
            'rans': 'RAS',
            'les': 'LES'
        }
        merged_config['physics']['simulation_type'] = model_to_sim_type.get(
            config['physics']['model'],
            'laminar'
        )

        # Add mesh settings if provided
        if 'mesh' in config:
            # Ensure mesh.mesh_resolution path exists
            merged_config.setdefault('mesh', {})
            merged_config['mesh'].setdefault('mesh_resolution', {})

            if 'cells_per_diameter' in config['mesh']:
                merged_config['mesh']['mesh_resolution']['cells_per_diameter'] = config['mesh']['cells_per_diameter']
            if 'target_cell_size_mm' in config['mesh']:
                merged_config['mesh']['mesh_resolution']['target_cell_size_mm'] = config['mesh']['target_cell_size_mm']

            # Copy other mesh settings
            for key in ['surface_refinement', 'boundary_layers']:
                if key in config['mesh']:
                    merged_config['mesh'][key] = config['mesh'][key]

        # Apply config settings (boundary conditions, etc.)
        self._apply_config_settings(merged_config, config)

        # Handle writeInterval from user config
        if 'simulation_control' in config and 'writeInterval' in config['simulation_control']:
            merged_config['simulation_control']['controlDict']['writeInterval'] = config['simulation_control']['writeInterval']

        # Store metadata
        merged_config['profile_metadata'] = {
            'system': 'new',
            'physics_model': config['physics']['model'],
            'numerics_profile': profile_name,
            'description': f"{config['physics']['model'].upper()} with {profile_name} numerics",
        }

        if 'mesh' in config:
            merged_config['profile_metadata']['mesh'] = config['mesh']

        # Store config source information
        merged_config['config_source'] = {
            'case_config_file': case_info['config_file'],
            'system': 'new (physics/numerics/mesh)',
            'numerics_profile': profile_name,
        }

        # Preserve config file path for finding related files (e.g., inlet CSV)
        if '_config_file_path' in config:
            merged_config['_config_file_path'] = config['_config_file_path']

        return {
            'config': merged_config,
            'profile_name': f"{config['physics']['model']}_{profile_name}",
            'profile_key': f"{config['physics']['model']}_{profile_name}",
            'run_dir': run_dir,
            'patient_output_dir': patient_output_dir,
            'case_config': case_info['config'],
            'case_config_file': case_info['config_file'],
            'parallel': merged_config['mesh']['SNAPPY_SETTINGS'].get('parallel', False)
        }

    def run_workflow_step(self, sim_config: dict, workflow_step: str = 'runAll', case_dir: str = None) -> bool:
        """Run specific workflow step.

        Args:
            sim_config: Simulation configuration dictionary
            workflow_step: Workflow command to execute
            case_dir: Optional existing case directory (for post-processing old cases)
        """
        try:
            manager = WorkflowManager(sim_config['config'])

            # Use existing case directory if provided, otherwise create new
            if case_dir:
                openfoam_dir = Path(case_dir)
                if not openfoam_dir.exists():
                    raise PatientSimulationError(f"Case directory not found: {case_dir}")
                self.logger.info(f"Using existing case directory: {openfoam_dir}")
            else:
                # Setup new case directory
                run_dir = sim_config['run_dir']
                openfoam_dir = run_dir / "openfoam"
                openfoam_dir.mkdir(parents=True, exist_ok=True)

            # Set context
            manager.context['case_directory'] = str(openfoam_dir)
            manager.context['patient_name'] = sim_config['config'].get('case_info', {}).get('patient_id',
                                                                                            sim_config['config'].get('geometry', {}).get('case_name', 'unknown'))

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
        results_dir.mkdir(exist_ok=True)

        # NOTE: Logs are kept in openfoam/logs/ directory (created by run_command)
        # No need to duplicate them at run_dir/logs/

        # Create basic summary file
        summary = {
            'patient_id': patient_id,
            'run_directory': str(run_dir),
            'analysis_completed': datetime.now().isoformat()
        }

        # Add log location information
        openfoam_dir = Path(sim_config.get('output_directory', ''))
        if openfoam_dir.exists():
            openfoam_logs = openfoam_dir / "logs"
            if openfoam_logs.exists():
                summary['logs_location'] = str(openfoam_logs.relative_to(run_dir))

        with open(run_dir / 'summary.json', 'w') as f:
            json.dump(summary, f, indent=2)


        return str(run_dir)
    
    def list_available_patients(self) -> list:
        """List all available patient cases."""
        if not self.cases_dir.exists():
            return []
        
        patients = []
        for item in self.cases_dir.iterdir():
            if item.is_dir():
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

        # Apply computational settings while respecting explicit mesh overrides
        comp = case_config.get('computational', {})
        mesh_overrides = case_config.get('mesh', {}).get('SNAPPY_SETTINGS', {})
        snappy_config = config.setdefault('mesh', {}).setdefault('SNAPPY_SETTINGS', {})

        if 'parallel' in mesh_overrides:
            snappy_config['parallel'] = mesh_overrides['parallel']
        else:
            if comp.get('parallel') is True:
                snappy_config['parallel'] = True
            elif comp.get('parallel') is False:
                snappy_config['parallel'] = False

        if 'nProcessors' in mesh_overrides:
            snappy_config['nProcessors'] = mesh_overrides['nProcessors']
        elif comp.get('parallel') is True and 'max_processors' in comp and comp['max_processors'] != 'auto':
            snappy_config['nProcessors'] = comp['max_processors']

        # Convert NEW config format (mesh.boundary_layers, mesh.surface_refinement) to SNAPPY_SETTINGS
        # This allows users to write human-friendly configs that get mapped to OpenFOAM parameters
        mesh_config = case_config.get('mesh', {})

        # Handle boundary_layers settings - traditional OpenFOAM addLayersControls style
        # Maps user-friendly config keys to SNAPPY_SETTINGS
        boundary_layers = mesh_config.get('boundary_layers', {})

        # enabled -> addLayers
        if 'enabled' in boundary_layers:
            snappy_config['addLayers'] = boundary_layers['enabled']
            self.logger.info(f"🔧 Mapped mesh.boundary_layers.enabled={boundary_layers['enabled']} → SNAPPY_SETTINGS.addLayers")

        # num_layers -> addLayer (nSurfaceLayers)
        num_layers = boundary_layers.get('num_layers') or boundary_layers.get('n_surface_layers')
        if num_layers is not None:
            snappy_config['addLayer'] = num_layers
            self.logger.info(f"🔧 Mapped mesh.boundary_layers.num_layers={num_layers} → SNAPPY_SETTINGS.addLayer (nSurfaceLayers)")

        # expansion_ratio -> expansionRatio (also accept camelCase)
        expansion_ratio = boundary_layers.get('expansion_ratio') or boundary_layers.get('expansionRatio')
        if expansion_ratio is not None:
            snappy_config['expansionRatio'] = expansion_ratio
            self.logger.info(f"🔧 Mapped mesh.boundary_layers.expansion_ratio={expansion_ratio} → SNAPPY_SETTINGS.expansionRatio")

        # final_layer_thickness -> finalLayerThickness (relative, when relativeSizes=true)
        # Also accept camelCase 'finalLayerThickness' for backward compatibility
        final_layer_thickness = boundary_layers.get('final_layer_thickness') or boundary_layers.get('finalLayerThickness')
        if final_layer_thickness is not None:
            snappy_config['finalLayerThickness'] = final_layer_thickness
            snappy_config['relativeSizes'] = True  # Ensure relative sizing mode
            self.logger.info(
                f"🔧 Mapped mesh.boundary_layers.final_layer_thickness={final_layer_thickness} "
                f"→ SNAPPY_SETTINGS.finalLayerThickness (relativeSizes=true)"
            )

        # min_thickness -> minThickness
        if 'min_thickness' in boundary_layers:
            snappy_config['minThickness'] = boundary_layers['min_thickness']
            self.logger.info(f"🔧 Mapped mesh.boundary_layers.min_thickness={boundary_layers['min_thickness']} → SNAPPY_SETTINGS.minThickness")

        # relativeSizes option (default: true)
        if 'relativeSizes' in boundary_layers:
            snappy_config['relativeSizes'] = boundary_layers['relativeSizes']
            self.logger.info(f"🔧 Mapped mesh.boundary_layers.relativeSizes={boundary_layers['relativeSizes']} → SNAPPY_SETTINGS.relativeSizes")

        # Handle surface refinement configuration
        # surfaceRefinementLevels: [min, max] direct snappy levels in SNAPPY_SETTINGS
        # Also support legacy mesh.surface_refinement.levels for backward compatibility
        surface_refinement = mesh_config.get('surface_refinement', {})

        if 'surfaceRefinementLevels' in snappy_config:
            # Already set in SNAPPY_SETTINGS - use as-is
            levels = snappy_config['surfaceRefinementLevels']
            self.logger.info(f"surfaceRefinementLevels: {levels}")
        elif 'levels' in surface_refinement:
            # LEGACY: mesh.surface_refinement.levels for backward compatibility
            levels = surface_refinement['levels']
            if isinstance(levels, list) and len(levels) == 2:
                snappy_config['surfaceRefinementLevels'] = levels
                self.logger.info(f"Mapped mesh.surface_refinement.levels={levels} → SNAPPY_SETTINGS.surfaceRefinementLevels")

    def _resolve_profile_choice(self, simulation_settings: dict, options: dict, catalog: dict):
        """
        Resolve profile selection from solver/analysis settings and options.
        Simplified logic with clear fallback chain and helpful error messages.
        """
        options = options or {}

        # Priority 1: CLI --profile override
        if options.get('profile'):
            profile_key = options['profile']
            if profile_key in catalog:
                return profile_key, catalog[profile_key].copy(), None
            # Give helpful error with available profiles
            available = ', '.join(sorted(catalog.keys()))
            raise PatientConfigurationError(
                f"Unknown profile override: '{profile_key}'\n"
                f"Available profiles: {available}"
            )

        # Get solver and analysis type from config
        solver_type = str(simulation_settings.get('solver_type', 'laminar') or 'laminar').strip().lower()
        analysis_type = simulation_settings.get('analysis_type', 'medium')
        analysis_type = 'medium' if analysis_type is None else str(analysis_type).strip().lower()

        # Priority 2: Try direct profile key (sim_solver_analysis)
        profile_key = f"sim_{solver_type}_{analysis_type}"
        if profile_key in catalog:
            # Check for variant overrides (e.g., "publication")
            profile_data = catalog[profile_key].copy()
            variants = profile_data.get('variants', {})

            # Check if analysis_type itself is a variant
            if analysis_type in variants:
                variant_overrides = variants[analysis_type].copy()
                variant_label = variant_overrides.pop('variant_label', analysis_type)
                profile_data.update(variant_overrides)
                return profile_key, profile_data, variant_label

            return profile_key, profile_data, None

        # Priority 3: Legacy alias support (for backward compatibility)
        legacy_map = {
            'draft': 'sim_laminar_coarse',
            'quick': 'sim_laminar_coarse',
            'clinical': 'sim_laminar_medium',
            'standard': 'sim_laminar_medium',
            'high_resolution': 'sim_laminar_fine',
            'coarse': 'sim_laminar_coarse',
            'medium': 'sim_laminar_medium',
            'fine': 'sim_laminar_fine',
        }

        if analysis_type in legacy_map:
            legacy_key = legacy_map[analysis_type]
            if legacy_key in catalog:
                self.logger.info(
                    f"Using legacy alias '{analysis_type}' → '{legacy_key}'"
                )
                return legacy_key, catalog[legacy_key].copy(), None

        # Priority 4: Fallback with clear warning
        fallback_key = f"sim_{solver_type}_medium"
        if fallback_key not in catalog:
            fallback_key = 'sim_laminar_medium'

        available_profiles = '\n  '.join(sorted(catalog.keys()))
        self.logger.warning(
            f"⚠️  Could not find profile for solver='{solver_type}', analysis='{analysis_type}'.\n"
            f"   Attempted: '{profile_key}'\n"
            f"   Falling back to: '{fallback_key}'\n"
            f"   Available profiles:\n  {available_profiles}"
        )

        return fallback_key, catalog[fallback_key].copy(), None

    def _profile_catalog(self) -> dict:
        """Define all available simulation profiles and metadata."""
        publication_overrides = {
            'variant_label': 'publication',
            'display_name': 'RANS Fine (Aggressive)',
            'solver_recipe_fragment': 'aggressive',
            'solver_recipe_label': 'aggressive',
            'estimated_time': '4-8 hours',
            'max_CFL': 1.0,
            'description': 'Publication-grade RANS fine configuration with aggressive PIMPLE outer loops',
            'details': 'Second-order accurate, very fine mesh, tight residual control',
            'use_case': 'High-quality turbulence publication',
            'mesh_resolution': 25,
        }

        les_publication_overrides = {
            'variant_label': 'publication',
            'display_name': 'LES Fine (Aggressive)',
            'solver_recipe_fragment': 'aggressive',
            'solver_recipe_label': 'aggressive',
            'estimated_time': '6-10 hours',
            'max_CFL': 0.5,
            'description': 'Publication-grade LES fine configuration with aggressive PIMPLE iterations',
            'details': 'WALE LES with aggressive solver control on a fine mesh',
            'use_case': 'Highest fidelity LES publication work',
            'mesh_resolution': 25,
        }

        return {
            'sim_laminar_coarse': {
                'base_profile': 'sim_laminar_coarse',
                'display_name': 'Laminar Coarse',
                'solver_type': 'laminar',
                'analysis_level': 'coarse',
                'mesh_resolution': 10,
                'resolution_fragment': 'coarse',
                'solver_recipe_fragment': 'robust',
                'solver_recipe_label': 'robust',
                'max_CFL': 0.5,
                'estimated_time': '5-10 minutes',
                'use_case': 'Quick preliminary check',
                'details': 'First-order numerics, coarse mesh, very stable',
                'description': 'Coarse laminar warm-up run',
                'aliases': ['laminar:coarse', 'coarse', 'draft', 'quick'],
                'variants': {}
            },
            'sim_laminar_medium': {
                'base_profile': 'sim_laminar_medium',
                'display_name': 'Laminar Medium',
                'solver_type': 'laminar',
                'analysis_level': 'medium',
                'mesh_resolution': 15,
                'resolution_fragment': 'medium',
                'solver_recipe_fragment': 'balanced',
                'solver_recipe_label': 'balanced',
                'max_CFL': 0.8,
                'estimated_time': '30-60 minutes',
                'use_case': 'Routine clinical decision support',
                'details': 'Second-order accurate numerics with medium mesh for good fidelity',
                'description': 'Clinical laminar configuration',
                'aliases': ['laminar:medium', 'medium', 'clinical', 'standard'],
                'variants': {}
            },
            'sim_laminar_fine': {
                'base_profile': 'sim_laminar_fine',
                'display_name': 'Laminar Fine',
                'solver_type': 'laminar',
                'analysis_level': 'fine',
                'mesh_resolution': 20,
                'resolution_fragment': 'fine',
                'solver_recipe_fragment': 'aggressive',
                'solver_recipe_label': 'aggressive',
                'max_CFL': 1.0,
                'estimated_time': '2-4 hours',
                'use_case': 'High-resolution laminar studies',
                'details': 'Maximum accuracy with fine mesh and pure 2nd-order schemes',
                'description': 'High resolution laminar analysis',
                'aliases': ['laminar:fine', 'fine', 'high_resolution'],
                'variants': {}
            },
            'sim_rans_coarse': {
                'base_profile': 'sim_rans_coarse',
                'display_name': 'RANS Coarse',
                'solver_type': 'rans',
                'analysis_level': 'coarse',
                'mesh_resolution': 16,
                'resolution_fragment': 'coarse',
                'solver_recipe_fragment': 'robust',
                'solver_recipe_label': 'robust',
                'max_CFL': 0.7,
                'estimated_time': '1-2 hours',
                'use_case': 'Fast turbulence screening',
                'details': 'Stabilized turbulence start-up on coarse mesh',
                'description': 'Entry-level RANS configuration',
                'aliases': ['rans:coarse', 'rans_coarse'],
                'variants': {}
            },
            'sim_rans_medium': {
                'base_profile': 'sim_rans_medium',
                'display_name': 'RANS Medium',
                'solver_type': 'rans',
                'analysis_level': 'medium',
                'mesh_resolution': 18,
                'resolution_fragment': 'medium',
                'solver_recipe_fragment': 'balanced',
                'solver_recipe_label': 'balanced',
                'max_CFL': 0.8,
                'estimated_time': '2-3 hours',
                'use_case': 'Accurate turbulence simulations',
                'details': 'Second-order accurate with 2 outer correctors for good turbulence resolution',
                'description': 'Accurate RANS configuration',
                'aliases': ['rans:medium', 'rans_medium'],
                'variants': {}
            },
            'sim_rans_fine': {
                'base_profile': 'sim_rans_fine',
                'display_name': 'RANS Fine',
                'solver_type': 'rans',
                'analysis_level': 'fine',
                'mesh_resolution': 22,
                'resolution_fragment': 'fine',
                'solver_recipe_fragment': 'aggressive',
                'solver_recipe_label': 'aggressive',
                'max_CFL': 1.0,
                'estimated_time': '3-5 hours',
                'use_case': 'Research-grade turbulence modeling',
                'details': 'Maximum accuracy with pure 2nd-order schemes and tight tolerances for publication quality',
                'description': 'Research-quality RANS configuration',
                'aliases': ['rans:fine', 'rans_fine', 'research', 'publication'],
                'variants': {
                    'publication': publication_overrides,
                    'rans:publication': publication_overrides,
                }
            },
            'sim_les_medium': {
                'base_profile': 'sim_les_medium',
                'display_name': 'LES Medium',
                'solver_type': 'les',
                'analysis_level': 'medium',
                'mesh_resolution': 20,
                'resolution_fragment': 'medium',
                'solver_recipe_fragment': 'balanced',
                'solver_recipe_label': 'balanced',
                'max_CFL': 0.5,
                'estimated_time': '3-5 hours',
                'use_case': 'Transitional flow LES studies',
                'details': 'WALE LES with 2nd-order accurate schemes and 2 outer correctors',
                'description': 'Accurate LES configuration',
                'aliases': ['les:medium', 'les_medium'],
                'variants': {}
            },
            'sim_les_fine': {
                'base_profile': 'sim_les_fine',
                'display_name': 'LES Fine',
                'solver_type': 'les',
                'analysis_level': 'fine',
                'mesh_resolution': 25,
                'resolution_fragment': 'fine',
                'solver_recipe_fragment': 'aggressive',
                'solver_recipe_label': 'aggressive',
                'max_CFL': 0.5,
                'estimated_time': '5-7 hours',
                'use_case': 'High-fidelity LES simulations',
                'details': 'WALE LES with maximum accuracy (pure 2nd-order central schemes, tight tolerances)',
                'description': 'High fidelity LES configuration',
                'aliases': ['les:fine', 'les_fine', 'les_publication'],
                'variants': {
                    'les:publication': les_publication_overrides,
                    'publication': les_publication_overrides,
                }
            }
        }

    def get_available_profiles(self) -> dict:
        """Expose available simulation profiles in a user-friendly format."""
        catalog = self._profile_catalog()
        profiles = {}
        for key, data in catalog.items():
            config_summary = f"{data['analysis_level'].capitalize()}/{data['solver_type'].upper()}/{data['solver_recipe_label'].capitalize()}"
            profiles[key] = {
                'name': data['display_name'],
                'time': data['estimated_time'],
                'config': config_summary,
                'use_case': data['use_case'],
                'details': data['details'],
            }
        return profiles

    def display_profile_selection(self):
        """Print a catalog of profiles for interactive selection."""
        catalog = self._profile_catalog()
        profiles = self.get_available_profiles()

        print("\n" + "=" * 70)
        print("SIMULATION PROFILE SELECTION")
        print("=" * 70)
        print("\nSelect by combining solver_type with analysis_type (coarse | medium | fine | publication)\n")
        print("-" * 70)

        for idx, (profile_key, data) in enumerate(catalog.items(), 1):
            profile = profiles[profile_key]
            print(f"{idx}. {profile['name']:<18} | Time: {profile['time']:<12} | {profile['config']}")
            print(f"   └─ {profile['use_case']}")
            print(f"      ({profile['details']})")
            variants = data.get('variants', {})
            if variants:
                available_variants = sorted({v.get('variant_label', alias) for alias, v in variants.items()})
                print(f"      Variants: {', '.join(available_variants)}")
            print(f"   [Key: {profile_key}]")
            print()

        print("-" * 70)
        print("Example: solver_type=laminar, analysis_type=medium → sim_laminar_medium")
        print("         solver_type=rans, analysis_type=publication → RANS fine (aggressive)")

        return profiles
