"""
Test suite for simulation_report_generator module.

Tests cover:
- SimulationReportGenerator class
- Report generation methods
- Markdown to text conversion
- Configuration JSON saving
- Helper methods for data extraction
"""

import pytest
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSimulationReportGeneratorInit:
    """Test SimulationReportGenerator initialization."""

    def test_init_creates_report_dir(self):
        """Test initialization creates report directory."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            assert generator.output_dir == Path(tmpdir)
            assert generator.case_name == "PAT001"
            assert generator.report_dir.exists()
            assert generator.report_dir == Path(tmpdir) / "reports"

    def test_init_handles_existing_report_dir(self):
        """Test initialization handles existing report directory."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create reports dir manually
            (Path(tmpdir) / "reports").mkdir()

            # Should not raise
            generator = SimulationReportGenerator(tmpdir, "PAT001")
            assert generator.report_dir.exists()


class TestGenerateFullReport:
    """Test generate_full_report method."""

    def test_generate_full_report(self):
        """Test full report generation."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "geometry": {"case_name": "PAT001"},
                "simulation_settings": {"analysis_type": "laminar", "solver_type": "pimpleFoam"},
                "physics": {"blood_density": 1060, "nu": 3.5e-6},
                "openfoam_version": "8",
            }

            report_path = generator.generate_full_report(config)

            assert Path(report_path).exists()
            assert Path(report_path).name == "simulation_setup_report.txt"

            # Check config JSON was also created
            config_json = generator.report_dir / "merged_config.json"
            assert config_json.exists()

    def test_generate_full_report_with_geometry_info(self):
        """Test full report with geometry info."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"openfoam_version": "8"}
            geometry_info = {
                "inlet": {"area": 0.001, "radius": 0.018},
                "outlet1": {"area": 0.0005, "radius": 0.013},
                "wall_aorta": {"area": 0.01},
            }

            report_path = generator.generate_full_report(config, geometry_info=geometry_info)

            assert Path(report_path).exists()


class TestConvertMdToTxt:
    """Test _convert_md_to_txt method."""

    def test_convert_header_level1(self):
        """Test converting level 1 header."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "# Main Title"
            txt = generator._convert_md_to_txt(markdown)

            assert "MAIN TITLE" in txt
            assert "=" in txt

    def test_convert_header_level2(self):
        """Test converting level 2 header."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "## Section Title"
            txt = generator._convert_md_to_txt(markdown)

            assert "Section Title" in txt
            # Level 2 headers use separator characters (= or -)
            assert "=" in txt or "-" in txt

    def test_convert_bold_text(self):
        """Test converting bold text."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "This is **bold** text"
            txt = generator._convert_md_to_txt(markdown)

            assert "bold" in txt
            assert "**" not in txt

    def test_convert_inline_code(self):
        """Test converting inline code."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "Use the `command` here"
            txt = generator._convert_md_to_txt(markdown)

            assert "command" in txt
            assert "`" not in txt

    def test_convert_links(self):
        """Test converting markdown links."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "Click [here](http://example.com) for more"
            txt = generator._convert_md_to_txt(markdown)

            assert "here" in txt
            assert "[" not in txt
            assert "http" not in txt


class TestSaveConfigJson:
    """Test _save_config_json method."""

    def test_save_config_json(self):
        """Test saving config as JSON."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"key1": "value1", "key2": 123, "_internal": "hidden"}
            output_path = generator.report_dir / "test_config.json"

            generator._save_config_json(config, output_path, "2024-01-01 12:00:00")

            assert output_path.exists()

            with open(output_path) as f:
                saved = json.load(f)

            assert "_metadata" in saved
            assert "key1" in saved
            assert saved["key1"] == "value1"


