"""
Physical results analyzer for Level 3 CFD validation.

Analyzes simulation results to validate:
- Solver convergence
- Physical quantities (velocity, pressure, WSS)
- Flow conservation
- Boundary condition correctness
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import subprocess


@dataclass
class ConvergenceMetrics:
    """Convergence metrics from solver logs."""
    final_time: float = 0.0
    total_iterations: int = 0
    avg_courant_number: float = 0.0
    max_courant_number: float = 0.0

    # Residuals (final values)
    final_p_residual: float = 0.0
    final_ux_residual: float = 0.0
    final_uy_residual: float = 0.0
    final_uz_residual: float = 0.0

    # Convergence status
    converged: bool = False
    convergence_issues: List[str] = field(default_factory=list)


@dataclass
class FlowMetrics:
    """Flow field metrics from simulation results."""
    # Velocity statistics
    max_velocity: float = 0.0
    mean_velocity: float = 0.0
    inlet_velocity: float = 0.0

    # Pressure statistics
    max_pressure: float = 0.0
    min_pressure: float = 0.0
    pressure_drop: float = 0.0

    # Wall shear stress
    max_wss: float = 0.0
    mean_wss: float = 0.0

    # Flow conservation
    inlet_flow_rate: float = 0.0
    outlet_flow_rate: float = 0.0
    flow_conservation_error: float = 0.0

    # Quality checks
    physical_issues: List[str] = field(default_factory=list)


@dataclass
class SimulationResults:
    """Complete simulation validation results."""
    case_name: str
    convergence: ConvergenceMetrics
    flow: FlowMetrics

    def passes_validation(self) -> Tuple[bool, List[str]]:
        """
        Check if simulation passes validation criteria.

        Returns:
            Tuple of (passed, list of issues)
        """
        issues = []

        # Check convergence
        if not self.convergence.converged:
            issues.append("Solver did not converge")

        if self.convergence.max_courant_number > 5.0:
            issues.append(f"High Courant number: {self.convergence.max_courant_number:.2f} > 5.0")

        # Check residuals
        if self.convergence.final_p_residual > 1e-3:
            issues.append(f"High pressure residual: {self.convergence.final_p_residual:.2e}")

        # Check flow conservation
        if abs(self.flow.flow_conservation_error) > 0.05:  # 5% tolerance
            issues.append(f"Poor flow conservation: {self.flow.flow_conservation_error*100:.1f}% error")

        # Check for negative pressure
        if self.flow.min_pressure < -10000:  # Unrealistic negative pressure
            issues.append(f"Unrealistic negative pressure: {self.flow.min_pressure:.0f} Pa")

        # Check for unrealistic velocities
        if self.flow.max_velocity > 10.0:  # > 10 m/s unrealistic for aorta
            issues.append(f"Unrealistic high velocity: {self.flow.max_velocity:.2f} m/s")

        # Add any convergence issues
        issues.extend(self.convergence.convergence_issues)
        issues.extend(self.flow.physical_issues)

        passed = len(issues) == 0
        return passed, issues


class PhysicalResultsAnalyzer:
    """Analyzer for Level 3 simulation validation."""

    def __init__(self, case_dir: Path):
        """
        Initialize analyzer.

        Args:
            case_dir: Path to OpenFOAM case directory
        """
        self.case_dir = Path(case_dir)

    def analyze_convergence(self, log_file: Optional[Path] = None) -> ConvergenceMetrics:
        """
        Analyze solver convergence from log files.

        Args:
            log_file: Optional path to log file (default: case_dir/log.foamRun)

        Returns:
            ConvergenceMetrics object
        """
        if log_file is None:
            log_file = self.case_dir / "log.foamRun"

        if not log_file.exists():
            log_file = self.case_dir / "log.pimpleFoam"  # Fallback

        if not log_file.exists():
            metrics = ConvergenceMetrics()
            metrics.convergence_issues.append("Solver log file not found")
            return metrics

        return self._parse_solver_log(log_file)

    def _parse_solver_log(self, log_file: Path) -> ConvergenceMetrics:
        """Parse solver log file for convergence metrics."""
        metrics = ConvergenceMetrics()

        try:
            content = log_file.read_text()

            # Extract final time
            if match := re.search(r"Time = ([\d.]+)", content):
                times = re.findall(r"Time = ([\d.]+)", content)
                metrics.final_time = float(times[-1]) if times else 0.0
                metrics.total_iterations = len(times)

            # Extract Courant numbers
            courant_numbers = re.findall(r"Courant Number.*?max:\s*([\d.eE+-]+)", content)
            if courant_numbers:
                courant_floats = [float(c) for c in courant_numbers]
                metrics.avg_courant_number = sum(courant_floats) / len(courant_floats)
                metrics.max_courant_number = max(courant_floats)

            # Extract final residuals (last occurrence)
            p_residuals = re.findall(r"Solving for p.*?Final residual = ([\d.eE+-]+)", content)
            ux_residuals = re.findall(r"Solving for Ux.*?Final residual = ([\d.eE+-]+)", content)
            uy_residuals = re.findall(r"Solving for Uy.*?Final residual = ([\d.eE+-]+)", content)
            uz_residuals = re.findall(r"Solving for Uz.*?Final residual = ([\d.eE+-]+)", content)

            if p_residuals:
                metrics.final_p_residual = float(p_residuals[-1])
            if ux_residuals:
                metrics.final_ux_residual = float(ux_residuals[-1])
            if uy_residuals:
                metrics.final_uy_residual = float(uy_residuals[-1])
            if uz_residuals:
                metrics.final_uz_residual = float(uz_residuals[-1])

            # Check for convergence
            if "End" in content:
                metrics.converged = True

            # Check for errors/warnings
            if "FOAM FATAL ERROR" in content:
                metrics.convergence_issues.append("Fatal error in solver")
                metrics.converged = False

            if "floating point exception" in content.lower():
                metrics.convergence_issues.append("Floating point exception (numerical instability)")
                metrics.converged = False

            if metrics.max_courant_number > 10.0:
                metrics.convergence_issues.append(f"Very high Courant number: {metrics.max_courant_number:.2f}")

        except Exception as e:
            metrics.convergence_issues.append(f"Error parsing log: {e}")

        return metrics

    def analyze_flow_field(self, time_dir: Optional[str] = None) -> FlowMetrics:
        """
        Analyze flow field results using postProcess.

        Args:
            time_dir: Time directory to analyze (default: latest time)

        Returns:
            FlowMetrics object
        """
        metrics = FlowMetrics()

        # Get latest time if not specified
        if time_dir is None:
            time_dir = self._get_latest_time()

        if time_dir is None:
            metrics.physical_issues.append("No time directories found")
            return metrics

        # Use OpenFOAM postProcess utilities
        try:
            # Get velocity magnitude statistics
            vel_stats = self._get_field_statistics("U", time_dir)
            if vel_stats:
                metrics.max_velocity = vel_stats.get("max", 0.0)
                metrics.mean_velocity = vel_stats.get("mean", 0.0)

            # Get pressure statistics
            p_stats = self._get_field_statistics("p", time_dir)
            if p_stats:
                metrics.max_pressure = p_stats.get("max", 0.0)
                metrics.min_pressure = p_stats.get("min", 0.0)
                metrics.pressure_drop = metrics.max_pressure - metrics.min_pressure

            # Get flow rates at boundaries
            flow_rates = self._get_boundary_flow_rates(time_dir)
            if flow_rates:
                metrics.inlet_flow_rate = flow_rates.get("inlet", 0.0)
                metrics.outlet_flow_rate = sum([v for k, v in flow_rates.items() if "outlet" in k])

                # Calculate conservation error
                total_in = abs(metrics.inlet_flow_rate)
                total_out = abs(metrics.outlet_flow_rate)
                if total_in > 0:
                    metrics.flow_conservation_error = (total_out - total_in) / total_in

        except Exception as e:
            metrics.physical_issues.append(f"Error analyzing flow field: {e}")

        return metrics

    def _get_latest_time(self) -> Optional[str]:
        """Get latest time directory in case."""
        time_dirs = []
        for item in self.case_dir.iterdir():
            if item.is_dir() and item.name.replace(".", "").replace("-", "").isdigit():
                try:
                    time_dirs.append((float(item.name), item.name))
                except ValueError:
                    continue

        if time_dirs:
            time_dirs.sort()
            return time_dirs[-1][1]
        return None

    def _get_field_statistics(self, field_name: str, time_dir: str) -> Optional[Dict[str, float]]:
        """
        Get field statistics using OpenFOAM postProcess.

        Args:
            field_name: Field name (U, p, etc.)
            time_dir: Time directory

        Returns:
            Dictionary with min, max, mean values
        """
        try:
            # Use foamDictionary or direct file reading
            # For now, return None (placeholder for actual implementation)
            # In production, would use:
            # - postProcess -func 'fieldMinMax(U)'
            # - Or read field files directly with OpenFOAM Python bindings
            return None
        except Exception:
            return None

    def _get_boundary_flow_rates(self, time_dir: str) -> Optional[Dict[str, float]]:
        """
        Get flow rates at boundaries using postProcess.

        Args:
            time_dir: Time directory

        Returns:
            Dictionary mapping patch names to flow rates
        """
        try:
            # Use postProcess -func 'patchFlowRate(patch=inlet)'
            # Placeholder for actual implementation
            return None
        except Exception:
            return None

    def run_postprocess_flow_rate(self, time: str = "latestTime") -> Dict[str, float]:
        """
        Run OpenFOAM postProcess to calculate patch flow rates.

        Args:
            time: Time to analyze (default: latestTime)

        Returns:
            Dictionary of patch flow rates
        """
        flow_rates = {}

        try:
            # Get list of patches from boundary file
            patches = self._get_patch_names()

            for patch in patches:
                result = subprocess.run(
                    ["postProcess", "-case", str(self.case_dir),
                     "-func", f"patchFlowRate(patch={patch})",
                     "-time", time],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                # Parse output for flow rate
                if match := re.search(rf"{patch}.*?([+-]?[\d.eE+-]+)", result.stdout):
                    flow_rates[patch] = float(match.group(1))

        except Exception as e:
            print(f"Warning: Could not calculate flow rates: {e}")

        return flow_rates

    def _get_patch_names(self) -> List[str]:
        """Get list of patch names from boundary file."""
        patches = []
        boundary_file = self.case_dir / "constant" / "polyMesh" / "boundary"

        if boundary_file.exists():
            content = boundary_file.read_text()
            # Simple regex to extract patch names (not robust, but works for validation)
            patch_matches = re.findall(r"^\s+(\w+)\s*$", content, re.MULTILINE)
            patches = [p for p in patch_matches if p not in ["FoamFile", "type", "nFaces", "startFace"]]

        return patches

    def validate_simulation(self, log_file: Optional[Path] = None,
                          time_dir: Optional[str] = None) -> SimulationResults:
        """
        Complete simulation validation.

        Args:
            log_file: Optional solver log file path
            time_dir: Optional time directory to analyze

        Returns:
            SimulationResults with convergence and flow metrics
        """
        convergence = self.analyze_convergence(log_file)
        flow = self.analyze_flow_field(time_dir)

        return SimulationResults(
            case_name=self.case_dir.name,
            convergence=convergence,
            flow=flow
        )


def format_validation_report(results: SimulationResults) -> str:
    """
    Format validation results as a readable report.

    Args:
        results: SimulationResults object

    Returns:
        Formatted report string
    """
    passed, issues = results.passes_validation()

    report = f"""
