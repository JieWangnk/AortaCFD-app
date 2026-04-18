# src/aortacfd_lib/utils/patch_utils.py
"""
Utility functions for patch operations to avoid code duplication.
"""
import os
import re


def detect_world_patch_mode(case_dir, log):
    """
    Detect if the case is using world patch mode by checking mesh files.
    
    Args:
        case_dir: Path to the case directory
        log: Logger instance for logging messages
        
    Returns:
        bool: True if world patch mode is detected, False otherwise
    """
    boundary_file = os.path.join(case_dir, "constant", "polyMesh", "boundary")
    
    if not os.path.exists(boundary_file):
        log.warning(f"Boundary file not found at {boundary_file}")
        return False
    
    try:
        with open(boundary_file, 'r') as f:
            content = f.read()
            
        # Check if only one patch exists (excluding defaultFaces)
        patches = re.findall(r'^\s*(\w+)\s*{', content, re.MULTILINE)
        non_default_patches = [p for p in patches if p not in ('defaultFaces', 'FoamFile')]

        if len(non_default_patches) == 1:
            log.info(f"Single patch mode detected: {non_default_patches[0]}")
            return True

        # Only trigger world-patch mode when 'world' is the sole
        # user-facing patch (i.e. blockMesh without snappyHexMesh).
        # After snappy, a residual 'world' patch may remain alongside
        # proper inlet/outlet/wall patches — that is NOT world-patch mode.
        has_world = re.search(r'\bworld\b\s*\{', content) is not None
        has_inlet = re.search(r'\binlet\b\s*\{', content) is not None
        if has_world and not has_inlet:
            log.info("World patch mode detected in boundary file")
            return True
        if has_world and has_inlet:
            log.info("Residual 'world' patch present alongside named patches — not world-patch mode")
            
    except Exception as e:
        log.warning(f"Error checking boundary file: {e}")
    
    return False


def get_murray_law_cache_key():
    """Get a consistent cache key for Murray's law results."""
    return 'murray_law_results'