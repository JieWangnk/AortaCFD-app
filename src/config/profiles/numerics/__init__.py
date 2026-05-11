"""Numeric profiles for OpenFOAM discretization schemes and solver settings.

IMPORTANT DISCLAIMER
====================
These profiles control NUMERICAL SCHEMES ONLY:
  - fvSchemes (discretization)
  - fvSolution (solvers, tolerances)
  - Time stepping (Courant number, correctors)

Presets do NOT and CANNOT guarantee:
  - Solution accuracy (depends on mesh resolution, physics, BCs)
  - Mesh independence (requires convergence study with Richardson extrapolation)
  - Physical validity (requires validation against experiments/literature)
  - Publication readiness (requires all of the above + proper documentation)

A preset NEVER makes a CFD solution scientifically publishable.
Only a properly conducted convergence study can.

3-PROFILE SYSTEM
================
This module provides 3 universal profiles that work for ALL physics models
(laminar, RANS k-ω SST, LES WALE).

AVAILABLE PROFILES
==================

robust
------
First-order schemes, maximum stability.
USE FOR: Debugging, poor mesh quality, initial testing, coarse mesh runs
SCHEMES: Euler time, upwind convection
TRADE-OFF: Stable but highly diffusive (damps physical gradients)
COST: Low (1x baseline)
MESH: Any quality

standard
--------
Second-order with TVD bounded schemes and robust stability measures.
USE FOR: ALL production runs (DEFAULT choice), Windkessel outlets, pulsatile flows
SCHEMES: backward time, limitedLinearV convection (TVD), limited corrected 0.5
STABILITY FEATURES: TVD bounded, cellLimited 0.5, pFinal/UFinal=1
TRADE-OFF: High stability with 2nd order accuracy
COST: Moderate (1.2x baseline)
MESH: ortho > 50°, skewness < 4

precise
-------
Second-order with MINIMAL numerical diffusion for LES/validation.
USE FOR: LES simulations, final validation, minimal diffusion required
SCHEMES: CrankNicolson 0.9 time, LUST convection (75% central + 25% upwind)
TRADE-OFF: Minimal diffusion, requires EXCELLENT mesh, longer runtime
COST: Higher (2-3x baseline)
MESH: ortho > 70°, skewness < 2 (REQUIRED)
NOTE: LUST is REQUIRED for LES to preserve resolved turbulence.

PROFILE SELECTION GUIDE
=======================

┌──────────────────────────────────────────────────────────────────────────────┐
│ START: What numerical characteristics do you need?                          │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
    Max stability?            Production?              Min diffusion?
    Poor mesh?                Windkessel?              LES? Validation?
    Debugging?                Clinical?                Excellent mesh?
          │                         │                         │
          ▼                         ▼                         ▼
        ROBUST                  STANDARD                  PRECISE
      1st order               2nd TVD bound             2nd LUST+CN
      Max stable              High stable               Min diffusion

IMPORTANT: None of these guarantee accuracy - that requires mesh convergence.

PHYSICS-SPECIFIC RECOMMENDATIONS
=================================

Laminar:
  - Debug:            robust
  - Production:       standard
  - Validation/GCI:   precise

RANS (k-ω SST):
  - Debug:            robust
  - Production:       standard (recommended)
  - Validation/GCI:   precise (if mesh quality permits)

LES (WALE):
  - Debug:            standard (quick test only)
  - Production/Final: precise (REQUIRED - LUST preserves turbulence)

MESH QUALITY REQUIREMENTS
==========================

Profile    Orthogonality  Skewness  y+ (RANS)    y+ (LES)
---------  -------------  --------  -----------  ---------
robust     > 50°          < 4       Any          Any
standard   > 50°          < 4       1-10         < 1
precise    > 70°          < 2       1-10         < 1 (required)

USAGE IN CONFIG
===============

Minimal (use profile defaults):
```json
{
  "numerics": {
    "profile": "standard"
  }
}
```

With high-level overrides:
```json
{
  "numerics": {
    "profile": "precise",
    "max_co": 0.8
  }
}
```

DEPRECATED PROFILES
===================
The following profiles have been removed for simplicity:
- conservative (use "robust" instead)
- publication (use "precise" instead)
- aggressive (use "precise" instead)
- accurate (use "precise" instead - similar schemes, LUST has lower diffusion)

If you encounter errors about missing profiles, update your config to use
one of the 3 current profiles: robust, standard, precise.

MIGRATION GUIDE
===============
Old Profile      → New Profile   Reason
-------------    -------------   ------
conservative     → robust        Same schemes (Euler + upwind)
publication      → precise       Similar accuracy, LUST for minimal diffusion
aggressive       → precise       LUST provides stability with low diffusion
accurate         → precise       Similar purpose, LUST has lower diffusion than linearUpwind

REFERENCES
==========

1. OpenFOAM User Guide v11+
   https://doc.cfd.direct/openfoam/user-guide-v11/

2. Friess, C., Manceau, R., Gatski, T.B. (2015).
   Toward an equivalence criterion for hybrid RANS/LES methods.
   Computers & Fluids, 122, 233-246. (LUST scheme)

3. Roache, P.J. (1998). Verification of Codes and Calculations.
   AIAA Journal, 36(5), 696-702. (Grid Convergence Index)
"""

