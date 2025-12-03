"""
Mesh Quality Analysis and Validation Module
============================================

This module provides mesh quality assessment tools for cardiovascular CFD simulations.
It analyzes OpenFOAM checkMesh output and provides:
- Quality tier classification (EXCELLENT/GOOD/FAIR/POOR/CRITICAL)
- Automatic solver setting recommendations based on mesh quality
- Grid Convergence Index (GCI) calculations for mesh independence studies

Based on best practices from SimVascular and OpenFOAM cardiovascular CFD literature.

Author: AortaCFD Team
Status: UNDER DEVELOPMENT - Features may change
"""

import re
import os
import numpy as np
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from .logger import Logger


class MeshQualityTier(Enum):
    """
    Mesh quality classification tiers.

    Based on OpenFOAM checkMesh metrics and cardiovascular CFD best practices.
    Higher tiers allow more aggressive solver settings.
    """
    EXCELLENT = "EXCELLENT"  # Publication quality, can use aggressive schemes
    GOOD = "GOOD"            # Standard production runs
    FAIR = "FAIR"            # May need conservative settings
    POOR = "POOR"            # Requires robust/conservative schemes
    CRITICAL = "CRITICAL"    # High risk of divergence, mesh needs improvement


@dataclass
class MeshQualityMetrics:
    """
    Container for mesh quality metrics from checkMesh.

    Attributes:
        max_skewness: Maximum cell skewness (0 = perfect, >4 = poor)
        max_non_orthogonality: Maximum face non-orthogonality in degrees
        max_aspect_ratio: Maximum cell aspect ratio
        num_cells: Total number of cells
        num_faces: Total number of faces
        num_points: Total number of points
        bounding_box: Mesh bounding box dimensions

    Status: UNDER DEVELOPMENT
    """
    max_skewness: float = 0.0
    max_non_orthogonality: float = 0.0
    max_aspect_ratio: float = 0.0
    avg_non_orthogonality: float = 0.0
    num_cells: int = 0
    num_faces: int = 0
    num_points: int = 0
    bounding_box: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    mesh_ok: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class SolverRecommendation:
    """
    Solver setting recommendations based on mesh quality.

    Status: UNDER DEVELOPMENT
    """
    profile: str  # "accurate", "standard", "robust", "aggressive"
    relaxation_U: float
    relaxation_p: float
    n_outer_correctors: int
    n_correctors: int
    n_non_ortho_correctors: int
    convection_scheme: str
    time_scheme: str
    notes: List[str] = field(default_factory=list)


