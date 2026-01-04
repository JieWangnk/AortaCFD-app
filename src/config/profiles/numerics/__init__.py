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

4-PROFILE SYSTEM
================
This module provides 4 universal profiles that work for ALL physics models
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

accurate
--------
Second-order with low numerical diffusion.
USE FOR: Convergence studies, validation, cases requiring low diffusion
SCHEMES: backward time, linearUpwind convection, corrected Laplacian
TRADE-OFF: Low diffusion but requires good mesh quality
COST: Moderate (1.5x baseline)
MESH: ortho > 65°, skewness < 3

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
     ┌──────────────┬───────────────┼───────────────┬──────────────┐
     │              │               │               │              │
     ▼              ▼               ▼               ▼              ▼
 Max stability?  Production?   Low diffusion?   Minimal diff?    LES?
 Poor mesh?      Windkessel?   Good mesh?       Excellent mesh?
     │              │               │               │              │
     ▼              ▼               ▼               ▼              ▼
   ROBUST        STANDARD       ACCURATE        PRECISE        PRECISE
 1st order     2nd TVD bound  2nd linearUpwind  2nd LUST      2nd LUST
 Max stable    High stable    Low diffusion    Min diffusion  Min diffusion

IMPORTANT: None of these guarantee accuracy - that requires mesh convergence.

PHYSICS-SPECIFIC RECOMMENDATIONS
=================================

Laminar:
  - Debug:            robust
  - Production:       standard
  - Convergence study: accurate or precise

RANS (k-ω SST):
  - Debug:            robust
  - Production:       standard (recommended)
  - Convergence study: accurate
  - Final validation:  precise (if mesh quality permits)

LES (WALE):
  - Debug:            standard (quick test only)
  - Production/Final: precise (REQUIRED - LUST preserves turbulence)

MESH QUALITY REQUIREMENTS
==========================

Profile    Orthogonality  Skewness  y+ (RANS)    y+ (LES)
---------  -------------  --------  -----------  ---------
robust     > 50°          < 4       Any          Any
standard   > 50°          < 4       1-10         < 1
accurate   > 65°          < 3       1-10         < 1
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
    "profile": "accurate",
    "max_co": 0.8
  }
}
```

DEPRECATED PROFILES
===================
The following profiles have been removed for simplicity:
- conservative (use "robust" instead)
- publication (use "precise" instead)
- aggressive (use "precise" instead, or manually set unbounded schemes if needed)

If you encounter errors about missing profiles, update your config to use
one of the 4 current profiles: robust, standard, accurate, precise.

MIGRATION GUIDE
===============
Old Profile      → New Profile   Reason
-------------    -------------   ------
conservative     → robust        Same schemes (Euler + upwind)
publication      → precise       Similar accuracy, LUST for minimal diffusion
aggressive       → precise       LUST provides stability with low diffusion

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

# Import the 4 core profiles
from .robust import config as robust_config
from .standard import config as standard_config
from .accurate import config as accurate_config
from .precise import config as precise_config

# Get logger
logger = logging.getLogger(__name__)

# Profile registry - 4 PROFILES
NUMERICS_PROFILES = {
    "robust": robust_config,       # 1st order, maximum stability
    "standard": standard_config,   # 2nd order TVD bounded (backward + limitedLinearV)
    "accurate": accurate_config,   # 2nd order low-diffusion (backward + linearUpwind)
    "precise": precise_config,     # 2nd order minimal diffusion (CN 0.9 + LUST)
}

# Deprecated profile mapping for helpful error messages
DEPRECATED_PROFILES = {
    "conservative": {
        "replacement": "robust",
        "reason": "Identical schemes (Euler + upwind), simplified naming"
    },
    "publication": {
        "replacement": "precise",
        "reason": "Misleading name removed. LUST scheme in 'precise' has minimal diffusion. Note: profile choice alone does not make results publication-ready - convergence study required."
    },
    "aggressive": {
        "replacement": "precise",
        "reason": "Pure central differencing is unstable. LUST provides comparable accuracy with stability.",
        "note": "If you need unbounded schemes for DNS, manually override divSchemes in your config."
    }
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
        "mesh_requirements": "orthogonality > 50°, skewness < 4"
    },
    "standard": {
        "order_of_accuracy": 2,
        "stability": "high",
        "numerical_diffusion": "moderate (TVD bounded)",
        "intended_use": "production runs, clinical studies, Windkessel outlets",
        "physics_models": ["laminar", "rans", "les"],
        "best_for": "stable production simulations with 2nd order accuracy",
        "mesh_requirements": "orthogonality > 50°, skewness < 4"
    },
    "accurate": {
        "order_of_accuracy": 2,
        "stability": "good",
        "numerical_diffusion": "low (linearUpwind)",
        "intended_use": "convergence studies, validation, good meshes",
        "physics_models": ["laminar", "rans", "les"],
        "best_for": "mesh independence studies, validation cases",
        "mesh_requirements": "orthogonality > 65°, skewness < 3"
    },
    "precise": {
        "order_of_accuracy": 2,
        "stability": "good (requires excellent mesh)",
        "numerical_diffusion": "minimal (LUST preserves gradients)",
        "intended_use": "LES, final validation, minimal diffusion required",
        "physics_models": ["laminar", "rans", "les"],
        "best_for": "LES (LUST preserves turbulence), minimal diffusion cases",
        "mesh_requirements": "orthogonality > 70°, skewness < 2, y+ < 1 for LES",
        "note": "LUST is REQUIRED for LES to preserve resolved turbulence"
    }
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
    # Check if using deprecated profile name
    if name in DEPRECATED_PROFILES:
        info = DEPRECATED_PROFILES[name]
        error_msg = (
            f"\n{'='*70}\n"
            f"❌ PROFILE '{name}' HAS BEEN REMOVED\n"
            f"{'='*70}\n"
            f"→ Use '{info['replacement']}' instead.\n\n"
            f"Reason: {info['reason']}\n"
        )
        if "note" in info:
            error_msg += f"\nNote: {info['note']}\n"

        error_msg += (
            f"\nUpdate your config:\n"
            f'  "numerics": {{\n'
            f'    "profile": "{info["replacement"]}"  // ← Change from "{name}"\n'
            f'  }}\n'
            f"\nAvailable profiles: {', '.join(NUMERICS_PROFILES.keys())}\n"
            f"{'='*70}\n"
        )
        logger.error(error_msg)
        raise ValueError(f"Profile '{name}' has been deprecated. Use '{info['replacement']}' instead.")

    # Check if profile exists
    if name not in NUMERICS_PROFILES:
        available = ", ".join(NUMERICS_PROFILES.keys())
        raise ValueError(
            f"Unknown numeric profile '{name}'. "
            f"Available profiles: {available}"
        )

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
            "best_for": PROFILE_METADATA[name]["best_for"]
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
                f"Recommending 'precise' profile (minimal numerical diffusion). "
                f"REMINDER: Profile choice does not guarantee solution accuracy - "
                f"mesh independence study required."
            )
            return "precise"
        elif ortho > 65 and skew < 3:
            logger.info(
                f"Recommending 'accurate' profile (low numerical diffusion). "
                f"For minimal diffusion, improve mesh to ortho>70°, skew<2."
            )
            return "accurate"
        else:
            logger.warning(
                f"Low-diffusion schemes require good mesh (ortho>65°, skew<3). "
                f"Current: ortho={ortho}°, skew={skew:.1f}. "
                f"Recommending 'standard' - improve mesh before using 'accurate'."
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
    "accurate_config",
    "precise_config",
]
