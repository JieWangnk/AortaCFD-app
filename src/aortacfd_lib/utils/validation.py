"""
Validation utilities for AortaCFD.

This module provides validation classes for:
- Geometry validation (STL files, patches)
- Mesh quality validation
- Boundary condition validation

All validators follow the pattern:
1. Check validity
2. Return (is_valid: bool, errors: list[str], warnings: list[str])
"""

import os
import struct
from pathlib import Path
from typing import Tuple, List, Dict, Optional
import logging
from .logger import Logger

logger = logging.getLogger(__name__)


class ValidationResult:
    """Container for validation results."""

    def __init__(self, is_valid: bool = True, errors: Optional[List[str]] = None,
                 warnings: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []

    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)

    def __bool__(self):
        return self.is_valid

    def __str__(self):
        parts = []
        if self.errors:
            parts.append(f"Errors: {', '.join(self.errors)}")
        if self.warnings:
            parts.append(f"Warnings: {', '.join(self.warnings)}")
        return "; ".join(parts) if parts else "Valid"


class GeometryValidator:
    """
    Validates STL geometry files and patch configurations.

    Checks:
    - STL file format and integrity
    - Triangle normal consistency
    - Patch connectivity
    - Minimum surface area requirements
    - Inlet/outlet orientation
    """

    # Minimum surface areas (in m²) for different patch types
    MIN_AREA_INLET = 1e-6      # 1 mm²
    MIN_AREA_OUTLET = 1e-7     # 0.1 mm²
    MIN_AREA_WALL = 1e-5       # 10 mm²

    def __init__(self, case_directory: str, scale_factor: float = 1.0):
        """
        Initialize geometry validator.

        Args:
            case_directory: Path to case input directory with STL files
            scale_factor: Geometry scale factor (e.g., 0.001 for mm to m)
        """
        self.case_directory = Path(case_directory)
        self.scale_factor = scale_factor
        self.logger = logger

    def validate_all(self) -> ValidationResult:
        """
        Run all geometry validation checks.

        Returns:
            ValidationResult with overall status and any errors/warnings
        """
        result = ValidationResult()

        # Check case directory exists
        if not self.case_directory.exists():
            result.add_error(f"Case directory not found: {self.case_directory}")
            return result

        # Find all STL files
        stl_files = list(self.case_directory.glob("*.stl"))
        if not stl_files:
            result.add_error(f"No STL files found in {self.case_directory}")
            return result

        # Validate each STL file
        for stl_file in stl_files:
            file_result = self.check_stl_integrity(stl_file)
            result.errors.extend(file_result.errors)
            result.warnings.extend(file_result.warnings)
            if not file_result.is_valid:
                result.is_valid = False

        # Validate patch configuration
        patch_result = self.validate_patch_configuration(stl_files)
        result.errors.extend(patch_result.errors)
        result.warnings.extend(patch_result.warnings)
        if not patch_result.is_valid:
            result.is_valid = False

        return result

    def check_stl_integrity(self, stl_file: Path) -> ValidationResult:
        """
        Check STL file format and integrity.

        Args:
            stl_file: Path to STL file

        Returns:
            ValidationResult with file integrity status
        """
        result = ValidationResult()

        if not stl_file.exists():
            result.add_error(f"STL file not found: {stl_file}")
            return result

        # Check file size
        file_size = stl_file.stat().st_size
        if file_size == 0:
            result.add_error(f"STL file is empty: {stl_file.name}")
            return result

        if file_size < 84:  # Minimum size for binary STL header
            result.add_error(f"STL file too small: {stl_file.name} ({file_size} bytes)")
            return result

        # Detect ASCII vs Binary format
        try:
            with open(stl_file, 'rb') as f:
                header = f.read(6)
                is_ascii = header.startswith(b'solid ')

            if is_ascii:
                return self._validate_ascii_stl(stl_file)
            else:
                return self._validate_binary_stl(stl_file)

        except Exception as e:
            result.add_error(f"Error reading STL file {stl_file.name}: {str(e)}")
            return result

    def _validate_ascii_stl(self, stl_file: Path) -> ValidationResult:
        """Validate ASCII STL format."""
        result = ValidationResult()

        try:
            with open(stl_file, 'r') as f:
                content = f.read()

            # Check for required keywords
            if 'solid' not in content:
                result.add_error(f"Missing 'solid' keyword in ASCII STL: {stl_file.name}")

            if 'endsolid' not in content:
                result.add_error(f"Missing 'endsolid' keyword in ASCII STL: {stl_file.name}")

            # Count facets
            facet_count = content.count('facet normal')
            if facet_count == 0:
                result.add_error(f"No facets found in ASCII STL: {stl_file.name}")
            elif facet_count < 10:
                result.add_warning(f"Very few facets ({facet_count}) in {stl_file.name}")

            # Check endfacet count matches
            endfacet_count = content.count('endfacet')
            if facet_count != endfacet_count:
                result.add_error(f"Mismatched facet/endfacet count in {stl_file.name}: "
                               f"{facet_count} facets vs {endfacet_count} endfacets")

        except UnicodeDecodeError:
            result.add_error(f"File appears to be binary, not ASCII: {stl_file.name}")
        except Exception as e:
            result.add_error(f"Error validating ASCII STL {stl_file.name}: {str(e)}")

        return result

    def _validate_binary_stl(self, stl_file: Path) -> ValidationResult:
        """Validate binary STL format."""
        result = ValidationResult()

        try:
            with open(stl_file, 'rb') as f:
                # Read header (80 bytes)
                header = f.read(80)

                # Read number of triangles (4 bytes, unsigned int)
                num_triangles_bytes = f.read(4)
                if len(num_triangles_bytes) != 4:
                    result.add_error(f"Corrupted STL header in {stl_file.name}")
                    return result

                num_triangles = struct.unpack('<I', num_triangles_bytes)[0]

                if num_triangles == 0:
                    result.add_error(f"Zero triangles in binary STL: {stl_file.name}")
                    return result

                if num_triangles < 10:
                    result.add_warning(f"Very few triangles ({num_triangles}) in {stl_file.name}")

                # Check file size matches expected size
                # Header (80) + count (4) + triangles (50 bytes each)
                expected_size = 80 + 4 + (num_triangles * 50)
                actual_size = stl_file.stat().st_size

                if actual_size != expected_size:
                    result.add_error(f"File size mismatch in {stl_file.name}: "
                                   f"expected {expected_size} bytes, got {actual_size} bytes")

        except Exception as e:
            result.add_error(f"Error validating binary STL {stl_file.name}: {str(e)}")

        return result

    def validate_patch_configuration(self, stl_files: List[Path]) -> ValidationResult:
        """
        Validate patch configuration and naming.

        Args:
            stl_files: List of STL file paths

        Returns:
            ValidationResult with patch configuration status
        """
        result = ValidationResult()

        # Extract patch names from filenames
        patch_names = [f.stem for f in stl_files]

        # Check for required patches
        has_inlet = any('inlet' in name.lower() for name in patch_names)
        has_outlet = any('outlet' in name.lower() for name in patch_names)
        has_wall = any('wall' in name.lower() or 'aorta' in name.lower() for name in patch_names)

        if not has_inlet:
            result.add_error("No inlet patch found. Expected file like 'inlet.stl'")

        if not has_outlet:
            result.add_error("No outlet patches found. Expected files like 'outlet1.stl'")

        if not has_wall:
            result.add_warning("No wall patch found. Expected file like 'wall_aorta.stl'")

        # Check for duplicate patch names
        if len(patch_names) != len(set(patch_names)):
            duplicates = [name for name in patch_names if patch_names.count(name) > 1]
            result.add_error(f"Duplicate patch names found: {set(duplicates)}")

        return result

    def check_minimum_surface_area(self, stl_file: Path, patch_type: str = "unknown") -> ValidationResult:
        """
        Check if patch has minimum required surface area.

        Args:
            stl_file: Path to STL file
            patch_type: Type of patch (inlet, outlet, wall)

        Returns:
            ValidationResult with area validation status
        """
        result = ValidationResult()

        try:
            # Parse STL and calculate area
            area = self._calculate_stl_area(stl_file)

            # Determine minimum area based on patch type
            patch_type_lower = patch_type.lower()
            if 'inlet' in patch_type_lower:
                min_area = self.MIN_AREA_INLET
            elif 'outlet' in patch_type_lower:
                min_area = self.MIN_AREA_OUTLET
            elif 'wall' in patch_type_lower:
                min_area = self.MIN_AREA_WALL
            else:
                min_area = self.MIN_AREA_OUTLET  # Default to outlet minimum

            if area < min_area:
                result.add_warning(f"Surface area of {stl_file.name} ({area:.2e} m²) "
                                 f"is below minimum ({min_area:.2e} m²)")

            # Log area for reference
            self.logger.debug(f"Surface area of {stl_file.name}: {area:.6e} m²")

        except Exception as e:
            result.add_error(f"Error calculating surface area for {stl_file.name}: {str(e)}")

        return result

    def _calculate_stl_area(self, stl_file: Path) -> float:
        """
        Calculate total surface area of STL file.

        Args:
            stl_file: Path to STL file

        Returns:
            Total surface area in m² (considering scale_factor)
        """
        total_area = 0.0

        # Try binary format first
        try:
            with open(stl_file, 'rb') as f:
                header = f.read(6)
                f.seek(0)

                if header.startswith(b'solid '):
                    # ASCII format
                    total_area = self._calculate_ascii_stl_area(f)
                else:
                    # Binary format
                    total_area = self._calculate_binary_stl_area(f)

        except Exception as e:
            self.logger.error(f"Error reading STL file {stl_file}: {e}")
            return 0.0

        # Apply scale factor (area scales as length²)
        return total_area * (self.scale_factor ** 2)

    def _calculate_binary_stl_area(self, file_handle) -> float:
        """Calculate area from binary STL file."""
        # Skip header
        file_handle.seek(80)

        # Read number of triangles
        num_triangles = struct.unpack('<I', file_handle.read(4))[0]

        total_area = 0.0
        for _ in range(num_triangles):
            # Read normal (3 floats, not used for area calculation)
            file_handle.read(12)

            # Read 3 vertices (9 floats)
            v1 = struct.unpack('<fff', file_handle.read(12))
            v2 = struct.unpack('<fff', file_handle.read(12))
            v3 = struct.unpack('<fff', file_handle.read(12))

            # Skip attribute byte count
            file_handle.read(2)

            # Calculate triangle area using cross product
            # Area = 0.5 * ||(v2-v1) × (v3-v1)||
            edge1 = [v2[i] - v1[i] for i in range(3)]
            edge2 = [v3[i] - v1[i] for i in range(3)]

            cross = [
                edge1[1] * edge2[2] - edge1[2] * edge2[1],
                edge1[2] * edge2[0] - edge1[0] * edge2[2],
                edge1[0] * edge2[1] - edge1[1] * edge2[0]
            ]

            area = 0.5 * (cross[0]**2 + cross[1]**2 + cross[2]**2)**0.5
            total_area += area

        return total_area

    def _calculate_ascii_stl_area(self, file_handle) -> float:
        """Calculate area from ASCII STL file."""
        file_handle.seek(0)
        content = file_handle.read().decode('utf-8', errors='ignore')

        total_area = 0.0
        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line.startswith('facet normal'):
                # Read next lines for vertices
                vertices = []
                for j in range(i + 1, min(i + 6, len(lines))):
                    if 'vertex' in lines[j]:
                        parts = lines[j].strip().split()
                        if len(parts) == 4:  # 'vertex x y z'
                            vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])

                if len(vertices) == 3:
                    # Calculate triangle area
                    v1, v2, v3 = vertices
                    edge1 = [v2[k] - v1[k] for k in range(3)]
                    edge2 = [v3[k] - v1[k] for k in range(3)]

                    cross = [
                        edge1[1] * edge2[2] - edge1[2] * edge2[1],
                        edge1[2] * edge2[0] - edge1[0] * edge2[2],
                        edge1[0] * edge2[1] - edge1[1] * edge2[0]
                    ]

                    area = 0.5 * (cross[0]**2 + cross[1]**2 + cross[2]**2)**0.5
                    total_area += area

                i += 7  # Skip to next facet
            else:
                i += 1

        return total_area

    def verify_inlet_outlet_orientation(self, inlet_file: Path, outlet_files: List[Path]) -> ValidationResult:
        """
        Verify that inlet and outlets have consistent flow direction.

        This is a simplified check - full verification would require
        computing patch normals and checking orientation.

        Args:
            inlet_file: Path to inlet STL
            outlet_files: List of outlet STL paths

        Returns:
            ValidationResult with orientation status
        """
        result = ValidationResult()

        # Basic check: verify files exist and have reasonable size
        if not inlet_file.exists():
            result.add_error(f"Inlet file not found: {inlet_file}")
            return result

        inlet_area = self._calculate_stl_area(inlet_file)
        outlet_total_area = sum(self._calculate_stl_area(f) for f in outlet_files if f.exists())

        # Sanity check: total outlet area should be reasonable compared to inlet
        # (For aorta, outlets are typically smaller due to branching)
        if outlet_total_area > inlet_area * 2:
            result.add_warning(
                f"Total outlet area ({outlet_total_area:.2e} m²) is much larger than "
                f"inlet area ({inlet_area:.2e} m²). Check geometry scaling."
            )

        if outlet_total_area < inlet_area * 0.1:
            result.add_warning(
                f"Total outlet area ({outlet_total_area:.2e} m²) is very small compared to "
                f"inlet area ({inlet_area:.2e} m²). Verify outlet patches are complete."
            )

        return result


