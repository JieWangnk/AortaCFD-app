#!/usr/bin/env python3
"""
Generate Windkessel Sensitivity Analysis Figures for Publication.

Creates:
1. Tornado plot showing sensitivity of systolic/diastolic pressure to each parameter
2. Pressure waveform comparison (2x2 grid) for each parameter variation
3. Summary bar chart of sensitivity indices

Author: AortaCFD Team
Date: 2026-01
"""

import json
from pathlib import Path
import numpy as np

# Try matplotlib, provide instructions if not available
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.ticker import MultipleLocator
except ImportError:
    print("matplotlib not installed. Install with: pip install matplotlib")
    exit(1)

# Publication style settings
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 11,
    'legend.fontsize': 9,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
})

# Paths
STUDY_DIR = Path("/home/mchi4jw4/GitHub/AortaCFD-app/output/BPM120/windkessel_sensitivity")
OUTPUT_DIR = STUDY_DIR / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_results():
    """Load extracted sensitivity results."""
    results_path = STUDY_DIR / "sensitivity_results.json"
    with open(results_path) as f:
        return json.load(f)


def create_tornado_plot(results: dict):
    """
    Create tornado plot showing parameter sensitivity.

    Horizontal bars showing deviation from baseline for each parameter.
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    baseline = results["baseline"]
    baseline_sys = baseline["p_systolic_mmHg"]
    baseline_dia = baseline["p_diastolic_mmHg"]

    # Define parameter groups
    param_groups = {
        r"$\tau$ (decay time)": ["tau_1p0", "tau_1p5", "tau_2p5"],
        "PWV": ["pwv_4p0", "pwv_8p0", "pwv_10p0"],
        "Murray exp.": ["murray_exponent_2p0", "murray_exponent_2p5"],
        "Blood pressure": ["blood_pressure_110_70", "blood_pressure_130_90"],
    }

    y_positions = []
    labels = []
    sys_deviations = []
    dia_deviations = []

    y = 0
    for param_name, cases in param_groups.items():
        sys_values = [results[c]["p_systolic_mmHg"] for c in cases if c in results]
        dia_values = [results[c]["p_diastolic_mmHg"] for c in cases if c in results]

        if sys_values:
            sys_min = min(sys_values) - baseline_sys
            sys_max = max(sys_values) - baseline_sys
            dia_min = min(dia_values) - baseline_dia
            dia_max = max(dia_values) - baseline_dia

            y_positions.append(y)
            labels.append(param_name)
            sys_deviations.append((sys_min, sys_max))
            dia_deviations.append((dia_min, dia_max))
            y += 1

    # Plot bars
    bar_height = 0.35
    colors = {'sys': '#1f77b4', 'dia': '#ff7f0e'}

    for i, (y_pos, label) in enumerate(zip(y_positions, labels)):
        sys_min, sys_max = sys_deviations[i]
        dia_min, dia_max = dia_deviations[i]

        # Systolic bar
        ax.barh(y_pos + bar_height/2, sys_max - sys_min,
                height=bar_height, left=sys_min,
                color=colors['sys'], alpha=0.8, label='Systolic' if i == 0 else '')

        # Diastolic bar
        ax.barh(y_pos - bar_height/2, dia_max - dia_min,
                height=bar_height, left=dia_min,
                color=colors['dia'], alpha=0.8, label='Diastolic' if i == 0 else '')

    # Styling
    ax.axvline(x=0, color='black', linewidth=0.8, linestyle='-')
    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels)
    ax.set_xlabel('Pressure deviation from baseline (mmHg)')
    ax.set_title('Windkessel Parameter Sensitivity')
    ax.legend(loc='upper right')
    ax.set_xlim(-25, 15)

    plt.tight_layout()

    # Save
    fig.savefig(OUTPUT_DIR / "tornado_plot.png")
    fig.savefig(OUTPUT_DIR / "tornado_plot.pdf")
    print(f"Saved: {OUTPUT_DIR / 'tornado_plot.png'}")
    plt.close()


def create_pressure_waveform_grid(results: dict):
    """
    Create 2x2 grid of pressure waveforms showing parameter variations.
    """
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))

    baseline = results["baseline"]

    # Define what to plot in each panel
    panels = [
        {
            "title": r"(a) Diastolic decay time $\tau$",
            "cases": ["tau_1p0", "tau_1p5", "baseline", "tau_2p5"],
            "labels": [r"$\tau$=1.0s", r"$\tau$=1.5s", r"$\tau$=1.92s (baseline)", r"$\tau$=2.5s"],
            "ax": axes[0, 0]
        },
        {
            "title": "(b) Pulse wave velocity (PWV)",
            "cases": ["pwv_4p0", "baseline", "pwv_8p0", "pwv_10p0"],
            "labels": ["PWV=4 m/s", "PWV=6 m/s (baseline)", "PWV=8 m/s", "PWV=10 m/s"],
            "ax": axes[0, 1]
        },
        {
            "title": "(c) Murray exponent $n$",
            "cases": ["murray_exponent_2p0", "murray_exponent_2p5", "baseline"],
            "labels": ["$n$=2.0", "$n$=2.5", "$n$=3.0 (baseline)"],
            "ax": axes[1, 0]
        },
        {
            "title": "(d) Blood pressure target",
            "cases": ["blood_pressure_110_70", "baseline", "blood_pressure_130_90"],
            "labels": ["110/70 mmHg", "120/80 mmHg (baseline)", "130/90 mmHg"],
            "ax": axes[1, 1]
        },
    ]

    colors = plt.cm.viridis(np.linspace(0.2, 0.8, 4))

    for panel in panels:
        ax = panel["ax"]

        for i, (case, label) in enumerate(zip(panel["cases"], panel["labels"])):
            if case in results and "outlet_data" in results[case]:
                outlet_data = results[case]["outlet_data"]["outlet1"]
                times = outlet_data["times"]
                pressures = outlet_data["pressures_mmHg"]

                # Normalize time to 0-1 (within cardiac cycle)
                t_normalized = [(t - 1.0) / 0.5 for t in times]  # Last cycle is t=1.0 to 1.5

                style = '-' if 'baseline' not in case else '-'
                lw = 1.5 if 'baseline' not in case else 2.5
                color = colors[i % len(colors)]

                ax.plot(t_normalized, pressures, style, linewidth=lw,
                       color=color, label=label)

        ax.set_xlabel('Cardiac cycle phase')
        ax.set_ylabel('Pressure (mmHg)')
        ax.set_title(panel["title"])
        ax.legend(loc='upper right', fontsize=8)
        ax.set_xlim(0, 1)
        ax.set_ylim(50, 160)
        ax.xaxis.set_major_locator(MultipleLocator(0.25))

    plt.tight_layout()

    # Save
    fig.savefig(OUTPUT_DIR / "pressure_waveforms_grid.png")
    fig.savefig(OUTPUT_DIR / "pressure_waveforms_grid.pdf")
    print(f"Saved: {OUTPUT_DIR / 'pressure_waveforms_grid.png'}")
    plt.close()


def create_sensitivity_bar_chart(results: dict):
    """
    Create bar chart of sensitivity indices.
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    baseline = results["baseline"]
    baseline_sys = baseline["p_systolic_mmHg"]
    baseline_dia = baseline["p_diastolic_mmHg"]
    baseline_mean = baseline["p_mean_mmHg"]
    baseline_pulse = baseline["p_pulse_mmHg"]

    # Calculate sensitivity indices
    def calc_sensitivity(param_values, baseline_val, param_range_ratio):
        """S = (delta_y / y) / (delta_x / x)"""
        min_val = min(param_values)
        max_val = max(param_values)
        delta_y = max_val - min_val
        return (delta_y / baseline_val) / param_range_ratio

    # Parameter range ratios (fraction of baseline)
    # tau: 1.0-2.5 baseline 1.92 => range = 1.5/1.92 = 0.78
    # PWV: 4-10 baseline 6 => range = 6/6 = 1.0
    # murray: 2-3 baseline 3 => range = 1/3 = 0.33
    # BP: 110-130/70-90 baseline 120/80 => ~0.17 for sys, 0.25 for dia

    params = ['$\\tau$', 'PWV', 'Murray $n$', 'Blood pressure']

    # Extract values for each parameter
    tau_sys = [results[c]["p_systolic_mmHg"] for c in ["tau_1p0", "tau_1p5", "tau_2p5"]]
    tau_dia = [results[c]["p_diastolic_mmHg"] for c in ["tau_1p0", "tau_1p5", "tau_2p5"]]
    tau_pulse = [results[c]["p_pulse_mmHg"] for c in ["tau_1p0", "tau_1p5", "tau_2p5"]]

    pwv_sys = [results[c]["p_systolic_mmHg"] for c in ["pwv_4p0", "pwv_8p0", "pwv_10p0"]]
    pwv_dia = [results[c]["p_diastolic_mmHg"] for c in ["pwv_4p0", "pwv_8p0", "pwv_10p0"]]
    pwv_pulse = [results[c]["p_pulse_mmHg"] for c in ["pwv_4p0", "pwv_8p0", "pwv_10p0"]]

    murray_sys = [results[c]["p_systolic_mmHg"] for c in ["murray_exponent_2p0", "murray_exponent_2p5"]]
    murray_dia = [results[c]["p_diastolic_mmHg"] for c in ["murray_exponent_2p0", "murray_exponent_2p5"]]

    bp_sys = [results[c]["p_systolic_mmHg"] for c in ["blood_pressure_110_70", "blood_pressure_130_90"]]
    bp_dia = [results[c]["p_diastolic_mmHg"] for c in ["blood_pressure_110_70", "blood_pressure_130_90"]]

    # Sensitivity indices (approximate)
    S_sys = [
        calc_sensitivity(tau_sys, baseline_sys, 0.78),
        calc_sensitivity(pwv_sys, baseline_sys, 1.0),
        calc_sensitivity(murray_sys, baseline_sys, 0.33) if len(murray_sys) > 1 else 0,
        calc_sensitivity(bp_sys, baseline_sys, 0.17),
    ]

    S_dia = [
        calc_sensitivity(tau_dia, baseline_dia, 0.78),
        calc_sensitivity(pwv_dia, baseline_dia, 1.0),
        calc_sensitivity(murray_dia, baseline_dia, 0.33) if len(murray_dia) > 1 else 0,
        calc_sensitivity(bp_dia, baseline_dia, 0.25),
    ]

    x = np.arange(len(params))
    width = 0.35

    rects1 = ax.bar(x - width/2, S_sys, width, label='Systolic', color='#1f77b4')
    rects2 = ax.bar(x + width/2, S_dia, width, label='Diastolic', color='#ff7f0e')

    ax.set_ylabel('Sensitivity index $S_i$')
    ax.set_title('Parameter Sensitivity Indices')
    ax.set_xticks(x)
    ax.set_xticklabels(params)
    ax.legend()
    ax.set_ylim(0, 1.5)
    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5, label='Linear scaling')

    plt.tight_layout()

    # Save
    fig.savefig(OUTPUT_DIR / "sensitivity_indices.png")
    fig.savefig(OUTPUT_DIR / "sensitivity_indices.pdf")
    print(f"Saved: {OUTPUT_DIR / 'sensitivity_indices.png'}")
    plt.close()