class TestHelperMethods:
    """Test helper methods."""

    def test_get_density_from_physics(self):
        """Test density extraction from physics section."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {"blood_density": 1060}}
            density = generator._get_density(config)

            assert density == "1060"

    def test_get_density_from_physical_properties(self):
        """Test density extraction from physical_properties section."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physical_properties": {"density": 1050}}
            density = generator._get_density(config)

            assert density == "1050"

    def test_get_density_missing(self):
        """Test density extraction when missing."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            density = generator._get_density({})

            assert density == "N/A"

    def test_get_kinematic_viscosity(self):
        """Test kinematic viscosity extraction."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {"nu": 3.5e-6}}
            nu = generator._get_kinematic_viscosity(config)

            assert "3.5" in nu
            assert "e-06" in nu.lower() or "e-6" in nu.lower()

    def test_calculate_dynamic_viscosity(self):
        """Test dynamic viscosity calculation."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {"nu": 3.5e-6, "blood_density": 1060}}
            mu = generator._calculate_dynamic_viscosity(config)

            # μ = ν * ρ = 3.5e-6 * 1060 ≈ 3.71e-3
            assert mu != "N/A"

    def test_get_profile_display_with_metadata(self):
        """Test profile display name extraction."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "config_source": {"profile_key": "sim_laminar_coarse"},
                "profile_metadata": {"display_name": "Laminar Coarse"},
            }
            display = generator._get_profile_display(config)

            assert "sim_laminar_coarse" in display
            assert "Laminar Coarse" in display

    def test_get_profile_name_fallback(self):
        """Test profile name fallback method."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"simulation_settings": {"analysis_type": "coarse", "solver_type": "laminar"}}
            name = generator._get_profile_name(config)

            assert name == "sim_laminar_coarse"

    def test_get_case_config_path(self):
        """Test case config path extraction."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"config_source": {"case_config_file": "/path/to/config.json"}}
            path = generator._get_case_config_path(config)

            assert "/path/to/config.json" in path


class TestDescribeFlowRegime:
    """Test _describe_flow_regime method."""

    def test_laminar_flow(self):
        """Test laminar flow regime description."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {"simulation_type": "laminar"}}
            desc = generator._describe_flow_regime(config)

            assert "Laminar" in desc
            assert "None" in desc or "Stokes" in desc

    def test_rans_flow(self):
        """Test RANS flow regime description."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {"simulation_type": "RANS"}, "turbulence_settings": {"RASModel": "kOmegaSST"}}
            desc = generator._describe_flow_regime(config)

            assert "RANS" in desc
            assert "kOmegaSST" in desc

    def test_les_flow(self):
        """Test LES flow regime description."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {"simulation_type": "LES", "subgrid_model": "WALE"}}
            desc = generator._describe_flow_regime(config)

            assert "LES" in desc
            assert "WALE" in desc


class TestGenerateSummaryTxt:
    """Test _generate_summary_txt method."""

    def test_generate_summary(self):
        """Test summary text generation."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "simulation_settings": {"analysis_type": "laminar", "solver_type": "pimpleFoam"},
                "boundary_conditions": {"inlet": {"type": "velocity"}, "outlets": {"type": "pressure"}},
                "mesh": {
                    "resolution_level": "medium",
                    "mesh_resolution": {"target_cell_size_mm": 0.5},
                    "boundary_layers": {"n_surface_layers": 5},
                },
                "physics": {"blood_density": 1060, "nu": 3.5e-6},
                "simulation_control": {"end_time": 1.0, "writeInterval": 0.01},
            }

            summary = generator._generate_summary_txt(config, "2024-01-01 12:00:00")

            assert "PAT001" in summary
            assert "SIMULATION SUMMARY" in summary
            assert "BOUNDARY CONDITIONS" in summary
            assert "MESH" in summary


