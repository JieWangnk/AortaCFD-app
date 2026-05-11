"""
Inlet Boundary Condition Quality Control and Audit Module

Implements comprehensive QC checks, Womersley number calculation,
profile recommendations, and audit trail logging for inlet BC setup.

Based on clinical best practices for cardiovascular CFD simulations.
"""

import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, asdict
import json

from .utils.logger import Logger


@dataclass
class InletAudit:
    """Complete audit record for inlet BC configuration."""

    # Geometry
    inlet_area_m2: float
    inlet_radius_eq_m: float
    inlet_center: List[float]
    inlet_normal: List[float]

    # Waveform statistics
    csv_file: str
    data_type: str
    n_points: int
    detected_period_s: float

    # Configuration (required fields - must come before optional fields)
    inlet_type: str
    profile: str
    orientation: str

    # Optional fields with defaults
    mean_flow_m3s: Optional[float] = None
    mean_velocity_ms: Optional[float] = None
    peak_systolic: float = 0.0
    backflow_fraction: float = 0.0

    # Physics
    nu_m2s: Optional[float] = None
    womersley_alpha: Optional[float] = None
    womersley_recommendation: Optional[str] = None

    # Orientation detection
    auto_orientation_detected: bool = False
    dot_product_normal_flow: Optional[float] = None
    orientation_flipped: bool = False

    # Scaling applied
    scaling_applied: bool = False
    target_CO_Lmin: Optional[float] = None
    original_mean_flow_m3s: Optional[float] = None
    scale_factor: float = 1.0

    # Filtering/resampling
    filter_method: Optional[str] = None
    target_dt_s: Optional[float] = None
    n_output_timesteps: Optional[int] = None

    # Validation flags
    warnings: List[str] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def save_json(self, filepath: Path):
        """Save audit to JSON file."""

        def _default(obj):
            if isinstance(obj, np.generic):
                return obj.item()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=_default)

    def get_summary_report(self) -> str:
        """Generate human-readable summary report."""
        lines = [
            "=" * 80,
            "INLET BOUNDARY CONDITION AUDIT REPORT",
            "=" * 80,
            "",
            "GEOMETRY:",
            f"  Inlet area: {self.inlet_area_m2*1e6:.2f} mm²",
            f"  Equivalent radius: {self.inlet_radius_eq_m*1e3:.2f} mm",
            f"  Center: [{self.inlet_center[0]:.3f}, {self.inlet_center[1]:.3f}, {self.inlet_center[2]:.3f}]",
            f"  Normal: [{self.inlet_normal[0]:.3f}, {self.inlet_normal[1]:.3f}, {self.inlet_normal[2]:.3f}]",
            "",
            "CONFIGURATION:",
            f"  Type: {self.inlet_type}",
            f"  Profile: {self.profile}",
            f"  CSV file: {self.csv_file}",
            f"  Data type: {self.data_type}",
            "",
            "WAVEFORM STATISTICS:",
            f"  Number of points: {self.n_points}",
            f"  Detected period: {self.detected_period_s:.3f} s"
            + (f" ({60/self.detected_period_s:.1f} bpm)" if self.detected_period_s > 0 else " (N/A)"),
        ]

        if self.mean_flow_m3s is not None:
            lines.append(f"  Mean flow: {self.mean_flow_m3s*1e6:.2f} mL/s ({self.mean_flow_m3s*60*1e3:.2f} L/min)")
        if self.mean_velocity_ms is not None:
            lines.append(f"  Mean velocity: {self.mean_velocity_ms:.3f} m/s")

        lines.extend(
            [
                f"  Peak systolic: {self.peak_systolic:.3f} {self.data_type}",
                f"  Backflow fraction: {self.backflow_fraction*100:.1f}%",
                "",
            ]
        )

        if self.womersley_alpha is not None:
            lines.extend(
                [
                    "WOMERSLEY ANALYSIS:",
                    f"  Kinematic viscosity (ν): {self.nu_m2s:.2e} m²/s",
                    f"  Womersley number (α): {self.womersley_alpha:.2f}",
                    f"  Recommended profile: {self.womersley_recommendation}",
                    "",
                ]
            )

        if self.auto_orientation_detected:
            lines.extend(
                [
                    "ORIENTATION:",
                    "  Method: automatic detection",
                    f"  Dot product (n·d): {self.dot_product_normal_flow:.3f}",
                    f"  Normal flipped: {'Yes' if self.orientation_flipped else 'No'}",
                    "",
                ]
            )
        else:
            lines.append(f"ORIENTATION: manual ({self.orientation})\n")

        if self.scaling_applied:
            lines.extend(
                [
                    "SCALING:",
                    f"  Target CO: {self.target_CO_Lmin:.2f} L/min",
                    f"  Original mean flow: {self.original_mean_flow_m3s*60*1e3:.2f} L/min",
                    f"  Scale factor: {self.scale_factor:.4f}",
                    "",
                ]
            )

        if self.filter_method:
            lines.extend(
                [
                    "FILTERING/RESAMPLING:",
                    f"  Method: {self.filter_method}",
                    f"  Target Δt: {self.target_dt_s:.4f} s",
                    f"  Output timesteps: {self.n_output_timesteps}",
                    "",
                ]
            )

        if self.warnings:
            lines.extend(["WARNINGS:", *[f"  ⚠ {w}" for w in self.warnings], ""])

        if self.errors:
            lines.extend(["ERRORS:", *[f"  ✗ {e}" for e in self.errors], ""])

        lines.append("=" * 80)
        return "\n".join(lines)


