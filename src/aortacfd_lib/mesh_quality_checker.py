"""
Mesh Quality Checker - Analyzes checkMesh output and provides alerts/recommendations
"""

import os
import re
from pathlib import Path
from aortacfd_lib.utils.logger import Logger

class MeshQualityChecker:
    """
    Analyzes mesh quality from checkMesh log and provides alerts for poor quality.
    Based on OpenFOAM best practices and CFD simulation stability requirements.
    """

    def __init__(self):
        self.logger = Logger()

    def analyze_mesh_quality(self, case_dir: str) -> dict:
        """
        Analyze mesh quality from checkMesh log file.

        Args:
            case_dir: Path to OpenFOAM case directory

        Returns:
            dict: Quality analysis results with alerts and recommendations
        """
        checkmesh_log = Path(case_dir) / "logs" / "log.checkMesh"

        if not checkmesh_log.exists():
            return {
                'status': 'error',
                'message': 'checkMesh log file not found',
                'alerts': ['Mesh quality cannot be assessed - checkMesh log missing']
            }

        try:
            with open(checkmesh_log, 'r') as f:
                log_content = f.read()
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to read checkMesh log: {e}',
                'alerts': ['Cannot read mesh quality log file']
            }

        return self._parse_checkmesh_output(log_content)

    def _parse_checkmesh_output(self, content: str) -> dict:
        """Parse checkMesh output and extract quality metrics."""

        quality_report = {
            'status': 'good',
            'alerts': [],
            'warnings': [],
            'recommendations': [],
            'metrics': {}
        }

        # Check final status
        if "Failed" in content and "mesh checks" in content:
            failed_match = re.search(r'Failed (\d+) mesh checks', content)
            if failed_match:
                failed_checks = int(failed_match.group(1))
                quality_report['status'] = 'failed' if failed_checks > 0 else 'good'
                quality_report['metrics']['failed_checks'] = failed_checks

                if failed_checks > 0:
                    quality_report['alerts'].append(f"Mesh failed {failed_checks} quality checks")

        # Extract specific metrics
        self._extract_skewness(content, quality_report)
        self._extract_aspect_ratio(content, quality_report)
        self._extract_non_orthogonality(content, quality_report)
        self._extract_face_areas(content, quality_report)
        self._extract_cell_volumes(content, quality_report)

        # Generate recommendations based on issues found
        self._generate_recommendations(quality_report)

        return quality_report

    def _extract_skewness(self, content: str, report: dict):
        """Extract skewness information."""
        skew_match = re.search(r'Max skewness = ([\d.]+)', content)
        if skew_match:
            max_skew = float(skew_match.group(1))
            report['metrics']['max_skewness'] = max_skew

            # Check for highly skew faces
            highly_skew_match = re.search(r'(\d+) highly skew faces detected', content)
            if highly_skew_match:
                highly_skew_faces = int(highly_skew_match.group(1))
                report['metrics']['highly_skew_faces'] = highly_skew_faces

            # Thresholds based on OpenFOAM best practices for curved geometry
            # maxInternalSkewness default is 4, but <2 recommended for transitional flow
            if max_skew > 4.0:
                report['status'] = 'poor'
                report['alerts'].append(f"Very high skewness detected: {max_skew:.2f} (threshold: 4.0)")
                if 'highly_skew_faces' in report['metrics']:
                    report['alerts'].append(f"{report['metrics']['highly_skew_faces']} highly skewed faces found")
            elif max_skew > 2.0:
                report['status'] = 'warning' if report['status'] == 'good' else report['status']
                report['warnings'].append(f"High skewness: {max_skew:.2f} (recommend < 2.0 for curved geometry)")

    def _extract_aspect_ratio(self, content: str, report: dict):
        """Extract aspect ratio information."""
        aspect_match = re.search(r'Max aspect ratio = ([\d.]+)', content)
        if aspect_match:
            max_aspect = float(aspect_match.group(1))
            report['metrics']['max_aspect_ratio'] = max_aspect

            if max_aspect > 10.0:
                report['status'] = 'poor' if report['status'] != 'failed' else report['status']
                report['alerts'].append(f"Very high aspect ratio: {max_aspect:.2f} (threshold: 10.0)")
            elif max_aspect > 6.0:
                report['status'] = 'warning' if report['status'] == 'good' else report['status']
                report['warnings'].append(f"High aspect ratio: {max_aspect:.2f} (recommend < 6.0)")

    def _extract_non_orthogonality(self, content: str, report: dict):
        """Extract non-orthogonality information."""
        ortho_match = re.search(r'Mesh non-orthogonality Max: ([\d.]+) average: ([\d.]+)', content)
        if ortho_match:
            max_ortho = float(ortho_match.group(1))
            avg_ortho = float(ortho_match.group(2))
            report['metrics']['max_non_orthogonality'] = max_ortho
            report['metrics']['avg_non_orthogonality'] = avg_ortho

            if max_ortho > 70.0:
                report['status'] = 'poor' if report['status'] != 'failed' else report['status']
                report['alerts'].append(f"Very high non-orthogonality: {max_ortho:.1f}° (threshold: 70°)")
            elif max_ortho > 60.0:
                report['status'] = 'warning' if report['status'] == 'good' else report['status']
                report['warnings'].append(f"High non-orthogonality: {max_ortho:.1f}° (recommend < 60°)")

    def _extract_face_areas(self, content: str, report: dict):
        """Extract face area information."""
        area_match = re.search(r'Minimum face area = ([\d.e-]+)\. Maximum face area = ([\d.e-]+)', content)
        if area_match:
            min_area = float(area_match.group(1))
            max_area = float(area_match.group(2))
            report['metrics']['min_face_area'] = min_area
            report['metrics']['max_face_area'] = max_area
            report['metrics']['face_area_ratio'] = max_area / min_area if min_area > 0 else float('inf')

    def _extract_cell_volumes(self, content: str, report: dict):
        """Extract cell volume information."""
        vol_match = re.search(r'Min volume = ([\d.e-]+)\. Max volume = ([\d.e-]+)', content)
        if vol_match:
            min_vol = float(vol_match.group(1))
            max_vol = float(vol_match.group(2))
            report['metrics']['min_cell_volume'] = min_vol
            report['metrics']['max_cell_volume'] = max_vol
            report['metrics']['volume_ratio'] = max_vol / min_vol if min_vol > 0 else float('inf')

    def _generate_recommendations(self, report: dict):
        """Generate recommendations based on quality issues."""
        if report['status'] in ['poor', 'failed']:
            report['recommendations'].append("🔴 CRITICAL: This mesh quality will likely cause simulation instability")

            # Specific recommendations based on issues
            metrics = report['metrics']

            if metrics.get('max_skewness', 0) > 2.0:
                report['recommendations'].extend([
                    "• Increase surface refinement levels to reduce skewness",
                    "• Ensure feature extraction level ≤ minimum surface refinement level",
                    "• Consider using 'draft' profile with 1st order numerics for stability"
                ])

            if metrics.get('max_aspect_ratio', 0) > 8.0:
                report['recommendations'].extend([
                    "• Disable boundary layers (addLayer: 0) to reduce aspect ratio",
                    "• Increase minThickness and finalLayerThickness in layer settings",
                    "• Use span-based refinement for narrow regions"
                ])

            if metrics.get('max_non_orthogonality', 0) > 60.0:
                report['recommendations'].extend([
                    "• Increase nSmoothPatch iterations",
                    "• Lower resolveFeatureAngle (try 20-25°)",
                    "• Enable non-orthogonal correctors in solver (nNonOrthogonalCorrectors 2-3)"
                ])

            # Profile recommendations
            report['recommendations'].append("• Consider switching to 'draft' profile for testing with poor mesh quality")
            report['recommendations'].append("• If using high-order numerics, switch to 1st order stable schemes")

        elif report['status'] == 'warning':
            report['recommendations'].append("⚠️  Mesh quality is acceptable but could be improved")
            report['recommendations'].append("• Monitor solver stability and reduce CFL if needed")
            report['recommendations'].append("• Consider mesh refinement for better accuracy")

    def print_quality_report(self, report: dict, case_name: str = ""):
        """Print a formatted quality report."""

        status_symbols = {
            'good': '✅',
            'warning': '⚠️',
            'poor': '🔴',
            'failed': '❌',
            'error': '💥'
        }

        print(f"\n{'='*70}")
        print(f"MESH QUALITY REPORT {f'- {case_name}' if case_name else ''}")
        print(f"{'='*70}")

        # Status
        symbol = status_symbols.get(report['status'], '❓')
        print(f"Status: {symbol} {report['status'].upper()}")

        # Metrics
        if report['metrics']:
            print(f"\nQuality Metrics:")
            metrics = report['metrics']

            if 'max_skewness' in metrics:
                print(f"  • Max Skewness: {metrics['max_skewness']:.2f} (recommend < 2.0)")
            if 'max_aspect_ratio' in metrics:
                print(f"  • Max Aspect Ratio: {metrics['max_aspect_ratio']:.2f} (recommend < 6.0)")
            if 'max_non_orthogonality' in metrics:
                print(f"  • Max Non-orthogonality: {metrics['max_non_orthogonality']:.1f}° (recommend < 60°)")
            if 'failed_checks' in metrics:
                print(f"  • Failed Checks: {metrics['failed_checks']}")

        # Alerts
        if report['alerts']:
            print(f"\nAlerts:")
            for alert in report['alerts']:
                print(f"  🚨 {alert}")

        # Warnings
        if report['warnings']:
            print(f"\nWarnings:")
            for warning in report['warnings']:
                print(f"  ⚠️  {warning}")

        # Recommendations
        if report['recommendations']:
            print(f"\nRecommendations:")
            for rec in report['recommendations']:
                print(f"  {rec}")

        print(f"{'='*70}\n")

    def should_abort_simulation(self, report: dict) -> bool:
        """
        Determine if simulation should be aborted based on mesh quality.

        Returns:
            bool: True if mesh quality is too poor to continue
        """
        if report['status'] == 'failed':
            return True

        # Check critical thresholds
        metrics = report['metrics']

        # Very high skewness will cause divergence
        if metrics.get('max_skewness', 0) > 6.0:
            return True

        # Extreme aspect ratios cause numerical issues
        if metrics.get('max_aspect_ratio', 0) > 15.0:
            return True

        return False