class MeshQualityChecker:
    """
    Validates mesh quality by parsing OpenFOAM checkMesh output.

    Checks:
    - Non-orthogonality
    - Skewness
    - Aspect ratio
    - Boundary layer coverage
    """

    # Quality thresholds (OpenFOAM recommended values)
    ORTHOGONALITY_WARNING = 70  # Degrees
    ORTHOGONALITY_ERROR = 75    # Degrees
    SKEWNESS_WARNING = 4        # Dimensionless
    SKEWNESS_ERROR = 8          # Dimensionless
    ASPECT_RATIO_WARNING = 100  # Dimensionless
    ASPECT_RATIO_ERROR = 1000   # Dimensionless

    def __init__(self, case_directory: str):
        """
        Initialize mesh quality checker.

        Args:
            case_directory: Path to OpenFOAM case directory
        """
        self.case_directory = Path(case_directory)
        self.logger = logger

    def validate_mesh_quality(self, log_file: Optional[str] = None) -> ValidationResult:
        """
        Validate mesh quality from checkMesh output.

        Args:
            log_file: Path to checkMesh log file (default: case_dir/log.checkMesh)

        Returns:
            ValidationResult with mesh quality status
        """
        result = ValidationResult()

        if log_file is None:
            log_file = self.case_directory / "log.checkMesh"
        else:
            log_file = Path(log_file)

        if not log_file.exists():
            result.add_error(f"checkMesh log file not found: {log_file}")
            return result

        try:
            with open(log_file, 'r') as f:
                content = f.read()

            # Parse mesh quality metrics
            metrics = self._parse_checkmesh_output(content)

            # Check orthogonality
            ortho_result = self.check_orthogonality(metrics)
            result.errors.extend(ortho_result.errors)
            result.warnings.extend(ortho_result.warnings)
            if not ortho_result.is_valid:
                result.is_valid = False

            # Check skewness
            skew_result = self.check_skewness(metrics)
            result.errors.extend(skew_result.errors)
            result.warnings.extend(skew_result.warnings)
            if not skew_result.is_valid:
                result.is_valid = False

            # Check aspect ratio
            aspect_result = self.check_aspect_ratio(metrics)
            result.errors.extend(aspect_result.errors)
            result.warnings.extend(aspect_result.warnings)
            if not aspect_result.is_valid:
                result.is_valid = False

            # Check for failed mesh
            if "Failed" in content or "FAILED" in content:
                result.add_error("checkMesh reported mesh failures. See log for details.")

        except Exception as e:
            result.add_error(f"Error parsing checkMesh output: {str(e)}")

        return result

    def _parse_checkmesh_output(self, content: str) -> Dict[str, float]:
        """
        Parse checkMesh output to extract quality metrics.

        Args:
            content: checkMesh log file content

        Returns:
            Dictionary of mesh quality metrics
        """
        import re

        metrics = {}

        # Parse max non-orthogonality
        ortho_match = re.search(r'Max non-orthogonality = ([\d.]+)', content)
        if ortho_match:
            metrics['max_non_orthogonality'] = float(ortho_match.group(1))

        # Parse max skewness
        skew_match = re.search(r'Max skewness = ([\d.]+)', content)
        if skew_match:
            metrics['max_skewness'] = float(skew_match.group(1))

        # Parse max aspect ratio
        aspect_match = re.search(r'Max aspect ratio = ([\d.]+)', content)
        if aspect_match:
            metrics['max_aspect_ratio'] = float(aspect_match.group(1))

        # Parse number of cells
        cells_match = re.search(r'cells:\s+(\d+)', content)
        if cells_match:
            metrics['num_cells'] = int(cells_match.group(1))

        # Parse number of faces
        faces_match = re.search(r'faces:\s+(\d+)', content)
        if faces_match:
            metrics['num_faces'] = int(faces_match.group(1))

        # Parse number of points
        points_match = re.search(r'points:\s+(\d+)', content)
        if points_match:
            metrics['num_points'] = int(points_match.group(1))

        return metrics

    def check_orthogonality(self, metrics: Dict[str, float]) -> ValidationResult:
        """
        Check mesh non-orthogonality.

        Args:
            metrics: Dictionary of mesh metrics

        Returns:
            ValidationResult with orthogonality status
        """
        result = ValidationResult()

        if 'max_non_orthogonality' not in metrics:
            result.add_warning("Non-orthogonality metric not found in checkMesh output")
            return result

        max_ortho = metrics['max_non_orthogonality']

        if max_ortho > self.ORTHOGONALITY_ERROR:
            result.add_error(
                f"Max non-orthogonality ({max_ortho:.1f}°) exceeds error threshold ({self.ORTHOGONALITY_ERROR}°). "
                f"Mesh quality is poor. Consider refining mesh or adjusting snappyHexMesh parameters."
            )
        elif max_ortho > self.ORTHOGONALITY_WARNING:
            result.add_warning(
                f"Max non-orthogonality ({max_ortho:.1f}°) exceeds warning threshold ({self.ORTHOGONALITY_WARNING}°). "
                f"Consider mesh refinement for better quality."
            )
        else:
            self.logger.debug(f"Non-orthogonality OK: {max_ortho:.1f}°")

        return result

    def check_skewness(self, metrics: Dict[str, float]) -> ValidationResult:
        """
        Check mesh skewness.

        Args:
            metrics: Dictionary of mesh metrics

        Returns:
            ValidationResult with skewness status
        """
        result = ValidationResult()

        if 'max_skewness' not in metrics:
            result.add_warning("Skewness metric not found in checkMesh output")
            return result

        max_skew = metrics['max_skewness']

        if max_skew > self.SKEWNESS_ERROR:
            result.add_error(
                f"Max skewness ({max_skew:.2f}) exceeds error threshold ({self.SKEWNESS_ERROR}). "
                f"Mesh has highly skewed cells. Refine mesh or check geometry."
            )
        elif max_skew > self.SKEWNESS_WARNING:
            result.add_warning(
                f"Max skewness ({max_skew:.2f}) exceeds warning threshold ({self.SKEWNESS_WARNING}). "
                f"Some cells are skewed. May affect solution accuracy."
            )
        else:
            self.logger.debug(f"Skewness OK: {max_skew:.2f}")

        return result

    def check_aspect_ratio(self, metrics: Dict[str, float]) -> ValidationResult:
        """
        Check mesh aspect ratio.

        Args:
            metrics: Dictionary of mesh metrics

        Returns:
            ValidationResult with aspect ratio status
        """
        result = ValidationResult()

        if 'max_aspect_ratio' not in metrics:
            result.add_warning("Aspect ratio metric not found in checkMesh output")
            return result

        max_aspect = metrics['max_aspect_ratio']

        if max_aspect > self.ASPECT_RATIO_ERROR:
            result.add_error(
                f"Max aspect ratio ({max_aspect:.1f}) exceeds error threshold ({self.ASPECT_RATIO_ERROR}). "
                f"Mesh has very elongated cells. Check boundary layer settings or refine mesh."
            )
        elif max_aspect > self.ASPECT_RATIO_WARNING:
            result.add_warning(
                f"Max aspect ratio ({max_aspect:.1f}) exceeds warning threshold ({self.ASPECT_RATIO_WARNING}). "
                f"Some cells are elongated. This may be acceptable in boundary layers."
            )
        else:
            self.logger.debug(f"Aspect ratio OK: {max_aspect:.1f}")

        return result

    def validate_boundary_layer_coverage(self, log_file: Optional[str] = None) -> ValidationResult:
        """
        Check boundary layer mesh coverage.

        Args:
            log_file: Path to checkMesh log file

        Returns:
            ValidationResult with boundary layer status
        """
        result = ValidationResult()

        if log_file is None:
            log_file = self.case_directory / "log.checkMesh"
        else:
            log_file = Path(log_file)

        if not log_file.exists():
            result.add_warning(f"checkMesh log not found: {log_file}")
            return result

        try:
            with open(log_file, 'r') as f:
                content = f.read()

            # Check for boundary layer info in log
            if "layer" in content.lower():
                # Look for layer thickness info
                import re
                layer_match = re.search(r'layer.*thickness', content, re.IGNORECASE)
                if layer_match:
                    self.logger.info("Boundary layers detected in mesh")
                else:
                    result.add_warning("Boundary layer information ambiguous in checkMesh output")
            else:
                result.add_warning("No boundary layer information found. Check addLayers settings.")

        except Exception as e:
            result.add_warning(f"Could not check boundary layer coverage: {str(e)}")

        return result


