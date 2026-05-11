"""AortaCFD library package."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("aortacfd")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__author__ = "AortaCFD Development Team"

__all__ = ["__version__", "__author__"]
