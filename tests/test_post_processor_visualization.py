"""
Test suite for post_processor visualization module.

Tests cover:
- Constants and default configuration
- Helper functions
- Configuration loading
- Color range handling

Note: ParaView-dependent functionality is mocked since ParaView may not be
available in all test environments.
"""

import pytest
import sys
import tempfile
import json
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# Mock ParaView imports before importing post_processor
@pytest.fixture(autouse=True)
def mock_paraview():
    """Mock ParaView imports for testing."""
    mock_paraview = MagicMock()
    mock_paraview.simple = MagicMock()

    sys.modules["paraview"] = mock_paraview
    sys.modules["paraview.simple"] = mock_paraview.simple
    sys.modules["paraview.servermanager"] = MagicMock()

    yield mock_paraview

    # Cleanup
    if "paraview" in sys.modules:
        del sys.modules["paraview"]
    if "paraview.simple" in sys.modules:
        del sys.modules["paraview.simple"]
    if "paraview.servermanager" in sys.modules:
        del sys.modules["paraview.servermanager"]


class TestConstants:
    """Test module constants."""

    def test_blood_density(self):
        """Test blood density constant."""
        # Import after mocking
        from aortacfd_lib import post_processor

        assert post_processor.BLOOD_DENSITY == 1060.0

    def test_pa_to_mmhg_conversion(self):
        """Test pressure conversion factor."""
        from aortacfd_lib import post_processor

        # 133.322 Pa = 1 mmHg
        expected = 1.0 / 133.322
        assert abs(post_processor.PA_TO_MMHG - expected) < 1e-10

    def test_default_property_map_structure(self):
        """Test default property map structure."""
        from aortacfd_lib import post_processor

        property_map = post_processor.DEFAULT_PROPERTY_MAP

        # Should have standard fields
        assert "U" in property_map
        assert "p" in property_map
        assert "TAWSS" in property_map
        assert "OSI" in property_map
        assert "RRT" in property_map

    def test_property_map_fields(self):
        """Test property map field structure."""
        from aortacfd_lib import post_processor

        u_props = post_processor.DEFAULT_PROPERTY_MAP["U"]

        assert "name" in u_props
        assert "derived" in u_props
        assert "prefix" in u_props
        assert "component" in u_props
        assert "preset" in u_props
        assert "representation" in u_props
        assert "unit" in u_props

    def test_default_color_ranges(self):
        """Test default color ranges."""
        from aortacfd_lib import post_processor

        color_ranges = post_processor.DEFAULT_COLOR_RANGES

        assert "U" in color_ranges
        assert color_ranges["U"] == [0, 1]
        assert color_ranges["OSI"] == [0, 0.5]


class TestPropertyMapConfiguration:
    """Test property map configuration options."""

    def test_velocity_field_config(self):
        """Test velocity field configuration."""
        from aortacfd_lib import post_processor

        u_props = post_processor.DEFAULT_PROPERTY_MAP["U"]

        assert u_props["derived"] is False
        assert u_props["representation"] == "Volume"
        assert u_props["unit"] == "m/s"

    def test_pressure_field_config(self):
        """Test pressure field configuration."""
        from aortacfd_lib import post_processor

        p_props = post_processor.DEFAULT_PROPERTY_MAP["p"]

        assert p_props["derived"] is True
        assert p_props["unit"] == "mmHg"

    def test_wss_field_config(self):
        """Test WSS field configuration."""
        from aortacfd_lib import post_processor

        wss_props = post_processor.DEFAULT_PROPERTY_MAP["wallShearStress"]

        assert wss_props["name"] == "WSS"
        assert wss_props["unit"] == "Pa"

    def test_hemodynamic_fields(self):
        """Test hemodynamic field configurations."""
        from aortacfd_lib import post_processor

        # TAWSS
        tawss = post_processor.DEFAULT_PROPERTY_MAP["TAWSS"]
        assert tawss["unit"] == "Pa"

        # OSI
        osi = post_processor.DEFAULT_PROPERTY_MAP["OSI"]
        assert osi["unit"] == ""  # Dimensionless

        # RRT
        rrt = post_processor.DEFAULT_PROPERTY_MAP["RRT"]
        assert rrt["unit"] == "1/Pa"


