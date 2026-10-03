"""Data models for NMRXiv API responses."""

from pydantic import BaseModel, Field


class NMRXivDataset(BaseModel):
    """An NMR dataset (single experiment) in NMRXiv."""

    id: str = Field(description="Dataset identifier (e.g., 'D123')")
    name: str = Field(description="Dataset name (e.g., '1H', '13C', 'HSQC')")
    type: str | None = Field(default=None, description="Experiment type")


class NMRXivStudy(BaseModel):
    """A study (sample) in NMRXiv containing multiple datasets."""

    id: str = Field(description="Study identifier (e.g., 'S69')")
    name: str = Field(description="Study name")
    description: str | None = Field(default=None, description="Study description")
    datasets: list[NMRXivDataset] = Field(
        default_factory=list, description="Datasets in this study"
    )


class NMRXivProject(BaseModel):
    """An NMRXiv project containing studies and datasets."""

    id: str = Field(description="Project identifier (e.g., 'P10')")
    name: str = Field(description="Project name/title")
    description: str | None = Field(default=None, description="Project description")
    doi: str | None = Field(default=None, description="DOI if published")
    owner: str = Field(description="Owner username (for download URLs)")
    studies: list[NMRXivStudy] = Field(
        default_factory=list, description="Studies in this project"
    )


class ParsedIdentifier(BaseModel):
    """Result of parsing an NMRXiv identifier (DOI or ID)."""

    project_id: str = Field(description="Project identifier (e.g., 'P10')")
    study_id: str | None = Field(
        default=None, description="Study identifier if specified (e.g., 'S69')"
    )
    original: str = Field(description="Original identifier string")

    @property
    def has_study(self) -> bool:
        """Whether a specific study was specified."""
        return self.study_id is not None


class DownloadResult(BaseModel):
    """Result of downloading from NMRXiv."""

    project_id: str = Field(description="Project identifier")
    project_name: str = Field(description="Project name/title")
    doi: str | None = Field(default=None, description="Project DOI")
    output_path: str = Field(description="Path where files were downloaded")
    studies_downloaded: list[str] = Field(
        default_factory=list, description="Study IDs that were downloaded"
    )
    total_datasets: int = Field(default=0, description="Number of datasets downloaded")
    total_files: int = Field(default=0, description="Number of files downloaded")
    total_bytes: int = Field(default=0, description="Total bytes downloaded")

    @property
    def total_size_mb(self) -> float:
        """Total size in megabytes."""
        return self.total_bytes / (1024 * 1024)
