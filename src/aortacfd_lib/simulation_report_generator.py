"""
Simulation Report Generator

Generates comprehensive technical reports documenting CFD simulation setup,
configuration parameters, and boundary conditions for reproducibility and auditing.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class SimulationReportGenerator:
    """Generate detailed technical reports for CFD simulations."""

    def __init__(self, output_dir: str, case_name: str):
        """
        Initialize report generator.

        Args:
            output_dir: Output directory path (e.g., output/patient1/run_YYYYMMDD_HHMMSS)
            case_name: Patient/case name
        """
        self.output_dir = Path(output_dir)
        self.case_name = case_name
        self.report_dir = self.output_dir / "reports"
        self.report_dir.mkdir(exist_ok=True)

    def generate_full_report(self, config: Dict[str, Any],
                            geometry_info: Optional[Dict] = None,
                            mesh_info: Optional[Dict] = None) -> str:
        """
        Generate complete technical report.

        Args:
            config: Full merged configuration dictionary
            geometry_info: Geometry analysis results (areas, radii, etc.)
            mesh_info: Mesh quality metrics

        Returns:
            Path to generated report file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Generate markdown report
        report_md = self._generate_markdown_report(config, geometry_info, mesh_info, timestamp)
        md_path = self.report_dir / "simulation_setup_report.md"
        with open(md_path, 'w') as f:
            f.write(report_md)

        # Generate JSON report for machine reading
        report_json = self._generate_json_report(config, geometry_info, mesh_info, timestamp)
        json_path = self.report_dir / "simulation_setup_report.json"
        with open(json_path, 'w') as f:
            json.dump(report_json, f, indent=2)

        # Generate summary text file
        summary_txt = self._generate_summary_txt(config, timestamp)
        txt_path = self.report_dir / "simulation_summary.txt"
        with open(txt_path, 'w') as f:
            f.write(summary_txt)

        return str(md_path)

    def _generate_markdown_report(self, config: Dict, geometry_info: Optional[Dict],
                                  mesh_info: Optional[Dict], timestamp: str) -> str:
        """Generate detailed markdown report."""

        report = f"""# CFD Simulation Technical Report

**Case:** {self.case_name}
**Generated:** {timestamp}
**Output Directory:** `{self.output_dir}`

---

## 1. Simulation Overview

### Case Information
- **Case Name:** {config.get('case_name', 'N/A')}
- **Patient ID:** {self.case_name}
- **Analysis Type:** {config.get('simulation_settings', {}).get('analysis_type', 'N/A')}
- **Solver Type:** {config.get('simulation_settings', {}).get('solver_type', 'N/A')}

### Configuration Source
- **Base Config:** Default template (`src/config/base.py`)
- **Profile:** {self._get_profile_name(config)}
- **Case Config:** `cases_input/{self.case_name}/config.json`

---

## 2. Physical Properties

### Fluid Properties
- **Density (ρ):** {config.get('physical_properties', {}).get('density', 'N/A')} kg/m³
- **Kinematic Viscosity (ν):** {config.get('physical_properties', {}).get('kinematic_viscosity', 'N/A')} m²/s
- **Dynamic Viscosity (μ):** {self._calculate_dynamic_viscosity(config)} Pa·s

### Flow Regime
{self._describe_flow_regime(config)}

---

## 3. Geometry

### STL Files
"""

        # Geometry details
        if geometry_info:
            report += self._format_geometry_section(geometry_info)
        else:
            report += "- Geometry information not available\n\n"

        # Boundary conditions
        report += """---

## 4. Boundary Conditions

"""
        report += self._format_boundary_conditions(config)

        # Mesh settings
        report += """---

## 5. Mesh Configuration

"""
        report += self._format_mesh_settings(config, mesh_info)

        # Numerical settings
        report += """---

## 6. Numerical Settings

"""
        report += self._format_numerical_settings(config)

        # Simulation control
        report += """---

## 7. Simulation Control

"""
        report += self._format_simulation_control(config)

        # Solver settings
        report += """---

## 8. Solver Configuration

"""
        report += self._format_solver_settings(config)

        # Footer
        report += f"""---

## 9. Reproducibility

### Command to Reproduce
```bash
python run_patient.py {self.case_name}
```

### Configuration Files
- Full config saved to: `{self.report_dir}/simulation_setup_report.json`
- OpenFOAM case: `{self.output_dir}/openfoam/`

---

**Report Generated:** {timestamp}
**Tool:** AortaCFD Pipeline v1.2.0
**OpenFOAM Version:** {config.get('openfoam_version', 'N/A')}
"""

        return report

    def _generate_json_report(self, config: Dict, geometry_info: Optional[Dict],
                             mesh_info: Optional[Dict], timestamp: str) -> Dict:
        """Generate machine-readable JSON report."""

        return {
            "metadata": {
                "case_name": self.case_name,
                "generated_at": timestamp,
                "output_directory": str(self.output_dir),
                "aortacfd_version": "1.2.0",
                "openfoam_version": config.get('openfoam_version', 'N/A')
            },
            "configuration": config,
            "geometry": geometry_info or {},
            "mesh_quality": mesh_info or {},
            "reproducibility": {
                "command": f"python run_patient.py {self.case_name}",
                "config_file": f"cases_input/{self.case_name}/config.json"
            }
        }

    def _generate_summary_txt(self, config: Dict, timestamp: str) -> str:
        """Generate concise text summary."""

        bc = config.get('boundary_conditions', {})
        inlet = bc.get('inlet', {})
        outlets = bc.get('outlets', {})

        summary = f"""CFD SIMULATION SUMMARY
{'=' * 60}

Case:           {self.case_name}
Generated:      {timestamp}
Analysis:       {config.get('simulation_settings', {}).get('analysis_type', 'N/A')}
Solver:         {config.get('simulation_settings', {}).get('solver_type', 'N/A')}

BOUNDARY CONDITIONS
{'-' * 60}
Inlet:          {inlet.get('type', 'N/A')}
Outlets:        {outlets.get('type', 'N/A')}

MESH
{'-' * 60}
Cell Size:      {config.get('mesh', {}).get('mesh_resolution', {}).get('target_cell_size_mm', 'N/A')} mm
BL Layers:      {config.get('mesh', {}).get('boundary_layers', {}).get('n_surface_layers', 'N/A')}

PHYSICAL PROPERTIES
{'-' * 60}
Density:        {config.get('physical_properties', {}).get('density', 'N/A')} kg/m³
Viscosity:      {config.get('physical_properties', {}).get('kinematic_viscosity', 'N/A')} m²/s

SIMULATION CONTROL
{'-' * 60}
End Time:       {config.get('simulation_control', {}).get('end_time', 'N/A')} s
Write Interval: {config.get('simulation_control', {}).get('write_interval', 'N/A')} s

OUTPUT
{'-' * 60}
Directory:      {self.output_dir}
OpenFOAM Case:  {self.output_dir}/openfoam/

REPRODUCIBILITY
{'-' * 60}
Command:        python run_patient.py {self.case_name}

{'=' * 60}
"""
        return summary

    # Helper methods

    def _get_profile_name(self, config: Dict) -> str:
        """Extract profile name from config."""
        analysis_type = config.get('simulation_settings', {}).get('analysis_type', '')
        solver_type = config.get('simulation_settings', {}).get('solver_type', '')
        return f"sim_{solver_type}_{analysis_type}" if solver_type and analysis_type else "N/A"

    def _calculate_dynamic_viscosity(self, config: Dict) -> str:
        """Calculate dynamic viscosity from kinematic viscosity and density."""
        try:
            nu = config.get('physical_properties', {}).get('kinematic_viscosity')
            rho = config.get('physical_properties', {}).get('density')
            if nu and rho:
                mu = nu * rho
                return f"{mu:.6e}"
        except:
            pass
        return "N/A"

    def _describe_flow_regime(self, config: Dict) -> str:
        """Describe flow regime based on settings."""
        solver = config.get('simulation_settings', {}).get('solver_type', '').upper()

        if solver == 'LAMINAR':
            return "- **Flow Regime:** Laminar (Re < 2300)\n- **Turbulence Model:** None\n"
        elif solver == 'RANS':
            turb_model = config.get('turbulence_settings', {}).get('RASModel', 'N/A')
            return f"- **Flow Regime:** Turbulent (RANS)\n- **Turbulence Model:** {turb_model}\n"
        elif solver == 'LES':
            les_model = config.get('turbulence_settings', {}).get('LESModel', 'N/A')
            return f"- **Flow Regime:** Turbulent (LES)\n- **LES Model:** {les_model}\n"
        else:
            return "- **Flow Regime:** Unknown\n"

    def _format_geometry_section(self, geometry_info: Dict) -> str:
        """Format geometry information."""
        section = ""

        if 'inlet' in geometry_info:
            inlet = geometry_info['inlet']
            section += f"- **Inlet:** area = {inlet.get('area', 'N/A'):.6e} m², "
            section += f"radius = {inlet.get('radius', 'N/A'):.6e} m\n"

        outlet_idx = 1
        while f'outlet{outlet_idx}' in geometry_info:
            outlet = geometry_info[f'outlet{outlet_idx}']
            section += f"- **Outlet{outlet_idx}:** area = {outlet.get('area', 'N/A'):.6e} m², "
            section += f"radius = {outlet.get('radius', 'N/A'):.6e} m\n"
            outlet_idx += 1

        if 'wall_aorta' in geometry_info:
            wall = geometry_info['wall_aorta']
            section += f"- **Wall:** area = {wall.get('area', 'N/A'):.6e} m²\n"

        section += "\n"
        return section

    def _format_boundary_conditions(self, config: Dict) -> str:
        """Format boundary conditions section."""
        bc = config.get('boundary_conditions', {})
        section = ""

        # Inlet
        inlet = bc.get('inlet', {})
        section += "### Inlet\n"
        section += f"- **Type:** {inlet.get('type', 'N/A')}\n"

        if inlet.get('type') == 'TIMEVARYING':
            section += f"- **CSV File:** {inlet.get('csv_file', 'N/A')}\n"
            section += f"- **Data Type:** {inlet.get('data_type', 'N/A')}\n"
            section += f"- **Profile:** {inlet.get('profile', 'N/A')}\n"
        elif inlet.get('type') == 'CONSTANT':
            if 'cardiac_output' in inlet:
                section += f"- **Cardiac Output:** {inlet.get('cardiac_output')} L/min\n"
            elif 'velocity_magnitude' in inlet:
                section += f"- **Velocity:** {inlet.get('velocity_magnitude')} m/s\n"

        # Outlets
        outlets = bc.get('outlets', {})
        section += "\n### Outlets\n"
        section += f"- **Type:** {outlets.get('type', 'N/A')}\n"

        if outlets.get('type') == '3EWINDKESSEL':
            wk = outlets.get('windkessel_settings', {})
            section += f"- **Systolic Pressure:** {wk.get('systolic_pressure', 'N/A')} mmHg\n"
            section += f"- **Diastolic Pressure:** {wk.get('diastolic_pressure', 'N/A')} mmHg\n"
            section += f"- **Flow Split Method:** {wk.get('flow_split_method', 'N/A')}\n"
            if 'flow_split' in wk:
                section += f"- **Flow Split:** {wk.get('flow_split')}\n"

        section += "\n"
        return section

    def _format_mesh_settings(self, config: Dict, mesh_info: Optional[Dict]) -> str:
        """Format mesh configuration section."""
        mesh = config.get('mesh', {})
        section = ""

        # Mesh resolution
        res = mesh.get('mesh_resolution', {})
        section += "### Mesh Resolution\n"
        section += f"- **Target Cell Size:** {res.get('target_cell_size_mm', 'N/A')} mm\n"
        section += f"- **Base Cell Size:** {res.get('base_cell_size_mm', 'N/A')} mm\n"

        # Boundary layers
        bl = mesh.get('boundary_layers', {})
        section += "\n### Boundary Layers\n"
        section += f"- **Number of Layers:** {bl.get('n_surface_layers', 'N/A')}\n"
        section += f"- **Expansion Ratio:** {bl.get('expansion_ratio', 'N/A')}\n"
        section += f"- **Final Thickness:** {bl.get('final_layer_thickness', 'N/A')} m\n"

        # Mesh quality (if available)
        if mesh_info:
            section += "\n### Mesh Quality Metrics\n"
            section += f"- **Total Cells:** {mesh_info.get('n_cells', 'N/A')}\n"
            section += f"- **Max Non-Orthogonality:** {mesh_info.get('max_non_ortho', 'N/A')}°\n"
            section += f"- **Max Skewness:** {mesh_info.get('max_skewness', 'N/A')}\n"

        section += "\n"
        return section

    def _format_numerical_settings(self, config: Dict) -> str:
        """Format numerical schemes and settings."""
        section = ""

        # Time schemes
        section += "### Time Discretization\n"
        section += f"- **ddt Scheme:** {config.get('numerical_settings', {}).get('ddtSchemes', {}).get('default', 'N/A')}\n"

        # Gradient schemes
        section += "\n### Gradient Schemes\n"
        section += f"- **Default:** {config.get('numerical_settings', {}).get('gradSchemes', {}).get('default', 'N/A')}\n"

        # Divergence schemes
        section += "\n### Divergence Schemes\n"
        div_schemes = config.get('numerical_settings', {}).get('divSchemes', {})
        for key, value in div_schemes.items():
            if key != 'default':
                section += f"- **{key}:** {value}\n"

        section += "\n"
        return section

    def _format_simulation_control(self, config: Dict) -> str:
        """Format simulation control parameters."""
        ctrl = config.get('simulation_control', {})
        section = ""

        section += f"- **End Time:** {ctrl.get('end_time', 'N/A')} s\n"
        section += f"- **Write Interval:** {ctrl.get('write_interval', 'N/A')} s\n"
        section += f"- **Time Step (Δt):** {ctrl.get('controlDict', {}).get('deltaT', 'N/A')} s\n"
        section += f"- **Max Courant Number:** {ctrl.get('controlDict', {}).get('maxCo', 'N/A')}\n"
        section += f"- **Adjustable Time Step:** {ctrl.get('controlDict', {}).get('adjustTimeStep', False)}\n"

        section += "\n"
        return section

    def _format_solver_settings(self, config: Dict) -> str:
        """Format solver configuration."""
        section = ""

        run_settings = config.get('run_settings', {})
        section += f"- **Solution Type:** {run_settings.get('solution_type', 'N/A')}\n"

        if run_settings.get('solution_type') == 'parallel':
            section += f"- **Number of Processors:** {run_settings.get('subdomains', 'N/A')}\n"
            section += f"- **Decomposition Method:** {run_settings.get('decomposition_method', 'N/A')}\n"

        section += f"- **OpenFOAM Version:** {config.get('openfoam_version', 'N/A')}\n"
        section += f"- **Solver Command:** `foamRun -solver incompressibleFluid`\n"

        section += "\n"
        return section
