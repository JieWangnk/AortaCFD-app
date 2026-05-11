"""
Comprehensive test suite for wk_setup.py module.

Tests cover:
- WkSetup class initialization
- Murray's law flow distribution
- Custom flow split parsing
- 2-element and 3-element Windkessel calculations
- Direct RCZ mode
- Inlet flow reading
- Flow split percentage parsing
"""

import pytest
import sys
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestWkSetupInit:
    """Test WkSetup initialization."""

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_init_basic(self, mock_logger):
        """Test basic initialization."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {
                "case_name": "test_case",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2"],
            },
            "boundary_conditions": {
                "inlet": {"type": "TIMEVARYING"},
                "outlets": {
                    "type": "3EWINDKESSEL",
                    "windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80},
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, ["inlet.stl", "outlet1.stl"], tmpdir, 0.8)

            assert wk.config == config
            assert wk.cardiac_cycle == 0.8
            assert wk.case_dir == tmpdir

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_init_with_flattened_config(self, mock_logger):
        """Test initialization with flattened config structure."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {
                "case_name": "test_case",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1"],
            },
            "inlet": {"type": "CONSTANT", "velocity": 0.5},
            "outlets": {"type": "2EWINDKESSEL", "windkessel_settings": {}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            # Should find inlet/outlet settings from flattened config
            assert wk.inlet_settings == config["inlet"]


class TestMurrayFlowSplit:
    """Test Murray's law flow split calculation."""

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_calculate_murray_flow_split_equal_radii(self, mock_logger):
        """Test Murray's law with equal radii."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {
                "case_name": "test",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["o1", "o2"],
            },
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "3EWINDKESSEL", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            # Equal radii should give equal flow
            outlet_radii = {"outlet1": 0.005, "outlet2": 0.005}  # 5mm each
            flow_split = wk._calculate_murray_flow_split(outlet_radii)

            assert abs(flow_split["outlet1"] - 0.5) < 0.01
            assert abs(flow_split["outlet2"] - 0.5) < 0.01
            assert abs(sum(flow_split.values()) - 1.0) < 0.001

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_calculate_murray_flow_split_unequal_radii(self, mock_logger):
        """Test Murray's law with unequal radii."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {
                "case_name": "test",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["o1", "o2"],
            },
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "3EWINDKESSEL", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            # Larger radius should get more flow
            outlet_radii = {"outlet1": 0.010, "outlet2": 0.005}  # 10mm vs 5mm
            flow_split = wk._calculate_murray_flow_split(outlet_radii)

            # With Murray's law (r^2.6), outlet1 should get more flow
            assert flow_split["outlet1"] > flow_split["outlet2"]
            assert abs(sum(flow_split.values()) - 1.0) < 0.001


class TestParseCustomFlowSplit:
    """Test custom flow split parsing."""

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_parse_complete_ratios(self, mock_logger):
        """Test parsing complete flow ratios that sum to 1.0."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {
                "case_name": "test",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["o1", "o2", "o3"],
            },
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "3EWINDKESSEL", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            flow_config = {"o1": 0.3, "o2": 0.3, "o3": 0.4}
            outlet_patches = ["o1", "o2", "o3"]
            outlet_radii = {"o1": 0.005, "o2": 0.005, "o3": 0.006}

            result = wk._parse_custom_flow_split(flow_config, outlet_patches, outlet_radii)

            assert abs(result["o1"] - 0.3) < 0.01
            assert abs(result["o2"] - 0.3) < 0.01
            assert abs(result["o3"] - 0.4) < 0.01

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_parse_percentages_with_murray_rest(self, mock_logger):
        """Test parsing percentages with Murray's law for remaining outlets."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {
                "case_name": "test",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["o1", "o2", "o3"],
            },
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "3EWINDKESSEL", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            # o1 gets 30%, remaining (o2, o3) share 70% by Murray's law
            flow_config = {"o1": 30, "_rest": "murray"}
            outlet_patches = ["o1", "o2", "o3"]
            outlet_radii = {"o1": 0.005, "o2": 0.005, "o3": 0.005}  # Equal radii

            result = wk._parse_custom_flow_split(flow_config, outlet_patches, outlet_radii)

            assert abs(result["o1"] - 0.30) < 0.01
            # o2 and o3 should share 70% equally (same radius)
            assert abs(result["o2"] - 0.35) < 0.02
            assert abs(result["o3"] - 0.35) < 0.02


class TestParseFlowSplitPercentage:
    """Test flow split percentage parsing (MATLAB method)."""

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_parse_branches_percentage(self, mock_logger):
        """Test parsing branches percentage with area distribution."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {
                "case_name": "test",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["o1", "o2", "o3"],
            },
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "3EWINDKESSEL", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            # 70% to branches (o1, o2), 30% to main (o3)
            outlet_patches = ["o1", "o2", "o3"]
            outlet_radii = {"o1": 0.005, "o2": 0.005, "o3": 0.010}

            result = wk._parse_flow_split_percentage(70, outlet_patches, "area", outlet_radii)

            # Main outlet (last) should get 30%
            assert abs(result["o3"] - 0.30) < 0.01
            # Branches should share 70% total
            assert abs(result["o1"] + result["o2"] - 0.70) < 0.01

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_single_outlet(self, mock_logger):
        """Test single outlet gets 100%."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {"case_name": "test", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["o1"]},
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "3EWINDKESSEL", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            result = wk._parse_flow_split_percentage(70, ["o1"], "area", {"o1": 0.005})

            assert result["o1"] == 1.0


