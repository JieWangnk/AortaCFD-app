# src/config/accessor.py
"""
Simplified configuration accessor.

This module provides a clean interface to access configuration values,
eliminating the need for repeated nested dictionary access patterns
throughout the codebase.

Usage:
    from src.config.accessor import Config

    cfg = Config(raw_config_dict)
    inlet = cfg.inlet          # Gets inlet config from either location
    profile = cfg.profile      # Gets numerical profile name
    case_dir = cfg.case_dir    # Gets case directory
"""

from typing import Any, Dict, List, Optional, Union


class Config:
    """
    Simplified configuration accessor with normalized paths.

    Handles both nested (boundary_conditions.inlet) and flattened (inlet)
    config structures transparently. Provides clear, type-hinted access
    to all configuration sections.

    Attributes:
        _config: The raw configuration dictionary
    """

    def __init__(self, raw_config: Dict[str, Any]):
        """
        Initialize config accessor.

        Args:
            raw_config: Raw configuration dictionary from JSON or builder
        """
        self._config = raw_config

    # =========================================================================
    # RAW ACCESS
    # =========================================================================

    def get(self, key: str, default: Any = None) -> Any:
        """Get a top-level config value."""
        return self._config.get(key, default)

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """Get a nested config value using a series of keys."""
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access: config['key']."""
        return self._config[key]

    def __contains__(self, key: str) -> bool:
        """Allow 'in' checks: 'key' in config."""
        return key in self._config

    def to_dict(self) -> Dict[str, Any]:
        """Return the raw config dictionary."""
        return self._config

    # =========================================================================
    # CASE INFO (METADATA)
    # =========================================================================

    @property
    def case_info(self) -> Dict[str, Any]:
        """Get case information/metadata."""
        return self._config.get("case_info", {})

    @property
    def patient_id(self) -> str:
        """Get patient ID."""
        return self.case_info.get("patient_id", "")

    @property
    def case_notes(self) -> str:
        """Get case notes/description."""
        return self.case_info.get("notes", "")

    @property
    def provenance(self) -> Dict[str, Any]:
        """Get provenance metadata for reproducibility tracking."""
        return self._config.get("provenance", {})

    # =========================================================================
    # GEOMETRY
    # =========================================================================

    @property
    def geometry(self) -> Dict[str, Any]:
        """Get geometry configuration."""
        return self._config.get("geometry", {})

    @property
    def case_name(self) -> str:
        """Get case name."""
        return self.geometry.get("case_name", "")

    @property
    def scale_factor(self) -> float:
        """Get geometry scale factor (default: 0.001 for mm->m)."""
        return self.geometry.get("scale_factor", 0.001)

    @property
    def inlet_patch_name(self) -> str:
        """Get inlet patch name from geometry."""
        return self.geometry.get("inlet_keywords_ordered", "")

    @property
    def outlet_patch_names(self) -> List[str]:
        """Get outlet patch names from geometry."""
        outlets = self.geometry.get("outlet_keywords_ordered", [])
        if isinstance(outlets, str):
            return [outlets]
        return outlets

    @property
    def wall_patch_name(self) -> str:
        """Get wall patch name from geometry."""
        return self.geometry.get("wall_keywords_ordered", "")

    @property
    def reference_radius_strategy(self) -> str:
        """Get reference radius strategy (inlet, minimum, average)."""
        return self.geometry.get("reference_radius_strategy", "inlet")

    # =========================================================================
    # BOUNDARY CONDITIONS (handles nested and flattened)
    # =========================================================================

    @property
    def boundary_conditions(self) -> Dict[str, Any]:
        """Get boundary conditions section."""
        return self._config.get("boundary_conditions", {})

    @property
    def inlet(self) -> Dict[str, Any]:
        """
        Get inlet configuration.

        Handles both:
        - boundary_conditions.inlet (nested)
        - inlet (flattened)
        """
        bc = self.boundary_conditions
        return bc.get("inlet") or self._config.get("inlet", {})

    @property
    def outlets(self) -> Dict[str, Any]:
        """
        Get outlets configuration.

        Handles both:
        - boundary_conditions.outlets (nested)
        - outlets (flattened)
        """
        bc = self.boundary_conditions
        return bc.get("outlets") or self._config.get("outlets", {})

    @property
    def inlet_type(self) -> str:
        """Get inlet type (CONSTANT, TIMEVARYING, WOMERSLEY, MRI)."""
        return self.inlet.get("type", "TIMEVARYING").upper()

    @property
    def outlet_type(self) -> str:
        """Get outlet type (zeroGradient, fixedValue, 2EWINDKESSEL, 3EWINDKESSEL)."""
        return self.outlets.get("type", "zeroGradient").upper()

    @property
    def is_windkessel(self) -> bool:
        """Check if Windkessel outlet BC is enabled."""
        return "WINDKESSEL" in self.outlet_type

    @property
    def is_pulsatile(self) -> bool:
        """Check if inlet is pulsatile (time-varying)."""
        return self.inlet_type in ["TIMEVARYING", "WOMERSLEY", "MRI"]

    # -------------------------------------------------------------------------
    # INLET BC DETAILED SETTINGS
    # -------------------------------------------------------------------------

    @property
    def inlet_velocity(self) -> Optional[float]:
        """Get inlet velocity (m/s) for CONSTANT/PARABOLIC inlet."""
        return self.inlet.get("velocity")

    @property
    def inlet_cardiac_output(self) -> Optional[float]:
        """Get cardiac output (L/min) - alternative to velocity."""
        return self.inlet.get("cardiac_output") or self.inlet.get("flowrate")

    @property
    def inlet_csv_file(self) -> Optional[str]:
        """Get CSV file path for TIMEVARYING inlet."""
        return self.inlet.get("csv_file")

    @property
    def inlet_data_type(self) -> str:
        """Get inlet data type from CSV (velocity or flowrate)."""
        return self.inlet.get("data_type", "flowrate")

    @property
    def inlet_velocity_profile(self) -> str:
        """Get inlet velocity profile shape (plug, parabolic, elliptical, wall_distance, womersley)."""
        return self.inlet.get("profile", "parabolic")

    @property
    def inlet_profile_exponent(self) -> float:
        """Get exponent for wall_distance profile (2.0=parabolic, 1.0=linear)."""
        return self.inlet.get("exponent", 2.0)

    @property
    def inlet_n_harmonics(self) -> Union[str, int]:
        """Get number of Womersley harmonics ('auto' or integer)."""
        return self.inlet.get("n_harmonics", "auto")

    @property
    def inlet_mri_file(self) -> Optional[str]:
        """Get MRI inlet data directory path."""
        return self.inlet.get("file")

    # -------------------------------------------------------------------------
    # OUTLET BC DETAILED SETTINGS
    # -------------------------------------------------------------------------

    @property
    def walls(self) -> Dict[str, Any]:
        """Get walls configuration."""
        bc = self.boundary_conditions
        return bc.get("walls") or self._config.get("walls", {})

    @property
    def wall_type(self) -> str:
        """Get wall BC type (no_slip, slip, moving_wall)."""
        return self.walls.get("type", "no_slip")

    @property
    def windkessel_settings(self) -> Dict[str, Any]:
        """Get Windkessel outlet settings."""
        return self.outlets.get("windkessel_settings", {})

    @property
    def windkessel_systolic_pressure(self) -> float:
        """Get systolic blood pressure (mmHg)."""
        return self.windkessel_settings.get("systolic_pressure", 120)

    @property
    def windkessel_diastolic_pressure(self) -> float:
        """Get diastolic blood pressure (mmHg)."""
        return self.windkessel_settings.get("diastolic_pressure", 80)

    @property
    def windkessel_venous_pressure(self) -> float:
        """Get venous/reference pressure (mmHg)."""
        return self.windkessel_settings.get("venous_pressure", 5)

    @property
    def windkessel_tau(self) -> float:
        """Get diastolic decay time constant (seconds)."""
        return self.windkessel_settings.get("tau", 1.8)

    @property
    def windkessel_betaT(self) -> float:
        """Get tangential backflow stabilization coefficient (0-1)."""
        return self.windkessel_settings.get("betaT", 0.3)

    @property
    def windkessel_betaN(self) -> float:
        """Get normal backflow stabilization coefficient (0-1)."""
        return self.windkessel_settings.get("betaN", 0.0)

    @property
    def windkessel_flow_split(self) -> Optional[Union[float, Dict[str, float]]]:
        """Get flow split configuration (None=Murray's law auto)."""
        return self.windkessel_settings.get("flow_split")

    @property
    def windkessel_order(self) -> int:
        """Get Windkessel time discretization order (1=Euler, 2=BDF2, 3=BDF3)."""
        return self.windkessel_settings.get("order", 3)

    @property
    def windkessel_coupling_mode(self) -> str:
        """Get Windkessel coupling mode (implicit or explicit)."""
        return self.windkessel_settings.get("coupling_mode", "implicit")

    @property
    def windkessel_enable_stabilization(self) -> bool:
        """Check if backflow stabilization is enabled."""
        return self.windkessel_settings.get("enable_stabilization", True)

    @property
    def windkessel_initial_pressure_method(self) -> str:
        """Get initial pressure method (diastolic, systolic, MAP, zero)."""
        return self.windkessel_settings.get("initial_pressure_method", "diastolic")

    @property
    def windkessel_outlet_parameters(self) -> Optional[Dict[str, Dict[str, float]]]:
        """Get direct R/C/Z parameters per outlet (bypasses calculation)."""
        return self.windkessel_settings.get("outlet_parameters")

    @property
    def windkessel_pwv_method(self) -> str:
        """Get pulse wave velocity calculation method (matlab, empirical, fixed)."""
        return self.windkessel_settings.get("pwv_method", "matlab")

    @property
    def windkessel_pwv(self) -> Optional[float]:
        """Get fixed pulse wave velocity (m/s) if pwv_method='fixed'."""
        return self.windkessel_settings.get("pwv")

    # =========================================================================
    # PHYSICS
    # =========================================================================

    @property
    def physics(self) -> Dict[str, Any]:
        """Get physics configuration."""
        return self._config.get("physics", {})

    @property
    def simulation_type(self) -> str:
        """Get simulation type (laminar, rans, les)."""
        return self.physics.get("simulation_type", "laminar").lower()

    @property
    def is_turbulent(self) -> bool:
        """Check if simulation uses turbulence model."""
        return self.simulation_type in ["rans", "les"]

    @property
    def is_les(self) -> bool:
        """Check if simulation uses LES."""
        return self.simulation_type == "les"

    @property
    def nu(self) -> float:
        """Get kinematic viscosity (m²/s)."""
        # Try new format first, then old format
        transport = self.physics.get("transport_properties", {})
        if "nu" in transport:
            return transport["nu"]
        if "nu" in self.physics:
            return self.physics["nu"]
        # Calculate from dynamic viscosity and density
        mu = self.physics.get("default_viscosity", 0.004)
        rho = self.physics.get("default_density", 1060)
        return mu / rho

    @property
    def rho(self) -> float:
        """Get density (kg/m³)."""
        transport = self.physics.get("transport_properties", {})
        return transport.get("rho", self.physics.get("rho", self.physics.get("default_density", 1060)))

    @property
    def turbulence_intensity(self) -> float:
        """Get turbulence intensity (fraction, e.g., 0.05 = 5%)."""
        return self.physics.get("turbulence_intensity", 0.05)

    @property
    def turbulence_model(self) -> str:
        """Get RANS turbulence model name."""
        return self.physics.get("turbulence_model", "kOmegaSST")

    @property
    def les_model(self) -> str:
        """Get LES subgrid model name."""
        return self.physics.get("les_model", "WALE")

    @property
    def physics_model(self) -> str:
        """Get physics model (laminar, RAS, LES) - maps to simulation_type."""
        model = self.physics.get("model", "laminar")
        # Normalize: RAS -> rans, LES -> les
        if model.upper() == "RAS":
            return "rans"
        elif model.upper() == "LES":
            return "les"
        return model.lower()

    # =========================================================================
    # NUMERICS
    # =========================================================================

    @property
    def numerics(self) -> Dict[str, Any]:
        """Get numerics configuration."""
        return self._config.get("numerics", {})

    @property
    def profile(self) -> str:
        """Get numerical profile name (robust, standard, precise)."""
        return self.numerics.get("profile", "standard")

    @property
    def mesh_adaptive(self) -> bool:
        """Check if mesh-adaptive schemes are enabled."""
        return self.numerics.get("mesh_adaptive", False)

    @property
    def max_co(self) -> Optional[float]:
        """Get max Courant number override (None = use profile default)."""
        return self.numerics.get("max_co")

    @property
    def adjustable_timestep(self) -> bool:
        """Check if adaptive time stepping is enabled."""
        return self.numerics.get("adjustable_timestep", True)

    @property
    def correctors(self) -> Dict[str, Any]:
        """Get PIMPLE corrector settings overrides."""
        return self.numerics.get("correctors", {})

    @property
    def relaxation_factors(self) -> Dict[str, float]:
        """Get relaxation factor overrides."""
        return self.numerics.get("relaxation_factors", {})

    @property
    def residual_control(self) -> Dict[str, float]:
        """Get residual control overrides."""
        return self.numerics.get("residual_control", {})

    # =========================================================================
    # MESH
    # =========================================================================

    @property
    def mesh(self) -> Dict[str, Any]:
        """Get mesh configuration."""
        return self._config.get("mesh", {})

    @property
    def snappy_settings(self) -> Dict[str, Any]:
        """Get snappyHexMesh settings."""
        return self.mesh.get("SNAPPY_SETTINGS", {})

    @property
    def boundary_layers(self) -> Dict[str, Any]:
        """Get boundary layer settings."""
        return self.mesh.get("boundary_layers", {})

    @property
    def mesh_resolution(self) -> Dict[str, Any]:
        """Get mesh resolution settings."""
        return self.mesh.get("mesh_resolution", {})

    # =========================================================================
    # SIMULATION CONTROL
    # =========================================================================

    @property
    def simulation_control(self) -> Dict[str, Any]:
        """Get simulation control settings."""
        return self._config.get("simulation_control", {})

    @property
    def end_time(self) -> Optional[float]:
        """Get simulation end time (None if auto-calculated)."""
        et = self.simulation_control.get("end_time")
        if et == "auto" or et is None:
            return None
        return float(et)

    @property
    def num_cycles(self) -> int:
        """Get number of cardiac cycles to simulate."""
        try:
            from aortacfd_lib.constants import DEFAULT_NUMBER_OF_CYCLES
        except ImportError:
            DEFAULT_NUMBER_OF_CYCLES = 3
        return self.simulation_control.get("number_of_cycles", DEFAULT_NUMBER_OF_CYCLES)

    @property
    def control_dict(self) -> Dict[str, Any]:
        """Get controlDict settings."""
        return self.simulation_control.get("controlDict", {})

    @property
    def write_interval(self) -> float:
        """Get write interval."""
        # Check multiple locations
        wi = self.simulation_control.get("writeInterval")
        if wi is not None:
            return wi
        return self.control_dict.get("writeInterval", 0.01)

    @property
    def cardiac_cycle(self) -> float:
        """Get cardiac cycle period (seconds)."""
        # Check multiple locations for backward compatibility
        cc = self._config.get("cardiac_cycle")
        if cc is not None:
            return cc
        return self.simulation_control.get("cardiac_cycle_period", 0.8)

    @property
    def delta_t(self) -> float:
        """Get initial time step (seconds)."""
        return self.simulation_control.get("delta_t", 1e-5)

    @property
    def write_format(self) -> str:
        """Get output write format (ascii or binary)."""
        return self.simulation_control.get("write_format", "binary")

    @property
    def purge_write(self) -> int:
        """Get purge write setting (0 = keep all)."""
        return self.simulation_control.get("purge_write", 0)

    @property
    def simulation_functions(self) -> Dict[str, Any]:
        """Get simulation function objects configuration."""
        return self.simulation_control.get("functions", {})

    @property
    def keep_last_cycles(self) -> Optional[int]:
        """Get number of last cardiac cycles to keep (None = keep all)."""
        # This is the preferred way - maps to purge_write
        klc = self.simulation_control.get("keep_last_cycles")
        if klc is not None:
            return klc
        # Fall back to purge_write
        pw = self.purge_write
        if pw > 0:
            # Convert purge_write to cycles
            return pw
        return None

    @property
    def simulation_wss_function(self) -> Dict[str, Any]:
        """Get wallShearStress function object settings from simulation_control."""
        return self.simulation_functions.get("wallShearStress", {})

    @property
    def simulation_field_average_function(self) -> Dict[str, Any]:
        """Get fieldAverage function object settings from simulation_control."""
        return self.simulation_functions.get("fieldAverage", {})

    @property
    def simulation_forces_function(self) -> Dict[str, Any]:
        """Get forces function object settings."""
        return self.simulation_functions.get("forces", {})

    @property
    def simulation_probes_function(self) -> Dict[str, Any]:
        """Get probes function object settings."""
        return self.simulation_functions.get("probes", {})

    # =========================================================================
    # RUN SETTINGS
    # =========================================================================

    @property
    def run_settings(self) -> Dict[str, Any]:
        """Get run settings."""
        return self._config.get("run_settings", {})

    @property
    def subdomains(self) -> int:
        """Get number of parallel subdomains for solver."""
        return self.run_settings.get("subdomains", 4)

    @property
    def decomposition_method(self) -> str:
        """Get decomposition method (scotch, hierarchical, simple)."""
        return self.run_settings.get("decomposition_method", "scotch")

    @property
    def solution_type(self) -> str:
        """Get solution type (serial or parallel)."""
        return self.run_settings.get("solution_type", "parallel")

    @property
    def is_parallel(self) -> bool:
        """Check if running in parallel mode."""
        return self.solution_type == "parallel"

    @property
    def decomposition_coeffs(self) -> Dict[str, Any]:
        """Get decomposition coefficients (for simple method)."""
        return self.run_settings.get("decomposition_coeffs", {})

    # =========================================================================
    # HEMODYNAMICS
    # =========================================================================

    @property
    def hemodynamics(self) -> Dict[str, Any]:
        """Get hemodynamics settings."""
        return self._config.get("hemodynamics", {})

    @property
    def runtime_functions(self) -> Dict[str, Any]:
        """Get hemodynamics runtime function settings."""
        return self.hemodynamics.get("runtime_functions", {})

    @property
    def runtime_wss_enabled(self) -> bool:
        """Check if runtime wall shear stress computation is enabled."""
        return self.runtime_functions.get("wallShearStress", True)

    @property
    def runtime_field_average(self) -> Union[bool, str]:
        """Get field averaging setting (True, False, or 'auto')."""
        return self.runtime_functions.get("fieldAverage", "auto")

    @property
    def runtime_velocity_field_average(self) -> bool:
        """Check if velocity field averaging (UMean, UPrime2Mean) is enabled."""
        return self.runtime_functions.get("velocityFieldAverage", False)

    @property
    def runtime_pressure_monitoring(self) -> bool:
        """Check if pressure monitoring at patches is enabled."""
        return self.runtime_functions.get("pressureMonitoring", True)

    @property
    def tawss_settings(self) -> Dict[str, Any]:
        """Get TAWSS computation settings."""
        return self.hemodynamics.get("tawss_settings", {})

    @property
    def tawss_skip_cycles(self) -> int:
        """Get number of initial cardiac cycles to skip before averaging."""
        return self.tawss_settings.get("skip_cycles", 2)

    @property
    def tawss_periodic_restart(self) -> bool:
        """Check if averaging restarts each cardiac cycle."""
        return self.tawss_settings.get("periodicRestart", True)

    @property
    def tawss_keep_all_cycles(self) -> bool:
        """Check if TAWSS data from all cycles is kept."""
        return self.tawss_settings.get("keep_all_cycles", True)

    # =========================================================================
    # POST-PROCESSING
    # =========================================================================

    @property
    def post_processing(self) -> Dict[str, Any]:
        """Get post-processing settings."""
        return self._config.get("post_processing", {})

    @property
    def compute_hemodynamics_enabled(self) -> bool:
        """Check if hemodynamic indices computation is enabled."""
        return self.post_processing.get("compute_hemodynamics", True)

    @property
    def extract_surfaces_settings(self) -> Dict[str, Any]:
        """Get surface extraction settings."""
        return self.post_processing.get("extract_surfaces", {})

    @property
    def extract_surfaces_enabled(self) -> bool:
        """Check if surface extraction is enabled."""
        settings = self.extract_surfaces_settings
        if isinstance(settings, dict):
            return settings.get("enabled", True)
        return bool(settings)

    @property
    def extract_surfaces_patches(self) -> List[str]:
        """Get patches for surface extraction."""
        settings = self.extract_surfaces_settings
        if isinstance(settings, dict):
            return settings.get("patches", [self.wall_patch_name])
        return [self.wall_patch_name]

    @property
    def extract_surfaces_time_points(self) -> Union[str, List[float]]:
        """Get time points for surface extraction ('all', 'last', or list)."""
        settings = self.extract_surfaces_settings
        if isinstance(settings, dict):
            return settings.get("time_points", "all")
        return "all"

    @property
    def compute_flow_rate_settings(self) -> Dict[str, Any]:
        """Get flow rate computation settings."""
        return self.post_processing.get("compute_flow_rate", {})

    @property
    def compute_flow_rate_enabled(self) -> bool:
        """Check if flow rate computation is enabled."""
        settings = self.compute_flow_rate_settings
        if isinstance(settings, dict):
            return settings.get("enabled", True)
        return bool(settings)

    @property
    def compute_flow_rate_patches(self) -> List[str]:
        """Get patches for flow rate computation."""
        settings = self.compute_flow_rate_settings
        if isinstance(settings, dict):
            patches = settings.get("patches", [])
            if patches:
                return patches
        # Default: inlet + all outlets
        return [self.inlet_patch_name] + self.outlet_patch_names

    @property
    def pressure_drop_settings(self) -> Dict[str, Any]:
        """Get pressure drop computation settings."""
        return self.post_processing.get("pressure_drop", {})

    @property
    def pressure_drop_enabled(self) -> bool:
        """Check if pressure drop computation is enabled."""
        settings = self.pressure_drop_settings
        if isinstance(settings, dict):
            return settings.get("enabled", True)
        return bool(settings)

    @property
    def pressure_drop_inlet_patch(self) -> str:
        """Get inlet patch for pressure drop calculation."""
        settings = self.pressure_drop_settings
        if isinstance(settings, dict):
            return settings.get("inlet_patch", self.inlet_patch_name)
        return self.inlet_patch_name

    @property
    def pressure_drop_outlet_patches(self) -> List[str]:
        """Get outlet patches for pressure drop calculation."""
        settings = self.pressure_drop_settings
        if isinstance(settings, dict):
            patches = settings.get("outlet_patches", [])
            if patches:
                return patches
        return self.outlet_patch_names

    # =========================================================================
    # VISUALIZATION
    # =========================================================================

    @property
    def visualization(self) -> Dict[str, Any]:
        """Get visualization settings."""
        return self._config.get("visualization", {})

    # =========================================================================
    # ADVANCED SETTINGS
    # =========================================================================

    @property
    def advanced(self) -> Dict[str, Any]:
        """Get advanced settings."""
        return self._config.get("advanced", {})

    @property
    def custom_templates(self) -> Dict[str, Any]:
        """Get custom templates settings."""
        return self.advanced.get("custom_templates", {})

    @property
    def custom_templates_enabled(self) -> bool:
        """Check if custom templates are enabled."""
        return self.custom_templates.get("enabled", False)

    @property
    def solver_overrides(self) -> Dict[str, Any]:
        """Get solver algorithm overrides."""
        return self.advanced.get("solver_overrides", {})

    @property
    def momentum_predictor(self) -> bool:
        """Get momentum predictor setting."""
        return self.solver_overrides.get("momentum_predictor", True)

    @property
    def pimple_consistent(self) -> bool:
        """Get PIMPLE consistent algorithm setting."""
        return self.solver_overrides.get("consistent", False)

    @property
    def turb_on_final_iter_only(self) -> bool:
        """Get turbOnFinalIterOnly setting."""
        return self.solver_overrides.get("turbOnFinalIterOnly", True)

    # =========================================================================
    # OPENFOAM SETTINGS
    # =========================================================================

    @property
    def openfoam_version(self) -> str:
        """Get OpenFOAM version."""
        return self._config.get("openfoam_version", "12")

    @property
    def solver_application(self) -> str:
        """Get solver application name."""
        return self._config.get("solver_application", "foamRun")

    @property
    def solver_module(self) -> str:
        """Get solver module name."""
        return self._config.get("solver_module", "incompressibleFluid")


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================


def wrap_config(config: Union[Dict[str, Any], Config]) -> Config:
    """
    Wrap a config dict in Config accessor if not already wrapped.

    Args:
        config: Either a raw dict or already a Config instance

    Returns:
        Config instance
    """
    if isinstance(config, Config):
        return config
    return Config(config)
