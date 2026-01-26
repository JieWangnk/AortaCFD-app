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
    # GEOMETRY
    # =========================================================================

    @property
    def geometry(self) -> Dict[str, Any]:
        """Get geometry configuration."""
        return self._config.get('geometry', {})

    @property
    def case_name(self) -> str:
        """Get case name."""
        return self.geometry.get('case_name', '')

    @property
    def scale_factor(self) -> float:
        """Get geometry scale factor (default: 0.001 for mm->m)."""
        return self.geometry.get('scale_factor', 0.001)

    @property
    def inlet_patch_name(self) -> str:
        """Get inlet patch name from geometry."""
        return self.geometry.get('inlet_keywords_ordered', '')

    @property
    def outlet_patch_names(self) -> List[str]:
        """Get outlet patch names from geometry."""
        outlets = self.geometry.get('outlet_keywords_ordered', [])
        if isinstance(outlets, str):
            return [outlets]
        return outlets

    @property
    def wall_patch_name(self) -> str:
        """Get wall patch name from geometry."""
        return self.geometry.get('wall_keywords_ordered', '')

    # =========================================================================
    # BOUNDARY CONDITIONS (handles nested and flattened)
    # =========================================================================

    @property
    def boundary_conditions(self) -> Dict[str, Any]:
        """Get boundary conditions section."""
        return self._config.get('boundary_conditions', {})

    @property
    def inlet(self) -> Dict[str, Any]:
        """
        Get inlet configuration.

        Handles both:
        - boundary_conditions.inlet (nested)
        - inlet (flattened)
        """
        bc = self.boundary_conditions
        return bc.get('inlet') or self._config.get('inlet', {})

    @property
    def outlets(self) -> Dict[str, Any]:
        """
        Get outlets configuration.

        Handles both:
        - boundary_conditions.outlets (nested)
        - outlets (flattened)
        """
        bc = self.boundary_conditions
        return bc.get('outlets') or self._config.get('outlets', {})

    @property
    def inlet_type(self) -> str:
        """Get inlet type (CONSTANT, TIMEVARYING, WOMERSLEY, MRI)."""
        return self.inlet.get('type', 'TIMEVARYING').upper()

    @property
    def outlet_type(self) -> str:
        """Get outlet type (zeroGradient, fixedValue, 2EWINDKESSEL, 3EWINDKESSEL)."""
        return self.outlets.get('type', 'zeroGradient').upper()

    @property
    def is_windkessel(self) -> bool:
        """Check if Windkessel outlet BC is enabled."""
        return 'WINDKESSEL' in self.outlet_type

    @property
    def is_pulsatile(self) -> bool:
        """Check if inlet is pulsatile (time-varying)."""
        return self.inlet_type in ['TIMEVARYING', 'WOMERSLEY', 'MRI']

    # =========================================================================
    # PHYSICS
    # =========================================================================

    @property
    def physics(self) -> Dict[str, Any]:
        """Get physics configuration."""
        return self._config.get('physics', {})

    @property
    def simulation_type(self) -> str:
        """Get simulation type (laminar, rans, les)."""
        return self.physics.get('simulation_type', 'laminar').lower()

    @property
    def is_turbulent(self) -> bool:
        """Check if simulation uses turbulence model."""
        return self.simulation_type in ['rans', 'les']

    @property
    def is_les(self) -> bool:
        """Check if simulation uses LES."""
        return self.simulation_type == 'les'

    @property
    def nu(self) -> float:
        """Get kinematic viscosity (m²/s)."""
        # Try new format first, then old format
        transport = self.physics.get('transport_properties', {})
        if 'nu' in transport:
            return transport['nu']
        if 'nu' in self.physics:
            return self.physics['nu']
        # Calculate from dynamic viscosity and density
        mu = self.physics.get('default_viscosity', 0.004)
        rho = self.physics.get('default_density', 1060)
        return mu / rho

    @property
    def rho(self) -> float:
        """Get density (kg/m³)."""
        transport = self.physics.get('transport_properties', {})
        return transport.get('rho', self.physics.get('rho',
               self.physics.get('default_density', 1060)))

    # =========================================================================
    # NUMERICS
    # =========================================================================

    @property
    def numerics(self) -> Dict[str, Any]:
        """Get numerics configuration."""
        return self._config.get('numerics', {})

    @property
    def profile(self) -> str:
        """Get numerical profile name (robust, standard, precise)."""
        return self.numerics.get('profile', 'standard')

    @property
    def mesh_adaptive(self) -> bool:
        """Check if mesh-adaptive schemes are enabled."""
        return self.numerics.get('mesh_adaptive', False)

    # =========================================================================
    # MESH
    # =========================================================================

    @property
    def mesh(self) -> Dict[str, Any]:
        """Get mesh configuration."""
        return self._config.get('mesh', {})

    @property
    def snappy_settings(self) -> Dict[str, Any]:
        """Get snappyHexMesh settings."""
        return self.mesh.get('SNAPPY_SETTINGS', {})

    @property
    def boundary_layers(self) -> Dict[str, Any]:
        """Get boundary layer settings."""
        return self.mesh.get('boundary_layers', {})

    @property
    def mesh_resolution(self) -> Dict[str, Any]:
        """Get mesh resolution settings."""
        return self.mesh.get('mesh_resolution', {})

    # =========================================================================
    # SIMULATION CONTROL
    # =========================================================================

    @property
    def simulation_control(self) -> Dict[str, Any]:
        """Get simulation control settings."""
        return self._config.get('simulation_control', {})

    @property
    def end_time(self) -> Optional[float]:
        """Get simulation end time (None if auto-calculated)."""
        et = self.simulation_control.get('end_time')
        if et == 'auto' or et is None:
            return None
        return float(et)

    @property
    def num_cycles(self) -> int:
        """Get number of cardiac cycles to simulate."""
        return self.simulation_control.get('number_of_cycles', 3)

    @property
    def control_dict(self) -> Dict[str, Any]:
        """Get controlDict settings."""
        return self.simulation_control.get('controlDict', {})

    @property
    def write_interval(self) -> float:
        """Get write interval."""
        return self.control_dict.get('writeInterval', 0.01)

    # =========================================================================
    # RUN SETTINGS
    # =========================================================================

    @property
    def run_settings(self) -> Dict[str, Any]:
        """Get run settings."""
        return self._config.get('run_settings', {})

    @property
    def subdomains(self) -> int:
        """Get number of parallel subdomains for solver."""
        return self.run_settings.get('subdomains', 4)

    @property
    def decomposition_method(self) -> str:
        """Get decomposition method (scotch, hierarchical, simple)."""
        return self.run_settings.get('decomposition_method', 'scotch')

    # =========================================================================
    # HEMODYNAMICS & POST-PROCESSING
    # =========================================================================

    @property
    def hemodynamics(self) -> Dict[str, Any]:
        """Get hemodynamics settings."""
        return self._config.get('hemodynamics', {})

    @property
    def visualization(self) -> Dict[str, Any]:
        """Get visualization settings."""
        return self._config.get('visualization', {})

    # =========================================================================
    # OPENFOAM SETTINGS
    # =========================================================================

    @property
    def openfoam_version(self) -> str:
        """Get OpenFOAM version."""
        return self._config.get('openfoam_version', '12')

    @property
    def solver_application(self) -> str:
        """Get solver application name."""
        return self._config.get('solver_application', 'foamRun')

    @property
    def solver_module(self) -> str:
        """Get solver module name."""
        return self._config.get('solver_module', 'incompressibleFluid')


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
