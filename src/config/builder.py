import os
import re
import json
import collections.abc
import importlib
import logging

def deep_merge(destination: dict, source: dict) -> dict:
    """Recursively merges the source dictionary into the destination dictionary."""
    for key, value in source.items():
        if isinstance(value, collections.abc.Mapping):
            node = destination.setdefault(key, {})
            deep_merge(node, value)
        else:
            destination[key] = value
    return destination

class ConfigBuilder:
    """
    Builds the final config dictionary by combining profiles and auto-discovery.
    This version will raise an error immediately if a file is missing or invalid.
    """
    def __init__(self):
        self.logger = logging.getLogger("ConfigBuilder")

    def build(self, case_name: str, sim_profile_name: str) -> dict:
        """
        Orchestrates the building of the final configuration.
        This version uses relative imports to be more robust.
        """
        try:
            # --- THE KEY CHANGE IS HERE ---
            # The '.' tells Python to look inside the current package.
            # The package='config' argument tells it what the current package is.
            base_config = self._load_python_profile('.base', package='src.config')
            sim_config = self._load_python_profile(f".profiles.{sim_profile_name}", package='src.config')
            # --------------------------------

            case_specific_config = self._discover_case_config(case_name)
        except (FileNotFoundError, AttributeError, ImportError) as e:
            raise RuntimeError(f"Failed to load configuration files. Please check paths and file contents. Original error: {e}")

        # Merge them all together
        final_config = {}
        final_config = deep_merge(final_config, base_config)
        final_config = deep_merge(final_config, sim_config)
        final_config = deep_merge(final_config, case_specific_config)

        # OpenFOAM 12 specific settings
        final_config = self._apply_openfoam_12_settings(final_config)

        # Validate physical parameters
        self._validate_physical_parameters(final_config)

        return final_config

    def build_base_and_profile(self, sim_profile_name: str) -> dict:
        """
        Build configuration from base and simulation profile only.
        This creates the foundation config without case-specific overrides.

        Args:
            sim_profile_name: Name of simulation profile

        Returns:
            Base + profile configuration dictionary (without case overrides)
        """
        try:
            # Load base and simulation profiles
            base_config = self._load_python_profile('.base', package='src.config')
            sim_config = self._load_python_profile(f".profiles.{sim_profile_name}", package='src.config')
        except (FileNotFoundError, AttributeError, ImportError) as e:
            raise RuntimeError(f"Failed to load configuration files. Please check paths and file contents. Original error: {e}")

        # Merge base + profile
        config = {}
        config = deep_merge(config, base_config)
        config = deep_merge(config, sim_config)

        return config

    def build_with_case_config(self, case_name: str, sim_profile_name: str, case_config: dict) -> dict:
        """
        Build configuration with directly provided case configuration.
        This method bypasses file system discovery and uses the provided config directly.

        Args:
            case_name: Name of the case
            sim_profile_name: Name of simulation profile
            case_config: Case-specific configuration dictionary

        Returns:
            Final merged configuration dictionary
        """
        try:
            # Load base and simulation profiles
            base_config = self._load_python_profile('.base', package='src.config')
            sim_config = self._load_python_profile(f".profiles.{sim_profile_name}", package='src.config')

            # Convert case config to expected format
            case_specific_config = self._convert_unified_config(case_name, case_config)

        except (FileNotFoundError, AttributeError, ImportError) as e:
            raise RuntimeError(f"Failed to load configuration files. Please check paths and file contents. Original error: {e}")

        # Merge them all together
        final_config = {}
        final_config = deep_merge(final_config, base_config)
        final_config = deep_merge(final_config, sim_config)
        final_config = deep_merge(final_config, case_specific_config)

        # OpenFOAM 12 specific settings
        final_config = self._apply_openfoam_12_settings(final_config)

        # Validate physical parameters
        self._validate_physical_parameters(final_config)

        return final_config

    def _load_python_profile(self, profile_path: str, package: str) -> dict:
        """
        Dynamically loads a python module using a relative path.
        """
        try:
            # Pass the package argument to import_module
            module = importlib.import_module(profile_path, package=package)
            return getattr(module, "config")
        except ImportError as e:
            # Add the original error 'e' for more detailed debugging
            raise ImportError(f"Configuration profile could not be imported: '{profile_path}' from package '{package}'. Check file path and __init__.py files. Original error: {e}")
        except AttributeError:
            raise AttributeError(f"File at '{profile_path}' was found, but it does not contain a 'config' dictionary variable.")

    def _discover_case_config(self, case_name: str, cad_root_dir: str = "cases_input") -> dict:
        """
        Discover case configuration by examining the case directory.
        Automatically detects STL files and boundary conditions.
        """
        case_path = os.path.join(cad_root_dir, case_name)
        if not os.path.isdir(case_path):
            raise FileNotFoundError(f"Case directory for auto-discovery not found: {case_path}")

        stl_files = [f for f in os.listdir(case_path) if f.lower().endswith(".stl")]
        
        wall_patches = [f.split('.')[0] for f in stl_files if "wall" in f.lower()]
        inlet_patches = [f.split('.')[0] for f in stl_files if "inlet" in f.lower()]
        outlet_files = [f for f in stl_files if "outlet" in f.lower()]
        outlet_files.sort(key=lambda f: int(re.findall(r'\d+', f)[-1]) if re.findall(r'\d+', f) else -1)
        
        discovered_geom_config = {
            "geometry": {
                "case_name": case_name,
                "wall_keywords_ordered": wall_patches[0] if wall_patches else "",
                "inlet_keywords_ordered": inlet_patches[0] if inlet_patches else "",
                "outlet_keywords_ordered": [f.split('.')[0] for f in outlet_files]
            }
        }

        bc_file_path = os.path.join(case_path, "boundary_conditions.json")
        bc_config = {}
        if os.path.exists(bc_file_path):
            with open(bc_file_path, 'r') as f:
                bc_config = json.load(f)

        return deep_merge(discovered_geom_config, bc_config)
    
    def _convert_unified_config(self, case_name: str, case_config: dict, cad_root_dir: str = "cases_input") -> dict:
        """
        Convert unified config.json format to the format expected by ConfigBuilder.
        
        Args:
            case_name: Name of the case
            case_config: Unified configuration dictionary
            cad_root_dir: Root directory for case files
            
        Returns:
            Configuration in the format expected by the workflow system
        """
        # First, do the STL file discovery (same as original method)
        case_path = os.path.join(cad_root_dir, case_name)
        if not os.path.isdir(case_path):
            raise FileNotFoundError(f"Case directory not found: {case_path}")

        stl_files = [f for f in os.listdir(case_path) if f.lower().endswith(".stl")]
        
        wall_patches = [f.split('.')[0] for f in stl_files if "wall" in f.lower()]
        inlet_patches = [f.split('.')[0] for f in stl_files if "inlet" in f.lower()]
        outlet_files = [f for f in stl_files if "outlet" in f.lower()]
        outlet_files.sort(key=lambda f: int(re.findall(r'\d+', f)[-1]) if re.findall(r'\d+', f) else -1)
        
        # Build geometry config from STL discovery
        discovered_geom_config = {
            "geometry": {
                "case_name": case_name,
                "wall_keywords_ordered": wall_patches[0] if wall_patches else "",
                "inlet_keywords_ordered": inlet_patches[0] if inlet_patches else "",
                "outlet_keywords_ordered": [f.split('.')[0] for f in outlet_files]
            }
        }
        
        # Extract boundary conditions from unified config
        boundary_conditions = case_config.get('boundary_conditions', {})
        
        # Extract geometry settings from unified config
        geometry_settings = case_config.get('geometry', {})
        
        # Extract simulation control settings from unified config
        simulation_control = case_config.get('simulation_control', {})
        
        # Extract mesh settings from unified config
        mesh_settings = case_config.get('mesh', {})

        # Merge all components: STL discovery + geometry settings + boundary conditions + simulation control + mesh
        result = deep_merge(discovered_geom_config, {"geometry": geometry_settings})
        result = deep_merge(result, boundary_conditions)
        result = deep_merge(result, {"simulation_control": simulation_control})
        if mesh_settings:
            result = deep_merge(result, {"mesh": mesh_settings})
        
        return result

    def _apply_openfoam_12_settings(self, config: dict) -> dict:
        """
        Apply OpenFOAM 12 specific configuration settings.
        """
        # OpenFOAM 12 fixed settings
        config["openfoam_version"] = "12"
        config["openfoam_env_path"] = "/opt/openfoam12/etc/bashrc"
        config["openfoam_major_version"] = 12
        config["openfoam_foundation"] = True
        
        # OpenFOAM 12 solver settings
        config["solver_application"] = "foamRun"
        config["solver_module"] = "incompressibleFluid"
        
        # Template variables for OpenFOAM 12
        config["template_vars"] = {
            "openfoam_version": "12",
            "openfoam_major_version": 12
        }
        
        # Map physics properties for transportProperties
        if 'physics' in config:
            # Calculate kinematic viscosity nu = mu/rho
            if 'default_viscosity' in config['physics'] and 'default_density' in config['physics']:
                mu = config['physics']['default_viscosity']  # Dynamic viscosity in Pa·s
                rho = config['physics']['default_density']   # Density in kg/m³
                nu = mu / rho  # Kinematic viscosity in m²/s
                config['physics']['nu'] = nu
                config['physics']['rho'] = rho
            # Also set mu for convenience
            if 'default_viscosity' in config['physics']:
                config['physics']['mu'] = config['physics']['default_viscosity']

        return config

    def _validate_physical_parameters(self, config: dict) -> None:
        """
        Validate physical parameters are within reasonable CFD ranges.
        Issues warnings for suspicious values but does not block execution.
        """
        # Validate physics
        physics = config.get('physics', {})

        # Blood density validation
        density = physics.get('default_density', physics.get('rho', 1060))
        if not 1000 <= density <= 1200:
            self.logger.warning(
                f"⚠️  Blood density {density} kg/m³ is outside typical range [1000, 1200]. "
                f"Normal blood density is ~1060 kg/m³. Simulation will continue but results may be unrealistic."
            )

        # Blood viscosity validation
        viscosity = physics.get('default_viscosity', physics.get('mu', 0.004))
        if not 0.001 <= viscosity <= 0.01:
            self.logger.warning(
                f"⚠️  Blood viscosity {viscosity} Pa·s is outside typical range [0.001, 0.01]. "
                f"Normal blood viscosity is ~0.004 Pa·s. Simulation will continue but results may be unrealistic."
            )

        # Time stepping validation
        time_stepping = config.get('time_stepping', {})
        max_co = time_stepping.get('maxCo')
        if max_co:
            if max_co < 0.1:
                self.logger.warning(
                    f"⚠️  maxCo {max_co} is very small (< 0.1). "
                    f"This will result in very slow simulation progress."
                )
            elif max_co > 2.0:
                self.logger.warning(
                    f"⚠️  maxCo {max_co} is high (> 2.0). "
                    f"Values above 2.0 may cause numerical instability."
                )

        # Processor count validation
        mesh_settings = config.get('mesh', {}).get('SNAPPY_SETTINGS', {})
        mesh_procs = mesh_settings.get('nProcessors')
        if mesh_procs:
            if not isinstance(mesh_procs, int) or mesh_procs < 1:
                self.logger.warning(
                    f"⚠️  mesh.SNAPPY_SETTINGS.nProcessors must be a positive integer, got: {mesh_procs}"
                )
            elif mesh_procs > 128:
                self.logger.warning(
                    f"⚠️  nProcessors={mesh_procs} seems very high. Ensure your system has sufficient cores."
                )

        run_settings = config.get('run_settings', {})
        solver_procs = run_settings.get('subdomains')
        if solver_procs:
            if not isinstance(solver_procs, int) or solver_procs < 1:
                self.logger.warning(
                    f"⚠️  run_settings.subdomains must be a positive integer, got: {solver_procs}"
                )
            elif solver_procs > 128:
                self.logger.warning(
                    f"⚠️  subdomains={solver_procs} seems very high. Ensure your system has sufficient cores."
                )

        # Check processor count consistency
        if mesh_procs and solver_procs and mesh_procs != solver_procs:
            self.logger.info(
                f"ℹ️  Mesh generation uses {mesh_procs} processors, "
                f"but solver uses {solver_procs} processors. "
                f"This is valid but may not be optimal for resource usage."
            )

        # Time validation
        sim_control = config.get('simulation_control', {})
        end_time = sim_control.get('end_time')
        if end_time and not isinstance(end_time, str):  # Allow "auto" as string
            if end_time <= 0:
                self.logger.warning(
                    f"⚠️  simulation_control.end_time must be positive, got: {end_time}"
                )