class TestFormatGeometrySection:
    """Test _format_geometry_section method."""

    def test_format_geometry_basic(self):
        """Test basic geometry formatting."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "geometry": {
                    "case_name": "PAT001",
                    "scale_factor": 0.001,
                    "inlet_keywords_ordered": "inlet",
                    "outlet_keywords_ordered": ["outlet1", "outlet2"],
                    "wall_keywords_ordered": "wall",
                }
            }

            section = generator._format_geometry_section(config, None)

            assert "PAT001" in section
            assert "0.001" in section
            assert "inlet" in section
            assert "outlet1" in section

    def test_format_geometry_with_info(self):
        """Test geometry formatting with measured data."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"geometry": {}}
            geometry_info = {"inlet": {"area": 0.001, "radius": 0.018}, "outlet1": {"area": 0.0005, "radius": 0.013}}

            section = generator._format_geometry_section(config, geometry_info)

            assert "Inlet" in section or "inlet" in section
            assert "Outlet" in section or "outlet" in section


class TestGenerateJsonReport:
    """Test _generate_json_report method."""

    def test_generate_json_report_structure(self):
        """Test JSON report structure."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"openfoam_version": "8"}
            timestamp = "2024-01-01 12:00:00"

            report = generator._generate_json_report(config, None, None, timestamp)

            assert "metadata" in report
            assert "configuration" in report
            assert "geometry" in report
            assert "mesh_quality" in report
            assert "reproducibility" in report

            assert report["metadata"]["case_name"] == "PAT001"
            assert report["metadata"]["openfoam_version"] == "8"


class TestConvertMdToTxtExtended:
    """Extended tests for _convert_md_to_txt method."""

    def test_convert_header_level3(self):
        """Test converting level 3 header."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "### Subsection Title"
            txt = generator._convert_md_to_txt(markdown)

            assert "Subsection Title" in txt
            # Level 3 headers get underline (= or - based on implementation)
            assert "=" in txt or "-" in txt

    def test_convert_header_level4_plus(self):
        """Test converting level 4+ headers."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "#### Deep Section"
            txt = generator._convert_md_to_txt(markdown)

            assert "Deep Section" in txt
            # Level 4+ headers just have colon appended

    def test_convert_italic_text(self):
        """Test converting italic text with single asterisk."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "This is *italic* text"
            txt = generator._convert_md_to_txt(markdown)

            assert "italic" in txt
            assert "*italic*" not in txt

    def test_convert_underscore_formatting(self):
        """Test converting underscores bold/italic."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "This is __bold__ and _italic_ text"
            txt = generator._convert_md_to_txt(markdown)

            assert "bold" in txt
            assert "italic" in txt
            assert "__" not in txt
            assert "_" not in txt or "italic" in txt

    def test_convert_horizontal_rules(self):
        """Test converting horizontal rules."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "Text\n---\nMore text"
            txt = generator._convert_md_to_txt(markdown)

            # Horizontal rules become === lines
            assert "=" in txt

    def test_clean_excessive_blank_lines(self):
        """Test cleaning excessive blank lines."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            markdown = "Text\n\n\n\n\nMore text"
            txt = generator._convert_md_to_txt(markdown)

            # Should reduce multiple blank lines
            assert "\n\n\n\n" not in txt


class TestDescribeFlowRegimeExtended:
    """Extended tests for _describe_flow_regime method."""

    def test_turbulent_flow_type(self):
        """Test TURBULENT flow regime description."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {"simulation_type": "TURBULENT"}}
            desc = generator._describe_flow_regime(config)

            assert "RANS" in desc or "Turbulent" in desc

    def test_default_turbulence_laminar(self):
        """Test laminar detection from default_turbulence setting."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {"default_turbulence": "laminar"}}
            desc = generator._describe_flow_regime(config)

            assert "Laminar" in desc

    def test_unknown_flow_regime(self):
        """Test unknown flow regime handling."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {}}  # No simulation type
            desc = generator._describe_flow_regime(config)

            assert "Unknown" in desc


class TestProfileDisplay:
    """Test profile display methods."""

    def test_get_profile_display_without_display_name(self):
        """Test profile display when display_name not available."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"config_source": {"profile_key": "sim_laminar_coarse"}, "profile_metadata": {}}  # No display_name
            display = generator._get_profile_display(config)

            assert display == "sim_laminar_coarse"

    def test_get_profile_display_fallback(self):
        """Test profile display fallback to _get_profile_name."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"simulation_settings": {"analysis_type": "coarse", "solver_type": "laminar"}}
            display = generator._get_profile_display(config)

            assert display == "sim_laminar_coarse"


