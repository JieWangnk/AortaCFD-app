"""
Test suite for OpenFOAM setup modules.

Tests cover:
- decompose_setup.py (SolnType class)
- simulation_control.py (SimulationSetup class)
- physical_properties_setup.py (PhysicalPropertiesWriter class)
"""

import pytest
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSolnTypeInit:
    """Test SolnType (decompose_setup) initialization."""

    @patch("aortacfd_lib.decompose_setup.Logger")
    @patch("aortacfd_lib.decompose_setup.Environment")
    @patch("aortacfd_lib.decompose_setup.FileSystemLoader")
    @patch("aortacfd_lib.decompose_setup.OFVersionAdapter")
    def test_init(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test initialization."""
        from aortacfd_lib.decompose_setup import SolnType

        config = {"openfoam_version": "8"}

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = SolnType(config, tmpdir)

            assert writer.config == config
            assert writer.case_dir == tmpdir
            mock_adapter.assert_called_once_with("8")


class TestWriteDecomposeParDict:
    """Test write_decomposeParDict method."""

    @patch("aortacfd_lib.decompose_setup.Logger")
    @patch("aortacfd_lib.decompose_setup.OFVersionAdapter")
    def test_write_decompose_par_dict(self, mock_adapter, mock_logger):
        """Test writing decomposeParDict file."""
        from aortacfd_lib.decompose_setup import SolnType

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.get_foam_file_header.return_value = "// Header"
        mock_adapter.return_value = mock_adapter_instance

        config = {"openfoam_version": "8", "run_settings": {"numberOfSubdomains": 4, "method": "simple"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create system directory
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            # Mock jinja template
            mock_template = MagicMock()
            mock_template.render.return_value = "// decomposeParDict content"

            with patch.object(SolnType, "__init__", lambda self, config, case_dir: None):
                writer = SolnType.__new__(SolnType)
                writer.config = config
                writer.case_dir = tmpdir
                writer.log = MagicMock()
                writer.jinja_env = MagicMock()
                writer.jinja_env.get_template.return_value = mock_template
                writer.version_adapter = mock_adapter_instance

                writer.write_decomposeParDict()

                # Verify file was written
                decompose_path = Path(tmpdir) / "system" / "decomposeParDict"
                assert decompose_path.exists()


class TestSimulationSetupInit:
    """Test SimulationSetup initialization."""

    @patch("aortacfd_lib.simulation_control.Logger")
    @patch("aortacfd_lib.simulation_control.Environment")
    @patch("aortacfd_lib.simulation_control.FileSystemLoader")
    @patch("aortacfd_lib.simulation_control.OFVersionAdapter")
    def test_init(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test initialization."""
        from aortacfd_lib.simulation_control import SimulationSetup

        config = {"openfoam_version": "8"}

        with tempfile.TemporaryDirectory() as tmpdir:
            setup = SimulationSetup(config, tmpdir)

            assert setup.config == config
            assert setup.case_dir == tmpdir


class TestWriteControlDict:
    """Test write_controlDict method."""

    @patch("aortacfd_lib.simulation_control.Logger")
    @patch("aortacfd_lib.simulation_control.prepare_control_dict_context")
    @patch("aortacfd_lib.simulation_control.OFVersionAdapter")
    def test_write_control_dict(self, mock_adapter, mock_prepare, mock_logger):
        """Test writing controlDict file."""
        from aortacfd_lib.simulation_control import SimulationSetup

        mock_adapter_instance = MagicMock()
        mock_adapter.return_value = mock_adapter_instance

        mock_prepare.return_value = {"needs_windkessel_lib": False, "is_pulsatile": True, "inlet_type": "TIMEVARYING"}

        config = {"openfoam_version": "8", "openfoam_major_version": 8, "cardiac_cycle": 0.8}

        final_control_dict = {"endTime": 1.0, "deltaT": 0.001, "writeInterval": 0.01}

        with tempfile.TemporaryDirectory() as tmpdir:
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            mock_template = MagicMock()
            mock_template.render.return_value = "// controlDict content"

            with patch.object(SimulationSetup, "__init__", lambda self, config, case_dir: None):
                setup = SimulationSetup.__new__(SimulationSetup)
                setup.config = config
                setup.case_dir = tmpdir
                setup.log = MagicMock()
                setup.jinja_env = MagicMock()
                setup.jinja_env.get_template.return_value = mock_template
                setup.version_adapter = mock_adapter_instance

                setup.write_controlDict(final_control_dict)

                control_path = Path(tmpdir) / "system" / "controlDict"
                assert control_path.exists()

    @patch("aortacfd_lib.simulation_control.Logger")
    @patch("aortacfd_lib.simulation_control.prepare_control_dict_context")
    @patch("aortacfd_lib.simulation_control.OFVersionAdapter")
    def test_write_control_dict_with_cardiac_cycle(self, mock_adapter, mock_prepare, mock_logger):
        """Test writing controlDict with explicit cardiac cycle."""
        from aortacfd_lib.simulation_control import SimulationSetup

        mock_prepare.return_value = {"needs_windkessel_lib": False, "is_pulsatile": True, "inlet_type": "TIMEVARYING"}

        config = {"openfoam_version": "8", "openfoam_major_version": 8}

        with tempfile.TemporaryDirectory() as tmpdir:
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            mock_template = MagicMock()
            mock_template.render.return_value = "// content"

            with patch.object(SimulationSetup, "__init__", lambda self, config, case_dir: None):
                setup = SimulationSetup.__new__(SimulationSetup)
                setup.config = config
                setup.case_dir = tmpdir
                setup.log = MagicMock()
                setup.jinja_env = MagicMock()
                setup.jinja_env.get_template.return_value = mock_template
                setup.version_adapter = MagicMock()

                setup.write_controlDict({}, cardiac_cycle=0.9)

                # Check template was called with correct cardiac_cycle
                call_context = mock_template.render.call_args[0][0]
                assert call_context["cardiac_cycle"] == 0.9


class TestPhysicalPropertiesWriterInit:
    """Test PhysicalPropertiesWriter initialization."""

    @patch("aortacfd_lib.physical_properties_setup.Logger")
    @patch("aortacfd_lib.physical_properties_setup.Environment")
    @patch("aortacfd_lib.physical_properties_setup.FileSystemLoader")
    @patch("aortacfd_lib.physical_properties_setup.OFVersionAdapter")
    def test_init(self, mock_adapter, mock_loader, mock_env, mock_logger):
        """Test initialization."""
        from aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter

        config = {"openfoam_version": "8"}

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = PhysicalPropertiesWriter(config, tmpdir)

            assert writer.config == config
            assert writer.case_dir == tmpdir


class TestWriteTransportProperties:
    """Test write_transportProperties_file method."""

    @patch("aortacfd_lib.physical_properties_setup.Logger")
    @patch("aortacfd_lib.physical_properties_setup.OFVersionAdapter")
    def test_write_transport_properties(self, mock_adapter, mock_logger):
        """Test writing transportProperties file."""
        from aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.get_foam_file_header.return_value = "// Header"
        mock_adapter.return_value = mock_adapter_instance

        config = {"openfoam_version": "8", "physics": {"nu": 3.5e-6, "rho": 1060}}

        with tempfile.TemporaryDirectory() as tmpdir:
            constant_dir = Path(tmpdir) / "constant"
            constant_dir.mkdir()

            mock_template = MagicMock()
            mock_template.render.return_value = "// transportProperties content"

            with patch.object(PhysicalPropertiesWriter, "__init__", lambda self, config, case_dir: None):
                writer = PhysicalPropertiesWriter.__new__(PhysicalPropertiesWriter)
                writer.config = config
                writer.case_dir = tmpdir
                writer.log = MagicMock()
                writer.jinja_env = MagicMock()
                writer.jinja_env.get_template.return_value = mock_template
                writer.version_adapter = mock_adapter_instance

                writer.write_transportProperties_file()

                transport_path = Path(tmpdir) / "constant" / "transportProperties"
                assert transport_path.exists()


class TestWriteMomentumTransport:
    """Test write_momentumTransport_file method."""

    @patch("aortacfd_lib.physical_properties_setup.Logger")
    @patch("aortacfd_lib.physical_properties_setup.OFVersionAdapter")
    def test_write_momentum_transport(self, mock_adapter, mock_logger):
        """Test writing momentumTransport file."""
        from aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.get_foam_file_header.return_value = "// Header"
        mock_adapter.return_value = mock_adapter_instance

        config = {"openfoam_version": "8", "openfoam_major_version": 8, "physics": {"simulation_type": "laminar"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            constant_dir = Path(tmpdir) / "constant"
            constant_dir.mkdir()

            mock_template = MagicMock()
            mock_template.render.return_value = "// momentumTransport content"

            with patch.object(PhysicalPropertiesWriter, "__init__", lambda self, config, case_dir: None):
                writer = PhysicalPropertiesWriter.__new__(PhysicalPropertiesWriter)
                writer.config = config
                writer.case_dir = tmpdir
                writer.log = MagicMock()
                writer.jinja_env = MagicMock()
                writer.jinja_env.get_template.return_value = mock_template
                writer.version_adapter = mock_adapter_instance

                writer.write_momentumTransport_file()

                momentum_path = Path(tmpdir) / "constant" / "momentumTransport"
                assert momentum_path.exists()


class TestWriteFvOptions:
    """Test write_fvOptions_file method."""

    @patch("aortacfd_lib.physical_properties_setup.Logger")
    @patch("aortacfd_lib.physical_properties_setup.prepare_fv_options_context")
    @patch("aortacfd_lib.physical_properties_setup.OFVersionAdapter")
    def test_write_fv_options_les(self, mock_adapter, mock_prepare, mock_logger):
        """Test writing fvOptions file for LES."""
        from aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter

        mock_prepare.return_value = {"is_les": True, "bound_nut": True, "nut_min": 0.0}

        config = {"openfoam_version": "8", "physics": {"simulation_type": "LES"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            mock_template = MagicMock()
            mock_template.render.return_value = "// fvOptions content"

            with patch.object(PhysicalPropertiesWriter, "__init__", lambda self, config, case_dir: None):
                writer = PhysicalPropertiesWriter.__new__(PhysicalPropertiesWriter)
                writer.config = config
                writer.case_dir = tmpdir
                writer.log = MagicMock()
                writer.jinja_env = MagicMock()
                writer.jinja_env.get_template.return_value = mock_template
                writer.version_adapter = MagicMock()

                writer.write_fvOptions_file()

                fvoptions_path = Path(tmpdir) / "system" / "fvOptions"
                assert fvoptions_path.exists()

                # Verify log was called for LES
                writer.log.info.assert_called()

    @patch("aortacfd_lib.physical_properties_setup.Logger")
    @patch("aortacfd_lib.physical_properties_setup.prepare_fv_options_context")
    @patch("aortacfd_lib.physical_properties_setup.OFVersionAdapter")
    def test_write_fv_options_laminar(self, mock_adapter, mock_prepare, mock_logger):
        """Test writing fvOptions file for laminar (no log)."""
        from aortacfd_lib.physical_properties_setup import PhysicalPropertiesWriter

        mock_prepare.return_value = {"is_les": False, "bound_nut": False, "nut_min": 0.0}

        config = {"openfoam_version": "8", "physics": {"simulation_type": "laminar"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            system_dir = Path(tmpdir) / "system"
            system_dir.mkdir()

            mock_template = MagicMock()
            mock_template.render.return_value = "// fvOptions content"

            with patch.object(PhysicalPropertiesWriter, "__init__", lambda self, config, case_dir: None):
                writer = PhysicalPropertiesWriter.__new__(PhysicalPropertiesWriter)
                writer.config = config
                writer.case_dir = tmpdir
                writer.log = MagicMock()
                writer.jinja_env = MagicMock()
                writer.jinja_env.get_template.return_value = mock_template
                writer.version_adapter = MagicMock()

                writer.write_fvOptions_file()

                fvoptions_path = Path(tmpdir) / "system" / "fvOptions"
                assert fvoptions_path.exists()

                # Log should NOT be called for laminar
                writer.log.info.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
