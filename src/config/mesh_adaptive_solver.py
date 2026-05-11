"""
Mesh-Quality-Aware Solver Settings Adjuster

Automatically adjusts fvSolution and fvSchemes settings based on checkMesh results.
Ensures numerical stability by adapting correctors, relaxation factors, and tolerances
to mesh quality (skewness, non-orthogonality, aspect ratio).

Philosophy:
- Poor mesh → More correctors, stronger relaxation, relaxed tolerances
- Good mesh → Fewer correctors, lighter relaxation, tight tolerances
- Profile-aware: Enhances robust/standard/accurate profiles based on mesh reality

OpenFOAM 12 Compatible - Works with foamRun solver modules
"""

from typing import Dict, Any
from pathlib import Path
import re


class MeshAdaptiveSolverSettings:
    """
    Adjusts solver settings based on mesh quality metrics from checkMesh.

    Mesh Quality Tiers:
    - EXCELLENT: skew<1.5, ortho<55, aspect<20
    - GOOD:      skew<2.5, ortho<65, aspect<30  (Standard mesh)
    - FAIR:      skew<4.0, ortho<70, aspect<50
    - POOR:      skew<6.0, ortho<75, aspect<100
    - CRITICAL:  skew≥6.0, ortho≥75, aspect≥100 (May not converge)
    """

    def __init__(self):
        self.mesh_quality_tier = None
        self.metrics = {}

    def analyze_checkmesh_log(self, checkmesh_log_path: str) -> Dict[str, float]:
        """
        Parse checkMesh log and extract quality metrics.

        Args:
            checkmesh_log_path: Path to log.checkMesh file

        Returns:
            dict with keys: max_skewness, max_non_orthogonality, max_aspect_ratio
        """
        try:
            with open(checkmesh_log_path, "r") as f:
                content = f.read()
        except FileNotFoundError:
            # Default to conservative assumptions if log not found
            return {"max_skewness": 4.0, "max_non_orthogonality": 65.0, "max_aspect_ratio": 30.0}

        metrics = {}

        # Extract skewness
        skew_match = re.search(r"Max skewness = ([\d.]+)", content)
        if skew_match:
            metrics["max_skewness"] = float(skew_match.group(1))

        # Extract non-orthogonality
        ortho_match = re.search(r"Mesh non-orthogonality Max: ([\d.]+)", content)
        if ortho_match:
            metrics["max_non_orthogonality"] = float(ortho_match.group(1))

        # Extract aspect ratio
        aspect_match = re.search(r"Max aspect ratio = ([\d.]+)", content)
        if aspect_match:
            metrics["max_aspect_ratio"] = float(aspect_match.group(1))

        self.metrics = metrics
        self.mesh_quality_tier = self._determine_quality_tier(metrics)

        return metrics

    def _determine_quality_tier(self, metrics: Dict[str, float]) -> str:
        """Determine mesh quality tier based on metrics."""
        skew = metrics.get("max_skewness", 10.0)
        ortho = metrics.get("max_non_orthogonality", 80.0)
        aspect = metrics.get("max_aspect_ratio", 100.0)

        # CRITICAL - likely to diverge
        if skew >= 6.0 or ortho >= 75 or aspect >= 100:
            return "CRITICAL"

        # POOR - needs heavy stabilization
        if skew >= 4.0 or ortho >= 70 or aspect >= 50:
            return "POOR"

        # FAIR - acceptable with adjustments
        if skew >= 2.5 or ortho >= 65 or aspect >= 30:
            return "FAIR"

        # GOOD - standard settings work well
        if skew >= 1.5 or ortho >= 55 or aspect >= 20:
            return "GOOD"

        # EXCELLENT - can use aggressive settings
        return "EXCELLENT"

    def adjust_fvsolution_for_mesh(self, base_fvsolution: Dict[str, Any], profile_name: str) -> Dict[str, Any]:
        """
        Adjust fvSolution PIMPLE settings based on mesh quality.

        Args:
            base_fvsolution: Base fvSolution dict from profile
            profile_name: 'robust', 'standard', or 'accurate'

        Returns:
            Adjusted fvSolution dict
        """
        if not self.mesh_quality_tier:
            # If not analyzed, assume FAIR quality
            self.mesh_quality_tier = "FAIR"

        tier = self.mesh_quality_tier
        self.metrics.get("max_skewness", 3.0)
        ortho = self.metrics.get("max_non_orthogonality", 65.0)

        # Start with base settings
        adjusted = base_fvsolution.copy()

        # ========== ADJUST CORRECTORS ==========
        nOuterCorrectors, nCorrectors, nNonOrthogonalCorrectors = self._get_correctors_for_quality(
            tier, profile_name, ortho
        )

        if "PIMPLE" not in adjusted:
            adjusted["PIMPLE"] = {}

        adjusted["PIMPLE"]["nOuterCorrectors"] = nOuterCorrectors
        adjusted["PIMPLE"]["nCorrectors"] = nCorrectors
        adjusted["PIMPLE"]["nNonOrthogonalCorrectors"] = nNonOrthogonalCorrectors

        # ========== ADJUST RELAXATION FACTORS ==========
        p_relax, u_relax = self._get_relaxation_for_quality(tier, profile_name)

        if "relaxationFactors" not in adjusted:
            adjusted["relaxationFactors"] = {"fields": {}, "equations": {}}

        adjusted["relaxationFactors"]["fields"]["p"] = p_relax
        adjusted["relaxationFactors"]["equations"]["U"] = u_relax
        adjusted["relaxationFactors"]["equations"]["k"] = u_relax
        adjusted["relaxationFactors"]["equations"]["omega"] = u_relax
        adjusted["relaxationFactors"]["equations"]["epsilon"] = u_relax

        # ========== ADJUST TOLERANCES ==========
        p_tol, u_tol = self._get_tolerances_for_quality(tier, profile_name)

        if "residualControl" not in adjusted:
            adjusted["residualControl"] = {}

        adjusted["residualControl"]["p"] = p_tol
        adjusted["residualControl"]["U"] = u_tol
        adjusted["residualControl"]["k"] = u_tol
        adjusted["residualControl"]["omega"] = u_tol

        # ========== ADD CORRECTOR RESIDUAL CONTROL ==========
        # For poor meshes, add inner loop convergence criteria
        if tier in ["POOR", "CRITICAL"]:
            adjusted["PIMPLE"]["correctorResidualControl"] = {
                "p": {"tolerance": p_tol * 10, "relTol": 0},
                "U": {"tolerance": u_tol * 10, "relTol": 0},
            }
            adjusted["PIMPLE"]["outerCorrectorResidualControl"] = {
                "p": {"tolerance": p_tol, "relTol": 0},
                "U": {"tolerance": u_tol, "relTol": 0},
                "(k|epsilon|omega)": {"tolerance": u_tol, "relTol": 0},
            }

        return adjusted

    def _get_correctors_for_quality(self, tier: str, profile: str, ortho: float) -> tuple:
        """
        Determine corrector counts based on mesh quality and profile.

        Returns:
            (nOuterCorrectors, nCorrectors, nNonOrthogonalCorrectors)
        """
        # Non-orthogonal correctors based on mesh non-orthogonality
        if ortho < 55:
            nNonOrtho = 1
        elif ortho < 65:
            nNonOrtho = 2
        elif ortho < 70:
            nNonOrtho = 3
        elif ortho < 75:
            nNonOrtho = 4
        else:
            nNonOrtho = 5  # Critical - maximum correction needed

        # Base correctors by profile and quality
        corrector_matrix = {
            "robust": {
                "EXCELLENT": (2, 2, nNonOrtho),
                "GOOD": (3, 2, nNonOrtho),
                "FAIR": (3, 3, nNonOrtho),
                "POOR": (4, 3, nNonOrtho),
                "CRITICAL": (5, 4, nNonOrtho),
            },
            "standard": {
                "EXCELLENT": (2, 2, nNonOrtho),
                "GOOD": (2, 2, nNonOrtho),
                "FAIR": (3, 2, nNonOrtho),
                "POOR": (4, 3, nNonOrtho),
                "CRITICAL": (5, 3, nNonOrtho),
            },
            "accurate": {
                "EXCELLENT": (3, 3, nNonOrtho),
                "GOOD": (3, 3, nNonOrtho),
                "FAIR": (4, 3, nNonOrtho),
                "POOR": (5, 4, nNonOrtho),
                "CRITICAL": (6, 4, nNonOrtho),
            },
        }

        return corrector_matrix.get(profile, corrector_matrix["standard"])[tier]

    def _get_relaxation_for_quality(self, tier: str, profile: str) -> tuple:
        """
        Determine relaxation factors based on mesh quality.

        Principle: Worse mesh → Stronger relaxation (smaller factors)

        Returns:
            (p_relaxation, U_relaxation)
        """
        relaxation_matrix = {
            "robust": {
                "EXCELLENT": (0.3, 0.6),
                "GOOD": (0.2, 0.5),
                "FAIR": (0.2, 0.5),
                "POOR": (0.15, 0.4),
                "CRITICAL": (0.1, 0.3),
            },
            "standard": {
                "EXCELLENT": (0.4, 0.8),
                "GOOD": (0.3, 0.7),
                "FAIR": (0.3, 0.7),
                "POOR": (0.2, 0.5),
                "CRITICAL": (0.15, 0.4),
            },
            "accurate": {
                "EXCELLENT": (0.5, 0.9),
                "GOOD": (0.5, 0.9),
                "FAIR": (0.4, 0.8),
                "POOR": (0.3, 0.6),
                "CRITICAL": (0.2, 0.5),
            },
        }

        return relaxation_matrix.get(profile, relaxation_matrix["standard"])[tier]

    def _get_tolerances_for_quality(self, tier: str, profile: str) -> tuple:
        """
        Determine residual tolerances based on mesh quality.

        Principle: Worse mesh → Relaxed tolerances (can't achieve tight convergence)

        Returns:
            (p_tolerance, U_tolerance)
        """
        tolerance_matrix = {
            "robust": {
                "EXCELLENT": (1e-5, 1e-5),
                "GOOD": (1e-5, 1e-5),
                "FAIR": (1e-4, 1e-4),
                "POOR": (5e-4, 5e-4),
                "CRITICAL": (1e-3, 1e-3),
            },
            "standard": {
                "EXCELLENT": (1e-6, 1e-6),
                "GOOD": (1e-6, 1e-6),
                "FAIR": (5e-6, 5e-6),
                "POOR": (1e-5, 1e-5),
                "CRITICAL": (5e-5, 5e-5),
            },
            "accurate": {
                "EXCELLENT": (1e-8, 1e-8),
                "GOOD": (1e-7, 1e-7),
                "FAIR": (1e-6, 1e-6),
                "POOR": (5e-6, 5e-6),
                "CRITICAL": (1e-5, 1e-5),
            },
        }

        return tolerance_matrix.get(profile, tolerance_matrix["standard"])[tier]

    def adjust_fvschemes_for_mesh(self, base_fvschemes: Dict[str, Any], profile_name: str) -> Dict[str, Any]:
        """
        Adjust fvSchemes laplacian scheme based on mesh non-orthogonality.

        High non-orthogonality requires limited correction to prevent overshoot.
        """
        if not self.mesh_quality_tier:
            self.mesh_quality_tier = "FAIR"

        adjusted = base_fvschemes.copy()
        ortho = self.metrics.get("max_non_orthogonality", 65.0)
        skew = self.metrics.get("max_skewness", 3.0)

        # Adjust laplacian scheme based on non-orthogonality
        if ortho < 60 and skew < 2.0:
            # Good quality - use standard corrected
            laplacian = "Gauss linear corrected"
        elif ortho < 70 and skew < 4.0:
            # Fair quality - use limited correction
            laplacian = "Gauss linear limited corrected 0.5"
        else:
            # Poor quality - heavy limiting
            laplacian = "Gauss linear limited corrected 0.33"

        if "laplacianSchemes" not in adjusted:
            adjusted["laplacianSchemes"] = {}

        adjusted["laplacianSchemes"]["default"] = laplacian

        # For very high skewness, also limit gradients more aggressively
        if skew > 4.0:
            if "gradSchemes" not in adjusted:
                adjusted["gradSchemes"] = {}
            # Tighter gradient limiting
            adjusted["gradSchemes"]["default"] = "cellLimited Gauss linear 0.5"
            adjusted["gradSchemes"]["grad(U)"] = "cellLimited Gauss linear 0.5"

        return adjusted

    def get_quality_report(self) -> Dict[str, Any]:
        """Generate a quality report with recommendations."""
        if not self.mesh_quality_tier:
            return {"status": "not_analyzed"}

        report = {"tier": self.mesh_quality_tier, "metrics": self.metrics, "recommendations": []}

        # Generate recommendations
        tier = self.mesh_quality_tier
        skew = self.metrics.get("max_skewness", 0)
        ortho = self.metrics.get("max_non_orthogonality", 0)
        aspect = self.metrics.get("max_aspect_ratio", 0)

        if tier == "CRITICAL":
            report["recommendations"].extend(
                [
                    "🔴 CRITICAL: Mesh quality may prevent convergence",
                    f"   Skewness={skew:.2f} (limit: 6.0), Ortho={ortho:.1f}° (limit: 75°)",
                    "   → Solver settings automatically adjusted for maximum stability",
                    "   → Consider remeshing with coarser settings",
                    "   → Use 'robust' profile with 1st order schemes",
                ]
            )
        elif tier == "POOR":
            report["recommendations"].extend(
                [
                    "⚠️  POOR: Mesh quality requires stabilization",
                    f"   Skewness={skew:.2f}, Ortho={ortho:.1f}°, Aspect={aspect:.1f}",
                    "   → Increased correctors and relaxation applied",
                    "   → Tolerances relaxed to prevent stalling",
                    "   → Monitor residuals carefully",
                ]
            )
        elif tier == "FAIR":
            report["recommendations"].extend(
                [
                    "✓ FAIR: Mesh quality acceptable with adjustments",
                    "   → Solver settings optimized for this mesh",
                    "   → Should converge reliably",
                ]
            )
        else:
            report["recommendations"].extend(
                [f"✅ {tier}: Excellent mesh quality", "   → Using optimal solver settings for accuracy"]
            )

        return report