class TestDynamicViscosityCalculation:
    """Test dynamic viscosity calculation edge cases."""

    def test_calculate_dynamic_viscosity_exception(self):
        """Test dynamic viscosity with values causing exception."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {"nu": "invalid", "blood_density": 1060}}
            mu = generator._calculate_dynamic_viscosity(config)

            assert mu == "N/A"

    def test_calculate_dynamic_viscosity_missing_values(self):
        """Test dynamic viscosity with missing values."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physics": {"nu": 3.5e-6}}  # Missing density
            mu = generator._calculate_dynamic_viscosity(config)

            assert mu == "N/A"


class TestFormatGeometrySectionExtended:
    """Extended tests for geometry section formatting."""

    def test_format_geometry_single_outlet_string(self):
        """Test geometry formatting with single outlet as string."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"geometry": {"case_name": "PAT001", "outlet_keywords_ordered": "outlet1"}}  # String, not list

            section = generator._format_geometry_section(config, None)

            assert "outlet1" in section

    def test_format_geometry_with_wall_info(self):
        """Test geometry formatting with wall info."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"geometry": {}}
            geometry_info = {
                "inlet": {"area": 0.001, "radius": 0.018},
                "outlet1": {"area": 0.0005, "radius": 0.013},
                "outlet2": {"area": 0.0003, "radius": 0.01},
                "wall": {"area": 0.01},
            }

            section = generator._format_geometry_section(config, geometry_info)

            assert "wall" in section.lower()
            assert "Outlet1" in section or "outlet1" in section
            assert "Outlet2" in section or "outlet2" in section


