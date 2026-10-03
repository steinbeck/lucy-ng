"""NMRXiv client for fetching NMR datasets from nmrxiv.org."""

from .client import NMRXivClient, NMRXivError
from .models import (
    DownloadResult,
    NMRXivDataset,
    NMRXivProject,
    NMRXivStudy,
    ParsedIdentifier,
)

__all__ = [
    "NMRXivClient",
    "NMRXivError",
    "NMRXivProject",
    "NMRXivStudy",
    "NMRXivDataset",
    "ParsedIdentifier",
    "DownloadResult",
]