from typing import Dict, Any
import logging

# Import the 3 core profiles
from .robust import config as robust_config
from .standard import config as standard_config
from .precise import config as precise_config

# Get logger
logger = logging.getLogger(__name__)

# Profile registry - 3 PROFILES
NUMERICS_PROFILES = {
    "robust": robust_config,  # 1st order, maximum stability
    "standard": standard_config,  # 2nd order TVD bounded (backward + limitedLinearV)
    "precise": precise_config,  # 2nd order minimal diffusion (CN 0.9 + LUST)
}

# Deprecated profile mapping for helpful error messages
DEPRECATED_PROFILES = {
    "conservative": {"replacement": "robust", "reason": "Identical schemes (Euler + upwind), simplified naming"},
    "publication": {
        "replacement": "precise",
        "reason": "Misleading name removed. LUST scheme in 'precise' has minimal diffusion. Note: profile choice alone does not make results publication-ready - convergence study required.",
    },
    "aggressive": {
        "replacement": "precise",
        "reason": "Pure central differencing is unstable. LUST provides comparable accuracy with stability.",
        "note": "If you need unbounded schemes for DNS, manually override divSchemes in your config.",
    },
    "accurate": {
        "replacement": "precise",
        "reason": "Consolidated into 3-profile system. 'precise' (LUST + CrankNicolson) has lower diffusion than 'accurate' (linearUpwind + backward) while maintaining stability.",
    },
}

# Profile metadata for quick reference
# Note: These describe NUMERICAL characteristics, not solution accuracy
PROFILE_METADATA = {
    "robust": {
        "order_of_accuracy": 1,
        "stability": "maximum",
        "numerical_diffusion": "high (damps gradients)",
        "intended_use": "debugging, poor meshes, initial testing",
        "physics_models": ["laminar", "rans", "les"],
        "best_for": "debug runs and stability testing",
        "limitations": "high numerical diffusion masks physics",
        "mesh_requirements": "orthogonality > 50°, skewness < 4",
    },
    "standard": {
        "order_of_accuracy": 2,
        "stability": "high",
        "numerical_diffusion": "moderate (TVD bounded)",
        "intended_use": "production runs, clinical studies, Windkessel outlets",
        "physics_models": ["laminar", "rans", "les"],
        "best_for": "stable production simulations with 2nd order accuracy",
        "mesh_requirements": "orthogonality > 50°, skewness < 4",
    },
    "precise": {
        "order_of_accuracy": 2,
        "stability": "good (requires excellent mesh)",
        "numerical_diffusion": "minimal (LUST preserves gradients)",
        "intended_use": "LES, final validation, minimal diffusion required",
        "physics_models": ["laminar", "rans", "les"],
        "best_for": "LES (LUST preserves turbulence), minimal diffusion cases",
        "mesh_requirements": "orthogonality > 70°, skewness < 2, y+ < 1 for LES",
        "note": "LUST is REQUIRED for LES to preserve resolved turbulence",
    },
}


