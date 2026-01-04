#!/usr/bin/env python3
"""
Numerical Profile Sensitivity Analysis for AortaCFD Paper

This script performs systematic sensitivity analysis comparing the three
numerical profiles (robust, standard, accurate) to quantify their impact
on hemodynamic predictions and computational cost.

Profiles Compared:
1. robust: First-order Euler/upwind, maximum stability
2. standard: Second-order backward/linearUpwind, production quality
3. accurate: Second-order CrankNicolson/LUST, low numerical diffusion

Output Metrics:
- Mean/peak WSS (Pa) and spatial distribution
- Pressure drop inlet-to-outlets (mmHg)
- Peak systolic velocity (m/s)
- Cycle-to-cycle convergence behavior
- Computational cost (wall-clock time, iterations per timestep)
- Residual convergence characteristics

Usage:
    python scripts/run_numerical_profile_sensitivity_study.py --case BPM120 --dry-run
    python scripts/run_numerical_profile_sensitivity_study.py --case BPM120 --generate
    python scripts/run_numerical_profile_sensitivity_study.py --case BPM120 --analyze

Author: AortaCFD Team
Date: 2025
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import copy

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class NumericalProfileSensitivityStudy:
    """Systematic sensitivity analysis for numerical discretization profiles."""

    # Profile specifications for sensitivity study
    PROFILE_SPECS = {
        "robust": {
            "description": "First-order schemes, maximum stability",
            "time_scheme": "Euler",
            "convection_scheme": "Gauss upwind",
            "max_co": 0.5,
            "order_of_accuracy": 1,
            "expected_diffusion": "high",
            "typical_runtime_factor": 1.5,  # Relative to standard
            "use_case": "Poor meshes, debugging, initial testing"
        },
        "standard": {
            "description": "Second-order bounded schemes, production quality",
            "time_scheme": "backward",
            "convection_scheme": "Gauss linearUpwind",
            "max_co": 1.0,
            "order_of_accuracy": 2,
            "expected_diffusion": "low",
            "typical_runtime_factor": 1.0,  # Baseline
            "use_case": "Clinical studies, production runs"
        },
        "accurate": {
            "description": "Low-diffusion schemes for validation",
            "time_scheme": "CrankNicolson 0.9",
            "convection_scheme": "Gauss LUST",
            "max_co": 0.8,
            "order_of_accuracy": 2,
            "expected_diffusion": "minimal",
            "typical_runtime_factor": 2.5,  # 2-3x standard
            "use_case": "Mesh convergence, validation, LES"
        }
    }

    # Key parameters that differ between profiles
    PROFILE_PARAMETERS = {
        "ddtSchemes": {
            "robust": "Euler",
            "standard": "backward",
            "accurate": "CrankNicolson 0.9"
        },
        "divSchemes_U": {
            "robust": "Gauss upwind",
            "standard": "Gauss linearUpwind grad(U)",
            "accurate": "Gauss LUST grad(U)"
        },
        "nOuterCorrectors": {
            "robust": 20,
            "standard": 30,
            "accurate": 50
        },
        "relaxation_p": {
            "robust": 0.15,
            "standard": 0.3,
            "accurate": 0.5
        },
        "relaxation_U": {
            "robust": 0.4,
            "standard": 0.7,
            "accurate": 0.9
        },
        "max_co": {
            "robust": 0.5,
            "standard": 1.0,
            "accurate": 0.8
        },
        "residual_tolerance": {
            "robust": 1e-4,
            "standard": 1e-6,
            "accurate": 1e-8
        }
    }

    def __init__(self, case_name: str, base_config_path: str = None):
        """Initialize numerical profile sensitivity study.

        Args:
            case_name: Patient case identifier (e.g., 'BPM120')
            base_config_path: Path to base configuration JSON
        """
        self.case_name = case_name
        self.root_dir = Path(__file__).parent.parent
        self.output_dir = self.root_dir / "output" / case_name / "profile_sensitivity"

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

    def generate_study_matrix(self, profiles: List[str] = None) -> List[Dict]:
        """Generate configuration matrix for profile sensitivity study.

        Args:
            profiles: List of profiles to test (default: all three)

        Returns:
            List of configuration dictionaries for each study case
        """
        if profiles is None:
            profiles = list(self.PROFILE_SPECS.keys())

        configs = []

        for profile in profiles:
            if profile not in self.PROFILE_SPECS:
                print(f"Warning: Unknown profile '{profile}', skipping")
                continue

            variant = self._create_config_variant(profile)
            configs.append(variant)

        self.study_configs = configs
        return configs

    def _create_config_variant(self, profile_name: str) -> Dict:
        """Create a configuration variant for a specific numerical profile.

        Args:
            profile_name: Name of the profile (robust, standard, accurate)

        Returns:
            Complete configuration dictionary
        """
        config = copy.deepcopy(self.base_config)

        # Set the numerical profile
        config["numerics_profile"] = profile_name

        # Override specific parameters to ensure profile is applied
        if "numerical" not in config:
            config["numerical"] = {}

        config["numerical"]["profile"] = profile_name

        return {
            "name": f"profile_{profile_name}",
            "profile": profile_name,
            "config": config,
            "specs": self.PROFILE_SPECS[profile_name],
            "output_dir": str(self.output_dir / f"profile_{profile_name}")
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
            "study_type": "numerical_profile_sensitivity",
            "case_name": self.case_name,
            "created": datetime.now().isoformat(),
            "base_config": str(self.base_config_path),
            "profile_specs": self.PROFILE_SPECS,
            "profile_parameters": self.PROFILE_PARAMETERS,
            "variants": [
                {
                    "name": s["name"],
                    "profile": s["profile"],
                    "config_file": f"config_{s['name']}.json",
                    "specs": s["specs"]
                }
                for s in self.study_configs
            ]
        }

        manifest_path = self.output_dir / "study_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2, default=str)

        print(f"\nStudy manifest: {manifest_path}")
        return config_paths

    def generate_run_script(self) -> Path:
        """Generate shell script to execute all profile sensitivity cases.

        Returns:
            Path to generated run script
        """
        script_lines = [
            "#!/bin/bash",
            "# Numerical Profile Sensitivity Study - Auto-generated Run Script",
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
            "echo 'Numerical Profile Sensitivity Study'",
            f"echo 'Case: {self.case_name}'",
            f"echo 'Profiles: {len(self.study_configs)}'",
            "echo '=========================================='",
            "",
            "# Record start times for computational cost analysis",
            "declare -A START_TIMES",
            "declare -A END_TIMES",
            ""
        ]

        # Get path to patient case input directory for copying required files
        patient_input_dir = self.root_dir / "cases_input" / self.case_name

        for i, study in enumerate(self.study_configs, 1):
            profile = study['profile']
            specs = study['specs']
            script_lines.extend([
                f"echo ''",
                f"echo '[{i}/{len(self.study_configs)}] Running profile: {profile}'",
                f"echo '  Description: {specs['description']}'",
                f"echo '  Time scheme: {specs['time_scheme']}'",
                f"echo '  Convection:  {specs['convection_scheme']}'",
                f"echo '  Max Co:      {specs['max_co']}'",
                f"echo '----------------------------------------'",
                f"START_TIMES[{profile}]=$(date +%s)",
                f"",
                f"# Create output directory and copy required input files",
                f"mkdir -p \"{study['output_dir']}/openfoam\"",
                f"cp -n \"{patient_input_dir}\"/*.csv \"{study['output_dir']}/\" 2>/dev/null || true",
                f"cp -n \"{patient_input_dir}\"/*.stl \"{study['output_dir']}/\" 2>/dev/null || true",
                f"python run_patient.py {self.case_name} \\",
                f"    --config \"{self.output_dir}/config_{study['name']}.json\" \\",
                f"    --case-dir \"{study['output_dir']}\" \\",
                f"    --steps case,mesh,boundary,solver",
                f"",
                f"END_TIMES[{profile}]=$(date +%s)",
                f"ELAPSED=$((END_TIMES[{profile}] - START_TIMES[{profile}]))",
                f"echo \"Profile {profile} completed in $ELAPSED seconds\"",
                ""
            ])

        script_lines.extend([
            "echo ''",
            "echo '=========================================='",
            "echo 'COMPUTATIONAL COST SUMMARY'",
            "echo '=========================================='",
        ])

        for study in self.study_configs:
            profile = study['profile']
            script_lines.append(
                f"echo \"  {profile}: $((END_TIMES[{profile}] - START_TIMES[{profile}])) seconds\""
            )

        script_lines.extend([
            "echo ''",
            "echo '=========================================='",
            "echo 'All profile sensitivity cases completed!'",
            "echo '=========================================='",
        ])

        script_path = self.output_dir / "run_profile_sensitivity.sh"
        with open(script_path, 'w') as f:
            f.write('\n'.join(script_lines))

        script_path.chmod(0o755)
        print(f"\nRun script: {script_path}")
        return script_path

    def print_study_summary(self):
        """Print summary of planned profile sensitivity study."""
        print("\n" + "=" * 70)
        print("NUMERICAL PROFILE SENSITIVITY STUDY")
        print("=" * 70)
        print(f"\nCase: {self.case_name}")
        print(f"Base config: {self.base_config_path}")
        print(f"Output directory: {self.output_dir}")

        print("\n" + "-" * 70)
        print("PROFILE SPECIFICATIONS")
        print("-" * 70)

        for profile, specs in self.PROFILE_SPECS.items():
            print(f"\n{profile.upper()}:")
            print(f"  Description:  {specs['description']}")
            print(f"  Time scheme:  {specs['time_scheme']}")
            print(f"  Convection:   {specs['convection_scheme']}")
            print(f"  Max Courant:  {specs['max_co']}")
            print(f"  Accuracy:     {specs['order_of_accuracy']}nd order")
            print(f"  Diffusion:    {specs['expected_diffusion']}")
            print(f"  Runtime:      {specs['typical_runtime_factor']}x standard")
            print(f"  Use case:     {specs['use_case']}")

        print("\n" + "-" * 70)
        print("KEY PARAMETER COMPARISON")
        print("-" * 70)
        print(f"\n{'Parameter':<25} {'robust':<15} {'standard':<15} {'accurate':<15}")
        print("-" * 70)

        for param, values in self.PROFILE_PARAMETERS.items():
            robust_val = str(values['robust'])
            standard_val = str(values['standard'])
            accurate_val = str(values['accurate'])
            print(f"{param:<25} {robust_val:<15} {standard_val:<15} {accurate_val:<15}")

        print("\n" + "-" * 70)
        print(f"STUDY VARIANTS ({len(self.study_configs)} total)")
        print("-" * 70)

        for study in self.study_configs:
            print(f"  {study['name']}: {study['specs']['description']}")

        # Estimate computational cost
        total_factor = sum(
            s['specs']['typical_runtime_factor'] for s in self.study_configs
        )
        base_time = 45  # minutes for standard profile

        print("\n" + "-" * 70)
        print("ESTIMATED COMPUTATIONAL COST")
        print("-" * 70)
        print(f"  Profiles to test: {len(self.study_configs)}")
        print(f"  Base time (standard): ~{base_time} min")
        print(f"  Combined factor: {total_factor:.1f}x")
        print(f"  Total estimated time: ~{int(base_time * total_factor)} min "
              f"({base_time * total_factor / 60:.1f} hours)")

        print("\n" + "-" * 70)
        print("EXPECTED OUTCOMES")
        print("-" * 70)
        print("""