class InletQC:
    """
    Inlet boundary condition quality control and validation.

    Performs:
    - Womersley number calculation
    - Profile recommendations based on flow physics
    - CSV validation and statistics
    - Area computation from mesh
    - Orientation detection validation
    - Scaling and filtering QC
    """

    def __init__(self, config: dict, case_directory: Path):
        """
        Initialize inlet QC.

        Args:
            config: Full configuration dictionary
            case_directory: Path to case directory
        """
        self.config = config
        self.case_dir = Path(case_directory)
        self.log = Logger("InletQC").get_logger()

        # Extract relevant config sections
        self.inlet_config = config.get("inlet", config.get("boundary_conditions", {}).get("inlet", {}))
        self.physics = config.get("physics", {})

        self.audit = None

    def calculate_womersley_number(self, radius_m: float, period_s: float, nu_m2s: float) -> float:
        """
        Calculate Womersley number (α).

        α = R * sqrt(ω / ν)
        where ω = 2π / T

        Args:
            radius_m: Inlet radius in meters
            period_s: Cardiac cycle period in seconds
            nu_m2s: Kinematic viscosity in m²/s

        Returns:
            Womersley number (dimensionless)
        """
        omega = 2 * np.pi / period_s
        alpha = radius_m * np.sqrt(omega / nu_m2s)
        return alpha

    def recommend_profile(self, alpha: float) -> str:
        """
        Recommend velocity profile based on Womersley number.

        Args:
            alpha: Womersley number

        Returns:
            Recommended profile: 'plug', 'parabolic', or 'womersley'
        """
        if alpha < 1.0:
            return "parabolic (quasi-steady)"
        elif alpha < 10.0:
            return "womersley (transitional)"
        else:
            return "plug (high-frequency, near-flat)"

    def compute_area_from_points(self, points_file: Path) -> Tuple[float, float, np.ndarray]:
        """
        Compute inlet area from boundary mesh points.

        Uses polygon triangulation for non-circular patches.

        Args:
            points_file: Path to OpenFOAM points file

        Returns:
            Tuple of (area_m2, radius_eq_m, centroid)
        """
        # Read points file
        with open(points_file, "r") as f:
            lines = [l.strip() for l in f if l.strip()]

        n_points = int(lines[0])

        # Parse points
        points = []
        start_idx = 2 if lines[1] == "(" else 1
        for i in range(n_points):
            line = lines[i + start_idx].replace("(", "").replace(")", "")
            coords = [float(x) for x in line.split()]
            points.append(coords)

        points = np.array(points)

        # Compute centroid
        centroid = np.mean(points, axis=0)

        # Compute area using shoelace formula (2D projection)
        # Project onto best-fit plane for non-planar patches
        centered = points - centroid

        # SVD to find principal directions
        U, S, Vt = np.linalg.svd(centered)

        # Project onto first two principal axes
        proj_2d = centered @ Vt.T[:, :2]

        # Shoelace formula
        x = proj_2d[:, 0]
        y = proj_2d[:, 1]
        area = 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

        # Equivalent radius
        radius_eq = np.sqrt(area / np.pi)

        return area, radius_eq, centroid

    def analyze_csv_waveform(self, csv_path: Path, data_type: str) -> Dict:
        """
        Analyze CSV waveform and extract statistics.

        Args:
            csv_path: Path to CSV file
            data_type: 'velocity' or 'flowrate'

        Returns:
            Dictionary with statistics
        """
        # Count comment/empty lines and detect header
        # skip_header in genfromtxt skips from beginning BEFORE comment processing
        comment_lines = 0
        header_line = 0

        with open(csv_path, "r") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    comment_lines += 1
                else:
                    # First non-comment line - check if it's a header
                    if any(c.isalpha() for c in stripped):
                        header_line = 1
                    break

        # Total lines to skip = comment lines + header (if present)
        skiprows = comment_lines + header_line

        data = np.genfromtxt(csv_path, delimiter=",", skip_header=skiprows)

        if data.ndim < 2 or data.shape[1] < 2:
            raise ValueError("CSV must have at least 2 columns")

        times = data[:, 0]
        values = data[:, 1]

        # Sort by time
        sort_idx = np.argsort(times)
        times = times[sort_idx]
        values = values[sort_idx]

        # Detect period (time range)
        period = times[-1] - times[0]

        # Statistics
        mean_val = np.mean(values)
        peak_val = np.max(values)

        # Backflow fraction (negative values)
        negative_mask = values < 0
        backflow_fraction = np.sum(negative_mask) / len(values) if len(values) > 0 else 0.0

        return {
            "n_points": len(times),
            "period_s": period,
            "mean_value": mean_val,
            "peak_value": peak_val,
            "backflow_fraction": backflow_fraction,
            "times": times,
            "values": values,
        }

    def compute_area_weighted_normal(self, points_file: Path, stl_file: Optional[Path] = None) -> np.ndarray:
        """
        Compute area-weighted surface normal from inlet patch.

        Args:
            points_file: Path to boundaryData points file
            stl_file: Optional path to STL for cross-validation

        Returns:
            Unit normal vector (area-weighted)
        """
        # Read points
        with open(points_file, "r") as f:
            lines = [l.strip() for l in f if l.strip()]

        n_points = int(lines[0])
        points = []
        start_idx = 2 if lines[1] == "(" else 1
        for i in range(n_points):
            line = lines[i + start_idx].replace("(", "").replace(")", "")
            coords = [float(x) for x in line.split()]
            points.append(coords)

        points = np.array(points)

        # Compute centroid
        centroid = np.mean(points, axis=0)

        # PCA to find normal direction
        centered = points - centroid
        U, S, Vt = np.linalg.svd(centered)

        # Normal is the third principal component (smallest variance)
        normal = Vt[2, :]

        # Normalize
        normal = normal / np.linalg.norm(normal)

        return normal

    def run_full_qc(
        self,
        inlet_patch_name: str,
        inlet_area: float,
        inlet_radius: float,
        inlet_center: np.ndarray,
        inlet_normal: np.ndarray,
    ) -> InletAudit:
        """
        Run complete QC analysis and generate audit trail.

        Args:
            inlet_patch_name: Name of inlet patch
            inlet_area: Computed inlet area (m²)
            inlet_radius: Equivalent radius (m)
            inlet_center: Inlet centroid coordinates
            inlet_normal: Inlet normal vector

        Returns:
            InletAudit object with complete analysis
        """
        self.log.info("Running inlet BC quality control...")

        audit = InletAudit(
            inlet_area_m2=inlet_area,
            inlet_radius_eq_m=inlet_radius,
            inlet_center=inlet_center.tolist() if isinstance(inlet_center, np.ndarray) else inlet_center,
            inlet_normal=inlet_normal.tolist() if isinstance(inlet_normal, np.ndarray) else inlet_normal,
            csv_file=self.inlet_config.get("csv_file", "N/A"),
            data_type=self.inlet_config.get("data_type", "N/A"),
            n_points=0,
            detected_period_s=0.0,
            inlet_type=self.inlet_config.get("type", "UNKNOWN"),
            profile=self.inlet_config.get("profile", "UNKNOWN"),
            orientation=self.inlet_config.get("orientation", "auto"),
        )

        # Analyze CSV if time-varying
        if audit.inlet_type in ["TIMEVARYING", "WOMERSLEY"]:
            csv_file = self.inlet_config.get("csv_file")
            if csv_file:
                csv_path = self.case_dir / "constant" / "boundaryData" / inlet_patch_name / csv_file
                if not csv_path.exists():
                    csv_path = Path(csv_file)  # Try as absolute path

                if csv_path.exists():
                    try:
                        stats = self.analyze_csv_waveform(csv_path, audit.data_type)
                        audit.n_points = stats["n_points"]
                        audit.detected_period_s = stats["period_s"]
                        audit.peak_systolic = stats["peak_value"]
                        audit.backflow_fraction = stats["backflow_fraction"]

                        if audit.data_type == "flowrate":
                            audit.mean_flow_m3s = stats["mean_value"]
                            audit.mean_velocity_ms = stats["mean_value"] / inlet_area
                        else:
                            audit.mean_velocity_ms = stats["mean_value"]
                            audit.mean_flow_m3s = stats["mean_value"] * inlet_area

                        self.log.info(
                            f"  CSV analysis: {audit.n_points} points, " f"period={audit.detected_period_s:.3f}s"
                        )
                    except Exception as e:
                        audit.errors.append(f"CSV analysis failed: {e}")
                        self.log.error(f"CSV analysis error: {e}")
                else:
                    audit.warnings.append(f"CSV file not found: {csv_path}")

        # Womersley analysis
        nu = self.physics.get("nu")
        if nu is None:
            transport = self.physics.get("transport_properties", {})
            nu = transport.get("nu")
        if nu and audit.detected_period_s > 0:
            try:
                audit.nu_m2s = nu
                audit.womersley_alpha = self.calculate_womersley_number(inlet_radius, audit.detected_period_s, nu)
                audit.womersley_recommendation = self.recommend_profile(audit.womersley_alpha)

                self.log.info(f"  Womersley number α = {audit.womersley_alpha:.2f}")
                self.log.info(f"  Recommended profile: {audit.womersley_recommendation}")

                # Check if configured profile matches recommendation
                if audit.profile not in audit.womersley_recommendation:
                    audit.warnings.append(
                        f"Profile '{audit.profile}' may not be optimal for α={audit.womersley_alpha:.2f}. "
                        f"Consider: {audit.womersley_recommendation}"
                    )
            except Exception as e:
                audit.warnings.append(f"Womersley calculation failed: {e}")

        # Check for cardiac output scaling
        scaling = self.inlet_config.get("scaling", {})
        if isinstance(scaling, dict) and scaling.get("target_CO"):
            target_CO_Lmin = scaling["target_CO"]
            if audit.mean_flow_m3s:
                audit.target_CO_Lmin = target_CO_Lmin
                audit.original_mean_flow_m3s = audit.mean_flow_m3s
                audit.scale_factor = (target_CO_Lmin / 60.0 / 1000.0) / audit.mean_flow_m3s
                audit.scaling_applied = True

                self.log.info(
                    f"  CO scaling: {audit.original_mean_flow_m3s*60*1e3:.2f} → "
                    f"{target_CO_Lmin:.2f} L/min (factor={audit.scale_factor:.4f})"
                )

        # Check filtering
        filter_cfg = self.inlet_config.get("filter", {})
        if isinstance(filter_cfg, dict) and filter_cfg.get("method"):
            audit.filter_method = filter_cfg["method"]
            audit.target_dt_s = filter_cfg.get("target_dt", 0.005)

        self.audit = audit

        # Print summary to log
        self.log.info("\n" + audit.get_summary_report())

        return audit