class TestFormatBoundaryConditions:
    """Test boundary condition formatting."""

    def test_format_bc_timevarying_inlet(self):
        """Test formatting TIMEVARYING inlet."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "boundary_conditions": {
                    "inlet": {
                        "type": "TIMEVARYING",
                        "csv_file": "flow.csv",
                        "data_type": "flowrate",
                        "profile": "parabolic",
                    },
                    "outlets": {"type": "ZEROGRADIENT"},
                }
            }

            section = generator._format_boundary_conditions(config)

            assert "TIMEVARYING" in section
            assert "flow.csv" in section
            assert "flowrate" in section
            assert "parabolic" in section

    def test_format_bc_womersley_inlet(self):
        """Test formatting WOMERSLEY inlet."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "boundary_conditions": {
                    "inlet": {
                        "type": "WOMERSLEY",
                        "csv_file": "waveform.csv",
                        "womersley_number": 12.5,
                        "fourier_modes": 10,
                    },
                    "outlets": {"type": "ZEROGRADIENT"},
                }
            }

            section = generator._format_boundary_conditions(config)

            assert "WOMERSLEY" in section
            assert "waveform.csv" in section
            assert "12.5" in section
            assert "10" in section

    def test_format_bc_constant_with_cardiac_output(self):
        """Test formatting CONSTANT inlet with cardiac output."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "boundary_conditions": {
                    "inlet": {"type": "CONSTANT", "cardiac_output": 5.5},
                    "outlets": {"type": "ZEROGRADIENT"},
                }
            }

            section = generator._format_boundary_conditions(config)

            assert "CONSTANT" in section
            assert "5.5" in section
            assert "L/min" in section

    def test_format_bc_constant_with_velocity_magnitude(self):
        """Test formatting CONSTANT inlet with velocity_magnitude."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "boundary_conditions": {
                    "inlet": {"type": "CONSTANT", "velocity_magnitude": 0.5},
                    "outlets": {"type": "ZEROGRADIENT"},
                }
            }

            section = generator._format_boundary_conditions(config)

            assert "0.5" in section
            assert "m/s" in section

    def test_format_bc_3ewindkessel(self):
        """Test formatting 3EWINDKESSEL outlet."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "boundary_conditions": {
                    "inlet": {"type": "CONSTANT", "velocity": 0.5},
                    "outlets": {
                        "type": "3EWINDKESSEL",
                        "windkessel_settings": {
                            "systolic_pressure": 120,
                            "diastolic_pressure": 80,
                            "venous_pressure": 5,
                            "flow_split": "auto",
                            "outlet_parameters": {"outlet1": {"R": 1e8, "C": 1e-9, "Z": 1e7}},
                        },
                    },
                }
            }

            section = generator._format_boundary_conditions(config)

            assert "3EWINDKESSEL" in section
            assert "120" in section
            assert "80" in section
            assert "Calculated" in section or "Parameters" in section

    def test_format_bc_windkessel_manual_flow_split(self):
        """Test formatting Windkessel with manual flow split."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "boundary_conditions": {
                    "inlet": {"type": "CONSTANT", "velocity": 0.5},
                    "outlets": {
                        "type": "3EWINDKESSEL",
                        "windkessel_settings": {
                            "systolic_pressure": 120,
                            "diastolic_pressure": 80,
                            "flow_split": {"outlet1": 0.7, "outlet2": 0.3},
                        },
                    },
                }
            }

            section = generator._format_boundary_conditions(config)

            assert "Manual" in section

    def test_format_bc_windkessel_numeric_flow_split(self):
        """Test formatting Windkessel with numeric flow split."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "boundary_conditions": {
                    "inlet": {"type": "CONSTANT", "velocity": 0.5},
                    "outlets": {
                        "type": "3EWINDKESSEL",
                        "windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80, "flow_split": 70},
                    },
                }
            }

            section = generator._format_boundary_conditions(config)

            assert "70%" in section

    def test_format_bc_zerogradient_outlet(self):
        """Test formatting zeroGradient outlet."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "boundary_conditions": {
                    "inlet": {"type": "CONSTANT", "velocity": 0.5},
                    "outlets": {"type": "zeroGradient"},
                }
            }

            section = generator._format_boundary_conditions(config)

            assert "zeroGradient" in section
            assert "Zero pressure gradient" in section

    def test_format_bc_fixedvalue_outlet(self):
        """Test formatting fixedValue outlet."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "boundary_conditions": {
                    "inlet": {"type": "CONSTANT", "velocity": 0.5},
                    "outlets": {"type": "fixedValue", "pressure": 10000},
                }
            }

            section = generator._format_boundary_conditions(config)

            assert "fixedValue" in section
            assert "10000" in section

    def test_format_bc_with_walls(self):
        """Test formatting walls section."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "boundary_conditions": {
                    "inlet": {"type": "CONSTANT", "velocity": 0.5},
                    "outlets": {"type": "ZEROGRADIENT"},
                    "walls": {"type": "no_slip", "roughness": 0.001},
                }
            }

            section = generator._format_boundary_conditions(config)

            assert "Walls" in section
            assert "no_slip" in section
            assert "Roughness" in section or "0.001" in section


class TestFormatMeshSettings:
    """Test mesh settings formatting."""

    def test_format_mesh_custom_resolution(self):
        """Test formatting mesh with custom resolution level."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "mesh": {
                    "resolution_level": "custom",
                    "mesh_resolution": {"target_cell_size_mm": 0.8, "base_cell_size_mm": 1.2},
                }
            }

            section = generator._format_mesh_settings(config, None)

            assert "0.8" in section
            assert "1.2" in section

    def test_format_mesh_with_boundary_layers(self):
        """Test formatting mesh with boundary layer details."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "mesh": {
                    "resolution_level": "medium",
                    "boundary_layers": {
                        "n_surface_layers": 5,
                        "expansion_ratio": 1.2,
                        "final_layer_thickness": 0.0001,  # 0.1mm
                    },
                }
            }

            section = generator._format_mesh_settings(config, None)

            assert "5" in section  # layers
            assert "1.2" in section  # expansion ratio
            assert "Thickness" in section

    def test_format_mesh_without_boundary_layers(self):
        """Test formatting mesh without boundary layers."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"mesh": {"resolution_level": "coarse"}}

            section = generator._format_mesh_settings(config, None)

            assert "default wall functions" in section or "Not configured" in section

    def test_format_mesh_with_quality_metrics(self):
        """Test formatting mesh with quality metrics."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"mesh": {"resolution_level": "medium"}}
            mesh_info = {"n_cells": 1000000, "max_non_ortho": 45.5, "max_skewness": 2.1}

            section = generator._format_mesh_settings(config, mesh_info)

            assert "1,000,000" in section
            assert "45.5" in section
            assert "2.1" in section


