import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter
from .template_context import prepare_fv_schemes_context

class FvSchemesWriter:
    """
    Generates the fvSchemes file using a unified config object and a
    single, intelligent Jinja2 template.

    Includes mesh-adaptive system that automatically adjusts schemes
    based on checkMesh quality metrics.
    """
    def __init__(self, config: dict, case_directory: str):
        """The constructor now takes the unified config object."""
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("numerical_setup").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))
        self.version_adapter = OFVersionAdapter(self.config['openfoam_version'])

    def write_fvSchemes_file(self):
        """
        Generates the fvSchemes file by rendering a template with the
        physics settings from the config.

        If mesh-adaptive system is enabled and checkMesh log exists,
        schemes will be automatically adjusted for mesh quality.
        """
        # Get schemes from config
        schemes = self.config.get('schemes', {})

        # Apply mesh-adaptive adjustments if enabled
        mesh_adaptive_enabled = self.config.get('numerics', {}).get('mesh_adaptive', True)

        if mesh_adaptive_enabled and 'schemes' in self.config:
            schemes = self._apply_mesh_adaptive_schemes(schemes)

        # This single method replaces all the previous private _get... methods.
        template = self.jinja_env.get_template("fvSchemes.tpl")

        # Pre-process business logic using template_context module
        # This extracts profile-based scheme decisions into testable Python code
        preprocessed = prepare_fv_schemes_context(self.config)

        # The template will use these settings to decide which schemes to write.
        context = {
            "header": self.version_adapter.get_foam_file_header("dictionary", "fvSchemes"),
            # Pre-computed business logic values
            "is_steady": preprocessed['is_steady'],
            "simulation_type": preprocessed['simulation_type'],
            "profile": preprocessed['profile'],
            "ddt_scheme": preprocessed['ddt_scheme'],
            "div_scheme_U": preprocessed['div_scheme_U'],
            "div_scheme_k": preprocessed['div_scheme_k'],
            "grad_limiter": preprocessed['grad_limiter'],
            "laplacian_scheme": preprocessed['laplacian_scheme'],
            "sngrad_scheme": preprocessed['sngrad_scheme'],
            # Raw data (still needed for scheme overrides)
            "physics": self.config['physics'],
            "schemes": schemes,
            "template_vars": self.config.get('template_vars', {}),
            "openfoam_version": self.config.get('openfoam_version', '8'),
            "openfoam_major_version": self.config.get('openfoam_major_version', 8)
        }

        output_path = os.path.join(self.case_dir, "system", "fvSchemes")
        with open(output_path, 'w') as f:
            f.write(template.render(context))
        self.log.info(f"Successfully wrote fvSchemes file to {output_path}")

    def _apply_mesh_adaptive_schemes(self, base_schemes: dict) -> dict:
        """
        Apply mesh-adaptive adjustments to schemes based on checkMesh quality.

        Args:
            base_schemes: Base schemes from numerics profile

        Returns:
            Adjusted schemes dictionary
        """
        try:
            from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

            # Find checkMesh log
            checkmesh_log = Path(self.case_dir) / "logs" / "log.checkMesh"
            if not checkmesh_log.exists():
                self.log.debug("checkMesh log not found, skipping mesh-adaptive adjustments")
                return base_schemes

            # Create adapter and analyze mesh
            adapter = MeshAdaptiveSolverSettings()
            adapter.analyze_checkmesh_log(str(checkmesh_log))

            # Get profile name (case-insensitive)
            profile_name = self.config.get('numerics', {}).get('profile', 'standard').lower()

            # Adjust schemes
            adjusted_schemes = adapter.adjust_fvschemes_for_mesh(base_schemes, profile_name)

            # Log adjustments if any were made
            if adjusted_schemes != base_schemes:
                tier = adapter.mesh_quality_tier
                self.log.info(f"🔧 Mesh-Adaptive System: Detected {tier} quality mesh")
                self.log.info(f"   Adjusted fvSchemes for mesh quality")

                # Log specific changes
                if 'laplacianSchemes' in adjusted_schemes:
                    base_lap = base_schemes.get('laplacianSchemes', {}).get('default', 'N/A')
                    adj_lap = adjusted_schemes['laplacianSchemes'].get('default', 'N/A')
                    if base_lap != adj_lap:
                        self.log.info(f"   Laplacian: {base_lap} → {adj_lap}")

            return adjusted_schemes

        except ImportError:
            self.log.warning("Mesh-adaptive system not available, using base schemes")
            return base_schemes
        except Exception as e:
            self.log.warning(f"Mesh-adaptive adjustment failed: {e}, using base schemes")
            return base_schemes