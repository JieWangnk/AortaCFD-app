"""
Test suite for the validation utilities module.

Tests cover:
- ValidationResult container
- GeometryValidator for STL files
- MeshQualityChecker for checkMesh output
- BoundaryConditionValidator for BC configurations
"""

import pytest
import sys
import os
import tempfile
import struct
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.utils.validation import (
    ValidationResult,
    GeometryValidator,
    MeshQualityChecker,
    BoundaryConditionValidator,
)


class TestValidationResult:
    """Test ValidationResult container class."""

    def test_default_is_valid(self):
        """Test that default ValidationResult is valid."""
        result = ValidationResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.cell_count == 0

    def test_add_error_sets_invalid(self):
        """Test that adding error sets is_valid to False."""
        result = ValidationResult()
        result.add_error("Test error")

        assert result.is_valid is False
        assert "Test error" in result.errors

    def test_add_warning_keeps_valid(self):
        """Test that adding warning keeps is_valid True."""
        result = ValidationResult()
        result.add_warning("Test warning")

        assert result.is_valid is True
        assert "Test warning" in result.warnings

    def test_bool_conversion(self):
        """Test bool conversion of ValidationResult."""
        valid_result = ValidationResult()
        assert bool(valid_result) is True

        invalid_result = ValidationResult(is_valid=False)
        assert bool(invalid_result) is False

    def test_str_representation(self):
        """Test string representation."""
        # Valid result
        valid = ValidationResult()
        assert str(valid) == "Valid"

        # With errors
        with_errors = ValidationResult()
        with_errors.add_error("Error 1")
        assert "Errors: Error 1" in str(with_errors)

        # With warnings
        with_warnings = ValidationResult()
        with_warnings.add_warning("Warning 1")
        assert "Warnings: Warning 1" in str(with_warnings)

    def test_init_with_values(self):
        """Test initialization with preset values."""
        result = ValidationResult(
            is_valid=False,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
            cell_count=12345
        )

        assert result.is_valid is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert result.cell_count == 12345


