"""
Unit tests for validation utilities.

Tests the GeometryValidator, MeshQualityChecker, and BoundaryConditionValidator classes.
"""

import pytest
import struct
from pathlib import Path
import tempfile

from src.aortacfd_lib.utils.validation import (
    ValidationResult,
    GeometryValidator,
    MeshQualityChecker,
    BoundaryConditionValidator
)


class TestValidationResult:
    """Tests for ValidationResult container."""

    def test_initialization_valid(self):
        """Test ValidationResult initializes as valid by default."""
        result = ValidationResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_initialization_invalid(self):
        """Test ValidationResult with errors."""
        result = ValidationResult(is_valid=False, errors=["Error 1"])
        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_add_error(self):
        """Test adding error marks result as invalid."""
        result = ValidationResult()
        result.add_error("Test error")

        assert result.is_valid is False
        assert "Test error" in result.errors

    def test_add_warning(self):
        """Test adding warning does not invalidate result."""
        result = ValidationResult()
        result.add_warning("Test warning")

        assert result.is_valid is True
        assert "Test warning" in result.warnings

    def test_bool_conversion(self):
        """Test ValidationResult converts to boolean."""
        valid_result = ValidationResult()
        invalid_result = ValidationResult(is_valid=False)

        assert bool(valid_result) is True
        assert bool(invalid_result) is False


