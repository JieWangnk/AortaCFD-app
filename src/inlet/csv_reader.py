# src/inlet/csv_reader.py
"""
CSV flow waveform reader and interpolator.

Handles reading flow rate or velocity data from CSV files
and interpolating to simulation timesteps.

Supported CSV formats:
- Two columns: time, value
- With or without header
- Comma or semicolon delimited
- Values can be flow rate (L/min, mL/s) or velocity (m/s)

Usage:
    from src.inlet.csv_reader import read_flow_csv, interpolate_flow

    # Read CSV file
    flow_data = read_flow_csv('flow.csv', data_type='flow_rate')

    # Interpolate to specific time
    value = interpolate_flow(flow_data, t=0.5)
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union
import logging
import os

logger = logging.getLogger(__name__)


@dataclass
class FlowData:
    """
    Container for flow waveform data.

    Attributes:
        times: Time values (s)
        values: Flow rate (m³/s) or velocity (m/s)
        data_type: 'flow_rate' or 'velocity'
        cardiac_cycle: Duration of one cardiac cycle (s)
        source_file: Original CSV file path
    """
    times: np.ndarray
    values: np.ndarray
    data_type: str
    cardiac_cycle: float
    source_file: Optional[str] = None

    @property
    def n_points(self) -> int:
        """Number of data points."""
        return len(self.times)

    @property
    def mean_value(self) -> float:
        """Time-averaged value."""
        return np.trapz(self.values, self.times) / self.cardiac_cycle

    @property
    def peak_value(self) -> float:
        """Peak (maximum) value."""
        return np.max(self.values)

    @property
    def min_value(self) -> float:
        """Minimum value."""
        return np.min(self.values)


def read_flow_csv(
    csv_path: str,
    data_type: str = 'flow_rate',
    time_unit: str = 's',
    value_unit: Optional[str] = None,
) -> FlowData:
    """
    Read flow waveform from CSV file.

    Args:
        csv_path: Path to CSV file
        data_type: Type of data ('flow_rate' or 'velocity')
        time_unit: Time unit in file ('s', 'ms')
        value_unit: Value unit ('L/min', 'mL/s', 'm3/s', 'm/s')
                   If None, auto-detected based on data_type

    Returns:
        FlowData object

    Raises:
        FileNotFoundError: If CSV file not found
        ValueError: If CSV format is invalid
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    logger.info(f"Reading flow CSV: {csv_path}")

    # Read CSV with flexible parsing
    times, values = _parse_csv_file(csv_path)

    # Convert time units
    if time_unit == 'ms':
        times = times / 1000.0

    # Determine cardiac cycle
    cardiac_cycle = times[-1] - times[0]
    if cardiac_cycle <= 0:
        raise ValueError("Invalid time range in CSV (must be increasing)")

    # Convert value units
    values = _convert_units(values, data_type, value_unit)

    logger.info(
        f"Loaded {len(times)} points, cardiac_cycle={cardiac_cycle:.4f}s, "
        f"mean={np.mean(values):.4e}, peak={np.max(values):.4e}"
    )

    return FlowData(
        times=times,
        values=values,
        data_type=data_type,
        cardiac_cycle=cardiac_cycle,
        source_file=csv_path,
    )


