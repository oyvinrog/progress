"""Exceptions raised by PyPlane."""


class PyPlaneError(Exception):
    """Base class for PyPlane errors."""


class InvalidMapError(PyPlaneError, ValueError):
    """Raised when a mind map is structurally invalid."""


class MMFormatError(PyPlaneError, ValueError):
    """Raised when an .mm file cannot be safely decoded."""
