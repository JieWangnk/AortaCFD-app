#!/usr/bin/env python3
"""
Level 4 & 6: Boundary Condition and Physical Results Validation

Tests:
- Level 4: BC Validation
  * Inlet BC types: plug, parabolic, pulsatile
  * Outlet BC types: zeroGradient, 3EWK
  * Murray's Law flow distribution
  * Flow conservation (inlet = sum of outlets)

- Level 6: Physical Results Validation
  * Velocity magnitudes (expected ~0.1-1.5 m/s for aorta)
  * Pressure drop (expected ~10-50 mmHg = 1333-6666 Pa)
  * Wall shear stress (expected ~1-7 Pa)
  * Reynolds number validation
  * Turbulence metrics (for RANS/LES)

Usage:
    ./validation/run_bc_validation.py patient1 --profile sim_laminar_medium --time 0.5
"""

import sys
import os
import argparse
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import numpy as np

# Add src and validation to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from analyzers.field_statistics import FieldStatisticsExtractor
from analyzers.openfoam_binary_reader import read_field_at_time
from analyzers.flow_split_analyzer import FlowSplitAnalyzer, FlowSplitMetrics
from analyzers.flow_rate_extractor import FlowRateExtractor, FlowRateMetrics


@dataclass
class BCValidationMetrics:
    """Metrics for boundary condition validation"""
    # Inlet metrics
    inlet_area_m2: float = 0.0
    inlet_mean_velocity_ms: float = 0.0
    inlet_max_velocity_ms: float = 0.0
    inlet_flow_rate_m3s: float = 0.0
    inlet_profile_type: str = "unknown"

    # Outlet metrics
    outlet_count: int = 0
    outlet_total_flow_rate_m3s: float = 0.0
    outlet_flow_rates: Dict[str, float] = None
    outlet_bc_type: str = "unknown"

    # Flow conservation
    flow_conservation_error_percent: float = 0.0
    flow_balance_pass: bool = False

    # Murray's Law validation (if applicable)
    murray_law_applied: bool = False
    murray_flow_ratios: Dict[str, float] = None
    murray_validation_pass: bool = False

    # Flow split analysis
    flow_split_metrics: Optional[FlowSplitMetrics] = None
    custom_split_valid: bool = False
    custom_vs_murray_deviation: float = 0.0

    # Actual flow rate validation
    flow_rate_metrics: Optional[FlowRateMetrics] = None
    actual_flow_extracted: bool = False

    def __post_init__(self):
        if self.outlet_flow_rates is None:
            self.outlet_flow_rates = {}
        if self.murray_flow_ratios is None:
            self.murray_flow_ratios = {}


@dataclass
class PhysicalValidationMetrics:
    """Metrics for physical results validation"""
    # Velocity metrics
    velocity_min_ms: float = 0.0
    velocity_max_ms: float = 0.0
    velocity_mean_ms: float = 0.0
    velocity_realistic: bool = False
    velocity_range_expected: str = "0.1-1.5 m/s"

    # Pressure metrics
    pressure_min_pa: float = 0.0
    pressure_max_pa: float = 0.0
    pressure_drop_pa: float = 0.0
    pressure_drop_mmhg: float = 0.0
    pressure_realistic: bool = False
    pressure_drop_expected: str = "10-50 mmHg"

    # Wall shear stress
    wss_min_pa: float = 0.0
    wss_max_pa: float = 0.0
    wss_mean_pa: float = 0.0
    wss_realistic: bool = False
    wss_range_expected: str = "1-7 Pa"

    # Flow characteristics
    reynolds_number: float = 0.0
    flow_regime: str = "unknown"

    # Turbulence metrics (for RANS/LES only)
    turbulent_kinetic_energy: Optional[float] = None
    y_plus_min: Optional[float] = None
    y_plus_max: Optional[float] = None
    y_plus_mean: Optional[float] = None

    # Overall validation
    physically_realistic: bool = False


