"""
Mesh resolution constants and presets for AortaCFD.

Centralized location for mesh resolution presets to avoid duplication
across mesh_setup.py and helper scripts.
"""

# Resolution level presets (cell size in mm)
RESOLUTION_PRESETS = {
    # Primary presets
    'coarse': 2.0,      # Draft quality: ~100K-300K cells, 5-15 min runtime
    'medium': 1.0,      # Clinical quality: ~500K-1.5M cells, 30-90 min runtime
    'fine': 0.5,        # Publication quality: ~2M-5M cells, 2-4 hours runtime
    'ultra_fine': 0.25, # Mesh independence: ~10M+ cells, 6-12 hours runtime

    # Aliases for intuitive naming
    'draft': 2.0,       # Alias for 'coarse'
    'clinical': 1.0,    # Alias for 'medium'
    'publication': 0.5, # Alias for 'fine'
}

# Default fallback cell size (matches 'medium' profile)
DEFAULT_CELL_SIZE_MM = 1.0

# Profile metadata for enhanced logging
RESOLUTION_PROFILES = {
    'coarse': {
        'cell_size_mm': 2.0,
        'expected_cells': '~100K-300K cells',
        'runtime': '5-15 min runtime',
        'aliases': ['draft']
    },
    'medium': {
        'cell_size_mm': 1.0,
        'expected_cells': '~500K-1.5M cells',
        'runtime': '30-90 min runtime',
        'aliases': ['clinical']
    },
    'fine': {
        'cell_size_mm': 0.5,
        'expected_cells': '~2M-5M cells',
        'runtime': '2-4 hours runtime',
        'aliases': ['publication']
    },
    'ultra_fine': {
        'cell_size_mm': 0.25,
        'expected_cells': '~10M+ cells',
        'runtime': '6-12 hours runtime',
        'aliases': []
    },
}

def get_cell_size_from_preset(level: str) -> float:
    """
    Get cell size (mm) from resolution level preset.

    Args:
        level: Resolution level string (coarse/medium/fine/ultra_fine or aliases)

    Returns:
        Cell size in millimeters, or None if invalid preset

    Examples:
        >>> get_cell_size_from_preset('medium')
        1.0
        >>> get_cell_size_from_preset('clinical')
        1.0
        >>> get_cell_size_from_preset('invalid')
        None
    """
    if level is None:
        return None
    return RESOLUTION_PRESETS.get(str(level).lower())


def get_profile_info(level: str) -> dict:
    """
    Get complete profile information for a resolution level.

    Args:
        level: Resolution level string

    Returns:
        Dictionary with cell_size_mm, expected_cells, runtime, aliases
        or None if invalid preset

    Examples:
        >>> info = get_profile_info('medium')
        >>> info['expected_cells']
        '~500K-1.5M cells'
    """
    if level is None:
        return None

    # Normalize aliases to primary names
    level_lower = str(level).lower()

    # Check if it's a primary name
    if level_lower in RESOLUTION_PROFILES:
        return RESOLUTION_PROFILES[level_lower]

    # Check if it's an alias
    for primary, profile in RESOLUTION_PROFILES.items():
        if level_lower in profile.get('aliases', []):
            return RESOLUTION_PROFILES[primary]

    return None


def get_available_presets() -> list:
    """
    Get list of all available preset names (including aliases).

    Returns:
        Sorted list of preset names

    Examples:
        >>> presets = get_available_presets()
        >>> 'medium' in presets
        True
        >>> 'clinical' in presets
        True
    """
    return sorted(RESOLUTION_PRESETS.keys())
