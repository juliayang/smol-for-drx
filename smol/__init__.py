"""Implementats classes/functions to study configurational thermodynamics."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("statmech-on-lattices")
except PackageNotFoundError:
    # package is not installed
    pass