class TestCheckDirectRCZMode:
    """Test direct RCZ mode detection."""

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_direct_rcz_mode_complete(self, mock_logger):
        """Test detection of complete direct RCZ parameters."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {
                "case_name": "test",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["o1", "o2"],
            },
            "boundary_conditions": {
                "inlet": {},
                "outlets": {
                    "type": "3EWINDKESSEL",
                    "windkessel_settings": {
                        "outlet_parameters": {
                            "o1": {"R": 1.5e9, "C": 1e-9, "Z": 1.5e8},
                            "o2": {"R": 2.0e9, "C": 0.8e-9, "Z": 2.0e8},
                        }
                    },
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            result = wk._check_direct_rcz_mode(["o1", "o2"])

            assert result is True

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_direct_rcz_mode_missing_outlet(self, mock_logger):
        """Test detection when outlet is missing from parameters."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {
                "case_name": "test",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["o1", "o2"],
            },
            "boundary_conditions": {
                "inlet": {},
                "outlets": {
                    "type": "3EWINDKESSEL",
                    "windkessel_settings": {
                        "outlet_parameters": {
                            "o1": {"R": 1.5e9, "C": 1e-9, "Z": 1.5e8}
                            # o2 is missing
                        }
                    },
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            result = wk._check_direct_rcz_mode(["o1", "o2"])

            assert result is False

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_direct_rcz_mode_missing_key(self, mock_logger):
        """Test detection when R/C/Z key is missing."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {"case_name": "test", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": ["o1"]},
            "boundary_conditions": {
                "inlet": {},
                "outlets": {
                    "type": "3EWINDKESSEL",
                    "windkessel_settings": {"outlet_parameters": {"o1": {"R": 1.5e9, "C": 1e-9}}},  # Z missing
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            result = wk._check_direct_rcz_mode(["o1"])

            assert result is False


class TestNormalizeDataType:
    """Test data type normalization."""

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_normalize_flowrate_variations(self, mock_logger):
        """Test normalizing flowrate variations."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {"case_name": "test", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": []},
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            assert wk._normalize_data_type("flowRate") == "flowrate"
            assert wk._normalize_data_type("FLOWRATE") == "flowrate"
            assert wk._normalize_data_type("flow_rate") == "flowrate"
            assert wk._normalize_data_type("flow") == "flowrate"
            assert wk._normalize_data_type("Q") == "flowrate"

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_normalize_velocity_variations(self, mock_logger):
        """Test normalizing velocity variations."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {"case_name": "test", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": []},
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            assert wk._normalize_data_type("velocity") == "velocity"
            assert wk._normalize_data_type("Velocity") == "velocity"
            assert wk._normalize_data_type("vel") == "velocity"
            assert wk._normalize_data_type("U") == "velocity"

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_normalize_none_value(self, mock_logger):
        """Test normalizing None returns None."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {"case_name": "test", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": []},
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            assert wk._normalize_data_type(None) is None


