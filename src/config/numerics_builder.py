"""Numerics configuration builder for OpenFOAM discretization schemes.

This module loads numeric profiles and applies user overrides to generate
complete fvSchemes and fvSolution configurations.
"""

import warnings
import logging
from typing import Any, Dict, Optional
from copy import deepcopy
from enum import Enum


class NumericProfile(str, Enum):
    """Available numeric profile names (avoids magic strings)."""
    CONSERVATIVE = 'conservative'
    STANDARD = 'standard'
    PUBLICATION = 'publication'
    AGGRESSIVE = 'aggressive'


class NumericsBuilder:
    """
    Build numerics configuration from profiles and user overrides.

    Process:
    1. Load base numeric profile (conservative, standard, publication, aggressive)
    2. Apply high-level overrides (max_co, correctors, relaxation)
    3. Apply patches (advanced scheme overrides)
    4. Validate compatibility with physics model
    """

    def __init__(self):
        self.logger = logging.getLogger("NumericsBuilder")

        # Import profiles (lazy to avoid circular imports)
        from .profiles.numerics import NUMERICS_PROFILES
        self.profiles = NUMERICS_PROFILES

    def build(self, config: dict) -> dict:
        """
        Build complete numerics configuration from user config.

        Args:
            config: Full configuration dictionary containing 'physics' and 'numerics'

        Returns:
            Complete numerics configuration dictionary ready for template rendering

        Raises:
            TypeError: If config is not a dictionary
            ValueError: If required keys are missing

        Example:
            >>> config = {
            ...     "physics": {"model": "rans"},
            ...     "numerics": {
            ...         "profile": "standard",
            ...         "max_co": 0.8,
            ...         "correctors": {"nOuterCorrectors": 3}
            ...     }
            ... }
            >>> builder = NumericsBuilder()
            >>> numerics = builder.build(config)
        """
        # Input validation
        if not isinstance(config, dict):
            raise TypeError(
                f"config must be a dictionary, got {type(config).__name__}"
            )

        # Check required keys
        required_keys = ['physics', 'numerics']
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise ValueError(
                f"Configuration missing required keys: {missing_keys}. "
                f"Expected keys: {required_keys}"
            )

        numerics_config = config.get('numerics', {})
        physics_config = config.get('physics', {})

        # Validate nested structures
        if not isinstance(numerics_config, dict):
            raise TypeError(f"config['numerics'] must be a dict, got {type(numerics_config).__name__}")
        if not isinstance(physics_config, dict):
            raise TypeError(f"config['physics'] must be a dict, got {type(physics_config).__name__}")

        # Default to standard profile if not specified
        profile_name = numerics_config.get('profile', 'standard')

        # Load base profile
        self.logger.info(f"Loading numeric profile: {profile_name}")
        numerics = self._load_profile(profile_name)

        # Apply high-level overrides
        numerics = self._apply_overrides(numerics, numerics_config)

        # Apply patches (advanced scheme overrides)
        if 'patches' in numerics_config:
            self.logger.info(f"Applying {len(numerics_config['patches'])} scheme patches")
            numerics = self._apply_patches(numerics, numerics_config['patches'])

        # Validate compatibility with physics model
        self._validate_numerics(numerics, physics_config, profile_name)

        return numerics

    def _load_profile(self, profile_name: str) -> dict:
        """
        Load numeric profile by name.

        Args:
            profile_name: One of 'conservative', 'standard', 'publication', 'aggressive'

        Returns:
            Deep copy of profile configuration

        Raises:
            ValueError: If profile name is unknown
        """
        if profile_name not in self.profiles:
            available = ", ".join(self.profiles.keys())
            raise ValueError(
                f"Unknown numeric profile '{profile_name}'. "
                f"Available profiles: {available}"
            )

        # Deep copy to avoid modifying the original
        return deepcopy(self.profiles[profile_name])

    def _apply_overrides(self, numerics: dict, numerics_config: dict) -> dict:
        """
        Apply high-level user overrides to numeric profile.

        Supported overrides:
        - max_co: Maximum Courant number
        - time_discretization: ddtScheme override
        - correctors: PIMPLE corrector settings
        - under_relaxation: Relaxation factors

        Args:
            numerics: Base numeric profile
            numerics_config: User numerics configuration

        Returns:
            Updated numerics dictionary
        """
        # Override max Courant number
        if 'max_co' in numerics_config:
            max_co = numerics_config['max_co']
            self.logger.info(f"Overriding max_co: {numerics['time_stepping']['max_co']} → {max_co}")
            numerics['time_stepping']['max_co'] = max_co

        # Override time discretization
        if 'time_discretization' in numerics_config:
            time_scheme = numerics_config['time_discretization']
            self.logger.info(f"Overriding time scheme: {numerics['ddtSchemes']['default']} → {time_scheme}")
            numerics['ddtSchemes']['default'] = time_scheme

        # Override correctors
        if 'correctors' in numerics_config:
            for key, value in numerics_config['correctors'].items():
                if key in numerics['solvers']['PIMPLE']:
                    old_value = numerics['solvers']['PIMPLE'][key]
                    self.logger.info(f"Overriding {key}: {old_value} → {value}")
                    numerics['solvers']['PIMPLE'][key] = value
                else:
                    self.logger.warning(f"Unknown corrector setting: {key}")

        # Override under-relaxation factors
        if 'under_relaxation' in numerics_config:
            for field, factor in numerics_config['under_relaxation'].items():
                # Determine if field or equation relaxation
                if field in ['p', 'rgh', 'p_rgh']:
                    target = numerics['solvers']['relaxationFactors']['fields']
                    old_value = target.get(field, 'N/A')
                    self.logger.info(f"Overriding field relaxation {field}: {old_value} → {factor}")
                    target[field] = factor
                else:
                    target = numerics['solvers']['relaxationFactors']['equations']
                    old_value = target.get(field, 'N/A')
                    self.logger.info(f"Overriding equation relaxation {field}: {old_value} → {factor}")
                    target[field] = factor

        return numerics

    def _apply_patches(self, numerics: dict, patches: dict) -> dict:
        """
        Apply targeted scheme overrides (expert feature).

        Patches use dotted key paths to override specific dictionary entries.

        Examples:
            "divSchemes.div(phi,U)": "Gauss limitedLinearV 1.0"
            "solvers.PIMPLE.nNonOrthogonalCorrectors": 3
            "ddtSchemes.default": "CrankNicolson 0.8"

        Args:
            numerics: Numerics configuration
            patches: Dictionary of key_path → value

        Returns:
            Updated numerics dictionary
        """
        for key_path, value in patches.items():
            self._apply_patch(numerics, key_path, value)

        return numerics

    def _apply_patch(self, numerics: dict, key_path: str, value: Any):
        """
        Apply a single patch to numerics configuration.

        Args:
            numerics: Numerics configuration (modified in place)
            key_path: Dotted key path (e.g., "divSchemes.div(phi,U)")
            value: New value to set
        """
        keys = key_path.split('.')

        # Navigate to parent dictionary
        target = numerics
        for key in keys[:-1]:
            if key not in target:
                self.logger.warning(f"Patch key path '{key_path}' not found in profile. Creating new entry.")
                target[key] = {}
            target = target[key]

        # Set value
        final_key = keys[-1]
        old_value = target.get(final_key, 'N/A')

        self.logger.info(f"Patch '{key_path}': {old_value} → {value}")
        target[final_key] = value

    def _validate_numerics(self, numerics: dict, physics: dict, profile_name: str):
        """
        Validate numerics are appropriate for physics model.

        Issues warnings for potentially problematic combinations:
        - Pure central differencing (Gauss linear) with RANS → may need stabilization
        - First-order upwind with LES → excessive numerical diffusion
        - Small max_co with laminar → unnecessarily slow
        - Publication profile without explicit mesh verification plan

        Args:
            numerics: Numerics configuration
            physics: Physics configuration
            profile_name: Name of selected profile
        """
        model = physics.get('model', 'laminar')

        # Check convection scheme compatibility
        u_scheme = numerics['divSchemes'].get('div(phi,U)', '')

        # Warning: Upwind with LES
        if model == 'les' and 'upwind' in u_scheme.lower():
            warnings.warn(
                f"\n⚠️  LES NUMERICS WARNING\n"
                f"─────────────────────────\n"
                f"LES with upwind convection scheme '{u_scheme}' will introduce "
                f"excessive numerical diffusion that interferes with SGS modeling.\n\n"
                f"Recommendation:\n"
                f"  - Use 'Gauss linear' (central) for wall-resolved LES\n"
                f"  - Use 'Gauss LUST' (hybrid) if stability issues\n\n"
                f"See: Pope (2000), Turbulent Flows; Sagaut (2006), Large Eddy Simulation\n",
                UserWarning,
                stacklevel=2
            )

        # Warning: Pure central with RANS
        if model == 'rans' and u_scheme == 'Gauss linear':
            warnings.warn(
                f"\n⚠️  RANS NUMERICS WARNING\n"
                f"────────────────────────\n"
                f"Pure central differencing with RANS may cause numerical instability.\n\n"
                f"Recommendation:\n"
                f"  - Use 'Gauss limitedLinear 1' (bounded 2nd order)\n"
                f"  - Use 'Gauss linearUpwind grad(U)' (upwind-biased)\n"
                f"  - Use 'Gauss LUST grad(U)' (hybrid for publication)\n\n"
                f"See: OpenFOAM User Guide, Section 4.4.2\n",
                UserWarning,
                stacklevel=2
            )

        # Warning: First-order with any model
        if 'upwind' in u_scheme.lower() and u_scheme == 'Gauss upwind':
            self.logger.warning(
                f"\n⚠️  FIRST-ORDER SCHEME DETECTED\n"
                f"──────────────────────────────\n"
                f"Using first-order upwind convection (profile: {profile_name}).\n"
                f"Results will have numerical diffusion and are NOT publication quality.\n\n"
                f"Appropriate for:\n"
                f"  - Debugging/initial testing\n"
                f"  - Poor mesh quality (as temporary fix)\n\n"
                f"NOT appropriate for:\n"
                f"  - Final results\n"
                f"  - Clinical decision-making\n"
                f"  - Publications\n\n"
                f"Consider switching to 'standard' or 'publication' profile for production runs.\n"
            )

        # Warning: High CFL with LES
        max_co = numerics['time_stepping'].get('max_co', 1.0)
        if model == 'les' and max_co > 0.5:
            warnings.warn(
                f"\n⚠️  LES TIME-STEPPING WARNING\n"
                f"────────────────────────────\n"
                f"LES typically requires max_co ≤ 0.5 for accuracy.\n"
                f"Current setting: max_co = {max_co}\n\n"
                f"Recommendation: Reduce to 0.3-0.5 for wall-resolved LES\n",
                UserWarning,
                stacklevel=2
            )

        # Info: Publication profile requirements
        if profile_name == 'publication':
            self.logger.info(
                f"\n✓ PUBLICATION PROFILE SELECTED\n"
                f"────────────────────────────────\n"
                f"Remember to perform validation studies:\n"
                f"  1. Mesh independence: 3 levels, calculate GCI\n"
                f"  2. Temporal convergence: halve Δt, verify < 1% change\n"
                f"  3. Residuals: < 1e-8 for all variables\n"
                f"  4. Compare to reference data if available\n"
                f"  5. Document numerical choices in paper methods section\n\n"
                f"See: docs/NUMERICS_PROFILES_IMPLEMENTATION.md\n"
            )

        # Info: Aggressive profile requirements
        if profile_name == 'aggressive':
            self.logger.warning(
                f"\n⚠️  AGGRESSIVE PROFILE - EXPERT ONLY\n"
                f"────────────────────────────────────\n"
                f"This profile uses UNBOUNDED central differencing.\n\n"
                f"STRICT requirements:\n"
                f"  - Mesh: cells_per_diameter ≥ 25, y+ < 1\n"
                f"  - Quality: orthogonality > 80°, skewness < 1\n"
                f"  - Time: max_co ≤ 0.3 (very small steps)\n"
                f"  - Model: Must be LES or DNS (NOT RANS)\n\n"
                f"WILL DIVERGE if requirements not met!\n\n"
                f"See: src/config/profiles/numerics/aggressive.py for details\n"
            )

    def get_profile_metadata(self, profile_name: str) -> dict:
        """
        Get metadata for a specific profile.

        Args:
            profile_name: Profile name

        Returns:
            Profile metadata dictionary

        Example:
            >>> builder = NumericsBuilder()
            >>> meta = builder.get_profile_metadata('standard')
            >>> print(meta['order_of_accuracy'])
            2
        """
        profile = self._load_profile(profile_name)
        return profile.get('_profile_metadata', {})

    def list_available_profiles(self) -> dict:
        """
        List all available numeric profiles with brief descriptions.

        Returns:
            Dictionary mapping profile names to summary info
        """
        return {
            name: {
                'order': profile['_profile_metadata']['order_of_accuracy'],
                'stability': profile['_profile_metadata']['stability'],
                'intended_use': profile['_profile_metadata']['intended_use']
            }
            for name, profile in self.profiles.items()
        }