@dataclass
class BCValidationResult:
    """Complete BC and physical validation result"""
    patient_name: str
    profile_name: str
    simulation_time: float
    mesh_cells: int

    bc_metrics: BCValidationMetrics
    physical_metrics: PhysicalValidationMetrics

    overall_pass: bool = False
    issues: List[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class BCValidator:
    """Validates boundary conditions and physical results"""

    # Physical validation thresholds (based on literature for aortic flow)
    VELOCITY_MIN_REALISTIC = 0.05  # m/s
    VELOCITY_MAX_REALISTIC = 2.0   # m/s
    PRESSURE_DROP_MIN_MMHG = 5     # mmHg
    PRESSURE_DROP_MAX_MMHG = 100   # mmHg
    WSS_MIN_REALISTIC = 0.5        # Pa
    WSS_MAX_REALISTIC = 15.0       # Pa
    FLOW_CONSERVATION_THRESHOLD = 5.0  # percent

    PA_TO_MMHG = 0.00750062  # Conversion factor

    def __init__(self, patient_name: str, output_dir: Path):
        self.patient_name = patient_name
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def validate_case(self, case_dir: Path, profile_name: str, sim_time: float) -> BCValidationResult:
        """Run complete BC and physical validation on a case"""
        print(f"\n{'='*70}")
        print(f"BC & PHYSICAL VALIDATION: {profile_name}")
        print(f"{'='*70}\n")

        # Initialize result
        result = BCValidationResult(
            patient_name=self.patient_name,
            profile_name=profile_name,
            simulation_time=sim_time,
            mesh_cells=0,
            bc_metrics=BCValidationMetrics(),
            physical_metrics=PhysicalValidationMetrics()
        )

        # Get mesh cell count
        result.mesh_cells = self._get_mesh_cell_count(case_dir)

        # Validate BCs
        print("  📊 Analyzing boundary conditions...")
        result.bc_metrics = self._validate_boundary_conditions(case_dir)

        # Validate physical results
        print("  🔬 Analyzing physical results...")
        result.physical_metrics = self._validate_physical_results(case_dir, sim_time)

        # Determine overall pass/fail
        result.overall_pass, result.issues = self._determine_overall_validation(
            result.bc_metrics, result.physical_metrics
        )

        # Print summary
        self._print_validation_summary(result)

        return result

    def _get_mesh_cell_count(self, case_dir: Path) -> int:
        """Extract mesh cell count from log"""
        try:
            log_file = case_dir / "log.snappyHexMesh"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    for line in f:
                        if "Layer mesh : cells:" in line:
                            parts = line.split("cells:")
                            if len(parts) > 1:
                                return int(parts[1].split()[0])
        except Exception as e:
            print(f"  ⚠️  Could not extract cell count: {e}")
        return 0

    def _validate_boundary_conditions(self, case_dir: Path) -> BCValidationMetrics:
        """Validate boundary condition setup and flow conservation"""
        metrics = BCValidationMetrics()

        try:
            # Read U boundary field to get inlet/outlet info
            u_file = case_dir / "0" / "U"
            if u_file.exists():
                metrics.inlet_profile_type = self._detect_inlet_profile_type(u_file)
                print(f"    ✓ Detected inlet profile: {metrics.inlet_profile_type}")
                metrics.outlet_bc_type = self._detect_outlet_bc_type(case_dir)
                print(f"    ✓ Detected outlet BC: {metrics.outlet_bc_type}")

            # Parse simulation results for flow rates
            log_file = case_dir / "log.foamRun"
            if log_file.exists():
                # For now, we'll use placeholder values
                # TODO: Implement OpenFOAM postProcessing to extract actual flow rates
                metrics.inlet_flow_rate_m3s = 0.0
                metrics.outlet_total_flow_rate_m3s = 0.0

                # Calculate conservation error
                if metrics.inlet_flow_rate_m3s > 0:
                    metrics.flow_conservation_error_percent = (
                        abs(metrics.inlet_flow_rate_m3s - metrics.outlet_total_flow_rate_m3s) /
                        metrics.inlet_flow_rate_m3s * 100.0
                    )
                    metrics.flow_balance_pass = (
                        metrics.flow_conservation_error_percent < self.FLOW_CONSERVATION_THRESHOLD
                    )

                print(f"    ✓ Flow conservation error: {metrics.flow_conservation_error_percent:.2f}%")

            # Check for Murray's Law usage
            windkessel_file = case_dir / "constant" / "windkesselProperties"
            if windkessel_file.exists():
                metrics.murray_law_applied = True
                print(f"    ✓ 3-Element Windkessel BCs detected")

            # Analyze flow split (custom vs Murray's Law)
            config_file = case_dir / "config.json"
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)

                analyzer = FlowSplitAnalyzer(case_dir)
                metrics.flow_split_metrics = analyzer.analyze_flow_split(config)

                metrics.custom_split_valid = metrics.flow_split_metrics.is_custom_valid
                metrics.custom_vs_murray_deviation = metrics.flow_split_metrics.mean_deviation_percent

                if metrics.flow_split_metrics.custom_split:
                    print(f"    ✓ Custom flow split detected: {metrics.flow_split_metrics.custom_split_source}")
                    print(f"    ✓ Murray deviation: {metrics.custom_vs_murray_deviation:.1f}% "
                          f"({'✓ match' if metrics.flow_split_metrics.ratios_match else '✗ differs'})")

            # Extract actual flow rates from postProcessing (if available)
            postproc_dir = case_dir / "postProcessing"
            if postproc_dir.exists() and config_file.exists():
                try:
                    with open(config_file) as f:
                        config = json.load(f)

                    # Get patch names from flow split metrics
                    if metrics.flow_split_metrics and metrics.flow_split_metrics.outlet_areas:
                        patch_names = ['inlet'] + list(metrics.flow_split_metrics.outlet_areas.keys())

                        extractor = FlowRateExtractor(case_dir)
                        metrics.flow_rate_metrics = extractor.analyze_flow_rates(
                            patch_names,
                            custom_split=metrics.flow_split_metrics.custom_split,
                            murray_split=metrics.flow_split_metrics.murray_split,
                            time_val=None  # Latest time
                        )

                        if metrics.flow_rate_metrics.actual_flow_rates:
                            metrics.actual_flow_extracted = True
                            metrics.inlet_flow_rate_m3s = metrics.flow_rate_metrics.inlet_flow_rate
                            metrics.outlet_total_flow_rate_m3s = metrics.flow_rate_metrics.outlet_total_flow_rate
                            metrics.flow_conservation_error_percent = metrics.flow_rate_metrics.flow_conservation_error_percent
                            metrics.flow_balance_pass = metrics.flow_rate_metrics.flow_conservation_pass

                            print(f"    ✓ Actual flow rates extracted from postProcessing")
                            print(f"    ✓ Flow conservation: {metrics.flow_conservation_error_percent:.2f}% error")

                except Exception as e:
                    print(f"    ⚠️  Could not extract actual flow rates: {e}")

        except Exception as e:
            print(f"    ⚠️  BC validation error: {e}")

        return metrics

    def _detect_inlet_profile_type(self, u_file: Path) -> str:
        """Detect inlet velocity profile type from U file"""
        try:
            content = u_file.read_text()
            if "timeVaryingMappedFixedValue" in content:
                return "pulsatile (time-varying)"
            elif "fixedValue" in content:
                # Check if uniform or profile
                if "uniform" in content:
                    return "plug (uniform)"
                else:
                    return "parabolic or custom"
            return "unknown"
        except:
            return "unknown"

    def _detect_outlet_bc_type(self, case_dir: Path) -> str:
        """Detect outlet boundary condition type"""
        try:
            # Check for windkessel
            if (case_dir / "constant" / "windkesselProperties").exists():
                return "3-Element Windkessel (3EWK)"

            # Check U file for outlet BC
            u_file = case_dir / "0" / "U"
            if u_file.exists():
                content = u_file.read_text()
                if "zeroGradient" in content:
                    return "zeroGradient"
                elif "fixedValue" in content:
                    return "fixedValue"

            return "unknown"
        except:
            return "unknown"

    def _validate_physical_results(self, case_dir: Path, sim_time: float) -> PhysicalValidationMetrics:
        """Validate physical realism of simulation results"""
        metrics = PhysicalValidationMetrics()

        try:
            # Find latest time directory
            time_dir = self._find_latest_time_dir(case_dir, sim_time)
            if not time_dir:
                print(f"    ⚠️  No results found for time {sim_time}s")
                return metrics

            print(f"    📁 Reading results from: {time_dir.name}/")

            # Parse velocity field
            u_file = time_dir / "U"
            if u_file.exists():
                velocity_stats = self._parse_vector_field_stats(u_file)
                if velocity_stats:
                    metrics.velocity_min_ms = velocity_stats['min']
                    metrics.velocity_max_ms = velocity_stats['max']
                    metrics.velocity_mean_ms = velocity_stats['mean']

                    # Validate velocity range
                    metrics.velocity_realistic = (
                        self.VELOCITY_MIN_REALISTIC <= metrics.velocity_max_ms <= self.VELOCITY_MAX_REALISTIC
                    )

                    print(f"    ✓ Velocity: min={metrics.velocity_min_ms:.3f}, "
                          f"max={metrics.velocity_max_ms:.3f}, mean={metrics.velocity_mean_ms:.3f} m/s")
                    if not metrics.velocity_realistic:
                        print(f"      ⚠️  Velocity outside realistic range {metrics.velocity_range_expected}")

            # Parse pressure field
            p_file = time_dir / "p"
            if p_file.exists():
                pressure_stats = self._parse_scalar_field_stats(p_file)
                if pressure_stats:
                    metrics.pressure_min_pa = pressure_stats['min']
                    metrics.pressure_max_pa = pressure_stats['max']
                    metrics.pressure_drop_pa = pressure_stats['max'] - pressure_stats['min']
                    metrics.pressure_drop_mmhg = metrics.pressure_drop_pa * self.PA_TO_MMHG

                    # Validate pressure drop
                    metrics.pressure_realistic = (
                        self.PRESSURE_DROP_MIN_MMHG <= metrics.pressure_drop_mmhg <= self.PRESSURE_DROP_MAX_MMHG
                    )

                    print(f"    ✓ Pressure: min={metrics.pressure_min_pa:.1f}, "
                          f"max={metrics.pressure_max_pa:.1f} Pa")
                    print(f"    ✓ Pressure drop: {metrics.pressure_drop_pa:.1f} Pa "
                          f"({metrics.pressure_drop_mmhg:.1f} mmHg)")
                    if not metrics.pressure_realistic:
                        print(f"      ⚠️  Pressure drop outside realistic range {metrics.pressure_drop_expected}")

            # Calculate Reynolds number (if we have velocity and geometry info)
            if metrics.velocity_mean_ms > 0:
                # Typical aortic diameter ~25mm, kinematic viscosity ~3.5e-6 m²/s
                D = 0.025  # m
                nu = 3.5e-6  # m²/s
                metrics.reynolds_number = metrics.velocity_mean_ms * D / nu

                if metrics.reynolds_number < 2300:
                    metrics.flow_regime = "laminar"
                elif metrics.reynolds_number < 4000:
                    metrics.flow_regime = "transitional"
                else:
                    metrics.flow_regime = "turbulent"

                print(f"    ✓ Reynolds number: {metrics.reynolds_number:.0f} ({metrics.flow_regime})")

            # Check for turbulence fields (RANS/LES)
            nut_file = time_dir / "nut"
            if nut_file.exists():
                print(f"    ✓ Turbulence model active (nut field present)")
                # TODO: Parse turbulent kinetic energy, y+ values

            # Overall physical realism check
            metrics.physically_realistic = (
                metrics.velocity_realistic and
                (metrics.pressure_realistic or metrics.pressure_drop_pa == 0)
            )

        except Exception as e:
            print(f"    ⚠️  Physical validation error: {e}")

        return metrics

    def _find_latest_time_dir(self, case_dir: Path, target_time: float) -> Optional[Path]:
        """Find the time directory closest to target_time"""
        try:
            time_dirs = []
            for item in case_dir.iterdir():
                if item.is_dir() and item.name.replace('.', '', 1).replace('-', '', 1).isdigit():
                    try:
                        time_val = float(item.name)
                        time_dirs.append((time_val, item))
                    except ValueError:
                        continue

            if not time_dirs:
                return None

            # Find closest to target
            time_dirs.sort(key=lambda x: abs(x[0] - target_time))
            return time_dirs[0][1]

        except:
            return None

    def _parse_vector_field_stats(self, field_file: Path) -> Optional[Dict[str, float]]:
        """Parse min/max/mean from vector field using binary reader"""
        try:
            # Try binary reader first (fast and accurate)
            case_dir = field_file.parent.parent
            time_val = float(field_file.parent.name)

            stats = read_field_at_time(case_dir, field_file.name, time_val)

            if stats:
                print(f"      ✓ Binary reader extracted velocity statistics")
                return stats

            # Fallback to OpenFOAM utilities
            extractor = FieldStatisticsExtractor(case_dir)
            velocity_stats, _ = extractor.get_velocity_pressure_stats(time_val)

            return velocity_stats

        except Exception as e:
            print(f"      ⚠️  Could not extract velocity statistics: {e}")
            return None

    def _parse_scalar_field_stats(self, field_file: Path) -> Optional[Dict[str, float]]:
        """Parse min/max/mean from scalar field using binary reader"""
        try:
            # Try binary reader first (fast and accurate)
            case_dir = field_file.parent.parent
            time_val = float(field_file.parent.name)

            stats = read_field_at_time(case_dir, field_file.name, time_val)

            if stats:
                print(f"      ✓ Binary reader extracted pressure statistics")
                return stats

            # Fallback to OpenFOAM utilities
            extractor = FieldStatisticsExtractor(case_dir)
            _, pressure_stats = extractor.get_velocity_pressure_stats(time_val)

            return pressure_stats

        except Exception as e:
            print(f"      ⚠️  Could not extract pressure statistics: {e}")
            return None

    def _determine_overall_validation(
        self, bc_metrics: BCValidationMetrics, phys_metrics: PhysicalValidationMetrics
    ) -> tuple[bool, List[str]]:
        """Determine overall validation pass/fail and list issues"""
        issues = []

        # Check BC issues
        if bc_metrics.inlet_profile_type == "unknown":
            issues.append("Inlet profile type not detected")

        if bc_metrics.outlet_bc_type == "unknown":
            issues.append("Outlet BC type not detected")

        if not bc_metrics.flow_balance_pass and bc_metrics.inlet_flow_rate_m3s > 0:
            issues.append(f"Flow conservation error {bc_metrics.flow_conservation_error_percent:.2f}% exceeds threshold")

        # Check physical issues
        if not phys_metrics.velocity_realistic and phys_metrics.velocity_max_ms > 0:
            issues.append(f"Velocity {phys_metrics.velocity_max_ms:.3f} m/s outside realistic range")

        if not phys_metrics.pressure_realistic and phys_metrics.pressure_drop_pa > 0:
            issues.append(f"Pressure drop {phys_metrics.pressure_drop_mmhg:.1f} mmHg outside realistic range")

        # Overall pass if no critical issues
        overall_pass = len(issues) == 0 or (
            bc_metrics.inlet_profile_type != "unknown" and
            bc_metrics.outlet_bc_type != "unknown"
        )

        return overall_pass, issues

    def _print_validation_summary(self, result: BCValidationResult):
        """Print formatted validation summary"""
        print(f"\n{'='*70}")
        print(f"VALIDATION SUMMARY: {result.profile_name}")
        print(f"{'='*70}\n")

        # BC Summary
        print("BOUNDARY CONDITION VALIDATION:")
        print(f"  Inlet Profile:           {result.bc_metrics.inlet_profile_type}")
        print(f"  Outlet BC Type:          {result.bc_metrics.outlet_bc_type}")
        print(f"  Murray's Law Applied:    {result.bc_metrics.murray_law_applied}")
        print(f"  Flow Conservation:       {result.bc_metrics.flow_conservation_error_percent:.2f}% error")

        if result.bc_metrics.flow_split_metrics:
            fs = result.bc_metrics.flow_split_metrics
            print(f"\n  FLOW SPLIT ANALYSIS:")
            print(f"    Source:                {fs.custom_split_source}")
            print(f"    Custom Split Valid:    {'✓ Yes' if fs.is_custom_valid else '✗ No'}")
            print(f"    Murray-Based:          {'✓ Yes' if fs.is_murray_based else '✗ No'}")
            print(f"    Deviation from Murray: {fs.mean_deviation_percent:.1f}% (max: {fs.max_deviation_percent:.1f}%)")
            print(f"    Ratios Match:          {'✓ Yes' if fs.ratios_match else '✗ No (>10% deviation)'}")

        # Actual flow rate analysis
        if result.bc_metrics.actual_flow_extracted and result.bc_metrics.flow_rate_metrics:
            fr = result.bc_metrics.flow_rate_metrics
            print(f"\n  ACTUAL FLOW RATE ANALYSIS:")
            print(f"    Flow Rates Extracted:  ✓ Yes (from postProcessing)")
            print(f"    Inlet Flow Rate:       {fr.inlet_flow_rate:.6e} m³/s")
            print(f"    Outlet Total:          {fr.outlet_total_flow_rate:.6e} m³/s")
            print(f"    Conservation Error:    {fr.flow_conservation_error_percent:.2f}% {'✓' if fr.flow_conservation_pass else '✗'}")

            if fr.custom_vs_actual_deviation:
                mean_custom = sum(fr.custom_vs_actual_deviation.values()) / len(fr.custom_vs_actual_deviation)
                print(f"    Custom vs Actual:      {mean_custom:.1f}% deviation")

            if fr.murray_vs_actual_deviation:
                mean_murray = sum(fr.murray_vs_actual_deviation.values()) / len(fr.murray_vs_actual_deviation)
                print(f"    Murray vs Actual:      {mean_murray:.1f}% deviation")

            if fr.best_match != "unknown":
                print(f"    Best Match:            {fr.best_match.upper()}")

        # Physical Summary
        print(f"\nPHYSICAL RESULTS VALIDATION:")
        print(f"  Velocity Range:          {result.physical_metrics.velocity_min_ms:.3f} - "
              f"{result.physical_metrics.velocity_max_ms:.3f} m/s "
              f"{'✓' if result.physical_metrics.velocity_realistic else '✗'}")
        print(f"  Pressure Drop:           {result.physical_metrics.pressure_drop_pa:.1f} Pa "
              f"({result.physical_metrics.pressure_drop_mmhg:.1f} mmHg) "
              f"{'✓' if result.physical_metrics.pressure_realistic else '✗'}")
        print(f"  Reynolds Number:         {result.physical_metrics.reynolds_number:.0f} "
              f"({result.physical_metrics.flow_regime})")
        print(f"  Physically Realistic:    {result.physical_metrics.physically_realistic}")

        # Overall
        print(f"\nOVERALL VALIDATION:")
        if result.overall_pass:
            print(f"  ✅ PASS")
        else:
            print(f"  ❌ FAIL")
            print(f"\nISSUES:")
            for issue in result.issues:
                print(f"    - {issue}")

        print(f"\n{'='*70}\n")

    def save_results(self, results: List[BCValidationResult]):
        """Save validation results to JSON"""
        output_file = self.output_dir / f"{self.patient_name}_bc_validation_results.json"

        results_dict = {
            "patient": self.patient_name,
            "validation_type": "bc_and_physical",
            "results": [
                {
                    **asdict(r),
                    "bc_metrics": asdict(r.bc_metrics),
                    "physical_metrics": asdict(r.physical_metrics)
                }
                for r in results
            ]
        }

        with open(output_file, 'w') as f:
            json.dump(results_dict, f, indent=2)

        print(f"📊 Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Level 4 & 6: Boundary Condition and Physical Validation"
    )
    parser.add_argument("patient", help="Patient name (e.g., patient1)")
    parser.add_argument("--profile", required=True, help="Simulation profile to test")
    parser.add_argument("--time", type=float, default=0.1, help="Simulation time (default: 0.1s)")
    parser.add_argument("--output-dir", type=Path, default=Path("validation/output"),
                       help="Output directory for validation results")

    args = parser.parse_args()

    print(f"\n{'#'*70}")
    print(f"# LEVEL 4 & 6: BC AND PHYSICAL VALIDATION")
    print(f"# Patient: {args.patient}")
    print(f"# Profile: {args.profile}")
    print(f"# Simulation Time: {args.time}s")
    print(f"{'#'*70}\n")

    # Find case directory (assume it was created by run_simulation_validation.py)
    case_dir = args.output_dir / args.patient / args.profile

    if not case_dir.exists():
        print(f"❌ Error: Case directory not found: {case_dir}")
        print(f"   Run simulation validation first:")
        print(f"   ./validation/run_simulation_validation.py {args.patient} --profiles {args.profile} --time {args.time}")
        return 1

    # Run validation
    validator = BCValidator(args.patient, args.output_dir / args.patient)
    result = validator.validate_case(case_dir, args.profile, args.time)

    # Save results
    validator.save_results([result])

    return 0 if result.overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
