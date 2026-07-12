"""NUS (Non-Uniform Sampling) 2D reconstruction support.

This package provides tools for handling Bruker NUS 2D NMR data:

- **Params**: Parse acquisition/processing parameters from acqus/acqu2s/procs/proc2s
  into a validated ``NusAcquisitionParams`` model (``nus.params``).
- **Schedule**: Parse the ``nuslist`` sampling schedule into a validated
  ``NusSchedule`` model, with a FnMODE-derived hard-fail sample-count assertion
  (``nus.schedule``).
- **Backends**: Runtime-detected external reconstruction backends (e.g.
  NMRPipe+SMILE), mirroring the ``lucy_ng.lsd`` external-binary detection
  pattern (``nus.backends``).

Example usage:

```python
from lucy_ng.nus import read_nus_params, read_nus_schedule, get_backend

params = read_nus_params("C20H32O2/3")
schedule = read_nus_schedule("C20H32O2/3")

if get_backend().is_available():
    ...  # Phase 98: reconstruction
```

Note: unlike ``cli/nus.py`` (which must stay import-safe for the core CLI),
this package-level ``__init__`` does top-level imports of its submodules --
``nus.params``/``nus.schedule``/``nus.backends.nmrpipe_smile`` only need core
dependencies (nmrglue, pydantic, click stdlib shutil/subprocess), all already
required by the core CLI.
"""

# Params
from lucy_ng.models.nus import NusAcquisitionParams, NusSchedule
from lucy_ng.nus.backends import NusBackend, get_backend, list_available_backends
from lucy_ng.nus.params import read_nus_params

# Schedule
from lucy_ng.nus.schedule import read_nus_schedule

__all__ = [
    # Params
    "NusAcquisitionParams",
    "read_nus_params",
    # Schedule
    "NusSchedule",
    "read_nus_schedule",
    # Backends
    "NusBackend",
    "get_backend",
    "list_available_backends",
]
