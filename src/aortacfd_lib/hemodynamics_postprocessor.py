"""
Hemodynamics Post-Processor for AortaCFD
=========================================

Computes clinical hemodynamic metrics from CFD simulation results:
- TAWSS (Time-Averaged Wall Shear Stress)
- OSI (Oscillatory Shear Index)
- RRT (Relative Residence Time)
- Pressure drop (inlet to each outlet)

Supports both:
1. Runtime function object data (from fieldAverage)
2. Post-simulation calculation (postProcess -func wallShearStress)

Author: AortaCFD Team
"""

import os
import re
import csv
import json
import shlex
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

from .constants import PA_TO_MMHG, BLOOD_DENSITY_DEFAULT

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

logger = logging.getLogger(__name__)


@dataclass
class HemodynamicsResults:
    """Container for hemodynamic analysis results."""

    # Inlet type determines which metrics are meaningful
    inlet_type: str = "UNKNOWN"
    is_pulsatile: bool = False
    cardiac_cycle: float = 0.8

    # Steady-state results (always computed)
    wss_max: float = 0.0
    wss_mean: float = 0.0
    wss_min: float = 0.0
    wss_p99: float = 0.0  # 99th percentile (robust descriptor)
    wss_p95: float = 0.0  # 95th percentile

    # Pulsatile-specific results (only for TIMEVARYING/WOMERSLEY)
    tawss_max: float = 0.0
    tawss_mean: float = 0.0
    tawss_p99: float = 0.0  # 99th percentile (robust descriptor)
    tawss_p95: float = 0.0  # 95th percentile
    osi_max: float = 0.0
    osi_mean: float = 0.0
    osi_mean_masked: float = 0.0  # Mean OSI where TAWSS > 0.5 Pa (Les et al. 2010)
    rrt_max: float = 0.0
    rrt_mean: float = 0.0

    # Peak systole information
    peak_systole_time: float = 0.0  # Time of peak inlet flow
    peak_systole_detected: bool = False

    # Flag: True if TAWSS was computed as |<tau>| (magnitude of mean) rather
    # than proper <|tau|> (mean of magnitudes). The approximation can introduce
    # 5-20% error in regions with oscillatory flow.
    tawss_is_approximate: bool = False

    # Per-cycle TAWSS (for convergence checking)
    per_cycle_tawss: List[float] = field(default_factory=list)

    # Pressure drop results
    pressure_inlet: float = 0.0
    pressure_outlets: Dict[str, float] = field(default_factory=dict)
    pressure_drops: Dict[str, float] = field(default_factory=dict)
    pressure_drop_mmhg: Dict[str, float] = field(default_factory=dict)

    # Time series (for plotting)
    time_series: List[float] = field(default_factory=list)
    pressure_inlet_series: List[float] = field(default_factory=list)
    pressure_outlet_series: Dict[str, List[float]] = field(default_factory=dict)


