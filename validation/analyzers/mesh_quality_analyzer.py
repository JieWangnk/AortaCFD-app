"""
Mesh Quality Analyzer for CFD Validation

Parses checkMesh output and analyzes mesh quality metrics from OpenFOAM cases.
Provides pass/fail criteria based on CFD best practices.
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class MeshQualityMetrics:
    """Container for mesh quality metrics."""

    # Basic mesh info
    num_points: int = 0
    num_cells: int = 0
    num_faces: int = 0
    num_internal_faces: int = 0

    # Quality metrics
    max_non_orthogonality: float = 0.0
    max_skewness: float = 0.0
    max_aspect_ratio: float = 0.0
    min_volume: float = 0.0
    min_face_area: float = 0.0

    # Check results
    failed_cells: int = 0
    mesh_ok: bool = False

    # Boundary layer info (if available)
    boundary_layer_thickness: Optional[float] = None
    boundary_layer_expansion_ratio: Optional[float] = None
    num_boundary_layers: Optional[int] = None

    def passes_quality_checks(self, solver_type: str = "laminar") -> Tuple[bool, List[str]]:
        """
        Check if mesh passes quality criteria for given solver type.

        Args:
            solver_type: "laminar", "rans", or "les"

        Returns:
            (passed, list_of_issues)
        """
        issues = []

        # OpenFOAM recommended limits
        if self.max_non_orthogonality > 70:
            issues.append(f"Non-orthogonality {self.max_non_orthogonality:.1f} > 70 (poor quality)")
        elif self.max_non_orthogonality > 65:
            issues.append(f"Non-orthogonality {self.max_non_orthogonality:.1f} > 65 (marginal quality)")

        if self.max_skewness > 4.0:
            issues.append(f"Skewness {self.max_skewness:.2f} > 4.0 (poor quality)")

        # Aspect ratio limits (more strict for LES)
        aspect_limit = 100 if solver_type == "les" else 1000
        if self.max_aspect_ratio > aspect_limit:
            issues.append(f"Aspect ratio {self.max_aspect_ratio:.1f} > {aspect_limit} ({solver_type} limit)")

        # Volume/area checks
        if self.min_volume <= 0:
            issues.append(f"Minimum volume {self.min_volume:.2e} <= 0 (invalid mesh)")

        if self.min_face_area <= 0:
            issues.append(f"Minimum face area {self.min_face_area:.2e} <= 0 (invalid mesh)")

        # Failed cells check
        if self.failed_cells > 0:
            issues.append(f"Mesh has {self.failed_cells} failed cells")

        # Overall mesh OK flag from checkMesh
        if not self.mesh_ok:
            issues.append("checkMesh reported mesh NOT OK")

        passed = len(issues) == 0
        return passed, issues


class MeshQualityAnalyzer:
    """Analyzes mesh quality from OpenFOAM case directories."""

    def __init__(self, case_directory: Path):
        """
        Initialize analyzer.

        Args:
            case_directory: Path to OpenFOAM case directory
        """
        self.case_dir = Path(case_directory)

    def check_mesh_files_exist(self) -> bool:
        """
        Check if mesh files (polyMesh) exist.

        Returns:
            True if mesh exists, False otherwise
        """
        poly_mesh = self.case_dir / "constant" / "polyMesh"
        return poly_mesh.exists() and (poly_mesh / "points").exists()

    def check_mesh_dict_files_exist(self) -> Dict[str, bool]:
        """
        Check if mesh dictionary files exist (Level 1 validation).

        Returns:
            Dictionary mapping file name to existence status
        """
        system_dir = self.case_dir / "system"
        return {
            "blockMeshDict": (system_dir / "blockMeshDict").exists(),
            "snappyHexMeshDict": (system_dir / "snappyHexMeshDict").exists(),
            "surfaceFeaturesDict": (system_dir / "surfaceFeaturesDict").exists(),
        }

    def run_checkMesh(self, log_file: Optional[Path] = None) -> str:
        """
        Run checkMesh on the case directory.

        Args:
            log_file: Optional path to save log output

        Returns:
            checkMesh output as string
        """
        try:
            # Run checkMesh
            result = subprocess.run(
                ["checkMesh", "-case", str(self.case_dir)],
                capture_output=True,
                text=True,
                timeout=60
            )

            output = result.stdout + result.stderr

            # Save to log file if requested
            if log_file:
                log_file.write_text(output)

            return output

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"checkMesh timed out after 60 seconds")
        except FileNotFoundError:
            raise RuntimeError("checkMesh not found. Is OpenFOAM installed and sourced?")
        except Exception as e:
            raise RuntimeError(f"Error running checkMesh: {e}")

    def parse_checkMesh_output(self, output: str) -> MeshQualityMetrics:
        """
        Parse checkMesh output and extract quality metrics.

        Args:
            output: checkMesh output string

        Returns:
            MeshQualityMetrics object
        """
        metrics = MeshQualityMetrics()

        # Parse basic mesh statistics
        if match := re.search(r"points:\s+(\d+)", output):
            metrics.num_points = int(match.group(1))

        if match := re.search(r"cells:\s+(\d+)", output):
            metrics.num_cells = int(match.group(1))

        if match := re.search(r"faces:\s+(\d+)", output):
            metrics.num_faces = int(match.group(1))

        if match := re.search(r"internal faces:\s+(\d+)", output):
            metrics.num_internal_faces = int(match.group(1))

        # Parse quality metrics (strip trailing periods from numbers)
        if match := re.search(r"Max non-orthogonality.*?:\s*([\d.]+)", output):
            metrics.max_non_orthogonality = float(match.group(1).rstrip('.'))
        elif match := re.search(r"non-orthogonality Max:\s*([\d.]+)", output):
            metrics.max_non_orthogonality = float(match.group(1).rstrip('.'))

        if match := re.search(r"Max skewness =\s*([\d.]+)", output):
            metrics.max_skewness = float(match.group(1).rstrip('.'))
        elif match := re.search(r"skewness =\s*([\d.]+)", output):
            metrics.max_skewness = float(match.group(1).rstrip('.'))

        # Aspect ratio (may appear as "Max cell openness" or "Max aspect ratio")
        if match := re.search(r"Max aspect ratio =\s*([\d.]+)", output):
            metrics.max_aspect_ratio = float(match.group(1).rstrip('.'))
        elif match := re.search(r"Max cell openness =\s*([\d.eE+-]+)", output):
            # Openness is related to aspect ratio
            metrics.max_aspect_ratio = float(match.group(1).rstrip('.')) * 10  # Rough conversion

        # Volume checks
        if match := re.search(r"Min volume =\s*([\d.eE+-]+)", output):
            metrics.min_volume = float(match.group(1).rstrip('.'))

        # Face area checks
        if match := re.search(r"Minimum face area =\s*([\d.eE+-]+)", output):
            metrics.min_face_area = float(match.group(1).rstrip('.'))
        elif match := re.search(r"Min area =\s*([\d.eE+-]+)", output):
            metrics.min_face_area = float(match.group(1).rstrip('.'))

        # Failed cells
        if match := re.search(r"Failed (\d+) mesh checks", output):
            metrics.failed_cells = int(match.group(1))

        # Overall mesh OK check
        if "Mesh OK" in output:
            metrics.mesh_ok = True
        elif "Failed" in output or "FAILED" in output:
            metrics.mesh_ok = False

        return metrics

    def analyze_boundary_layers(self) -> Dict[str, any]:
        """
        Analyze boundary layer quality from snappyHexMesh output.

        Returns:
            Dictionary with boundary layer statistics
        """
        snappy_log = self.case_dir / "log.snappyHexMesh"

        if not snappy_log.exists():
            return {
                "available": False,
                "message": "snappyHexMesh log not found"
            }

        content = snappy_log.read_text()

        bl_info = {
            "available": True,
            "first_layer_thickness": None,
            "expansion_ratio": None,
            "num_layers": None,
            "coverage": None
        }

        # Parse layer addition statistics
        if match := re.search(r"thickness of layer 0 :\s+([\d.eE+-]+)", content):
            bl_info["first_layer_thickness"] = float(match.group(1))

        if match := re.search(r"expansion ratio\s+:\s+([\d.]+)", content):
            bl_info["expansion_ratio"] = float(match.group(1))

        if match := re.search(r"number of layers\s+:\s+(\d+)", content):
            bl_info["num_layers"] = int(match.group(1))

        # Parse layer coverage
        if match := re.search(r"Added layers to ([\d.]+)% of faces", content):
            bl_info["coverage"] = float(match.group(1))

        return bl_info

    def get_cell_count_by_type(self) -> Dict[str, int]:
        """
        Get cell count breakdown by cell type.

        Returns:
            Dictionary mapping cell type to count
        """
        # Read polyMesh/owner to get cell count
        owner_file = self.case_dir / "constant" / "polyMesh" / "owner"

        if not owner_file.exists():
            return {"total": 0, "error": "polyMesh not found"}

        try:
            # Count unique cell IDs in owner file
            content = owner_file.read_text()

            # Find the data section (after header)
            if match := re.search(r"\n(\d+)\n\(", content):
                num_faces = int(match.group(1))
            else:
                num_faces = 0

            # Read actual cell IDs
            cell_ids = set()
            for line in content.split('\n'):
                if line.strip().isdigit():
                    cell_ids.add(int(line.strip()))

            num_cells = len(cell_ids)

            return {
                "total": num_cells,
                "hexahedra": num_cells,  # Assume mostly hex (snappyHexMesh)
                "note": "Detailed breakdown requires reading cellZones"
            }

        except Exception as e:
            return {"error": f"Failed to parse owner file: {e}"}

    def generate_quality_report(self, solver_type: str = "laminar") -> str:
        """
        Generate a human-readable quality report.

        Args:
            solver_type: "laminar", "rans", or "les"

        Returns:
            Formatted report string
        """
        # Run checkMesh
        try:
            output = self.run_checkMesh()
            metrics = self.parse_checkMesh_output(output)
        except Exception as e:
            return f"ERROR: Failed to run checkMesh: {e}"

        # Analyze boundary layers
        bl_info = self.analyze_boundary_layers()

        # Check quality
        passed, issues = metrics.passes_quality_checks(solver_type)

        # Build report
        report = []
        report.append("=" * 70)
        report.append(f"MESH QUALITY REPORT: {self.case_dir.name}")
        report.append("=" * 70)
        report.append("")

        # Basic statistics
        report.append("MESH STATISTICS:")
        report.append(f"  Points:         {metrics.num_points:>12,}")
        report.append(f"  Cells:          {metrics.num_cells:>12,}")
        report.append(f"  Faces:          {metrics.num_faces:>12,}")
        report.append(f"  Internal Faces: {metrics.num_internal_faces:>12,}")
        report.append("")

        # Quality metrics
        report.append("QUALITY METRICS:")
        report.append(f"  Non-orthogonality (max): {metrics.max_non_orthogonality:>8.2f}  [limit: < 70]")
        report.append(f"  Skewness (max):          {metrics.max_skewness:>8.2f}  [limit: < 4.0]")
        report.append(f"  Aspect ratio (max):      {metrics.max_aspect_ratio:>8.1f}")
        report.append(f"  Volume (min):            {metrics.min_volume:>8.2e}")
        report.append(f"  Face area (min):         {metrics.min_face_area:>8.2e}")
        report.append("")

        # Boundary layer info
        if bl_info.get("available"):
            report.append("BOUNDARY LAYER:")
            if bl_info["first_layer_thickness"]:
                report.append(f"  First layer thickness: {bl_info['first_layer_thickness']:.6f} m")
            if bl_info["expansion_ratio"]:
                report.append(f"  Expansion ratio:       {bl_info['expansion_ratio']:.2f}")
            if bl_info["num_layers"]:
                report.append(f"  Number of layers:      {bl_info['num_layers']}")
            if bl_info["coverage"]:
                report.append(f"  Coverage:              {bl_info['coverage']:.1f}%")
            report.append("")

        # Overall result
        report.append("OVERALL RESULT:")
        if passed:
            report.append(f"  ✅ PASS - Mesh quality acceptable for {solver_type.upper()} solver")
        else:
            report.append(f"  ❌ FAIL - Mesh quality issues detected:")
            for issue in issues:
                report.append(f"     - {issue}")

        report.append("")
        report.append("=" * 70)

        return "\n".join(report)


def analyze_mesh_quality(case_directory: Path, solver_type: str = "laminar") -> Tuple[MeshQualityMetrics, bool, List[str]]:
    """
    Convenience function to analyze mesh quality.

    Args:
        case_directory: Path to OpenFOAM case
        solver_type: "laminar", "rans", or "les"

    Returns:
        (metrics, passed, issues)
    """
    analyzer = MeshQualityAnalyzer(case_directory)

    try:
        output = analyzer.run_checkMesh()
        metrics = analyzer.parse_checkMesh_output(output)
        passed, issues = metrics.passes_quality_checks(solver_type)
        return metrics, passed, issues
    except Exception as e:
        # Return empty metrics with error
        metrics = MeshQualityMetrics()
        return metrics, False, [f"Analysis failed: {e}"]