The study should demonstrate:

1. NUMERICAL DIFFUSION EFFECT:
   - robust profile: Higher diffusion, smoother WSS gradients
   - standard profile: Moderate diffusion, good balance
   - accurate profile: Low diffusion, sharper gradients

2. COMPUTATIONAL COST:
   - robust: ~1.5x standard (more iterations, smaller timestep)
   - standard: baseline
   - accurate: ~2-3x standard (tighter tolerances, more correctors)

3. CONVERGENCE BEHAVIOR:
   - robust: Guaranteed convergence, slower
   - standard: Good convergence on quality meshes
   - accurate: Requires good mesh quality

4. QUANTITATIVE METRICS:
   - WSS: robust < standard < accurate (peak values)
   - Pressure: Similar within ~5%
   - Flow rates: Should match within mass conservation

Reference: Jasak (1996), Ferziger & Peric (2002)
        """)


def generate_paper_section():
    """Generate LaTeX text for numerical profile sensitivity section."""
    section = r"""
\subsection{Numerical Profile Sensitivity}

To quantify the impact of numerical discretization choices on hemodynamic predictions,
we performed a systematic sensitivity analysis comparing the three numerical profiles
implemented in AortaCFD: \texttt{robust}, \texttt{standard}, and \texttt{accurate}.
Each profile represents a trade-off between stability, accuracy, and computational cost.