class TestGeometryValidator:
    """Test GeometryValidator class."""

    def test_init(self):
        """Test validator initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = GeometryValidator(tmpdir, scale_factor=0.001)

            assert validator.case_directory == Path(tmpdir)
            assert validator.scale_factor == 0.001

    def test_validate_all_missing_directory(self):
        """Test validation with missing directory."""
        validator = GeometryValidator("/nonexistent/path")
        result = validator.validate_all()

        assert result.is_valid is False
        assert any("not found" in err.lower() for err in result.errors)

    def test_validate_all_no_stl_files(self):
        """Test validation with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = GeometryValidator(tmpdir)
            result = validator.validate_all()

            assert result.is_valid is False
            assert any("no stl" in err.lower() for err in result.errors)

    def test_check_stl_integrity_missing_file(self):
        """Test STL integrity check with missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = GeometryValidator(tmpdir)
            result = validator.check_stl_integrity(Path(tmpdir) / "nonexistent.stl")

            assert result.is_valid is False
            assert any("not found" in err.lower() for err in result.errors)

    def test_check_stl_integrity_empty_file(self):
        """Test STL integrity check with empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "empty.stl"
            stl_path.touch()  # Create empty file

            validator = GeometryValidator(tmpdir)
            result = validator.check_stl_integrity(stl_path)

            assert result.is_valid is False
            assert any("empty" in err.lower() for err in result.errors)

    def test_check_stl_integrity_too_small(self):
        """Test STL integrity check with file too small for header."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "tiny.stl"
            with open(stl_path, 'wb') as f:
                f.write(b'x' * 50)  # Less than 84 bytes

            validator = GeometryValidator(tmpdir)
            result = validator.check_stl_integrity(stl_path)

            assert result.is_valid is False
            assert any("too small" in err.lower() for err in result.errors)

    def test_validate_binary_stl(self):
        """Test binary STL validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"

            # Create valid binary STL with 1 triangle
            with open(stl_path, 'wb') as f:
                # Header (80 bytes)
                f.write(b'\x00' * 80)
                # Number of triangles (4 bytes)
                f.write(struct.pack('<I', 1))
                # Triangle data (50 bytes): normal + 3 vertices + attribute
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))  # Normal
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))  # V1
                f.write(struct.pack('<fff', 1.0, 0.0, 0.0))  # V2
                f.write(struct.pack('<fff', 0.0, 1.0, 0.0))  # V3
                f.write(struct.pack('<H', 0))  # Attribute byte count

            validator = GeometryValidator(tmpdir)
            result = validator.check_stl_integrity(stl_path)

            # May have warning about few triangles but should be valid
            # (1 triangle is valid but warned)
            # The test checks the file is processed correctly

    def test_validate_ascii_stl(self):
        """Test ASCII STL validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"

            # Create valid ASCII STL
            content = """solid test
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
endsolid test
"""
            stl_path.write_text(content)

            validator = GeometryValidator(tmpdir)
            result = validator._validate_ascii_stl(stl_path)

            # Should process without errors (may have warnings about few facets)

    def test_validate_patch_configuration(self):
        """Test patch configuration validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create patch files
            (Path(tmpdir) / "inlet.stl").touch()
            (Path(tmpdir) / "outlet1.stl").touch()
            (Path(tmpdir) / "wall_aorta.stl").touch()

            stl_files = list(Path(tmpdir).glob("*.stl"))
            validator = GeometryValidator(tmpdir)
            result = validator.validate_patch_configuration(stl_files)

            # Should be valid with inlet, outlet, wall
            assert result.is_valid is True

    def test_validate_patch_missing_inlet(self):
        """Test patch validation with missing inlet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "outlet1.stl").touch()
            (Path(tmpdir) / "wall.stl").touch()

            stl_files = list(Path(tmpdir).glob("*.stl"))
            validator = GeometryValidator(tmpdir)
            result = validator.validate_patch_configuration(stl_files)

            assert result.is_valid is False
            assert any("inlet" in err.lower() for err in result.errors)

    def test_validate_patch_duplicate_names(self):
        """Test patch validation with duplicate names."""
        # This tests the case where patch_names list has duplicates
        stl_files = [Path("/test/inlet.stl"), Path("/test/inlet.stl")]
        validator = GeometryValidator("/test")
        result = validator.validate_patch_configuration(stl_files)

        assert result.is_valid is False
        assert any("duplicate" in err.lower() for err in result.errors)


class TestMeshQualityChecker:
    """Test MeshQualityChecker class."""

    def test_init(self):
        """Test checker initialization."""
        checker = MeshQualityChecker("/test/case")
        assert checker.case_directory == Path("/test/case")

    def test_validate_missing_log(self):
        """Test validation with missing log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checker = MeshQualityChecker(tmpdir)
            result = checker.validate_mesh_quality()

            assert result.is_valid is False
            assert any("not found" in err.lower() for err in result.errors)

    def test_parse_checkmesh_output(self):
        """Test parsing checkMesh log output."""
        content = """
Mesh stats
    points:           123456
    faces:            234567
    cells:            100000
Max non-orthogonality = 65.4
Max skewness = 2.3
Max aspect ratio = 45.6
"""
        checker = MeshQualityChecker("/test")
        metrics = checker._parse_checkmesh_output(content)

        assert metrics['max_non_orthogonality'] == 65.4
        assert metrics['max_skewness'] == 2.3
        assert metrics['max_aspect_ratio'] == 45.6
        assert metrics['num_cells'] == 100000
        assert metrics['num_points'] == 123456
        assert metrics['num_faces'] == 234567

    def test_check_orthogonality_ok(self):
        """Test orthogonality check with good values."""
        checker = MeshQualityChecker("/test")
        metrics = {'max_non_orthogonality': 50.0}
        result = checker.check_orthogonality(metrics)

        assert result.is_valid is True
        assert len(result.warnings) == 0
        assert len(result.errors) == 0

    def test_check_orthogonality_warning(self):
        """Test orthogonality check with warning level."""
        checker = MeshQualityChecker("/test")
        metrics = {'max_non_orthogonality': 72.0}
        result = checker.check_orthogonality(metrics)

        assert result.is_valid is True
        assert len(result.warnings) > 0

    def test_check_orthogonality_error(self):
        """Test orthogonality check with error level."""
        checker = MeshQualityChecker("/test")
        metrics = {'max_non_orthogonality': 80.0}
        result = checker.check_orthogonality(metrics)

        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_check_skewness_ok(self):
        """Test skewness check with good values."""
        checker = MeshQualityChecker("/test")
        metrics = {'max_skewness': 2.0}
        result = checker.check_skewness(metrics)

        assert result.is_valid is True

    def test_check_skewness_error(self):
        """Test skewness check with error level."""
        checker = MeshQualityChecker("/test")
        metrics = {'max_skewness': 10.0}
        result = checker.check_skewness(metrics)

        assert result.is_valid is False

    def test_check_aspect_ratio_ok(self):
        """Test aspect ratio check with good values."""
        checker = MeshQualityChecker("/test")
        metrics = {'max_aspect_ratio': 50.0}
        result = checker.check_aspect_ratio(metrics)

        assert result.is_valid is True

    def test_check_aspect_ratio_error(self):
        """Test aspect ratio check with error level."""
        checker = MeshQualityChecker("/test")
        metrics = {'max_aspect_ratio': 1500.0}
        result = checker.check_aspect_ratio(metrics)

        assert result.is_valid is False

    def test_validate_mesh_quality_with_failures(self):
        """Test mesh quality validation with failed mesh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            log_path = logs_dir / "log.checkMesh"
            log_path.write_text("""
Mesh stats
    cells: 50000
