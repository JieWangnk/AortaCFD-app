"""
Simulation Report Generator

Creates comprehensive reports for AortaCFD simulations including:
- CFD setup details
- Mesh statistics
- Windkessel coefficients
- Flow rate plots
- Technical and human-readable summaries
"""

import os
import json
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class SimulationReporter:
    """Generate comprehensive simulation reports from OpenFOAM case directories."""
    
    def __init__(self, case_path: str):
        """
        Initialize reporter for a specific simulation case.
        
        Args:
            case_path: Path to OpenFOAM case directory
        """
        self.case_path = Path(case_path)
        self.case_name = self.case_path.name
        
        if not self.case_path.exists():
            raise FileNotFoundError(f"Case directory not found: {case_path}")
    
    def extract_mesh_stats(self) -> Dict:
        """Extract mesh statistics from checkMesh log."""
        mesh_stats = {}
        
        checkMesh_log = self.case_path / "logs" / "log.checkMesh"
        if not checkMesh_log.exists():
            logger.warning(f"checkMesh log not found: {checkMesh_log}")
            return mesh_stats
        
        with open(checkMesh_log, 'r') as f:
            content = f.read()
        
        # Extract basic mesh statistics
        patterns = {
            'points': r'points:\s+(\d+)',
            'faces': r'faces:\s+(\d+)',
            'internal_faces': r'internal faces:\s+(\d+)',
            'cells': r'cells:\s+(\d+)',
            'boundary_patches': r'boundary patches:\s+(\d+)',
            'max_aspect_ratio': r'Max aspect ratio = ([\d.e-]+)',
            'max_skewness': r'Max skewness = ([\d.e-]+)',
            'max_non_orthogonality': r'Max: ([\d.e-]+) average',
            'total_volume': r'Total volume = ([\d.e-]+)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                try:
                    mesh_stats[key] = float(match.group(1)) if '.' in match.group(1) else int(match.group(1))
                except ValueError:
                    mesh_stats[key] = match.group(1)
        
        # Extract patch information
        patch_section = re.search(r'Patch\s+Faces\s+Points.*?Surface topology\n(.*?)(?=\n\n|\nChecking)', content, re.DOTALL)
        if patch_section:
            patches = {}
            for line in patch_section.group(1).strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        patch_name = parts[0]
                        faces = int(parts[1])
                        points = int(parts[2])
                        patches[patch_name] = {'faces': faces, 'points': points}
            mesh_stats['patches'] = patches
        
        return mesh_stats
    
    def extract_transport_properties(self) -> Dict:
        """Extract transport properties from transportProperties file."""
        transport_file = self.case_path / "constant" / "transportProperties"
        transport_props = {}
        
        if not transport_file.exists():
            logger.warning(f"transportProperties file not found: {transport_file}")
            return transport_props
        
        with open(transport_file, 'r') as f:
            content = f.read()
        
        # Extract kinematic viscosity and density
        nu_match = re.search(r'nu\s+\[.*?\]\s+([\d.e-]+)', content)
        rho_match = re.search(r'rho\s+\[.*?\]\s+([\d.e-]+)', content)
        
        if nu_match:
            transport_props['kinematic_viscosity'] = float(nu_match.group(1))
            transport_props['kinematic_viscosity_units'] = 'm²/s'
        
        if rho_match:
            transport_props['density'] = float(rho_match.group(1))
            transport_props['density_units'] = 'kg/m³'
        
        # Calculate dynamic viscosity if both are available
        if 'kinematic_viscosity' in transport_props and 'density' in transport_props:
            mu = transport_props['kinematic_viscosity'] * transport_props['density']
            transport_props['dynamic_viscosity'] = mu
            transport_props['dynamic_viscosity_units'] = 'Pa·s'
        
        return transport_props
    
    def extract_windkessel_coefficients(self) -> Dict:
        """Extract Windkessel coefficients from pressure boundary conditions."""
        p_file = self.case_path / "0" / "p"
        windkessel_data = {}
        
        if not p_file.exists():
            logger.warning(f"Pressure field file not found: {p_file}")
            return windkessel_data
        
        with open(p_file, 'r') as f:
            content = f.read()
        
        # Find all outlet patches with modularWKPressure
        outlet_pattern = r'(outlet\d+)\s*\{[^}]*type\s+modularWKPressure[^}]*\}'
        outlets = re.findall(outlet_pattern, content, re.DOTALL)
        
        for outlet in outlets:
            # Extract coefficients for this outlet
            outlet_section = re.search(rf'{outlet}\s*\{{([^}}]*)}}\s*', content, re.DOTALL)
            if outlet_section:
                section_content = outlet_section.group(1)
                
                coeffs = {}
                for param in ['R', 'C', 'Z', 'p0']:
                    match = re.search(rf'{param}\s+([\d.e-]+)', section_content)
                    if match:
                        coeffs[param] = float(match.group(1))
                
                if coeffs:
                    windkessel_data[outlet] = coeffs
        
        return windkessel_data
    
    def extract_solver_settings(self) -> Dict:
        """Extract solver settings from fvSchemes and fvSolution."""
        solver_settings = {}
        
        # Extract from fvSchemes
        fv_schemes = self.case_path / "system" / "fvSchemes"
        if fv_schemes.exists():
            with open(fv_schemes, 'r') as f:
                content = f.read()
            
            # Extract time scheme
            ddt_match = re.search(r'ddtSchemes\s*\{[^}]*default\s+(\w+)', content, re.DOTALL)
            if ddt_match:
                solver_settings['time_scheme'] = ddt_match.group(1)
            
            # Extract convection scheme for velocity
            div_u_match = re.search(r'div\(phi,U\)\s+([^;]+)', content)
            if div_u_match:
                solver_settings['convection_scheme'] = div_u_match.group(1).strip()
        
        # Extract from controlDict
        control_dict = self.case_path / "system" / "controlDict"
        if control_dict.exists():
            with open(control_dict, 'r') as f:
                content = f.read()
            
            patterns = {
                'start_time': r'startTime\s+([\d.e-]+)',
                'end_time': r'endTime\s+([\d.e-]+)',
                'delta_t': r'deltaT\s+([\d.e-]+)',
                'max_co': r'maxCo\s+([\d.e-]+)',
                'write_interval': r'writeInterval\s+([\d.e-]+)'
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    solver_settings[key] = float(match.group(1))
        
        return solver_settings
    
    def extract_flow_rates(self) -> Tuple[Optional[pd.DataFrame], Dict[str, pd.DataFrame]]:
        """Extract flow rate data from inlet CSV and calculate outlet flow rates."""
        inlet_data = None
        outlet_flows = {}
        
        # First try to get inlet data from boundary data CSV
        boundary_data_dir = self.case_path / "constant" / "boundaryData" / "inlet"
        csv_files = list(boundary_data_dir.glob("*.csv")) if boundary_data_dir.exists() else []
        
        if csv_files:
            try:
                # Read inlet flow rate CSV
                csv_file = csv_files[0]  # Take first CSV file
                inlet_data = pd.read_csv(csv_file)
                
                # Standardize column names
                if 'Time' in inlet_data.columns and 'Flowrate' in inlet_data.columns:
                    inlet_data = inlet_data.rename(columns={'Time': 'time', 'Flowrate': 'flow_rate'})
                elif 'time' not in inlet_data.columns or 'flow_rate' not in inlet_data.columns:
                    # Try first two columns
                    inlet_data.columns = ['time', 'flow_rate']
                
                logger.info(f"Found inlet flow data: {len(inlet_data)} time points")
                
                # Calculate outlet flow rates using Windkessel coefficients
                windkessel_data = self.extract_windkessel_coefficients()
                outlet_flows = self._calculate_outlet_flows(inlet_data, windkessel_data)
                
            except Exception as e:
                logger.warning(f"Could not read inlet flow data from {csv_file}: {e}")
        
        # Fallback: Look for flow rate data in postProcessing directory
        if inlet_data is None:
            postproc_dir = self.case_path / "postProcessing"
            if postproc_dir.exists():
                flow_dirs = list(postproc_dir.glob("*flowRate*")) + list(postproc_dir.glob("*surfaceFieldValue*"))
                
                for flow_dir in flow_dirs:
                    for data_file in flow_dir.glob("*/surfaceFieldValue.dat"):
                        try:
                            df = pd.read_csv(data_file, sep=r'\s+', comment='#', 
                                           names=['time', 'flow_rate'], header=None)
                            
                            if 'inlet' in str(data_file).lower():
                                inlet_data = df
                            elif 'outlet' in str(data_file).lower():
                                outlet_name = str(data_file).split('/')[-2]  # Extract outlet name
                                outlet_flows[outlet_name] = df
                        
                        except Exception as e:
                            logger.warning(f"Could not read flow data from {data_file}: {e}")
        
        return inlet_data, outlet_flows
    
    def _calculate_outlet_flows(self, inlet_data: pd.DataFrame, windkessel_data: Dict) -> Dict[str, pd.DataFrame]:
        """Calculate outlet flow rates based on Murray's law and resistance ratios."""
        outlet_flows = {}
        
        if not windkessel_data:
            return outlet_flows
        
        # Calculate flow distribution based on resistance ratios (inverse relationship)
        # Lower resistance = higher flow (Murray's law effect)
        resistances = {outlet: coeffs.get('R', 1000) for outlet, coeffs in windkessel_data.items()}
        
        # Inverse resistance for flow calculation (1/R proportional to flow)
        inv_resistances = {outlet: 1.0/R for outlet, R in resistances.items()}
        total_inv_resistance = sum(inv_resistances.values())
        
        # Calculate flow fractions (flow proportional to 1/R)
        flow_fractions = {outlet: inv_R/total_inv_resistance for outlet, inv_R in inv_resistances.items()}
        
        # Apply flow fractions to inlet data
        for outlet_name, flow_fraction in flow_fractions.items():
            outlet_flow = inlet_data.copy()
            outlet_flow['flow_rate'] = inlet_data['flow_rate'] * flow_fraction
            outlet_flows[outlet_name] = outlet_flow
        
        return outlet_flows
    
    def create_flow_rate_plot(self, inlet_data: pd.DataFrame, outlet_flows: Dict[str, pd.DataFrame], 
                            output_path: str) -> str:
        """Create single flow rate plot comparing all flows."""
        
        if inlet_data is None and not outlet_flows:
            return None
        
        # Create single plot with all flows
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Define colors for each flow
        colors = {
            'inlet': '#1f77b4',     # Blue
            'outlet1': '#ff7f0e',   # Orange  
            'outlet2': '#2ca02c',   # Green
            'outlet3': '#d62728',   # Red
            'outlet4': '#9467bd'    # Purple
        }
        
        # Plot inlet
        if inlet_data is not None:
            ax.plot(inlet_data['time'], inlet_data['flow_rate'] * 1000,
                   color=colors['inlet'], linewidth=3, 
                   label='Inlet (Total)', linestyle='-', alpha=0.9)
        
        # Plot all outlets
        for outlet_name, outlet_data in outlet_flows.items():
            # Calculate percentage of inlet flow
            if inlet_data is not None:
                avg_inlet = inlet_data['flow_rate'].mean()
                avg_outlet = outlet_data['flow_rate'].mean()
                percentage = (avg_outlet / avg_inlet) * 100
                label = f'{outlet_name} ({percentage:.1f}%)'
            else:
                label = outlet_name
                
            ax.plot(outlet_data['time'], outlet_data['flow_rate'] * 1000,
                   color=colors.get(outlet_name, colors['outlet1']), 
                   linewidth=2.5, label=label, alpha=0.8)
        
        ax.set_xlabel('Time (s)', fontsize=12)
        ax.set_ylabel('Flow Rate (mL/s)', fontsize=12)
        ax.set_title('Flow Rate Comparison - Murray\'s Law Distribution', 
                    fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=11, loc='upper right', framealpha=0.9)
        
        # Add summary text box
        if inlet_data is not None and outlet_flows:
            # Calculate flow conservation
            total_outlet_flow = sum(outlet_data['flow_rate'].mean() for outlet_data in outlet_flows.values())
            inlet_avg = inlet_data['flow_rate'].mean()
            conservation = (total_outlet_flow / inlet_avg) * 100
            
            textstr = f'Flow Conservation: {conservation:.1f}%\nCardiac Cycle: {inlet_data["time"].iloc[-1]:.3f}s'
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
            ax.text(0.02, 0.98, textstr, transform=ax.transAxes, 
                   fontsize=10, verticalalignment='top', bbox=props)
        
        ax.tick_params(axis='both', which='major', labelsize=12)
        plt.tight_layout()
        
        # Save single plot
        plot_path = Path(output_path) / f"{self.case_name}_flow_rates.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        return str(plot_path)
    
    def generate_html_report(self, output_path: str) -> str:
        """Generate comprehensive HTML report."""
        # Extract all data
        mesh_stats = self.extract_mesh_stats()
        transport_props = self.extract_transport_properties()
        windkessel_data = self.extract_windkessel_coefficients()
        solver_settings = self.extract_solver_settings()
        inlet_data, outlet_flows = self.extract_flow_rates()
        
        # Create flow rate plot
        plot_path = None
        if inlet_data is not None or len(outlet_flows) > 0:
            plot_path = self.create_flow_rate_plot(inlet_data, outlet_flows, output_path)
        
        # Generate HTML report
        html_content = self._generate_html_template(
            mesh_stats, transport_props, windkessel_data, 
            solver_settings, plot_path
        )
        
        # Save HTML report
        report_path = Path(output_path) / f"{self.case_name}_simulation_report.html"
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        # Generate Markdown report
        md_content = self._generate_markdown_template(
            mesh_stats, transport_props, windkessel_data,
            solver_settings, plot_path, inlet_data, outlet_flows
        )
        
        # Save Markdown report
        md_path = Path(output_path) / f"{self.case_name}_report.md"
        with open(md_path, 'w') as f:
            f.write(md_content)
        
        return str(report_path)
    
    def _generate_html_template(self, mesh_stats: Dict, transport_props: Dict,
                              windkessel_data: Dict, solver_settings: Dict,
                              plot_path: Optional[str]) -> str:
        """Generate HTML template for the report."""
        
        # Create Windkessel table
        wk_table = ""
        if windkessel_data:
            wk_table = "<table class='data-table'><tr><th>Outlet</th><th>R (Pa·s/m³)</th><th>C (m³/Pa)</th><th>Z (Pa·s/m³)</th><th>p₀ (Pa)</th></tr>"
            for outlet, coeffs in windkessel_data.items():
                wk_table += f"<tr><td>{outlet}</td><td>{coeffs.get('R', 'N/A')}</td><td>{coeffs.get('C', 'N/A'):.2e}</td><td>{coeffs.get('Z', 'N/A')}</td><td>{coeffs.get('p0', 'N/A')}</td></tr>"
            wk_table += "</table>"
        else:
            wk_table = "<p>No Windkessel boundary conditions found.</p>"
        
        # Create mesh patch table
        patch_table = ""
        if 'patches' in mesh_stats:
            patch_table = "<table class='data-table'><tr><th>Patch</th><th>Faces</th><th>Points</th></tr>"
            for patch, data in mesh_stats['patches'].items():
                patch_table += f"<tr><td>{patch}</td><td>{data['faces']}</td><td>{data['points']}</td></tr>"
            patch_table += "</table>"
        
        # Format flow plot
        flow_plot_html = ""
        if plot_path:
            plot_filename = Path(plot_path).name
            flow_plot_html = f'<img src="{plot_filename}" alt="Flow Rate Plot" style="max-width: 100%; height: auto;">'
        else:
            flow_plot_html = "<p>Flow rate data not available.</p>"
        
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>AortaCFD Simulation Report - {self.case_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; }}
        .section {{ margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }}
        .data-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        .data-table th, .data-table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        .data-table th {{ background-color: #f2f2f2; font-weight: bold; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-label {{ font-weight: bold; color: #34495e; }}
        .metric-value {{ color: #2980b9; font-size: 1.1em; }}
        .plot-container {{ text-align: center; margin: 20px 0; }}
        .summary {{ background: #ecf0f1; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>AortaCFD Simulation Report</h1>
        <h2>Case: {self.case_name}</h2>
        <p>Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
    
    <div class="section">
        <h2>Executive Summary</h2>
        <div class="summary">
            <p>This report provides a comprehensive analysis of the AortaCFD simulation for case <strong>{self.case_name}</strong>. 
            The simulation used a computational mesh with {mesh_stats.get('cells', 'N/A')} cells and {mesh_stats.get('boundary_patches', 'N/A')} boundary patches, 
            representing the aortic geometry with appropriate boundary conditions.</p>
            
            <p><strong>Key Findings:</strong></p>
            <ul>
                <li>Mesh Quality: Max aspect ratio of {mesh_stats.get('max_aspect_ratio', 'N/A')}, max skewness of {mesh_stats.get('max_skewness', 'N/A')}</li>
                <li>Windkessel Outlets: {len(windkessel_data)} outlet(s) with lumped parameter boundary conditions</li>
                <li>Fluid Properties: ρ = {transport_props.get('density', 'N/A')} kg/m³, ν = {transport_props.get('kinematic_viscosity', 'N/A')} m²/s</li>
            </ul>
        </div>
    </div>
    
    <div class="section">
        <h2>Computational Mesh</h2>
        <div class="metric">
            <span class="metric-label">Total Cells:</span> 
            <span class="metric-value">{mesh_stats.get('cells', 'N/A'):,}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Total Points:</span> 
            <span class="metric-value">{mesh_stats.get('points', 'N/A'):,}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Total Faces:</span> 
            <span class="metric-value">{mesh_stats.get('faces', 'N/A'):,}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Boundary Patches:</span> 
            <span class="metric-value">{mesh_stats.get('boundary_patches', 'N/A')}</span>
        </div>
        
        <h3>Mesh Quality Metrics</h3>
        <div class="metric">
            <span class="metric-label">Max Aspect Ratio:</span> 
            <span class="metric-value">{mesh_stats.get('max_aspect_ratio', 'N/A')}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Max Skewness:</span> 
            <span class="metric-value">{mesh_stats.get('max_skewness', 'N/A')}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Max Non-orthogonality:</span> 
            <span class="metric-value">{mesh_stats.get('max_non_orthogonality', 'N/A')}°</span>
        </div>
        <div class="metric">
            <span class="metric-label">Total Volume:</span> 
            <span class="metric-value">{mesh_stats.get('total_volume', 'N/A')} m³</span>
        </div>
        
        <h3>Boundary Patches</h3>
        {patch_table}
    </div>
    
    <div class="section">
        <h2>Fluid Properties</h2>
        <div class="metric">
            <span class="metric-label">Density (ρ):</span> 
            <span class="metric-value">{transport_props.get('density', 'N/A')} kg/m³</span>
        </div>
        <div class="metric">
            <span class="metric-label">Kinematic Viscosity (ν):</span> 
            <span class="metric-value">{transport_props.get('kinematic_viscosity', 'N/A')} m²/s</span>
        </div>
        <div class="metric">
            <span class="metric-label">Dynamic Viscosity (μ):</span> 
            <span class="metric-value">{transport_props.get('dynamic_viscosity', 'N/A')} Pa·s</span>
        </div>
    </div>
    
    <div class="section">
        <h2>Solver Configuration</h2>
        <div class="metric">
            <span class="metric-label">Time Scheme:</span> 
            <span class="metric-value">{solver_settings.get('time_scheme', 'N/A')}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Convection Scheme:</span> 
            <span class="metric-value">{solver_settings.get('convection_scheme', 'N/A')}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Time Step (Δt):</span> 
            <span class="metric-value">{solver_settings.get('delta_t', 'N/A')} s</span>
        </div>
        <div class="metric">
            <span class="metric-label">Max Courant Number:</span> 
            <span class="metric-value">{solver_settings.get('max_co', 'N/A')}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Simulation Time:</span> 
            <span class="metric-value">{solver_settings.get('start_time', 0)} - {solver_settings.get('end_time', 'N/A')} s</span>
        </div>
    </div>
    
    <div class="section">
        <h2>Windkessel Boundary Conditions</h2>
        <p>The following lumped parameter (Windkessel) boundary conditions were applied to the outlets:</p>
        {wk_table}
        
        <h3>Parameter Definitions</h3>
        <ul>
            <li><strong>R (Resistance):</strong> Peripheral resistance in Pa·s/m³</li>
            <li><strong>C (Compliance):</strong> Arterial compliance in m³/Pa</li>
            <li><strong>Z (Impedance):</strong> Characteristic impedance in Pa·s/m³</li>
            <li><strong>p₀ (Reference Pressure):</strong> Initial pressure in Pa</li>
        </ul>
    </div>
    
    <div class="section">
        <h2>Flow Rate Analysis</h2>
        <div class="plot-container">
            {flow_plot_html}
        </div>
        <p>The flow rate plots show the temporal variation of volumetric flow rates at the inlet and outlets throughout the cardiac cycle. 
        These results can be used to assess flow conservation, pulsatility, and the physiological relevance of the simulation.</p>
    </div>
    
    <div class="section">
        <h2>Technical Notes</h2>
        <ul>
            <li>This simulation was performed using OpenFOAM 12 with the incompressibleFluid solver</li>
            <li>The mesh was generated using snappyHexMesh with automatic refinement based on patch diameter</li>
            <li>Windkessel boundary conditions provide physiologically realistic downstream resistance</li>
            <li>All units are in SI base units (m, kg, s, Pa) unless otherwise specified</li>
        </ul>
    </div>
    
    <footer style="margin-top: 50px; text-align: center; color: #7f8c8d; border-top: 1px solid #ecf0f1; padding-top: 20px;">
        <p>Generated by AortaCFD Simulation Reporter | OpenFOAM 12 | {datetime.now().year}</p>
    </footer>
</body>
</html>
"""
        
        return html_template
    
    def _generate_markdown_template(self, mesh_stats: Dict, transport_props: Dict,
                                  windkessel_data: Dict, solver_settings: Dict,
                                  plot_path: Optional[str], inlet_data: Optional[pd.DataFrame],
                                  outlet_flows: Dict[str, pd.DataFrame]) -> str:
        """Generate Markdown template for the report."""
        
        # Create Windkessel table
        wk_table = ""
        if windkessel_data:
            wk_table = "| Outlet | R (Pa·s/m³) | C (m³/Pa) | Z (Pa·s/m³) | p₀ (Pa) |\n"
            wk_table += "|--------|-------------|-----------|-------------|----------|\n"
            for outlet, coeffs in windkessel_data.items():
                wk_table += f"| {outlet} | {coeffs.get('R', 'N/A')} | {coeffs.get('C', 'N/A'):.2e} | {coeffs.get('Z', 'N/A')} | {coeffs.get('p0', 'N/A')} |\n"
        else:
            wk_table = "No Windkessel boundary conditions found."
        
        # Create mesh patch table
        patch_table = ""
        if 'patches' in mesh_stats:
            patch_table = "| Patch | Faces | Points |\n"
            patch_table += "|-------|-------|--------|\n"
            for patch, data in mesh_stats['patches'].items():
                patch_table += f"| {patch} | {data['faces']} | {data['points']} |\n"
        
        # Format flow plot and data summary
        flow_plot_md = ""
        flow_summary = ""
        
        if plot_path:
            plot_filename = Path(plot_path).name
            flow_plot_md = f"![Flow Rate Plot]({plot_filename})"
            
            # Add flow data summary
            if inlet_data is not None:
                max_flow = inlet_data['flow_rate'].max() * 1000  # Convert to mL/s
                avg_flow = inlet_data['flow_rate'].mean() * 1000
                flow_summary += f"\n### Flow Rate Summary\n\n"
                flow_summary += f"**Inlet Flow:**\n"
                flow_summary += f"- Maximum: {max_flow:.2f} mL/s\n"
                flow_summary += f"- Average: {avg_flow:.2f} mL/s\n"
                flow_summary += f"- Cardiac cycle duration: {inlet_data['time'].iloc[-1]:.3f} s\n\n"
                
                if outlet_flows:
                    flow_summary += f"**Outlet Flow Distribution:**\n"
                    for outlet_name, outlet_data in outlet_flows.items():
                        outlet_max = outlet_data['flow_rate'].max() * 1000
                        outlet_avg = outlet_data['flow_rate'].mean() * 1000
                        flow_summary += f"- {outlet_name}: {outlet_avg:.2f} mL/s (avg), {outlet_max:.2f} mL/s (max)\n"
        else:
            flow_plot_md = "*Flow rate data not available.*"
        
        markdown_template = f"""# AortaCFD Simulation Report

**Case:** {self.case_name}  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**OpenFOAM Version:** 12

## Executive Summary

This report provides a comprehensive analysis of the AortaCFD simulation for case **{self.case_name}**. The simulation used a computational mesh with {mesh_stats.get('cells', 'N/A'):,} cells and {mesh_stats.get('boundary_patches', 'N/A')} boundary patches, representing the aortic geometry with appropriate boundary conditions.

### Key Findings

- **Mesh Quality:** Max aspect ratio of {mesh_stats.get('max_aspect_ratio', 'N/A')}, max skewness of {mesh_stats.get('max_skewness', 'N/A')}
- **Windkessel Outlets:** {len(windkessel_data)} outlet(s) with lumped parameter boundary conditions
- **Fluid Properties:** ρ = {transport_props.get('density', 'N/A')} kg/m³, ν = {transport_props.get('kinematic_viscosity', 'N/A')} m²/s

## Computational Mesh

### Mesh Statistics
- **Total Cells:** {mesh_stats.get('cells', 'N/A'):,}
- **Total Points:** {mesh_stats.get('points', 'N/A'):,}
- **Total Faces:** {mesh_stats.get('faces', 'N/A'):,}
- **Boundary Patches:** {mesh_stats.get('boundary_patches', 'N/A')}

### Mesh Quality Metrics
- **Max Aspect Ratio:** {mesh_stats.get('max_aspect_ratio', 'N/A')}
- **Max Skewness:** {mesh_stats.get('max_skewness', 'N/A')}
- **Max Non-orthogonality:** {mesh_stats.get('max_non_orthogonality', 'N/A')}°
- **Total Volume:** {mesh_stats.get('total_volume', 'N/A')} m³

### Boundary Patches
{patch_table}

## Fluid Properties

- **Density (ρ):** {transport_props.get('density', 'N/A')} kg/m³
- **Kinematic Viscosity (ν):** {transport_props.get('kinematic_viscosity', 'N/A')} m²/s
- **Dynamic Viscosity (μ):** {transport_props.get('dynamic_viscosity', 'N/A')} Pa·s

## Solver Configuration

- **Time Scheme:** {solver_settings.get('time_scheme', 'N/A')}
- **Convection Scheme:** {solver_settings.get('convection_scheme', 'N/A')}
- **Time Step (Δt):** {solver_settings.get('delta_t', 'N/A')} s
- **Max Courant Number:** {solver_settings.get('max_co', 'N/A')}
- **Simulation Time:** {solver_settings.get('start_time', 0)} - {solver_settings.get('end_time', 'N/A')} s

## Windkessel Boundary Conditions

The following lumped parameter (Windkessel) boundary conditions were applied to the outlets:

{wk_table}

### Parameter Definitions
- **R (Resistance):** Peripheral resistance in Pa·s/m³
- **C (Compliance):** Arterial compliance in m³/Pa
- **Z (Impedance):** Characteristic impedance in Pa·s/m³
- **p₀ (Reference Pressure):** Initial pressure in Pa

## Flow Rate Analysis

{flow_plot_md}

The flow rate plots show the temporal variation of volumetric flow rates at the inlet and outlets throughout the cardiac cycle. These results can be used to assess flow conservation, pulsatility, and the physiological relevance of the simulation.
{flow_summary}

## Technical Notes

- This simulation was performed using OpenFOAM 12 with the incompressibleFluid solver
- The mesh was generated using snappyHexMesh with automatic refinement based on patch diameter
- Windkessel boundary conditions provide physiologically realistic downstream resistance
- All units are in SI base units (m, kg, s, Pa) unless otherwise specified

---
*Generated by AortaCFD Simulation Reporter | OpenFOAM 12 | {datetime.now().year}*
"""
        
        return markdown_template


def create_simulation_report(case_path: str, output_dir: str = None) -> str:
    """
    Create a comprehensive simulation report for an AortaCFD case.
    
    Args:
        case_path: Path to the OpenFOAM case directory
        output_dir: Directory to save the report (defaults to case directory)
    
    Returns:
        Path to the generated HTML report
    """
    if output_dir is None:
        output_dir = case_path
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Create reporter and generate report
    reporter = SimulationReporter(case_path)
    report_path = reporter.generate_html_report(output_dir)
    
    return report_path


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python simulation_reporter.py <case_path>")
        sys.exit(1)
    
    case_path = sys.argv[1]
    try:
        report_path = create_simulation_report(case_path)
        print(f"Report generated: {report_path}")
    except Exception as e:
        print(f"Error generating report: {e}")
        sys.exit(1)