\subsubsection{Profile Specifications}

Table~\ref{tab:profile_comparison} summarizes the key discretization parameters
for each profile. The \texttt{robust} profile employs first-order schemes (Euler time
integration, upwind convection) for maximum stability at the cost of numerical diffusion.
The \texttt{standard} profile uses second-order bounded schemes (backward time integration,
linearUpwind convection) providing a balance suitable for production simulations.
The \texttt{accurate} profile minimizes numerical diffusion using Crank-Nicolson time
integration ($\alpha=0.9$) and the LUST convection scheme (75\% central + 25\% upwind).

\begin{table}[h]
\centering
\caption{Numerical profile parameter comparison}
\label{tab:profile_comparison}
\small
\begin{tabular}{lccc}
\toprule
\textbf{Parameter} & \textbf{robust} & \textbf{standard} & \textbf{accurate} \\
\midrule
Time scheme & Euler & backward & CrankNicolson 0.9 \\
Convection (U) & Gauss upwind & linearUpwind & LUST \\
Max Courant & 0.5 & 1.0 & 0.8 \\
nOuterCorrectors & 20 & 30 & 50 \\
$\alpha_p$ & 0.15 & 0.3 & 0.5 \\
$\alpha_U$ & 0.4 & 0.7 & 0.9 \\
Residual tol. & $10^{-4}$ & $10^{-6}$ & $10^{-8}$ \\
\midrule
Order of accuracy & 1st & 2nd & 2nd \\
Numerical diffusion & High & Low & Minimal \\
Relative cost & 1.5$\times$ & 1.0$\times$ & 2.5$\times$ \\
\bottomrule
\end{tabular}
\end{table}

