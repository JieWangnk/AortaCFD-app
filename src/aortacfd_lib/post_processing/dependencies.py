"""
Dependency checking for post-processing module.

Checks for required and optional dependencies:
- Required: numpy, vtk (for data handling)
- Visualization: paraview (for screenshots/animations)
- Animations: ffmpeg (for video creation)
- Plots: matplotlib (for pressure/WSS plots)
- Config: pyyaml (for YAML config files)
"""

import shutil
import subprocess
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class DependencyStatus:
    """Status of a single dependency."""

    name: str
    available: bool = False
    version: Optional[str] = None
    path: Optional[str] = None
    required: bool = False
    purpose: str = ""
    install_hint: str = ""


@dataclass
class DependencyReport:
    """Complete dependency check report."""

    all_required_available: bool = True
    dependencies: Dict[str, DependencyStatus] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def print_report(self) -> None:
        """Print formatted dependency report."""
        print("\n" + "=" * 60)
        print("DEPENDENCY CHECK REPORT")
        print("=" * 60)

        # Group by required/optional
        required = [d for d in self.dependencies.values() if d.required]
        optional = [d for d in self.dependencies.values() if not d.required]

        print("\nREQUIRED DEPENDENCIES:")
        print("-" * 60)
        for dep in required:
            status = "[OK]" if dep.available else "[MISSING]"
            version_str = f" (v{dep.version})" if dep.version else ""
            print(f"  {status:10} {dep.name:15}{version_str}")
            if not dep.available:
                print(f"             Purpose: {dep.purpose}")
                print(f"             Install: {dep.install_hint}")

        print("\nOPTIONAL DEPENDENCIES:")
        print("-" * 60)
        for dep in optional:
            status = "[OK]" if dep.available else "[MISSING]"
            version_str = f" (v{dep.version})" if dep.version else ""
            print(f"  {status:10} {dep.name:15}{version_str}")
            if not dep.available:
                print(f"             Purpose: {dep.purpose}")
                print(f"             Install: {dep.install_hint}")

        if self.warnings:
            print("\nWARNINGS:")
            print("-" * 60)
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.errors:
            print("\nERRORS:")
            print("-" * 60)
            for error in self.errors:
                print(f"  - {error}")

        print("\n" + "=" * 60)
        if self.all_required_available:
            print("STATUS: All required dependencies available")
        else:
            print("STATUS: Missing required dependencies - some features unavailable")
        print("=" * 60 + "\n")


def check_python_module(module_name: str, package_name: Optional[str] = None) -> DependencyStatus:
    """
    Check if a Python module is available.

    Args:
        module_name: Name of the module to import
        package_name: Package name for error messages (defaults to module_name)

    Returns:
        DependencyStatus with availability information
    """
    package_name = package_name or module_name
    status = DependencyStatus(name=package_name)

    try:
        module = __import__(module_name)
        status.available = True
        # Try to get version
        for attr in ['__version__', 'VERSION', 'version']:
            if hasattr(module, attr):
                version = getattr(module, attr)
                if callable(version):
                    version = version()
                status.version = str(version)
                break
    except ImportError:
        status.available = False

    return status


