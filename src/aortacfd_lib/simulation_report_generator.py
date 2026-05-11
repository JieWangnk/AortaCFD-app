"""
Simulation Report Generator

Generates comprehensive technical reports documenting CFD simulation setup,
configuration parameters, and boundary conditions for reproducibility and auditing.
"""

import json
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

    def generate_full_report(
        self, config: Dict[str, Any], geometry_info: Optional[Dict] = None, mesh_info: Optional[Dict] = None
    ) -> str:
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

        # Generate detailed text report (convert markdown to plain text)
        report_md = self._generate_markdown_report(config, geometry_info, mesh_info, timestamp)
        report_txt = self._convert_md_to_txt(report_md)
        txt_path = self.report_dir / "simulation_setup_report.txt"
        with open(txt_path, "w") as f:
            f.write(report_txt)

        # Save full merged config as JSON for reproducibility
        config_json_path = self.report_dir / "merged_config.json"
        self._save_config_json(config, config_json_path, timestamp)

        # Note: simulation_summary.txt removed as simulation_setup_report.txt
        # provides more comprehensive information

        return str(txt_path)

    def _generate_markdown_report(
        self, config: Dict, geometry_info: Optional[Dict], mesh_info: Optional[Dict], timestamp: str
    ) -> str:
        """Generate detailed markdown report."""

        report = f"""# CFD Simulation Technical Report

**Case:** {self.case_name}
**Generated:** {timestamp}
**Output Directory:** `{self.output_dir}`

---

## 1. Simulation Overview

### Case Information
- **Case Name:** {config.get('geometry', {}).get('case_name', config.get('case_info', {}).get('patient_id', 'N/A'))}
- **Patient ID:** {self.case_name}
- **Analysis Type:** {config.get('simulation_settings', {}).get('analysis_type', 'N/A')}
- **Solver Type:** {config.get('simulation_settings', {}).get('solver_type', 'N/A')}

### Configuration Source
- **Base Config:** Default template (`src/config/base.py`)
- **Profile:** {self._get_profile_display(config)}
- **Case Config:** {self._get_case_config_path(config)}

---

## 2. Physical Properties

### Fluid Properties
- **Density (ρ):** {self._get_density(config)} kg/m³
- **Kinematic Viscosity (ν):** {self._get_kinematic_viscosity(config)} m²/s
- **Dynamic Viscosity (μ):** {self._calculate_dynamic_viscosity(config)} Pa·s

### Flow Regime
{self._describe_flow_regime(config)}

---

## 3. Geometry

### STL Files
"""

        # Geometry details
        report += self._format_geometry_section(config, geometry_info)

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

    def _convert_md_to_txt(self, markdown_text: str) -> str:
        """
        Convert markdown to plain text.

        Simple conversion that removes markdown formatting:
        - Remove # headers → plain text with separator lines
        - Remove ** bold ** → plain text
        - Remove ` code ` → plain text
        - Remove --- separators → use === instead
        - Keep structure and readability
        """
        import re

        txt = markdown_text

        # Convert headers (# Header → HEADER with underline)
        def replace_header(match):
            level = len(match.group(1))
            title = match.group(2).strip()
            if level == 1:
                return f"\n{'='*80}\n{title.upper()}\n{'='*80}\n"
            elif level == 2:
                return f"\n{'-'*80}\n{title}\n{'-'*80}\n"
            elif level == 3:
                return f"\n{title}\n{'-'*len(title)}\n"
            else:
                return f"\n{title}:\n"

        txt = re.sub(r"^(#{1,6})\s+(.+)$", replace_header, txt, flags=re.MULTILINE)

        # Remove bold/italic
        txt = re.sub(r"\*\*(.+?)\*\*", r"\1", txt)  # **bold**
        txt = re.sub(r"\*(.+?)\*", r"\1", txt)  # *italic*
        txt = re.sub(r"__(.+?)__", r"\1", txt)  # __bold__
        txt = re.sub(r"_(.+?)_", r"\1", txt)  # _italic_

        # Remove inline code
        txt = re.sub(r"`(.+?)`", r"\1", txt)

        # Remove markdown links [text](url) → text
        txt = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", txt)

        # Remove horizontal rules
        txt = re.sub(r"^---+$", "=" * 80, txt, flags=re.MULTILINE)

        # Clean up excessive blank lines
        txt = re.sub(r"\n{3,}", "\n\n", txt)

        return txt

    def _generate_json_report(
        self, config: Dict, geometry_info: Optional[Dict], mesh_info: Optional[Dict], timestamp: str
    ) -> Dict:
        """Generate machine-readable JSON report."""

        return {
            "metadata": {
                "case_name": self.case_name,
                "generated_at": timestamp,
                "output_directory": str(self.output_dir),
                "aortacfd_version": "1.2.0",
                "openfoam_version": config.get("openfoam_version", "N/A"),
            },
            "configuration": config,
            "geometry": geometry_info or {},
            "mesh_quality": mesh_info or {},
            "reproducibility": {
                "command": f"python run_patient.py {self.case_name}",
                "config_file": f"cases_input/{self.case_name}/config.json",
            },
        }

    def _save_config_json(self, config: Dict, output_path: Path, timestamp: str) -> None:
        """
        Save full merged configuration as JSON for reproducibility.

        This enables exact reproduction of the simulation by capturing all
        parameters (user-specified + defaults + computed values).
        """
        # Create a clean config dict with metadata
        export_config = {
            "_metadata": {
                "case_name": self.case_name,
                "generated_at": timestamp,
                "output_directory": str(self.output_dir),
                "description": "Full merged configuration for simulation reproducibility",
                "usage": f"python run_patient.py {self.case_name} --config <this_file>",
            },
            **{k: v for k, v in config.items() if not k.startswith("_")},
        }

        # Also preserve any user comments/metadata from original config
        for key in config:
            if key.startswith("_") and key not in ["_metadata"]:
                export_config[key] = config[key]

        with open(output_path, "w") as f:
            json.dump(export_config, f, indent=2, default=str)

    def _generate_summary_txt(self, config: Dict, timestamp: str) -> str:
        """Generate concise text summary."""

        bc = config.get("boundary_conditions", {})
        inlet = bc.get("inlet", {})
        outlets = bc.get("outlets", {})

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
Resolution:     {config.get('mesh', {}).get('resolution_level', 'N/A')}
Cell Size:      {config.get('mesh', {}).get('mesh_resolution', {}).get('target_cell_size_mm', 'N/A')} mm
BL Layers:      {config.get('mesh', {}).get('boundary_layers', {}).get('n_surface_layers', 'N/A')}