Max non-orthogonality = 60
Max skewness = 3.0
Max aspect ratio = 80
***FAILED*** - mesh check failed
""")

            checker = MeshQualityChecker(tmpdir)
            result = checker.validate_mesh_quality()

            assert result.is_valid is False
            # Error message contains "failures" not "failed"
            assert any("failure" in err.lower() for err in result.errors)


class TestBoundaryConditionValidator:
    """Test BoundaryConditionValidator class."""

    def test_init(self):
        """Test validator initialization."""
        config = {'boundary_conditions': {}}
        validator = BoundaryConditionValidator(config, "/test/case")

        assert validator.config == config
        assert validator.case_directory == Path("/test/case")

    def test_normalize_data_type(self):
        """Test data type normalization."""
        # flowrate variations
        assert BoundaryConditionValidator.normalize_data_type('flowRate') == 'flowrate'
        assert BoundaryConditionValidator.normalize_data_type('FLOWRATE') == 'flowrate'
        assert BoundaryConditionValidator.normalize_data_type('flow_rate') == 'flowrate'
        assert BoundaryConditionValidator.normalize_data_type('q') == 'flowrate'

        # velocity variations
        assert BoundaryConditionValidator.normalize_data_type('velocity') == 'velocity'
        assert BoundaryConditionValidator.normalize_data_type('Velocity') == 'velocity'
        assert BoundaryConditionValidator.normalize_data_type('vel') == 'velocity'

        # pressure
        assert BoundaryConditionValidator.normalize_data_type('pressure') == 'pressure'

        # None/empty
        assert BoundaryConditionValidator.normalize_data_type(None) is None
        assert BoundaryConditionValidator.normalize_data_type('') is None

    def test_validate_all_no_bc_config(self):
        """Test validation with missing BC configuration."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_all()

        assert result.is_valid is False
        assert any("no boundary condition" in err.lower() for err in result.errors)

    def test_validate_all_nested_structure(self):
        """Test validation with nested BC structure."""
        config = {
            'boundary_conditions': {
                'inlet': {'type': 'CONSTANT', 'velocity': 0.5, 'profile': 'parabolic'},
                'outlets': {'type': 'ZEROGRADIENT'}
            }
        }
        validator = BoundaryConditionValidator(config)
        result = validator.validate_all()

        # Should pass basic validation
        assert result.is_valid is True or len(result.errors) == 0

    def test_validate_all_flattened_structure(self):
        """Test validation with flattened BC structure."""
        config = {
            'inlet': {'type': 'CONSTANT', 'velocity': 0.5, 'profile': 'parabolic'},
            'outlets': {'type': 'ZEROGRADIENT'}
        }
        validator = BoundaryConditionValidator(config)
        result = validator.validate_all()

        # Should recognize flattened structure

    def test_validate_inlet_missing_type(self):
        """Test inlet validation with missing type."""
        config = {'boundary_conditions': {'inlet': {}}}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_inlet_configuration({})

        assert result.is_valid is False
        assert any("type" in err.lower() for err in result.errors)

    def test_validate_inlet_invalid_type(self):
        """Test inlet validation with invalid type."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_inlet_configuration({'type': 'INVALID'})

        assert result.is_valid is False
        assert any("invalid inlet type" in err.lower() for err in result.errors)

    def test_validate_inlet_valid_types(self):
        """Test inlet validation with valid types."""
        config = {}
        validator = BoundaryConditionValidator(config)

        for inlet_type in ['TIMEVARYING', 'CONSTANT', 'WOMERSLEY']:
            # Create minimal valid config for each type
            inlet_config = {'type': inlet_type}
            if inlet_type in ['TIMEVARYING', 'WOMERSLEY']:
                inlet_config['csv_file'] = 'test.csv'
                inlet_config['data_type'] = 'flowrate'
                inlet_config['profile'] = 'parabolic'
            else:
                inlet_config['velocity'] = 0.5
                inlet_config['profile'] = 'parabolic'

            result = validator.validate_inlet_configuration(inlet_config)
            # Just check it processes without crashing

    def test_validate_inlet_profile_compatibility(self):
        """Test inlet type-profile compatibility."""
        config = {}
        validator = BoundaryConditionValidator(config)

        # WOMERSLEY requires womersley profile
        result = validator.validate_inlet_configuration({
            'type': 'WOMERSLEY',
            'csv_file': 'test.csv',
            'data_type': 'flowrate',
            'profile': 'parabolic'  # Wrong profile
        })
        assert any("incompatible" in err.lower() for err in result.errors)

    def test_validate_outlet_missing_type(self):
        """Test outlet validation with missing type."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_outlet_configuration({})

        assert result.is_valid is False

    def test_validate_outlet_invalid_type(self):
        """Test outlet validation with invalid type."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_outlet_configuration({'type': 'INVALID'})

        assert result.is_valid is False

    def test_validate_outlet_valid_types(self):
        """Test outlet validation with valid types."""
        config = {}
        validator = BoundaryConditionValidator(config)

        for outlet_type in ['ZEROGRADIENT', 'FIXEDVALUE', '2EWINDKESSEL']:
            inlet_config = {'type': outlet_type}
            if 'WINDKESSEL' in outlet_type:
                inlet_config['windkessel_settings'] = {
                    'systolic_pressure': 120,
                    'diastolic_pressure': 80
                }
            result = validator.validate_outlet_configuration(inlet_config)
            # Just check it processes

    def test_validate_windkessel_missing_settings(self):
        """Test Windkessel validation with missing settings."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_windkessel_parameters({'type': '3EWINDKESSEL'})

        assert result.is_valid is False
        assert any("windkessel_settings" in err.lower() for err in result.errors)

    def test_validate_windkessel_missing_pressure(self):
        """Test Windkessel validation with missing pressure."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {}
        })

        assert result.is_valid is False
        # Should complain about missing pressure

    def test_validate_windkessel_invalid_pressure_relationship(self):
        """Test Windkessel validation with SP <= DP."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'systolic_pressure': 80,
                'diastolic_pressure': 120  # DP > SP
            }
        })

        assert result.is_valid is False
        assert any("greater than" in err.lower() for err in result.errors)

    def test_validate_windkessel_direct_rcz_mode(self):
        """Test Windkessel validation with direct RCZ mode."""
        config = {}
        validator = BoundaryConditionValidator(config)

        # Direct RCZ mode - pressure not required
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'outlet_parameters': {
                    'outlet1': {'R': 1e8, 'C': 1e-9, 'Z': 1e7}
                }
            }
        })

        # Should not complain about missing pressure in direct RCZ mode
        # May have other validation issues but not pressure-related

    def test_check_direct_rcz_mode(self):
        """Test direct RCZ mode detection."""
        config = {}
        validator = BoundaryConditionValidator(config)

        # Not direct mode
        assert validator._check_direct_rcz_mode({}) is False
        assert validator._check_direct_rcz_mode({'outlet_parameters': {}}) is False

        # Direct mode
        assert validator._check_direct_rcz_mode({
            'outlet_parameters': {
                'outlet1': {'R': 1e8, 'C': 1e-9, 'Z': 1e7}
            }
        }) is True

    def test_validate_bc_consistency(self):
        """Test BC consistency validation."""
        config = {}
        validator = BoundaryConditionValidator(config)

        # Time-varying with Windkessel - recommended
        result = validator.validate_bc_consistency(
            {'type': 'TIMEVARYING'},
            {'type': '3EWINDKESSEL'}
        )
        # Should have no warnings about this combo

    def test_validate_bc_consistency_constant_windkessel(self):
        """Test BC consistency with CONSTANT inlet and 3E Windkessel."""
        config = {}
        validator = BoundaryConditionValidator(config)

        result = validator.validate_bc_consistency(
            {'type': 'CONSTANT'},
            {'type': '3EWINDKESSEL'}
        )

        # Should warn about using 2E instead
        assert len(result.warnings) > 0