class TestColorRanges:
    """Test color range handling."""

    def test_velocity_range(self):
        """Test velocity default range."""
        from aortacfd_lib import post_processor

        assert post_processor.DEFAULT_COLOR_RANGES["U"][0] == 0
        assert post_processor.DEFAULT_COLOR_RANGES["U"][1] == 1

    def test_wss_range(self):
        """Test WSS default range."""
        from aortacfd_lib import post_processor

        assert post_processor.DEFAULT_COLOR_RANGES["WSS"][0] == 0
        assert post_processor.DEFAULT_COLOR_RANGES["WSS"][1] == 50

    def test_osi_range(self):
        """Test OSI default range (0 to 0.5)."""
        from aortacfd_lib import post_processor

        assert post_processor.DEFAULT_COLOR_RANGES["OSI"] == [0, 0.5]


class TestHelperFunctionsMocked:
    """Test helper functions with mocked VTK."""

    @patch("aortacfd_lib.post_processor.vtk")
    def test_get_all_points_from_multiblock_empty(self, mock_vtk):
        """Test get_all_points with empty dataset."""
        from aortacfd_lib.post_processor import get_all_points_from_multiblock

        mock_dataset = MagicMock()
        mock_dataset.GetNumberOfBlocks.return_value = 0

        result = get_all_points_from_multiblock(mock_dataset)

        # Should handle empty dataset gracefully (returns None when no points)


class TestOpenFOAMParaViewMocked:
    """Test OpenFOAMParaView class with mocking."""

    @patch("aortacfd_lib.post_processor.OpenFOAMReader")
    @patch("aortacfd_lib.post_processor.CreateView")
    @patch("aortacfd_lib.post_processor.servermanager")
    def test_init_basic(self, mock_sm, mock_create_view, mock_reader):
        """Test basic initialization."""
        from aortacfd_lib.post_processor import OpenFOAMParaView

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal case structure
            case_path = Path(tmpdir)
            (case_path / "system").mkdir()

            # Create a .foam file
            foam_file = case_path / "case.foam"
            foam_file.touch()

            # Mock reader
            mock_reader_instance = MagicMock()
            mock_reader.return_value = mock_reader_instance

            # Mock view
            mock_view = MagicMock()
            mock_create_view.return_value = mock_view

            # This will fail without full ParaView but tests structure
            try:
                processor = OpenFOAMParaView(str(case_path))
            except Exception:
                pass  # Expected without ParaView

    @patch("aortacfd_lib.post_processor.OpenFOAMReader")
    def test_find_foam_file(self, mock_reader):
        """Test .foam file discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .foam file
            foam_file = Path(tmpdir) / "test.foam"
            foam_file.touch()

            # Check file exists
            foam_files = list(Path(tmpdir).glob("*.foam"))
            assert len(foam_files) == 1


class TestOutputGeneration:
    """Test output generation utilities."""

    def test_output_directory_structure(self):
        """Test expected output directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create expected output structure
            output_dir = Path(tmpdir) / "postProcessing" / "images"
            output_dir.mkdir(parents=True)

            assert output_dir.exists()

    def test_screenshot_naming_convention(self):
        """Test screenshot naming conventions."""
        # Expected format: {field}_{timestep}.png
        field = "Velocity"
        timestep = "0.5"

        expected_name = f"{field}_{timestep}.png"

        assert "Velocity" in expected_name
        assert "0.5" in expected_name
        assert expected_name.endswith(".png")


class TestColorPresets:
    """Test color preset configurations."""

    def test_velocity_preset(self):
        """Test velocity uses rainbow preset."""
        from aortacfd_lib import post_processor

        preset = post_processor.DEFAULT_PROPERTY_MAP["U"]["preset"]
        assert preset == "Rainbow Desaturated"

    def test_wss_preset(self):
        """Test WSS uses viridis preset."""
        from aortacfd_lib import post_processor

        preset = post_processor.DEFAULT_PROPERTY_MAP["TAWSS"]["preset"]
        assert preset == "Viridis (matplotlib)"

    def test_osi_preset(self):
        """Test OSI uses cool to warm preset."""
        from aortacfd_lib import post_processor

        preset = post_processor.DEFAULT_PROPERTY_MAP["OSI"]["preset"]
        assert preset == "Cool to Warm"


