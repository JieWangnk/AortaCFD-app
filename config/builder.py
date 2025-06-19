# CONFIG/builder.py
import os
import re
import json
import collections.abc
import importlib

def deep_merge(destination: dict, source: dict) -> dict:
    for key, value in source.items():
        if isinstance(value, collections.abc.Mapping):
            node = destination.setdefault(key, {})
            deep_merge(node, value)
        else:
            destination[key] = value
    return destination

class ConfigBuilder:
    def build(self, case_name: str, sim_profile_name: str) -> dict:
        # Load base and simulation profiles
        base_config = self._load_python_profile(f"CONFIG.base")
        sim_config = self._load_python_profile(f"CONFIG.profiles.{sim_profile_name}")

        # Discover all case-specific info
        case_specific_config = self._discover_case_config(case_name)

        # Merge them all together
        final_config = {}
        final_config = deep_merge(final_config, base_config)
        final_config = deep_merge(final_config, sim_config)
        final_config = deep_merge(final_config, case_specific_config)
        
        return final_config

    def _discover_case_config(self, case_name: str, cad_root_dir: str = "CAD") -> dict:
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

    def _load_python_profile(self, profile_path: str) -> dict:
        try:
            module = importlib.import_module(profile_path)
            return getattr(module, "CONFIG", {})
        except ImportError:
            print(f"Warning: Configuration profile '{profile_path}' not found.")
            return {}