class TestBoundaryConditionValidatorCSV:
    """Test CSV file validation in BoundaryConditionValidator."""

    def test_validate_flow_data_csv_missing(self):
        """Test CSV validation with missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {}
            validator = BoundaryConditionValidator(config, tmpdir)
            result = validator.validate_flow_data_csv("nonexistent.csv")

            assert result.is_valid is False
            assert any("not found" in err.lower() for err in result.errors)

    def test_validate_flow_data_csv_valid(self):
        """Test CSV validation with valid file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "flow.csv"
            # Create valid CSV with enough data points
            lines = ["time,flowrate"]
            for i in range(20):
                t = i * 0.05  # 0 to 0.95s
                q = 0.5 + 0.3 * (i % 10) / 10  # Some variation
                lines.append(f"{t:.3f},{q:.3f}")
            csv_path.write_text("\n".join(lines))

            config = {}
            validator = BoundaryConditionValidator(config, tmpdir)
            result = validator.validate_flow_data_csv("flow.csv")

            # Should be valid or have only minor warnings

    def test_validate_flow_data_csv_missing_time(self):
        """Test CSV validation with missing time column."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "flow.csv"
            csv_path.write_text("flowrate\n0.5\n0.6\n0.7\n")

            config = {}
            validator = BoundaryConditionValidator(config, tmpdir)
            result = validator.validate_flow_data_csv("flow.csv")

            assert result.is_valid is False
            assert any("time" in err.lower() for err in result.errors)

    def test_validate_flow_data_csv_insufficient_points(self):
        """Test CSV validation with too few data points."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "flow.csv"
            csv_path.write_text("time,flowrate\n0.0,0.5\n0.1,0.6\n")  # Only 2 points

            config = {}
            validator = BoundaryConditionValidator(config, tmpdir)
            result = validator.validate_flow_data_csv("flow.csv")

            assert result.is_valid is False
            assert any("insufficient" in err.lower() for err in result.errors)


