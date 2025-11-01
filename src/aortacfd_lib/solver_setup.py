import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from .utils.logger import Logger
from .utils.ofVersionAdapter import OFVersionAdapter

class FvSolutionWriter:
    """
    Generates the fvSolution file using a unified config object and a
    single, intelligent Jinja2 template.

    Includes mesh-adaptive system that automatically adjusts solver settings
    based on checkMesh quality metrics.
    """
    def __init__(self, config: dict, case_directory: str):
        """The constructor now takes the unified config object."""
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("solver_setup").get_logger()

        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))
        self.version_adapter = OFVersionAdapter(self.config['openfoam_version'])

    def write_fvSolution_file(self):
        """
        Generates the fvSolution file by rendering a template with the
        solver settings defined in the simulation profile.

        If mesh-adaptive system is enabled and checkMesh log exists,
        solver settings will be automatically adjusted for mesh quality.
        """
        # Get fvSolution from config
        fvSolution = self.config['fvSolution']

        # Apply mesh-adaptive adjustments if enabled
        mesh_adaptive_enabled = self.config.get('numerics', {}).get('mesh_adaptive', True)

        if mesh_adaptive_enabled:
            fvSolution, quality_report = self._apply_mesh_adaptive_solver(fvSolution)

            # Print quality report if mesh was analyzed
            if quality_report and quality_report.get('tier'):
                self._print_quality_report(quality_report)

        # This single method replaces all the previous private _get... methods.
        template = self.jinja_env.get_template("fvSolution.tpl")

        # The template will use these dictionaries to build the file.
        # This data comes directly from your sim_*.py profile.
        context = {
            "header": self.version_adapter.get_foam_file_header("dictionary", "fvSolution"),
            "fvSolution": fvSolution,
            "template_vars": self.config.get('template_vars', {}),
            "openfoam_version": self.config.get('openfoam_version', '8'),
            "openfoam_major_version": self.config.get('openfoam_major_version', 8)
        }

        output_path = os.path.join(self.case_dir, "system", "fvSolution")
        with open(output_path, 'w') as f:
            f.write(template.render(context))
        self.log.info(f"Successfully wrote fvSolution file to {output_path}")

    def _apply_mesh_adaptive_solver(self, base_fvsolution: dict) -> tuple:
        """
        Apply mesh-adaptive adjustments to solver settings based on checkMesh quality.

        Args:
            base_fvsolution: Base fvSolution dict from numerics profile

        Returns:
            (adjusted_fvsolution, quality_report) tuple
        """
        try:
            from config.mesh_adaptive_solver import MeshAdaptiveSolverSettings

            # Find checkMesh log
            checkmesh_log = Path(self.case_dir) / "logs" / "log.checkMesh"
            if not checkmesh_log.exists():
                self.log.debug("checkMesh log not found, skipping mesh-adaptive adjustments")
                return base_fvsolution, {}

            # Create adapter and analyze mesh
            adapter = MeshAdaptiveSolverSettings()
            adapter.analyze_checkmesh_log(str(checkmesh_log))

            # Get profile name
            profile_name = self.config.get('numerics', {}).get('profile', 'standard')

            # Adjust fvSolution
            adjusted_fvsolution = adapter.adjust_fvsolution_for_mesh(base_fvsolution, profile_name)

            # Get quality report
            quality_report = adapter.get_quality_report()

            # Log major adjustments
            if adjusted_fvsolution != base_fvsolution:
                tier = adapter.mesh_quality_tier
                self.log.info(f"🔧 Mesh-Adaptive System: Detected {tier} quality mesh")
                self.log.info(f"   Adjusted fvSolution for mesh quality")

                # Log specific changes
                pimple_base = base_fvsolution.get('PIMPLE', {})
                pimple_adj = adjusted_fvsolution.get('PIMPLE', {})

                if pimple_base.get('nOuterCorrectors') != pimple_adj.get('nOuterCorrectors'):
                    self.log.info(f"   nOuterCorrectors: {pimple_base.get('nOuterCorrectors')} → {pimple_adj.get('nOuterCorrectors')}")

                if pimple_base.get('nNonOrthogonalCorrectors') != pimple_adj.get('nNonOrthogonalCorrectors'):
                    self.log.info(f"   nNonOrthogonalCorrectors: {pimple_base.get('nNonOrthogonalCorrectors')} → {pimple_adj.get('nNonOrthogonalCorrectors')}")

                relax_base = base_fvsolution.get('relaxationFactors', {}).get('fields', {})
                relax_adj = adjusted_fvsolution.get('relaxationFactors', {}).get('fields', {})

                if relax_base.get('p') != relax_adj.get('p'):
                    self.log.info(f"   p relaxation: {relax_base.get('p')} → {relax_adj.get('p')}")

            return adjusted_fvsolution, quality_report

        except ImportError:
            self.log.warning("Mesh-adaptive system not available, using base settings")
            return base_fvsolution, {}
        except Exception as e:
            self.log.warning(f"Mesh-adaptive adjustment failed: {e}, using base settings")
            return base_fvsolution, {}

    def _print_quality_report(self, quality_report: dict):
        """Print mesh quality report to log with explicit warnings for poor meshes."""
        tier = quality_report.get('tier', 'UNKNOWN')
        metrics = quality_report.get('metrics', {})
        recommendations = quality_report.get('recommendations', [])

        self.log.info("="*70)
        self.log.info(f"MESH QUALITY REPORT - {tier}")
        self.log.info("="*70)

        # Print metrics
        if metrics:
            skew = metrics.get('max_skewness')
            ortho = metrics.get('max_non_orthogonality')
            aspect = metrics.get('max_aspect_ratio')

            if skew:
                self.log.info(f"  Max Skewness: {skew:.2f}")
            if ortho:
                self.log.info(f"  Max Non-Orthogonality: {ortho:.1f}°")
            if aspect:
                self.log.info(f"  Max Aspect Ratio: {aspect:.1f}")

        # EXPLICIT WARNINGS for POOR/CRITICAL meshes
        if tier in ['POOR', 'CRITICAL']:
            self.log.warning("")
            self.log.warning("⚠️  MESH QUALITY WARNING ⚠️")
            self.log.warning("="*70)
            self.log.warning("The mesh-adaptive system has stabilized your solver settings,")
            self.log.warning("but this introduces NUMERICAL DIFFUSION and degrades accuracy.")
            self.log.warning("")
            self.log.warning("ACCURACY IMPACTS:")
            self.log.warning("  • Wall shear stress: May be under-predicted by 10-30%")
            self.log.warning("  • Pressure drops: May be inaccurate by 5-15%")
            self.log.warning("  • Flow patterns: Recirculation zones may be smoothed")
            self.log.warning("")
            self.log.warning("RECOMMENDED ACTION:")
            self.log.warning("  1. REMESH with improved snappyHexMesh settings")
            self.log.warning("  2. Target: Skewness <3.0, Non-orthogonality <70°")
            self.log.warning("  3. See: docs/MESH_QUALITY_WARNINGS.md for guidance")
            self.log.warning("")
            self.log.warning("CURRENT RESULTS:")
            self.log.warning("  ✓ Should converge (solver stabilized)")
            self.log.warning("  ✗ May not be accurate (numerical diffusion)")
            self.log.warning("  ✗ NOT suitable for publications or clinical decisions")
            self.log.warning("")
            self.log.warning("The adaptive system is a SAFETY NET, not a solution.")
            self.log.warning("Use it for initial testing, then IMPROVE THE MESH.")
            self.log.warning("="*70)
            self.log.warning("")

        # Print recommendations
        if recommendations:
            self.log.info("")
            for rec in recommendations:
                self.log.info(f"  {rec}")

        self.log.info("="*70)