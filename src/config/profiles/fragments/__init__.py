"""Fragment registry package.

This namespace groups all reusable profile fragments (orthogonal axes
like spatial resolution, solver recipe, and turbulence model) under a
single module path:

    from config.profiles.fragments import (
        RESOLUTION_FRAGMENTS,
        SOLVER_RECIPE_FRAGMENTS,
        TURBULENCE_FRAGMENTS
    )

Legacy direct imports from ``config.profiles.resolution_fragments`` and
``config.profiles.solver_recipe_fragments`` are still temporarily
supported via lightweight shim modules left at the old locations. New
code should import from ``config.profiles.fragments``.
"""

from .resolution import RESOLUTION_FRAGMENTS, FRAGMENT_META_KEY as _RES_META_KEY  # noqa: F401
from .solver_recipe import SOLVER_RECIPE_FRAGMENTS  # noqa: F401
from .turbulence import TURBULENCE_FRAGMENTS  # noqa: F401

__all__ = [
    "RESOLUTION_FRAGMENTS",
    "SOLVER_RECIPE_FRAGMENTS",
    "TURBULENCE_FRAGMENTS",
]
