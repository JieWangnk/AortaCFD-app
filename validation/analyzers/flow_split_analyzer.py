#!/usr/bin/env python3
"""
Flow Split Analyzer - Compare Custom vs Murray's Law Flow Distributions

This module validates flow split configurations by:
1. Reading custom flow_split from config
2. Calculating expected Murray's Law ratios from geometry
3. Comparing custom vs Murray distributions
4. Generating validation reports
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import math


@dataclass
class FlowSplitMetrics:
    """Metrics for flow split analysis"""
    # Custom flow split (from config)
    custom_split: Dict[str, float] = None
    custom_split_source: str = "unknown"  # "config", "equal", "murray_auto"

    # Murray's Law calculated split
    murray_split: Dict[str, float] = None
    murray_exponent: float = 2.39

    # Outlet geometries
    outlet_areas: Dict[str, float] = None
    outlet_diameters: Dict[str, float] = None

    # Comparison metrics
    deviation_percent: Dict[str, float] = None  # Per-outlet deviation
    max_deviation_percent: float = 0.0
    mean_deviation_percent: float = 0.0

    # Validation
    is_murray_based: bool = False
    is_custom_valid: bool = False
    ratios_match: bool = False

    def __post_init__(self):
        if self.custom_split is None:
            self.custom_split = {}
        if self.murray_split is None:
            self.murray_split = {}
        if self.outlet_areas is None:
            self.outlet_areas = {}
        if self.outlet_diameters is None:
            self.outlet_diameters = {}
        if self.deviation_percent is None:
            self.deviation_percent = {}


class FlowSplitAnalyzer:
    """Analyzes and compares flow split configurations"""

    DEVIATION_THRESHOLD = 10.0  # percent - custom vs Murray must be within 10%

    def __init__(self, case_dir: Path):
        self.case_dir = Path(case_dir)

    def analyze_flow_split(self, config: dict) -> FlowSplitMetrics:
        """
        Analyze flow split configuration and compare with Murray's Law

        Args:
            config: Full simulation configuration dictionary

        Returns:
            FlowSplitMetrics with analysis results
        """
        metrics = FlowSplitMetrics()

        # Extract custom flow split from config
        metrics.custom_split, metrics.custom_split_source = self._extract_custom_split(config)

        # Calculate Murray's Law expected ratios from geometry
        metrics.outlet_areas = self._extract_outlet_areas()
        metrics.murray_exponent = self._get_murray_exponent(config)
        metrics.murray_split = self._calculate_murray_ratios(
            metrics.outlet_areas,
            metrics.murray_exponent
        )

        # Calculate outlet diameters for reporting
        metrics.outlet_diameters = {
            name: 2 * math.sqrt(area / math.pi) * 1000  # mm
            for name, area in metrics.outlet_areas.items()
        }

        # Compare custom vs Murray
        if metrics.custom_split and metrics.murray_split:
            metrics.deviation_percent = self._calculate_deviations(
                metrics.custom_split,
                metrics.murray_split
            )

            if metrics.deviation_percent:
                deviations = list(metrics.deviation_percent.values())
                metrics.max_deviation_percent = max(deviations)
                metrics.mean_deviation_percent = sum(deviations) / len(deviations)
                metrics.ratios_match = metrics.max_deviation_percent < self.DEVIATION_THRESHOLD

        # Determine if Murray-based
        metrics.is_murray_based = (
            metrics.custom_split_source == "murray_auto" or
            (metrics.custom_split_source == "config" and metrics.ratios_match)
        )

        # Validate custom split
        metrics.is_custom_valid = self._validate_custom_split(metrics.custom_split)

        return metrics

    def _extract_custom_split(self, config: dict) -> Tuple[Dict[str, float], str]:
        """
        Extract custom flow split from config

        Returns:
            (flow_split_dict, source_type)
            source_type: "config", "equal", "murray_auto", "unknown"
        """
        # Check windkessel settings for flow_split
        wk_settings = config.get('boundary_conditions', {}).get('outlets', {}).get('windkessel_settings', {})

        if 'flow_split' in wk_settings and wk_settings['flow_split']:
            flow_split = wk_settings['flow_split']

            # Check if all ratios are equal (suggests equal split default)
            ratios = list(flow_split.values())
            if len(set(ratios)) == 1:
                return flow_split, "equal"

            # Check if methodology is Murray's Law
            methodology = wk_settings.get('methodology', '')
            if 'murray' in methodology.lower():
                return flow_split, "murray_auto"

            return flow_split, "config"

        # No flow_split found
        return {}, "unknown"

    def _extract_outlet_areas(self) -> Dict[str, float]:
        """Extract outlet areas from checkMesh log or STL files"""
        # Try checkMesh log first
        areas = self._extract_areas_from_checkmesh()

        if areas:
            return areas

        # Fallback to STL analysis
        return self._extract_areas_from_stl()

    def _extract_areas_from_checkmesh(self) -> Dict[str, float]:
        """Extract outlet areas from checkMesh log"""
        outlet_areas = {}

        try:
            # Try multiple log locations
            possible_logs = [
                self.case_dir / "logs" / "log.checkMesh",
                self.case_dir / "log.checkMesh",
            ]

            checkmesh_log = None
            for log_path in possible_logs:
                if log_path.exists():
                    checkmesh_log = log_path
                    break

            if not checkmesh_log:
                return outlet_areas

            with open(checkmesh_log, 'r') as f:
                content = f.read()

            # Find patch topology section
            patch_section = re.search(
                r'Checking patch topology.*?\n(.*?)(?=\n\n|\nChecking)',
                content, re.DOTALL
            )

            if patch_section:
                patch_faces = {}
                lines = patch_section.group(1).strip().split('\n')

                for line in lines:
                    if line.strip() and not line.strip().startswith('Patch'):
                        parts = line.split()
                        if len(parts) >= 3:
                            try:
                                patch_name = parts[0]
                                faces = int(parts[1])
                                patch_faces[patch_name] = faces
                            except ValueError:
                                continue

                # Filter outlet patches
                for patch_name, faces in patch_faces.items():
                    if any(keyword in patch_name.lower() for keyword in ['outlet', 'exit', 'out']):
                        # Estimate area: assume avg face area of 1e-6 m² (1 mm²)
                        outlet_areas[patch_name] = faces * 1e-6

        except Exception as e:
            pass

        return outlet_areas

    def _extract_areas_from_stl(self) -> Dict[str, float]:
        """Extract outlet areas from STL files using actual geometry calculation"""
        outlet_areas = {}

        stl_dir = self.case_dir / "constant" / "triSurface"
        if not stl_dir.exists():
            return outlet_areas

        for stl_file in stl_dir.glob("outlet*.stl"):
            patch_name = stl_file.stem

            try:
                # Read STL and calculate actual area
                area = self._calculate_stl_surface_area(stl_file)
                if area > 0:
                    outlet_areas[patch_name] = area

            except Exception as e:
                continue

        return outlet_areas

    def _calculate_stl_surface_area(self, stl_file: Path) -> float:
        """
        Calculate surface area of STL file by summing triangle areas
        Handles both ASCII and binary STL formats

        Formula: Area of triangle = 0.5 * |AB × AC|
        where AB and AC are edge vectors
        """
        import struct
        import re

        try:
            # Check if binary STL (starts with 80-byte header)
            with open(stl_file, 'rb') as f:
                header = f.read(80)
                # Check if ASCII (starts with "solid")
                is_ascii = header[:5].decode('ascii', errors='ignore').lower() == 'solid'

            if is_ascii:
                return self._calculate_ascii_stl_area(stl_file)
            else:
                return self._calculate_binary_stl_area(stl_file)

        except Exception as e:
            return 0.0

    def _calculate_ascii_stl_area(self, stl_file: Path) -> float:
        """Calculate area from ASCII STL"""
        import re

        with open(stl_file, 'r') as f:
            content = f.read()

        # Extract all vertices using regex
        vertices = []
        for match in re.finditer(r'vertex\s+([-\d.e+]+)\s+([-\d.e+]+)\s+([-\d.e+]+)', content):
            x, y, z = float(match.group(1)), float(match.group(2)), float(match.group(3))
            vertices.append([x, y, z])

        if len(vertices) < 3:
            return 0.0

        # Calculate area of each triangle
        total_area = 0.0
        for i in range(0, len(vertices), 3):
            if i + 2 < len(vertices):
                area = self._triangle_area(vertices[i], vertices[i+1], vertices[i+2])
                total_area += area

        return total_area

    def _calculate_binary_stl_area(self, stl_file: Path) -> float:
        """Calculate area from binary STL"""
        import struct

        total_area = 0.0

        with open(stl_file, 'rb') as f:
            # Skip 80-byte header
            f.read(80)

            # Read number of triangles
            num_triangles = struct.unpack('<I', f.read(4))[0]

            # Read each triangle
            for _ in range(num_triangles):
                # Normal vector (3 floats) - skip
                f.read(12)

                # 3 vertices (3 floats each)
                v1 = struct.unpack('<fff', f.read(12))
                v2 = struct.unpack('<fff', f.read(12))
                v3 = struct.unpack('<fff', f.read(12))

                # Attribute byte count - skip
                f.read(2)

                # Calculate triangle area
                area = self._triangle_area(v1, v2, v3)
                total_area += area

        return total_area

    def _triangle_area(self, v1, v2, v3) -> float:
        """Calculate area of a triangle from 3 vertices"""
        # Edge vectors
        AB = [v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]]
        AC = [v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]]

        # Cross product AB × AC
        cross = [
            AB[1]*AC[2] - AB[2]*AC[1],
            AB[2]*AC[0] - AB[0]*AC[2],
            AB[0]*AC[1] - AB[1]*AC[0]
        ]

        # Magnitude of cross product
        magnitude = math.sqrt(cross[0]**2 + cross[1]**2 + cross[2]**2)

        # Triangle area = 0.5 * magnitude
        return 0.5 * magnitude

    def _get_murray_exponent(self, config: dict) -> float:
        """Get Murray exponent from config or use default"""
        # Check physics section for explicit exponent
        exponent = config.get('physics', {}).get('murray_exponent')

        if exponent:
            return float(exponent)

        # Default to meta-analysis value
        return 2.39

    def _calculate_murray_ratios(
        self,
        outlet_areas: Dict[str, float],
        exponent: float
    ) -> Dict[str, float]:
        """
        Calculate flow split ratios using Murray's Law

        Murray's Law: Q ∝ r^n  (or Q ∝ A^(n/2))

        Args:
            outlet_areas: Dict mapping outlet names to areas (m²)
            exponent: Murray exponent (typically 2.0-3.0)

        Returns:
            Dict mapping outlet names to flow ratios (sum = 1.0)
        """
        if not outlet_areas:
            return {}

        # Calculate flow proportions: Q_i ∝ A_i^(n/2)
        flow_proportions = {}
        for name, area in outlet_areas.items():
            radius = math.sqrt(area / math.pi)
            flow_proportions[name] = radius ** exponent

        # Normalize to ratios (sum = 1.0)
        total = sum(flow_proportions.values())
        ratios = {name: prop / total for name, prop in flow_proportions.items()}

        return ratios

    def _calculate_deviations(
        self,
        custom_split: Dict[str, float],
        murray_split: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calculate deviation between custom and Murray splits

        Returns:
            Dict mapping outlet names to deviation percentage
        """
        deviations = {}

        # Only compare outlets present in both
        common_outlets = set(custom_split.keys()) & set(murray_split.keys())

        for outlet in common_outlets:
            custom_ratio = custom_split[outlet]
            murray_ratio = murray_split[outlet]

            if murray_ratio > 0:
                deviation = abs(custom_ratio - murray_ratio) / murray_ratio * 100
                deviations[outlet] = deviation

        return deviations

    def _validate_custom_split(self, custom_split: Dict[str, float]) -> bool:
        """Validate that custom split ratios sum to 1.0"""
        if not custom_split:
            return False

        total = sum(custom_split.values())
        return abs(total - 1.0) < 0.01  # Within 1% of perfect sum

    def print_analysis_report(self, metrics: FlowSplitMetrics):
        """Print formatted analysis report"""
        print("\n" + "="*70)
        print("FLOW SPLIT ANALYSIS REPORT")
        print("="*70)

        # Outlet geometry
        print("\nOUTLET GEOMETRY:")
        if metrics.outlet_diameters:
            for name in sorted(metrics.outlet_diameters.keys()):
                area = metrics.outlet_areas.get(name, 0)
                diameter = metrics.outlet_diameters[name]
                print(f"  {name:20s} → d={diameter:5.1f} mm  (A={area:.2e} m²)")
        else:
            print("  ⚠️  No outlet geometry data available")

        # Custom flow split
        print(f"\nCUSTOM FLOW SPLIT:")
        print(f"  Source: {metrics.custom_split_source}")
        if metrics.custom_split:
            total = sum(metrics.custom_split.values())
            print(f"  Total: {total:.3f} {'✓' if abs(total - 1.0) < 0.01 else '✗ (should be 1.0)'}")
            for name in sorted(metrics.custom_split.keys()):
                ratio = metrics.custom_split[name]
                print(f"    {name:20s} → {ratio:6.1%}")
        else:
            print("  ⚠️  No custom flow split defined")

        # Murray's Law calculation
        print(f"\nMURRAY'S LAW CALCULATION:")
        print(f"  Exponent: {metrics.murray_exponent}")
        if metrics.murray_split:
            for name in sorted(metrics.murray_split.keys()):
                ratio = metrics.murray_split[name]
                print(f"    {name:20s} → {ratio:6.1%}")
        else:
            print("  ⚠️  Could not calculate Murray ratios (missing geometry)")

        # Comparison
        if metrics.custom_split and metrics.murray_split:
            print(f"\nCOMPARISON (Custom vs Murray):")
            for name in sorted(metrics.deviation_percent.keys()):
                custom = metrics.custom_split[name]
                murray = metrics.murray_split[name]
                deviation = metrics.deviation_percent[name]

                status = "✓" if deviation < self.DEVIATION_THRESHOLD else "✗"
                print(f"  {name:20s} → {custom:6.1%} vs {murray:6.1%}  "
                      f"(deviation: {deviation:5.1f}%) {status}")

            print(f"\n  Mean Deviation:      {metrics.mean_deviation_percent:5.1f}%")
            print(f"  Max Deviation:       {metrics.max_deviation_percent:5.1f}%")
            print(f"  Threshold:           {self.DEVIATION_THRESHOLD:.1f}%")

        # Validation summary
        print(f"\nVALIDATION SUMMARY:")
        print(f"  Custom Split Valid:  {'✓ Yes' if metrics.is_custom_valid else '✗ No'}")
        print(f"  Murray-Based:        {'✓ Yes' if metrics.is_murray_based else '✗ No'}")
        print(f"  Ratios Match:        {'✓ Yes' if metrics.ratios_match else '✗ No (>10% deviation)'}")

        overall = metrics.is_custom_valid and (metrics.is_murray_based or metrics.ratios_match)
        print(f"\n  OVERALL:             {'✅ PASS' if overall else '❌ FAIL'}")

        print("\n" + "="*70 + "\n")


def main():
    """CLI for flow split analysis"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze and compare flow split configurations"
    )
    parser.add_argument("case_dir", type=Path, help="Case directory path")
    parser.add_argument("--config", type=Path, help="Config JSON file path")

    args = parser.parse_args()

    # Load config
    if args.config:
        with open(args.config) as f:
            config = json.load(f)
    else:
        # Try to find config in case directory
        config_file = args.case_dir / "config.json"
        if not config_file.exists():
            print(f"❌ Error: No config file found. Specify --config or place config.json in case directory")
            return 1

        with open(config_file) as f:
            config = json.load(f)

    # Run analysis
    analyzer = FlowSplitAnalyzer(args.case_dir)
    metrics = analyzer.analyze_flow_split(config)
    analyzer.print_analysis_report(metrics)

    return 0 if (metrics.is_custom_valid and (metrics.is_murray_based or metrics.ratios_match)) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
