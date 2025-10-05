#!/usr/bin/env python3
"""
Demo: Custom Flow Split vs Murray's Law Comparison

This demonstrates how to:
1. Create a custom flow split (30% outlets 1-3, 70% outlet 4)
2. Calculate Murray's Law expected ratios from geometry
3. Compare custom vs Murray distributions
"""

import sys
import json
from pathlib import Path
import shutil

# Add validation to path
sys.path.insert(0, str(Path(__file__).parent))

from analyzers.flow_split_analyzer import FlowSplitAnalyzer


def setup_demo_case():
    """Create a demo case directory with STL files"""
    demo_dir = Path("validation/output/flow_split_demo")
    demo_dir.mkdir(parents=True, exist_ok=True)

    # Create triSurface directory
    stl_dir = demo_dir / "constant" / "triSurface"
    stl_dir.mkdir(parents=True, exist_ok=True)

    # Copy patient1 STL files
    patient_dir = Path("cases_input/patient1")
    for stl_file in patient_dir.glob("outlet*.stl"):
        shutil.copy(stl_file, stl_dir / stl_file.name)

    print(f"✓ Created demo case: {demo_dir}")
    print(f"✓ Copied outlet STL files to {stl_dir}")

    return demo_dir


def test_custom_split(case_dir: Path):
    """Test custom flow split: 30% to outlets 1-3, 70% to outlet 4"""

    print("\n" + "="*70)
    print("TEST 1: Custom Flow Split (30% outlets 1-3, 70% outlet 4)")
    print("="*70)

    # Create custom config
    config = {
        "physics": {
            "murray_exponent": 2.39
        },
        "boundary_conditions": {
            "outlets": {
                "type": "3EWINDKESSEL",
                "windkessel_settings": {
                    "methodology": "custom_flow_split",
                    "flow_split": {
                        "outlet1": 0.10,  # 10%
                        "outlet2": 0.10,  # 10%
                        "outlet3": 0.10,  # 10%
                        "outlet4": 0.70   # 70%
                    }
                }
            }
        }
    }

    # Run analysis
    analyzer = FlowSplitAnalyzer(case_dir)
    metrics = analyzer.analyze_flow_split(config)
    analyzer.print_analysis_report(metrics)

    return metrics


def test_murray_auto(case_dir: Path):
    """Test Murray's Law automatic calculation"""

    print("\n" + "="*70)
    print("TEST 2: Murray's Law Automatic (from geometry)")
    print("="*70)

    # Create Murray auto config
    config = {
        "physics": {
            "murray_exponent": 2.39
        },
        "boundary_conditions": {
            "outlets": {
                "type": "3EWINDKESSEL",
                "windkessel_settings": {
                    "methodology": "murray_law_automatic"
                    # No flow_split - will be auto-calculated
                }
            }
        }
    }

    # Run analysis
    analyzer = FlowSplitAnalyzer(case_dir)
    metrics = analyzer.analyze_flow_split(config)
    analyzer.print_analysis_report(metrics)

    return metrics


def test_equal_split(case_dir: Path):
    """Test equal flow split (25% each for 4 outlets)"""

    print("\n" + "="*70)
    print("TEST 3: Equal Flow Split (25% each)")
    print("="*70)

    # Create equal split config
    config = {
        "physics": {
            "murray_exponent": 2.39
        },
        "boundary_conditions": {
            "outlets": {
                "type": "3EWINDKESSEL",
                "windkessel_settings": {
                    "methodology": "equal_split",
                    "flow_split": {
                        "outlet1": 0.25,
                        "outlet2": 0.25,
                        "outlet3": 0.25,
                        "outlet4": 0.25
                    }
                }
            }
        }
    }

    # Run analysis
    analyzer = FlowSplitAnalyzer(case_dir)
    metrics = analyzer.analyze_flow_split(config)
    analyzer.print_analysis_report(metrics)

    return metrics


def compare_results(custom_metrics, murray_metrics, equal_metrics):
    """Compare all three flow split methods"""

    print("\n" + "="*70)
    print("COMPARISON: Custom vs Murray vs Equal")
    print("="*70)

    print("\nFLOW SPLIT RATIOS:")
    print(f"{'Outlet':<15} {'Custom':<12} {'Murray':<12} {'Equal':<12}")
    print("-" * 70)

    outlets = sorted(custom_metrics.custom_split.keys())
    for outlet in outlets:
        custom = custom_metrics.custom_split.get(outlet, 0)
        murray = murray_metrics.murray_split.get(outlet, 0)
        equal = equal_metrics.custom_split.get(outlet, 0)

        print(f"{outlet:<15} {custom:>10.1%}  {murray:>10.1%}  {equal:>10.1%}")

    print("\nDEVIATION FROM MURRAY'S LAW:")
    print(f"{'Method':<15} {'Mean Deviation':<20} {'Max Deviation':<20} {'Match?':<10}")
    print("-" * 70)

    methods = [
        ("Custom (30/70)", custom_metrics),
        ("Equal (25%)", equal_metrics),
        ("Murray Auto", murray_metrics)
    ]

    for name, m in methods:
        mean_dev = m.mean_deviation_percent
        max_dev = m.max_deviation_percent
        match = "✓ Yes" if m.ratios_match else "✗ No"

        print(f"{name:<15} {mean_dev:>18.1f}%  {max_dev:>18.1f}%  {match:<10}")

    print("\n" + "="*70 + "\n")


def main():
    print("\n" + "="*70)
    print("FLOW SPLIT ANALYSIS DEMO")
    print("Comparing Custom vs Murray's Law Flow Distributions")
    print("="*70 + "\n")

    # Setup demo case
    case_dir = setup_demo_case()

    # Test 1: Custom split (30% outlets 1-3, 70% outlet 4)
    custom_metrics = test_custom_split(case_dir)

    # Test 2: Murray's Law automatic
    murray_metrics = test_murray_auto(case_dir)

    # Test 3: Equal split
    equal_metrics = test_equal_split(case_dir)

    # Compare all results
    compare_results(custom_metrics, murray_metrics, equal_metrics)

    print("✅ Demo complete!")
    print(f"\nDemo case created at: {case_dir}")
    print("You can modify the flow_split values in the configs above to test different distributions.\n")


if __name__ == "__main__":
    main()