class TestGeometryValidator:
    """Tests for GeometryValidator class."""

    def test_initialization(self, tmp_path):
        """Test GeometryValidator initialization."""
        validator = GeometryValidator(str(tmp_path), scale_factor=0.001)

        assert validator.case_directory == tmp_path
        assert validator.scale_factor == 0.001

    def test_validate_all_missing_directory(self):
        """Test validation with non-existent directory."""
        validator = GeometryValidator("/nonexistent/path")
        result = validator.validate_all()

        assert result.is_valid is False
        assert any("not found" in err.lower() for err in result.errors)

    def test_validate_all_no_stl_files(self, tmp_path):
        """Test validation with directory containing no STL files."""
        validator = GeometryValidator(str(tmp_path))
        result = validator.validate_all()

        assert result.is_valid is False
        assert any("no stl files" in err.lower() for err in result.errors)

    def test_check_stl_integrity_missing_file(self, tmp_path):
        """Test STL integrity check with missing file."""
        validator = GeometryValidator(str(tmp_path))
        stl_file = tmp_path / "nonexistent.stl"
        result = validator.check_stl_integrity(stl_file)

        assert result.is_valid is False
        assert any("not found" in err.lower() for err in result.errors)

    def test_check_stl_integrity_empty_file(self, tmp_path):
        """Test STL integrity check with empty file."""
        validator = GeometryValidator(str(tmp_path))
        stl_file = tmp_path / "empty.stl"
        stl_file.touch()

        result = validator.check_stl_integrity(stl_file)

        assert result.is_valid is False
        assert any("empty" in err.lower() for err in result.errors)

    def test_validate_binary_stl(self, tmp_path):
        """Test validation of binary STL file."""
        validator = GeometryValidator(str(tmp_path))
        stl_file = tmp_path / "test.stl"

        # Create a minimal valid binary STL
        with open(stl_file, 'wb') as f:
            # Header (80 bytes)
            f.write(b' ' * 80)

            # Number of triangles (1 triangle)
            f.write(struct.pack('<I', 1))

            # Triangle data (50 bytes: normal + 3 vertices + attribute)
            # Normal (3 floats)
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))

            # Vertex 1
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            # Vertex 2
            f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
            # Vertex 3
            f.write(struct.pack('<fff', 0.0, 1.0, 0.0))

            # Attribute byte count
            f.write(struct.pack('<H', 0))

        result = validator.check_stl_integrity(stl_file)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_ascii_stl(self, tmp_path):
        """Test validation of ASCII STL file."""
        validator = GeometryValidator(str(tmp_path))
        stl_file = tmp_path / "test_ascii.stl"

        # Create a minimal valid ASCII STL
        stl_content = """solid test
facet normal 0.0 0.0 1.0
  outer loop
    vertex 0.0 0.0 0.0
    vertex 1.0 0.0 0.0
    vertex 0.0 1.0 0.0
  endloop
endfacet
endsolid test
"""
        stl_file.write_text(stl_content)

        result = validator.check_stl_integrity(stl_file)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_ascii_stl_missing_keywords(self, tmp_path):
        """Test ASCII STL with missing required keywords."""
        validator = GeometryValidator(str(tmp_path))
        stl_file = tmp_path / "bad_ascii.stl"

        # Create invalid ASCII STL (missing endsolid)
        stl_content = """solid test
facet normal 0.0 0.0 1.0
  outer loop
    vertex 0.0 0.0 0.0
    vertex 1.0 0.0 0.0
    vertex 0.0 1.0 0.0
  endloop
endfacet
"""
        stl_file.write_text(stl_content)

        result = validator.check_stl_integrity(stl_file)

        assert result.is_valid is False
        assert any("endsolid" in err.lower() for err in result.errors)

    def test_validate_patch_configuration_complete(self, tmp_path):
        """Test patch configuration with all required patches."""
        validator = GeometryValidator(str(tmp_path))

        # Create dummy STL files with appropriate names
        inlet = tmp_path / "inlet.stl"
        outlet1 = tmp_path / "outlet1.stl"
        wall = tmp_path / "wall_aorta.stl"

        for f in [inlet, outlet1, wall]:
            f.touch()

        stl_files = [inlet, outlet1, wall]
        result = validator.validate_patch_configuration(stl_files)

        assert result.is_valid is True

    def test_validate_patch_configuration_missing_inlet(self, tmp_path):
        """Test patch configuration with missing inlet."""
        validator = GeometryValidator(str(tmp_path))

        outlet1 = tmp_path / "outlet1.stl"
        wall = tmp_path / "wall_aorta.stl"

        stl_files = [outlet1, wall]
        result = validator.validate_patch_configuration(stl_files)

        assert result.is_valid is False
        assert any("inlet" in err.lower() for err in result.errors)

    def test_validate_patch_configuration_missing_outlet(self, tmp_path):
        """Test patch configuration with missing outlet."""
        validator = GeometryValidator(str(tmp_path))

        inlet = tmp_path / "inlet.stl"
        wall = tmp_path / "wall_aorta.stl"

        stl_files = [inlet, wall]
        result = validator.validate_patch_configuration(stl_files)

        assert result.is_valid is False
        assert any("outlet" in err.lower() for err in result.errors)

    def test_validate_patch_configuration_duplicate_names(self, tmp_path):
        """Test patch configuration with duplicate patch names."""
        validator = GeometryValidator(str(tmp_path))

        # Create files with duplicate names in different subdirs
        inlet1 = tmp_path / "inlet.stl"
        inlet2 = tmp_path / "inlet.stl"  # Same name

        inlet1.touch()

        stl_files = [inlet1, inlet1]  # Duplicate in list
        result = validator.validate_patch_configuration(stl_files)

        assert result.is_valid is False
        assert any("duplicate" in err.lower() for err in result.errors)

    def test_calculate_stl_area_binary(self, tmp_path):
        """Test STL area calculation for binary file."""
        validator = GeometryValidator(str(tmp_path), scale_factor=1.0)
        stl_file = tmp_path / "triangle.stl"

        # Create binary STL with known area (triangle with base=1, height=1, area=0.5)
        with open(stl_file, 'wb') as f:
            f.write(b' ' * 80)
            f.write(struct.pack('<I', 1))

            # Normal
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))

            # Vertices forming right triangle
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 0.0, 1.0, 0.0))

            f.write(struct.pack('<H', 0))

        area = validator._calculate_stl_area(stl_file)

        # Area should be 0.5 (half of 1x1 square)
        assert 0.4 < area < 0.6  # Allow small floating point error

    def test_calculate_stl_area_with_scale_factor(self, tmp_path):
        """Test STL area calculation with scale factor."""
        validator = GeometryValidator(str(tmp_path), scale_factor=0.001)
        stl_file = tmp_path / "triangle.stl"

        # Create binary STL
        with open(stl_file, 'wb') as f:
            f.write(b' ' * 80)
            f.write(struct.pack('<I', 1))
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 0.0, 1.0, 0.0))
            f.write(struct.pack('<H', 0))

        area = validator._calculate_stl_area(stl_file)

        # Area should be scaled by scale_factor²
        # Original area ~0.5, scaled = 0.5 * (0.001)² = 0.5e-6
        assert 0.4e-6 < area < 0.6e-6

    def test_check_minimum_surface_area_inlet(self, tmp_path):
        """Test minimum surface area check for inlet."""
        validator = GeometryValidator(str(tmp_path), scale_factor=1.0)
        stl_file = tmp_path / "inlet.stl"

        # Create STL with reasonable area for inlet
        with open(stl_file, 'wb') as f:
            f.write(b' ' * 80)
            f.write(struct.pack('<I', 1))
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 0.0, 1.0, 0.0))
            f.write(struct.pack('<H', 0))

        result = validator.check_minimum_surface_area(stl_file, patch_type="inlet")

        # Area of ~0.5 m² should be well above minimum
        assert result.is_valid is True

    def test_verify_inlet_outlet_orientation(self, tmp_path):
        """Test inlet/outlet orientation verification."""
        validator = GeometryValidator(str(tmp_path), scale_factor=1.0)

        # Create inlet STL
        inlet_file = tmp_path / "inlet.stl"
        with open(inlet_file, 'wb') as f:
            f.write(b' ' * 80)
            f.write(struct.pack('<I', 1))
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 2.0, 0.0, 0.0))  # Larger triangle
            f.write(struct.pack('<fff', 0.0, 2.0, 0.0))
            f.write(struct.pack('<H', 0))

        # Create outlet STL (smaller)
        outlet_file = tmp_path / "outlet1.stl"
        with open(outlet_file, 'wb') as f:
            f.write(b' ' * 80)
            f.write(struct.pack('<I', 1))
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 0.0, 1.0, 0.0))
            f.write(struct.pack('<H', 0))

        result = validator.verify_inlet_outlet_orientation(inlet_file, [outlet_file])

        # Should pass basic checks (inlet larger than outlet)
        assert result.is_valid is True

    def test_verify_inlet_outlet_unrealistic_ratio(self, tmp_path):
        """Test warning for unrealistic inlet/outlet area ratio."""
        validator = GeometryValidator(str(tmp_path), scale_factor=1.0)

        # Create small inlet
        inlet_file = tmp_path / "inlet.stl"
        with open(inlet_file, 'wb') as f:
            f.write(b' ' * 80)
            f.write(struct.pack('<I', 1))
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 0.0, 1.0, 0.0))
            f.write(struct.pack('<H', 0))

        # Create very large outlet (unrealistic)
        outlet_file = tmp_path / "outlet1.stl"
        with open(outlet_file, 'wb') as f:
            f.write(b' ' * 80)
            f.write(struct.pack('<I', 1))
            f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
            f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
            f.write(struct.pack('<fff', 5.0, 0.0, 0.0))  # Much larger
            f.write(struct.pack('<fff', 0.0, 5.0, 0.0))
            f.write(struct.pack('<H', 0))

        result = validator.verify_inlet_outlet_orientation(inlet_file, [outlet_file])

        # Should generate warning about area ratio
        assert len(result.warnings) > 0