class BoundaryConditionValidator:
    """
    Validates boundary condition configurations and data files.

    Checks:
    - Flow data CSV files (format, columns, time range, data quality)
    - Boundary condition consistency with geometry
    - Windkessel parameter validity
    - Time-varying data continuity
    """

    # Valid inlet types
    VALID_INLET_TYPES = ['TIMEVARYING', 'CONSTANT', 'WOMERSLEY']

    # Valid outlet types
    VALID_OUTLET_TYPES = ['ZEROGRADIENT', 'FIXEDVALUE', '3EWINDKESSEL', 'RCRLUMPED']

    # Valid data types for inlet (normalized to lowercase)
    VALID_DATA_TYPES = ['velocity', 'flowrate', 'pressure']

    @staticmethod
    def normalize_data_type(data_type):
        """
        Normalize data type to lowercase standard format.

        Accepts: flowRate, flowrate, FLOWRATE, flow_rate, velocity, Velocity, etc.
        Returns: 'flowrate', 'velocity', or 'pressure'
        """
        if not data_type:
            return None

        normalized = str(data_type).lower().strip()

        # Handle common variations
        if normalized in ['flowrate', 'flow_rate', 'flow', 'q']:
            return 'flowrate'
        elif normalized in ['velocity', 'vel', 'u', 'v']:
            return 'velocity'
        elif normalized in ['pressure', 'p', 'press']:
            return 'pressure'
        else:
            # Return as-is if not recognized
            return normalized

    # Valid profiles
    VALID_PROFILES = ['plug', 'parabolic', 'womersley', 'wall_distance', 'elliptical']

    # Type-profile compatibility rules (strict enforcement)
    TYPE_PROFILE_RULES = {
        'TIMEVARYING': ['plug', 'parabolic', 'womersley', 'wall_distance', 'elliptical'],
        'CONSTANT': ['plug', 'parabolic', 'wall_distance', 'elliptical'],
        'WOMERSLEY': ['womersley']                          # Must use womersley profile
    }

    # Required parameters per type
    REQUIRED_PARAMS = {
        'TIMEVARYING': ['csv_file', 'data_type', 'profile'],
        'CONSTANT': ['profile'],  # velocity OR flowrate OR cardiac_output (checked separately)
        'WOMERSLEY': ['csv_file', 'data_type', 'profile']
    }

    # Minimum requirements
    MIN_TIME_POINTS = 10  # Minimum data points in CSV
    MIN_CARDIAC_CYCLE_TIME = 0.3  # Minimum cycle time (s) - very fast heart rate ~200 bpm
    MAX_CARDIAC_CYCLE_TIME = 2.0  # Maximum cycle time (s) - slow heart rate ~30 bpm

    # Womersley number thresholds for profile recommendations
    WOMERSLEY_ALPHA_LOW = 1.0   # Below this: parabolic acceptable
    WOMERSLEY_ALPHA_MID = 10.0  # Above this: near-plug (typical proximal aorta)

    # Windkessel parameter ranges (physiological)
    WINDKESSEL_RANGES = {
        'systolic_pressure': (80, 200),    # mmHg
        'diastolic_pressure': (40, 120),   # mmHg
        'C_compliance': (1e-10, 1e-7),     # m³/Pa
        'R_proximal': (1e5, 1e9),          # Pa·s/m³
        'R_distal': (1e6, 1e10)            # Pa·s/m³
    }

    def __init__(self, config: dict, case_directory: str = None):
        """
        Initialize the boundary condition validator.

        Args:
            config: Configuration dictionary
            case_directory: Path to case directory
        """
        self.config = config
        self.case_directory = Path(case_directory) if case_directory else None
        self.logger = Logger("BoundaryConditionValidator").get_logger()

    def validate_all(self) -> ValidationResult:
        """
        Run all boundary condition validation checks.

        Supports both nested (boundary_conditions.inlet) and flattened (inlet) formats.

        Returns:
            ValidationResult with overall BC validation status
        """
        result = ValidationResult()

        # Support both nested and flattened config structures
        # After ConfigBuilder merge, BCs may be at root level
        if 'boundary_conditions' in self.config:
            bc_config = self.config['boundary_conditions']
        elif 'inlet' in self.config or 'outlets' in self.config:
            # Flattened structure - BCs at root level
            bc_config = self.config
        else:
            result.add_error("No boundary condition configuration found (expected 'boundary_conditions' or 'inlet'/'outlets' at root)")
            return result

        # Validate inlet configuration
        if 'inlet' in bc_config:
            inlet_result = self.validate_inlet_configuration(bc_config['inlet'])
            result.errors.extend(inlet_result.errors)
            result.warnings.extend(inlet_result.warnings)
            if not inlet_result.is_valid:
                result.is_valid = False
        else:
            result.add_error("No inlet boundary condition specified")

        # Validate outlet configuration
        if 'outlets' in bc_config:
            outlet_result = self.validate_outlet_configuration(bc_config['outlets'])
            result.errors.extend(outlet_result.errors)
            result.warnings.extend(outlet_result.warnings)
            if not outlet_result.is_valid:
                result.is_valid = False
        else:
            result.add_error("No outlet boundary condition specified")

        # Validate consistency between inlet and outlets
        if 'inlet' in bc_config and 'outlets' in bc_config:
            consistency_result = self.validate_bc_consistency(bc_config['inlet'], bc_config['outlets'])
            result.errors.extend(consistency_result.errors)
            result.warnings.extend(consistency_result.warnings)
            if not consistency_result.is_valid:
                result.is_valid = False

        return result

    def validate_inlet_configuration(self, inlet_config: dict) -> ValidationResult:
        """
        Validate inlet boundary condition configuration with strict type-profile rules.

        Args:
            inlet_config: Inlet configuration dictionary

        Returns:
            ValidationResult with inlet validation status
        """
        result = ValidationResult()

        # Check inlet type
        inlet_type = inlet_config.get('type', '').upper()
        if not inlet_type:
            result.add_error("Inlet type not specified")
            return result

        if inlet_type not in self.VALID_INLET_TYPES:
            result.add_error(
                f"Invalid inlet type '{inlet_type}'. Valid types: {', '.join(self.VALID_INLET_TYPES)}"
            )
            return result

        # Check required parameters for this type
        required = self.REQUIRED_PARAMS.get(inlet_type, [])
        for param in required:
            if param not in inlet_config:
                result.add_error(f"Inlet type '{inlet_type}' requires parameter '{param}'")

        # Validate profile compatibility with type
        profile = inlet_config.get('profile', '').lower()
        if profile:
            if profile not in self.VALID_PROFILES:
                result.add_error(
                    f"Invalid profile '{profile}'. Valid profiles: {', '.join(self.VALID_PROFILES)}"
                )
            else:
                # Strict type-profile compatibility check
                allowed_profiles = self.TYPE_PROFILE_RULES.get(inlet_type, [])
                if profile not in allowed_profiles:
                    result.add_error(
                        f"Profile '{profile}' incompatible with inlet type '{inlet_type}'. "
                        f"Allowed profiles for {inlet_type}: {', '.join(allowed_profiles)}"
                    )

        # Validate data_type (normalize to handle flowRate, flow_rate, etc.)
        data_type_raw = inlet_config.get('data_type', '')
        data_type = self.normalize_data_type(data_type_raw) if data_type_raw else ''
        if data_type and data_type not in self.VALID_DATA_TYPES:
            result.add_error(
                f"Invalid data_type '{data_type_raw}' (normalized: '{data_type}'). "
                f"Valid types: {', '.join(self.VALID_DATA_TYPES)} (case-insensitive)"
            )

        # Type-specific validation
        if inlet_type in ['TIMEVARYING', 'WOMERSLEY']:
            csv_file = inlet_config.get('csv_file')
            if csv_file:
                csv_result = self.validate_flow_data_csv(csv_file)
                result.errors.extend(csv_result.errors)
                result.warnings.extend(csv_result.warnings)
                if not csv_result.is_valid:
                    result.is_valid = False

        if inlet_type == 'CONSTANT':
            # Check for either velocity, flowrate, or cardiac_output parameter
            has_velocity = 'velocity' in inlet_config
            has_flowrate = 'flowrate' in inlet_config
            has_cardiac_output = 'cardiac_output' in inlet_config

            # Allow flowrate as alias for cardiac_output
            if has_flowrate and not has_cardiac_output:
                inlet_config['cardiac_output'] = inlet_config['flowrate']
                has_cardiac_output = True

            if not has_velocity and not has_cardiac_output:
                result.add_error(
                    f"Inlet type '{inlet_type}' requires either 'velocity' (m/s), 'flowrate' (L/min), or 'cardiac_output' (L/min) parameter"
                )
            elif has_velocity and has_cardiac_output:
                result.add_warning(
                    "Both 'velocity' and 'cardiac_output' specified. Using 'cardiac_output' and ignoring 'velocity'."
                )
                cardiac_output = inlet_config['cardiac_output']
                if not isinstance(cardiac_output, (int, float)) or cardiac_output <= 0:
                    result.add_error(f"Cardiac output must be a positive number, got: {cardiac_output}")
                elif cardiac_output < 2.0 or cardiac_output > 30.0:
                    result.add_warning(
                        f"Cardiac output {cardiac_output:.1f} L/min is outside typical range (3-25 L/min). "
                        "Typical resting: 4.5-5.5 L/min, exercise: 10-25 L/min."
                    )
            elif has_velocity:
                velocity = inlet_config['velocity']
                if not isinstance(velocity, (int, float)) or velocity <= 0:
                    result.add_error(f"Velocity must be a positive number, got: {velocity}")
            elif has_cardiac_output:
                cardiac_output = inlet_config['cardiac_output']
                if not isinstance(cardiac_output, (int, float)) or cardiac_output <= 0:
                    result.add_error(f"Cardiac output must be a positive number, got: {cardiac_output}")
                elif cardiac_output < 2.0 or cardiac_output > 30.0:
                    result.add_warning(
                        f"Cardiac output {cardiac_output:.1f} L/min is outside typical range (3-25 L/min). "
                        "Typical resting: 4.5-5.5 L/min, exercise: 10-25 L/min."
                    )

        # Check for physics.nu if womersley profile is used
        if profile == 'womersley' or inlet_type == 'WOMERSLEY':
            physics = self.config.get('physics', {})
            if 'nu' not in physics:
                result.add_error(
                    "Womersley profile requires 'physics.nu' (kinematic viscosity) in configuration"
                )
            elif physics['nu'] <= 0:
                result.add_error(f"physics.nu must be positive, got: {physics['nu']}")

        # Validate optional period parameter
        if 'period' in inlet_config:
            period = inlet_config['period']
            if not isinstance(period, (int, float)) or period <= 0:
                result.add_error(f"Period must be a positive number, got: {period}")
            elif period < self.MIN_CARDIAC_CYCLE_TIME or period > self.MAX_CARDIAC_CYCLE_TIME:
                result.add_warning(
                    f"Period {period:.3f}s outside typical cardiac range "
                    f"({self.MIN_CARDIAC_CYCLE_TIME}-{self.MAX_CARDIAC_CYCLE_TIME}s)"
                )

        return result

    def validate_outlet_configuration(self, outlet_config: dict) -> ValidationResult:
        """
        Validate outlet boundary condition configuration.

        Args:
            outlet_config: Outlet configuration dictionary

        Returns:
            ValidationResult with outlet validation status
        """
        result = ValidationResult()

        # Check outlet type
        outlet_type = outlet_config.get('type', '').upper()
        if not outlet_type:
            result.add_error("Outlet type not specified")
            return result

        if outlet_type not in self.VALID_OUTLET_TYPES:
            result.add_error(
                f"Invalid outlet type '{outlet_type}'. Valid types: {', '.join(self.VALID_OUTLET_TYPES)}"
            )
            return result

        # For Windkessel, validate parameters
        if '3EWINDKESSEL' in outlet_type or 'WINDKESSEL' in outlet_type:
            wk_result = self.validate_windkessel_parameters(outlet_config)
            result.errors.extend(wk_result.errors)
            result.warnings.extend(wk_result.warnings)
            if not wk_result.is_valid:
                result.is_valid = False

        return result

    def validate_flow_data_csv(self, csv_file: str) -> ValidationResult:
        """
        Validate flow data CSV file format and content.

        Args:
            csv_file: Path to CSV file (relative or absolute)

        Returns:
            ValidationResult with CSV validation status
        """
        result = ValidationResult()

        # Resolve file path - check multiple possible locations
        if self.case_directory:
            # Try case root first
            csv_path = self.case_directory / csv_file

            # If not found, try constant/boundaryData/inlet/
            if not csv_path.exists():
                # Get inlet patch name from config
                inlet_patch = self.config.get('geometry', {}).get('inlet_keywords_ordered', 'inlet')
                csv_path_boundary = self.case_directory / "constant" / "boundaryData" / inlet_patch / csv_file
                if csv_path_boundary.exists():
                    csv_path = csv_path_boundary
        else:
            csv_path = Path(csv_file)

        # Check file exists
        if not csv_path.exists():
            result.add_error(f"Flow data CSV file not found: {csv_path}")
            return result

        try:
            import pandas as pd

            # Read CSV file
            df = pd.read_csv(csv_path)

            # Normalize column names to lowercase for case-insensitive matching
            # Create mapping: original_name -> lowercase_name
            column_name_map = {col: col.lower().strip() for col in df.columns}
            lowercase_columns = list(column_name_map.values())

            # Check required 'time' column (case-insensitive)
            time_column = None
            for orig_col, lower_col in column_name_map.items():
                if lower_col == 'time':
                    time_column = orig_col
                    break

            if time_column is None:
                result.add_error(
                    f"CSV file missing required 'time' column. "
                    f"Found columns: {list(df.columns)}"
                )
                return result

            # Check for at least one data column (velocity, flowrate, or pressure)
            # Normalize column names to handle flowRate, flow_rate, Time, TIME, etc.
            normalized_columns = {col: self.normalize_data_type(col) for col in df.columns}
            data_columns = [col for col, norm in normalized_columns.items()
                          if norm and norm in self.VALID_DATA_TYPES]
            if not data_columns:
                result.add_error(
                    f"CSV file missing data column. Expected one of: {', '.join(self.VALID_DATA_TYPES)} "
                    f"(case-insensitive, accepts flowRate/flow_rate)"
                )
                return result

            # Validate minimum number of points
            if len(df) < self.MIN_TIME_POINTS:
                result.add_error(
                    f"Insufficient data points in CSV: {len(df)} (minimum: {self.MIN_TIME_POINTS})"
                )

            # Validate time column (use discovered column name for case-insensitivity)
            time_result = self._validate_time_column(df[time_column])
            result.errors.extend(time_result.errors)
            result.warnings.extend(time_result.warnings)
            if not time_result.is_valid:
                result.is_valid = False

            # Validate data columns
            for col in data_columns:
                data_result = self._validate_data_column(df[col], col)
                result.errors.extend(data_result.errors)
                result.warnings.extend(data_result.warnings)
                if not data_result.is_valid:
                    result.is_valid = False

        except Exception as e:
            result.add_error(f"Error reading CSV file: {str(e)}")

        return result

    def _validate_time_column(self, time_series) -> ValidationResult:
        """Validate time column data."""
        result = ValidationResult()

        # Check for non-numeric values
        if not all(isinstance(t, (int, float)) for t in time_series):
            result.add_error("Time column contains non-numeric values")
            return result

        # Check time starts at or near zero
        if time_series.iloc[0] > 0.1:
            result.add_warning(
                f"Time series starts at {time_series.iloc[0]:.3f}s (expected to start near 0)"
            )

        # Check time is monotonically increasing
        if not time_series.is_monotonic_increasing:
            result.add_error("Time values must be monotonically increasing")

        # Check for duplicate time values
        if time_series.duplicated().any():
            result.add_error("Time column contains duplicate values")

        # Check cardiac cycle duration
        cycle_duration = time_series.iloc[-1] - time_series.iloc[0]
        if cycle_duration < self.MIN_CARDIAC_CYCLE_TIME:
            result.add_error(
                f"Cardiac cycle duration ({cycle_duration:.3f}s) is too short. "
                f"Minimum: {self.MIN_CARDIAC_CYCLE_TIME}s (heart rate would be >200 bpm)"
            )
        elif cycle_duration > self.MAX_CARDIAC_CYCLE_TIME:
            result.add_warning(
                f"Cardiac cycle duration ({cycle_duration:.3f}s) is unusually long. "
                f"Maximum recommended: {self.MAX_CARDIAC_CYCLE_TIME}s (heart rate ~30 bpm)"
            )

        # Check time step uniformity
        time_diffs = time_series.diff().dropna()
        if time_diffs.std() / time_diffs.mean() > 0.1:  # >10% variation
            result.add_warning("Time steps are not uniform. Consider using uniform time spacing.")

        return result

    def _validate_data_column(self, data_series, column_name: str) -> ValidationResult:
        """Validate data column (velocity, flowrate, pressure)."""
        result = ValidationResult()

        # Check for non-numeric values
        if not all(isinstance(v, (int, float)) for v in data_series):
            result.add_error(f"{column_name} column contains non-numeric values")
            return result

        # Check for NaN or inf values
        if data_series.isna().any():
            result.add_error(f"{column_name} column contains NaN values")

        import numpy as np
        if np.isinf(data_series).any():
            result.add_error(f"{column_name} column contains infinite values")

        # Check for negative values (only for velocity/flowrate)
        if column_name.lower() in ['velocity', 'flowrate']:
            if (data_series < 0).any():
                result.add_warning(
                    f"{column_name} contains negative values. Ensure this is intentional (backflow)."
                )

        # Check for unrealistic values
        if column_name.lower() == 'velocity':
            max_val = data_series.max()
            if max_val > 5.0:  # >5 m/s is unusual in aorta
                result.add_warning(
                    f"Peak velocity ({max_val:.2f} m/s) is unusually high. "
                    f"Expected range: 0.5-2.5 m/s for aorta"
                )
            elif max_val < 0.1:  # <0.1 m/s is very low
                result.add_warning(
                    f"Peak velocity ({max_val:.2f} m/s) is unusually low. "
                    f"Check units (should be m/s, not mm/s)"
                )

        # Check data starts and ends at similar values (for cyclic flow)
        start_val = data_series.iloc[0]
        end_val = data_series.iloc[-1]
        if abs(end_val - start_val) > 0.1 * data_series.max():
            result.add_warning(
                f"{column_name} starts at {start_val:.3f} but ends at {end_val:.3f}. "
                f"For cyclic flow, start and end values should be similar."
            )

        return result

    def validate_windkessel_parameters(self, outlet_config: dict) -> ValidationResult:
        """
        Validate Windkessel boundary condition parameters.

        Args:
            outlet_config: Outlet configuration dictionary

        Returns:
            ValidationResult with Windkessel validation status
        """
        result = ValidationResult()

        # Check for windkessel_settings
        if 'windkessel_settings' not in outlet_config:
            result.add_error("3-element Windkessel requires 'windkessel_settings' section")
            return result

        wk_settings = outlet_config['windkessel_settings']

        # Check methodology (optional - defaults are used if not specified)
        methodology = wk_settings.get('methodology', '').lower()
        valid_methodologies = ['murray_law_automatic', 'manual', 'literature_based']

        if methodology and methodology not in valid_methodologies:
            result.add_warning(
                f"Unknown methodology '{methodology}'. Expected: {', '.join(valid_methodologies)}"
            )

        # Validate pressure values (always required)
        systolic_p = wk_settings.get('systolic_pressure')
        diastolic_p = wk_settings.get('diastolic_pressure')

        if systolic_p is None:
            result.add_error("Windkessel settings missing 'systolic_pressure'")
        elif not isinstance(systolic_p, (int, float)):
            result.add_error(f"Invalid systolic_pressure: {systolic_p} (must be numeric)")
        else:
            min_p, max_p = self.WINDKESSEL_RANGES['systolic_pressure']
            if not (min_p <= systolic_p <= max_p):
                result.add_warning(
                    f"Systolic pressure ({systolic_p} mmHg) outside typical range: {min_p}-{max_p} mmHg"
                )

        if diastolic_p is None:
            result.add_error("Windkessel settings missing 'diastolic_pressure'")
        elif not isinstance(diastolic_p, (int, float)):
            result.add_error(f"Invalid diastolic_pressure: {diastolic_p} (must be numeric)")
        else:
            min_p, max_p = self.WINDKESSEL_RANGES['diastolic_pressure']
            if not (min_p <= diastolic_p <= max_p):
                result.add_warning(
                    f"Diastolic pressure ({diastolic_p} mmHg) outside typical range: {min_p}-{max_p} mmHg"
                )

        # Check pressure relationship
        if systolic_p and diastolic_p:
            if systolic_p <= diastolic_p:
                result.add_error(
                    f"Systolic pressure ({systolic_p}) must be greater than diastolic ({diastolic_p})"
                )

            pulse_pressure = systolic_p - diastolic_p
            if pulse_pressure < 20:
                result.add_warning(
                    f"Pulse pressure ({pulse_pressure} mmHg) is very low. Typical range: 30-50 mmHg"
                )
            elif pulse_pressure > 80:
                result.add_warning(
                    f"Pulse pressure ({pulse_pressure} mmHg) is very high. Typical range: 30-50 mmHg"
                )

        # Validate initial_pressure_method if specified
        init_method = wk_settings.get('initial_pressure_method', 'diastolic').lower()
        valid_methods = ['diastolic', 'systolic', 'map', 'zero']
        if init_method not in valid_methods:
            result.add_error(
                f"Invalid initial_pressure_method '{init_method}'. "
                f"Valid options: {', '.join(valid_methods)}"
            )

        # For manual methodology, validate C, R_proximal, R_distal
        if methodology == 'manual':
            for param in ['C_compliance', 'R_proximal', 'R_distal']:
                value = wk_settings.get(param)
                if value is None:
                    result.add_error(f"Manual Windkessel requires '{param}' parameter")
                elif not isinstance(value, (int, float)):
                    result.add_error(f"Invalid {param}: {value} (must be numeric)")
                elif value <= 0:
                    result.add_error(f"{param} must be positive (got {value})")
                elif param in self.WINDKESSEL_RANGES:
                    min_val, max_val = self.WINDKESSEL_RANGES[param]
                    if not (min_val <= value <= max_val):
                        result.add_warning(
                            f"{param} ({value:.2e}) outside typical range: {min_val:.2e}-{max_val:.2e}"
                        )

        return result

    def validate_bc_consistency(self, inlet_config: dict, outlet_config: dict) -> ValidationResult:
        """
        Validate consistency between inlet and outlet boundary conditions.

        Args:
            inlet_config: Inlet configuration
            outlet_config: Outlet configuration

        Returns:
            ValidationResult with consistency checks
        """
        result = ValidationResult()

        # Check for time-varying inlet with Windkessel outlets
        inlet_type = inlet_config.get('type', '').upper()
        outlet_type = outlet_config.get('type', '').upper()

        if inlet_type == 'TIMEVARYING' and 'WINDKESSEL' in outlet_type:
            # This is the most common and recommended combination
            self.logger.debug("Time-varying inlet with Windkessel outlets - recommended configuration")
        elif inlet_type == 'CONSTANT' and outlet_type == 'ZEROGRADIENT':
            result.add_warning(
                "Constant inlet with zero-gradient outlets may lead to stability issues. "
                "Consider using pressure outlets or Windkessel."
            )
        elif inlet_type == 'CONSTANT' and 'WINDKESSEL' in outlet_type:
            result.add_warning(
                "Constant inlet with 3-Element Windkessel outlets: at steady state (DC), "
                "the capacitor C is open-circuit and the model collapses to pure resistance R_total = R1 + R2. "
                "R1 (characteristic impedance) only matters for transients/waves. "
                "\n\n"
                "RECOMMENDED: Use simple resistance outlets for mean hemodynamics:\n"
                "  R_i = (MAP - P_v) / Q̄_i\n"
                "where MAP = DP + (SP-DP)/3, P_v ≈ 0-5 mmHg, Q̄_i from Murray's law (r³) or area split.\n"
                "This is exactly what RCR reduces to at steady state.\n"
                "\n"
                "Manual workarounds (not implemented): "
                "(1) implement fixed pressure BC at outlets near MAP, or "
                "(2) create synthetic sinusoidal CSV (60-70 bpm) to add mild pulsation."
            )

        return result