class TestGeometryValidatorSurfaceArea:
    """Test surface area calculation and validation."""

    def test_check_minimum_surface_area_inlet(self):
        """Test minimum surface area check for inlet patch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "inlet.stl"
            # Create binary STL with a reasonable-sized triangle
            with open(stl_path, 'wb') as f:
                f.write(b'\x00' * 80)  # Header
                f.write(struct.pack('<I', 1))  # 1 triangle
                # Triangle with some area
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))  # Normal
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))  # V1
                f.write(struct.pack('<fff', 0.01, 0.0, 0.0))  # V2 (10mm)
                f.write(struct.pack('<fff', 0.0, 0.01, 0.0))  # V3 (10mm)
                f.write(struct.pack('<H', 0))

            validator = GeometryValidator(tmpdir)
            result = validator.check_minimum_surface_area(stl_path, "inlet")
            # Area = 0.5 * 0.01 * 0.01 = 5e-5 m² (above MIN_AREA_INLET=1e-6)
            assert result.is_valid is True

    def test_check_minimum_surface_area_below_threshold(self):
        """Test minimum surface area check with tiny patch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "tiny_outlet.stl"
            # Create very small triangle
            with open(stl_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 1e-5, 0.0, 0.0))  # Very tiny
                f.write(struct.pack('<fff', 0.0, 1e-5, 0.0))
                f.write(struct.pack('<H', 0))

            validator = GeometryValidator(tmpdir)
            result = validator.check_minimum_surface_area(stl_path, "outlet")
            # Area is tiny, should generate warning
            assert len(result.warnings) > 0

    def test_check_minimum_surface_area_wall(self):
        """Test minimum surface area check for wall patch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "wall.stl"
            # Create STL with larger area
            with open(stl_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.1, 0.0, 0.0))  # 100mm
                f.write(struct.pack('<fff', 0.0, 0.1, 0.0))  # 100mm
                f.write(struct.pack('<H', 0))

            validator = GeometryValidator(tmpdir)
            result = validator.check_minimum_surface_area(stl_path, "wall")
            # Area = 0.5 * 0.1 * 0.1 = 5e-3 m² (above MIN_AREA_WALL=1e-5)
            assert result.is_valid is True

    def test_check_minimum_surface_area_unknown_type(self):
        """Test minimum surface area for unknown patch type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "other.stl"
            with open(stl_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.01, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.0, 0.01, 0.0))
                f.write(struct.pack('<H', 0))

            validator = GeometryValidator(tmpdir)
            result = validator.check_minimum_surface_area(stl_path, "unknown")
            # Should use default (outlet) threshold
            assert result.is_valid is True

    def test_check_minimum_surface_area_with_scale_factor(self):
        """Test surface area calculation with scale factor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "inlet.stl"
            # Create STL with large coords (assuming mm input)
            with open(stl_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 10.0, 0.0, 0.0))  # 10mm in mm units
                f.write(struct.pack('<fff', 0.0, 10.0, 0.0))
                f.write(struct.pack('<H', 0))

            # Scale factor 0.001 for mm -> m
            validator = GeometryValidator(tmpdir, scale_factor=0.001)
            result = validator.check_minimum_surface_area(stl_path, "inlet")
            # Area in file units = 50 mm², scaled = 50e-6 m² (above 1e-6)
            assert result.is_valid is True


class TestCalculateSTLArea:
    """Test STL area calculation methods."""

    def test_calculate_binary_stl_area(self):
        """Test area calculation for binary STL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            # Create binary STL with known area (right triangle 1x1)
            with open(stl_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.0, 1.0, 0.0))
                f.write(struct.pack('<H', 0))

            validator = GeometryValidator(tmpdir)
            area = validator._calculate_stl_area(stl_path)
            # Area of right triangle = 0.5 * base * height = 0.5
            assert abs(area - 0.5) < 1e-6

    def test_calculate_ascii_stl_area(self):
        """Test area calculation for ASCII STL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            content = """solid test
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
endsolid test
"""
            stl_path.write_text(content)

            validator = GeometryValidator(tmpdir)
            area = validator._calculate_stl_area(stl_path)
            # Area of right triangle = 0.5
            assert abs(area - 0.5) < 1e-6

    def test_calculate_stl_area_multiple_triangles(self):
        """Test area calculation with multiple triangles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "test.stl"
            # Create 2 triangles (makes a 1x1 square)
            with open(stl_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 2))  # 2 triangles
                # First triangle
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.0, 1.0, 0.0))
                f.write(struct.pack('<H', 0))
                # Second triangle
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 1.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 1.0, 1.0, 0.0))
                f.write(struct.pack('<fff', 0.0, 1.0, 0.0))
                f.write(struct.pack('<H', 0))

            validator = GeometryValidator(tmpdir)
            area = validator._calculate_stl_area(stl_path)
            # Total area = 0.5 + 0.5 = 1.0
            assert abs(area - 1.0) < 1e-6

    def test_calculate_stl_area_error_handling(self):
        """Test area calculation error handling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "bad.stl"
            stl_path.write_bytes(b'corrupted data')

            validator = GeometryValidator(tmpdir)
            area = validator._calculate_stl_area(stl_path)
            # Should return 0.0 on error
            assert area == 0.0


class TestVerifyInletOutletOrientation:
    """Test inlet/outlet orientation verification."""

    def test_verify_orientation_normal(self):
        """Test orientation verification with normal geometry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create inlet (larger)
            inlet_path = Path(tmpdir) / "inlet.stl"
            with open(inlet_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.02, 0.0, 0.0))  # Larger inlet
                f.write(struct.pack('<fff', 0.0, 0.02, 0.0))
                f.write(struct.pack('<H', 0))

            # Create outlet (smaller - typical for aorta)
            outlet_path = Path(tmpdir) / "outlet1.stl"
            with open(outlet_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.01, 0.0, 0.0))  # Smaller outlet
                f.write(struct.pack('<fff', 0.0, 0.01, 0.0))
                f.write(struct.pack('<H', 0))

            validator = GeometryValidator(tmpdir)
            result = validator.verify_inlet_outlet_orientation(
                inlet_path, [outlet_path]
            )
            assert result.is_valid is True

    def test_verify_orientation_missing_inlet(self):
        """Test orientation verification with missing inlet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = GeometryValidator(tmpdir)
            result = validator.verify_inlet_outlet_orientation(
                Path(tmpdir) / "nonexistent.stl", []
            )
            assert result.is_valid is False
            assert any("not found" in err.lower() for err in result.errors)

    def test_verify_orientation_outlet_much_larger(self):
        """Test warning when outlets are much larger than inlet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create small inlet
            inlet_path = Path(tmpdir) / "inlet.stl"
            with open(inlet_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.005, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.0, 0.005, 0.0))
                f.write(struct.pack('<H', 0))

            # Create large outlet (3x inlet area)
            outlet_path = Path(tmpdir) / "outlet1.stl"
            with open(outlet_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.02, 0.0, 0.0))  # Much larger
                f.write(struct.pack('<fff', 0.0, 0.02, 0.0))
                f.write(struct.pack('<H', 0))

            validator = GeometryValidator(tmpdir)
            result = validator.verify_inlet_outlet_orientation(
                inlet_path, [outlet_path]
            )
            # Should warn about outlet being larger
            assert len(result.warnings) > 0
            assert any("larger" in w.lower() for w in result.warnings)

    def test_verify_orientation_outlet_very_small(self):
        """Test warning when outlets are very small compared to inlet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create large inlet
            inlet_path = Path(tmpdir) / "inlet.stl"
            with open(inlet_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.1, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.0, 0.1, 0.0))
                f.write(struct.pack('<H', 0))

            # Create tiny outlet (<10% inlet area)
            outlet_path = Path(tmpdir) / "outlet1.stl"
            with open(outlet_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 1))
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                f.write(struct.pack('<fff', 0.005, 0.0, 0.0))  # Very small
                f.write(struct.pack('<fff', 0.0, 0.005, 0.0))
                f.write(struct.pack('<H', 0))

            validator = GeometryValidator(tmpdir)
            result = validator.verify_inlet_outlet_orientation(
                inlet_path, [outlet_path]
            )
            # Should warn about small outlet
            assert len(result.warnings) > 0
            assert any("small" in w.lower() for w in result.warnings)


class TestMeshQualityCheckerExtended:
    """Extended tests for MeshQualityChecker."""

    def test_validate_boundary_layer_coverage_found(self):
        """Test boundary layer coverage detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "log.checkMesh"
            log_path.write_text("""
Mesh stats
    cells: 100000
layer thickness info
Max non-orthogonality = 45.0
""")

            checker = MeshQualityChecker(tmpdir)
            result = checker.validate_boundary_layer_coverage()
            assert result.is_valid is True

    def test_validate_boundary_layer_coverage_not_found(self):
        """Test when no boundary layer info in log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()
            log_path = logs_dir / "log.checkMesh"
            log_path.write_text("""
Mesh stats
    cells: 100000
