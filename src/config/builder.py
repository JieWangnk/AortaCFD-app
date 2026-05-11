import os
import re
import json
import collections.abc
import importlib
import logging
from typing import Optional

from .mesh_quality_presets import get_mesh_preset, get_available_presets
from .schema import validate_config, is_pydantic_available


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
            base_config = self._load_python_profile(".base")
            sim_config = self._load_python_profile(f".profiles.numerics.{sim_profile_name}")

            case_specific_config = self._discover_case_config(case_name)
        except (FileNotFoundError, AttributeError, ImportError) as e:
            raise RuntimeError(
                f"Failed to load configuration files. Please check paths and file contents. Original error: {e}"
            )

        # Merge them all together
        final_config = {}
        final_config = deep_merge(final_config, base_config)
        final_config = deep_merge(final_config, sim_config)
        final_config = deep_merge(final_config, case_specific_config)

        # Check for explicit mesh specification
        self._warn_if_no_explicit_mesh(case_specific_config, sim_profile_name)

        # Apply mesh quality preset if specified
        final_config = self._apply_mesh_quality_preset(final_config)

        # OpenFOAM 12 specific settings
        final_config = self._apply_openfoam_12_settings(final_config)

        # Validate physical parameters
        self._validate_physical_parameters(final_config)
        self._validate_windkessel_parameters(final_config)

        # Physics model advisory (warns if RANS/LES may be inappropriate)
        self._validate_physics_model(final_config)

        # Schema validation (if pydantic available)
        if is_pydantic_available():
            try:
                validate_config(final_config)
                self.logger.debug("✅ Final config validated against schema")
            except Exception as e:
                self.logger.warning(f"⚠️ Config schema validation warning: {e}")

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
            base_config = self._load_python_profile(".base")
            sim_config = self._load_python_profile(f".profiles.numerics.{sim_profile_name}")
        except (FileNotFoundError, AttributeError, ImportError) as e:
            raise RuntimeError(
                f"Failed to load configuration files. Please check paths and file contents. Original error: {e}"
            )

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
            base_config = self._load_python_profile(".base")
            sim_config = self._load_python_profile(f".profiles.numerics.{sim_profile_name}")

            # Convert case config to expected format
            case_specific_config = self._convert_unified_config(case_name, case_config)

        except (FileNotFoundError, AttributeError, ImportError) as e:
            raise RuntimeError(
                f"Failed to load configuration files. Please check paths and file contents. Original error: {e}"
            )

        # Merge them all together
        final_config = {}
        final_config = deep_merge(final_config, base_config)
        final_config = deep_merge(final_config, sim_config)
        final_config = deep_merge(final_config, case_specific_config)

        # Check for explicit mesh specification (pass original case_config for direct check)
        self._warn_if_no_explicit_mesh(case_config, sim_profile_name)

        # Apply mesh quality preset if specified
        final_config = self._apply_mesh_quality_preset(final_config)

        # OpenFOAM 12 specific settings
        final_config = self._apply_openfoam_12_settings(final_config)

        # Validate physical parameters
        self._validate_physical_parameters(final_config)
        self._validate_windkessel_parameters(final_config)

        # Physics model advisory (warns if RANS/LES may be inappropriate)
        self._validate_physics_model(final_config)

        # Schema validation (if pydantic available)
        if is_pydantic_available():
            try:
                validate_config(final_config)
                self.logger.debug("✅ Final config validated against schema")
            except Exception as e:
                self.logger.warning(f"⚠️ Config schema validation warning: {e}")

        return final_config

    def _load_python_profile(self, profile_path: str, package: Optional[str] = None) -> dict:
        """
        Dynamically load a config module and return its ``config`` dict.

        Args:
            profile_path: Relative module path such as ``".base"`` or
                ``".profiles.numerics.standard"``.
            package: Anchor package for the relative import. Defaults to this
                module's own package (``__package__``), which resolves
                correctly whether the caller imports us as ``config.builder``
                or ``src.config.builder``.
        """
        anchor = package or __package__
        try:
            module = importlib.import_module(profile_path, package=anchor)
            return getattr(module, "config")
        except ImportError as e:
            raise ImportError(
                f"Configuration profile could not be imported: '{profile_path}' "
                f"from package '{anchor}'. Check file path and __init__.py files. "
                f"Original error: {e}"
            )
        except AttributeError:
            raise AttributeError(
                f"File at '{profile_path}' was found, but it does not contain " f"a 'config' dictionary variable."
            )

    def _discover_case_config(self, case_name: str, cad_root_dir: str = "cases_input") -> dict:
        """
        Discover case configuration by examining the case directory.
        Automatically detects STL files and boundary conditions.
        """
        case_path = os.path.join(cad_root_dir, case_name)
        if not os.path.isdir(case_path):
            raise FileNotFoundError(f"Case directory for auto-discovery not found: {case_path}")

        stl_files = [f for f in os.listdir(case_path) if f.lower().endswith(".stl")]

        wall_patches = [f.split(".")[0] for f in stl_files if "wall" in f.lower()]
        inlet_patches = [f.split(".")[0] for f in stl_files if "inlet" in f.lower()]
        outlet_files = [f for f in stl_files if "outlet" in f.lower()]
        outlet_files.sort(key=lambda f: int(re.findall(r"\d+", f)[-1]) if re.findall(r"\d+", f) else -1)

        discovered_geom_config = {
            "geometry": {
                "case_name": case_name,
                "wall_keywords_ordered": wall_patches[0] if wall_patches else "",
                "inlet_keywords_ordered": inlet_patches[0] if inlet_patches else "",
                "outlet_keywords_ordered": [f.split(".")[0] for f in outlet_files],
            }
        }

        bc_file_path = os.path.join(case_path, "boundary_conditions.json")
        bc_config = {}
        if os.path.exists(bc_file_path):
            with open(bc_file_path, "r") as f:
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

        wall_patches = [f.split(".")[0] for f in stl_files if "wall" in f.lower()]
        inlet_patches = [f.split(".")[0] for f in stl_files if "inlet" in f.lower()]
        outlet_files = [f for f in stl_files if "outlet" in f.lower()]
        outlet_files.sort(key=lambda f: int(re.findall(r"\d+", f)[-1]) if re.findall(r"\d+", f) else -1)

        # Build geometry config from STL discovery
        discovered_geom_config = {
            "geometry": {
                "case_name": case_name,
                "wall_keywords_ordered": wall_patches[0] if wall_patches else "",
                "inlet_keywords_ordered": inlet_patches[0] if inlet_patches else "",
                "outlet_keywords_ordered": [f.split(".")[0] for f in outlet_files],
            }
        }

        # Extract boundary conditions from unified config
        boundary_conditions = case_config.get("boundary_conditions", {})

        # Extract geometry settings from unified config
        geometry_settings = case_config.get("geometry", {})

        # Extract simulation control settings from unified config
        simulation_control = case_config.get("simulation_control", {})

        # Extract mesh settings from unified config
        mesh_settings = case_config.get("mesh", {})

        # Tag user-provided SNAPPY keys so downstream code can distinguish
        # user overrides from base.py defaults after deep merge
        if "SNAPPY_SETTINGS" in mesh_settings:
            mesh_settings["SNAPPY_SETTINGS"]["_user_provided_keys"] = list(mesh_settings["SNAPPY_SETTINGS"].keys())

        # Extract run settings from unified config
        run_settings = case_config.get("run_settings", {})

        # Extract simulation settings from unified config
        simulation_settings = case_config.get("simulation_settings", {})

        # Extract hemodynamics settings from unified config
        hemodynamics = case_config.get("hemodynamics", {})

        # Extract visualization settings from unified config
        visualization = case_config.get("visualization", {})

        # Extract top-level cardiac_cycle from unified config
        cardiac_cycle = case_config.get("cardiac_cycle")

        # Merge all components: STL discovery + geometry settings + boundary conditions + simulation control + mesh + run_settings + simulation_settings + hemodynamics + visualization
        result = deep_merge(discovered_geom_config, {"geometry": geometry_settings})
        result = deep_merge(result, {"boundary_conditions": boundary_conditions})
        result = deep_merge(result, {"simulation_control": simulation_control})
        if mesh_settings:
            result = deep_merge(result, {"mesh": mesh_settings})
        if run_settings:
            result = deep_merge(result, {"run_settings": run_settings})
        if simulation_settings:
            result = deep_merge(result, {"simulation_settings": simulation_settings})
        if hemodynamics:
            result = deep_merge(result, {"hemodynamics": hemodynamics})
        if visualization:
            result = deep_merge(result, {"visualization": visualization})
        if cardiac_cycle is not None:
            result["cardiac_cycle"] = cardiac_cycle

        return result

    def _apply_openfoam_12_settings(self, config: dict) -> dict:
        """
        Apply OpenFOAM 12 specific configuration settings.
        """
        # OpenFOAM 12 fixed settings
        config["openfoam_version"] = "12"
        # Allow HPC environments (CSF3, etc.) to override the bashrc path via
        # $OPENFOAM_BASHRC or $foamDotFile (set by CSF3's OF module load).
        config["openfoam_env_path"] = os.environ.get(
            "OPENFOAM_BASHRC",
            os.environ.get("foamDotFile", "/opt/openfoam12/etc/bashrc"),
        )
        config["openfoam_major_version"] = 12
        config["openfoam_foundation"] = True

        # OpenFOAM 12 solver settings
        config["solver_application"] = "foamRun"
        config["solver_module"] = "incompressibleFluid"

        # Template variables for OpenFOAM 12
        config["template_vars"] = {"openfoam_version": "12", "openfoam_major_version": 12}

        # Set default run_settings if not present
        if "run_settings" not in config:
            config["run_settings"] = {}

        # Set default decomposition_method if not specified
        if "decomposition_method" not in config["run_settings"]:
            config["run_settings"]["decomposition_method"] = "scotch"  # Default: scotch (automatic load balancing)

        # Map physics properties for transportProperties
        if "physics" in config:
            # NEW FORMAT: physics.transport_properties.{nu, rho} (already in SI units)
            if "transport_properties" in config["physics"]:
                transport = config["physics"]["transport_properties"]
                if "nu" in transport:
                    config["physics"]["nu"] = transport["nu"]
                if "rho" in transport:
                    config["physics"]["rho"] = transport["rho"]
                # Calculate mu from nu and rho if available
                if "nu" in transport and "rho" in transport:
                    config["physics"]["mu"] = transport["nu"] * transport["rho"]

            # OLD FORMAT: Calculate kinematic viscosity nu = mu/rho
            elif "default_viscosity" in config["physics"] and "default_density" in config["physics"]:
                mu = config["physics"]["default_viscosity"]  # Dynamic viscosity in Pa·s
                rho = config["physics"]["default_density"]  # Density in kg/m³
                nu = mu / rho  # Kinematic viscosity in m²/s
                config["physics"]["nu"] = nu
                config["physics"]["rho"] = rho
                config["physics"]["mu"] = mu

        return config

    def _warn_if_no_explicit_mesh(self, case_config: dict, profile_name: str) -> None:
        """
        Warn if user config does not explicitly specify mesh resolution.

        Profiles contain default mesh settings, but these are DEPRECATED.
        Users should always specify mesh resolution explicitly in their config.
        """
        mesh_config = case_config.get("mesh", {})
        mesh_resolution = mesh_config.get("mesh_resolution", {})

        # Check if user has specified ANY explicit mesh resolution method
        has_explicit_mesh = "target_cell_size_mm" in mesh_resolution or "cells_per_diameter" in mesh_resolution

        if not has_explicit_mesh:
            self.logger.warning(
                f"\n"
                f"⚠️  DEPRECATION WARNING: No mesh resolution specified in config\n"
                f"─────────────────────────────────────────────────────────────\n"
                f"Profile '{profile_name}' contains default mesh settings, but these are DEPRECATED.\n"
                f"You should ALWAYS specify mesh resolution explicitly in your config:\n\n"
                f"  {{\n"
                f'    "mesh": {{\n'
                f'      "mesh_resolution": {{\n'
                f'        "cells_per_diameter": 15  // Recommended: geometry-adaptive\n'
                f"      }}\n"
                f"    }}\n"
                f"  }}\n\n"
                f"Profile defaults will be removed in a future release.\n"
                f"See docs/PROFILE_USAGE_GUIDE.md for details.\n"
            )

    def _validate_physical_parameters(self, config: dict) -> None:
        """
        Validate physical parameters are within reasonable CFD ranges.
        Issues warnings for suspicious values but does not block execution.
        """
        # Validate physics
        physics = config.get("physics", {})

        # Blood density validation
        density = physics.get("default_density", physics.get("rho", 1060))
        if not 1000 <= density <= 1200:
            self.logger.warning(
                f"⚠️  Blood density {density} kg/m³ is outside typical range [1000, 1200]. "
                f"Normal blood density is ~1060 kg/m³. Simulation will continue but results may be unrealistic."
            )

        # Blood viscosity validation
        viscosity = physics.get("default_viscosity", physics.get("mu", 0.004))
        if not 0.001 <= viscosity <= 0.01:
            self.logger.warning(
                f"⚠️  Blood viscosity {viscosity} Pa·s is outside typical range [0.001, 0.01]. "
                f"Normal blood viscosity is ~0.004 Pa·s. Simulation will continue but results may be unrealistic."
            )

        # Time stepping validation
        time_stepping = config.get("time_stepping", {})
        max_co = time_stepping.get("maxCo")
        if max_co:
            if max_co < 0.1:
                self.logger.warning(
                    f"⚠️  maxCo {max_co} is very small (< 0.1). " f"This will result in very slow simulation progress."
                )
            elif max_co > 2.0:
                self.logger.warning(
                    f"⚠️  maxCo {max_co} is high (> 2.0). " f"Values above 2.0 may cause numerical instability."
                )

        # Processor count validation
        mesh_settings = config.get("mesh", {}).get("SNAPPY_SETTINGS", {})
        mesh_procs = mesh_settings.get("nProcessors")
        if mesh_procs:
            if not isinstance(mesh_procs, int) or mesh_procs < 1:
                self.logger.warning(
                    f"⚠️  mesh.SNAPPY_SETTINGS.nProcessors must be a positive integer, got: {mesh_procs}"
                )
            elif mesh_procs > 128:
                self.logger.warning(
                    f"⚠️  nProcessors={mesh_procs} seems very high. Ensure your system has sufficient cores."
                )

        run_settings = config.get("run_settings", {})
        solver_procs = run_settings.get("subdomains")
        if solver_procs:
            if not isinstance(solver_procs, int) or solver_procs < 1:
                self.logger.warning(f"⚠️  run_settings.subdomains must be a positive integer, got: {solver_procs}")
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
        sim_control = config.get("simulation_control", {})
        end_time = sim_control.get("end_time")
        if end_time and not isinstance(end_time, str):  # Allow "auto" as string
            if end_time <= 0:
                self.logger.warning(f"⚠️  simulation_control.end_time must be positive, got: {end_time}")

    def _validate_windkessel_parameters(self, config: dict) -> None:
        """
        Validate Windkessel model parameters are within physiological ranges.
        Issues warnings (non-blocking) to avoid breaking existing workflows.
        """
        outlets = config.get("boundary_conditions", {}).get("outlets", {})
        wk_settings = outlets.get("windkessel_settings", {})
        if not wk_settings:
            return

        # Tau (RC time constant)
        tau = wk_settings.get("tau")
        if tau is not None and not (0.5 <= tau <= 3.0):
            self.logger.warning(
                f"Windkessel tau={tau:.2f}s outside physiological range [0.5, 3.0]s. "
                f"Typical adult: 1.0-2.0s, pediatric: 0.5-1.0s."
            )

        # Stabilization parameters
        for key in ["betaT", "betaN"]:
            val = wk_settings.get(key)
            if val is not None and not (0 <= val <= 1):
                self.logger.warning(f"Windkessel {key}={val} outside valid range [0, 1].")

        # Venous pressure
        p_v = wk_settings.get("venous_pressure")
        if p_v is not None and not (0 <= p_v <= 10):
            self.logger.warning(f"Venous pressure {p_v} mmHg outside typical range [0, 10] mmHg.")

        # Pressure consistency
        sp = wk_settings.get("systolic_pressure")
        dp = wk_settings.get("diastolic_pressure")
        if sp is not None and dp is not None:
            if sp <= dp:
                self.logger.warning(f"Systolic pressure ({sp} mmHg) must exceed diastolic ({dp} mmHg).")
            pulse = sp - dp
            if not (20 <= pulse <= 80):
                self.logger.warning(f"Pulse pressure ({pulse:.0f} mmHg) outside typical range [20, 80] mmHg.")

        # Murray's law exponent
        murray_exp = wk_settings.get("murray_exponent")
        if murray_exp is not None and not (2.0 <= murray_exp <= 3.5):
            self.logger.warning(f"Murray's law exponent {murray_exp} outside range [2.0, 3.5].")

        # Pulse wave velocity
        pwv = wk_settings.get("pwv")
        if pwv is not None and not (2.0 <= pwv <= 15.0):
            self.logger.warning(f"Pulse wave velocity {pwv} m/s outside typical range [2.0, 15.0] m/s.")

        # Flow split sum
        flow_split = wk_settings.get("flow_split")
        if flow_split and isinstance(flow_split, dict):
            numeric_vals = [v for v in flow_split.values() if isinstance(v, (int, float))]
            if numeric_vals:
                total = sum(numeric_vals)
                # Check if values look like ratios (sum near 1.0)
                if all(v <= 1.0 for v in numeric_vals) and abs(total - 1.0) > 0.05:
                    self.logger.warning(f"Flow split fractions sum to {total:.3f}, expected ~1.0.")

    def _validate_physics_model(self, config: dict) -> None:
        """
        Check if the selected physics model is appropriate for the flow conditions
        and mesh settings. Issues warnings (non-blocking) for potential issues.

        Warns when:
        - RANS/LES selected but estimated Re is in the laminar regime (< 4000)
        - Mesh refinement level jumps create volume ratio risks for turbulence models
        - LES selected without adequate boundary layer resolution
        """
        physics = config.get("physics", {})
        sim_type = physics.get("simulation_type", "laminar").lower()

        if sim_type == "laminar":
            return  # No warnings needed for laminar

        try:
            from aortacfd_lib.physics_advisor import (
                recommend_physics_model,
                log_physics_advice,
            )

            advice = recommend_physics_model(config)
            log_physics_advice(advice, sim_type)

        except ImportError:
            self.logger.debug("Physics advisor not available, skipping model check")
        except Exception as e:
            self.logger.debug(f"Physics model check skipped: {e}")

    def _apply_mesh_quality_preset(self, config: dict) -> dict:
        """
        Apply mesh quality preset if specified in config.

        The preset provides base SNAPPY_SETTINGS values, which are then
        overridden by any user-specified values in config.mesh.SNAPPY_SETTINGS.

        Merge order (later overrides earlier):
        1. base.py defaults
        2. Preset values (if quality_preset specified)
        3. User config values

        Args:
            config: Configuration dictionary (already merged with base + profile)

        Returns:
            Configuration with preset values applied
        """
        mesh_config = config.get("mesh", {})
        preset_name = mesh_config.get("quality_preset")

        if not preset_name:
            return config

        # Validate preset name
        available = get_available_presets()
        if preset_name not in available:
            self.logger.warning(
                f"⚠️  Unknown mesh quality preset: '{preset_name}'. " f"Valid options: {available}. Using defaults."
            )
            return config

        # Get preset values
        preset_values = get_mesh_preset(preset_name)

        # Get current SNAPPY_SETTINGS (from base.py defaults)
        current_snappy = mesh_config.get("SNAPPY_SETTINGS", {})

        # Store user-specified overrides (values explicitly set in case config)
        # These should take precedence over preset values
        user_overrides = current_snappy.copy()

        # Apply preset values as the new base
        # Then re-apply user overrides on top
        merged_snappy = preset_values.copy()
        merged_snappy.update(user_overrides)

        # Update config
        if "mesh" not in config:
            config["mesh"] = {}
        config["mesh"]["SNAPPY_SETTINGS"] = merged_snappy

        self.logger.info(f"📐 Applied mesh quality preset: '{preset_name}'")

        return config
