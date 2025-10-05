"""
Field Statistics Extractor

Extracts velocity, pressure, and other field statistics from OpenFOAM log files
and creates simple function objects for post-processing.
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple
import tempfile


class FieldStatisticsExtractor:
    """Extract field statistics from OpenFOAM cases"""

    def __init__(self, case_dir: Path):
        self.case_dir = Path(case_dir)
        self.log_file = case_dir / "log.foamRun"

    def get_velocity_pressure_stats(self, time: float) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Get velocity and pressure statistics using execFlowFunctionObjects.

        This runs OpenFOAM's built-in post-processing to calculate field statistics.

        Args:
            time: Time value to analyze

        Returns:
            Tuple of (velocity_stats, pressure_stats) dictionaries or (None, None)
        """
        # Create temporary controlDict with fieldMinMax function
        temp_control_dict = self._create_postprocess_controldict(time)

        try:
            # Write temporary controlDict
            control_dict_path = self.case_dir / "system" / "controlDict_postProcess"
            control_dict_path.write_text(temp_control_dict)

            # Run execFlowFunctionObjects
            cmd = [
                "execFlowFunctionObjects",
                "-case", str(self.case_dir),
                "-time", f"{time}:{ time}",
                "-dict", "system/controlDict_postProcess"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.case_dir,
                env={"FOAM_ABORT": "1"}  # Abort on error
            )

            # Clean up temporary file
            if control_dict_path.exists():
                control_dict_path.unlink()

            if result.returncode == 0:
                # Parse output
                velocity_stats = self._parse_field_minmax(result.stdout, "U")
                pressure_stats = self._parse_field_minmax(result.stdout, "p")
                return velocity_stats, pressure_stats
            else:
                # OpenFOAM not available, try parsing from existing logs
                return self._fallback_parse_from_log()

        except FileNotFoundError:
            print("    ⚠️  OpenFOAM utilities not available - using log file parsing fallback")
            return self._fallback_parse_from_log()
        except subprocess.TimeoutExpired:
            print("    ⚠️  Post-processing timeout")
            return None, None
        except Exception as e:
            print(f"    ⚠️  Post-processing error: {e}")
            return self._fallback_parse_from_log()

    def _fallback_parse_from_log(self) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Fallback method: estimate statistics from convergence residuals.

        This is not accurate but gives order-of-magnitude estimates when
        OpenFOAM post-processing is not available.
        """
        try:
            if not self.log_file.exists():
                return None, None

            with open(self.log_file, 'r') as f:
                content = f.read()

            # Look for Courant number (gives velocity estimate)
            courant_matches = re.findall(r'Courant Number mean:\s*([\d.e+-]+)\s+max:\s*([\d.e+-]+)', content)
            if courant_matches:
                mean_co, max_co = courant_matches[-1]
                # Typical cell size ~1mm, dt~0.0001s, so Co = U*dt/dx
                # U ~ Co * dx / dt, roughly estimate U ~ Co * 10 m/s for dt=0.0001, dx=0.001
                estimated_mean_vel = float(mean_co) * 100  # Very rough estimate
                estimated_max_vel = float(max_co) * 100

                velocity_stats = {
                    'min': 0.0,
                    'max': estimated_max_vel,
                    'mean': estimated_mean_vel,
                    'estimated': True
                }
            else:
                velocity_stats = None

            # Pressure is harder to estimate - return None
            pressure_stats = None

            return velocity_stats, pressure_stats

        except Exception as e:
            print(f"    ⚠️  Log parsing error: {e}")
            return None, None

    def get_patch_flow_rate(self, patch_name: str, time: float) -> Optional[float]:
        """
        Calculate volumetric flow rate through a patch.

        Args:
            patch_name: Patch name (e.g., 'inlet', 'outlet1')
            time: Time value

        Returns:
            Flow rate in m³/s or None
        """
        try:
            # Use surfaceFieldValue function object via execFlowFunctionObjects
            control_dict = self._create_flow_rate_controldict(patch_name, time)

            control_dict_path = self.case_dir / "system" / "controlDict_flowRate"
            control_dict_path.write_text(control_dict)

            cmd = [
                "execFlowFunctionObjects",
                "-case", str(self.case_dir),
                "-time", f"{time}:{time}",
                "-dict", "system/controlDict_flowRate"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.case_dir
            )

            if control_dict_path.exists():
                control_dict_path.unlink()

            if result.returncode == 0:
                return self._parse_flow_rate_output(result.stdout, patch_name)

        except FileNotFoundError:
            # OpenFOAM not available
            pass
        except Exception as e:
            print(f"    ⚠️  Flow rate calculation error: {e}")

        return None

    def _create_postprocess_controldict(self, time: float) -> str:
        """Create a controlDict for field statistics post-processing"""
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
FoamFile
{{
    format      ascii;
    class       dictionary;
    object      controlDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     foamRun;

startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {time};
deltaT          0.001;
writeControl    timeStep;
writeInterval   1;

functions
{{
    fieldMinMax
    {{
        type            fieldMinMax;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   1;
        log             yes;
        fields          (U p);
    }}
}}
// ************************************************************************* //
"""

    def _create_flow_rate_controldict(self, patch_name: str, time: float) -> str:
        """Create a controlDict for flow rate calculation"""
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
FoamFile
{{
    format      ascii;
    class       dictionary;
    object      controlDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     foamRun;

startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {time};
deltaT          0.001;
writeControl    timeStep;
writeInterval   1;

functions
{{
    flowRate_{patch_name}
    {{
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   1;
        log             yes;
        writeFields     false;
        regionType      patch;
        name            {patch_name};
        operation       sum;
        fields          (phi);
    }}
}}
// ************************************************************************* //
"""

    def _parse_field_minmax(self, output: str, field_name: str) -> Optional[Dict[str, float]]:
        """Parse field min/max from execFlowFunctionObjects output"""
        try:
            # Look for lines like:
            # fieldMinMax U: min = (0 0 0) max = (0.15 0.05 0.8)
            # or: fieldMinMax p: min = -10 max = 100
            pattern = rf'fieldMinMax\s+{field_name}.*?min\s*=\s*\(?([^\)]+)\)?.*?max\s*=\s*\(?([^\)]+)\)?'
            match = re.search(pattern, output, re.IGNORECASE)

            if match:
                min_str = match.group(1).strip()
                max_str = match.group(2).strip()

                # Handle vector fields (extract magnitude)
                if ' ' in min_str:  # Vector field like "(0 0 0)"
                    min_vals = [float(x) for x in min_str.split()]
                    max_vals = [float(x) for x in max_str.split()]
                    min_mag = (sum(v**2 for v in min_vals))**0.5
                    max_mag = (sum(v**2 for v in max_vals))**0.5
                else:  # Scalar field
                    min_mag = float(min_str)
                    max_mag = float(max_str)

                return {
                    'min': min_mag,
                    'max': max_mag,
                    'mean': (min_mag + max_mag) / 2.0  # Rough estimate
                }

        except Exception as e:
            print(f"    ⚠️  Failed to parse {field_name} stats: {e}")

        return None

    def _parse_flow_rate_output(self, output: str, patch_name: str) -> Optional[float]:
        """Parse flow rate from output"""
        try:
            # Look for line like: sum(phi) for patch inlet = 0.00123
            pattern = rf'sum\(phi\).*?{patch_name}.*?=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)'
            match = re.search(pattern, output)
            if match:
                return float(match.group(1))
        except:
            pass
        return None