\subsubsection{Sensitivity Results}

[INSERT RESULTS FROM SENSITIVITY STUDY HERE]

Key findings:
\begin{itemize}
    \item Peak WSS values increased by X\% from \texttt{robust} to \texttt{accurate},
          consistent with reduced numerical diffusion
    \item Mean pressure drop varied by less than Y\% across profiles
    \item Flow distribution remained within Z\% of Murray's law predictions
    \item Computational cost ratio: robust:standard:accurate = A:1:B
\end{itemize}

The results demonstrate that while first-order schemes (\texttt{robust}) provide
reliable convergence, they underpredict peak WSS values due to numerical diffusion.
For clinical applications requiring accurate WSS quantification, the \texttt{standard}
or \texttt{accurate} profiles are recommended. The \texttt{robust} profile remains
valuable for initial geometry testing and cases with challenging mesh quality.
"""
    return section


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Numerical Profile Sensitivity Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Preview study design (dry run)
    python scripts/run_numerical_profile_sensitivity_study.py --case BPM120 --dry-run

    # Generate configs and run script
    python scripts/run_numerical_profile_sensitivity_study.py --case BPM120 --generate

    # Specific profiles only
    python scripts/run_numerical_profile_sensitivity_study.py --case BPM120 --profiles standard,accurate

    # Generate paper section template
    python scripts/run_numerical_profile_sensitivity_study.py --paper-section
        """
    )

    parser.add_argument("--case", required=False,
                        help="Case name (e.g., BPM120)")
    parser.add_argument("--config", default=None,
                        help="Base configuration file (default: cases_input/<case>/config.json)")
    parser.add_argument("--profiles", default=None,
                        help="Comma-separated list of profiles to test (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview study design without writing files")
    parser.add_argument("--generate", action="store_true",
                        help="Generate configuration files and run script")
    parser.add_argument("--paper-section", action="store_true",
                        help="Print LaTeX template for paper sensitivity section")

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    if args.paper_section:
        print(generate_paper_section())
        return

    if not args.case:
        print("Error: --case is required unless using --paper-section")
        sys.exit(1)

    # Initialize study
    study = NumericalProfileSensitivityStudy(args.case, args.config)

    # Parse profile list
    if args.profiles:
        profiles = [p.strip() for p in args.profiles.split(",")]
    else:
        profiles = None

    # Generate study matrix
    study.generate_study_matrix(profiles=profiles)

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
   bash {study.output_dir}/run_profile_sensitivity.sh

3. After completion, analyze results:
   python scripts/analyze_sensitivity_results.py --study-dir {study.output_dir}

4. Extract LaTeX section for paper:
   python scripts/run_numerical_profile_sensitivity_study.py --paper-section
        """)


if __name__ == "__main__":
    main()
