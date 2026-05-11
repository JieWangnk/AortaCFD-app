"""
Windkessel Analyzer

Analyzes flow rates and Windkessel parameters from OpenFOAM simulation results
and generates PDF reports with plots.
"""

import numpy as np
import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for server
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path
from typing import Dict, Tuple
import re

from .constants import MMHG_TO_PA


class WindkesselAnalyzer:
    """Analyze and report Windkessel boundary condition behavior."""

    def __init__(self, case_directory: str, config: dict):
        """
        Initialize analyzer.

        Args:
            case_directory: Path to OpenFOAM case directory
            config: Full configuration dictionary
        """
        self.case_dir = Path(case_directory)
        self.config = config
        self.outlet_patches = config.get("geometry", {}).get("outlet_keywords_ordered", [])

    def extract_flow_rates(self) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """
        Extract flow rates at outlets over time from postProcessing data.

        Returns:
            (times, flow_rates) where flow_rates is dict of {outlet_name: flow_array}
        """
        # Check for surfaceFieldValue post-processing
        post_dir = self.case_dir / "postProcessing"

        if not post_dir.exists():
            raise FileNotFoundError(f"No postProcessing directory found at {post_dir}")

        # Find flow rate data directories
        flow_data = {}
        times = None

        for outlet in self.outlet_patches:
            # Look for surfaceFieldValue data
            outlet_dirs = list(post_dir.glob(f"*{outlet}*/*/surfaceFieldValue.dat"))

            if not outlet_dirs:
                # Try alternative location
                outlet_dirs = list(post_dir.glob(f"surfaceFieldValue/{outlet}/*/phi.dat"))

            if outlet_dirs:
                # Read the data file
                data_file = outlet_dirs[0]
                data = np.loadtxt(data_file, comments="#")

                if times is None:
                    times = data[:, 0]

                # Flow rate is typically in column 1 (after time)
                flow_data[outlet] = data[:, 1]

        if times is None or len(flow_data) == 0:
            # Fallback: read from p boundary field files
            times, flow_data = self._extract_from_boundary_fields()

        return times, flow_data

    def _extract_from_boundary_fields(self) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """
        Fallback: Extract flow from boundary field history written by WK BC.

        Returns:
            (times, flow_rates)
        """
        # Get all time directories
        time_dirs = sorted(
            [d for d in self.case_dir.iterdir() if d.is_dir() and d.name.replace(".", "").replace("-", "").isdigit()]
        )

        times = []
        flow_data = {outlet: [] for outlet in self.outlet_patches}

        for time_dir in time_dirs:
            try:
                time_val = float(time_dir.name)
                times.append(time_val)

                # Read pressure file to get q_1 values
                p_file = time_dir / "p"
                if p_file.exists():
                    with open(p_file, "r") as f:
                        content = f.read()

                        for outlet in self.outlet_patches:
                            # Find the outlet section
                            pattern = rf"{outlet}\s*{{.*?q_1\s+([\d\.\-e\+]+)"
                            match = re.search(pattern, content, re.DOTALL)

                            if match:
                                q_val = float(match.group(1))
                                flow_data[outlet].append(q_val)
                            else:
                                flow_data[outlet].append(0.0)
            except:
                continue

        return np.array(times), {k: np.array(v) for k, v in flow_data.items()}

    def generate_report(self, output_dir: str) -> str:
        """
        Generate comprehensive PDF report with Windkessel analysis.

        Args:
            output_dir: Directory to save the PDF report

        Returns:
            Path to generated PDF file
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        pdf_file = output_path / "windkessel_analysis.pdf"

        # Extract data
        try:
            times, flow_rates = self.extract_flow_rates()
        except Exception as e:
            print(f"Warning: Could not extract flow rates: {e}")
            # Create empty report
            times = np.array([0, 1])
            flow_rates = {outlet: np.array([0, 0]) for outlet in self.outlet_patches}

        # Get WK parameters from config
        wk_params = self._get_wk_parameters()

        # Create PDF
        with PdfPages(pdf_file) as pdf:
            # Page 1: Title and parameters
            self._create_title_page(pdf, wk_params)

            # Page 2: Flow rates over time
            if len(times) > 2:
                self._create_flow_rate_plots(pdf, times, flow_rates)

            # Page 3: Flow distribution
            self._create_flow_distribution_plot(pdf, flow_rates)

            # Page 4: Windkessel response analysis
            if len(times) > 2:
                self._create_pressure_analysis_plots(pdf, times)

        print(f"Windkessel analysis report saved to: {pdf_file}")
        return str(pdf_file)

    def _get_wk_parameters(self) -> Dict[str, Dict]:
        """Extract Windkessel parameters from config."""
        params = {}

        # Extract from config - Windkessel parameters are in boundary_conditions.outlets
        bc_config = self.config.get("boundary_conditions", {})
        outlets_config = bc_config.get("outlets", {})

        if outlets_config.get("type", "").upper() == "3EWINDKESSEL":
            wk_params = outlets_config.get("windkessel_params", {})

            for outlet in self.outlet_patches:
                outlet_params = wk_params.get(outlet, {})
                if outlet_params:
                    params[outlet] = {
                        "R": outlet_params.get("R", 0.0),
                        "C": outlet_params.get("C", 0.0),
                        "Z": outlet_params.get("Z", 0.0),
                    }

        return params

    def _create_title_page(self, pdf: PdfPages, wk_params: Dict):
        """Create title page with parameters table."""
        fig = plt.figure(figsize=(11, 8.5))
        fig.suptitle("Windkessel Boundary Condition Analysis", fontsize=16, fontweight="bold")

        # Add text information
        ax = fig.add_subplot(111)
        ax.axis("off")

        # Case information
        case_info = self.config.get("case_info", {})
        geometry = self.config.get("geometry", {})

        info_text = f"""
