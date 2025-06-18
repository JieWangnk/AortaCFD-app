# CONFIG/builder.py
"""
Intelligently builds the final configuration by merging profiles and auto-discovery.
This module is self-contained.
"""

import os
import re
import json
import collections.abc
import importlib

def deep_merge(destination: dict, source: dict) -> dict:
    """
    Recursively merges the source dictionary into the destination dictionary.
    Nested dictionaries are merged, not overwritten.
    """
    for key, value in source.items():
        if isinstance(value, collections.abc.Mapping):
            node = destination.setdefault(key, {})
            deep_merge(node, value)
        else:
            destination[key] = value
    return destination


class ConfigBuilder:
    """
    Builds the final CONFIG dictionary by combining a static simulation profile
    with a dynamically discovered case configuration.
    """
    def build(self, case_name: str, sim_profile_name: str) -> dict:
        """
        Orchestrates the building of the final configuration.

        The merge order is critical to allow specific profiles to override base settings:
        1. Base config (lowest priority)
        2. Simulation profile (e.g., numerics, solver settings)
        3. Case-specific config (geometry and boundary conditions)
        """
        # Load base and simulation profiles
        base_config = self._load_python_profile('CONFIG.base')
        sim_config = self._load_python_profile(f"CONFIG.profiles.{sim_profile_name}")

        # Discover all case-specific info (geometry AND boundary conditions)
        case_specific_config = self._discover_case_config(case_name)

        # Merge them all together
        final_config = {}
        final_config = deep_merge(final_config, base_config)
        final_config = deep_merge(final_config, sim_config)
        final_config = deep_merge(final_config, case_specific_config)
        
        return final_config

    def _discover_case_config(self, case_name: str, cad_root_dir: str = "CAD") -> dict:
        """
        Scans a case directory to auto-discover patch names from STLs
        AND loads the boundary_conditions.json file.
        """
        case_path = os.path.join(cad_root_dir, case_name)
        if not os.path.isdir(case_path):
            raise FileNotFoundError(f"Case directory for auto-discovery not found: {case_path}")

        # Part A: Discover geometry from STL filenames
        stl_files = [f for f in os.listdir(case_path) if f.lower().endswith(".stl")]
        
        wall_patches = [f.split('.')[0] for f in stl_files if "wall" in f.lower()]
        inlet_patches = [f.split('.')[0] for f in stl_files if "inlet" in f.lower()]
        outlet_files = [f for f in stl_files if "outlet" in f.lower()]

        # Sort outlets numerically by the number in their filename
        outlet_files.sort(key=lambda f: int(re.findall(r'\d+', f)[-1]) if re.findall(r'\d+', f) else -1)
        
        discovered_geom_config = {
            "geometry": {
                "case_name": case_name,
                "scale_factor": 1e-3, # A reasonable default, can be overridden by bc.json
                "wall_keywords_ordered": wall_patches[0] if wall_patches else "",
                "inlet_keywords_ordered": inlet_patches[0] if inlet_patches else "",
                "outlet_keywords_ordered": [f.split('.')[0] for f in outlet_files]
            }
        }

        # Part B: Load the boundary conditions file for this case
        bc_file_path = os.path.join(case_path, "boundary_conditions.json")
        bc_config = {}
        if os.path.exists(bc_file_path):
            with open(bc_file_path, 'r') as f:
                bc_config = json.load(f)
        else:
            print(f"Warning: boundary_conditions.json not found in {case_path}. Using defaults.")

        # Merge the discovered geometry and the loaded BCs into one case-specific config
        return deep_merge(discovered_geom_config, bc_config)

    def _load_python_profile(self, profile_path: str) -> dict:
        """Dynamically loads a python module and returns its CONFIG dict."""
        try:
            # We assume the app is run from the root, so CONFIG is importable
            module = importlib.import_module(profile_path)
            return getattr(module, "CONFIG", {})
        except ImportError:
            print(f"Warning: Configuration profile '{profile_path}' not found.")
            return {}
        except AttributeError:
            print(f"Warning: No 'CONFIG' dictionary found in {profile_path}.")
            return {}