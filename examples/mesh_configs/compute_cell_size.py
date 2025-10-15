#!/usr/bin/env python3
"""
Mesh Cell Size Calculator - AortaCFD

Helper script to compute the effective cell size that will be used
given a configuration file. Helps users understand the parameter hierarchy
without running the full simulation.

Usage:
    python compute_cell_size.py ../../cases_input/patient1/config.json
    python compute_cell_size.py mesh_medium.json --reference-radius 12.5
"""

import json
import sys
from pathlib import Path
from typing import Optional, Tuple

# Add src to path to import mesh constants
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from aortacfd_lib.utils.mesh_constants import (
    get_cell_size_from_preset,
    get_available_presets,
    DEFAULT_CELL_SIZE_MM
)


class CellSizeCalculator:
    """Calculate cell size from configuration following AortaCFD hierarchy."""

    def __init__(self, config: dict, reference_radius_mm: Optional[float] = None):
        """
        Initialize calculator.

        Args:
            config: Full configuration dictionary
            reference_radius_mm: Override reference radius (mm) for testing
        """
        self.config = config
        self.override_radius = reference_radius_mm

    def _coerce_positive(self, value, label: str) -> Optional[float]:
        """Validate positive numeric value."""
        if value is None:
            return None
        if isinstance(value, bool):
            print(f"⚠️  Warning: Ignoring boolean {label}: {value}")
            return None
        try:
            coerced = float(value)
        except (TypeError, ValueError):
            print(f"⚠️  Warning: Ignoring non-numeric {label}: {value}")
            return None
        if coerced <= 0:
            print(f"⚠️  Warning: Ignoring non-positive {label}: {value}")
            return None
        return coerced

    def get_reference_radius(self) -> Optional[float]:
        """Get reference radius from override or config."""
        if self.override_radius is not None:
            print(f"ℹ️  Using override reference radius: {self.override_radius:.2f} mm")
            return self.override_radius

        # Try to get from geometry settings (if pre-computed)
        geom = self.config.get('geometry', {})
        ref_radius = geom.get('reference_radius_mm')
        if ref_radius:
            strategy = geom.get('reference_radius_strategy', 'min')
            print(f"ℹ️  Reference radius from config: {ref_radius:.2f} mm (strategy: {strategy})")
            return float(ref_radius)

        print("⚠️  No reference radius available")
        print("   To compute cell size from blockmesh_resolution or cells_per_diameter,")
        print("   provide --reference-radius or run geometry analysis first")
        return None

    def method_1_resolution_level(self) -> Tuple[Optional[float], str]:
        """Priority 1: resolution_level preset."""
        mesh = self.config.get('mesh', {})
        mesh_res = mesh.get('mesh_resolution', {})

        # Check both locations
        level = mesh.get('resolution_level') or mesh_res.get('resolution_level')
        if level is None:
            return None, ""

        # Use centralized preset mapping
        cell_size = get_cell_size_from_preset(level)
        if cell_size is not None:
            return cell_size, f"mesh.resolution_level='{level}' → {cell_size}mm"

        # Unknown level
        available = ', '.join(get_available_presets())
        print(f"⚠️  Unknown resolution_level: '{level}'")
        print(f"   Available: {available}")
        return None, ""

    def method_2_target_mm(self) -> Tuple[Optional[float], str]:
        """Priority 2: target_cell_size_mm."""
        mesh_res = self.config.get('mesh', {}).get('mesh_resolution', {})
        target_mm = mesh_res.get('target_cell_size_mm')
        validated = self._coerce_positive(target_mm, "mesh.mesh_resolution.target_cell_size_mm")

        if validated is not None:
            return validated, "mesh.mesh_resolution.target_cell_size_mm (explicit)"
        return None, ""

    def method_3_blockmesh_resolution(self) -> Tuple[Optional[float], str]:
        """Priority 3: blockmesh_resolution."""
        mesh = self.config.get('mesh', {})
        mesh_res = mesh.get('mesh_resolution', {})

        # Try multiple naming conventions
        block_res = mesh_res.get('blockmesh_resolution')
        if block_res is None:
            block_res = mesh_res.get('blockMesh_resolution')
        if block_res is None:
            block_res = mesh.get('BLOCKMESH_SETTINGS', {}).get('resolution')

        block_res_val = self._coerce_positive(block_res, "blockmesh_resolution")

        if block_res_val is not None:
            ref_radius = self.get_reference_radius()
            if ref_radius and ref_radius > 0:
                cell_size = (2.0 * ref_radius) / block_res_val
                return cell_size, f"2*R/{block_res_val:.1f} = 2*{ref_radius:.2f}/{block_res_val:.1f}"
            else:
                print("⚠️  blockmesh_resolution requires reference_radius")
        return None, ""

    def method_4_cells_per_diameter(self) -> Tuple[Optional[float], str]:
        """Priority 4: cells_per_diameter."""
        mesh_res = self.config.get('mesh', {}).get('mesh_resolution', {})
        cells_per_diam = mesh_res.get('cells_per_diameter')
        cells_val = None

        if isinstance(cells_per_diam, dict):
            for key in ('branch', 'inlet'):
                cells_val = self._coerce_positive(
                    cells_per_diam.get(key),
                    f"cells_per_diameter.{key}"
                )
                if cells_val is not None:
                    break
        else:
            cells_val = self._coerce_positive(cells_per_diam, "cells_per_diameter")

        if cells_val is not None:
            ref_radius = self.get_reference_radius()
            if ref_radius and ref_radius > 0:
                cell_size = (2.0 * ref_radius) / cells_val
                return cell_size, f"2*R/{cells_val:.1f} = 2*{ref_radius:.2f}/{cells_val:.1f}"
            else:
                print("⚠️  cells_per_diameter requires reference_radius")
        return None, ""

    def method_5_refinement_level(self) -> Tuple[Optional[float], str]:
        """Priority 5: refinement_levels lookup."""
        geom = self.config.get('geometry', {})
        mesh = self.config.get('mesh', {})

        ref_level_key = geom.get('refinement_level')
        if not ref_level_key:
            return None, ""

        refinement_levels = mesh.get('refinement_levels', {})
        if not isinstance(refinement_levels, dict):
            return None, ""

        level_meters = refinement_levels.get(ref_level_key)
        level_meters = self._coerce_positive(level_meters, f"refinement_levels['{ref_level_key}']")

        if level_meters is not None:
            cell_size_mm = level_meters * 1000.0
            return cell_size_mm, f"refinement_levels['{ref_level_key}'] = {level_meters}m = {cell_size_mm}mm"
        return None, ""

    def calculate(self) -> Tuple[float, str, int]:
        """
        Calculate cell size following priority hierarchy.

        Returns:
            (cell_size_mm, source_description, priority_level)
        """
        # Try each method in order
        cell_size, source = self.method_1_resolution_level()
        if cell_size is not None:
            return cell_size, source, 1

        cell_size, source = self.method_2_target_mm()
        if cell_size is not None:
            return cell_size, source, 2

        cell_size, source = self.method_3_blockmesh_resolution()
        if cell_size is not None:
            return cell_size, source, 3

        cell_size, source = self.method_4_cells_per_diameter()
        if cell_size is not None:
            return cell_size, source, 4

        cell_size, source = self.method_5_refinement_level()
        if cell_size is not None:
            return cell_size, source, 5

        # Default fallback (use centralized constant)
        return DEFAULT_CELL_SIZE_MM, f"default fallback ({DEFAULT_CELL_SIZE_MM}mm, matches 'medium' profile)", 6