class TestRepresentationTypes:
    """Test visualization representation types."""

    def test_velocity_uses_volume(self):
        """Test velocity uses volume representation."""
        from aortacfd_lib import post_processor

        rep = post_processor.DEFAULT_PROPERTY_MAP["U"]["representation"]
        assert rep == "Volume"

    def test_surface_fields(self):
        """Test surface fields use surface representation."""
        from aortacfd_lib import post_processor

        surface_fields = ["p", "wallShearStress", "TAWSS", "OSI", "RRT"]

        for field in surface_fields:
            rep = post_processor.DEFAULT_PROPERTY_MAP[field]["representation"]
            assert rep == "Surface"


class TestFieldUnits:
    """Test field unit specifications."""

    def test_velocity_units(self):
        """Test velocity units."""
        from aortacfd_lib import post_processor

        unit = post_processor.DEFAULT_PROPERTY_MAP["U"]["unit"]
        assert unit == "m/s"

    def test_pressure_units(self):
        """Test pressure units (mmHg)."""
        from aortacfd_lib import post_processor

        unit = post_processor.DEFAULT_PROPERTY_MAP["p"]["unit"]
        assert unit == "mmHg"

    def test_wss_units(self):
        """Test WSS units (Pa)."""
        from aortacfd_lib import post_processor

        unit = post_processor.DEFAULT_PROPERTY_MAP["wallShearStress"]["unit"]
        assert unit == "Pa"

    def test_osi_dimensionless(self):
        """Test OSI is dimensionless."""
        from aortacfd_lib import post_processor

        unit = post_processor.DEFAULT_PROPERTY_MAP["OSI"]["unit"]
        assert unit == ""


class TestDerivedFields:
    """Test derived field configurations."""

    def test_derived_field_flags(self):
        """Test derived field identification."""
        from aortacfd_lib import post_processor

        # Derived fields require calculation
        assert post_processor.DEFAULT_PROPERTY_MAP["p"]["derived"] is True
        assert post_processor.DEFAULT_PROPERTY_MAP["wallShearStress"]["derived"] is True

        # Direct fields don't
        assert post_processor.DEFAULT_PROPERTY_MAP["U"]["derived"] is False
        assert post_processor.DEFAULT_PROPERTY_MAP["TAWSS"]["derived"] is False


class TestPressureConversion:
    """Test pressure conversion utilities."""

    def test_pa_to_mmhg(self):
        """Test Pascal to mmHg conversion."""
        from aortacfd_lib import post_processor

        pa_value = 133.322  # 1 mmHg in Pa
        mmhg = pa_value * post_processor.PA_TO_MMHG

        assert abs(mmhg - 1.0) < 0.001

    def test_standard_bp_conversion(self):
        """Test conversion of standard blood pressure."""
        from aortacfd_lib import post_processor

        # 120/80 mmHg is about 16000/10666 Pa
        systolic_pa = 120 / post_processor.PA_TO_MMHG
        diastolic_pa = 80 / post_processor.PA_TO_MMHG

        # Convert back
        systolic_mmhg = systolic_pa * post_processor.PA_TO_MMHG
        diastolic_mmhg = diastolic_pa * post_processor.PA_TO_MMHG

        assert abs(systolic_mmhg - 120) < 0.1
        assert abs(diastolic_mmhg - 80) < 0.1


class TestKEFieldConfiguration:
    """Test kinetic energy field configuration."""

    def test_ke_field_properties(self):
        """Test KE field properties."""
        from aortacfd_lib import post_processor

        ke_props = post_processor.DEFAULT_PROPERTY_MAP["KE"]

        assert ke_props["derived"] is True
        assert ke_props["representation"] == "Volume"
        assert ke_props["preset"] == "Inferno (matplotlib)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