def apply_mesh_adaptive_settings(
    case_dir: str, profile_name: str, base_fvsolution: Dict[str, Any], base_fvschemes: Dict[str, Any]
) -> tuple:
    """
    Convenience function to apply mesh-adaptive settings.

    Args:
        case_dir: Path to OpenFOAM case directory
        profile_name: 'robust', 'standard', or 'accurate'
        base_fvsolution: Base fvSolution dict from profile
        base_fvschemes: Base fvSchemes dict from profile

    Returns:
        (adjusted_fvsolution, adjusted_fvschemes, quality_report)
    """
    adapter = MeshAdaptiveSolverSettings()

    # Find checkMesh log
    checkmesh_log = Path(case_dir) / "logs" / "log.checkMesh"
    if not checkmesh_log.exists():
        checkmesh_log = Path(case_dir) / "openfoam" / "logs" / "log.checkMesh"

    # Analyze mesh quality
    if checkmesh_log.exists():
        adapter.analyze_checkmesh_log(str(checkmesh_log))

    # Adjust settings
    adjusted_fvsolution = adapter.adjust_fvsolution_for_mesh(base_fvsolution, profile_name)
    adjusted_fvschemes = adapter.adjust_fvschemes_for_mesh(base_fvschemes, profile_name)
    quality_report = adapter.get_quality_report()

    return adjusted_fvsolution, adjusted_fvschemes, quality_report