def recommend_numerics_profile(mesh_quality: dict, objective: str = 'production',
                                physics_model: str = 'laminar') -> str:
    """
    Recommend numeric profile based on mesh quality, objective, and physics.

    Args:
        mesh_quality: Dict with keys 'orthogonality' (degrees), 'skewness'
        objective: One of 'debug', 'production', 'publication', 'les'
        physics_model: One of 'laminar', 'rans', 'les'

    Returns:
        Recommended profile name

    Example:
        >>> recommend_numerics_profile(
        ...     mesh_quality={'orthogonality': 65, 'skewness': 2.5},
        ...     objective='production',
        ...     physics_model='rans'
        ... )
        'standard'
    """
    ortho = mesh_quality.get('orthogonality', 0)
    skew = mesh_quality.get('skewness', 10)

    # Debug mode - always conservative
    if objective == 'debug':
        return 'conservative'

    # LES mode - requires excellent mesh
    if objective == 'les' or physics_model == 'les':
        if ortho > 80 and skew < 1:
            return 'aggressive'  # Can use unbounded schemes
        elif ortho > 70 and skew < 2:
            return 'publication'  # Use LUST (bounded hybrid)
        else:
            logging.warning(
                f"LES requires excellent mesh quality (ortho > 70°, skew < 2). "
                f"Current: ortho={ortho}°, skew={skew}. "
                f"Falling back to 'standard', but consider improving mesh."
            )
            return 'standard'

    # Publication mode
    if objective == 'publication':
        if ortho > 70 and skew < 2:
            return 'publication'
        else:
            logging.warning(
                f"Publication profile requires ortho > 70°, skew < 2. "
                f"Current: ortho={ortho}°, skew={skew}. "
                f"Using 'standard' instead. Consider improving mesh for publication."
            )
            return 'standard'

    # Production mode (default)
    if ortho < 60 or skew > 3:
        logging.info(
            f"Mesh quality below recommended levels (ortho={ortho}°, skew={skew}). "
            f"Using 'conservative' profile for stability. "
            f"Consider improving mesh and switching to 'standard'."
        )
        return 'conservative'
    else:
        return 'standard'


__all__ = [
    'NumericsBuilder',
    'recommend_numerics_profile',
]