class MeshQualityAnalyzer:
    """
    Analyze mesh quality from OpenFOAM checkMesh output.

    Provides quality tier classification and solver recommendations
    based on mesh metrics.

    Example:
        >>> analyzer = MeshQualityAnalyzer(case_directory="/path/to/case")
        >>> metrics = analyzer.run_checkmesh()
        >>> tier = analyzer.get_quality_tier(metrics)
        >>> recommendations = analyzer.get_solver_recommendations(tier)

    Status: UNDER DEVELOPMENT - API may change
    """

    # Quality thresholds based on cardiovascular CFD best practices
    # Reference: OpenFOAM User Guide, SimVascular documentation
    THRESHOLDS = {
        MeshQualityTier.EXCELLENT: {
            'max_skewness': 1.5,
            'max_non_orthogonality': 55.0,
            'max_aspect_ratio': 20.0,
        },
        MeshQualityTier.GOOD: {
            'max_skewness': 2.5,
            'max_non_orthogonality': 65.0,
            'max_aspect_ratio': 30.0,
        },
        MeshQualityTier.FAIR: {
            'max_skewness': 4.0,
            'max_non_orthogonality': 70.0,
            'max_aspect_ratio': 50.0,
        },
        MeshQualityTier.POOR: {
            'max_skewness': 6.0,
            'max_non_orthogonality': 75.0,
            'max_aspect_ratio': 100.0,
        },
        # CRITICAL: anything worse than POOR thresholds
    }

    def __init__(self, case_directory: str):
        """
        Initialize mesh quality analyzer.

        Args:
            case_directory: Path to OpenFOAM case directory
        """
        self.case_dir = case_directory
        self.log = Logger("mesh_quality").get_logger()

    def run_checkmesh(self, parallel: bool = False, n_procs: int = 1) -> MeshQualityMetrics:
        """
        Run OpenFOAM checkMesh and parse results.

        Args:
            parallel: Whether mesh is decomposed for parallel
            n_procs: Number of processors (if parallel)

        Returns:
            MeshQualityMetrics with parsed results

        Status: UNDER DEVELOPMENT
        """
        import subprocess

        metrics = MeshQualityMetrics()

        try:
            if parallel and n_procs > 1:
                cmd = f"mpirun -np {n_procs} checkMesh -parallel -case {self.case_dir}"
            else:
                cmd = f"checkMesh -case {self.case_dir}"

            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=300
            )

            output = result.stdout + result.stderr
            metrics = self._parse_checkmesh_output(output)

        except subprocess.TimeoutExpired:
            self.log.error("checkMesh timed out after 5 minutes")
            metrics.errors.append("checkMesh timeout")
            metrics.mesh_ok = False
        except Exception as e:
            self.log.error(f"Failed to run checkMesh: {e}")
            metrics.errors.append(str(e))
            metrics.mesh_ok = False

        return metrics

    def _parse_checkmesh_output(self, output: str) -> MeshQualityMetrics:
        """
        Parse checkMesh output text to extract metrics.

        Status: UNDER DEVELOPMENT
        """
        metrics = MeshQualityMetrics()

        # Parse cell count
        match = re.search(r'cells:\s*(\d+)', output)
        if match:
            metrics.num_cells = int(match.group(1))

        # Parse face count
        match = re.search(r'faces:\s*(\d+)', output)
        if match:
            metrics.num_faces = int(match.group(1))

        # Parse point count
        match = re.search(r'points:\s*(\d+)', output)
        if match:
            metrics.num_points = int(match.group(1))

        # Parse max skewness
        match = re.search(r'Max skewness\s*=\s*([\d.e+-]+)', output)
        if match:
            metrics.max_skewness = float(match.group(1))

        # Parse max non-orthogonality
        match = re.search(r'Mesh non-orthogonality Max:\s*([\d.e+-]+)', output)
        if match:
            metrics.max_non_orthogonality = float(match.group(1))

        # Parse average non-orthogonality
        match = re.search(r'average:\s*([\d.e+-]+)', output)
        if match:
            metrics.avg_non_orthogonality = float(match.group(1))

        # Parse max aspect ratio
        match = re.search(r'Max aspect ratio\s*=\s*([\d.e+-]+)', output)
        if match:
            metrics.max_aspect_ratio = float(match.group(1))

        # Check for mesh errors
        if 'FAILED' in output or 'Mesh has invalid' in output:
            metrics.mesh_ok = False
            # Extract error messages
            for line in output.split('\n'):
                if 'FAILED' in line or 'invalid' in line.lower():
                    metrics.errors.append(line.strip())

        # Check for warnings
        for line in output.split('\n'):
            if 'warning' in line.lower() or '***' in line:
                metrics.warnings.append(line.strip())

        return metrics

    def get_quality_tier(self, metrics: MeshQualityMetrics) -> MeshQualityTier:
        """
        Classify mesh quality into tier based on metrics.

        Args:
            metrics: MeshQualityMetrics from checkMesh

        Returns:
            MeshQualityTier classification

        Status: UNDER DEVELOPMENT
        """
        if not metrics.mesh_ok:
            return MeshQualityTier.CRITICAL

        # Check against thresholds from best to worst
        for tier in [MeshQualityTier.EXCELLENT, MeshQualityTier.GOOD,
                     MeshQualityTier.FAIR, MeshQualityTier.POOR]:
            thresholds = self.THRESHOLDS[tier]

            if (metrics.max_skewness <= thresholds['max_skewness'] and
                metrics.max_non_orthogonality <= thresholds['max_non_orthogonality'] and
                metrics.max_aspect_ratio <= thresholds['max_aspect_ratio']):
                return tier

        return MeshQualityTier.CRITICAL

    def get_solver_recommendations(self, tier: MeshQualityTier) -> SolverRecommendation:
        """
        Get solver setting recommendations based on mesh quality tier.

        Args:
            tier: MeshQualityTier classification

        Returns:
            SolverRecommendation with suggested settings

        Status: UNDER DEVELOPMENT
        """
        recommendations = {
            MeshQualityTier.EXCELLENT: SolverRecommendation(
                profile="accurate",
                relaxation_U=0.9,
                relaxation_p=0.5,
                n_outer_correctors=3,
                n_correctors=3,
                n_non_ortho_correctors=1,
                convection_scheme="Gauss LUST grad(U)",
                time_scheme="CrankNicolson 0.9",
                notes=["Mesh quality allows aggressive schemes",
                       "Can use higher-order discretization"]
            ),
            MeshQualityTier.GOOD: SolverRecommendation(
                profile="standard",
                relaxation_U=0.7,
                relaxation_p=0.3,
                n_outer_correctors=2,
                n_correctors=2,
                n_non_ortho_correctors=1,
                convection_scheme="Gauss linearUpwind grad(U)",
                time_scheme="backward",
                notes=["Standard settings for production runs"]
            ),
            MeshQualityTier.FAIR: SolverRecommendation(
                profile="standard",
                relaxation_U=0.6,
                relaxation_p=0.25,
                n_outer_correctors=3,
                n_correctors=2,
                n_non_ortho_correctors=2,
                convection_scheme="Gauss linearUpwind grad(U)",
                time_scheme="backward",
                notes=["Increased non-orthogonal corrections recommended",
                       "Consider mesh improvement for better accuracy"]
            ),
            MeshQualityTier.POOR: SolverRecommendation(
                profile="robust",
                relaxation_U=0.5,
                relaxation_p=0.2,
                n_outer_correctors=5,
                n_correctors=3,
                n_non_ortho_correctors=2,
                convection_scheme="Gauss upwind",
                time_scheme="Euler",
                notes=["Using conservative schemes for stability",
                       "Accuracy reduced - recommend mesh improvement",
                       "First-order schemes may introduce numerical diffusion"]
            ),
            MeshQualityTier.CRITICAL: SolverRecommendation(
                profile="robust",
                relaxation_U=0.3,
                relaxation_p=0.1,
                n_outer_correctors=10,
                n_correctors=3,
                n_non_ortho_correctors=3,
                convection_scheme="Gauss upwind",
                time_scheme="Euler",
                notes=["HIGH RISK OF DIVERGENCE",
                       "Mesh quality is critical - strongly recommend remeshing",
                       "Results may not be reliable even if converged"]
            ),
        }

        return recommendations.get(tier, recommendations[MeshQualityTier.POOR])

    def generate_report(self, metrics: MeshQualityMetrics) -> str:
        """
        Generate human-readable mesh quality report.

        Status: UNDER DEVELOPMENT
        """
        tier = self.get_quality_tier(metrics)
        recommendations = self.get_solver_recommendations(tier)

        report = []
        report.append("=" * 60)
        report.append("MESH QUALITY ANALYSIS REPORT")
        report.append("=" * 60)
        report.append("")
        report.append(f"Quality Tier: {tier.value}")
        report.append("")
        report.append("Metrics:")
        report.append(f"  Cells:              {metrics.num_cells:,}")
        report.append(f"  Max Skewness:       {metrics.max_skewness:.2f}")
        report.append(f"  Max Non-Ortho:      {metrics.max_non_orthogonality:.1f}°")
        report.append(f"  Avg Non-Ortho:      {metrics.avg_non_orthogonality:.1f}°")
        report.append(f"  Max Aspect Ratio:   {metrics.max_aspect_ratio:.1f}")
        report.append("")
        report.append("Recommended Solver Settings:")
        report.append(f"  Profile:            {recommendations.profile}")
        report.append(f"  Relaxation (U):     {recommendations.relaxation_U}")
        report.append(f"  Relaxation (p):     {recommendations.relaxation_p}")
        report.append(f"  Outer Correctors:   {recommendations.n_outer_correctors}")
        report.append(f"  Non-Ortho Corr:     {recommendations.n_non_ortho_correctors}")
        report.append(f"  Convection Scheme:  {recommendations.convection_scheme}")
        report.append(f"  Time Scheme:        {recommendations.time_scheme}")
        report.append("")

        if recommendations.notes:
            report.append("Notes:")
            for note in recommendations.notes:
                report.append(f"  - {note}")
            report.append("")

        if metrics.warnings:
            report.append("Warnings:")
            for warning in metrics.warnings[:5]:  # Limit to first 5
                report.append(f"  - {warning}")
            report.append("")

        if metrics.errors:
            report.append("ERRORS:")
            for error in metrics.errors:
                report.append(f"  - {error}")
            report.append("")

        report.append("=" * 60)

        return "\n".join(report)