class TestMeshQualityChecker:
    """Tests for MeshQualityChecker class."""

    def test_initialization(self, tmp_path):
        """Test MeshQualityChecker initialization."""
        checker = MeshQualityChecker(str(tmp_path))

        assert checker.case_directory == tmp_path
        assert checker.ORTHOGONALITY_WARNING == 70
        assert checker.ORTHOGONALITY_ERROR == 75
        assert checker.SKEWNESS_WARNING == 4
        assert checker.SKEWNESS_ERROR == 8

    def test_validate_mesh_quality_missing_log(self, tmp_path):
        """Test validation with missing checkMesh log file."""
        checker = MeshQualityChecker(str(tmp_path))
        result = checker.validate_mesh_quality()

        assert result.is_valid is False
        assert any("checkMesh log file not found" in err for err in result.errors)

    def test_parse_checkmesh_output_complete(self):
        """Test parsing complete checkMesh output."""
        checker = MeshQualityChecker("/tmp")

        checkmesh_output = """
Mesh stats
    points:           1234567
    faces:            2345678
    internal faces:   2000000
    cells:            789012
    boundary patches: 4

Checking geometry...
    Max non-orthogonality = 65.4 degrees
    Max skewness = 3.2
    Max aspect ratio = 85.7
    Mesh OK
"""

        metrics = checker._parse_checkmesh_output(checkmesh_output)

        assert metrics['max_non_orthogonality'] == 65.4
        assert metrics['max_skewness'] == 3.2
        assert metrics['max_aspect_ratio'] == 85.7
        assert metrics['num_cells'] == 789012

    def test_parse_checkmesh_output_partial(self):
        """Test parsing checkMesh output with missing metrics."""
        checker = MeshQualityChecker("/tmp")

        checkmesh_output = """
Mesh stats
    cells:            100000

Checking geometry...
    Max non-orthogonality = 72.1 degrees
"""

        metrics = checker._parse_checkmesh_output(checkmesh_output)

        assert metrics['max_non_orthogonality'] == 72.1
        assert 'max_skewness' not in metrics
        assert metrics['num_cells'] == 100000

    def test_check_orthogonality_good(self):
        """Test orthogonality check with good mesh."""
        checker = MeshQualityChecker("/tmp")
        metrics = {'max_non_orthogonality': 50.0}

        result = checker.check_orthogonality(metrics)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_check_orthogonality_warning(self):
        """Test orthogonality check with warning threshold exceeded."""
        checker = MeshQualityChecker("/tmp")
        metrics = {'max_non_orthogonality': 72.0}

        result = checker.check_orthogonality(metrics)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert "72.0" in result.warnings[0]

    def test_check_orthogonality_error(self):
        """Test orthogonality check with error threshold exceeded."""
        checker = MeshQualityChecker("/tmp")
        metrics = {'max_non_orthogonality': 78.0}

        result = checker.check_orthogonality(metrics)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "78.0" in result.errors[0]

    def test_check_orthogonality_missing_metric(self):
        """Test orthogonality check with missing metric."""
        checker = MeshQualityChecker("/tmp")
        metrics = {}

        result = checker.check_orthogonality(metrics)

        # Missing metric generates a warning, not an error
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "not found" in result.warnings[0].lower()

    def test_check_skewness_good(self):
        """Test skewness check with good mesh."""
        checker = MeshQualityChecker("/tmp")
        metrics = {'max_skewness': 2.5}

        result = checker.check_skewness(metrics)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_check_skewness_warning(self):
        """Test skewness check with warning threshold exceeded."""
        checker = MeshQualityChecker("/tmp")
        metrics = {'max_skewness': 5.5}

        result = checker.check_skewness(metrics)

        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "5.5" in result.warnings[0]

    def test_check_skewness_error(self):
        """Test skewness check with error threshold exceeded."""
        checker = MeshQualityChecker("/tmp")
        metrics = {'max_skewness': 10.0}

        result = checker.check_skewness(metrics)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "10.0" in result.errors[0]

    def test_check_aspect_ratio_good(self):
        """Test aspect ratio check with good mesh."""
        checker = MeshQualityChecker("/tmp")
        metrics = {'max_aspect_ratio': 50.0}

        result = checker.check_aspect_ratio(metrics)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_check_aspect_ratio_warning(self):
        """Test aspect ratio check with warning threshold exceeded."""
        checker = MeshQualityChecker("/tmp")
        metrics = {'max_aspect_ratio': 250.0}

        result = checker.check_aspect_ratio(metrics)

        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "250.0" in result.warnings[0]

    def test_check_aspect_ratio_error(self):
        """Test aspect ratio check with error threshold exceeded."""
        checker = MeshQualityChecker("/tmp")
        metrics = {'max_aspect_ratio': 1500.0}

        result = checker.check_aspect_ratio(metrics)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "1500.0" in result.errors[0]

    def test_validate_mesh_quality_all_good(self, tmp_path):
        """Test complete mesh quality validation with good metrics."""
        checker = MeshQualityChecker(str(tmp_path))

        # Create checkMesh log with good metrics
        log_file = tmp_path / "log.checkMesh"
        log_content = """
Mesh stats
    cells:            500000

Checking geometry...
    Max non-orthogonality = 55.2 degrees
    Max skewness = 2.8
    Max aspect ratio = 75.3
    Mesh OK
"""
        log_file.write_text(log_content)

        result = checker.validate_mesh_quality()

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_validate_mesh_quality_with_warnings(self, tmp_path):
        """Test mesh quality validation with warning-level issues."""
        checker = MeshQualityChecker(str(tmp_path))

        # Create checkMesh log with warning-level metrics
        log_file = tmp_path / "log.checkMesh"
        log_content = """
Mesh stats
    cells:            500000

Checking geometry...
    Max non-orthogonality = 72.5 degrees
    Max skewness = 5.2
    Max aspect ratio = 150.0
    Mesh OK
"""
        log_file.write_text(log_content)

        result = checker.validate_mesh_quality()

        assert result.is_valid is True
        assert len(result.warnings) == 3  # All three metrics have warnings

    def test_validate_mesh_quality_with_errors(self, tmp_path):
        """Test mesh quality validation with error-level issues."""
        checker = MeshQualityChecker(str(tmp_path))

        # Create checkMesh log with error-level metrics
        log_file = tmp_path / "log.checkMesh"
        log_content = """
Mesh stats
    cells:            500000

Checking geometry...
    Max non-orthogonality = 80.0 degrees
    Max skewness = 12.0
    Max aspect ratio = 2000.0
    ***Errors in mesh***
"""
        log_file.write_text(log_content)

        result = checker.validate_mesh_quality()

        assert result.is_valid is False
        assert len(result.errors) >= 3  # At least three error-level issues


