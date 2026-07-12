"""NUS (Non-Uniform Sampling) 2D reconstruction support.

This package provides tools for handling Bruker NUS 2D NMR data:

- **Params**: Parse acquisition/processing parameters from acqus/acqu2s/procs/proc2s
  into a validated ``NusAcquisitionParams`` model (``nus.params``, added in a later plan).
- **Schedule**: Parse the ``nuslist`` sampling schedule into a validated
  ``NusSchedule`` model, with a FnMODE-derived hard-fail sample-count assertion
  (``nus.schedule``, added in a later plan).
- **Backends**: Runtime-detected external reconstruction backends (e.g.
  NMRPipe+SMILE), mirroring the ``lucy_ng.lsd`` external-binary detection
  pattern (``nus.backends``, see that subpackage).

This module intentionally has no top-level re-imports yet: ``nus.params`` and
``nus.schedule`` do not exist until a later wave of this phase. The full
re-export list (mirroring ``lucy_ng.lsd``'s ``__all__`` pattern) is added once
those submodules land.
"""
