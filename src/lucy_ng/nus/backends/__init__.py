"""NUS reconstruction backend detection.

Runtime-detected external NUS reconstruction backends (e.g. NMRPipe+SMILE),
mirroring the ``lucy_ng.lsd`` external-binary detection pattern
(``LSDRunner.is_available()``): a backend binary is never a core
``pyproject.toml`` dependency, and its availability is probed at runtime via
``shutil.which``/subprocess capability probes.

This module defines the ``NusBackend`` protocol (the generic detection
surface every backend must expose) and a small name -> backend-class
registry (``get_backend``/``list_available_backends``) so callers (e.g.
``cli/nus.py``, added in a later plan) can address backends generically
without importing concrete backend classes directly.
"""

from typing import Any, Protocol, runtime_checkable

from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend


@runtime_checkable
class NusBackend(Protocol):
    """Generic detection surface every NUS reconstruction backend exposes.

    Concrete backends (e.g. ``NmrPipeSmileBackend``) implement these as
    classmethods, mirroring ``LSDRunner``'s classmethod-based availability
    API. The protocol only captures the detection surface -- reconstruction
    invocation itself is out of scope for Phase 97 (added in Phase 98).
    """

    @classmethod
    def is_available(cls) -> bool:
        """Return True if the backend is fully usable on this system."""
        ...

    @classmethod
    def missing_tools(cls) -> list[str]:
        """Return the names of required external tools not found on PATH."""
        ...

    @classmethod
    def diagnose(cls) -> dict[str, Any]:
        """Return a diagnostic dict distinguishing why a backend is/isn't
        usable (status/missing_tools/hint, etc.)."""
        ...


#: Registry of backend name -> backend class. Concrete backend classes are
#: never instantiated (all detection methods are classmethods) -- the
#: registry hands back the class itself, matching how NmrPipeSmileBackend
#: is used directly elsewhere (e.g. in tests).
_REGISTRY: dict[str, type[NusBackend]] = {
    "nmrpipe_smile": NmrPipeSmileBackend,
}


def get_backend(name: str = "nmrpipe_smile") -> type[NusBackend]:
    """Look up a registered NUS reconstruction backend by name.

    Args:
        name: Registry key (default: "nmrpipe_smile", the only backend
            registered in Phase 97).

    Returns:
        The backend class registered under ``name``.

    Raises:
        ValueError: If ``name`` is not a registered backend.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY)) or "(none registered)"
        raise ValueError(
            f"Unknown NUS backend: {name!r}. Registered backends: {available}"
        ) from None


def list_available_backends() -> list[str]:
    """List the names of registered backends currently usable on this system.

    Returns:
        Sorted list of registry names whose ``is_available()`` is True.
        Empty on a system with no reconstruction backend installed (e.g.
        this dev machine, which has no NMRPipe).
    """
    return sorted(name for name, cls in _REGISTRY.items() if cls.is_available())


__all__ = [
    "NusBackend",
    "get_backend",
    "list_available_backends",
]