class GridConvergenceIndex:
    """
    Grid Convergence Index (GCI) Calculator for Mesh Independence Studies.

    Implements the Richardson extrapolation method to estimate discretization
    error and assess mesh independence. Based on Roache (1997) and ASME V&V 20.

    Example:
        >>> gci = GridConvergenceIndex()
        >>> result = gci.calculate(
        ...     h=[1.0, 0.5, 0.25],  # Mesh sizes (coarse to fine)
        ...     f=[100.2, 98.5, 98.1]  # Results (e.g., max WSS)
        ... )
        >>> print(f"GCI_fine = {result['GCI_fine_percent']:.2f}%")

    Reference:
        Roache, P.J. (1997). "Quantification of Uncertainty in Computational
        Fluid Dynamics". Annual Review of Fluid Mechanics, 29:123-160.

    Status: UNDER DEVELOPMENT - Validation ongoing
    """

    def __init__(self, safety_factor: float = 1.25):
        """
        Initialize GCI calculator.

        Args:
            safety_factor: Safety factor for GCI (1.25 for 3+ grids, 3.0 for 2 grids)
        """
        self.Fs = safety_factor
        self.log = Logger("gci").get_logger()

    def calculate(self, h: List[float], f: List[float],
                  p_expected: float = 2.0) -> Dict:
        """
        Calculate Grid Convergence Index.

        Args:
            h: List of characteristic mesh sizes [coarse, medium, fine]
            f: List of corresponding solution values [f_coarse, f_medium, f_fine]
            p_expected: Expected order of convergence (usually 2 for 2nd-order schemes)

        Returns:
            Dictionary with GCI results:
                - p_observed: Observed order of convergence
                - GCI_fine_percent: GCI for fine grid (%)
                - GCI_medium_percent: GCI for medium grid (%)
                - asymptotic_check: Ratio (should be ~1.0 for asymptotic range)
                - extrapolated_value: Richardson extrapolated value
                - converged: Whether solution is in asymptotic range

        Status: UNDER DEVELOPMENT
        """
        if len(h) < 3 or len(f) < 3:
            raise ValueError("Need at least 3 mesh levels for GCI calculation")

        # Sort by mesh size (finest first)
        sorted_data = sorted(zip(h, f))
        h1, f1 = sorted_data[0]  # Fine
        h2, f2 = sorted_data[1]  # Medium
        h3, f3 = sorted_data[2]  # Coarse

        # Refinement ratios
        r21 = h2 / h1
        r32 = h3 / h2

        # Solution differences
        eps32 = f3 - f2
        eps21 = f2 - f1

        # Check for monotonic convergence
        if abs(eps21) < 1e-15 or abs(eps32) < 1e-15:
            self.log.warning("Solutions are nearly identical - may be converged or oscillating")
            return {
                'p_observed': p_expected,
                'GCI_fine_percent': 0.0,
                'GCI_medium_percent': 0.0,
                'asymptotic_check': 1.0,
                'extrapolated_value': f1,
                'converged': True,
                'notes': ['Solutions nearly identical across meshes']
            }

        # Check convergence type
        s = np.sign(eps32 / eps21)
        if s < 0:
            self.log.warning("Oscillatory convergence detected")

        # Calculate observed order of convergence
        # Using iterative method for non-constant refinement ratios
        p = self._calculate_order(r21, r32, eps21, eps32, p_expected)

        # Calculate GCI
        e_a_21 = abs((f1 - f2) / f1) if abs(f1) > 1e-15 else abs(f1 - f2)
        e_a_32 = abs((f2 - f3) / f2) if abs(f2) > 1e-15 else abs(f2 - f3)

        GCI_fine = self.Fs * e_a_21 / (r21**p - 1)
        GCI_medium = self.Fs * e_a_32 / (r32**p - 1)

        # Asymptotic range check
        asymptotic_ratio = (r21**p * GCI_fine) / GCI_medium if GCI_medium > 0 else 1.0

        # Richardson extrapolation
        f_extrapolated = f1 + (f1 - f2) / (r21**p - 1)

        # Determine if converged
        converged = (0.95 <= asymptotic_ratio <= 1.05) and (GCI_fine * 100 < 5.0)

        result = {
            'p_observed': p,
            'GCI_fine_percent': GCI_fine * 100,
            'GCI_medium_percent': GCI_medium * 100,
            'asymptotic_check': asymptotic_ratio,
            'extrapolated_value': f_extrapolated,
            'converged': converged,
            'refinement_ratio_21': r21,
            'refinement_ratio_32': r32,
            'notes': []
        }

        # Add notes
        if not converged:
            if asymptotic_ratio < 0.95 or asymptotic_ratio > 1.05:
                result['notes'].append(
                    f"Not in asymptotic range (ratio={asymptotic_ratio:.3f}, should be ~1.0)"
                )
            if GCI_fine * 100 >= 5.0:
                result['notes'].append(
                    f"GCI_fine ({GCI_fine*100:.1f}%) exceeds 5% - consider finer mesh"
                )

        if p < 0.5 * p_expected:
            result['notes'].append(
                f"Observed order ({p:.2f}) much lower than expected ({p_expected})"
            )

        return result

    def _calculate_order(self, r21: float, r32: float,
                         eps21: float, eps32: float,
                         p_init: float) -> float:
        """
        Calculate observed order of convergence using fixed-point iteration.

        For non-constant refinement ratios, the order p must be solved iteratively.

        Status: UNDER DEVELOPMENT
        """
        if abs(r21 - r32) < 0.01:
            # Constant refinement ratio - direct formula
            ratio = eps32 / eps21
            if ratio > 0:
                return np.log(ratio) / np.log(r21)
            else:
                return p_init

        # Iterative solution for non-constant ratios
        p = p_init
        for _ in range(50):  # Max iterations
            s = np.sign(eps32 / eps21)
            q = np.log((r21**p - s) / (r32**p - s))
            p_new = abs(np.log(abs(eps32 / eps21)) + q) / np.log(r21)

            if abs(p_new - p) < 1e-6:
                break
            p = p_new

        return max(0.1, min(p, 5.0))  # Bound to reasonable range

    def generate_report(self, h: List[float], f: List[float],
                        quantity_name: str = "Value") -> str:
        """
        Generate a formatted GCI report.

        Status: UNDER DEVELOPMENT
        """
        result = self.calculate(h, f)

        report = []
        report.append("=" * 60)
        report.append("GRID CONVERGENCE INDEX (GCI) REPORT")
        report.append("=" * 60)
        report.append(f"Quantity: {quantity_name}")
        report.append("")
        report.append("Input Data:")
        report.append(f"  Coarse mesh (h={h[0]:.4f}): {quantity_name} = {f[0]:.6f}")
        report.append(f"  Medium mesh (h={h[1]:.4f}): {quantity_name} = {f[1]:.6f}")
        report.append(f"  Fine mesh   (h={h[2]:.4f}): {quantity_name} = {f[2]:.6f}")
        report.append("")
        report.append("Results:")
        report.append(f"  Observed order (p):     {result['p_observed']:.3f}")
        report.append(f"  GCI_fine:               {result['GCI_fine_percent']:.2f}%")
        report.append(f"  GCI_medium:             {result['GCI_medium_percent']:.2f}%")
        report.append(f"  Asymptotic check:       {result['asymptotic_check']:.4f} (target: ~1.0)")
        report.append(f"  Extrapolated value:     {result['extrapolated_value']:.6f}")
        report.append("")
        report.append(f"  Mesh Independence:      {'YES' if result['converged'] else 'NO'}")
        report.append("")

        if result['notes']:
            report.append("Notes:")
            for note in result['notes']:
                report.append(f"  - {note}")
            report.append("")

        report.append("Interpretation:")
        if result['converged']:
            report.append("  Solution is in asymptotic range and GCI < 5%.")
            report.append("  Mesh independence achieved - fine mesh results are reliable.")
        else:
            report.append("  Solution may not be mesh-independent.")
            report.append("  Consider additional refinement or check for modeling issues.")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