def get_profile(name: str) -> Dict[str, Any]:
    """
    Get numeric profile configuration by name.

    Args:
        name: Profile name (robust, standard, accurate, precise)

    Returns:
        Profile configuration dictionary

    Raises:
        ValueError: If profile name is unknown or deprecated

    Examples:
        >>> profile = get_profile("standard")
        >>> profile = get_profile("accurate")
        >>> profile = get_profile("precise")
    """
    # Check if using deprecated profile name - auto-migrate with warning
    if name in DEPRECATED_PROFILES:
        info = DEPRECATED_PROFILES[name]
        replacement = info["replacement"]
        warning_msg = (
            f"\n{'='*70}\n"
            f"⚠️  DEPRECATED PROFILE: '{name}' → auto-migrated to '{replacement}'\n"
            f"{'='*70}\n"
            f"Reason: {info['reason']}\n"
        )
        if "note" in info:
            warning_msg += f"Note: {info['note']}\n"

        warning_msg += (
            f"\nPlease update your config to silence this warning:\n"
            f'  "numerics": {{\n'
            f'    "profile": "{replacement}"  // ← Change from "{name}"\n'
            f"  }}\n"
            f"{'='*70}\n"
        )
        logger.warning(warning_msg)
        # Auto-migrate to replacement profile
        name = replacement

    # Check if profile exists
    if name not in NUMERICS_PROFILES:
        available = ", ".join(NUMERICS_PROFILES.keys())
        raise ValueError(f"Unknown numeric profile '{name}'. " f"Available profiles: {available}")

    return NUMERICS_PROFILES[name]


def list_profiles() -> Dict[str, Dict[str, Any]]:
    """
    List available numeric profiles with descriptions.

    Returns:
        Dictionary mapping profile names to metadata

    Example:
        >>> profiles = list_profiles()
        >>> for name, info in profiles.items():
        ...     print(f"{name}: {info['use']}")
    """
    return {
        name: {
            "order": PROFILE_METADATA[name]["order_of_accuracy"],
            "stability": PROFILE_METADATA[name]["stability"],
            "use": PROFILE_METADATA[name]["intended_use"],
            "physics": PROFILE_METADATA[name]["physics_models"],
            "best_for": PROFILE_METADATA[name]["best_for"],
        }
        for name in NUMERICS_PROFILES.keys()
    }


def recommend_profile(mesh_quality: dict, physics_model: str = "rans", objective: str = "production") -> str:
    """
    Recommend numeric profile based on mesh quality, physics model, and objective.

    Args:
        mesh_quality: Dict with keys 'orthogonality', 'skewness'
        physics_model: One of 'laminar', 'rans', 'les'
        objective: One of 'debug', 'production', 'validation', 'convergence'

    Returns:
        Recommended profile name

    Example:
        >>> recommend_profile({'orthogonality': 65, 'skewness': 2.5}, 'rans', 'production')
        'standard'
        >>> recommend_profile({'orthogonality': 75, 'skewness': 1.5}, 'les', 'production')
        'precise'
    """
    ortho = mesh_quality.get("orthogonality", 0)
    skew = mesh_quality.get("skewness", 10)

    # Debug mode: always use robust
    if objective == "debug":
        return "robust"

    # Poor mesh quality: use robust
    if ortho < 50 or skew > 4:
        logger.warning(
            f"Mesh quality poor (ortho={ortho}°, skew={skew:.1f}). "
            f"Recommending 'robust' profile. Consider improving mesh."
        )
        return "robust"

    # LES: always use precise (LUST required)
    if physics_model.lower() == "les":
        if ortho < 70 or skew > 2:
            logger.warning(
                f"LES requires excellent mesh (ortho>70°, skew<2). "
                f"Current: ortho={ortho}°, skew={skew:.1f}. "
                f"Recommending 'precise' but mesh improvement strongly advised."
            )
        return "precise"

    # Convergence study / low diffusion needed
    if objective in ("convergence", "validation"):
        if ortho > 70 and skew < 2:
            logger.info(
                "Recommending 'precise' profile (minimal numerical diffusion). "
                "REMINDER: Profile choice does not guarantee solution accuracy - "
                "mesh independence study required."
            )
            return "precise"
        else:
            logger.warning(
                f"Low-diffusion 'precise' profile requires good mesh (ortho>70°, skew<2). "
                f"Current: ortho={ortho}°, skew={skew:.1f}. "
                f"Recommending 'standard' - improve mesh before using 'precise'."
            )
            return "standard"

    # Production (laminar or RANS): use standard
    return "standard"


__all__ = [
    "NUMERICS_PROFILES",
    "PROFILE_METADATA",
    "DEPRECATED_PROFILES",
    "get_profile",
    "list_profiles",
    "recommend_profile",
    "robust_config",
    "standard_config",
    "precise_config",
]