def _parse_csv_file(csv_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Parse CSV file with flexible format handling.

    Handles:
    - Comma or semicolon delimiters
    - With or without header
    - Whitespace variations

    Args:
        csv_path: Path to CSV file

    Returns:
        Tuple of (times, values) arrays
    """
    # Try different delimiters
    for delimiter in [',', ';', '\t', ' ']:
        try:
            data = np.genfromtxt(
                csv_path,
                delimiter=delimiter,
                skip_header=0,
                invalid_raise=False,
            )

            # Check if first row is header (contains NaN)
            if np.any(np.isnan(data[0])):
                data = data[1:]

            # Should have 2 columns
            if data.ndim == 2 and data.shape[1] >= 2:
                times = data[:, 0]
                values = data[:, 1]

                # Validate
                if not np.any(np.isnan(times)) and not np.any(np.isnan(values)):
                    return times, values

        except Exception:
            continue

    # If all delimiters fail, try pandas-like approach
    try:
        with open(csv_path, 'r') as f:
            lines = f.readlines()

        times = []
        values = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Try to parse as two numbers
            parts = line.replace(';', ',').replace('\t', ',').split(',')
            try:
                t = float(parts[0].strip())
                v = float(parts[1].strip())
                times.append(t)
                values.append(v)
            except (ValueError, IndexError):
                continue

        if times:
            return np.array(times), np.array(values)

    except Exception as e:
        logger.error(f"Failed to parse CSV: {e}")

    raise ValueError(f"Could not parse CSV file: {csv_path}")


def _convert_units(
    values: np.ndarray,
    data_type: str,
    value_unit: Optional[str],
) -> np.ndarray:
    """
    Convert values to SI units (m³/s for flow, m/s for velocity).

    Args:
        values: Raw values from CSV
        data_type: 'flow_rate' or 'velocity'
        value_unit: Unit string or None for auto-detection

    Returns:
        Values in SI units
    """
    if value_unit is None:
        # Auto-detect based on typical ranges
        if data_type == 'flow_rate':
            # Typical cardiac output: 4-8 L/min
            # If max > 100, probably mL/s; if < 100, probably L/min
            if np.max(values) > 100:
                value_unit = 'mL/s'
            else:
                value_unit = 'L/min'
        else:
            # Velocity: typically 0.1-2 m/s
            value_unit = 'm/s'

        logger.debug(f"Auto-detected unit: {value_unit}")

    # Apply conversion
    if value_unit == 'L/min':
        # L/min -> m³/s
        return values / 60000.0
    elif value_unit == 'mL/s':
        # mL/s -> m³/s
        return values * 1e-6
    elif value_unit == 'm3/s' or value_unit == 'm³/s':
        return values
    elif value_unit == 'm/s':
        return values
    elif value_unit == 'cm/s':
        return values / 100.0
    else:
        logger.warning(f"Unknown unit '{value_unit}', assuming SI")
        return values


def interpolate_flow(
    flow_data: FlowData,
    time: float,
    method: str = 'linear',
) -> float:
    """
    Interpolate flow value at a specific time.

    Handles cyclic interpolation (wraps around cardiac cycle).

    Args:
        flow_data: FlowData object
        time: Time to interpolate at (s)
        method: Interpolation method ('linear', 'cubic')

    Returns:
        Interpolated value
    """
    # Wrap time to cardiac cycle
    t_wrapped = time % flow_data.cardiac_cycle

    # Adjust if needed (handle edge case at end of cycle)
    if t_wrapped > flow_data.times[-1]:
        t_wrapped = flow_data.times[-1]

    if method == 'linear':
        return np.interp(t_wrapped, flow_data.times, flow_data.values)

    elif method == 'cubic':
        from scipy.interpolate import CubicSpline
        cs = CubicSpline(flow_data.times, flow_data.values, bc_type='periodic')
        return float(cs(t_wrapped))

    else:
        raise ValueError(f"Unknown interpolation method: {method}")


def interpolate_flow_array(
    flow_data: FlowData,
    times: np.ndarray,
    method: str = 'linear',
) -> np.ndarray:
    """
    Interpolate flow values at multiple times.

    Args:
        flow_data: FlowData object
        times: Array of times to interpolate at
        method: Interpolation method

    Returns:
        Array of interpolated values
    """
    return np.array([
        interpolate_flow(flow_data, t, method)
        for t in times
    ])


def generate_timesteps(
    flow_data: FlowData,
    dt: Optional[float] = None,
    n_steps: Optional[int] = None,
) -> np.ndarray:
    """
    Generate uniform timesteps for a cardiac cycle.

    Args:
        flow_data: FlowData object
        dt: Time step size (s)
        n_steps: Number of steps (alternative to dt)

    Returns:
        Array of times
    """
    if dt is not None:
        n_steps = int(np.ceil(flow_data.cardiac_cycle / dt))
    elif n_steps is None:
        # Default: same resolution as input
        n_steps = len(flow_data.times)

    return np.linspace(0, flow_data.cardiac_cycle, n_steps, endpoint=False)


def flow_to_velocity(
    flow_rate: float,
    area: float,
) -> float:
    """
    Convert volumetric flow rate to mean velocity.

    Args:
        flow_rate: Volumetric flow rate (m³/s)
        area: Cross-sectional area (m²)

    Returns:
        Mean velocity (m/s)
    """
    if area <= 0:
        raise ValueError("Area must be positive")
    return flow_rate / area


def velocity_to_flow(
    velocity: float,
    area: float,
) -> float:
    """
    Convert mean velocity to volumetric flow rate.

    Args:
        velocity: Mean velocity (m/s)
        area: Cross-sectional area (m²)

    Returns:
        Volumetric flow rate (m³/s)
    """
    return velocity * area
