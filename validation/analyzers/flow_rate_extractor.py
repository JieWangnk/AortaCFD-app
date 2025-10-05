#!/usr/bin/env python3
"""
Flow Rate Extractor - Extract Actual Flow Rates from OpenFOAM Simulations

This module:
1. Generates surfaceFieldValue function objects for controlDict
2. Runs OpenFOAM postProcessing to extract patch flow rates
3. Parses postProcessing output to get actual flow distributions
4. Compares actual vs custom vs Murray's Law flow ratios
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import subprocess


@dataclass
class FlowRateMetrics:
    """Metrics for actual flow rate validation"""
    # Actual flow rates from simulation
    actual_flow_rates: Dict[str, float] = None  # m³/s
    actual_flow_ratios: Dict[str, float] = None  # normalized (sum=1.0)

    # Inlet/outlet tracking
    inlet_flow_rate: float = 0.0  # m³/s
    outlet_total_flow_rate: float = 0.0  # m³/s

    # Conservation
    flow_conservation_error_percent: float = 0.0
    flow_conservation_pass: bool = False

    # Comparison with expected values
    custom_vs_actual_deviation: Dict[str, float] = None  # percent
    murray_vs_actual_deviation: Dict[str, float] = None  # percent

    # Best match
    best_match: str = "unknown"  # "custom", "murray", "actual"

    def __post_init__(self):
        if self.actual_flow_rates is None:
            self.actual_flow_rates = {}
        if self.actual_flow_ratios is None:
            self.actual_flow_ratios = {}
        if self.custom_vs_actual_deviation is None:
            self.custom_vs_actual_deviation = {}
        if self.murray_vs_actual_deviation is None:
            self.murray_vs_actual_deviation = {}


class FlowRateExtractor:
    """Extract and validate actual flow rates from OpenFOAM simulations"""

    CONSERVATION_THRESHOLD = 5.0  # percent

    def __init__(self, case_dir: Path):
        self.case_dir = Path(case_dir)

    def generate_surface_field_value_functions(
        self,
        patch_names: List[str],
        controlDict_path: Optional[Path] = None
    ) -> str:
        """
        Generate surfaceFieldValue function objects for OpenFOAM

        Args:
            patch_names: List of patch names to monitor (inlet, outlet1, outlet2, ...)
            controlDict_path: Path to controlDict (optional, for appending)

        Returns:
            Function object dictionary as string
        """
        functions = []

        for patch in patch_names:
            func = f"""
    {patch}_flowRate
    {{
        type            surfaceFieldValue;
        libs            (fieldFunctionObjects);

        writeControl    timeStep;
        writeInterval   1;

        log             yes;
        writeFields     no;

        regionType      patch;
        name            {patch};

        operation       sum;
        fields          (phi);
    }}"""
            functions.append(func)

        # Complete functions block
        functions_block = "functions\n{" + "".join(functions) + "\n}\n"

        return functions_block

    def add_functions_to_controlDict(
        self,
        patch_names: List[str]
    ) -> bool:
        """
        Add surfaceFieldValue functions to controlDict

        Args:
            patch_names: List of patch names to monitor

        Returns:
            True if successful, False otherwise
        """
        controlDict = self.case_dir / "system" / "controlDict"

        if not controlDict.exists():
            print(f"❌ Error: controlDict not found at {controlDict}")
            return False

        # Read existing controlDict
        with open(controlDict, 'r') as f:
            content = f.read()

        # Check if functions already exist
        if "surfaceFieldValue" in content:
            print("⚠️  surfaceFieldValue functions already exist in controlDict")
            return True

        # Generate functions block
        functions_block = self.generate_surface_field_value_functions(patch_names)

        # Append to controlDict (before closing brace)
        if content.rstrip().endswith('}'):
            # Insert before final brace
            content = content.rstrip()[:-1] + "\n" + functions_block + "\n}\n"
        else:
            content += "\n" + functions_block

        # Write updated controlDict
        with open(controlDict, 'w') as f:
            f.write(content)

        print(f"✓ Added surfaceFieldValue functions to {controlDict}")
        return True

    def run_postProcessing(
        self,
        patch_names: List[str],
        latest_time: Optional[float] = None
    ) -> bool:
        """
        Run OpenFOAM postProcessing to extract flow rates

        Args:
            patch_names: List of patch names
            latest_time: Time to process (None = latest)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Add functions to controlDict
            if not self.add_functions_to_controlDict(patch_names):
                return False

            # Run postProcess
            cmd = ["foamRun", "-postProcess"]

            if latest_time is not None:
                cmd.extend(["-time", str(latest_time)])
            else:
                cmd.append("-latestTime")

            print(f"Running: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=self.case_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                print(f"❌ postProcess failed: {result.stderr}")
                return False

            print("✓ postProcess completed successfully")
            return True

        except subprocess.TimeoutExpired:
            print("❌ postProcess timed out")
            return False
        except Exception as e:
            print(f"❌ postProcess error: {e}")
            return False

    def extract_flow_rates_from_postProcessing(
        self,
        patch_names: List[str],
        time_val: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Extract flow rates from postProcessing output

        Args:
            patch_names: List of patch names
            time_val: Time directory to read (None = latest)

        Returns:
            Dict mapping patch names to flow rates (m³/s)
        """
        flow_rates = {}

        postproc_dir = self.case_dir / "postProcessing"

        if not postproc_dir.exists():
            print(f"⚠️  No postProcessing directory found: {postproc_dir}")
            return flow_rates

        for patch in patch_names:
            func_dir = postproc_dir / f"{patch}_flowRate"

            if not func_dir.exists():
                continue

            # Find time directory
            if time_val is not None:
                data_file = func_dir / str(time_val) / "surfaceFieldValue.dat"
            else:
                # Find latest time
                time_dirs = sorted([d for d in func_dir.iterdir() if d.is_dir()],
                                 key=lambda x: float(x.name))
                if not time_dirs:
                    continue
                data_file = time_dirs[-1] / "surfaceFieldValue.dat"

            if data_file.exists():
                flow_rate = self._parse_surface_field_value(data_file)
                if flow_rate is not None:
                    flow_rates[patch] = flow_rate
                    print(f"  {patch}: {flow_rate:.6e} m³/s")

        return flow_rates

    def _parse_surface_field_value(self, data_file: Path) -> Optional[float]:
        """Parse surfaceFieldValue.dat file"""
        try:
            with open(data_file, 'r') as f:
                lines = f.readlines()

            # Skip header lines (starting with #)
            data_lines = [line for line in lines if not line.strip().startswith('#')]

            if not data_lines:
                return None

            # Last line contains: time value
            last_line = data_lines[-1].strip().split()

            if len(last_line) >= 2:
                return float(last_line[1])

            return None

        except Exception as e:
            print(f"⚠️  Could not parse {data_file}: {e}")
            return None

    def calculate_flow_ratios(
        self,
        flow_rates: Dict[str, float],
        exclude_inlet: bool = True
    ) -> Dict[str, float]:
        """
        Calculate normalized flow ratios from flow rates

        Args:
            flow_rates: Dict mapping patch names to flow rates
            exclude_inlet: If True, calculate ratios among outlets only

        Returns:
            Dict mapping patch names to ratios (sum = 1.0)
        """
        if not flow_rates:
            return {}

        # Filter patches
        if exclude_inlet:
            outlet_rates = {k: v for k, v in flow_rates.items()
                           if 'inlet' not in k.lower() and 'in' != k.lower()}
        else:
            outlet_rates = flow_rates.copy()

        # Calculate total
        total = sum(abs(v) for v in outlet_rates.values())

        if total == 0:
            return {}

        # Normalize to ratios
        ratios = {k: abs(v) / total for k, v in outlet_rates.items()}

        return ratios

    def validate_flow_conservation(
        self,
        flow_rates: Dict[str, float]
    ) -> Tuple[float, float, float]:
        """
        Validate flow conservation (inlet = sum of outlets)

        Args:
            flow_rates: Dict mapping patch names to flow rates

        Returns:
            (inlet_rate, outlet_total, error_percent)
        """
        # Identify inlet and outlets
        inlet_rate = 0.0
        outlet_total = 0.0

        for patch, rate in flow_rates.items():
            if 'inlet' in patch.lower() or patch.lower() == 'in':
                inlet_rate += abs(rate)
            elif 'outlet' in patch.lower() or patch.lower().startswith('out'):
                outlet_total += abs(rate)

        # Calculate conservation error
        if inlet_rate > 0:
            error_percent = abs(inlet_rate - outlet_total) / inlet_rate * 100
        else:
            error_percent = 0.0

        return inlet_rate, outlet_total, error_percent

    def compare_ratios(
        self,
        actual_ratios: Dict[str, float],
        expected_ratios: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Compare actual vs expected flow ratios

        Returns:
            Dict mapping outlet names to deviation percentage
        """
        deviations = {}

        common_outlets = set(actual_ratios.keys()) & set(expected_ratios.keys())

        for outlet in common_outlets:
            actual = actual_ratios[outlet]
            expected = expected_ratios[outlet]

            if expected > 0:
                deviation = abs(actual - expected) / expected * 100
                deviations[outlet] = deviation

        return deviations

    def analyze_flow_rates(
        self,
        patch_names: List[str],
        custom_split: Optional[Dict[str, float]] = None,
        murray_split: Optional[Dict[str, float]] = None,
        time_val: Optional[float] = None
    ) -> FlowRateMetrics:
        """
        Complete flow rate analysis

        Args:
            patch_names: List of patch names to analyze
            custom_split: Custom flow split ratios (optional)
            murray_split: Murray's Law predicted ratios (optional)
            time_val: Time to analyze (None = latest)

        Returns:
            FlowRateMetrics with complete analysis
        """
        metrics = FlowRateMetrics()

        # Extract actual flow rates
        print("Extracting flow rates from postProcessing...")
        metrics.actual_flow_rates = self.extract_flow_rates_from_postProcessing(
            patch_names, time_val
        )

        if not metrics.actual_flow_rates:
            print("⚠️  No flow rates extracted")
            return metrics

        # Calculate actual ratios
        metrics.actual_flow_ratios = self.calculate_flow_ratios(
            metrics.actual_flow_rates,
            exclude_inlet=True
        )

        # Validate conservation
        metrics.inlet_flow_rate, metrics.outlet_total_flow_rate, metrics.flow_conservation_error_percent = \
            self.validate_flow_conservation(metrics.actual_flow_rates)

        metrics.flow_conservation_pass = (
            metrics.flow_conservation_error_percent < self.CONSERVATION_THRESHOLD
        )

        print(f"\n✓ Flow Conservation:")
        print(f"  Inlet:  {metrics.inlet_flow_rate:.6e} m³/s")
        print(f"  Outlet: {metrics.outlet_total_flow_rate:.6e} m³/s")
        print(f"  Error:  {metrics.flow_conservation_error_percent:.2f}% "
              f"{'✓' if metrics.flow_conservation_pass else '✗'}")

        # Compare with custom split
        if custom_split and metrics.actual_flow_ratios:
            metrics.custom_vs_actual_deviation = self.compare_ratios(
                metrics.actual_flow_ratios,
                custom_split
            )

            if metrics.custom_vs_actual_deviation:
                mean_custom = sum(metrics.custom_vs_actual_deviation.values()) / len(metrics.custom_vs_actual_deviation)
                print(f"\n✓ Custom vs Actual: {mean_custom:.1f}% mean deviation")

        # Compare with Murray's Law
        if murray_split and metrics.actual_flow_ratios:
            metrics.murray_vs_actual_deviation = self.compare_ratios(
                metrics.actual_flow_ratios,
                murray_split
            )

            if metrics.murray_vs_actual_deviation:
                mean_murray = sum(metrics.murray_vs_actual_deviation.values()) / len(metrics.murray_vs_actual_deviation)
                print(f"✓ Murray vs Actual: {mean_murray:.1f}% mean deviation")

        # Determine best match
        if metrics.custom_vs_actual_deviation and metrics.murray_vs_actual_deviation:
            custom_dev = sum(metrics.custom_vs_actual_deviation.values()) / len(metrics.custom_vs_actual_deviation)
            murray_dev = sum(metrics.murray_vs_actual_deviation.values()) / len(metrics.murray_vs_actual_deviation)

            if custom_dev < murray_dev:
                metrics.best_match = "custom"
            else:
                metrics.best_match = "murray"

        return metrics

    def print_flow_rate_report(
        self,
        metrics: FlowRateMetrics,
        custom_split: Optional[Dict[str, float]] = None,
        murray_split: Optional[Dict[str, float]] = None
    ):
        """Print comprehensive flow rate validation report"""
        print("\n" + "="*70)
        print("FLOW RATE VALIDATION REPORT")
        print("="*70)

        # Actual flow rates
        print("\nACTUAL FLOW RATES (from simulation):")
        if metrics.actual_flow_rates:
            for patch in sorted(metrics.actual_flow_rates.keys()):
                rate = metrics.actual_flow_rates[patch]
                print(f"  {patch:20s} → {rate:10.6e} m³/s")
        else:
            print("  ⚠️  No flow rates available")

        # Flow ratios comparison
        print("\nFLOW RATIO COMPARISON:")
        print(f"{'Outlet':<15} {'Actual':<12} {'Custom':<12} {'Murray':<12}")
        print("-" * 70)

        outlets = sorted(metrics.actual_flow_ratios.keys())
        for outlet in outlets:
            actual = metrics.actual_flow_ratios.get(outlet, 0)
            custom = custom_split.get(outlet, 0) if custom_split else 0
            murray = murray_split.get(outlet, 0) if murray_split else 0

            print(f"{outlet:<15} {actual:>10.1%}  {custom:>10.1%}  {murray:>10.1%}")

        # Deviation analysis
        if metrics.custom_vs_actual_deviation or metrics.murray_vs_actual_deviation:
            print("\nDEVIATION FROM ACTUAL:")
            print(f"{'Outlet':<15} {'Custom Dev':<15} {'Murray Dev':<15}")
            print("-" * 70)

            for outlet in outlets:
                custom_dev = metrics.custom_vs_actual_deviation.get(outlet, 0)
                murray_dev = metrics.murray_vs_actual_deviation.get(outlet, 0)

                print(f"{outlet:<15} {custom_dev:>13.1f}%  {murray_dev:>13.1f}%")

        # Conservation summary
        print(f"\nFLOW CONSERVATION:")
        print(f"  Inlet Flow Rate:     {metrics.inlet_flow_rate:.6e} m³/s")
        print(f"  Outlet Total:        {metrics.outlet_total_flow_rate:.6e} m³/s")
        print(f"  Conservation Error:  {metrics.flow_conservation_error_percent:.2f}%")
        print(f"  Status:              {'✅ PASS' if metrics.flow_conservation_pass else '❌ FAIL'}")

        # Best match
        if metrics.best_match != "unknown":
            print(f"\nBEST MATCH: {metrics.best_match.upper()}")

        print("\n" + "="*70 + "\n")


def main():
    """CLI for flow rate extraction and validation"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract and validate flow rates from OpenFOAM simulation"
    )
    parser.add_argument("case_dir", type=Path, help="OpenFOAM case directory")
    parser.add_argument("--patches", nargs='+', required=True,
                       help="Patch names to monitor (e.g., inlet outlet1 outlet2)")
    parser.add_argument("--time", type=float, help="Time to analyze (default: latest)")
    parser.add_argument("--custom-split", type=Path,
                       help="JSON file with custom flow split ratios")
    parser.add_argument("--murray-split", type=Path,
                       help="JSON file with Murray's Law ratios")
    parser.add_argument("--run-postprocess", action="store_true",
                       help="Run postProcessing before extraction")

    args = parser.parse_args()

    # Load custom split if provided
    custom_split = None
    if args.custom_split:
        with open(args.custom_split) as f:
            data = json.load(f)
            custom_split = data.get('flow_split', {})

    # Load Murray split if provided
    murray_split = None
    if args.murray_split:
        with open(args.murray_split) as f:
            murray_split = json.load(f)

    # Create extractor
    extractor = FlowRateExtractor(args.case_dir)

    # Run postProcessing if requested
    if args.run_postprocess:
        extractor.run_postProcessing(args.patches, args.time)

    # Analyze flow rates
    metrics = extractor.analyze_flow_rates(
        args.patches,
        custom_split,
        murray_split,
        args.time
    )

    # Print report
    extractor.print_flow_rate_report(metrics, custom_split, murray_split)

    return 0 if metrics.flow_conservation_pass else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