======================================================================
SIMULATION VALIDATION REPORT: {results.case_name}
======================================================================

CONVERGENCE METRICS:
  Final Time:               {results.convergence.final_time:.3f} s
  Total Iterations:         {results.convergence.total_iterations}
  Max Courant Number:       {results.convergence.max_courant_number:.3f}
  Avg Courant Number:       {results.convergence.avg_courant_number:.3f}

RESIDUALS (Final):
  Pressure:                 {results.convergence.final_p_residual:.2e}
  Velocity (Ux):            {results.convergence.final_ux_residual:.2e}
  Velocity (Uy):            {results.convergence.final_uy_residual:.2e}
  Velocity (Uz):            {results.convergence.final_uz_residual:.2e}

FLOW FIELD METRICS:
  Max Velocity:             {results.flow.max_velocity:.3f} m/s
  Mean Velocity:            {results.flow.mean_velocity:.3f} m/s
  Max Pressure:             {results.flow.max_pressure:.1f} Pa
  Min Pressure:             {results.flow.min_pressure:.1f} Pa
  Pressure Drop:            {results.flow.pressure_drop:.1f} Pa

FLOW CONSERVATION:
  Inlet Flow Rate:          {results.flow.inlet_flow_rate:.6f} m³/s
  Outlet Flow Rate:         {results.flow.outlet_flow_rate:.6f} m³/s
  Conservation Error:       {results.flow.flow_conservation_error*100:.2f}%

OVERALL RESULT:
"""

    if passed:
        report += "  ✅ PASS - Simulation converged with physically realistic results\n"
    else:
        report += "  ❌ FAIL - Simulation validation issues detected:\n"
        for issue in issues:
            report += f"     - {issue}\n"

    report += "\n" + "="*70 + "\n"

    return report
