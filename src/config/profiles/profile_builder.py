"""Composable profile builder that merges axis fragments.

This module provides a helper for constructing simulation profile
configurations by combining reusable fragments along orthogonal axes such
as spatial resolution and solver recipes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from ..builder import deep_merge
from .fragments import RESOLUTION_FRAGMENTS, SOLVER_RECIPE_FRAGMENTS, TURBULENCE_FRAGMENTS

FRAGMENT_META_KEY = "__profile_fragment__"


class ProfileComposer:
    """Compose simulation profiles from reusable fragments."""

    def __init__(self) -> None:
        self._axes: Dict[str, Dict[str, Dict[str, Any]]] = {
            "spatial_resolution": RESOLUTION_FRAGMENTS,
            "solver_recipe": SOLVER_RECIPE_FRAGMENTS,
            "turbulence_model": TURBULENCE_FRAGMENTS,
        }

    def available_axes(self) -> Iterable[str]:
        """Return the names of registered axes."""
        return self._axes.keys()

    def levels_for(self, axis: str) -> List[str]:
        """Return the available levels for the requested axis."""
        if axis not in self._axes:
            raise KeyError(f"Unknown axis '{axis}'. Registered axes: {sorted(self._axes)}")
        return sorted(self._axes[axis].keys())

    def compose(
        self,
        *,
    spatial_resolution: Optional[str] = None,
    solver_recipe: Optional[str] = None,
    turbulence_model: Optional[str] = None,
    extras: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compose a profile from the specified axis levels.

        Args:
            spatial_resolution: Selected spatial resolution fragment level.
            solver_recipe: Selected solver recipe fragment level.
            turbulence_model: Selected turbulence model fragment level.
            extras: Optional dictionary merged last to supply overrides.

        Returns:
            A deep-merged configuration dictionary with fragment metadata attached.
        """
        selections = {
            "spatial_resolution": spatial_resolution,
            "solver_recipe": solver_recipe,
            "turbulence_model": turbulence_model,
        }

        composed: Dict[str, Any] = {}
        fragment_meta: List[Dict[str, Any]] = []

        for axis, level in selections.items():
            if not level:
                continue
            if axis not in self._axes:
                raise KeyError(f"Axis '{axis}' is not registered.")
            fragments = self._axes[axis]
            if level not in fragments:
                raise KeyError(
                    f"Level '{level}' not available for axis '{axis}'. "
                    f"Valid levels: {sorted(fragments.keys())}"
                )

            fragment = deepcopy(fragments[level])
            meta = fragment.pop(FRAGMENT_META_KEY, None)
            deep_merge(composed, fragment)
            if meta:
                fragment_meta.append(meta)

        if extras:
            deep_merge(composed, deepcopy(extras))

        if fragment_meta:
            composed.setdefault("profile_fragments", []).extend(fragment_meta)

        return composed


__all__ = [
    "ProfileComposer",
]
