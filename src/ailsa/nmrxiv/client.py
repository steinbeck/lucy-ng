"""NMRXiv API client for fetching NMR datasets."""

import logging
import re
import zipfile
from io import BytesIO
from pathlib import Path

import requests
from tqdm import tqdm

from .models import (
    DownloadResult,
    NMRXivDataset,
    NMRXivProject,
    NMRXivStudy,
    ParsedIdentifier,
)

logger = logging.getLogger(__name__)


class NMRXivError(Exception):
    """Base exception for NMRXiv client errors."""

    pass


class NMRXivClient:
    """Client for fetching NMR datasets from NMRXiv.

    NMRXiv (https://nmrxiv.org) is an open repository for NMR data.
    This client supports downloading public projects by DOI or ID.

    Example:
        >>> client = NMRXivClient()
        >>> result = client.download("10.57992/NMRXIV.P10.S69", output_dir="./data")
        >>> print(f"Downloaded {result.total_files} files")
    """

    BASE_URL = "https://nmrxiv.org"
    API_URL = "https://nmrxiv.org/api/v1"

    # DOI pattern: 10.57992/NMRXIV.P{project}.S{study} or 10.57992/NMRXIV.P{project}
    DOI_PATTERN = re.compile(
        r"(?:https?://doi\.org/)?10\.57992/NMRXIV\.P(\d+)(?:\.S(\d+))?",
        re.IGNORECASE,
    )

    # Direct ID patterns
    PROJECT_PATTERN = re.compile(r"^P(\d+)$", re.IGNORECASE)
    STUDY_PATTERN = re.compile(r"^S(\d+)$", re.IGNORECASE)

    def __init__(self, timeout: int = 60) -> None:
        """Initialize the NMRXiv client.

        Args:
            timeout: Request timeout in seconds (default: 60)
        """
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "ailsa/1.0 (NMR structure elucidation tool)",
            }
        )
        self._timeout = timeout

    def parse_identifier(self, identifier: str) -> ParsedIdentifier:
        """Parse a DOI or ID string into project/study components.

        Supported formats:
        - DOI: 10.57992/NMRXIV.P10.S69 or https://doi.org/10.57992/NMRXIV.P10
        - Project ID: P10
        - Study ID: S69 (requires separate project context)
        - URL: https://nmrxiv.org/P10

        Args:
            identifier: DOI, project ID, or URL

        Returns:
            ParsedIdentifier with project_id and optional study_id

        Raises:
            NMRXivError: If identifier format is not recognized
        """
        identifier = identifier.strip()

        # Try DOI pattern first
        doi_match = self.DOI_PATTERN.match(identifier)
        if doi_match:
            project_num = doi_match.group(1)
            study_num = doi_match.group(2)
            return ParsedIdentifier(
                project_id=f"P{project_num}",
                study_id=f"S{study_num}" if study_num else None,
                original=identifier,
            )

        # Try URL pattern (https://nmrxiv.org/P10)
        url_match = re.match(
            r"https?://(?:www\.)?nmrxiv\.org/P(\d+)(?:/S(\d+))?",
            identifier,
            re.IGNORECASE,
        )
        if url_match:
            project_num = url_match.group(1)
            study_num = url_match.group(2)
            return ParsedIdentifier(
                project_id=f"P{project_num}",
                study_id=f"S{study_num}" if study_num else None,
                original=identifier,
            )

        # Try direct project ID
        project_match = self.PROJECT_PATTERN.match(identifier)
        if project_match:
            return ParsedIdentifier(
                project_id=identifier.upper(),
                study_id=None,
                original=identifier,
            )

        # Try direct study ID (will need project context later)
        study_match = self.STUDY_PATTERN.match(identifier)
        if study_match:
            raise NMRXivError(
                f"Study ID '{identifier}' requires a project context. "
                "Use full DOI or project ID instead."
            )

        raise NMRXivError(
            f"Unrecognized identifier format: '{identifier}'. "
            "Expected DOI (10.57992/NMRXIV.P10.S69), project ID (P10), "
            "or URL (https://nmrxiv.org/P10)"
        )

    def get_project(self, project_id: str) -> NMRXivProject:
        """Fetch project metadata from NMRXiv API.

        Args:
            project_id: Project identifier (e.g., 'P10')

        Returns:
            NMRXivProject with studies and datasets

        Raises:
            NMRXivError: If project not found or API error
        """
        # Normalize ID
        if not project_id.upper().startswith("P"):
            project_id = f"P{project_id}"
        project_id = project_id.upper()

        url = f"{self.API_URL}/{project_id}"
        logger.debug(f"Fetching project metadata: {url}")

        try:
            response = self._session.get(url, timeout=self._timeout)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise NMRXivError(f"Project not found: {project_id}")
            raise NMRXivError(f"API error fetching project: {e}")
        except requests.exceptions.RequestException as e:
            raise NMRXivError(f"Network error fetching project: {e}")

        data = response.json()

        # Parse studies from response
        studies = []
        for study_data in data.get("studies", []):
            datasets = []
            for dataset_data in study_data.get("datasets", []):
                datasets.append(
                    NMRXivDataset(
                        id=dataset_data.get("identifier", dataset_data.get("id", "")),
                        name=dataset_data.get("name", ""),
                        type=dataset_data.get("type"),
                    )
                )
            studies.append(
                NMRXivStudy(
                    id=study_data.get("identifier", study_data.get("id", "")),
                    name=study_data.get("name", ""),
                    description=study_data.get("description"),
                    datasets=datasets,
                )
            )

        # Extract owner username from data
        owner = data.get("owner", {})
        if isinstance(owner, dict):
            owner_name = owner.get("username", owner.get("name", ""))
        else:
            owner_name = str(owner) if owner else ""

        return NMRXivProject(
            id=project_id,
            name=data.get("name", data.get("title", "")),
            description=data.get("description"),
            doi=data.get("doi"),
            owner=owner_name,
            studies=studies,
        )

    def download(
        self,
        identifier: str,
        output_dir: str | Path = ".",
        study_id: str | None = None,
        download_all: bool = False,
        progress: bool = True,
    ) -> DownloadResult:
        """Download NMR data from NMRXiv.

        Args:
            identifier: DOI, project ID, or URL
            output_dir: Directory to save downloaded files
            study_id: Specific study to download (overrides DOI study)
            download_all: Download all studies even if DOI specifies one
            progress: Show progress bar

        Returns:
            DownloadResult with download statistics

        Raises:
            NMRXivError: If download fails
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Parse identifier
        parsed = self.parse_identifier(identifier)
        logger.info(f"Parsed identifier: project={parsed.project_id}, study={parsed.study_id}")

        # Override study from parameter if provided
        if study_id:
            parsed = ParsedIdentifier(
                project_id=parsed.project_id,
                study_id=study_id.upper() if not study_id.upper().startswith("S") else study_id,
                original=parsed.original,
            )

        # Get project metadata
        project = self.get_project(parsed.project_id)
        logger.info(f"Project: {project.name} ({len(project.studies)} studies)")

        # Determine which studies to download
        if download_all or not parsed.study_id:
            studies_to_download = project.studies
        else:
            # Find the specific study
            matching = [s for s in project.studies if s.id.upper() == parsed.study_id.upper()]
            if not matching:
                available = ", ".join(s.id for s in project.studies)
                raise NMRXivError(
                    f"Study {parsed.study_id} not found in project. "
                    f"Available studies: {available}"
                )
            studies_to_download = matching

        # Download each study
        project_dir = output_dir / project.id
        project_dir.mkdir(parents=True, exist_ok=True)

        total_files = 0
        total_bytes = 0
        total_datasets = 0
        studies_downloaded = []

        for study in studies_to_download:
            logger.info(f"Downloading study: {study.id} ({study.name})")
            study_dir = project_dir / study.id

            # Download study as zip
            files, bytes_dl = self._download_study(
                project=project,
                study=study,
                output_dir=study_dir,
                progress=progress,
            )
            total_files += files
            total_bytes += bytes_dl
            total_datasets += len(study.datasets)
            studies_downloaded.append(study.id)

        return DownloadResult(
            project_id=project.id,
            project_name=project.name,
            doi=project.doi,
            output_path=str(project_dir),
            studies_downloaded=studies_downloaded,
            total_datasets=total_datasets,
            total_files=total_files,
            total_bytes=total_bytes,
        )

    def _download_study(
        self,
        project: NMRXivProject,
        study: NMRXivStudy,
        output_dir: Path,
        progress: bool = True,
    ) -> tuple[int, int]:
        """Download a single study's data.

        Returns:
            Tuple of (file_count, byte_count)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Try to download as zip archive first
        # URL pattern: {owner}/download/{project}/{study}
        if project.owner:
            zip_url = f"{self.BASE_URL}/{project.owner}/download/{project.id}/{study.id}"
        else:
            # Fallback to API-based download
            zip_url = f"{self.API_URL}/download/{project.id}/{study.id}"

        logger.debug(f"Downloading study zip: {zip_url}")

        try:
            response = self._session.get(zip_url, stream=True, timeout=self._timeout * 5)
            response.raise_for_status()

            # Get content length for progress bar
            total_size = int(response.headers.get("content-length", 0))

            # Download to memory
            content = BytesIO()
            if progress and total_size > 0:
                with tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    desc=f"{study.id}",
                    leave=False,
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        content.write(chunk)
                        pbar.update(len(chunk))
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    content.write(chunk)

            content.seek(0)
            total_bytes = content.getbuffer().nbytes

            # Extract zip
            file_count = 0
            with zipfile.ZipFile(content, "r") as zf:
                for member in zf.namelist():
                    # Skip directories
                    if member.endswith("/"):
                        continue
                    # Extract preserving structure
                    zf.extract(member, output_dir)
                    file_count += 1

            logger.info(f"Extracted {file_count} files to {output_dir}")
            return file_count, total_bytes

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Study zip not available, trying individual datasets")
                return self._download_datasets_individually(project, study, output_dir, progress)
            raise NMRXivError(f"Error downloading study {study.id}: {e}")
        except zipfile.BadZipFile:
            logger.warning("Response was not a valid zip, trying individual datasets")
            return self._download_datasets_individually(project, study, output_dir, progress)
        except requests.exceptions.RequestException as e:
            raise NMRXivError(f"Network error downloading study: {e}")

    def _download_datasets_individually(
        self,
        project: NMRXivProject,
        study: NMRXivStudy,
        output_dir: Path,
        progress: bool = True,
    ) -> tuple[int, int]:
        """Fallback: download each dataset individually.

        Returns:
            Tuple of (file_count, byte_count)
        """
        total_files = 0
        total_bytes = 0

        for dataset in study.datasets:
            dataset_dir = output_dir / dataset.name
            dataset_dir.mkdir(parents=True, exist_ok=True)

            # Try dataset download URL
            if project.owner:
                url = f"{self.BASE_URL}/{project.owner}/download/{project.id}/{study.id}/{dataset.id}"
            else:
                url = f"{self.API_URL}/download/{project.id}/{study.id}/{dataset.id}"

            logger.debug(f"Downloading dataset: {url}")

            try:
                response = self._session.get(url, stream=True, timeout=self._timeout * 2)
                response.raise_for_status()

                # Check if it's a zip
                content_type = response.headers.get("content-type", "")
                total_size = int(response.headers.get("content-length", 0))

                content = BytesIO()
                if progress and total_size > 0:
                    with tqdm(
                        total=total_size,
                        unit="B",
                        unit_scale=True,
                        desc=dataset.name,
                        leave=False,
                    ) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            content.write(chunk)
                            pbar.update(len(chunk))
                else:
                    for chunk in response.iter_content(chunk_size=8192):
                        content.write(chunk)

                content.seek(0)
                total_bytes += content.getbuffer().nbytes

                if "zip" in content_type or dataset.id.endswith(".zip"):
                    # Extract zip
                    with zipfile.ZipFile(content, "r") as zf:
                        for member in zf.namelist():
                            if not member.endswith("/"):
                                zf.extract(member, dataset_dir)
                                total_files += 1
                else:
                    # Save as single file
                    file_path = dataset_dir / dataset.id
                    file_path.write_bytes(content.read())
                    total_files += 1

            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to download dataset {dataset.id}: {e}")
                continue

        return total_files, total_bytes

    def __enter__(self) -> "NMRXivClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close session."""
        self._session.close()