PHYSICAL PROPERTIES
{'-' * 60}
Density:        {config.get('physics', {}).get('blood_density', config.get('physical_properties', {}).get('density', 'N/A'))} kg/m³
Viscosity:      {config.get('physics', {}).get('nu', config.get('physical_properties', {}).get('kinematic_viscosity', 'N/A'))} m²/s

SIMULATION CONTROL
{'-' * 60}
End Time:       {config.get('simulation_control', {}).get('end_time', 'N/A')} s
Write Interval: {config.get('simulation_control', {}).get('writeInterval', config.get('simulation_control', {}).get('write_interval', 'N/A'))} s

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
        analysis_type = config.get("simulation_settings", {}).get("analysis_type", "")
        solver_type = config.get("simulation_settings", {}).get("solver_type", "")
        return f"sim_{solver_type}_{analysis_type}" if solver_type and analysis_type else "N/A"

    def _get_profile_display(self, config: Dict) -> str:
        """Get profile display name with metadata if available."""
        config_source = config.get("config_source", {})
        profile_key = config_source.get("profile_key")
        profile_metadata = config.get("profile_metadata", {})

        if profile_key:
            display_name = profile_metadata.get("display_name", "")
            if display_name:
                return f"{profile_key} ({display_name})"
            return profile_key

        # Fallback to old method
        return self._get_profile_name(config)

    def _get_case_config_path(self, config: Dict) -> str:
        """Get the actual case config file path used."""
        config_source = config.get("config_source", {})
        config_path = config_source.get("case_config_file")

        if config_path:
            return f"`{config_path}`"

        # Fallback to default assumption
        return f"`cases_input/{self.case_name}/config.json`"

    def _get_density(self, config: Dict) -> str:
        """Extract density from config with fallback."""
        physics = config.get("physics", {})
        phys_props = config.get("physical_properties", {})

        # Try multiple keys
        rho = (
            physics.get("blood_density")
            or physics.get("rho")
            or phys_props.get("density")
            or phys_props.get("blood_density")
        )

        return str(rho) if rho else "N/A"

    def _get_kinematic_viscosity(self, config: Dict) -> str:
        """Extract kinematic viscosity from config with fallback."""
        physics = config.get("physics", {})
        phys_props = config.get("physical_properties", {})

        # Try multiple keys
        nu = (
            physics.get("nu")
            or physics.get("kinematic_viscosity")
            or phys_props.get("nu")
            or phys_props.get("kinematic_viscosity")
        )

        return f"{nu:.6e}" if nu else "N/A"

    def _calculate_dynamic_viscosity(self, config: Dict) -> str:
        """Calculate dynamic viscosity from kinematic viscosity and density."""
        try:
            # Try new config structure first, then fall back to old
            physics = config.get("physics", {})
            phys_props = config.get("physical_properties", {})

            nu = (
                physics.get("nu")
                or physics.get("kinematic_viscosity")
                or phys_props.get("nu")
                or phys_props.get("kinematic_viscosity")
            )

            rho = (
                physics.get("blood_density")
                or physics.get("rho")
                or phys_props.get("density")
                or phys_props.get("blood_density")
            )

            if nu and rho:
                mu = float(nu) * float(rho)
                return f"{mu:.6e}"
        except Exception:
            pass
        return "N/A"

    def _describe_flow_regime(self, config: Dict) -> str:
        """Describe flow regime based on settings."""
        physics = config.get("physics", {})

        # Check multiple locations for flow model/simulation type
        flow_model = (
            physics.get("simulation_type")
            or physics.get("model")
            or config.get("simulation_settings", {}).get("solver_type", "")
            or ""
        ).upper()

        if flow_model == "LAMINAR":
            return "- **Flow Regime:** Laminar\n- **Turbulence Model:** None (Stokes)\n"
        elif flow_model in ["RANS", "TURBULENT"]:
            # Try multiple locations for turbulence model
            turb_model = (
                physics.get("turbulence_model")
                or config.get("turbulence_settings", {}).get("RASModel")
                or "kOmegaSST (default)"
            )
            return f"- **Flow Regime:** Turbulent (RANS)\n- **Turbulence Model:** {turb_model}\n"
        elif flow_model == "LES":
            # Try multiple locations for LES model
            les_model = (
                physics.get("subgrid_model")
                or config.get("turbulence_settings", {}).get("LESModel")
                or "WALE (default)"
            )
            return f"- **Flow Regime:** Turbulent (LES)\n- **LES Model:** {les_model}\n"
        else:
            # Fallback: check for laminar indicators
            if physics.get("default_turbulence") == "laminar":
                return "- **Flow Regime:** Laminar\n- **Turbulence Model:** None (Stokes)\n"
            return "- **Flow Regime:** Unknown\n"

    def _format_geometry_section(self, config: Dict, geometry_info: Optional[Dict]) -> str:
        """Format geometry information."""
        section = ""

        # Get geometry config
        geom = config.get("geometry", {})
        case_name = geom.get("case_name", "N/A")
        scale_factor = geom.get("scale_factor", 1e-3)

        # STL file information
        section += f"- **Case Name:** {case_name}\n"
        section += f"- **Scale Factor:** {scale_factor} (geometry units → meters)\n"

        # List patches from config
        inlet_patch = geom.get("inlet_keywords_ordered", "N/A")
        outlet_patches = geom.get("outlet_keywords_ordered", [])
        wall_patch = geom.get("wall_keywords_ordered", "N/A")

        section += f"- **Inlet Patch:** {inlet_patch}\n"
        if isinstance(outlet_patches, list):
            section += f"- **Outlet Patches:** {', '.join(outlet_patches)} ({len(outlet_patches)} outlets)\n"
        else:
            section += f"- **Outlet Patches:** {outlet_patches}\n"
        section += f"- **Wall Patch:** {wall_patch}\n"

        # Add measured geometry data if available
        if geometry_info:
            section += "\n### Measured Geometry\n"

            if "inlet" in geometry_info:
                inlet = geometry_info["inlet"]
                area = inlet.get("area", 0)
                radius = inlet.get("radius", 0)
                section += f"- **Inlet:** area = {area:.2e} m² ({area*1e6:.2f} mm²), "
                section += f"radius = {radius:.2e} m ({radius*1e3:.2f} mm)\n"

            outlet_idx = 1
            while f"outlet{outlet_idx}" in geometry_info:
                outlet = geometry_info[f"outlet{outlet_idx}"]
                area = outlet.get("area", 0)
                radius = outlet.get("radius", 0)
                section += f"- **Outlet{outlet_idx}:** area = {area:.2e} m² ({area*1e6:.2f} mm²), "
                section += f"radius = {radius:.2e} m ({radius*1e3:.2f} mm)\n"
                outlet_idx += 1

            if "wall_aorta" in geometry_info or "wall" in geometry_info:
                wall = geometry_info.get("wall_aorta", geometry_info.get("wall", {}))
                area = wall.get("area", 0)
                section += f"- **Wall:** area = {area:.2e} m² ({area*1e6:.2f} mm²)\n"

        section += "\n"
        return section

    def _format_boundary_conditions(self, config: Dict) -> str:
        """Format boundary conditions section."""
        bc = config.get("boundary_conditions", {})
        section = ""

        # Inlet - check both locations
        inlet = bc.get("inlet", config.get("inlet", {}))
        section += "### Inlet\n"
        inlet_type = inlet.get("type", "N/A")
        section += f"- **Type:** {inlet_type}\n"

        if inlet_type == "TIMEVARYING":
            section += f"- **CSV File:** {inlet.get('csv_file', 'N/A')}\n"
            section += f"- **Data Type:** {inlet.get('data_type', 'N/A')}\n"
            section += f"- **Profile:** {inlet.get('profile', 'N/A')}\n"
        elif inlet_type == "WOMERSLEY":
            section += f"- **CSV File:** {inlet.get('csv_file', 'N/A')}\n"
            section += f"- **Womersley Number:** {inlet.get('womersley_number', 'N/A')}\n"
            section += f"- **Fourier Modes:** {inlet.get('fourier_modes', 'N/A')}\n"
        elif inlet_type in ["CONSTANT", "PARABOLIC"]:
            if "cardiac_output" in inlet:
                section += f"- **Cardiac Output:** {inlet.get('cardiac_output')} L/min\n"
            elif "velocity" in inlet:
                section += f"- **Velocity:** {inlet.get('velocity')} m/s\n"
            elif "velocity_magnitude" in inlet:
                section += f"- **Velocity:** {inlet.get('velocity_magnitude')} m/s\n"

        # Outlets - check both locations
        outlets = bc.get("outlets", config.get("outlets", {}))
        section += "\n### Outlets\n"
        outlet_type = outlets.get("type", "N/A")
        section += f"- **Type:** {outlet_type}\n"

        if outlet_type == "3EWINDKESSEL":
            wk = outlets.get("windkessel_settings", {})
            section += f"- **Systolic Pressure:** {wk.get('systolic_pressure', 'N/A')} mmHg\n"
            section += f"- **Diastolic Pressure:** {wk.get('diastolic_pressure', 'N/A')} mmHg\n"
            section += f"- **Venous Pressure:** {wk.get('venous_pressure', 0)} mmHg\n"

            flow_split = wk.get("flow_split", "auto")
            if isinstance(flow_split, dict):
                section += "- **Flow Split:** Manual (per outlet)\n"
                for outlet, fraction in flow_split.items():
                    section += f"  - {outlet}: {fraction*100:.1f}%\n"
            elif isinstance(flow_split, (int, float)):
                section += f"- **Flow Split:** {flow_split}% to main branch (rest distributed by Murray's law)\n"
            else:
                section += "- **Flow Split:** Auto-calculated (Murray's law)\n"

            # Check if WK parameters were calculated
            if "outlet_parameters" in wk:
                section += "- **Windkessel Parameters:** Calculated (see logs for R, C, Z values)\n"

        elif outlet_type == "zeroGradient":
            section += "- **Description:** Zero pressure gradient at outlets\n"
        elif outlet_type == "fixedValue":
            section += f"- **Pressure:** {outlets.get('pressure', 'N/A')} Pa\n"

        # Walls
        walls = bc.get("walls", {})
        if walls:
            section += "\n### Walls\n"
            wall_type = walls.get("type", "no_slip")
            section += f"- **Type:** {wall_type}\n"
            if "roughness" in walls:
                section += f"- **Roughness:** {walls.get('roughness')} m\n"

        section += "\n"
        return section

    def _format_mesh_settings(self, config: Dict, mesh_info: Optional[Dict]) -> str:
        """Format mesh configuration section."""
        mesh = config.get("mesh", {})
        section = ""

        # Mesh resolution - check multiple possible structures
        res_level = mesh.get("resolution_level", "N/A")
        section += "### Mesh Resolution\n"
        section += f"- **Resolution Level:** {res_level}\n"

        # Map resolution level to approximate cell sizes
        resolution_map = {
            "coarse": {"target": 1.8, "base": 2.5, "description": "Quick validation (~300K cells)"},
            "medium": {"target": 1.0, "base": 1.5, "description": "Standard analysis (~1M cells)"},
            "fine": {"target": 0.6, "base": 0.9, "description": "High accuracy (~3M cells)"},
            "very_fine": {"target": 0.4, "base": 0.6, "description": "Very high accuracy (~8M cells)"},
        }

        if res_level in resolution_map:
            info = resolution_map[res_level]
            section += f"- **Target Cell Size:** {info['target']} mm\n"
            section += f"- **Base Cell Size:** {info['base']} mm\n"
            section += f"- **Description:** {info['description']}\n"
        else:
            # Try to get from mesh_resolution dict
            res = mesh.get("mesh_resolution", {})
            target_size = res.get("target_cell_size_mm", res.get("target_cell_size", "N/A"))
            base_size = res.get("base_cell_size_mm", res.get("base_cell_size", "N/A"))
            section += f"- **Target Cell Size:** {target_size} mm\n"
            section += f"- **Base Cell Size:** {base_size} mm\n"

        # Boundary layers - check multiple structures
        bl = mesh.get("boundary_layers", {})
        if bl or "n_surface_layers" in mesh:
            section += "\n### Boundary Layers\n"
            n_layers = bl.get("n_surface_layers", mesh.get("n_surface_layers", bl.get("nSurfaceLayers", "N/A")))
            expansion = bl.get("expansion_ratio", mesh.get("expansion_ratio", bl.get("expansionRatio", "N/A")))
            thickness = bl.get(
                "final_layer_thickness", mesh.get("final_layer_thickness", bl.get("finalLayerThickness", "N/A"))
            )

            section += f"- **Number of Layers:** {n_layers}\n"
            section += f"- **Expansion Ratio:** {expansion}\n"

            if thickness != "N/A":
                if isinstance(thickness, (int, float)):
                    section += f"- **Final Thickness:** {thickness:.2e} m ({thickness*1000:.3f} mm)\n"
                else:
                    section += f"- **Final Thickness:** {thickness}\n"
            else:
                section += "- **Final Thickness:** N/A\n"

            # Calculate first layer thickness if possible
            if n_layers != "N/A" and expansion != "N/A" and thickness != "N/A":
                try:
                    n = int(n_layers)
                    r = float(expansion)
                    t_final = float(thickness)
                    # Geometric series: t_final = t_first * r^(n-1)
                    t_first = t_final / (r ** (n - 1))
                    section += f"- **First Layer Thickness:** {t_first:.2e} m ({t_first*1000:.3f} mm)\n"
                except:
                    pass
        else:
            section += "\n### Boundary Layers\n"
            section += "- **Status:** Not configured (using default wall functions)\n"

        # Mesh quality (if available)
        if mesh_info:
            section += "\n### Mesh Quality Metrics\n"
            section += f"- **Total Cells:** {mesh_info.get('n_cells', 'N/A'):,}\n"
            section += f"- **Max Non-Orthogonality:** {mesh_info.get('max_non_ortho', 'N/A')}°\n"
            section += f"- **Max Skewness:** {mesh_info.get('max_skewness', 'N/A')}\n"

        section += "\n"
        return section

    def _format_numerical_settings(self, config: Dict) -> str:
        """Format numerical schemes and settings."""
        section = ""

        # Check multiple locations for numerical settings
        num_settings = config.get("numerical_settings", {})
        numerical = config.get("numerical", {})

        # Time schemes - check controlDict and numerical config
        section += "### Time Discretization\n"
        config.get("simulation_control", {}).get("controlDict", {})
        ddt_scheme = num_settings.get("ddtSchemes", {}).get("default") or numerical.get("time_scheme") or "Euler"
        section += f"- **ddt Scheme:** {ddt_scheme}\n"
        section += "- **Description:** Time derivative discretization for transient simulations\n"

        # Gradient schemes
        section += "\n### Gradient Schemes\n"
        grad_scheme = (
            num_settings.get("gradSchemes", {}).get("default") or numerical.get("gradient_scheme") or "Gauss linear"
        )
        section += f"- **Default:** {grad_scheme}\n"
        section += "- **Description:** Spatial gradient calculation using Gauss integration\n"

        # Divergence schemes
        section += "\n### Divergence Schemes\n"
        div_scheme = num_settings.get("divSchemes", {}).get("div(phi,U)") or numerical.get("divergence_scheme") or None
        if div_scheme:
            section += f"- **Momentum (div(phi,U)):** {div_scheme}\n"
        else:
            section += "- **Momentum:** Gauss linearUpwindV grad(U) (default for incompressible flow)\n"

        # Laplacian schemes
        laplacian = (
            num_settings.get("laplacianSchemes", {}).get("default")
            or numerical.get("laplacian_scheme")
            or "Gauss linear corrected"
        )
        section += "\n### Laplacian Schemes\n"
        section += f"- **Default:** {laplacian}\n"

        # Linear solvers
        section += "\n### Linear Solvers\n"
        p_solver = (
            num_settings.get("solvers", {}).get("p", {}).get("solver") or numerical.get("pressure_solver") or "GAMG"
        )
        u_solver = (
            num_settings.get("solvers", {}).get("U", {}).get("solver")
            or numerical.get("velocity_solver")
            or "smoothSolver"
        )
        section += f"- **Pressure:** {p_solver}\n"
        section += f"- **Velocity:** {u_solver}\n"

        section += "\n"
        return section

    def _format_simulation_control(self, config: Dict) -> str:
        """Format simulation control parameters."""
        ctrl = config.get("simulation_control", {})
        section = ""

        # End time calculation
        end_time = ctrl.get("end_time", "N/A")
        num_cycles = ctrl.get("number_of_cycles", None)

        if end_time == "auto" and num_cycles:
            # Calculate from cardiac cycle
            case_info = config.get("case_info", {})
            heart_rate = case_info.get("heart_rate", 60)
            cardiac_cycle = 60.0 / heart_rate  # seconds per cycle
            calculated_end_time = num_cycles * cardiac_cycle
            section += f"- **End Time:** {end_time} ({num_cycles} cycles × {cardiac_cycle:.2f}s = {calculated_end_time:.2f}s)\n"
            section += f"- **Number of Cycles:** {num_cycles}\n"
            section += f"- **Heart Rate:** {heart_rate} BPM (cardiac cycle = {cardiac_cycle:.3f}s)\n"
        else:
            section += f"- **End Time:** {end_time} s\n"
            if num_cycles:
                section += f"- **Number of Cycles:** {num_cycles}\n"

        # Write interval
        write_interval = ctrl.get("writeInterval", ctrl.get("write_interval", 0.02))
        section += f"- **Write Interval:** {write_interval} s (output every {write_interval*1000:.0f} ms)\n"

        # Try to get deltaT from different locations
        delta_t = ctrl.get("deltaT", ctrl.get("controlDict", {}).get("deltaT", 1e-5))
        if isinstance(delta_t, (int, float)):
            section += f"- **Initial Time Step (Δt):** {delta_t:.2e} s ({delta_t*1e6:.1f} μs)\n"
        else:
            section += f"- **Initial Time Step (Δt):** {delta_t} s\n"

        # Get Courant number
        max_co = ctrl.get("maxCo", ctrl.get("controlDict", {}).get("maxCo", 0.5))
        section += f"- **Max Courant Number:** {max_co}\n"

        # Get adaptive time stepping
        adjust_dt = ctrl.get("adjustTimeStep", ctrl.get("controlDict", {}).get("adjustTimeStep", True))
        section += f"- **Adjustable Time Step:** {'yes' if adjust_dt else 'no'}\n"

        if adjust_dt:
            max_dt = ctrl.get("maxDeltaT", ctrl.get("controlDict", {}).get("maxDeltaT", None))
            if max_dt:
                section += f"- **Max Time Step:** {max_dt:.2e} s\n"

        section += "\n"
        return section

    def _format_solver_settings(self, config: Dict) -> str:
        """Format solver configuration."""
        section = ""

        run_settings = config.get("run_settings", {})
        sim_settings = config.get("simulation_settings", {})

        solution_type = run_settings.get("solution_type", "serial")
        section += f"- **Solution Type:** {solution_type}\n"

        if solution_type == "parallel":
            n_procs = run_settings.get("subdomains", "N/A")
            decomp = run_settings.get("decomposition_method", "scotch")
            section += f"- **Number of Processors:** {n_procs}\n"
            section += f"- **Decomposition Method:** {decomp}\n"

        # OpenFOAM version
        of_version = config.get("openfoam_version", "12")
        section += f"- **OpenFOAM Version:** {of_version}\n"

        # Solver type
        solver_type = sim_settings.get("solver_type", "laminar")
        section += f"- **Solver Type:** {solver_type}\n"

        # Solver command
        if solution_type == "parallel":
            n_procs = run_settings.get("subdomains", 4)
            section += f"- **Solver Command:** `mpirun -np {n_procs} foamRun -solver incompressibleFluid -parallel`\n"
        else:
            section += "- **Solver Command:** `foamRun -solver incompressibleFluid`\n"

        section += "\n"
        return section