Max non-orthogonality = 45.0
""")

            checker = MeshQualityChecker(tmpdir)
            result = checker.validate_boundary_layer_coverage()
            assert len(result.warnings) > 0
            assert any("layer" in w.lower() for w in result.warnings)

    def test_validate_boundary_layer_coverage_missing_log(self):
        """Test boundary layer check with missing log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checker = MeshQualityChecker(tmpdir)
            result = checker.validate_boundary_layer_coverage()
            assert len(result.warnings) > 0

    def test_validate_boundary_layer_with_custom_log_path(self):
        """Test boundary layer check with custom log path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "custom_log.txt"
            log_path.write_text("layer thickness detected")

            checker = MeshQualityChecker(tmpdir)
            result = checker.validate_boundary_layer_coverage(str(log_path))
            assert result.is_valid is True

    def test_check_orthogonality_missing_metric(self):
        """Test orthogonality check when metric is missing."""
        checker = MeshQualityChecker("/test")
        result = checker.check_orthogonality({})
        assert len(result.warnings) > 0
        assert any("not found" in w.lower() for w in result.warnings)

    def test_check_skewness_missing_metric(self):
        """Test skewness check when metric is missing."""
        checker = MeshQualityChecker("/test")
        result = checker.check_skewness({})
        assert len(result.warnings) > 0
        assert any("not found" in w.lower() for w in result.warnings)

    def test_check_aspect_ratio_missing_metric(self):
        """Test aspect ratio check when metric is missing."""
        checker = MeshQualityChecker("/test")
        result = checker.check_aspect_ratio({})
        assert len(result.warnings) > 0
        assert any("not found" in w.lower() for w in result.warnings)

    def test_check_skewness_warning_level(self):
        """Test skewness check at warning level."""
        checker = MeshQualityChecker("/test")
        metrics = {'max_skewness': 5.0}  # Between warning (4) and error (8)
        result = checker.check_skewness(metrics)
        assert result.is_valid is True
        assert len(result.warnings) > 0

    def test_check_aspect_ratio_warning_level(self):
        """Test aspect ratio check at warning level."""
        checker = MeshQualityChecker("/test")
        metrics = {'max_aspect_ratio': 200.0}  # Between warning (100) and error (1000)
        result = checker.check_aspect_ratio(metrics)
        assert result.is_valid is True
        assert len(result.warnings) > 0

    def test_validate_mesh_quality_with_custom_log(self):
        """Test mesh validation with custom log file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "custom.log"
            log_path.write_text("""
Mesh stats
    cells: 50000
Max non-orthogonality = 50
Max skewness = 2.0
Max aspect ratio = 50
""")

            checker = MeshQualityChecker(tmpdir)
            result = checker.validate_mesh_quality(str(log_path))
            assert result.is_valid is True
            assert result.cell_count == 50000