class HemodynamicsPostProcessor:
    """
    Post-processor for hemodynamic metrics computation.

    Usage:
        # From simulation output
        processor = HemodynamicsPostProcessor(case_dir, config)
        results = processor.compute_all()
        processor.generate_report(results, output_dir)

        # Run WSS post-processing if not done during runtime
        processor.run_wss_postprocess()
    """

    def __init__(self, case_dir: str, config: Dict[str, Any]):
        """
        Initialize hemodynamics post-processor.

        Args:
            case_dir: Path to OpenFOAM case directory
            config: Merged configuration dictionary
        """
        self.case_dir = Path(case_dir)
        self.config = config
        self.log = logging.getLogger(self.__class__.__name__)

        # Determine inlet type
        inlet_config = config.get('inlet', {}) or config.get('boundary_conditions', {}).get('inlet', {})
        self.inlet_type = inlet_config.get('type', 'CONSTANT').upper()
        self.is_pulsatile = self.inlet_type in ['TIMEVARYING', 'WOMERSLEY']

        # Get cardiac cycle
        self.cardiac_cycle = config.get('cardiac_cycle', 0.8)

        # Get geometry info
        geom = config.get('geometry', {})
        self.inlet_patch = geom.get('inlet_keywords_ordered', 'inlet')
        outlet_patches = geom.get('outlet_keywords_ordered', ['outlet'])
        if isinstance(outlet_patches, str):
            outlet_patches = [outlet_patches]
        self.outlet_patches = outlet_patches
        self.wall_patch = geom.get('wall_keywords_ordered', 'wall')

        # hemodynamics settings
        hemo_config = config.get('hemodynamics', {})
        tawss_settings = hemo_config.get('tawss_settings', {})
        self.skip_cycles = tawss_settings.get('skip_cycles', 2)

    def run_wss_postprocess(self) -> bool:
        """
        Run OpenFOAM wallShearStress post-processing.

        Use this if WSS was not computed during runtime.
        OpenFOAM 12: foamPostProcess -solver incompressibleFluid -func wallShearStress

        Returns:
            True if successful, False otherwise
        """
        import subprocess

        self.log.info("Running wallShearStress post-processing (OpenFOAM 12)...")

        try:
            # OpenFOAM 12 uses foamPostProcess with solver specification
            # The solver is needed to provide turbulence model context
            # Use shlex.quote to prevent shell injection from case_dir paths
            cmd = f"cd {shlex.quote(str(self.case_dir))} && foamPostProcess -solver incompressibleFluid -func wallShearStress"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                self.log.error(f"foamPostProcess failed: {result.stderr}")
                return False

            self.log.info("wallShearStress post-processing completed")
            return True

        except subprocess.TimeoutExpired:
            self.log.error("foamPostProcess timed out after 5 minutes")
            return False
        except Exception as e:
            self.log.error(f"foamPostProcess failed: {e}")
            return False

    def _detect_peak_systole(self, results: HemodynamicsResults) -> None:
        """
        Detect peak systole time from inlet flowrate data.

        Peak systole is defined as the time of maximum inlet flow rate.
        This is useful for identifying the correct timestep for peak WSS visualization.
        """
        if not self.is_pulsatile:
            return

        # Try to find flowrate.csv in boundaryData
        flowrate_file = None
        boundary_data_dir = self.case_dir / 'constant' / 'boundaryData'
        if boundary_data_dir.exists():
            for inlet_dir in boundary_data_dir.iterdir():
                if 'inlet' in inlet_dir.name.lower():
                    candidate = inlet_dir / 'flowrate.csv'
                    if candidate.exists():
                        flowrate_file = candidate
                        break

        if flowrate_file is None:
            self.log.debug("flowrate.csv not found, peak systole detection skipped")
            return

        try:
            # Read flowrate CSV (format: time, flowrate)
            import csv
            times = []
            flowrates = []
            with open(flowrate_file, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        try:
                            t = float(row[0])
                            q = abs(float(row[1]))  # Use absolute value
                            times.append(t)
                            flowrates.append(q)
                        except ValueError:
                            continue  # Skip header or invalid rows

            if times and flowrates:
                # Find time of maximum flow (within first cardiac cycle)
                times = np.array(times)
                flowrates = np.array(flowrates)
                # Consider only first cardiac cycle for peak detection
                cycle_mask = times <= self.cardiac_cycle
                if np.any(cycle_mask):
                    cycle_times = times[cycle_mask]
                    cycle_flows = flowrates[cycle_mask]
                    peak_idx = np.argmax(cycle_flows)
                    results.peak_systole_time = float(cycle_times[peak_idx])
                    results.peak_systole_detected = True
                    self.log.info(f"Peak systole detected at t = {results.peak_systole_time:.4f} s")

        except Exception as e:
            self.log.warning(f"Failed to detect peak systole: {e}")

    def compute_all(self) -> HemodynamicsResults:
        """
        Compute all hemodynamic metrics.

        Returns:
            HemodynamicsResults with computed metrics
        """
        results = HemodynamicsResults(
            inlet_type=self.inlet_type,
            is_pulsatile=self.is_pulsatile,
            cardiac_cycle=self.cardiac_cycle
        )

        # Detect peak systole from inlet flowrate
        self._detect_peak_systole(results)

        # Always compute pressure drop
        self._compute_pressure_drop(results)

        # Check if WSS data exists
        if not self._check_wss_exists():
            self.log.warning("WSS data not found. Run 'foamPostProcess -solver incompressibleFluid -func wallShearStress' first.")
            return results

        # Compute steady WSS metrics
        self._compute_steady_wss(results)

        # For pulsatile flow, compute TAWSS/OSI/RRT
        if self.is_pulsatile:
            if self._check_fieldaverage_exists():
                self._compute_tawss_osi_rrt(results)
            else:
                self.log.warning(
                    "fieldAverage data not found. TAWSS/OSI/RRT not computed.\n"
                    "Enable hemodynamics.runtime_functions.fieldAverage in config."
                )
        else:
            self.log.info(
                f"Inlet type is {self.inlet_type} (steady). "
                "OSI=0, RRT undefined. Only WSS computed."
            )

        return results

    def _check_wss_exists(self) -> bool:
        """Check if wallShearStress field exists in any time directory."""
        for time_dir in self._get_time_directories():
            wss_file = time_dir / 'wallShearStress'
            if wss_file.exists():
                return True
        return False

    def _check_fieldaverage_exists(self) -> bool:
        """Check if fieldAverage output exists."""
        for time_dir in self._get_time_directories():
            mean_file = time_dir / 'wallShearStressMean'
            if mean_file.exists():
                return True
        return False

    def _get_time_directories(self) -> List[Path]:
        """Get list of time directories sorted by time value."""
        time_dirs = []
        for item in self.case_dir.iterdir():
            if item.is_dir():
                try:
                    time_val = float(item.name)
                    if time_val >= 0:
                        time_dirs.append(item)
                except ValueError:
                    continue
        return sorted(time_dirs, key=lambda p: float(p.name))

    def _get_latest_time(self) -> Optional[Path]:
        """Get the latest time directory."""
        time_dirs = self._get_time_directories()
        return time_dirs[-1] if time_dirs else None

    def _compute_steady_wss(self, results: HemodynamicsResults) -> None:
        """Compute steady-state WSS metrics from latest time step.

        Note: OpenFOAM's wallShearStress function object outputs KINEMATIC WSS
        with dimensions [0 2 -2 0 0 0 0] = m²/s² (τ/ρ).
        We multiply by density to get true WSS in Pa.
        """
        latest = self._get_latest_time()
        if not latest:
            return

        wss_file = latest / 'wallShearStress'
        if not wss_file.exists():
            return

        try:
            wss_data = self._read_vector_field(wss_file)
            if wss_data is not None:
                # OpenFOAM outputs kinematic WSS (m²/s²), multiply by density for Pa
                wss_mag = np.linalg.norm(wss_data, axis=1) * BLOOD_DENSITY_DEFAULT
                results.wss_max = float(np.max(wss_mag))
                results.wss_mean = float(np.mean(wss_mag))
                results.wss_min = float(np.min(wss_mag))
                # Percentile-based descriptors (robust to mesh topology artifacts)
                results.wss_p99 = float(np.percentile(wss_mag, 99))
                results.wss_p95 = float(np.percentile(wss_mag, 95))
                self.log.info(f"WSS: max={results.wss_max:.4f}, p99={results.wss_p99:.4f}, mean={results.wss_mean:.4f} Pa")
        except Exception as e:
            self.log.error(f"Failed to compute WSS: {e}")

    def _compute_tawss_osi_rrt(self, results: HemodynamicsResults) -> None:
        """
        Compute TAWSS, OSI, and RRT from fieldAverage data.

        TAWSS = (1/T) * integral(|WSS|) dt  (computed by fieldAverage)
        OSI = 0.5 * (1 - |mean(WSS)| / mean(|WSS|))
        RRT = 1 / ((1 - 2*OSI) * TAWSS)

        Note: OpenFOAM outputs kinematic WSS (m²/s²), we multiply by density for Pa.
        """
        # Find time directories after skip_cycles
        time_dirs = self._get_time_directories()
        skip_time = self.skip_cycles * self.cardiac_cycle

        valid_dirs = [d for d in time_dirs if float(d.name) >= skip_time]
        if not valid_dirs:
            self.log.warning(f"No time directories after skip_cycles ({skip_time}s)")
            return

        # Get TAWSS from wallShearStressMean
        latest = valid_dirs[-1]
        mean_file = latest / 'wallShearStressMean'

        if not mean_file.exists():
            self.log.warning(f"wallShearStressMean not found at {latest}")
            return

        try:
            # Read mean WSS vector field
            wss_mean_vec = self._read_vector_field(mean_file)
            if wss_mean_vec is None:
                return

            # |<tau>| = magnitude of time-averaged WSS vector (approximate TAWSS).
            # Proper TAWSS = <|tau|> = mean of magnitudes. These differ for oscillatory flow.
            # Multiply by density to convert from kinematic (m²/s²) to dynamic (Pa).
            tawss = np.linalg.norm(wss_mean_vec, axis=1) * BLOOD_DENSITY_DEFAULT

            results.tawss_max = float(np.max(tawss))
            results.tawss_mean = float(np.mean(tawss))
            results.tawss_is_approximate = True
            self.log.warning(
                "TAWSS computed as |<tau>| (magnitude of time-averaged WSS vector). "
                "Proper TAWSS = <|tau|> (mean of magnitudes) requires individual "
                "wallShearStress fields at each time step. Approximation error can "
                "be 5-20%% in regions with oscillatory flow."
            )

            # For OSI, we need the time-averaged magnitude as well
            # OSI = 0.5 * (1 - |mean(WSS)| / TAWSS_proper)
            # If we only have wallShearStressMean, OSI calculation is approximate

            # Compute WSS magnitude at each saved time step and average
            wss_mags = []
            for d in valid_dirs:
                wss_file = d / 'wallShearStress'
                if wss_file.exists():
                    wss_vec = self._read_vector_field(wss_file)
                    if wss_vec is not None:
                        # Multiply by density for Pa
                        wss_mags.append(np.linalg.norm(wss_vec, axis=1) * BLOOD_DENSITY_DEFAULT)

            if wss_mags:
                # Proper TAWSS = time average of magnitudes (already in Pa)
                tawss_proper = np.mean(wss_mags, axis=0)

                # OSI = 0.5 * (1 - |mean(WSS)| / TAWSS)
                # Avoid division by zero
                osi = np.zeros_like(tawss_proper)
                nonzero = tawss_proper > 1e-10
                osi[nonzero] = 0.5 * (1.0 - tawss[nonzero] / tawss_proper[nonzero])
                # OSI is theoretically bounded [0, 0.5]; values outside indicate numerical issues
                clipped_count = int(np.sum((osi < 0) | (osi > 0.5)))
                osi = np.clip(osi, 0, 0.5)
                if clipped_count > 0:
                    total_cells = len(osi)
                    self.log.warning(
                        f"OSI clipped to [0, 0.5] for {clipped_count}/{total_cells} cells "
                        f"({100*clipped_count/total_cells:.1f}%). This may indicate numerical artifacts."
                    )

                results.osi_max = float(np.max(osi))
                results.osi_mean = float(np.mean(osi))
                # Masked OSI mean: only cells with TAWSS > 0.5 Pa (Les et al. 2010)
                # Low TAWSS regions have poor signal-to-noise for OSI calculation
                osi_mask = tawss_proper > 0.5
                results.osi_mean_masked = float(np.mean(osi[osi_mask])) if np.any(osi_mask) else 0.0

                # RRT = 1 / ((1 - 2*OSI) * TAWSS), units are Pa⁻¹
                # Avoid division by zero
                denominator = (1.0 - 2.0 * osi) * tawss_proper
                rrt = np.zeros_like(denominator)
                valid = np.abs(denominator) > 1e-10
                rrt[valid] = 1.0 / denominator[valid]

                results.rrt_max = float(np.max(rrt[valid])) if np.any(valid) else 0.0
                results.rrt_mean = float(np.mean(rrt[valid])) if np.any(valid) else 0.0

                # Update TAWSS with proper calculation (overrides approximate)
                results.tawss_max = float(np.max(tawss_proper))
                results.tawss_mean = float(np.mean(tawss_proper))
                # Percentile-based descriptors (robust to mesh topology artifacts)
                results.tawss_p99 = float(np.percentile(tawss_proper, 99))
                results.tawss_p95 = float(np.percentile(tawss_proper, 95))
                results.tawss_is_approximate = False

                # Per-cycle TAWSS convergence check
                if len(wss_mags) > 1 and self.cardiac_cycle > 0:
                    cycle_groups = {}
                    wss_dir_indices = []
                    idx = 0
                    for d in valid_dirs:
                        wss_file = d / 'wallShearStress'
                        if wss_file.exists():
                            t = float(d.name)
                            cycle_idx = int((t - skip_time) / self.cardiac_cycle)
                            cycle_groups.setdefault(cycle_idx, []).append(idx)
                            idx += 1

                    cycle_tawss_values = []
                    for cycle_idx in sorted(cycle_groups.keys()):
                        indices = cycle_groups[cycle_idx]
                        cycle_mags = [wss_mags[i] for i in indices if i < len(wss_mags)]
                        if cycle_mags:
                            cycle_tawss = float(np.mean([np.mean(m) for m in cycle_mags]))
                            cycle_tawss_values.append(cycle_tawss)

                    results.per_cycle_tawss = cycle_tawss_values
                    if len(cycle_tawss_values) >= 2:
                        mean_val = np.mean(cycle_tawss_values)
                        cv = np.std(cycle_tawss_values) / mean_val if mean_val > 0 else 0
                        self.log.info(f"TAWSS convergence: {len(cycle_tawss_values)} cycles, CV={cv:.4f}")
                        if cv > 0.05:
                            self.log.warning(
                                f"TAWSS inter-cycle CV ({cv:.3f}) exceeds 5%. "
                                "Results may not be fully converged. Consider running more cycles."
                            )

            self.log.info(f"TAWSS: max={results.tawss_max:.4f}, p99={results.tawss_p99:.4f}, mean={results.tawss_mean:.4f} Pa")
            self.log.info(f"OSI: max={results.osi_max:.4f}, mean={results.osi_mean:.4f}, mean_masked={results.osi_mean_masked:.4f}")
            self.log.info(f"RRT: max={results.rrt_max:.4f}, mean={results.rrt_mean:.4f} Pa⁻¹")

            # Save fields for ParaView visualization
            self._save_hemodynamic_fields(latest, tawss_proper, osi, rrt)

        except Exception as e:
            self.log.error(f"Failed to compute TAWSS/OSI/RRT: {e}")
            import traceback
            traceback.print_exc()

    def _save_hemodynamic_fields(self, time_dir: Path, tawss: np.ndarray,
                                  osi: np.ndarray, rrt: np.ndarray) -> None:
        """
        Save TAWSS, OSI, and RRT as OpenFOAM scalar boundary fields for ParaView visualization.

        These are saved as volScalarField files in the time directory with the data
        on the wall boundary patch.
        """
        try:
            # Get wall patch name from geometry config
            wall_keywords = self.config.get('geometry', {}).get('wall_keywords_ordered', 'wall')
            if isinstance(wall_keywords, list):
                wall_patch = wall_keywords[0]
            else:
                wall_patch = wall_keywords

            # Find actual wall patch name in the case
            wall_patch_name = None
            for patch_name in self._get_boundary_patches():
                if wall_patch.lower() in patch_name.lower() or 'wall' in patch_name.lower():
                    wall_patch_name = patch_name
                    break

            if not wall_patch_name:
                self.log.warning("Could not find wall patch for saving fields")
                return

            # Save each field
            fields_to_save = [
                ('TAWSS', tawss, 'Pa'),
                ('OSI', osi, ''),
                ('RRT', rrt, '1/Pa')
            ]

            for field_name, field_data, unit in fields_to_save:
                self._write_scalar_boundary_field(
                    time_dir, field_name, field_data, wall_patch_name, unit
                )

            self.log.info(f"Saved TAWSS, OSI, RRT fields to {time_dir}")

        except Exception as e:
            self.log.warning(f"Could not save hemodynamic fields: {e}")

    def _get_boundary_patches(self) -> list:
        """Get list of boundary patch names from the case."""
        boundary_file = self.case_dir / 'constant' / 'polyMesh' / 'boundary'
        patches = []
        if boundary_file.exists():
            with open(boundary_file, 'r') as f:
                content = f.read()
                # Simple regex to find patch names
                import re
                matches = re.findall(r'^\s*(\w+)\s*\n\s*\{', content, re.MULTILINE)
                patches = [m for m in matches if m not in ['FoamFile', 'boundary']]
        return patches

    def _write_scalar_boundary_field(self, time_dir: Path, field_name: str,
                                      data: np.ndarray, wall_patch: str, unit: str) -> None:
        """Write a scalar field as OpenFOAM boundary field format."""
        output_file = time_dir / field_name

        n_faces = len(data)

        # Format data as OpenFOAM list
        data_str = '\n'.join(f'{v:.8g}' for v in data)

        content = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       volScalarField;
    object      {field_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 0 0 0 0 0 0];

internalField   uniform 0;

boundaryField
{{
    {wall_patch}
    {{
        type            fixedValue;
        value           nonuniform List<scalar>
{n_faces}
(
{data_str}
)
;
    }}

    ".*"
    {{
        type            calculated;
        value           uniform 0;
    }}
}}

// ************************************************************************* //
'''

        with open(output_file, 'w') as f:
            f.write(content)

    def _compute_pressure_drop(self, results: HemodynamicsResults) -> None:
        """
        Compute pressure drop from inlet to each outlet.

        Reads data from postProcessing/*/surfaceFieldValue.dat files.
        """
        postproc_dir = self.case_dir / 'postProcessing'
        if not postproc_dir.exists():
            self.log.warning("postProcessing directory not found")
            return

        # Read inlet pressure
        inlet_data = self._read_surface_field_value(f"{self.inlet_patch}Pressure")
        if inlet_data is not None:
            times, pressures = inlet_data
            results.time_series = times.tolist()
            results.pressure_inlet_series = pressures.tolist()
            results.pressure_inlet = float(np.mean(pressures))

        # Read each outlet pressure
        for outlet in self.outlet_patches:
            outlet_data = self._read_surface_field_value(f"{outlet}Pressure")
            if outlet_data is not None:
                times, pressures = outlet_data
                results.pressure_outlet_series[outlet] = pressures.tolist()
                results.pressure_outlets[outlet] = float(np.mean(pressures))

                # Compute pressure drop
                if results.pressure_inlet > 0:
                    dp = results.pressure_inlet - results.pressure_outlets[outlet]
                    results.pressure_drops[outlet] = dp
                    # Conversion: OpenFOAM kinematic pressure (p/rho, m²/s²)
                    #   × BLOOD_DENSITY_DEFAULT → dynamic pressure (Pa)
                    #   × PA_TO_MMHG → clinical units (mmHg)
                    results.pressure_drop_mmhg[outlet] = dp * BLOOD_DENSITY_DEFAULT * PA_TO_MMHG

        if results.pressure_drops:
            self.log.info("Pressure drops (inlet → outlet):")
            for outlet, dp_mmhg in results.pressure_drop_mmhg.items():
                self.log.info(f"  → {outlet}: {dp_mmhg:.2f} mmHg")

    def _read_surface_field_value(self, func_name: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Read surfaceFieldValue.dat from postProcessing."""
        postproc_dir = self.case_dir / 'postProcessing' / func_name
        if not postproc_dir.exists():
            return None

        # Find the data file (could be in '0/' or another time subdirectory)
        data_file = None
        for subdir in postproc_dir.iterdir():
            candidate = subdir / 'surfaceFieldValue.dat'
            if candidate.exists():
                data_file = candidate
                break

        if data_file is None:
            return None

        try:
            # Parse the OpenFOAM data file
            times = []
            values = []
            with open(data_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        times.append(float(parts[0]))
                        values.append(float(parts[1]))

            return np.array(times), np.array(values)
        except Exception as e:
            self.log.warning(f"Failed to read {data_file}: {e}")
            return None

    def _read_vector_field(self, filepath: Path) -> Optional[np.ndarray]:
        """
        Read OpenFOAM vector field file (ASCII or binary format).

        Returns numpy array of shape (N, 3) where N is number of cells/faces.
        Only reads wall patch data (not internalField).
        """
        if not filepath.exists():
            return None

        try:
            # Read file in binary mode to handle both formats
            with open(filepath, 'rb') as f:
                raw_content = f.read()

            # Check if binary format
            is_binary = b'format      binary' in raw_content[:500]

            if is_binary:
                return self._read_binary_vector_field(filepath, raw_content)
            else:
                return self._read_ascii_vector_field(filepath, raw_content.decode('utf-8', errors='ignore'))

        except Exception as e:
            self.log.warning(f"Failed to read vector field {filepath}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _read_ascii_vector_field(self, filepath: Path, content: str) -> Optional[np.ndarray]:
        """Read ASCII format OpenFOAM vector field."""
        # Find the data section between parentheses
        # Format: N\n(\n(x y z)\n(x y z)\n...\n)
        match = re.search(r'(\d+)\s*\(\s*\(([\s\S]*?)\)\s*\)', content)
        if not match:
            return None

        n_elements = int(match.group(1))
        data_str = match.group(2)

        # Parse vector data
        vectors = []
        for line in data_str.split(')'):
            line = line.strip().lstrip('(')
            if line:
                parts = line.split()
                if len(parts) >= 3:
                    vectors.append([float(parts[0]), float(parts[1]), float(parts[2])])

        if len(vectors) != n_elements:
            self.log.warning(f"Expected {n_elements} vectors, got {len(vectors)}")

        return np.array(vectors) if vectors else None

    def _read_binary_vector_field(self, filepath: Path, raw_content: bytes) -> Optional[np.ndarray]:
        """
        Read binary format OpenFOAM vector field from wall boundary.

        For wallShearStress, we need the data from the wall patch boundary,
        not the internalField (which is uniform zero for WSS).
        """
        import struct

        content_str = raw_content.decode('utf-8', errors='replace')

        # Find wall patch in boundaryField - look for 'wall' keyword
        # The pattern matches: patchName { type calculated; value nonuniform List<vector> N (...binary data...)
        # Patterns: wall_aorta, wallAorta, aortaWall, aorta_wall, wall, etc.
        wall_patches = []
        for patch_match in re.finditer(r'(\w*wall\w*)\s*\{', content_str, re.IGNORECASE):
            wall_patches.append(patch_match.group(1))

        if not wall_patches:
            self.log.warning(f"No wall patch found in {filepath}")
            return None

        # Find the wall patch data
        # Pattern: wall_name\n    {\n        type ...; value nonuniform List<vector> N
        for wall_patch in wall_patches:
            # Find this patch in boundaryField
            pattern = rf'{re.escape(wall_patch)}\s*\{{\s*type\s+\w+;\s*value\s+nonuniform\s+List<vector>\s*\n\s*(\d+)'
            match = re.search(pattern, content_str)

            if match:
                n_elements = int(match.group(1))
                self.log.info(f"Reading {n_elements} vectors from wall patch '{wall_patch}'")

                # Find the position of the count in binary content
                count_pos = raw_content.find(f'\n{n_elements}\n'.encode())
                if count_pos == -1:
                    # Try alternative format
                    count_str = f'{n_elements}'
                    count_pos = content_str.find(match.group(1))

                if count_pos == -1:
                    continue

                # Binary data starts after "N\n("
                # Find the opening parenthesis after the count
                search_start = count_pos + len(str(n_elements))
                paren_pos = raw_content.find(b'(', search_start)

                if paren_pos == -1:
                    continue

                # Read binary doubles (3 per vector)
                data_start = paren_pos + 1
                bytes_needed = n_elements * 3 * 8  # 3 doubles per vector, 8 bytes per double

                if data_start + bytes_needed > len(raw_content):
                    self.log.warning(f"Not enough binary data: need {bytes_needed}, have {len(raw_content) - data_start}")
                    continue

                binary_data = raw_content[data_start:data_start + bytes_needed]

                try:
                    # Unpack as little-endian doubles
                    values = struct.unpack(f'<{n_elements * 3}d', binary_data)
                    vectors = np.array(values).reshape(-1, 3)
                    return vectors
                except struct.error as e:
                    self.log.warning(f"Failed to unpack binary data: {e}")
                    continue

        self.log.warning(f"Could not parse binary vector field from {filepath}")
        return None

    def generate_report(self, results: HemodynamicsResults, output_dir: str) -> str:
        """
        Generate hemodynamics report.

        Args:
            results: Computed hemodynamics results
            output_dir: Directory for output files

        Returns:
            Path to generated report file
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        report_file = output_path / 'hemodynamics_report.txt'

        with open(report_file, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("HEMODYNAMICS ANALYSIS REPORT\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"Inlet Type: {results.inlet_type}\n")
            f.write(f"Flow Type: {'Pulsatile' if results.is_pulsatile else 'Steady'}\n")
            if results.is_pulsatile:
                f.write(f"Cardiac Cycle: {results.cardiac_cycle:.3f} s\n")
            if results.peak_systole_detected:
                f.write(f"Peak Systole: t = {results.peak_systole_time:.4f} s\n")
            f.write("\n")

            f.write("-" * 70 + "\n")
            f.write("WALL SHEAR STRESS (WSS) - Peak Systole\n")
            f.write("-" * 70 + "\n")
            f.write(f"  Maximum:        {results.wss_max:.4f} Pa\n")
            f.write(f"  99th Percentile:{results.wss_p99:.4f} Pa  (robust descriptor)\n")
            f.write(f"  95th Percentile:{results.wss_p95:.4f} Pa\n")
            f.write(f"  Mean:           {results.wss_mean:.4f} Pa\n")
            f.write(f"  Minimum:        {results.wss_min:.4f} Pa\n")
            f.write("\n")

            if results.is_pulsatile and results.tawss_mean > 0:
                f.write("-" * 70 + "\n")
                f.write("TIME-AVERAGED METRICS (Pulsatile Flow)\n")
                f.write("-" * 70 + "\n")
                f.write(f"  TAWSS Maximum:        {results.tawss_max:.4f} Pa\n")
                f.write(f"  TAWSS 99th Percentile:{results.tawss_p99:.4f} Pa  (robust descriptor)\n")
                f.write(f"  TAWSS 95th Percentile:{results.tawss_p95:.4f} Pa\n")
                f.write(f"  TAWSS Mean:           {results.tawss_mean:.4f} Pa\n")
                f.write("\n")
                f.write(f"  OSI Maximum:          {results.osi_max:.4f}\n")
                f.write(f"  OSI Mean:             {results.osi_mean:.4f}\n")
                f.write(f"  OSI Mean (masked):    {results.osi_mean_masked:.4f}  (where TAWSS > 0.5 Pa)\n")
                f.write("\n")
                f.write(f"  RRT Maximum:          {results.rrt_max:.4f} Pa⁻¹\n")
                f.write(f"  RRT Mean:             {results.rrt_mean:.4f} Pa⁻¹\n")
                f.write("\n")
                f.write("  Clinical thresholds:\n")
                f.write("    Low TAWSS (<0.4 Pa): Atherogenic phenotype risk\n")
                f.write("    High TAWSS (>40 Pa): Endothelial injury risk\n")
                f.write("    High OSI (>0.3): Oscillatory flow, thrombus risk\n")
                f.write("    High RRT (>10 Pa⁻¹): Particle trapping risk\n")
                f.write("\n")
            elif not results.is_pulsatile:
                f.write("-" * 70 + "\n")
                f.write("PULSATILE METRICS (Not Applicable)\n")
                f.write("-" * 70 + "\n")
                f.write("  OSI = 0 (no flow oscillation with steady inlet)\n")
                f.write("  RRT = undefined (requires OSI)\n")
                f.write("\n")

            f.write("-" * 70 + "\n")
            f.write("PRESSURE DROP (Inlet → Outlets)\n")
            f.write("-" * 70 + "\n")
            if results.pressure_drops:
                # Convert kinematic pressure (m²/s²) → Pa → mmHg
                f.write(f"  Inlet pressure: {results.pressure_inlet * BLOOD_DENSITY_DEFAULT * PA_TO_MMHG:.2f} mmHg\n")
                f.write("\n")
                for outlet in self.outlet_patches:
                    if outlet in results.pressure_drop_mmhg:
                        dp = results.pressure_drop_mmhg[outlet]
                        # Convert kinematic pressure (m²/s²) → Pa → mmHg
                        p_out = results.pressure_outlets.get(outlet, 0) * BLOOD_DENSITY_DEFAULT * PA_TO_MMHG
                        f.write(f"  → {outlet}:\n")
                        f.write(f"      Outlet pressure: {p_out:.2f} mmHg\n")
                        f.write(f"      Pressure drop:   {dp:.2f} mmHg\n")
                f.write("\n")
                f.write("  Clinical significance:\n")
                f.write("    ΔP > 20 mmHg at rest: Significant coarctation\n")
            else:
                f.write("  (No pressure data available)\n")

            # QoI Summary section for verification studies
            f.write("\n" + "-" * 70 + "\n")
            f.write("QUANTITIES OF INTEREST (QoI) SUMMARY\n")
            f.write("-" * 70 + "\n")
            f.write("  Verification-oriented metrics using robust percentile descriptors:\n\n")

            # Pressure QoI
            if results.pressure_drop_mmhg:
                mean_dp = sum(results.pressure_drop_mmhg.values()) / len(results.pressure_drop_mmhg)
                f.write(f"  QoI-1: Pressure Drop (mean)     = {mean_dp:.2f} mmHg\n")

            # WSS QoIs
            f.write(f"  QoI-2: TAWSS p99                = {results.tawss_p99:.2f} Pa\n")
            f.write(f"  QoI-3: WSS p99 (peak systole)   = {results.wss_p99:.2f} Pa\n")
            f.write(f"  QoI-4: OSI mean (masked)        = {results.osi_mean_masked:.4f}\n")

            f.write("\n  Note: p99 = 99th percentile (robust to mesh topology artifacts)\n")
            f.write("        masked = TAWSS > 0.5 Pa (filters low-shear noise, Les et al. 2010)\n")

            f.write("\n" + "=" * 70 + "\n")

        self.log.info(f"Hemodynamics report saved to: {report_file}")

        # Generate pressure drop plot if matplotlib available
        if HAS_MATPLOTLIB and results.time_series:
            self._generate_pressure_plot(results, output_path)

        return str(report_file)

    def _generate_pressure_plot(self, results: HemodynamicsResults, output_dir: Path) -> None:
        """Generate pressure drop time-series plot."""
        if not results.time_series:
            return

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

        times = np.array(results.time_series)

        # Convert to mmHg
        p_inlet_mmhg = np.array(results.pressure_inlet_series) * PA_TO_MMHG * BLOOD_DENSITY_DEFAULT

        # Top plot: Absolute pressures
        ax1.plot(times, p_inlet_mmhg, 'b-', linewidth=2, label='Inlet', zorder=10)

        # Use distinct colors and line styles for outlets to show overlapping lines
        colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00']  # Colorblind-friendly
        linestyles = ['-', '--', '-.', ':', (0, (3, 1, 1, 1))]
        markers = ['o', 's', '^', 'D', 'v']

        for i, outlet in enumerate(self.outlet_patches):
            if outlet in results.pressure_outlet_series:
                p_out = np.array(results.pressure_outlet_series[outlet]) * PA_TO_MMHG * BLOOD_DENSITY_DEFAULT
                # Use different line styles and sample markers to show overlapping lines
                color = colors[i % len(colors)]
                ls = linestyles[i % len(linestyles)]
                marker = markers[i % len(markers)]
                # Plot with markers at sparse intervals to show distinct lines
                marker_every = max(1, len(times) // 20)
                ax1.plot(times, p_out, color=color, linestyle=ls, linewidth=1.5,
                        marker=marker, markevery=marker_every, markersize=4,
                        label=outlet, alpha=0.8)

        ax1.set_ylabel('Pressure (mmHg)')
        ax1.set_title('Patch-Averaged Pressure Over Time')
        ax1.legend(loc='upper right', fontsize=9, ncol=2)
        ax1.grid(True, alpha=0.3)

        # Bottom plot: Pressure drops
        for i, outlet in enumerate(self.outlet_patches):
            if outlet in results.pressure_outlet_series:
                p_out = np.array(results.pressure_outlet_series[outlet]) * PA_TO_MMHG * BLOOD_DENSITY_DEFAULT
                dp = p_inlet_mmhg - p_out
                color = colors[i % len(colors)]
                ls = linestyles[i % len(linestyles)]
                marker = markers[i % len(markers)]
                marker_every = max(1, len(times) // 20)
                ax2.plot(times, dp, color=color, linestyle=ls, linewidth=1.5,
                        marker=marker, markevery=marker_every, markersize=4,
                        label=f'Inlet → {outlet}', alpha=0.8)

        ax2.axhline(y=20, color='red', linestyle='--', linewidth=2, alpha=0.7,
                   label='Clinical threshold (20 mmHg)')
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Pressure Drop (mmHg)')
        ax2.set_title('Pressure Drop: Inlet to Each Outlet')
        ax2.legend(loc='upper right', fontsize=9, ncol=2)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        plot_path = output_dir / 'pressure_drop_timeseries.png'
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        plt.close()

        self.log.info(f"Pressure plot saved to: {plot_path}")

    def export_qoi(self, results: HemodynamicsResults, output_dir: str) -> Tuple[str, str]:
        """
        Export QoI (Quantities of Interest) to JSON and CSV formats.

        This provides machine-readable outputs for verification studies and
        automated analysis pipelines. The QoIs are defined following cardiovascular
        CFD verification best practices (percentile-based, cycle-averaged).

        Args:
            results: Computed hemodynamics results
            output_dir: Directory for output files

        Returns:
            Tuple of (json_path, csv_path)
        """
        output_path = Path(output_dir)
        results_dir = output_path / 'results'
        results_dir.mkdir(parents=True, exist_ok=True)

        # Build QoI dictionary with definitions
        patient_id = self.config.get('case_info', {}).get('patient_id', '')
        qoi_data = {
            "_metadata": {
                "description": "Hemodynamic Quantities of Interest for CFD verification",
                "patient_id": patient_id,
                "case_dir": str(self.case_dir),
                "inlet_type": results.inlet_type,
                "is_pulsatile": results.is_pulsatile,
                "cardiac_cycle_s": results.cardiac_cycle,
                "peak_systole_time_s": results.peak_systole_time if results.peak_systole_detected else None,
            },
            "qoi": {
                "pressure_drop_mean_mmhg": {
                    "value": float(np.mean(list(results.pressure_drop_mmhg.values()))) if results.pressure_drop_mmhg else 0.0,
                    "unit": "mmHg",
                    "definition": "Cycle-averaged pressure drop (inlet to outlets mean)",
                },
                "wss_p99_pa": {
                    "value": results.wss_p99,
                    "unit": "Pa",
                    "definition": "99th percentile peak systolic wall shear stress",
                },
                "wss_p95_pa": {
                    "value": results.wss_p95,
                    "unit": "Pa",
                    "definition": "95th percentile peak systolic wall shear stress",
                },
                "tawss_p99_pa": {
                    "value": results.tawss_p99,
                    "unit": "Pa",
                    "definition": "99th percentile time-averaged wall shear stress",
                },
                "tawss_p95_pa": {
                    "value": results.tawss_p95,
                    "unit": "Pa",
                    "definition": "95th percentile time-averaged wall shear stress",
                },
                "tawss_mean_pa": {
                    "value": results.tawss_mean,
                    "unit": "Pa",
                    "definition": "Mean time-averaged wall shear stress",
                },
                "osi_mean": {
                    "value": results.osi_mean,
                    "unit": "-",
                    "definition": "Mean oscillatory shear index (all cells)",
                },
                "osi_mean_masked": {
                    "value": results.osi_mean_masked,
                    "unit": "-",
                    "definition": "Mean OSI where TAWSS > 0.5 Pa (Les et al. 2010)",
                },
            },
            "per_outlet_pressure_drop_mmhg": results.pressure_drop_mmhg,
        }

        # Write JSON
        json_path = results_dir / 'qoi_summary.json'
        with open(json_path, 'w') as f:
            json.dump(qoi_data, f, indent=2)

        # Write CSV (flat format for easy import to spreadsheets/scripts)
        csv_path = results_dir / 'qoi_summary.csv'
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['metric', 'value', 'unit', 'definition'])
            for key, data in qoi_data['qoi'].items():
                writer.writerow([key, data['value'], data['unit'], data['definition']])
            # Add per-outlet pressure drops
            for outlet, dp in results.pressure_drop_mmhg.items():
                writer.writerow([f'pressure_drop_{outlet}_mmhg', dp, 'mmHg', f'Pressure drop to {outlet}'])

        self.log.info(f"QoI exported to: {json_path}, {csv_path}")
        return str(json_path), str(csv_path)


def run_hemodynamics_analysis(case_dir: str, config: Dict[str, Any], output_dir: str) -> HemodynamicsResults:
    """
    Convenience function to run complete hemodynamics analysis.

    Args:
        case_dir: Path to OpenFOAM case directory
        config: Merged configuration dictionary
        output_dir: Directory for output files

    Returns:
        HemodynamicsResults with all computed metrics
    """
    processor = HemodynamicsPostProcessor(case_dir, config)

    # Check if WSS exists, run postProcess if not
    if not processor._check_wss_exists():
        logger.info("WSS not found in time directories, running postProcess...")
        processor.run_wss_postprocess()

    # Compute all metrics
    results = processor.compute_all()

    # Generate report
    processor.generate_report(results, output_dir)

    # Export QoI to JSON/CSV
    processor.export_qoi(results, output_dir)

    return results


if __name__ == "__main__":
    """Command-line interface for hemodynamics post-processing."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="AortaCFD Hemodynamics Post-Processor")
    parser.add_argument("case_dir", help="Path to OpenFOAM case directory")
    parser.add_argument("--config", "-c", help="Path to config JSON file")
    parser.add_argument("--output", "-o", default=".", help="Output directory for reports")
    parser.add_argument("--run-wss", action="store_true", help="Force run postProcess -func wallShearStress")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Load config
    config = {}
    if args.config and os.path.exists(args.config):
        with open(args.config) as f:
            config = json.load(f)

    # Create processor
    processor = HemodynamicsPostProcessor(args.case_dir, config)

    # Optionally run WSS post-processing
    if args.run_wss:
        processor.run_wss_postprocess()

    # Compute and report
    results = processor.compute_all()
    processor.generate_report(results, args.output)

    print("\nHemodynamics analysis complete!")