class MassBalanceChecker:
    """
    Mass balance verification for cardiovascular CFD simulations.

    Checks that mass (flow rate) is conserved across inlet and outlets
    at each timestep or time-averaged.

    Status: UNDER DEVELOPMENT
    """

    def __init__(self, tolerance_percent: float = 1.0):
        """
        Initialize mass balance checker.

        Args:
            tolerance_percent: Acceptable mass balance error (default 1%)
        """
        self.tolerance = tolerance_percent / 100.0
        self.log = Logger("mass_balance").get_logger()

    def check_instantaneous(self, inlet_flow: float,
                            outlet_flows: Dict[str, float]) -> Dict:
        """
        Check instantaneous mass balance.

        Args:
            inlet_flow: Inlet volumetric flow rate (m³/s)
            outlet_flows: Dict of outlet name -> flow rate (m³/s)

        Returns:
            Dict with mass balance results

        Status: UNDER DEVELOPMENT
        """
        total_outlet = sum(outlet_flows.values())
        error = abs(inlet_flow - total_outlet)
        error_percent = (error / abs(inlet_flow) * 100) if abs(inlet_flow) > 1e-15 else 0.0

        balanced = error_percent <= self.tolerance * 100

        result = {
            'inlet_flow': inlet_flow,
            'total_outlet_flow': total_outlet,
            'outlet_flows': outlet_flows,
            'error_absolute': error,
            'error_percent': error_percent,
            'balanced': balanced,
            'flow_splits': {}
        }

        # Calculate flow splits
        for outlet, flow in outlet_flows.items():
            result['flow_splits'][outlet] = (flow / inlet_flow * 100) if abs(inlet_flow) > 1e-15 else 0.0

        return result

    def check_time_averaged(self, inlet_flows: List[float],
                            outlet_flows_series: List[Dict[str, float]],
                            times: Optional[List[float]] = None) -> Dict:
        """
        Check time-averaged mass balance over a cardiac cycle.

        Args:
            inlet_flows: List of inlet flow rates at each timestep
            outlet_flows_series: List of outlet flow dicts at each timestep
            times: Optional list of time values for weighted averaging

        Returns:
            Dict with time-averaged mass balance results

        Status: UNDER DEVELOPMENT
        """
        n_steps = len(inlet_flows)

        if times is not None and len(times) == n_steps:
            # Time-weighted average
            dt = np.diff(times)
            weights = np.concatenate([[dt[0]], dt])
            inlet_avg = np.average(inlet_flows, weights=weights)

            outlet_avgs = {}
            for outlet in outlet_flows_series[0].keys():
                outlet_values = [step[outlet] for step in outlet_flows_series]
                outlet_avgs[outlet] = np.average(outlet_values, weights=weights)
        else:
            # Simple average
            inlet_avg = np.mean(inlet_flows)

            outlet_avgs = {}
            for outlet in outlet_flows_series[0].keys():
                outlet_values = [step[outlet] for step in outlet_flows_series]
                outlet_avgs[outlet] = np.mean(outlet_values)

        # Check instantaneous balance at each step
        max_error = 0.0
        for i, (inlet_q, outlet_q) in enumerate(zip(inlet_flows, outlet_flows_series)):
            step_result = self.check_instantaneous(inlet_q, outlet_q)
            max_error = max(max_error, step_result['error_percent'])

        # Time-averaged result
        result = self.check_instantaneous(inlet_avg, outlet_avgs)
        result['max_instantaneous_error'] = max_error
        result['n_timesteps'] = n_steps

        return result

    def generate_report(self, result: Dict) -> str:
        """
        Generate mass balance report.

        Status: UNDER DEVELOPMENT
        """
        report = []
        report.append("=" * 60)
        report.append("MASS BALANCE VERIFICATION REPORT")
        report.append("=" * 60)
        report.append("")
        report.append(f"Inlet Flow:        {result['inlet_flow']*1e6:.2f} mL/s")
        report.append(f"Total Outlet Flow: {result['total_outlet_flow']*1e6:.2f} mL/s")
        report.append(f"Mass Balance Error: {result['error_percent']:.4f}%")
        report.append("")
        report.append("Outlet Flow Distribution:")
        for outlet, split in result['flow_splits'].items():
            flow = result['outlet_flows'][outlet]
            report.append(f"  {outlet}: {flow*1e6:.2f} mL/s ({split:.1f}%)")
        report.append("")
        report.append(f"Mass Conservation: {'PASS' if result['balanced'] else 'FAIL'}")

        if 'max_instantaneous_error' in result:
            report.append(f"Max Instantaneous Error: {result['max_instantaneous_error']:.4f}%")
            report.append(f"Timesteps Analyzed: {result['n_timesteps']}")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)