class TestBoundaryConditionValidatorExtended:
    """Extended tests for BoundaryConditionValidator."""

    def test_validate_inlet_womersley_missing_physics(self):
        """Test Womersley inlet requiring physics.nu."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_inlet_configuration({
            'type': 'WOMERSLEY',
            'csv_file': 'test.csv',
            'data_type': 'flowrate',
            'profile': 'womersley'
        })
        assert any("physics.nu" in err.lower() for err in result.errors)

    def test_validate_inlet_womersley_invalid_nu(self):
        """Test Womersley inlet with invalid physics.nu."""
        config = {'physics': {'nu': -1e-6}}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_inlet_configuration({
            'type': 'WOMERSLEY',
            'csv_file': 'test.csv',
            'data_type': 'flowrate',
            'profile': 'womersley'
        })
        assert any("positive" in err.lower() for err in result.errors)

    def test_validate_inlet_constant_with_flowrate_alias(self):
        """Test CONSTANT inlet with flowrate (alias for cardiac_output)."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_inlet_configuration({
            'type': 'CONSTANT',
            'flowrate': 5.0,
            'profile': 'parabolic'
        })
        # Should accept flowrate as alias for cardiac_output
        assert all("flowrate" not in err.lower() and "cardiac_output" not in err.lower()
                  for err in result.errors)

    def test_validate_inlet_constant_both_velocity_and_cardiac(self):
        """Test CONSTANT inlet with both velocity and cardiac_output."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_inlet_configuration({
            'type': 'CONSTANT',
            'velocity': 0.5,
            'cardiac_output': 5.0,
            'profile': 'parabolic'
        })
        # Should warn about using both
        assert len(result.warnings) > 0

    def test_validate_inlet_constant_invalid_velocity(self):
        """Test CONSTANT inlet with invalid velocity."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_inlet_configuration({
            'type': 'CONSTANT',
            'velocity': -0.5,
            'profile': 'parabolic'
        })
        assert any("positive" in err.lower() for err in result.errors)

    def test_validate_inlet_constant_invalid_cardiac_output(self):
        """Test CONSTANT inlet with invalid cardiac_output."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_inlet_configuration({
            'type': 'CONSTANT',
            'cardiac_output': 'invalid',
            'profile': 'parabolic'
        })
        assert any("positive" in err.lower() or "must be" in err.lower()
                  for err in result.errors)

    def test_validate_inlet_constant_extreme_cardiac_output(self):
        """Test CONSTANT inlet with extreme cardiac_output."""
        config = {}
        validator = BoundaryConditionValidator(config)

        # Very low
        result = validator.validate_inlet_configuration({
            'type': 'CONSTANT',
            'cardiac_output': 1.5,  # Below typical 2-30 range
            'profile': 'parabolic'
        })
        assert len(result.warnings) > 0

        # Very high
        result = validator.validate_inlet_configuration({
            'type': 'CONSTANT',
            'cardiac_output': 35.0,  # Above typical range
            'profile': 'parabolic'
        })
        assert len(result.warnings) > 0

    def test_validate_inlet_invalid_profile(self):
        """Test inlet with invalid profile."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_inlet_configuration({
            'type': 'CONSTANT',
            'velocity': 0.5,
            'profile': 'invalid_profile'
        })
        assert any("invalid profile" in err.lower() for err in result.errors)

    def test_validate_inlet_invalid_data_type(self):
        """Test inlet with invalid data_type."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_inlet_configuration({
            'type': 'TIMEVARYING',
            'csv_file': 'test.csv',
            'data_type': 'invalid_type',
            'profile': 'parabolic'
        })
        assert any("data_type" in err.lower() for err in result.errors)

    def test_validate_inlet_period_validation(self):
        """Test inlet period parameter validation."""
        config = {}
        validator = BoundaryConditionValidator(config)

        # Invalid period (non-numeric)
        result = validator.validate_inlet_configuration({
            'type': 'CONSTANT',
            'velocity': 0.5,
            'profile': 'parabolic',
            'period': 'invalid'
        })
        assert any("period" in err.lower() for err in result.errors)

        # Period too short
        result = validator.validate_inlet_configuration({
            'type': 'CONSTANT',
            'velocity': 0.5,
            'profile': 'parabolic',
            'period': 0.2  # Below 0.3s
        })
        assert len(result.warnings) > 0

        # Period too long
        result = validator.validate_inlet_configuration({
            'type': 'CONSTANT',
            'velocity': 0.5,
            'profile': 'parabolic',
            'period': 3.0  # Above 2.0s
        })
        assert len(result.warnings) > 0

    def test_validate_windkessel_pressure_range_warnings(self):
        """Test Windkessel pressure range warnings."""
        config = {}
        validator = BoundaryConditionValidator(config)

        # Extreme systolic pressure
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'systolic_pressure': 250,  # Very high
                'diastolic_pressure': 80
            }
        })
        assert len(result.warnings) > 0

        # Extreme diastolic pressure
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'systolic_pressure': 120,
                'diastolic_pressure': 30  # Very low
            }
        })
        assert len(result.warnings) > 0

    def test_validate_windkessel_pulse_pressure(self):
        """Test Windkessel pulse pressure validation."""
        config = {}
        validator = BoundaryConditionValidator(config)

        # Very low pulse pressure
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'systolic_pressure': 100,
                'diastolic_pressure': 90  # Only 10 mmHg difference
            }
        })
        assert len(result.warnings) > 0

        # Very high pulse pressure
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'systolic_pressure': 180,
                'diastolic_pressure': 80  # 100 mmHg difference
            }
        })
        assert len(result.warnings) > 0

    def test_validate_windkessel_invalid_methodology(self):
        """Test Windkessel with invalid methodology."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'systolic_pressure': 120,
                'diastolic_pressure': 80,
                'methodology': 'invalid_methodology'
            }
        })
        assert len(result.warnings) > 0

    def test_validate_windkessel_manual_mode(self):
        """Test Windkessel manual mode parameter validation."""
        config = {}
        validator = BoundaryConditionValidator(config)

        # Missing manual parameters
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'systolic_pressure': 120,
                'diastolic_pressure': 80,
                'methodology': 'manual'
            }
        })
        assert len(result.errors) > 0

        # Invalid manual parameter (negative)
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'systolic_pressure': 120,
                'diastolic_pressure': 80,
                'methodology': 'manual',
                'C_compliance': -1e-8,
                'R_proximal': 1e7,
                'R_distal': 1e8
            }
        })
        assert any("positive" in err.lower() for err in result.errors)

    def test_validate_windkessel_deprecated_init_method(self):
        """Test Windkessel deprecated initial_pressure_method."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'systolic_pressure': 120,
                'diastolic_pressure': 80,
                'initial_pressure_method': 'windkessel'  # Deprecated
            }
        })
        assert len(result.warnings) > 0
        assert any("deprecated" in w.lower() for w in result.warnings)

    def test_validate_windkessel_invalid_init_method(self):
        """Test Windkessel invalid initial_pressure_method."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_windkessel_parameters({
            'type': '3EWINDKESSEL',
            'windkessel_settings': {
                'systolic_pressure': 120,
                'diastolic_pressure': 80,
                'initial_pressure_method': 'invalid'
            }
        })
        assert any("initial_pressure_method" in err.lower() for err in result.errors)

    def test_validate_bc_consistency_constant_zerogradient(self):
        """Test BC consistency for CONSTANT + ZEROGRADIENT."""
        config = {}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_bc_consistency(
            {'type': 'CONSTANT'},
            {'type': 'ZEROGRADIENT'}
        )
        assert len(result.warnings) > 0

    def test_validate_all_missing_inlet(self):
        """Test validate_all with missing inlet."""
        config = {'boundary_conditions': {'outlets': {'type': 'ZEROGRADIENT'}}}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_all()
        assert any("inlet" in err.lower() for err in result.errors)

    def test_validate_all_missing_outlets(self):
        """Test validate_all with missing outlets."""
        config = {'boundary_conditions': {'inlet': {'type': 'CONSTANT', 'velocity': 0.5, 'profile': 'parabolic'}}}
        validator = BoundaryConditionValidator(config)
        result = validator.validate_all()
        assert any("outlet" in err.lower() for err in result.errors)


