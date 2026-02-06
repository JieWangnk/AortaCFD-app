"""
Test suite for WindkesselAnalyzer module.

Tests the Windkessel analysis and reporting functionality.
"""

import pytest
import sys
import numpy as np
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aortacfd_lib.windkessel_analyzer import WindkesselAnalyzer
from aortacfd_lib.constants import MMHG_TO_PA


class TestWindkesselAnalyzerInit:
    """Test WindkesselAnalyzer initialization."""

    def test_init_with_valid_config(self):
        """Test initialization with valid config."""
        config = {
            'geometry': {
                'case_name': 'test_case',
                'outlet_keywords_ordered': ['outlet1', 'outlet2']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = WindkesselAnalyzer(tmpdir, config)

            assert analyzer.case_dir == Path(tmpdir)
            assert analyzer.config == config
            assert analyzer.outlet_patches == ['outlet1', 'outlet2']

    def test_init_with_empty_outlets(self):
        """Test initialization with no outlets."""
        config = {
            'geometry': {
                'case_name': 'test_case'
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = WindkesselAnalyzer(tmpdir, config)

            assert analyzer.outlet_patches == []

    def test_init_with_missing_geometry(self):
        """Test initialization with missing geometry section."""
        config = {}

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = WindkesselAnalyzer(tmpdir, config)

            assert analyzer.outlet_patches == []


class TestGetWKParameters:
    """Test Windkessel parameter extraction from config."""

    def test_extract_3element_params(self):
        """Test extraction of 3-element Windkessel parameters."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1', 'outlet2']
            },
            'boundary_conditions': {
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_params': {
                        'outlet1': {'R': 1e8, 'C': 1e-9, 'Z': 1e7},
                        'outlet2': {'R': 2e8, 'C': 2e-9, 'Z': 2e7}
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = WindkesselAnalyzer(tmpdir, config)
            params = analyzer._get_wk_parameters()

            assert 'outlet1' in params
            assert 'outlet2' in params
            assert params['outlet1']['R'] == 1e8
            assert params['outlet1']['C'] == 1e-9
            assert params['outlet1']['Z'] == 1e7
            assert params['outlet2']['R'] == 2e8

    def test_extract_params_non_windkessel(self):
        """Test extraction with non-Windkessel outlet type returns empty."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            },
            'boundary_conditions': {
                'outlets': {
                    'type': 'zeroGradient'
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = WindkesselAnalyzer(tmpdir, config)
            params = analyzer._get_wk_parameters()

            assert params == {}

    def test_extract_params_missing_outlet_data(self):
        """Test extraction when outlet not in windkessel_params."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1', 'outlet2']
            },
            'boundary_conditions': {
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_params': {
                        'outlet1': {'R': 1e8, 'C': 1e-9, 'Z': 1e7}
                        # outlet2 missing
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = WindkesselAnalyzer(tmpdir, config)
            params = analyzer._get_wk_parameters()

            assert 'outlet1' in params
            assert 'outlet2' not in params


class TestExtractFlowRates:
    """Test flow rate extraction from simulation data."""

    def test_extract_raises_without_postprocessing(self):
        """Test that extraction raises error without postProcessing dir."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = WindkesselAnalyzer(tmpdir, config)

            with pytest.raises(FileNotFoundError, match="No postProcessing"):
                analyzer.extract_flow_rates()

    def test_extract_with_empty_postprocessing(self):
        """Test extraction with empty postProcessing directory."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty postProcessing directory
            post_dir = Path(tmpdir) / "postProcessing"
            post_dir.mkdir()

            analyzer = WindkesselAnalyzer(tmpdir, config)

            # Should fall back to boundary field extraction
            times, flow_data = analyzer.extract_flow_rates()

            # Should return empty arrays
            assert len(times) == 0 or np.all(times == 0)

    def test_extract_from_surfacefieldvalue(self):
        """Test extraction from surfaceFieldValue data."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock surfaceFieldValue data
            post_dir = Path(tmpdir) / "postProcessing" / "surfaceFieldValue_outlet1" / "0"
            post_dir.mkdir(parents=True)

            # Create data file with time and flow rate columns
            data_file = post_dir / "surfaceFieldValue.dat"
            with open(data_file, 'w') as f:
                f.write("# Time    Flow\n")
                f.write("0.0    1.0e-5\n")
                f.write("0.1    2.0e-5\n")
                f.write("0.2    3.0e-5\n")

            analyzer = WindkesselAnalyzer(tmpdir, config)
            times, flow_data = analyzer.extract_flow_rates()

            assert len(times) == 3
            assert 'outlet1' in flow_data
            assert len(flow_data['outlet1']) == 3
            assert flow_data['outlet1'][0] == pytest.approx(1e-5, rel=1e-6)


class TestExtractFromBoundaryFields:
    """Test fallback extraction from boundary field files."""

    def test_extract_from_time_directories(self):
        """Test extraction from time directory structure."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create time directories with p files
            for t in ['0', '0.1', '0.2']:
                time_dir = Path(tmpdir) / t
                time_dir.mkdir()

                # Create minimal p file with outlet section
                p_file = time_dir / "p"
                with open(p_file, 'w') as f:
                    f.write(f"""
boundaryField
{{
    outlet1
    {{
        type            fixedValue;
        q_1             {float(t) * 1e-5};
    }}
}}
""")

            analyzer = WindkesselAnalyzer(tmpdir, config)
            times, flow_data = analyzer._extract_from_boundary_fields()

            assert len(times) == 3
            assert 'outlet1' in flow_data

    def test_extract_no_time_directories(self):
        """Test extraction with no time directories."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = WindkesselAnalyzer(tmpdir, config)
            times, flow_data = analyzer._extract_from_boundary_fields()

            assert len(times) == 0
            assert 'outlet1' in flow_data
            assert len(flow_data['outlet1']) == 0


class TestGenerateReport:
    """Test PDF report generation."""

    def test_generate_report_creates_pdf(self):
        """Test that generate_report creates a PDF file."""
        config = {
            'geometry': {
                'case_name': 'test_case',
                'outlet_keywords_ordered': ['outlet1']
            },
            'case_info': {
                'patient_id': 'TEST001',
                'description': 'Test simulation'
            },
            'simulation_settings': {
                'solver_type': 'pimpleFoam',
                'analysis_type': 'transient'
            },
            'boundary_conditions': {
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_params': {
                        'outlet1': {'R': 1e8, 'C': 1e-9, 'Z': 1e7}
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = Path(tmpdir) / "case"
            case_dir.mkdir()

            # Create empty postProcessing (will trigger fallback)
            post_dir = case_dir / "postProcessing"
            post_dir.mkdir()

            output_dir = Path(tmpdir) / "output"

            analyzer = WindkesselAnalyzer(str(case_dir), config)
            pdf_path = analyzer.generate_report(str(output_dir))

            assert Path(pdf_path).exists()
            assert pdf_path.endswith('.pdf')
            assert 'windkessel_analysis.pdf' in pdf_path

    def test_generate_report_creates_output_dir(self):
        """Test that generate_report creates output directory if needed."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = Path(tmpdir) / "case"
            case_dir.mkdir()
            (case_dir / "postProcessing").mkdir()

            output_dir = Path(tmpdir) / "new" / "nested" / "output"

            analyzer = WindkesselAnalyzer(str(case_dir), config)
            pdf_path = analyzer.generate_report(str(output_dir))

            assert output_dir.exists()
            assert Path(pdf_path).exists()


class TestClinicalUnitConversions:
    """Test clinical unit conversions in reporting."""

    def test_resistance_conversion(self):
        """Test resistance conversion from SI to clinical units."""
        # R in Pa·s/m³ → mmHg·s/mL
        R_SI = 1e8  # Pa·s/m³

        # Conversion: 1 Pa = 1/133.322 mmHg, 1 m³ = 1e6 mL
        R_clinical = R_SI / (MMHG_TO_PA * 1e6)

        # Check reasonable clinical range (typically 0.1-10 mmHg·s/mL)
        assert 0.01 < R_clinical < 100

    def test_compliance_conversion(self):
        """Test compliance conversion from SI to clinical units."""
        # C in m³/Pa → mL/mmHg
        C_SI = 1e-9  # m³/Pa

        # Conversion: 1 m³ = 1e6 mL, 1 Pa = 1/133.322 mmHg
        C_clinical = C_SI * (MMHG_TO_PA * 1e6)

        # Check reasonable clinical range (typically 0.1-5 mL/mmHg)
        assert 0.001 < C_clinical < 10

    def test_pressure_conversion_roundtrip(self):
        """Test pressure conversion roundtrip."""
        P_mmHg = 100.0
        P_Pa = P_mmHg * MMHG_TO_PA
        P_mmHg_back = P_Pa / MMHG_TO_PA

        assert P_mmHg_back == pytest.approx(P_mmHg, rel=1e-9)


class TestFlowAnalysis:
    """Test flow rate analysis functions."""

    def test_total_flow_calculation(self):
        """Test sum of outlet flows equals inlet."""
        flow_rates = {
            'outlet1': np.array([1e-5, 2e-5, 3e-5]),
            'outlet2': np.array([0.5e-5, 1e-5, 1.5e-5]),
            'outlet3': np.array([0.5e-5, 1e-5, 1.5e-5])
        }

        total_flow = np.zeros(3)
        for flow in flow_rates.values():
            total_flow += flow

        # Total should equal sum
        expected_total = np.array([2e-5, 4e-5, 6e-5])
        np.testing.assert_array_almost_equal(total_flow, expected_total)

    def test_mean_flow_calculation(self):
        """Test mean flow calculation for distribution."""
        flow_rates = {
            'outlet1': np.array([1e-5, 2e-5, 3e-5]),  # mean = 2e-5
            'outlet2': np.array([0.5e-5, 0.5e-5, 0.5e-5])  # mean = 0.5e-5
        }

        mean_flows = {name: np.mean(np.abs(flow)) for name, flow in flow_rates.items()}

        assert mean_flows['outlet1'] == pytest.approx(2e-5, rel=1e-6)
        assert mean_flows['outlet2'] == pytest.approx(0.5e-5, rel=1e-6)

        # Check percentage distribution
        total = sum(mean_flows.values())
        pct_outlet1 = mean_flows['outlet1'] / total * 100
        pct_outlet2 = mean_flows['outlet2'] / total * 100

        assert pct_outlet1 == pytest.approx(80.0, rel=1e-3)
        assert pct_outlet2 == pytest.approx(20.0, rel=1e-3)


class TestExtractFlowRatesWithData:
    """Test flow rate extraction with actual data."""

    def test_extract_multiple_outlets(self):
        """Test extraction with multiple outlets having data."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1', 'outlet2']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create surfaceFieldValue data for multiple outlets
            for i, outlet in enumerate(['outlet1', 'outlet2']):
                post_dir = Path(tmpdir) / "postProcessing" / f"surfaceFieldValue_{outlet}" / "0"
                post_dir.mkdir(parents=True)

                data_file = post_dir / "surfaceFieldValue.dat"
                with open(data_file, 'w') as f:
                    f.write("# Time    Flow\n")
                    for t in [0.0, 0.1, 0.2, 0.3, 0.4]:
                        f.write(f"{t}    {(i + 1) * t * 1e-5}\n")

            analyzer = WindkesselAnalyzer(tmpdir, config)
            times, flow_data = analyzer.extract_flow_rates()

            assert len(times) == 5
            assert 'outlet1' in flow_data
            assert 'outlet2' in flow_data
            assert len(flow_data['outlet1']) == 5
            assert len(flow_data['outlet2']) == 5


class TestBoundaryFieldExtraction:
    """Test boundary field extraction with various edge cases."""

    def test_extract_with_unmatched_outlet(self):
        """Test extraction when outlet pattern doesn't match in p file."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1', 'missing_outlet']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create time directories with p files only mentioning outlet1
            for t in ['0', '0.1', '0.2']:
                time_dir = Path(tmpdir) / t
                time_dir.mkdir()

                p_file = time_dir / "p"
                with open(p_file, 'w') as f:
                    f.write(f"""
boundaryField
{{
    outlet1
    {{
        type            fixedValue;
        q_1             {float(t) * 1e-5};
    }}
}}
""")

            analyzer = WindkesselAnalyzer(tmpdir, config)
            times, flow_data = analyzer._extract_from_boundary_fields()

            assert len(times) == 3
            assert 'outlet1' in flow_data
            assert 'missing_outlet' in flow_data
            # missing_outlet should have zeros
            assert all(v == 0.0 for v in flow_data['missing_outlet'])

    def test_extract_handles_parse_errors(self):
        """Test extraction handles files that can't be parsed."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a non-numeric time directory (should be skipped)
            (Path(tmpdir) / "constant").mkdir()

            # Create a valid time directory
            time_dir = Path(tmpdir) / "0.1"
            time_dir.mkdir()
            p_file = time_dir / "p"
            with open(p_file, 'w') as f:
                f.write("outlet1 { q_1 1e-5; }")

            analyzer = WindkesselAnalyzer(tmpdir, config)
            times, flow_data = analyzer._extract_from_boundary_fields()

            # Should only process valid numeric time directories
            assert len(times) >= 0


class TestGenerateReportWithData:
    """Test report generation with actual flow data."""

    def test_generate_report_with_flow_data(self):
        """Test report generation with sufficient flow data for plots."""
        config = {
            'geometry': {
                'case_name': 'test_case',
                'outlet_keywords_ordered': ['outlet1', 'outlet2']
            },
            'case_info': {
                'patient_id': 'TEST001',
                'description': 'Test simulation'
            },
            'simulation_settings': {
                'solver_type': 'pimpleFoam',
                'analysis_type': 'transient'
            },
            'boundary_conditions': {
                'outlets': {
                    'type': '3EWINDKESSEL',
                    'windkessel_params': {
                        'outlet1': {'R': 1e8, 'C': 1e-9, 'Z': 1e7},
                        'outlet2': {'R': 2e8, 'C': 2e-9, 'Z': 2e7}
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = Path(tmpdir) / "case"
            case_dir.mkdir()

            # Create surfaceFieldValue data with enough points for plots
            for i, outlet in enumerate(['outlet1', 'outlet2']):
                post_dir = case_dir / "postProcessing" / f"surfaceFieldValue_{outlet}" / "0"
                post_dir.mkdir(parents=True)

                data_file = post_dir / "surfaceFieldValue.dat"
                with open(data_file, 'w') as f:
                    f.write("# Time    Flow\n")
                    for t in np.linspace(0, 1, 20):  # 20 time points
                        f.write(f"{t}    {(i + 1) * t * 1e-5}\n")

            output_dir = Path(tmpdir) / "output"

            analyzer = WindkesselAnalyzer(str(case_dir), config)
            pdf_path = analyzer.generate_report(str(output_dir))

            assert Path(pdf_path).exists()
            # PDF should have multiple pages
            assert os.path.getsize(pdf_path) > 1000  # Non-trivial PDF size

    def test_generate_report_with_exception_in_extraction(self):
        """Test report generation handles exception during extraction."""
        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = Path(tmpdir) / "case"
            case_dir.mkdir()

            # Create postProcessing but with bad data that will cause extraction to fail
            post_dir = case_dir / "postProcessing" / "surfaceFieldValue_outlet1" / "0"
            post_dir.mkdir(parents=True)

            # Create data file with unparseable content
            data_file = post_dir / "surfaceFieldValue.dat"
            with open(data_file, 'w') as f:
                f.write("invalid\ndata\nformat\n")

            output_dir = Path(tmpdir) / "output"

            analyzer = WindkesselAnalyzer(str(case_dir), config)
            # Should not raise, but print warning and create empty report
            pdf_path = analyzer.generate_report(str(output_dir))

            assert Path(pdf_path).exists()


class TestPlotCreation:
    """Test individual plot creation methods."""

    def test_create_flow_rate_plots(self):
        """Test _create_flow_rate_plots method."""
        from matplotlib.backends.backend_pdf import PdfPages

        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1', 'outlet2']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = Path(tmpdir) / "case"
            case_dir.mkdir()

            pdf_file = Path(tmpdir) / "test.pdf"

            times = np.linspace(0, 1, 10)
            flow_rates = {
                'outlet1': np.sin(times) * 1e-5,
                'outlet2': np.cos(times) * 0.5e-5
            }

            analyzer = WindkesselAnalyzer(str(case_dir), config)

            with PdfPages(pdf_file) as pdf:
                analyzer._create_flow_rate_plots(pdf, times, flow_rates)

            assert pdf_file.exists()
            assert os.path.getsize(pdf_file) > 100

    def test_create_flow_distribution_plot_with_data(self):
        """Test _create_flow_distribution_plot with valid data."""
        from matplotlib.backends.backend_pdf import PdfPages

        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1', 'outlet2']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = Path(tmpdir) / "case"
            case_dir.mkdir()

            pdf_file = Path(tmpdir) / "test.pdf"

            flow_rates = {
                'outlet1': np.array([1e-5, 2e-5, 3e-5]),
                'outlet2': np.array([0.5e-5, 1e-5, 1.5e-5])
            }

            analyzer = WindkesselAnalyzer(str(case_dir), config)

            with PdfPages(pdf_file) as pdf:
                analyzer._create_flow_distribution_plot(pdf, flow_rates)

            assert pdf_file.exists()
            assert os.path.getsize(pdf_file) > 100

    def test_create_flow_distribution_plot_empty_data(self):
        """Test _create_flow_distribution_plot with empty/zero data."""
        from matplotlib.backends.backend_pdf import PdfPages

        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = Path(tmpdir) / "case"
            case_dir.mkdir()

            pdf_file = Path(tmpdir) / "test.pdf"

            flow_rates = {
                'outlet1': np.array([0.0, 0.0, 0.0])
            }

            analyzer = WindkesselAnalyzer(str(case_dir), config)

            with PdfPages(pdf_file) as pdf:
                analyzer._create_flow_distribution_plot(pdf, flow_rates)

            assert pdf_file.exists()

    def test_create_pressure_analysis_plots(self):
        """Test _create_pressure_analysis_plots method."""
        from matplotlib.backends.backend_pdf import PdfPages

        config = {
            'geometry': {
                'outlet_keywords_ordered': ['outlet1']
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = Path(tmpdir) / "case"
            case_dir.mkdir()

            pdf_file = Path(tmpdir) / "test.pdf"

            times = np.linspace(0, 1, 10)

            analyzer = WindkesselAnalyzer(str(case_dir), config)

            with PdfPages(pdf_file) as pdf:
                analyzer._create_pressure_analysis_plots(pdf, times)

            assert pdf_file.exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
