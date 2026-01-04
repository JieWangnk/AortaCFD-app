#!/usr/bin/env python3
"""
Windkessel Parameter Sensitivity Analysis for AortaCFD Paper

This script performs systematic sensitivity analysis on Windkessel boundary
condition parameters to quantify their impact on hemodynamic predictions.

Parameters Varied:
1. Diastolic decay time (tau): 1.0, 1.5, 1.92 (default), 2.5 s
2. Pulse wave velocity (PWV): 4, 6 (default), 8, 10 m/s
3. Murray's law exponent: 2.0, 2.5, 3.0 (default)
4. Blood pressure: 110/70, 120/80 (default), 130/90 mmHg

Output Metrics:
- Mean outlet pressure (mmHg)
- Pressure drop inlet-to-outlets (mmHg)
- Flow split accuracy vs Murray prediction (%)
- Peak systolic velocity (m/s)
- Cycle-to-cycle convergence (cycles to steady state)

Usage:
    python scripts/run_windkessel_sensitivity_study.py --case BPM120 --dry-run
    python scripts/run_windkessel_sensitivity_study.py --case BPM120 --execute
    python scripts/run_windkessel_sensitivity_study.py --case BPM120 --analyze

Author: AortaCFD Team
Date: 2025
"""

import os
import sys
import json
import argparse
import itertools
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any
import copy

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np