class TestBoundaryConditionValidator:
    """Tests for BoundaryConditionValidator class."""

    def test_initialization(self, tmp_path):
        """Test BoundaryConditionValidator initialization."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config, str(tmp_path))

        assert validator.config == config
        assert validator.case_directory == tmp_path

    def test_validate_all_missing_bc_section(self):
        """Test validation with missing boundary_conditions section."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_all()

        assert result.is_valid is False
        assert any("boundary_conditions" in err.lower() for err in result.errors)

    def test_validate_all_missing_inlet(self):
        """Test validation with missing inlet configuration."""
        config = {
            'boundary_conditions': {
                'outlets': {'type': 'ZEROGRADIENT'}
            }
        }
        validator = BoundaryConditionValidator(config)
        result = validator.validate_all()

        assert result.is_valid is False
        assert any("inlet" in err.lower() for err in result.errors)

    def test_validate_all_missing_outlet(self):
        """Test validation with missing outlet configuration."""
        config = {
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'value': 1.0}
            }
        }
        validator = BoundaryConditionValidator(config)
        result = validator.validate_all()

        assert result.is_valid is False
        assert any("outlet" in err.lower() for err in result.errors)

    def test_validate_inlet_invalid_type(self):
        """Test inlet validation with invalid type."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        inlet_config = {'type': 'INVALID_TYPE'}

        result = validator.validate_inlet_configuration(inlet_config)

        assert result.is_valid is False
        assert any("invalid inlet type" in err.lower() for err in result.errors)

    def test_validate_inlet_timevarying_missing_csv(self):
        """Test time-varying inlet without CSV file."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        inlet_config = {'type': 'TIMEVARYING'}

        result = validator.validate_inlet_configuration(inlet_config)

        assert result.is_valid is False
        assert any("csv_file" in err.lower() for err in result.errors)

    def test_validate_inlet_constant_missing_value(self):
        """Test constant inlet without value."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        inlet_config = {'type': 'CONSTANT'}

        result = validator.validate_inlet_configuration(inlet_config)

        assert result.is_valid is False
        assert any("value" in err.lower() for err in result.errors)

    def test_validate_inlet_constant_invalid_value(self):
        """Test constant inlet with invalid (negative) value."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        inlet_config = {'type': 'CONSTANT', 'value': -1.0}

        result = validator.validate_inlet_configuration(inlet_config)

        assert result.is_valid is False
        assert any("positive" in err.lower() for err in result.errors)

    def test_validate_outlet_invalid_type(self):
        """Test outlet validation with invalid type."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        outlet_config = {'type': 'INVALID_TYPE'}

        result = validator.validate_outlet_configuration(outlet_config)

        assert result.is_valid is False
        assert any("invalid outlet type" in err.lower() for err in result.errors)

    def test_validate_flow_data_csv_missing_file(self, tmp_path):
        """Test CSV validation with missing file."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config, str(tmp_path))
        result = validator.validate_flow_data_csv("nonexistent.csv")

        assert result.is_valid is False
        assert any("not found" in err.lower() for err in result.errors)

    def test_validate_flow_data_csv_valid_file(self, tmp_path):
        """Test CSV validation with valid file."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config, str(tmp_path))

        # Create valid CSV file
        csv_file = tmp_path / "flow_data.csv"
        csv_content = """time,velocity