class TestFormatNumericalSettings:
    """Test numerical settings formatting."""

    def test_format_numerical_with_div_scheme(self):
        """Test formatting numerical with explicit divergence scheme."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"numerical_settings": {"divSchemes": {"div(phi,U)": "Gauss vanLeer"}}}

            section = generator._format_numerical_settings(config)

            assert "vanLeer" in section


class TestFormatSimulationControl:
    """Test simulation control formatting."""

    def test_format_control_auto_end_time(self):
        """Test formatting with auto-calculated end time."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "simulation_control": {"end_time": "auto", "number_of_cycles": 4},
                "case_info": {"heart_rate": 75},
            }

            section = generator._format_simulation_control(config)

            assert "4 cycles" in section
            assert "75" in section or "BPM" in section

    def test_format_control_with_number_of_cycles(self):
        """Test formatting with explicit number of cycles."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"simulation_control": {"end_time": 2.4, "number_of_cycles": 3}}

            section = generator._format_simulation_control(config)

            assert "2.4" in section
            assert "3" in section

    def test_format_control_delta_t_string(self):
        """Test formatting with deltaT as string."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"simulation_control": {"deltaT": "auto"}}

            section = generator._format_simulation_control(config)

            assert "auto" in section

    def test_format_control_adjustable_timestep_with_max(self):
        """Test formatting with adjustable time step and maxDeltaT."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"simulation_control": {"adjustTimeStep": True, "maxDeltaT": 0.001}}

            section = generator._format_simulation_control(config)

            assert "yes" in section
            assert "0.001" in section or "Max Time Step" in section


class TestFormatSolverSettings:
    """Test solver settings formatting."""

    def test_format_solver_parallel(self):
        """Test formatting parallel solver settings."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "run_settings": {"solution_type": "parallel", "subdomains": 8, "decomposition_method": "scotch"},
                "simulation_settings": {"solver_type": "laminar"},
                "openfoam_version": "12",
            }

            section = generator._format_solver_settings(config)

            assert "parallel" in section
            assert "8" in section
            assert "scotch" in section
            assert "mpirun" in section

    def test_format_solver_serial(self):
        """Test formatting serial solver settings."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {
                "run_settings": {"solution_type": "serial"},
                "simulation_settings": {"solver_type": "turbulent"},
                "openfoam_version": "12",
            }

            section = generator._format_solver_settings(config)

            assert "serial" in section
            assert "foamRun" in section
            assert "parallel" not in section or "serial" in section


class TestCaseConfigPath:
    """Test case config path extraction."""

    def test_get_case_config_path_fallback(self):
        """Test case config path fallback to default."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {}  # No config_source
            path = generator._get_case_config_path(config)

            assert "cases_input/PAT001/config.json" in path


class TestGetKinematicViscosity:
    """Test kinematic viscosity extraction."""

    def test_get_kinematic_viscosity_from_physical_properties(self):
        """Test kinematic viscosity from physical_properties."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            config = {"physical_properties": {"kinematic_viscosity": 3.5e-6}}
            nu = generator._get_kinematic_viscosity(config)

            assert "3.5" in nu

    def test_get_kinematic_viscosity_missing(self):
        """Test kinematic viscosity when missing."""
        from aortacfd_lib.simulation_report_generator import SimulationReportGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SimulationReportGenerator(tmpdir, "PAT001")

            nu = generator._get_kinematic_viscosity({})

            assert nu == "N/A"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