Case: {geometry.get('case_name', 'Unknown')}
Patient ID: {case_info.get('patient_id', 'N/A')}
Description: {case_info.get('description', 'N/A')}

Solver: {self.config.get('simulation_settings', {}).get('solver_type', 'N/A')}
Analysis Type: {self.config.get('simulation_settings', {}).get('analysis_type', 'N/A')}

Number of Outlets: {len(self.outlet_patches)}
Outlets: {', '.join(self.outlet_patches)}
"""

        ax.text(0.1, 0.8, info_text, transform=ax.transAxes, fontsize=11, verticalalignment="top", family="monospace")

        # Windkessel parameters table
        if wk_params:
            table_text = "\nWindkessel Parameters (SI Units):\n"
            table_text += "=" * 80 + "\n"
            table_text += f"{'Outlet':<12} {'R (Pa·s/m³)':<20} {'C (m³/Pa)':<20} {'Z (Pa·s/m³)':<20}\n"
            table_text += "-" * 80 + "\n"

            for outlet, params in wk_params.items():
                table_text += f"{outlet:<12} {params['R']:<20.4e} {params['C']:<20.4e} {params['Z']:<20.4e}\n"

            table_text += "=" * 80 + "\n"

            # Also show in clinical units
            table_text += "\nWindkessel Parameters (Clinical Units):\n"
            table_text += "=" * 80 + "\n"
            table_text += f"{'Outlet':<12} {'R (mmHg·s/mL)':<20} {'C (mL/mmHg)':<20} {'Z (mmHg·s/mL)':<20}\n"
            table_text += "-" * 80 + "\n"

            for outlet, params in wk_params.items():
                R_clinical = params["R"] / (MMHG_TO_PA * 1e6)
                C_clinical = params["C"] * (MMHG_TO_PA * 1e6)
                Z_clinical = params["Z"] / (MMHG_TO_PA * 1e6)

                table_text += f"{outlet:<12} {R_clinical:<20.4f} {C_clinical:<20.6f} {Z_clinical:<20.4f}\n"

            table_text += "=" * 80

            ax.text(
                0.1, 0.45, table_text, transform=ax.transAxes, fontsize=9, verticalalignment="top", family="monospace"
            )

        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

    def _create_flow_rate_plots(self, pdf: PdfPages, times: np.ndarray, flow_rates: Dict[str, np.ndarray]):
        """Create plots of flow rates vs time."""
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
        fig.suptitle("Outlet Flow Rates Over Time", fontsize=14, fontweight="bold")

        # Plot 1: All outlets on same plot
        ax = axes[0]
        for outlet, flow in flow_rates.items():
            if len(flow) == len(times):
                # Convert to mL/s
                flow_ml_s = flow * 1e6
                ax.plot(times, flow_ml_s, label=outlet, linewidth=2)

        ax.set_xlabel("Time (s)", fontsize=11)
        ax.set_ylabel("Flow Rate (mL/s)", fontsize=11)
        ax.set_title("All Outlets", fontsize=12)
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)

        # Plot 2: Sum of all outlets (should equal inlet)
        ax = axes[1]
        total_flow = np.zeros_like(times)
        for outlet, flow in flow_rates.items():
            if len(flow) == len(times):
                total_flow += flow

        ax.plot(times, total_flow * 1e6, "k-", linewidth=2, label="Total Outlet Flow")
        ax.set_xlabel("Time (s)", fontsize=11)
        ax.set_ylabel("Total Flow Rate (mL/s)", fontsize=11)
        ax.set_title("Sum of All Outlet Flow Rates (Should Match Inlet)", fontsize=12)
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

    def _create_flow_distribution_plot(self, pdf: PdfPages, flow_rates: Dict[str, np.ndarray]):
        """Create pie chart of mean flow distribution."""
        fig, ax = plt.subplots(1, 1, figsize=(11, 8.5))
        fig.suptitle("Mean Flow Distribution Among Outlets", fontsize=14, fontweight="bold")

        # Calculate mean flow for each outlet
        mean_flows = {}
        for outlet, flow in flow_rates.items():
            if len(flow) > 0:
                mean_flows[outlet] = np.mean(np.abs(flow)) * 1e6  # mL/s

        if mean_flows and sum(mean_flows.values()) > 1e-10:
            labels = list(mean_flows.keys())
            sizes = list(mean_flows.values())
            total = sum(sizes)
            percentages = [s / total * 100 for s in sizes]

            colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))

            wedges, texts, autotexts = ax.pie(
                sizes, labels=labels, autopct="%1.1f%%", colors=colors, startangle=90, textprops={"fontsize": 11}
            )

            # Add legend with actual values
            legend_labels = [
                f"{label}: {size:.2f} mL/s ({pct:.1f}%)" for label, size, pct in zip(labels, sizes, percentages)
            ]
            ax.legend(legend_labels, loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))

            ax.axis("equal")
        else:
            # No valid flow data
            ax.axis("off")
            ax.text(
                0.5,
                0.5,
                "No flow rate data available.\nEnsure postProcessing is enabled in controlDict.",
                ha="center",
                va="center",
                fontsize=12,
                transform=ax.transAxes,
            )

        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

    def _create_pressure_analysis_plots(self, pdf: PdfPages, times: np.ndarray):
        """Create pressure evolution plots if data is available."""
        fig = plt.figure(figsize=(11, 8.5))
        fig.suptitle("Windkessel Pressure Analysis", fontsize=14, fontweight="bold")

        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            "Pressure time-series data extraction not yet implemented.\n"
            "See boundary field files for pressure evolution.",
            ha="center",
            va="center",
            fontsize=12,
            transform=ax.transAxes,
        )

        pdf.savefig(fig, bbox_inches="tight")
        plt.close()
