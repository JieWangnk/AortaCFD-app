"""Numeric profiles for OpenFOAM discretization schemes and solver settings.

SIMPLIFIED 3-PROFILE SYSTEM
============================
This module provides 3 universal profiles that work for ALL physics models
(laminar, RANS k-ω SST, LES WALE).

AVAILABLE PROFILES
==================

robust
------
First-order schemes, maximum stability.
USE FOR: Debugging, poor mesh quality, initial testing, coarse mesh convergence
SCHEMES: Euler time, upwind convection
TRADE-OFF: Stable but diffusive (not publication quality)
COST: Low (1x baseline)
PHYSICS: Laminar, RANS, LES (not recommended for final LES results)

standard
--------
Second-order bounded schemes, production quality.
USE FOR: Production runs, clinical studies, most RANS simulations
SCHEMES: backward time, linearUpwind convection
TRADE-OFF: Good accuracy and stability balance
COST: Moderate (1.5x baseline)
PHYSICS: Laminar, RANS (recommended), LES (acceptable but "accurate" is better)

accurate
--------
Second-order low-diffusion schemes, publication quality.
USE FOR: Publications, mesh independence studies, ALL LES simulations
SCHEMES: CrankNicolson 0.9 time, LUST convection (75% central + 25% upwind)
TRADE-OFF: Minimal diffusion, requires good mesh, longer runtime
COST: Higher (2-3x baseline)
PHYSICS: Laminar, RANS, LES (REQUIRED for LES - LUST preserves turbulence)

PROFILE SELECTION GUIDE
=======================

┌─────────────────────────────────────────────────────────────────────┐
│ START: What is your objective?                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   Debug/Test?         Production?          Publication?
   Poor mesh?          Clinical?                 LES?
        │                     │                     │
        ▼                     ▼                     ▼
     ROBUST              STANDARD               ACCURATE
        │                     │                     │
   1st order           2nd order bounded     2nd order LUST
   Max stability       Good balance          Min diffusion

PHYSICS-SPECIFIC RECOMMENDATIONS
=================================

Laminar:
  - Debug:       robust
  - Production:  standard
  - Publication: accurate

RANS (k-ω SST):
  - Debug:       robust
  - Production:  standard (recommended)
  - Publication: accurate

LES (WALE):
  - Debug:       standard (quick test only)
  - Production:  accurate (REQUIRED - LUST preserves turbulence)
  - Publication: accurate (same)

MESH QUALITY REQUIREMENTS
==========================

Profile    Orthogonality  Skewness  y+ (RANS)    y+ (LES)
---------  -------------  --------  -----------  ---------
robust     > 50°          < 4       Any          Any
standard   > 60°          < 3       1-10         < 1
accurate   > 70°          < 2       1-10         < 1 (required)

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
- publication (use "accurate" instead)
- precise (use "accurate" instead)
- aggressive (use "accurate" instead, or manually set unbounded schemes if needed)

If you encounter errors about missing profiles, update your config to use
one of the 3 current profiles: robust, standard, accurate.

MIGRATION GUIDE
===============
Old Profile      → New Profile   Reason
-------------    -------------   ------
conservative     → robust        Same schemes (Euler + upwind)
publication      → accurate      Similar accuracy, LUST better for all models
precise          → accurate      Consolidated high-accuracy profiles
aggressive       → accurate      LUST provides stability with low diffusion

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
from .accurate import config as accurate_config

# Get logger
logger = logging.getLogger(__name__)

# Profile registry - ONLY 3 PROFILES
NUMERICS_PROFILES = {
    "robust": robust_config,       # 1st order, maximum stability
    "standard": standard_config,   # 2nd order bounded (backward + linearUpwind)
    "accurate": accurate_config,   # 2nd order low-diffusion (CN 0.9 + LUST)
}

# Deprecated profile mapping for helpful error messages
DEPRECATED_PROFILES = {
    "conservative": {
        "replacement": "robust",
        "reason": "Identical schemes (Euler + upwind), simplified naming"
    },
    "publication": {
        "replacement": "accurate",
        "reason": "Similar accuracy. LUST scheme in 'accurate' is better for all models."
    },
    "precise": {
        "replacement": "accurate",
        "reason": "Consolidated high-accuracy profiles. Use 'accurate' for all publication work."
    },
    "aggressive": {
        "replacement": "accurate",
        "reason": "Pure central differencing is unstable. LUST provides comparable accuracy with stability.",
        "note": "If you need unbounded schemes for DNS, manually override divSchemes in your config."
    }
}

# Profile metadata for quick reference
PROFILE_METADATA = {
    "robust": {
        "order_of_accuracy": 1,
        "stability": "maximum",
        "intended_use": "debugging, poor meshes, initial testing",
        "physics_models": ["laminar", "rans", "les"],
        "best_for": "debug and coarse mesh convergence studies",
        "not_recommended_for": "final results, publications (high numerical diffusion)"
    },
    "standard": {
        "order_of_accuracy": 2,
        "stability": "good",
        "intended_use": "production runs, clinical studies, most RANS",
        "physics_models": ["laminar", "rans", "les"],
        "best_for": "RANS production simulations",
        "mesh_requirements": "orthogonality > 60°, skewness < 3"
    },
    "accurate": {
        "order_of_accuracy": 2,
        "stability": "good (requires quality mesh)",
        "intended_use": "publications, validation, mesh independence, ALL LES",
        "physics_models": ["laminar", "rans", "les"],
        "best_for": "LES (LUST preserves turbulence), publications, validation studies",
        "mesh_requirements": "orthogonality > 70°, skewness < 2, y+ < 1 for LES"
    }
}


def get_profile(name: str) -> Dict[str, Any]:
    """
    Get numeric profile configuration by name.

    Args:
        name: Profile name (robust, standard, accurate)

    Returns:
        Profile configuration dictionary

    Raises:
        ValueError: If profile name is unknown or deprecated

    Examples:
        >>> profile = get_profile("standard")
        >>> profile = get_profile("accurate")
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
        objective: One of 'debug', 'production', 'publication'

    Returns:
        Recommended profile name

    Example:
        >>> recommend_profile({'orthogonality': 65, 'skewness': 2.5}, 'rans', 'production')
        'standard'
        >>> recommend_profile({'orthogonality': 75, 'skewness': 1.5}, 'les', 'production')
        'accurate'
    """
    ortho = mesh_quality.get("orthogonality", 0)
    skew = mesh_quality.get("skewness", 10)

    # Debug mode: always use robust
    if objective == "debug":
        return "robust"

    # Poor mesh quality: use robust
    if ortho < 60 or skew > 3:
        logger.warning(
            f"Mesh quality marginal (ortho={ortho}°, skew={skew:.1f}). "
            f"Recommending 'robust' profile. Consider improving mesh."
        )
        return "robust"

    # LES: always use accurate (LUST required)
    if physics_model.lower() == "les":
        if ortho < 70 or skew > 2:
            logger.warning(
                f"LES requires excellent mesh (ortho>70°, skew<2). "
                f"Current: ortho={ortho}°, skew={skew:.1f}. "
                f"Recommending 'accurate' but mesh improvement strongly advised."
            )
        return "accurate"

    # Publication: use accurate
    if objective == "publication":
        if ortho > 70 and skew < 2:
            return "accurate"
        else:
            logger.warning(
                f"Publication-quality requires good mesh (ortho>70°, skew<2). "
                f"Current: ortho={ortho}°, skew={skew:.1f}. "
                f"Recommending 'standard' but consider improving mesh for 'accurate'."
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
]