def main():
    """Main CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Calculate mesh cell size from AortaCFD configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze patient config
  python compute_cell_size.py ../../cases_input/patient1/config.json

  # Test with specific reference radius
  python compute_cell_size.py mesh_medium.json --reference-radius 12.5

  # Show all methods
  python compute_cell_size.py mesh_fine.json --show-all-methods
        """
    )

    parser.add_argument('config_file', help='Path to configuration JSON file')
    parser.add_argument('--reference-radius', '-r', type=float,
                       help='Override reference radius (mm) for testing')
    parser.add_argument('--show-all-methods', '-a', action='store_true',
                       help='Show results from all methods, not just selected one')

    args = parser.parse_args()

    # Load config
    config_path = Path(args.config_file)
    if not config_path.exists():
        print(f"❌ Error: Config file not found: {config_path}")
        sys.exit(1)

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {config_path}: {e}")
        sys.exit(1)

    print("=" * 70)
    print("AortaCFD Mesh Cell Size Calculator")
    print("=" * 70)
    print(f"Config file: {config_path}")
    print()

    calculator = CellSizeCalculator(config, args.reference_radius)

    if args.show_all_methods:
        print("Testing all methods:")
        print("-" * 70)

        methods = [
            ("1. target_cell_size_mm", calculator.method_1_target_mm),
            ("2. blockmesh_resolution", calculator.method_2_blockmesh_resolution),
            ("3. cells_per_diameter", calculator.method_3_cells_per_diameter),
            ("4. refinement_levels", calculator.method_4_refinement_level),
        ]

        for name, method in methods:
            cell_size, source = method()
            if cell_size is not None:
                print(f"✓ {name}: {cell_size:.3f} mm")
                print(f"  Formula: {source}")
            else:
                print(f"✗ {name}: Not configured")
            print()

    # Calculate using priority hierarchy
    print("SELECTED METHOD (following priority hierarchy):")
    print("-" * 70)
    cell_size, source, priority = calculator.calculate()

    priority_labels = {
        1: "Priority 1 (highest)",
        2: "Priority 2",
        3: "Priority 3",
        4: "Priority 4",
        5: "Default fallback"
    }

    print(f"✓ Cell size: {cell_size:.3f} mm")
    print(f"  Method: {source}")
    print(f"  Priority: {priority_labels[priority]}")
    print()

    # Estimate mesh size
    print("ESTIMATED MESH CHARACTERISTICS:")
    print("-" * 70)

    # Assume 100mm domain (rough estimate)
    domain_size = 100.0  # mm
    cells_per_dim = int(domain_size / cell_size)
    total_cells = cells_per_dim ** 3

    print(f"Approximate domain: {domain_size}mm × {domain_size}mm × {domain_size}mm")
    print(f"Background mesh: ~{cells_per_dim}³ = ~{total_cells:,} cells")
    print()

    if cell_size >= 2.0:
        quality = "COARSE"
        use_case = "Quick checks, draft runs"
    elif cell_size >= 1.0:
        quality = "MEDIUM"
        use_case = "Clinical analysis, routine work"
    else:
        quality = "FINE"
        use_case = "Publication, detailed analysis"

    print(f"Quality level: {quality}")
    print(f"Typical use: {use_case}")
    print()

    print("=" * 70)

    # Recommendations
    if priority == 6:
        print()
        print(f"⚠️  WARNING: Using default fallback ({DEFAULT_CELL_SIZE_MM}mm)")
        print("   Recommendation: Set one of these parameters explicitly:")
        print("   1. mesh.resolution_level = 'medium' (RECOMMENDED)")
        print(f"   2. mesh.mesh_resolution.target_cell_size_mm = {DEFAULT_CELL_SIZE_MM}")
        print("   3. mesh.mesh_resolution.cells_per_diameter = 15")


if __name__ == '__main__':
    main()
