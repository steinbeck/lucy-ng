"""NUS reconstruction backend detection.

Runtime-detected external NUS reconstruction backends (e.g. NMRPipe+SMILE),
mirroring the ``lucy_ng.lsd`` external-binary detection pattern
(``LSDRunner.is_available()``): a backend binary is never a core
``pyproject.toml`` dependency, and its availability is probed at runtime via
``shutil.which``/subprocess capability probes.

This module intentionally has no top-level re-imports yet: the
``NusBackend`` protocol, concrete backend implementations (e.g.
``nmrpipe_smile.py``), and the backend registry (``get_backend``,
``list_available_backends``) are added in a later plan of this phase.
"""