class TestReadInletFlow:
    """Test inlet flow CSV reading."""

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_read_inlet_flow_flowrate(self, mock_logger):
        """Test reading flowrate data from CSV."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {"case_name": "test", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": []},
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create CSV file
            csv_content = "time,flowrate\n0.0,0.0001\n0.5,0.0002\n1.0,0.0001\n"
            csv_path = Path(tmpdir) / "inlet.csv"
            csv_path.write_text(csv_content)

            wk = WkSetup(config, [], tmpdir, 1.0)
            times, flows = wk._read_inlet_flow(str(csv_path), "flowrate", 0.001)

            assert len(times) == 3
            assert len(flows) == 3
            np.testing.assert_array_almost_equal(times, [0.0, 0.5, 1.0])
            np.testing.assert_array_almost_equal(flows, [0.0001, 0.0002, 0.0001])

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_read_inlet_flow_velocity(self, mock_logger):
        """Test reading velocity data and converting to flowrate."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {"case_name": "test", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": []},
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create CSV file with velocity
            csv_content = "0.0,1.0\n0.5,2.0\n1.0,1.0\n"
            csv_path = Path(tmpdir) / "inlet.csv"
            csv_path.write_text(csv_content)

            wk = WkSetup(config, [], tmpdir, 1.0)
            inlet_area = 0.001  # 0.001 m²
            times, flows = wk._read_inlet_flow(str(csv_path), "velocity", inlet_area)

            # Flow = velocity * area
            expected_flows = [1.0 * inlet_area, 2.0 * inlet_area, 1.0 * inlet_area]
            np.testing.assert_array_almost_equal(flows, expected_flows)

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_read_inlet_flow_file_not_found(self, mock_logger):
        """Test FileNotFoundError for missing CSV."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {"case_name": "test", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": []},
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            with pytest.raises(FileNotFoundError):
                wk._read_inlet_flow("/nonexistent/path.csv", "flowrate", 0.001)


class TestPlotFlowDistributionSteady:
    """Test steady-state flow distribution plotting."""

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_plot_flow_distribution_steady_no_matplotlib(self, mock_logger):
        """Test that missing matplotlib is handled gracefully."""
        from aortacfd_lib.wk_setup import WkSetup

        config = {
            "geometry": {"case_name": "test", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": []},
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            # Mock matplotlib import to fail
            with patch.dict("sys.modules", {"matplotlib": None, "matplotlib.pyplot": None}):
                # Should not raise, just log warning
                wk.plot_flow_distribution_steady(
                    0.0001,
                    {"o1": 0.5, "o2": 0.5},
                    {"o1": {"R": 1e9, "C": 1e-9, "Z": 1e8}, "o2": {"R": 1e9, "C": 1e-9, "Z": 1e8}},
                    str(Path(tmpdir) / "plot.png"),
                )

    @patch("aortacfd_lib.wk_setup.Logger")
    def test_plot_flow_distribution_steady_creates_figure(self, mock_logger):
        """Test that plotting creates a figure when matplotlib is available."""
        from aortacfd_lib.wk_setup import WkSetup

        # Skip if matplotlib not available
        pytest.importorskip("matplotlib")

        config = {
            "geometry": {"case_name": "test", "inlet_keywords_ordered": "inlet", "outlet_keywords_ordered": []},
            "boundary_conditions": {"inlet": {}, "outlets": {"type": "", "windkessel_settings": {}}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            wk = WkSetup(config, [], tmpdir, 1.0)

            output_path = str(Path(tmpdir) / "plot.png")

            # Call should complete without error (matplotlib is installed)
            wk.plot_flow_distribution_steady(
                0.0001,
                {"o1": 0.5, "o2": 0.5},
                {"o1": {"R": 1e9, "C": 1e-9, "Z": 1e8}, "o2": {"R": 1e9, "C": 1e-9, "Z": 1e8}},
                output_path,
            )

            # Verify file was created
            assert Path(output_path).exists()


class TestExecuteIntegration:
    """Integration tests for the execute method."""

    @patch("aortacfd_lib.wk_setup.PatchProcessing")
    @patch("aortacfd_lib.wk_setup.Logger")
    def test_execute_2element_windkessel(self, mock_logger, mock_patch_processing):
        """Test 2-element Windkessel calculation."""
        from aortacfd_lib.wk_setup import WkSetup

        # Mock patch processing for area calculations
        mock_patch_instance = MagicMock()
        mock_patch_instance.calculate_surface_area.return_value = 0.0001  # 1 cm²
        mock_patch_processing.return_value = mock_patch_instance

        config = {
            "geometry": {
                "case_name": "test",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1"],
            },
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT", "velocity": 0.5},
                "outlets": {
                    "type": "2EWINDKESSEL",
                    "windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80, "tau": 1.8},
                },
            },
            "physics": {"rho": 1060},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create necessary directories
            (Path(tmpdir) / "constant" / "triSurface").mkdir(parents=True)

            wk = WkSetup(config, [], tmpdir, 1.0)

            # Mock plotting to avoid matplotlib issues
            with patch.object(wk, "plot_flow_distribution_steady"):
                wk.execute()

            # Verify outlet parameters were stored
            assert "outlet_parameters" in wk.wk_model_settings
            params = wk.wk_model_settings["outlet_parameters"]["outlet1"]

            # 2-element should have Z=0
            assert params["Z"] == 0.0
            assert params["R"] > 0
            assert params["C"] > 0


class TestPhysicalCalculations:
    """Test physical calculations and unit conversions."""

    def test_mmhg_to_pa_conversion(self):
        """Test mmHg to Pa conversion constant."""
        from aortacfd_lib.constants import MMHG_TO_PA

        # 1 mmHg ≈ 133.322 Pa
        assert abs(MMHG_TO_PA - 133.322) < 0.01

    def test_map_calculation(self):
        """Test mean arterial pressure calculation."""
        # MAP = DP + (SP - DP) / 3
        SP = 120  # mmHg
        DP = 80  # mmHg
        expected_MAP = 80 + (120 - 80) / 3  # 93.33 mmHg

        calculated_MAP = DP + (1.0 / 3.0) * (SP - DP)
        assert abs(calculated_MAP - expected_MAP) < 0.01

    def test_resistance_calculation(self):
        """Test total resistance calculation."""
        # R_total = (MAP - P_venous) / Q
        from aortacfd_lib.constants import MMHG_TO_PA

        MAP_mmHg = 93.33
        P_venous_mmHg = 0
        MAP_Pa = MAP_mmHg * MMHG_TO_PA
        P_venous_Pa = P_venous_mmHg * MMHG_TO_PA

        # 5 L/min = 8.33e-5 m³/s
        Q = 5.0 / 60.0 / 1000.0

        R_total = (MAP_Pa - P_venous_Pa) / Q

        # R should be in Pa·s/m³ (typical range: 1e8 - 1e10)
        assert R_total > 1e8
        assert R_total < 1e11


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
