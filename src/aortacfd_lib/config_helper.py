import json
import os
from typing import Dict, Any, List
from .utils.logger import Logger

class BoundaryConditionsHelper:
    """
    Intelligent helper to analyze and auto-complete boundary_conditions.json files
    based on key parameters and common cardiovascular simulation patterns.
    """
    
    def __init__(self):
        self.log = Logger("configHelper.log").get_logger()
        
        # Define key parameters that drive other configurations
        self.key_parameters = {
            "geometry.refinement_level": ["coarse", "medium", "fine"],
            "inlet.profile": ["plug", "parabolic", "womersley"],
            "outlets.type": ["ZEROGRADIENT", "FIXEDVALUE", "3EWINDKESSEL"],
            "simulation_control.number_of_cycles": [1, 2, 3, 4, 5]
        }
        
        # Intelligent defaults based on patterns
        self.intelligent_defaults = {
            "geometry": {
                "rotation": True,
                "target_normal": [0, 0, 1],
                "scale_factor": 0.001  # mm to m conversion
            },
            "inlet": {
                "type": "TIMEVARYING",
                "data_type": "velocity",
                "orientation": "out"
            },
            "outlets": {
                "windkessel_settings": {
                    "systolic_pressure": 120,
                    "diastolic_pressure": 80
                }
            },
            "simulation_control": {
                "end_time": 0.1  # Will be auto-calculated based on cycles
            }
        }
        
    def analyze_boundary_conditions(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze a boundary_conditions.json file and return analysis report.
        """
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.log.error(f"Error reading boundary conditions file: {e}")
            return {"error": str(e)}
            
        analysis = {
            "key_parameters": self._extract_key_parameters(config),
            "missing_parameters": self._find_missing_parameters(config),
            "suggestions": self._generate_suggestions(config),
            "completeness": self._calculate_completeness(config)
        }
        
        return analysis
    
    def auto_complete_config(self, partial_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligently complete a partial boundary conditions configuration.
        """
        completed_config = partial_config.copy()
        
        # Auto-complete based on refinement level
        refinement_level = partial_config.get("geometry", {}).get("refinement_level", "medium")
        completed_config = self._apply_refinement_level_defaults(completed_config, refinement_level)
        
        # Auto-complete based on inlet profile
        inlet_profile = partial_config.get("inlet", {}).get("profile", "womersley")
        completed_config = self._apply_inlet_profile_defaults(completed_config, inlet_profile)
        
        # Auto-complete based on outlet type
        outlet_type = partial_config.get("outlets", {}).get("type", "ZEROGRADIENT")
        completed_config = self._apply_outlet_type_defaults(completed_config, outlet_type)
        
        # Apply general intelligent defaults
        completed_config = self._merge_intelligent_defaults(completed_config)
        
        # Auto-calculate flow split for multiple outlets
        completed_config = self._auto_calculate_flow_split(completed_config)
        
        return completed_config
    
    def _extract_key_parameters(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the key driving parameters from configuration."""
        key_params = {}
        
        # Geometry parameters
        geometry = config.get("geometry", {})
        key_params["refinement_level"] = geometry.get("refinement_level", "unknown")
        key_params["scale_factor"] = geometry.get("scale_factor", "missing")
        
        # Inlet parameters
        inlet = config.get("inlet", {})
        key_params["inlet_profile"] = inlet.get("profile", "unknown")
        key_params["inlet_data_type"] = inlet.get("data_type", "unknown")
        
        # Outlet parameters
        outlets = config.get("outlets", {})
        key_params["outlet_type"] = outlets.get("type", "unknown")
        
        # Simulation parameters
        sim_control = config.get("simulation_control", {})
        key_params["number_of_cycles"] = sim_control.get("number_of_cycles", "unknown")
        
        return key_params
    
    def _find_missing_parameters(self, config: Dict[str, Any]) -> List[str]:
        """Identify missing critical parameters."""
        missing = []
        
        # Check required geometry parameters
        geometry = config.get("geometry", {})
        if "scale_factor" not in geometry:
            missing.append("geometry.scale_factor")
        if "refinement_level" not in geometry:
            missing.append("geometry.refinement_level")
            
        # Check required inlet parameters
        inlet = config.get("inlet", {})
        if "csv_file" not in inlet:
            missing.append("inlet.csv_file")
        if "profile" not in inlet:
            missing.append("inlet.profile")
            
        # Check outlet parameters
        outlets = config.get("outlets", {})
        if "type" not in outlets:
            missing.append("outlets.type")
            
        return missing
    
    def _generate_suggestions(self, config: Dict[str, Any]) -> List[str]:
        """Generate intelligent suggestions for improvement."""
        suggestions = []
        
        # Refinement level suggestions
        refinement = config.get("geometry", {}).get("refinement_level")
        if refinement == "coarse":
            suggestions.append("Consider 'medium' refinement for better accuracy")
        elif refinement == "fine":
            suggestions.append("'Fine' mesh will be slower but more accurate")
            
        # Inlet profile suggestions
        profile = config.get("inlet", {}).get("profile")
        if profile == "plug":
            suggestions.append("Consider 'womersley' profile for realistic pulsatile flow")
        elif profile == "womersley":
            suggestions.append("Womersley profile requires kinematic viscosity (nu) in physics config")
            
        # Outlet suggestions
        outlet_type = config.get("outlets", {}).get("type")
        if outlet_type == "ZEROGRADIENT":
            suggestions.append("Consider 'WINDKESSEL' outlets for physiological boundary conditions")
            
        # Simulation time suggestions
        cycles = config.get("simulation_control", {}).get("number_of_cycles", 0)
        if cycles < 2:
            suggestions.append("Recommend at least 2 cardiac cycles for flow development")
        elif cycles > 3:
            suggestions.append("More than 3 cycles may be computationally expensive")
            
        return suggestions
    
    def _calculate_completeness(self, config: Dict[str, Any]) -> float:
        """Calculate configuration completeness as percentage."""
        total_expected = 15  # Total number of expected parameters
        present = 0
        
        # Count present parameters
        if config.get("geometry", {}).get("scale_factor"): present += 1
        if config.get("geometry", {}).get("refinement_level"): present += 1
        if config.get("geometry", {}).get("rotation") is not None: present += 1
        if config.get("geometry", {}).get("target_normal"): present += 1
        
        if config.get("inlet", {}).get("csv_file"): present += 1
        if config.get("inlet", {}).get("profile"): present += 1
        if config.get("inlet", {}).get("data_type"): present += 1
        if config.get("inlet", {}).get("type"): present += 1
        
        if config.get("outlets", {}).get("type"): present += 1
        if config.get("outlets", {}).get("windkessel_settings"): present += 1
        
        if config.get("simulation_control", {}).get("number_of_cycles"): present += 1
        if config.get("simulation_control", {}).get("end_time"): present += 1
        
        return (present / total_expected) * 100
    
    def _apply_refinement_level_defaults(self, config: Dict[str, Any], refinement_level: str) -> Dict[str, Any]:
        """Apply defaults based on refinement level."""
        if "geometry" not in config:
            config["geometry"] = {}
            
        # Time step recommendations based on mesh density
        if "simulation_control" not in config:
            config["simulation_control"] = {}
            
        time_step_defaults = {
            "coarse": {"initial_deltaT": 1e-4, "maxDeltaT": 5e-3},
            "medium": {"initial_deltaT": 1e-5, "maxDeltaT": 1e-3},
            "fine": {"initial_deltaT": 1e-6, "maxDeltaT": 5e-4}
        }
        
        defaults = time_step_defaults.get(refinement_level, time_step_defaults["medium"])
        config["simulation_control"].update(defaults)
        
        return config
    
    def _apply_inlet_profile_defaults(self, config: Dict[str, Any], profile: str) -> Dict[str, Any]:
        """Apply defaults based on inlet profile type."""
        if "inlet" not in config:
            config["inlet"] = {}
            
        profile_defaults = {
            "plug": {"data_type": "velocity", "requires_nu": False},
            "parabolic": {"data_type": "velocity", "requires_nu": False},
            "womersley": {"data_type": "velocity", "requires_nu": True}
        }
        
        defaults = profile_defaults.get(profile, profile_defaults["womersley"])
        config["inlet"].update({k: v for k, v in defaults.items() if k != "requires_nu"})
        
        return config
    
    def _apply_outlet_type_defaults(self, config: Dict[str, Any], outlet_type: str) -> Dict[str, Any]:
        """Apply defaults based on outlet boundary condition type."""
        if "outlets" not in config:
            config["outlets"] = {}
            
        if outlet_type == "3EWINDKESSEL" and "windkessel_settings" not in config["outlets"]:
            config["outlets"]["windkessel_settings"] = {
                "systolic_pressure": 120,
                "diastolic_pressure": 80,
                "resistance": 1000,
                "compliance": 1e-6
            }
            
        return config
    
    def _merge_intelligent_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge intelligent defaults without overwriting existing values."""
        for section, defaults in self.intelligent_defaults.items():
            if section not in config:
                config[section] = {}
            for key, value in defaults.items():
                if key not in config[section]:
                    config[section][key] = value
                    
        return config
    
    def _auto_calculate_flow_split(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-calculate equal flow split for multiple outlets."""
        # This would require knowing the number of outlets from the geometry
        # For now, assume 4 outlets as in the current case
        if "outlets" not in config:
            config["outlets"] = {}
        if "windkessel_settings" not in config["outlets"]:
            config["outlets"]["windkessel_settings"] = {}
            
        # Equal distribution among 4 outlets
        config["outlets"]["windkessel_settings"]["flow_split"] = {
            "outlet1": 0.25,
            "outlet2": 0.25, 
            "outlet3": 0.25,
            "outlet4": 0.25
        }
        
        return config

    def create_template_config(self, case_name: str, csv_file: str) -> Dict[str, Any]:
        """Create a template configuration with intelligent defaults."""
        template = {
            "geometry": {
                "refinement_level": "medium",
                "rotation": True,
                "target_normal": [0, 0, 1],
                "scale_factor": 0.001
            },
            "inlet": {
                "type": "TIMEVARYING",
                "csv_file": csv_file,
                "data_type": "velocity",
                "profile": "womersley",
                "orientation": "out"
            },
            "outlets": {
                "type": "ZEROGRADIENT",
                "windkessel_settings": {
                    "systolic_pressure": 120,
                    "diastolic_pressure": 80,
                    "flow_split": {
                        "outlet1": 0.25,
                        "outlet2": 0.25,
                        "outlet3": 0.25,
                        "outlet4": 0.25
                    }
                }
            },
            "simulation_control": {
                "number_of_cycles": 2,
                "end_time": 0.1
            }
        }
        
        return template