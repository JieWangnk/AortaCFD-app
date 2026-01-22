#!/usr/bin/env python3
"""
Generate combined comparison figures for AortaCFD paper.
Creates multi-panel figures combining individual screenshots.
"""

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from pathlib import Path
import numpy as np

# Directories
PAPER_FIG_DIR = Path("/home/mchi4jw4/GitHub/AortaCFDappPaper/figures")


def create_tawss_comparison_figure():
    """Create combined TAWSS comparison figure for profile sensitivity."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    cases = [
        ("profile_robust", "Robust (1st order)"),
        ("profile_standard", "Standard (2nd order TVD)"),
        ("profile_accurate", "Accurate (linearUpwind)"),
    ]

    for ax, (case_name, label) in zip(axes, cases):
        img_path = PAPER_FIG_DIR / "NumericsProfileSensitivity" / f"{case_name}_TAWSS_t_1.5.png"
        if img_path.exists():
            img = mpimg.imread(str(img_path))
            ax.imshow(img)
            ax.set_title(label, fontsize=12, fontweight='bold')
        ax.axis('off')

    plt.tight_layout()
    output_file = PAPER_FIG_DIR / "profile_sensitivity" / "profile_sensitivity_TAWSS_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(output_file.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
    print(f"Saved: {output_file}")
    plt.close()


def create_physics_model_tawss_comparison():
    """Create combined TAWSS comparison figure for physics models."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    cases = [
        ("laminar", "Laminar"),
        ("rans", "RANS k-ω SST"),
        ("les", "LES Smagorinsky"),
    ]

    for ax, (case_name, label) in zip(axes, cases):
        img_path = PAPER_FIG_DIR / "PhysicsModelComparison" / f"{case_name}_TAWSS_t_1.5.png"
        if img_path.exists():
            img = mpimg.imread(str(img_path))
            ax.imshow(img)
            ax.set_title(label, fontsize=12, fontweight='bold')
        ax.axis('off')

    plt.tight_layout()
    output_file = PAPER_FIG_DIR / "physics_model" / "physics_model_TAWSS_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(output_file.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
    print(f"Saved: {output_file}")
    plt.close()


def create_velocity_comparison_figure():
    """Create combined velocity streamline comparison figure."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))

    # Profile sensitivity (top row)
    profile_cases = [
        ("profile_robust", "Robust"),
        ("profile_standard", "Standard"),
        ("profile_accurate", "Accurate"),
    ]

    for ax, (case_name, label) in zip(axes[0], profile_cases):
        img_path = PAPER_FIG_DIR / "NumericsProfileSensitivity" / f"{case_name}_VelocityStreamline_t_1.1.png"
        if img_path.exists():
            img = mpimg.imread(str(img_path))
            ax.imshow(img)
            ax.set_title(f"Profile: {label}", fontsize=11, fontweight='bold')
        ax.axis('off')

    # Physics models (bottom row)
    physics_cases = [
        ("laminar", "Laminar"),
        ("rans", "RANS"),
        ("les", "LES"),
    ]

    for ax, (case_name, label) in zip(axes[1], physics_cases):
        img_path = PAPER_FIG_DIR / "PhysicsModelComparison" / f"{case_name}_VelocityStreamline_t_1.1.png"
        if img_path.exists():
            img = mpimg.imread(str(img_path))
            ax.imshow(img)
            ax.set_title(f"Physics: {label}", fontsize=11, fontweight='bold')
        ax.axis('off')

    # Add row labels
    fig.text(0.02, 0.75, 'Numerics\nProfile', ha='center', va='center',
             fontsize=12, fontweight='bold', rotation=90)
    fig.text(0.02, 0.25, 'Physics\nModel', ha='center', va='center',
             fontsize=12, fontweight='bold', rotation=90)

    plt.tight_layout(rect=[0.03, 0, 1, 1])
    output_file = PAPER_FIG_DIR / "combined_velocity_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(output_file.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
    print(f"Saved: {output_file}")
    plt.close()


def create_all_tawss_comparison():
    """Create a 2x3 combined TAWSS figure for both studies."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))

    # Profile sensitivity (top row)
    profile_cases = [
        ("profile_robust", "Robust (1st order)"),
        ("profile_standard", "Standard (TVD)"),
        ("profile_accurate", "Accurate (linearUpwind)"),
    ]

    for ax, (case_name, label) in zip(axes[0], profile_cases):
        img_path = PAPER_FIG_DIR / "NumericsProfileSensitivity" / f"{case_name}_TAWSS_t_1.5.png"
        if img_path.exists():
            img = mpimg.imread(str(img_path))
            ax.imshow(img)
            ax.set_title(label, fontsize=11, fontweight='bold')
        ax.axis('off')

    # Physics models (bottom row)
    physics_cases = [
        ("laminar", "Laminar"),
        ("rans", "RANS k-ω SST"),
        ("les", "LES Smagorinsky"),
    ]

    for ax, (case_name, label) in zip(axes[1], physics_cases):
        img_path = PAPER_FIG_DIR / "PhysicsModelComparison" / f"{case_name}_TAWSS_t_1.5.png"
        if img_path.exists():
            img = mpimg.imread(str(img_path))
            ax.imshow(img)
            ax.set_title(label, fontsize=11, fontweight='bold')
        ax.axis('off')

    # Add row labels
    fig.text(0.02, 0.75, 'Numerics\nSensitivity', ha='center', va='center',
             fontsize=12, fontweight='bold', rotation=90)
    fig.text(0.02, 0.25, 'Physics\nModel', ha='center', va='center',
             fontsize=12, fontweight='bold', rotation=90)

    plt.tight_layout(rect=[0.03, 0, 1, 1])
    output_file = PAPER_FIG_DIR / "combined_TAWSS_all_studies.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(output_file.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
    print(f"Saved: {output_file}")
    plt.close()


def main():
    """Generate all comparison figures."""
    print("Generating comparison figures...")
    print("=" * 50)

    create_tawss_comparison_figure()
    create_physics_model_tawss_comparison()
    create_velocity_comparison_figure()
    create_all_tawss_comparison()

    print("\n" + "=" * 50)
    print("All comparison figures generated!")


if __name__ == "__main__":
    main()
