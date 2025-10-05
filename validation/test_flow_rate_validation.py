#!/usr/bin/env python3
"""
Flow Rate Validation Test - Demonstrate Complete Flow Rate Analysis

This script demonstrates:
1. Running OpenFOAM postProcessing to extract flow rates
2. Comparing actual vs custom vs Murray's Law distributions
3. Validating flow conservation
4. Identifying best match
"""

import sys
import json
from pathlib import Path

# Add validation to path
sys.path.insert(0, str(Path(__file__).parent))

from analyzers.flow_rate_extractor import FlowRateExtractor
from analyzers.flow_split_analyzer import FlowSplitAnalyzer


def test_flow_rate_validation_complete(case_dir: Path):
    """
    Complete flow rate validation workflow

    Steps:
    1. Analyze flow split (custom vs Murray from geometry)
    2. Extract actual flow rates from simulation
    3. Compare all three: Actual vs Custom vs Murray
    4. Validate flow conservation
    5. Determine best match
    """
    print("\n" + "="*70)
    print("COMPLETE FLOW RATE VALIDATION TEST")
    print("="*70)

    # Load config
    config_file = case_dir / "config.json"
    if not config_file.exists():
        print(f"❌ Error: No config.json found in {case_dir}")
        return False

    with open(config_file) as f:
        config = json.load(f)

    # Step 1: Flow split analysis (custom vs Murray from geometry)
    print("\nSTEP 1: Flow Split Analysis (Custom vs Murray)")
    print("-" * 70)

    analyzer = FlowSplitAnalyzer(case_dir)
    flow_split_metrics = analyzer.analyze_flow_split(config)

    if not flow_split_metrics.outlet_areas:
        print("❌ Error: Could not extract outlet geometry")
        return False

    print(f"✓ Outlets found: {list(flow_split_metrics.outlet_areas.keys())}")
    print(f"✓ Custom split: {flow_split_metrics.custom_split}")
    print(f"✓ Murray split: {flow_split_metrics.murray_split}")
    print(f"✓ Deviation: {flow_split_metrics.mean_deviation_percent:.1f}% (max: {flow_split_metrics.max_deviation_percent:.1f}%)")

    # Step 2: Extract actual flow rates
    print("\nSTEP 2: Extract Actual Flow Rates from Simulation")
    print("-" * 70)

    patch_names = ['inlet'] + list(flow_split_metrics.outlet_areas.keys())

    extractor = FlowRateExtractor(case_dir)

    # Check if postProcessing exists
    postproc_dir = case_dir / "postProcessing"
    if not postproc_dir.exists():
        print("⚠️  No postProcessing directory found")
        print("   Run: foamRun -postProcess -latestTime")
        print("   Or use: --run-postprocess flag")
        return False

    flow_rate_metrics = extractor.analyze_flow_rates(
        patch_names,
        custom_split=flow_split_metrics.custom_split,
        murray_split=flow_split_metrics.murray_split,
        time_val=None  # Latest time
    )

    if not flow_rate_metrics.actual_flow_rates:
        print("❌ Error: Could not extract flow rates")
        return False

    # Step 3: Compare all three
    print("\nSTEP 3: Compare Actual vs Custom vs Murray")
    print("-" * 70)

    print(f"\n{'Outlet':<15} {'Actual':<12} {'Custom':<12} {'Murray':<12} {'Custom Dev':<12} {'Murray Dev':<12}")
    print("-" * 90)

    outlets = sorted(flow_rate_metrics.actual_flow_ratios.keys())
    for outlet in outlets:
        actual = flow_rate_metrics.actual_flow_ratios.get(outlet, 0)
        custom = flow_split_metrics.custom_split.get(outlet, 0)
        murray = flow_split_metrics.murray_split.get(outlet, 0)
        custom_dev = flow_rate_metrics.custom_vs_actual_deviation.get(outlet, 0)
        murray_dev = flow_rate_metrics.murray_vs_actual_deviation.get(outlet, 0)

        print(f"{outlet:<15} {actual:>10.1%}  {custom:>10.1%}  {murray:>10.1%}  {custom_dev:>10.1f}%  {murray_dev:>10.1f}%")

    # Step 4: Flow conservation
    print("\nSTEP 4: Flow Conservation Validation")
    print("-" * 70)

    print(f"Inlet Flow Rate:    {flow_rate_metrics.inlet_flow_rate:.6e} m³/s")
    print(f"Outlet Total:       {flow_rate_metrics.outlet_total_flow_rate:.6e} m³/s")
    print(f"Conservation Error: {flow_rate_metrics.flow_conservation_error_percent:.2f}%")
    print(f"Status:             {'✅ PASS' if flow_rate_metrics.flow_conservation_pass else '❌ FAIL'} "
          f"(threshold: {extractor.CONSERVATION_THRESHOLD}%)")

    # Step 5: Best match
    print("\nSTEP 5: Best Match Determination")
    print("-" * 70)

    if flow_rate_metrics.custom_vs_actual_deviation and flow_rate_metrics.murray_vs_actual_deviation:
        custom_mean = sum(flow_rate_metrics.custom_vs_actual_deviation.values()) / len(flow_rate_metrics.custom_vs_actual_deviation)
        murray_mean = sum(flow_rate_metrics.murray_vs_actual_deviation.values()) / len(flow_rate_metrics.murray_vs_actual_deviation)

        print(f"Custom vs Actual: {custom_mean:.1f}% mean deviation")
        print(f"Murray vs Actual: {murray_mean:.1f}% mean deviation")
        print(f"\nBest Match: {flow_rate_metrics.best_match.upper()}")

        if custom_mean < 10:
            print("✓ Custom split matches actual flow distribution well (<10% deviation)")
        elif murray_mean < 10:
            print("✓ Murray's Law matches actual flow distribution well (<10% deviation)")
        else:
            print("⚠️  Neither custom nor Murray match actual flow well (>10% deviation)")

    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)

    print(f"\n✓ Flow Split Analysis:  {'PASS' if flow_split_metrics.is_custom_valid else 'FAIL'}")
    print(f"✓ Flow Conservation:    {'PASS' if flow_rate_metrics.flow_conservation_pass else 'FAIL'}")
    print(f"✓ Best Match:           {flow_rate_metrics.best_match.upper()}")

    overall_pass = (
        flow_split_metrics.is_custom_valid and
        flow_rate_metrics.flow_conservation_pass
    )

    print(f"\n{'✅ OVERALL: PASS' if overall_pass else '❌ OVERALL: FAIL'}")
    print("\n" + "="*70 + "\n")

    return overall_pass


def main():
    """CLI for flow rate validation test"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test complete flow rate validation workflow"
    )
    parser.add_argument("case_dir", type=Path, help="OpenFOAM case directory")
    parser.add_argument("--run-postprocess", action="store_true",
                       help="Run postProcessing before validation")

    args = parser.parse_args()

    if not args.case_dir.exists():
        print(f"❌ Error: Case directory not found: {args.case_dir}")
        return 1

    # Run postProcessing if requested
    if args.run_postprocess:
        print("Running postProcessing...")
        from analyzers.flow_rate_extractor import FlowRateExtractor

        # Get patch names from geometry
        stl_dir = args.case_dir / "constant" / "triSurface"
        if stl_dir.exists():
            patches = ['inlet'] + [f.stem for f in stl_dir.glob("outlet*.stl")]

            extractor = FlowRateExtractor(args.case_dir)
            if not extractor.run_postProcessing(patches):
                print("❌ Error: postProcessing failed")
                return 1

    # Run validation
    success = test_flow_rate_validation_complete(args.case_dir)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