class TestValidateBinarySTLEdgeCases:
    """Test edge cases in binary STL validation."""

    def test_binary_stl_corrupted_header(self):
        """Test binary STL with corrupted triangle count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "bad.stl"
            with open(stl_path, 'wb') as f:
                f.write(b'\x00' * 80)  # Header
                f.write(b'xx')  # Incomplete count

            validator = GeometryValidator(tmpdir)
            result = validator._validate_binary_stl(stl_path)
            assert result.is_valid is False

    def test_binary_stl_size_mismatch(self):
        """Test binary STL with incorrect file size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "bad.stl"
            with open(stl_path, 'wb') as f:
                f.write(b'\x00' * 80)  # Header
                f.write(struct.pack('<I', 10))  # Claims 10 triangles
                # But only write 1 triangle worth of data
                f.write(b'\x00' * 50)

            validator = GeometryValidator(tmpdir)
            result = validator._validate_binary_stl(stl_path)
            assert any("mismatch" in err.lower() for err in result.errors)


class TestValidateASCIISTLEdgeCases:
    """Test edge cases in ASCII STL validation."""

    def test_ascii_stl_mismatched_endfacet(self):
        """Test ASCII STL with mismatched facet/endfacet (edge case)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "bad.stl"
            # Has facet but no endfacet - triggers mismatch error
            stl_path.write_text("solid test\nfacet normal 0 0 1\nendsolid test\n")

            validator = GeometryValidator(tmpdir)
            result = validator._validate_ascii_stl(stl_path)
            # Should complain about mismatch
            assert any("mismatch" in err.lower() for err in result.errors)

    def test_ascii_stl_missing_endsolid(self):
        """Test ASCII STL missing endsolid keyword."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "bad.stl"
            stl_path.write_text("solid test\nfacet normal 0 0 1\n")

            validator = GeometryValidator(tmpdir)
            result = validator._validate_ascii_stl(stl_path)
            assert any("endsolid" in err.lower() for err in result.errors)

    def test_ascii_stl_mismatched_facet_count(self):
        """Test ASCII STL with mismatched facet/endfacet count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "bad.stl"
            stl_path.write_text("""solid test
facet normal 0 0 1
facet normal 0 0 1
endfacet
endsolid test
""")

            validator = GeometryValidator(tmpdir)
            result = validator._validate_ascii_stl(stl_path)
            assert any("mismatch" in err.lower() for err in result.errors)

    def test_ascii_stl_no_facets(self):
        """Test ASCII STL with no facets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stl_path = Path(tmpdir) / "empty.stl"
            stl_path.write_text("solid test\nendsolid test\n")

            validator = GeometryValidator(tmpdir)
            result = validator._validate_ascii_stl(stl_path)
            assert any("no facets" in err.lower() for err in result.errors)


class TestGeometryValidatorValidateAll:
    """Test the complete validate_all workflow."""

    def test_validate_all_success(self):
        """Test validate_all with valid geometry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid inlet STL
            inlet_path = Path(tmpdir) / "inlet.stl"
            with open(inlet_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 100))  # 100 triangles
                for _ in range(100):
                    f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                    f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                    f.write(struct.pack('<fff', 0.01, 0.0, 0.0))
                    f.write(struct.pack('<fff', 0.0, 0.01, 0.0))
                    f.write(struct.pack('<H', 0))

            # Create outlet
            outlet_path = Path(tmpdir) / "outlet1.stl"
            with open(outlet_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 50))
                for _ in range(50):
                    f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                    f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                    f.write(struct.pack('<fff', 0.01, 0.0, 0.0))
                    f.write(struct.pack('<fff', 0.0, 0.01, 0.0))
                    f.write(struct.pack('<H', 0))

            # Create wall
            wall_path = Path(tmpdir) / "wall_aorta.stl"
            with open(wall_path, 'wb') as f:
                f.write(b'\x00' * 80)
                f.write(struct.pack('<I', 200))
                for _ in range(200):
                    f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                    f.write(struct.pack('<fff', 0.0, 0.0, 0.0))
                    f.write(struct.pack('<fff', 0.01, 0.0, 0.0))
                    f.write(struct.pack('<fff', 0.0, 0.01, 0.0))
                    f.write(struct.pack('<H', 0))

            validator = GeometryValidator(tmpdir)
            result = validator.validate_all()
            assert result.is_valid is True


class TestCSVValidationEdgeCases:
    """Test edge cases in CSV validation."""

    def test_validate_csv_with_comments(self):
        """Test CSV with comment lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "flow.csv"
            lines = ["# This is a comment", "time,flowrate"]
            for i in range(20):
                lines.append(f"{i * 0.05:.3f},{0.5 + 0.1 * (i % 5):.3f}")
            csv_path.write_text("\n".join(lines))

            config = {}
            validator = BoundaryConditionValidator(config, tmpdir)
            result = validator.validate_flow_data_csv("flow.csv")
            assert result.is_valid is True or len(result.errors) == 0

    def test_validate_csv_time_not_monotonic(self):
        """Test CSV with non-monotonic time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "flow.csv"
            csv_path.write_text("""time,flowrate
0.0,0.5
0.1,0.6
0.05,0.7
0.2,0.8
0.3,0.9
0.4,1.0
0.5,0.9
0.6,0.8
0.7,0.7
0.8,0.6
""")

            config = {}
            validator = BoundaryConditionValidator(config, tmpdir)
            result = validator.validate_flow_data_csv("flow.csv")
            assert any("monotonic" in err.lower() for err in result.errors)

    def test_validate_csv_duplicate_time(self):
        """Test CSV with duplicate time values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "flow.csv"
            csv_path.write_text("""time,flowrate
0.0,0.5
0.1,0.6
0.1,0.7
0.2,0.8
0.3,0.9
0.4,1.0
0.5,0.9
0.6,0.8
0.7,0.7
0.8,0.6
""")

            config = {}
            validator = BoundaryConditionValidator(config, tmpdir)
            result = validator.validate_flow_data_csv("flow.csv")
            assert any("duplicate" in err.lower() for err in result.errors)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
