"""Entry point for ``python -m ailsa.cli``.

Allows the ailsa CLI to be invoked as::

    python -m ailsa.cli <command> [args...]

This is used as a subprocess-launch fallback by :func:`ailsa.webview.server.start`
when the ``ailsa`` script is not on PATH (e.g. in an editable/dev install).
"""

from ailsa.cli import cli

if __name__ == "__main__":
    cli()