def check_executable(exe_name: str, version_flag: str = "--version") -> DependencyStatus:
    """
    Check if an executable is available in PATH.

    Args:
        exe_name: Name of the executable
        version_flag: Flag to get version (default: --version)

    Returns:
        DependencyStatus with availability information
    """
    status = DependencyStatus(name=exe_name)

    # Find executable
    exe_path = shutil.which(exe_name)
    if exe_path:
        status.available = True
        status.path = exe_path

        # Try to get version
        try:
            result = subprocess.run(
                [exe_path, version_flag],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Parse version from output (first line usually contains version)
            output = result.stdout or result.stderr
            if output:
                # Extract first line and look for version pattern
                first_line = output.split('\n')[0]
                # Common patterns: "program 1.2.3", "program version 1.2.3"
                import re
                version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', first_line)
                if version_match:
                    status.version = version_match.group(1)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            pass
    else:
        status.available = False

    return status


def check_paraview() -> DependencyStatus:
    """Check for ParaView/pvbatch availability."""
    # First try pvbatch (batch mode)
    status = check_executable('pvbatch')
    if status.available:
        status.name = 'ParaView (pvbatch)'
        return status

    # Try pvpython
    status = check_executable('pvpython')
    if status.available:
        status.name = 'ParaView (pvpython)'
        return status

    # Try paraview CLI
    status = check_executable('paraview')
    if status.available:
        status.name = 'ParaView'

    return status


def check_openfoam() -> DependencyStatus:
    """Check for OpenFOAM availability."""
    # Check for foamPostProcess (OpenFOAM 12+)
    status = check_executable('foamPostProcess')
    if status.available:
        status.name = 'OpenFOAM (foamPostProcess)'
        # Try to get OpenFOAM version
        try:
            result = subprocess.run(
                ['foamPostProcess', '-help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Look for version in help output
            import re
            version_match = re.search(r'OpenFOAM\s*(v?\d+(?:\.\d+)?)', result.stderr or result.stdout)
            if version_match:
                status.version = version_match.group(1)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
        return status

    # Check for postProcess (older OpenFOAM)
    status = check_executable('postProcess')
    if status.available:
        status.name = 'OpenFOAM (postProcess)'
        return status

    # Check for simpleFoam as proxy for OpenFOAM
    status = check_executable('simpleFoam')
    if status.available:
        status.name = 'OpenFOAM'

    return status


def check_dependencies(verbose: bool = False) -> DependencyReport:
    """
    Check all dependencies for post-processing.

    Args:
        verbose: Print detailed dependency report

    Returns:
        DependencyReport with all dependency statuses
    """
    report = DependencyReport()

    # Required Python modules
    numpy_status = check_python_module('numpy')
    numpy_status.required = True
    numpy_status.purpose = "Numerical array operations"
    numpy_status.install_hint = "pip install numpy"
    report.dependencies['numpy'] = numpy_status

    vtk_status = check_python_module('vtk')
    vtk_status.required = True
    vtk_status.purpose = "VTK data handling"
    vtk_status.install_hint = "pip install vtk"
    report.dependencies['vtk'] = vtk_status

    scipy_status = check_python_module('scipy')
    scipy_status.required = True
    scipy_status.purpose = "Scientific computing (ConvexHull for camera)"
    scipy_status.install_hint = "pip install scipy"
    report.dependencies['scipy'] = scipy_status

    # Optional Python modules
    matplotlib_status = check_python_module('matplotlib')
    matplotlib_status.required = False
    matplotlib_status.purpose = "Pressure drop and WSS plots"
    matplotlib_status.install_hint = "pip install matplotlib"
    report.dependencies['matplotlib'] = matplotlib_status

    yaml_status = check_python_module('yaml', 'PyYAML')
    yaml_status.required = False
    yaml_status.purpose = "YAML configuration file support"
    yaml_status.install_hint = "pip install pyyaml"
    report.dependencies['pyyaml'] = yaml_status

    # ParaView (optional but needed for visualization)
    paraview_status = check_paraview()
    paraview_status.required = False
    paraview_status.purpose = "Screenshots and volume rendering"
    paraview_status.install_hint = "Install ParaView: https://www.paraview.org/download/"
    report.dependencies['paraview'] = paraview_status

    # ffmpeg (optional for animations)
    ffmpeg_status = check_executable('ffmpeg')
    ffmpeg_status.required = False
    ffmpeg_status.purpose = "Animation video creation"
    ffmpeg_status.install_hint = "apt install ffmpeg OR brew install ffmpeg"
    report.dependencies['ffmpeg'] = ffmpeg_status

    # OpenFOAM (optional for WSS post-processing)
    openfoam_status = check_openfoam()
    openfoam_status.required = False
    openfoam_status.purpose = "WSS post-processing (foamPostProcess)"
    openfoam_status.install_hint = "Source OpenFOAM environment"
    report.dependencies['openfoam'] = openfoam_status

    # Check if all required dependencies are available
    for dep in report.dependencies.values():
        if dep.required and not dep.available:
            report.all_required_available = False
            report.errors.append(f"Missing required dependency: {dep.name}")

    # Add warnings for missing optional dependencies
    if not paraview_status.available:
        report.warnings.append("ParaView not available - visualization disabled")

    if not ffmpeg_status.available:
        report.warnings.append("ffmpeg not available - animations disabled")

    if not matplotlib_status.available:
        report.warnings.append("matplotlib not available - plots disabled")

    if verbose:
        report.print_report()

    return report


def require_dependencies(*dependency_names: str) -> bool:
    """
    Check that specific dependencies are available.

    Args:
        *dependency_names: Names of dependencies to check

    Returns:
        True if all specified dependencies are available

    Raises:
        RuntimeError: If any dependency is missing
    """
    report = check_dependencies(verbose=False)
    missing = []

    for name in dependency_names:
        if name in report.dependencies:
            if not report.dependencies[name].available:
                dep = report.dependencies[name]
                missing.append(f"{name} ({dep.purpose}) - Install: {dep.install_hint}")

    if missing:
        raise RuntimeError(
            f"Missing required dependencies:\n" +
            "\n".join(f"  - {m}" for m in missing)
        )

    return True


# Convenience functions for specific checks
def has_paraview() -> bool:
    """Check if ParaView is available."""
    return check_paraview().available


def has_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return check_executable('ffmpeg').available


def has_matplotlib() -> bool:
    """Check if matplotlib is available."""
    return check_python_module('matplotlib').available


def has_openfoam() -> bool:
    """Check if OpenFOAM is available."""
    return check_openfoam().available


if __name__ == "__main__":
    # Run dependency check when executed directly
    check_dependencies(verbose=True)
