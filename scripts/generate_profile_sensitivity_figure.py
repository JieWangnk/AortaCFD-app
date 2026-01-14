#!/usr/bin/env python3
"""
Generate profile sensitivity comparison figure for AortaCFD paper.
Compares pressure waveforms between standard and accurate profiles.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Set publication-quality parameters
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif']
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 11
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['figure.dpi'] = 300

# Physical constants
RHO = 1060  # kg/m³
PA_TO_MMHG = 1.0 / 133.322
CARDIAC_CYCLE = 0.5  # seconds

# Data from simulation (3 cardiac cycles, t=0.05 to 1.5s)
# Times: 0.05, 0.1, 0.15, ..., 1.5 (30 values - exclude initial t=0)
times_raw = np.arange(0.05, 1.55, 0.05)  # 30 time points

# Standard profile outlet1 pressure (p/rho values) - 30 values
standard_p_raw = np.array([
    10.062, 13.592, 16.919, 15.6312, 13.693, 12.2555, 10.3723, 9.39558, 8.92256, 8.4769,
    8.05581, 13.9201, 17.3646, 15.8724, 13.8941, 12.4287, 10.5187, 9.52396, 9.05463, 8.60617,
    8.1818, 14.0573, 17.485, 15.9922, 14.0136, 12.5339, 10.6151, 9.61969, 9.14849, 8.69609
])

# Accurate profile outlet1 pressure (p/rho values) - 30 values
accurate_p_raw = np.array([
    10.062, 13.5853, 16.9013, 15.6262, 13.691, 12.259, 10.3817, 9.39215, 8.92404, 8.47737,
    8.05537, 13.9125, 17.3627, 15.8681, 13.883, 12.4254, 10.5129, 9.52438, 9.05631, 8.60729,
    8.18254, 14.0516, 17.4985, 15.9871, 14.0028, 12.5312, 10.6117, 9.62045, 9.14804, 8.69497
])

# Convert to mmHg
standard_p_mmhg = standard_p_raw * RHO * PA_TO_MMHG
accurate_p_mmhg = accurate_p_raw * RHO * PA_TO_MMHG

# Extract last cardiac cycle (t=1.0 to 1.5s)
mask_last_cycle = times_raw >= 1.0
times_cycle = (times_raw[mask_last_cycle] - 1.0) * 1000  # ms
standard_cycle = standard_p_mmhg[mask_last_cycle]
accurate_cycle = accurate_p_mmhg[mask_last_cycle]

# Create figure
fig, axes = plt.subplots(1, 2, figsize=(7, 3))

# Panel (a): Pressure waveform comparison
ax1 = axes[0]
ax1.plot(times_cycle, standard_cycle, 'b-', linewidth=1.5, label='Standard')
ax1.plot(times_cycle, accurate_cycle, 'r--', linewidth=1.5, label='Accurate')
ax1.set_xlabel('Time (ms)')
ax1.set_ylabel('Outlet Pressure (mmHg)')
ax1.set_title('(a) Pressure Waveform Comparison')
ax1.legend(loc='upper right')
ax1.set_xlim([0, 500])
ax1.set_ylim([60, 150])
ax1.grid(True, alpha=0.3)

# Panel (b): Difference plot
ax2 = axes[1]
diff = accurate_cycle - standard_cycle
diff_pct = diff / standard_cycle * 100
ax2.plot(times_cycle, diff, 'k-', linewidth=1.5)
ax2.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
ax2.set_xlabel('Time (ms)')
ax2.set_ylabel('Difference (mmHg)')
ax2.set_title('(b) Accurate − Standard')
ax2.set_xlim([0, 500])
ax2.grid(True, alpha=0.3)

# Add statistics annotation
mean_diff = np.mean(diff)
max_diff = np.max(np.abs(diff))
ax2.text(0.95, 0.95, f'Mean: {mean_diff:.3f} mmHg\nMax: {max_diff:.3f} mmHg',
         transform=ax2.transAxes, ha='right', va='top',
         fontsize=8, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

plt.tight_layout()

# Save figure
output_dir = Path('/home/mchi4jw4/GitHub/AortaCFDappPaper/figures')
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'profile_sensitivity_comparison.pdf'
plt.savefig(output_path, bbox_inches='tight', dpi=300)
print(f"Saved: {output_path}")

# Also save as PNG
output_path_png = output_dir / 'profile_sensitivity_comparison.png'
plt.savefig(output_path_png, bbox_inches='tight', dpi=300)
print(f"Saved: {output_path_png}")

plt.close()

# Print statistics
print("\n=== Profile Sensitivity Statistics ===")
print(f"Standard profile:")
print(f"  Mean: {np.mean(standard_cycle):.1f} mmHg")
print(f"  Peak: {np.max(standard_cycle):.1f} mmHg")
print(f"  Min:  {np.min(standard_cycle):.1f} mmHg")
print(f"\nAccurate profile:")
print(f"  Mean: {np.mean(accurate_cycle):.1f} mmHg")
print(f"  Peak: {np.max(accurate_cycle):.1f} mmHg")
print(f"  Min:  {np.min(accurate_cycle):.1f} mmHg")
print(f"\nDifference (accurate - standard):")
print(f"  Mean: {mean_diff:.4f} mmHg ({mean_diff/np.mean(standard_cycle)*100:.4f}%)")
print(f"  Max absolute: {max_diff:.4f} mmHg")