0.00,0.0
0.10,1.0
0.20,1.5
0.30,1.2
0.40,0.8
0.50,0.5
0.60,0.3
0.70,0.2
0.80,0.1
0.90,0.05
1.00,0.0
"""
        csv_file.write_text(csv_content)

        result = validator.validate_flow_data_csv("flow_data.csv")

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_flow_data_csv_missing_time_column(self, tmp_path):
        """Test CSV validation with missing time column."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config, str(tmp_path))

        # Create CSV without time column
        csv_file = tmp_path / "bad_flow.csv"
        csv_content = """velocity
1.0
1.5
1.2
"""
        csv_file.write_text(csv_content)

        result = validator.validate_flow_data_csv("bad_flow.csv")

        assert result.is_valid is False
        assert any("time" in err.lower() for err in result.errors)

    def test_validate_flow_data_csv_missing_data_column(self, tmp_path):
        """Test CSV validation with missing data column."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config, str(tmp_path))

        # Create CSV without velocity/flowrate/pressure column
        csv_file = tmp_path / "bad_flow.csv"
        csv_content = """time,unknown
0.0,1.0
0.1,1.5
"""
        csv_file.write_text(csv_content)

        result = validator.validate_flow_data_csv("bad_flow.csv")

        assert result.is_valid is False
        assert any("data column" in err.lower() for err in result.errors)

    def test_validate_flow_data_csv_insufficient_points(self, tmp_path):
        """Test CSV validation with too few data points."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config, str(tmp_path))

        # Create CSV with only 5 points (minimum is 10)
        csv_file = tmp_path / "short_flow.csv"
        csv_content = """time,velocity
0.0,0.0
0.1,1.0
0.2,1.5
0.3,1.0
0.4,0.0
"""
        csv_file.write_text(csv_content)

        result = validator.validate_flow_data_csv("short_flow.csv")

        assert result.is_valid is False
        assert any("insufficient" in err.lower() for err in result.errors)

    def test_validate_windkessel_missing_settings(self):
        """Test Windkessel validation without settings section."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        outlet_config = {'type': '3EWINDKESSEL'}

        result = validator.validate_windkessel_parameters(outlet_config)

        assert result.is_valid is False
        assert any("windkessel_settings" in err.lower() for err in result.errors)

    def test_validate_windkessel_missing_pressures(self):
        """Test Windkessel validation with missing pressure values."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        outlet_config = {
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'methodology': 'murray_law_automatic'
            }
        }

        result = validator.validate_windkessel_parameters(outlet_config)

        assert result.is_valid is False
        assert any("systolic_pressure" in err.lower() for err in result.errors)
        assert any("diastolic_pressure" in err.lower() for err in result.errors)

    def test_validate_windkessel_invalid_pressure_relationship(self):
        """Test Windkessel with systolic <= diastolic pressure."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        outlet_config = {
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'methodology': 'murray_law_automatic',
                'systolic_pressure': 80,
                'diastolic_pressure': 120  # Backwards!
            }
        }

        result = validator.validate_windkessel_parameters(outlet_config)

        assert result.is_valid is False
        assert any("greater than" in err.lower() for err in result.errors)

    def test_validate_windkessel_valid_automatic(self):
        """Test valid Windkessel with murray_law_automatic."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        outlet_config = {
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'methodology': 'murray_law_automatic',
                'systolic_pressure': 120,
                'diastolic_pressure': 80
            }
        }

        result = validator.validate_windkessel_parameters(outlet_config)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_bc_consistency_timevarying_windkessel(self):
        """Test recommended combination: time-varying inlet with Windkessel."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        inlet_config = {'type': 'TIMEVARYING', 'csv_file': 'flow.csv'}
        outlet_config = {'type': '3EWINDKESSEL'}

        result = validator.validate_bc_consistency(inlet_config, outlet_config)

        # Should be valid (recommended combination)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_bc_consistency_constant_zerogradient_warning(self):
        """Test warning for constant inlet with zero-gradient outlets."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config)
        inlet_config = {'type': 'CONSTANT', 'value': 1.0}
        outlet_config = {'type': 'ZEROGRADIENT'}

        result = validator.validate_bc_consistency(inlet_config, outlet_config)

        # Should generate warning
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("stability" in warn.lower() for warn in result.warnings)