class WindkesselSensitivityStudy:
    """Systematic sensitivity analysis for Windkessel parameters."""

    # Parameter ranges for sensitivity study
    PARAMETER_RANGES = {
        # Diastolic decay time constant (seconds)
        # Literature range: 1.5-2.5s (Westerhof 2009)
        "tau": {
            "values": [1.0, 1.5, 1.92, 2.5],
            "default": 1.92,
            "unit": "s",
            "description": "Diastolic decay time constant",
            "literature_range": "1.5-2.5 s"
        },

        # Pulse wave velocity (m/s)
        # Increases with age and arterial stiffness
        # Young healthy: 4-6 m/s, Elderly: 8-12 m/s
        "pwv": {
            "values": [4.0, 6.0, 8.0, 10.0],
            "default": 6.0,
            "unit": "m/s",
            "description": "Pulse wave velocity",
            "literature_range": "4-10 m/s (age-dependent)"
        },

        # Murray's law exponent
        # Theoretical: 3.0 for laminar flow optimization
        # Large vessels may deviate: 2.0-2.5 observed
        "murray_exponent": {
            "values": [2.0, 2.5, 3.0],
            "default": 3.0,
            "unit": "-",
            "description": "Murray's law flow distribution exponent",
            "literature_range": "2.0-3.0 (vessel size dependent)"
        },

        # Blood pressure (systolic/diastolic)
        "blood_pressure": {
            "values": [(110, 70), (120, 80), (130, 90)],
            "default": (120, 80),
            "unit": "mmHg",
            "description": "Systolic/Diastolic blood pressure",
            "literature_range": "Normal: 120/80 mmHg"
        }
    }

    def __init__(self, case_name: str, base_config_path: str = None):
        """Initialize sensitivity study.

        Args:
            case_name: Patient case identifier (e.g., 'BPM120')
            base_config_path: Path to base configuration JSON
        """
        self.case_name = case_name
        self.root_dir = Path(__file__).parent.parent
        self.output_dir = self.root_dir / "output" / case_name / "windkessel_sensitivity"

        # Load base configuration
        if base_config_path:
            self.base_config_path = Path(base_config_path)
        else:
            self.base_config_path = self.root_dir / "cases_input" / case_name / "config.json"

        if self.base_config_path.exists():
            with open(self.base_config_path) as f:
                self.base_config = json.load(f)
        else:
            raise FileNotFoundError(f"Base config not found: {self.base_config_path}")

        self.study_configs = []
        self.results = []

    def generate_study_matrix(self,
                              parameters: List[str] = None,
                              one_at_a_time: bool = True) -> List[Dict]:
        """Generate configuration matrix for sensitivity study.

        Args:
            parameters: List of parameters to vary (default: all)
            one_at_a_time: If True, vary one parameter at a time from baseline
                          If False, full factorial design

        Returns:
            List of configuration dictionaries for each study case
        """
        if parameters is None:
            parameters = list(self.PARAMETER_RANGES.keys())

        configs = []

        # Baseline configuration (all defaults)
        baseline = self._create_config_variant("baseline", {})
        configs.append(baseline)

        if one_at_a_time:
            # One-at-a-time (OAT) sensitivity analysis
            for param in parameters:
                param_info = self.PARAMETER_RANGES[param]
                default_val = param_info["default"]

                for value in param_info["values"]:
                    if value == default_val:
                        continue  # Skip baseline value

                    variant_name = f"{param}_{self._value_to_string(value)}"
                    variant = self._create_config_variant(variant_name, {param: value})
                    configs.append(variant)
        else:
            # Full factorial design (computationally expensive)
            param_values = [self.PARAMETER_RANGES[p]["values"] for p in parameters]

            for combination in itertools.product(*param_values):
                param_dict = dict(zip(parameters, combination))

                # Check if this is the baseline
                is_baseline = all(
                    param_dict[p] == self.PARAMETER_RANGES[p]["default"]
                    for p in parameters
                )
                if is_baseline:
                    continue

                variant_name = "_".join(
                    f"{p}_{self._value_to_string(v)}"
                    for p, v in param_dict.items()
                )
                variant = self._create_config_variant(variant_name, param_dict)
                configs.append(variant)

        self.study_configs = configs
        return configs

    def _value_to_string(self, value: Any) -> str:
        """Convert parameter value to safe string for filenames."""
        if isinstance(value, tuple):
            return f"{value[0]}_{value[1]}"
        elif isinstance(value, float):
            return f"{value:.1f}".replace(".", "p")
        else:
            return str(value)

    def _create_config_variant(self, name: str, param_overrides: Dict) -> Dict:
        """Create a configuration variant with specified parameter overrides.

        Args:
            name: Variant identifier
            param_overrides: Dictionary of parameter names to values

        Returns:
            Complete configuration dictionary
        """
        config = copy.deepcopy(self.base_config)

        # Ensure windkessel_settings exists
        if "boundary_conditions" not in config:
            config["boundary_conditions"] = {}
        if "outlets" not in config["boundary_conditions"]:
            config["boundary_conditions"]["outlets"] = {}
        if "windkessel_settings" not in config["boundary_conditions"]["outlets"]:
            config["boundary_conditions"]["outlets"]["windkessel_settings"] = {}

        wk_settings = config["boundary_conditions"]["outlets"]["windkessel_settings"]

        # Apply parameter overrides
        for param, value in param_overrides.items():
            if param == "tau":
                wk_settings["tau"] = value
            elif param == "pwv":
                wk_settings["pwv"] = value
                wk_settings["pwv_method"] = "fixed"
            elif param == "murray_exponent":
                # Murray exponent is applied through flow_split calculation
                wk_settings["murray_exponent"] = value
            elif param == "blood_pressure":
                wk_settings["systolic_pressure"] = value[0]
                wk_settings["diastolic_pressure"] = value[1]

        return {
            "name": name,
            "config": config,
            "parameters": param_overrides,
            "output_dir": str(self.output_dir / name)
        }

    def write_study_configs(self) -> List[Path]:
        """Write all study configurations to JSON files.

        Returns:
            List of paths to written configuration files
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        config_paths = []
        for study in self.study_configs:
            config_path = self.output_dir / f"config_{study['name']}.json"

            with open(config_path, 'w') as f:
                json.dump(study['config'], f, indent=2)

            config_paths.append(config_path)
            print(f"  Written: {config_path.name}")

        # Write study manifest
        manifest = {
            "study_type": "windkessel_sensitivity",
            "case_name": self.case_name,
            "created": datetime.now().isoformat(),
            "base_config": str(self.base_config_path),
            "parameter_ranges": self.PARAMETER_RANGES,
            "variants": [
                {
                    "name": s["name"],
                    "parameters": s["parameters"],
                    "config_file": f"config_{s['name']}.json"
                }
                for s in self.study_configs
            ]
        }

        manifest_path = self.output_dir / "study_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        print(f"\nStudy manifest: {manifest_path}")
        return config_paths

    def generate_run_script(self) -> Path:
        """Generate shell script to execute all sensitivity study cases.

        Returns:
            Path to generated run script
        """
        script_lines = [
            "#!/bin/bash",
            "# Windkessel Sensitivity Study - Auto-generated Run Script",
            f"# Case: {self.case_name}",
            f"# Generated: {datetime.now().isoformat()}",
            "",
            "set -e  # Exit on error",
            "",
            f"CASE_DIR=\"{self.root_dir}\"",
            f"OUTPUT_BASE=\"{self.output_dir}\"",
            "",
            "cd $CASE_DIR",
            "",
            "echo '=========================================='",
            "echo 'Windkessel Sensitivity Study'",
            f"echo 'Case: {self.case_name}'",
            f"echo 'Variants: {len(self.study_configs)}'",
            "echo '=========================================='",
            ""
        ]

        # Get path to patient case input directory for copying required files
        patient_input_dir = self.root_dir / "cases_input" / self.case_name

        for i, study in enumerate(self.study_configs, 1):
            script_lines.extend([
                f"echo ''",
                f"echo '[{i}/{len(self.study_configs)}] Running: {study['name']}'",
                f"echo '----------------------------------------'",
                f"# Create output directory and copy required input files",
                f"mkdir -p \"{study['output_dir']}/openfoam\"",
                f"cp -n \"{patient_input_dir}\"/*.csv \"{study['output_dir']}/\" 2>/dev/null || true",
                f"cp -n \"{patient_input_dir}\"/*.stl \"{study['output_dir']}/\" 2>/dev/null || true",
                f"python run_patient.py {self.case_name} \\",
                f"    --config \"{self.output_dir}/config_{study['name']}.json\" \\",
                f"    --case-dir \"{study['output_dir']}\" \\",
                f"    --steps case,mesh,boundary,solver",
                ""
            ])

        script_lines.extend([
            "echo ''",
            "echo '=========================================='",
            "echo 'All sensitivity study cases completed!'",
            "echo '=========================================='",
        ])

        script_path = self.output_dir / "run_sensitivity_study.sh"
        with open(script_path, 'w') as f:
            f.write('\n'.join(script_lines))

        script_path.chmod(0o755)
        print(f"\nRun script: {script_path}")
        return script_path

    def print_study_summary(self):
        """Print summary of planned sensitivity study."""
        print("\n" + "=" * 70)
        print("WINDKESSEL PARAMETER SENSITIVITY STUDY")
        print("=" * 70)
        print(f"\nCase: {self.case_name}")
        print(f"Base config: {self.base_config_path}")
        print(f"Output directory: {self.output_dir}")

        print("\n" + "-" * 70)
        print("PARAMETER RANGES")
        print("-" * 70)

        for param, info in self.PARAMETER_RANGES.items():
            print(f"\n{param} ({info['description']}):")
            print(f"  Values: {info['values']} {info['unit']}")
            print(f"  Default: {info['default']} {info['unit']}")
            print(f"  Literature: {info['literature_range']}")

        print("\n" + "-" * 70)
        print(f"STUDY VARIANTS ({len(self.study_configs)} total)")
        print("-" * 70)

        for study in self.study_configs:
            if study['parameters']:
                params_str = ", ".join(
                    f"{k}={v}" for k, v in study['parameters'].items()
                )
            else:
                params_str = "(baseline - all defaults)"
            print(f"  {study['name']}: {params_str}")

        # Estimate computational cost
        est_time_per_case = 45  # minutes (standard profile, ~1M cells)
        total_time = len(self.study_configs) * est_time_per_case

        print("\n" + "-" * 70)
        print("ESTIMATED COMPUTATIONAL COST")
        print("-" * 70)
        print(f"  Cases: {len(self.study_configs)}")
        print(f"  Est. time per case: ~{est_time_per_case} min (standard profile)")
        print(f"  Total estimated time: ~{total_time} min ({total_time/60:.1f} hours)")
        print(f"  Parallel (8 cores each): ~{total_time/60:.1f} hours sequential")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Windkessel Parameter Sensitivity Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Preview study design (dry run)
    python scripts/run_windkessel_sensitivity_study.py --case BPM120 --dry-run

    # Generate configs and run script
    python scripts/run_windkessel_sensitivity_study.py --case BPM120 --generate

    # Specific parameters only
    python scripts/run_windkessel_sensitivity_study.py --case BPM120 --params tau,pwv

    # Full factorial design (many cases!)
    python scripts/run_windkessel_sensitivity_study.py --case BPM120 --factorial
        """
    )

    parser.add_argument("--case", required=True,
                        help="Case name (e.g., BPM120)")
    parser.add_argument("--config", default=None,
                        help="Base configuration file (default: cases_input/<case>/config.json)")
    parser.add_argument("--params", default=None,
                        help="Comma-separated list of parameters to vary (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview study design without writing files")
    parser.add_argument("--generate", action="store_true",
                        help="Generate configuration files and run script")
    parser.add_argument("--factorial", action="store_true",
                        help="Use full factorial design (default: one-at-a-time)")

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Initialize study
    study = WindkesselSensitivityStudy(args.case, args.config)

    # Parse parameter list
    if args.params:
        parameters = [p.strip() for p in args.params.split(",")]
    else:
        parameters = None

    # Generate study matrix
    study.generate_study_matrix(
        parameters=parameters,
        one_at_a_time=not args.factorial
    )

    # Print summary
    study.print_study_summary()

    if args.dry_run:
        print("\n[DRY RUN] No files written.")
        return

    if args.generate:
        print("\n" + "=" * 70)
        print("GENERATING STUDY FILES")
        print("=" * 70)

        study.write_study_configs()
        study.generate_run_script()

        print("\n" + "=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print(f"""
1. Review generated configurations in:
   {study.output_dir}/

2. Execute the sensitivity study:
   bash {study.output_dir}/run_sensitivity_study.sh

3. After completion, analyze results:
   python scripts/run_windkessel_sensitivity_study.py --case {args.case} --analyze
        """)


if __name__ == "__main__":
    main()
