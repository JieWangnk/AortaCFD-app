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
from config.profiles import ProfileComposer
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
            'config_file': str(config_file.resolve()),
            'stl_files': self._classify_stl_files(stl_files),
            'flow_data': flow_data
        }
    
    def prepare_simulation(self, case_info: dict, options: dict = None) -> dict:
        """Prepare simulation configuration with fragment-based profiles."""
        config = case_info['config']

        catalog = self._profile_catalog()
        profile_key, profile_data, variant_label = self._resolve_profile_choice(
            config.get('simulation_settings', {}),
            options,
            catalog
        )

        profile_name = profile_data['base_profile']

        # Allow user overrides for solver recipe and mesh resolution
        if options:
            if 'solver_recipe' in options:
                profile_data['solver_recipe_fragment'] = options['solver_recipe']
                profile_data['solver_recipe_label'] = options['solver_recipe']
            elif 'numerical_schemes' in options:
                profile_data['solver_recipe_fragment'] = options['numerical_schemes']
                profile_data['solver_recipe_label'] = options['numerical_schemes']
            if 'mesh_resolution' in options:
                profile_data['mesh_resolution'] = options['mesh_resolution']

        # Prepare output directories
        patient_output_dir = self.output_dir / case_info['patient_id']
        patient_output_dir.mkdir(parents=True, exist_ok=True)

        if options and options.get('overwrite'):
            run_dir = patient_output_dir / "latest"
            if run_dir.exists():
                shutil.rmtree(run_dir)
            run_dir.mkdir(exist_ok=True)
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            run_dir = patient_output_dir / f"run_{timestamp}"
            run_dir.mkdir(exist_ok=True)

        builder = ConfigBuilder()

        # Step 1: Build base + profile (without case-specific overrides)
        base_and_profile = builder.build_base_and_profile(sim_profile_name=profile_name)

        # Step 2: Merge fragments (after base+profile, before case config)
        composer = ProfileComposer()
        fragment_config = composer.compose(
            spatial_resolution=profile_data.get('resolution_fragment'),
            solver_recipe=profile_data.get('solver_recipe_fragment'),
        )
        if fragment_config:
            merged_config = deep_merge(base_and_profile, fragment_config)
        else:
            merged_config = base_and_profile

        # Step 3: Convert and apply case-specific config (user overrides win!)
        case_specific_config = builder._convert_unified_config(
            case_name=case_info['patient_id'],
            case_config=case_info['config']
        )
        merged_config = deep_merge(merged_config, case_specific_config)

        # Step 4: Apply OpenFOAM 12 settings and validation
        merged_config = builder._apply_openfoam_12_settings(merged_config)
        builder._validate_physical_parameters(merged_config)

        merged_config.setdefault('simulation_settings', {})
        merged_config['simulation_settings']['selected_profile_key'] = profile_key
        merged_config['simulation_settings']['solver_type'] = profile_data['solver_type']
        merged_config['simulation_settings']['analysis_level'] = profile_data['analysis_level']
        if variant_label:
            merged_config['simulation_settings']['profile_variant'] = variant_label

        self._apply_config_settings(merged_config, case_info['config'])
        self._apply_numerical_schemes(merged_config, profile_data)

        merged_config['profile_metadata'] = {
            'profile_key': profile_key,
            'display_name': profile_data['display_name'],
            'solver_type': profile_data['solver_type'],
            'analysis_level': profile_data['analysis_level'],
            'variant': variant_label,
            'description': profile_data['description'],
            'estimated_time': profile_data['estimated_time'],
            'solver_recipe': profile_data.get('solver_recipe_label'),
            'numerical_schemes': profile_data.get('solver_recipe_label'),
            'mesh_resolution': profile_data['mesh_resolution'],
            'fragments': merged_config.get('profile_fragments', []),
            'use_case': profile_data['use_case'],
            'details': profile_data['details'],
            'max_CFL': profile_data.get('max_CFL'),
        }

        return {
            'config': merged_config,
            'profile_name': profile_name,
            'profile_key': profile_key,
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

    def _apply_numerical_schemes(self, config: dict, profile_data: dict):
        """Apply numerical scheme templates unless overridden by fragments."""
        if any(
            fragment.get("axis") == "solver_recipe"
            for fragment in config.get("profile_fragments", [])
        ):
            self.logger.info("Solver recipe fragment applied; skipping numerical scheme overrides.")
            return

        schemes_type = profile_data.get('solver_recipe_label', 'balanced')

        schemes_templates = {
            'stable': {
                'ddtSchemes': {
                    'default': 'Euler'
                },
                'gradSchemes': {
                    'default': 'cellLimited Gauss linear 1',
                    'grad(U)': 'cellLimited Gauss linear 1'
                },
                'divSchemes': {
                    'default': 'none',
                    'div(phi,U)': 'Gauss upwind',
                    'div(phi,k)': 'Gauss upwind',
                    'div(phi,omega)': 'Gauss upwind',
                    'div((nuEff*dev2(T(grad(U)))))': 'Gauss linear'
                },
                'laplacianSchemes': {
                    'default': 'Gauss linear limited 0.5'
                },
                'interpolationSchemes': {
                    'default': 'linear'
                },
                'snGradSchemes': {
                    'default': 'limited 0.5'
                }
            },
            'balanced': {
                'ddtSchemes': {
                    'default': 'CrankNicolson 0.9'
                },
                'gradSchemes': {
                    'default': 'cellLimited Gauss linear 0.5',
                    'grad(U)': 'cellLimited Gauss linear 1'
                },
                'divSchemes': {
                    'default': 'none',
                    'div(phi,U)': 'Gauss linearUpwindV grad(U)',
                    'div(phi,k)': 'Gauss linearUpwind default',
                    'div(phi,omega)': 'Gauss linearUpwind default',
                    'div((nuEff*dev2(T(grad(U)))))': 'Gauss linear'
                },
                'laplacianSchemes': {
                    'default': 'Gauss linear limited 1'
                },
                'interpolationSchemes': {
                    'default': 'linear'
                },
                'snGradSchemes': {
                    'default': 'limited 1'
                }
            },
            'accurate': {
                'ddtSchemes': {
                    'default': 'CrankNicolson 0.7'
                },
                'gradSchemes': {
                    'default': 'Gauss leastSquares'
                },
                'divSchemes': {
                    'default': 'none',
                    'div(phi,U)': 'Gauss linear',
                    'div(phi,k)': 'Gauss limitedLinear 1',
                    'div(phi,omega)': 'Gauss limitedLinear 1',
                    'div((nuEff*dev2(T(grad(U)))))': 'Gauss linear'
                },
                'laplacianSchemes': {
                    'default': 'Gauss linear limited 1'
                },
                'interpolationSchemes': {
                    'default': 'linear'
                },
                'snGradSchemes': {
                    'default': 'limited 1'
                }
            }
        }

        selected_schemes = schemes_templates.get(schemes_type, schemes_templates['balanced'])

        config.setdefault('schemes', {})
        config['schemes'].update(selected_schemes)

        if 'solver' in config:
            if schemes_type == 'stable':
                config['solver']['convergence_criteria'] = 1e-4
                config['solver']['max_iterations'] = 500
            elif schemes_type == 'accurate':
                config['solver']['convergence_criteria'] = 1e-6
                config['solver']['max_iterations'] = 1500
            else:
                config['solver']['convergence_criteria'] = 1e-5
                config['solver']['max_iterations'] = 1000

        max_cfl = profile_data.get('max_CFL', 1.0)
        config.setdefault('time_stepping', {})
        config['time_stepping']['maxCo'] = max_cfl

        self.logger.info(f"Applied numerical schemes: {schemes_type}")
        self.logger.info(f"Max CFL number: {max_cfl}")

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
                'max_CFL': 1.0,
                'estimated_time': '30-60 minutes',
                'use_case': 'Routine clinical decision support',
                'details': 'Second-order bounded numerics with a medium mesh',
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
                'solver_recipe_fragment': 'balanced',
                'solver_recipe_label': 'balanced',
                'max_CFL': 1.5,
                'estimated_time': '2-4 hours',
                'use_case': 'High-resolution laminar studies',
                'details': 'Second-order bounded numerics with fine mesh control',
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
                'max_CFL': 1.0,
                'estimated_time': '2-3 hours',
                'use_case': 'Balanced turbulence simulations',
                'details': 'Balanced PIMPLE recipe with medium resolution turbulence mesh',
                'description': 'Balanced RANS configuration',
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
                'solver_recipe_fragment': 'balanced',
                'solver_recipe_label': 'balanced',
                'max_CFL': 1.5,
                'estimated_time': '3-5 hours',
                'use_case': 'Research-grade turbulence modeling',
                'details': 'Balanced PIMPLE control with fine turbulence mesh',
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
                'details': 'WALE LES with balanced solver recipe on a medium mesh',
                'description': 'Medium fidelity LES configuration',
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
                'solver_recipe_fragment': 'balanced',
                'solver_recipe_label': 'balanced',
                'max_CFL': 0.5,
                'estimated_time': '5-7 hours',
                'use_case': 'High-fidelity LES simulations',
                'details': 'WALE LES on a fine mesh with balanced solver settings',
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
