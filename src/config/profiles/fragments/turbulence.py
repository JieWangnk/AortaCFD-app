"""Turbulence model fragment definitions.

These fragments encapsulate turbulence modeling strategies (laminar, RANS, LES)
as reusable configuration blocks that can be composed with spatial resolution
and solver recipe fragments.

PHYSICAL UNITS CONVENTION (SI):
    - nu (kinematic viscosity): m²/s  [e.g., 3.77e-6 m²/s for blood]
    - rho (density): kg/m³            [e.g., 1060 kg/m³ for blood]
    - turbulence_intensity: dimensionless fraction [0.05 = 5%]
    - turbulence_viscosity_ratio: dimensionless [ν_t/ν, typically 1-100]
    - y_plus: dimensionless wall distance [y⁺ = yuτ/ν]

BLOOD PROPERTIES (37°C):
    - Density: 1060 kg/m³ (typical range: 1025-1065 kg/m³)
    - Dynamic viscosity: 0.004 Pa·s = 4 mPa·s (range: 3-5 mPa·s)
    - Kinematic viscosity: μ/ρ = 3.77×10⁻⁶ m²/s
    - Newtonian assumption valid for: shear rate > 100 s⁻¹ (large vessels)

TURBULENCE INTENSITY GUIDELINES (arterial flows):
    - Healthy aorta (laminar-transitional): I = 1-3%
    - Aortic valve jets: I = 5-10%
    - Post-stenotic region: I = 8-15%
    - Coarctation/aneurysm: I = 10-20%
"""

from __future__ import annotations

from typing import Any, Dict

FRAGMENT_META_KEY = "__profile_fragment__"

# Laminar flow (no turbulence model)
TURBULENCE_LAMINAR: Dict[str, Any] = {
    "physics": {
        "simulation_type": "laminar",
        "simulation_performance": "balanced",
        "steady_state": False,
    },
    FRAGMENT_META_KEY: {
        "axis": "turbulence_model",
        "level": "laminar",
        "targets": {
            "model_type": "laminar",
            "re_max": 2300,
            "notes": "Direct numerical simulation of laminar flow, no turbulence closure.",
        },
    },
}

# RANS: k-omega SST turbulence model
TURBULENCE_RANS_KOMEGA_SST: Dict[str, Any] = {
    "physics": {
        "simulation_type": "RAS",
        "turbulence_model": "kOmegaSST",
        "turbulence_intensity": 0.05,  # 5% - typical for large arteries
        "turbulence_viscosity_ratio": 10.0,  # Conservative for inlet conditions
        "nu": 3.77e-06,  # Kinematic viscosity of blood
        "rho": 1060,  # Blood density
    },
    FRAGMENT_META_KEY: {
        "axis": "turbulence_model",
        "level": "rans_komega_sst",
        "targets": {
            "model_type": "RANS",
            "closure": "k-omega SST",
            "y_plus_target": "1-300 (wall functions)",
            "notes": "Industry-standard RANS model for arterial flows with adverse pressure gradients.",
        },
    },
}

# RANS: k-omega SST with higher turbulence intensity (for more turbulent flows)
TURBULENCE_RANS_HIGH_INTENSITY: Dict[str, Any] = {
    "physics": {
        "simulation_type": "RAS",
        "turbulence_model": "kOmegaSST",
        "turbulence_intensity": 0.08,  # 8% - higher turbulence
        "turbulence_viscosity_ratio": 12.0,
        "nu": 3.77e-06,
        "rho": 1060,
    },
    FRAGMENT_META_KEY: {
        "axis": "turbulence_model",
        "level": "rans_high_intensity",
        "targets": {
            "model_type": "RANS",
            "closure": "k-omega SST",
            "turbulence_intensity": "8%",
            "notes": "Higher turbulence intensity for more aggressive flows or post-stenotic regions.",
        },
    },
}

# LES: WALE subgrid-scale model
TURBULENCE_LES_WALE: Dict[str, Any] = {
    "physics": {
        "simulation_type": "LES",
        "simulation_performance": "high",
        "steady_state": False,
        "filter_width": "cubeRootVol",  # Standard for unstructured meshes
        "subgrid_model": "WALE",  # Wall-Adapting Local Eddy-viscosity
    },
    FRAGMENT_META_KEY: {
        "axis": "turbulence_model",
        "level": "les_wale",
        "targets": {
            "model_type": "LES",
            "subgrid_model": "WALE",
            "y_plus_target": "<1 (resolved)",
            "filter": "cubeRootVol",
            "notes": "WALE model handles near-wall behavior better than Smagorinsky for complex geometries.",
        },
    },
}

# LES: Smagorinsky subgrid-scale model (alternative to WALE)
TURBULENCE_LES_SMAGORINSKY: Dict[str, Any] = {
    "physics": {
        "simulation_type": "LES",
        "simulation_performance": "high",
        "steady_state": False,
        "filter_width": "cubeRootVol",
        "subgrid_model": "Smagorinsky",
        "smagorinsky_constant": 0.18,  # Typical value
    },
    FRAGMENT_META_KEY: {
        "axis": "turbulence_model",
        "level": "les_smagorinsky",
        "targets": {
            "model_type": "LES",
            "subgrid_model": "Smagorinsky",
            "y_plus_target": "<1 (resolved)",
            "notes": "Classic Smagorinsky model, simpler but less accurate near walls than WALE.",
        },
    },
}

# Collection of all turbulence fragments
TURBULENCE_FRAGMENTS: Dict[str, Dict[str, Any]] = {
    "laminar": TURBULENCE_LAMINAR,
    "rans_komega_sst": TURBULENCE_RANS_KOMEGA_SST,
    "rans_high_intensity": TURBULENCE_RANS_HIGH_INTENSITY,
    "les_wale": TURBULENCE_LES_WALE,
    "les_smagorinsky": TURBULENCE_LES_SMAGORINSKY,
}

__all__ = [
    "FRAGMENT_META_KEY",
    "TURBULENCE_FRAGMENTS",
    "TURBULENCE_LAMINAR",
    "TURBULENCE_RANS_KOMEGA_SST",
    "TURBULENCE_RANS_HIGH_INTENSITY",
    "TURBULENCE_LES_WALE",
    "TURBULENCE_LES_SMAGORINSKY",
]
