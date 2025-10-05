"""
OpenFOAM Post-Processing Utilities

Uses OpenFOAM utilities to extract field statistics from simulation results.
"""

import subprocess
from pathlib import Path
from typing import Dict, Optional, List
import re


class OpenFOAMPostProcessor:
    """Extract field statistics using OpenFOAM utilities"""

    def __init__(self, case_dir: Path):
        self.case_dir = Path(case_dir)

    def get_field_min_max(self, field_name: str, time: float) -> Optional[Dict[str, float]]:
        """
        Get min/max values for a field at specific time using postProcess utility.

        Args:
            field_name: Field name (U, p, nut, etc.)
            time: Time value

        Returns:
            Dict with 'min' and 'max' keys, or None if failed
        """
        try:
            # Use OpenFOAM's postProcess utility with fieldMinMax function
            cmd = [
                "postProcess",
                "-case", str(self.case_dir),
                "-func", f"'mag({field_name})'",
                "-time", f"{time}",
                "-noZero"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.case_dir
            )

            if result.returncode == 0:
                return self._parse_minmax_output(result.stdout)

        except subprocess.TimeoutExpired:
            print(f"    ⚠️  postProcess timeout for field {field_name}")
        except FileNotFoundError:
            print(f"    ⚠️  postProcess utility not found - OpenFOAM not sourced?")
        except Exception as e:
            print(f"    ⚠️  Error running postProcess: {e}")

        return None

    def get_field_stats_foamDictionary(self, field_path: Path) -> Optional[Dict[str, any]]:
        """
        Read field file and extract basic stats using foamDictionary.

        Args:
            field_path: Path to field file (e.g., case/0.1/U)

        Returns:
            Dict with field info or None
        """
        try:
            # Use foamDictionary to read internalField dimensions
            cmd = ["foamDictionary", "-entry", "dimensions", str(field_path)]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {"dimensions": result.stdout.strip()}

        except FileNotFoundError:
            print(f"    ⚠️  foamDictionary not found - OpenFOAM not sourced?")
        except Exception as e:
            print(f"    ⚠️  Error reading field file: {e}")

        return None

    def calculate_field_magnitude_stats(self, field_file: Path) -> Optional[Dict[str, float]]:
        """
        Calculate magnitude statistics for a field using sample/postProcess.

        This is a workaround for reading binary files by using OpenFOAM's own tools.

        Args:
            field_file: Path to field file

        Returns:
            Dict with 'min', 'max', 'mean' or None
        """
        try:
            case_dir = field_file.parent.parent
            time_name = field_file.parent.name
            field_name = field_file.name

            # Create a temporary sample dict to extract field data
            sample_dict = self._create_sample_dict(field_name)

            # Write temporary sampleDict
            sample_file = case_dir / "system" / "sampleDict"
            original_existed = sample_file.exists()
            original_content = None
            if original_existed:
                original_content = sample_file.read_text()

            sample_file.write_text(sample_dict)

            # Run postProcess with sample function
            cmd = [
                "postProcess",
                "-case", str(case_dir),
                "-func", "sample",
                "-time", time_name,
                "-noZero"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=case_dir
            )

            # Restore original sampleDict
            if original_existed and original_content:
                sample_file.write_text(original_content)
            elif sample_file.exists():
                sample_file.unlink()

            if result.returncode == 0:
                # Parse output for field statistics
                return self._parse_sample_output(result.stdout, field_name)

        except Exception as e:
            print(f"    ⚠️  Error calculating field stats: {e}")

        return None

    def get_flow_rate_at_patch(self, patch_name: str, time: float) -> Optional[float]:
        """
        Calculate flow rate through a patch using surfaceFieldValue function.

        Args:
            patch_name: Patch name (inlet, outlet1, etc.)
            time: Time value

        Returns:
            Flow rate in m³/s or None
        """
        try:
            # Use surfaceFieldValue function object
            cmd = [
                "postProcess",
                "-case", str(self.case_dir),
                "-func",
                f"'surfaceFieldValue(name={patch_name},operation=sum,fields=(phi))'",
                "-time", f"{time}",
                "-noZero"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.case_dir
            )

            if result.returncode == 0:
                # Parse flow rate from output
                return self._parse_flow_rate(result.stdout)

        except Exception as e:
            print(f"    ⚠️  Error calculating flow rate for {patch_name}: {e}")

        return None

    def _parse_minmax_output(self, output: str) -> Optional[Dict[str, float]]:
        """Parse min/max from postProcess output"""
        try:
            lines = output.split('\n')
            for line in lines:
                if 'min' in line.lower() and 'max' in line.lower():
                    # Extract numbers from line like "min = 0.001 max = 1.234"
                    numbers = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', line)
                    if len(numbers) >= 2:
                        return {'min': float(numbers[0]), 'max': float(numbers[1])}
        except:
            pass
        return None

    def _parse_sample_output(self, output: str, field_name: str) -> Optional[Dict[str, float]]:
        """Parse field statistics from sample output"""
        # This would need to parse the specific output format
        # For now, return None indicating not implemented
        return None

    def _parse_flow_rate(self, output: str) -> Optional[float]:
        """Parse flow rate from surfaceFieldValue output"""
        try:
            # Look for lines like "sum(patch) phi = 0.001234"
            match = re.search(r'sum.*?phi.*?=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)', output)
            if match:
                return float(match.group(1))
        except:
            pass
        return None

    def _create_sample_dict(self, field_name: str) -> str:
        """Create a sampleDict for extracting field statistics"""
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  12
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       dictionary;
    location    "system";
    object      sampleDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

type            sets;
libs            ("libsampling.so");

interpolationScheme cellPoint;

setFormat       raw;

sets
(
    volumeAverage
    {{
        type        uniform;
        axis        xyz;
        start       (0 0 0);
        end         (0 0 0);
        nPoints     1;
    }}
);

fields          ({field_name});

// ************************************************************************* //
"""

    def extract_all_patch_names(self) -> List[str]:
        """Extract all patch names from boundary file"""
        try:
            boundary_file = self.case_dir / "constant" / "polyMesh" / "boundary"
            if not boundary_file.exists():
                return []

            with open(boundary_file, 'r') as f:
                content = f.read()

            # Extract patch names (simple regex)
            patches = re.findall(r'^\s*(\w+)\s*$', content, re.MULTILINE)
            # Filter out OpenFOAM keywords
            keywords = ['FoamFile', 'type', 'class', 'object', 'patch', 'wall', 'nFaces', 'startFace']
            patches = [p for p in patches if p not in keywords and not p.isdigit()]

            return patches

        except Exception as e:
            print(f"    ⚠️  Error extracting patch names: {e}")
            return []