def create_summary_table(results: dict):
    """Create summary table for paper."""
    print("\n" + "=" * 80)
    print("SUMMARY TABLE FOR PAPER")
    print("=" * 80)

    baseline = results["baseline"]

    # Organize by parameter
    param_data = {
        "tau": {
            "label": "τ (decay time)",
            "range": "1.0-2.5 s",
            "baseline": "1.92 s",
            "cases": ["tau_1p0", "tau_1p5", "baseline", "tau_2p5"],
        },
        "pwv": {
            "label": "PWV",
            "range": "4-10 m/s",
            "baseline": "6 m/s",
            "cases": ["pwv_4p0", "baseline", "pwv_8p0", "pwv_10p0"],
        },
        "murray": {
            "label": "Murray exponent",
            "range": "2.0-3.0",
            "baseline": "3.0",
            "cases": ["murray_exponent_2p0", "murray_exponent_2p5", "baseline"],
        },
        "bp": {
            "label": "Blood pressure",
            "range": "110/70-130/90",
            "baseline": "120/80 mmHg",
            "cases": ["blood_pressure_110_70", "baseline", "blood_pressure_130_90"],
        },
    }

    print(f"\nBaseline: P_sys={baseline['p_systolic_mmHg']:.1f}, P_dia={baseline['p_diastolic_mmHg']:.1f}, "
          f"P_mean={baseline['p_mean_mmHg']:.1f} mmHg")
    print()

    print(f"{'Parameter':<20} {'Range':<15} {'P_sys range':<20} {'P_dia range':<20}")
    print("-" * 80)

    for key, data in param_data.items():
        sys_vals = [results[c]["p_systolic_mmHg"] for c in data["cases"] if c in results]
        dia_vals = [results[c]["p_diastolic_mmHg"] for c in data["cases"] if c in results]

        sys_range = f"{min(sys_vals):.1f}-{max(sys_vals):.1f}"
        dia_range = f"{min(dia_vals):.1f}-{max(dia_vals):.1f}"

        print(f"{data['label']:<20} {data['range']:<15} {sys_range:<20} {dia_range:<20}")


def main():
    print("Loading results...")
    results = load_results()

    print("\nGenerating figures...")

    create_tornado_plot(results)
    create_pressure_waveform_grid(results)
    create_sensitivity_bar_chart(results)
    create_summary_table(results)

    print(f"\nAll figures saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
