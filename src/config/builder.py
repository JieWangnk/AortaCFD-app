import os
import re
import json
import collections.abc
import importlib

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
    def build(self, case_name: str, sim_profile_name: str, openfoam_version: str = None) -> dict:
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
        
        # Apply OpenFOAM version-specific configuration
        final_config = self._apply_openfoam_version(final_config, openfoam_version)
        
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

    def _discover_case_config(self, case_name: str, cad_root_dir: str = "data/CAD") -> dict:
        # ... (This method remains the same as before) ...
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
        else:
            print(f"Warning: boundary_conditions.json not found in {case_path}. Using defaults.")

        return deep_merge(discovered_geom_config, bc_config)

    def _apply_openfoam_version(self, config: dict, openfoam_version: str = None) -> dict:
        """
        Apply OpenFOAM version-specific configuration settings.
        """
        # Get the OpenFOAM configuration
        of_config = config.get("openfoam", {})
        
        # Determine which version to use
        if openfoam_version is None:
            version = of_config.get("default_version", "8")
        else:
            version = openfoam_version
            
        # Validate version is supported
        supported_versions = of_config.get("supported_versions", ["8"])
        if version not in supported_versions:
            raise ValueError(f"OpenFOAM version '{version}' is not supported. Supported versions: {supported_versions}")
        
        # Get version-specific configuration
        version_config = of_config.get("version_configs", {}).get(version, {})
        
        if not version_config:
            raise ValueError(f"No configuration found for OpenFOAM version '{version}'")
        
        # Update the main config with version-specific settings
        config["openfoam_version"] = version
        config["openfoam_env_path"] = version_config.get("env_path")
        config["openfoam_major_version"] = version_config.get("major_version")
        config["openfoam_foundation"] = version_config.get("foundation", True)
        
        # Update solver names based on version
        solver_names = version_config.get("solver_names", {})
        solver_modules = version_config.get("solver_modules", {})
        
        if "solver" in config:
            # Update application name based on simulation type
            if config["solver"].get("application") == "pimpleFoam":
                config["solver"]["application"] = solver_names.get("incompressible", "pimpleFoam")
        
        # Set solver module for OpenFOAM 12+
        if version_config.get("major_version", 8) >= 12:
            config["solver_module"] = solver_modules.get("incompressible", "incompressibleFluid")
        
        # Add version-specific template variables
        if "template_vars" not in config:
            config["template_vars"] = {}
        config["template_vars"]["openfoam_version"] = version
        config["template_vars"]["openfoam_major_version"] = version_config.get("major_version")
        
        return config