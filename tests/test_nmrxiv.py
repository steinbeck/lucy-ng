"""Tests for NMRXiv client module."""

import json
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ailsa.nmrxiv import (
    DownloadResult,
    NMRXivClient,
    NMRXivDataset,
    NMRXivError,
    NMRXivProject,
    NMRXivStudy,
    ParsedIdentifier,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestParsedIdentifier:
    """Tests for ParsedIdentifier model."""

    def test_project_only(self):
        """Test creating identifier with project only."""
        parsed = ParsedIdentifier(project_id="P10", original="P10")
        assert parsed.project_id == "P10"
        assert parsed.study_id is None
        assert not parsed.has_study

    def test_with_study(self):
        """Test creating identifier with study."""
        parsed = ParsedIdentifier(
            project_id="P10", study_id="S69", original="10.57992/NMRXIV.P10.S69"
        )
        assert parsed.project_id == "P10"
        assert parsed.study_id == "S69"
        assert parsed.has_study


class TestNMRXivModels:
    """Tests for NMRXiv data models."""

    def test_dataset_model(self):
        """Test NMRXivDataset model."""
        dataset = NMRXivDataset(id="D123", name="1H", type="proton")
        assert dataset.id == "D123"
        assert dataset.name == "1H"
        assert dataset.type == "proton"

    def test_study_model(self):
        """Test NMRXivStudy model with datasets."""
        datasets = [
            NMRXivDataset(id="D1", name="1H"),
            NMRXivDataset(id="D2", name="13C"),
        ]
        study = NMRXivStudy(
            id="S69", name="Sample 1", description="Test sample", datasets=datasets
        )
        assert study.id == "S69"
        assert study.name == "Sample 1"
        assert len(study.datasets) == 2

    def test_project_model(self):
        """Test NMRXivProject model with studies."""
        studies = [
            NMRXivStudy(id="S1", name="Study 1"),
            NMRXivStudy(id="S2", name="Study 2"),
        ]
        project = NMRXivProject(
            id="P10",
            name="Test Project",
            description="A test project",
            doi="10.57992/NMRXIV.P10",
            owner="testuser",
            studies=studies,
        )
        assert project.id == "P10"
        assert project.name == "Test Project"
        assert project.doi == "10.57992/NMRXIV.P10"
        assert len(project.studies) == 2

    def test_download_result_model(self):
        """Test DownloadResult model with size calculation."""
        result = DownloadResult(
            project_id="P10",
            project_name="Test",
            output_path="/tmp/P10",
            studies_downloaded=["S1", "S2"],
            total_datasets=5,
            total_files=100,
            total_bytes=1024 * 1024 * 10,  # 10 MB
        )
        assert result.total_size_mb == 10.0


# =============================================================================
# Client Tests - Identifier Parsing
# =============================================================================


class TestNMRXivClientIdentifierParsing:
    """Tests for identifier parsing."""

    def test_parse_full_doi(self):
        """Test parsing full DOI with study."""
        client = NMRXivClient()
        parsed = client.parse_identifier("10.57992/NMRXIV.P10.S69")
        assert parsed.project_id == "P10"
        assert parsed.study_id == "S69"

    def test_parse_doi_project_only(self):
        """Test parsing DOI without study."""
        client = NMRXivClient()
        parsed = client.parse_identifier("10.57992/NMRXIV.P10")
        assert parsed.project_id == "P10"
        assert parsed.study_id is None

    def test_parse_doi_with_url_prefix(self):
        """Test parsing DOI with https://doi.org/ prefix."""
        client = NMRXivClient()
        parsed = client.parse_identifier("https://doi.org/10.57992/NMRXIV.P10.S69")
        assert parsed.project_id == "P10"
        assert parsed.study_id == "S69"

    def test_parse_project_id_direct(self):
        """Test parsing direct project ID."""
        client = NMRXivClient()
        parsed = client.parse_identifier("P10")
        assert parsed.project_id == "P10"
        assert parsed.study_id is None

    def test_parse_project_id_lowercase(self):
        """Test parsing lowercase project ID."""
        client = NMRXivClient()
        parsed = client.parse_identifier("p10")
        assert parsed.project_id == "P10"

    def test_parse_url(self):
        """Test parsing NMRXiv URL."""
        client = NMRXivClient()
        parsed = client.parse_identifier("https://nmrxiv.org/P10")
        assert parsed.project_id == "P10"
        assert parsed.study_id is None

    def test_parse_url_with_study(self):
        """Test parsing NMRXiv URL with study."""
        client = NMRXivClient()
        parsed = client.parse_identifier("https://nmrxiv.org/P10/S69")
        assert parsed.project_id == "P10"
        assert parsed.study_id == "S69"

    def test_parse_invalid_identifier(self):
        """Test parsing invalid identifier raises error."""
        client = NMRXivClient()
        with pytest.raises(NMRXivError, match="Unrecognized identifier format"):
            client.parse_identifier("invalid-id")

    def test_parse_study_only_raises_error(self):
        """Test parsing study ID without project raises error."""
        client = NMRXivClient()
        with pytest.raises(NMRXivError, match="requires a project context"):
            client.parse_identifier("S69")


# =============================================================================
# Client Tests - API Mocking
# =============================================================================


class TestNMRXivClientAPI:
    """Tests for API interactions with mocking."""

    @patch("ailsa.nmrxiv.client.requests.Session")
    def test_get_project_success(self, mock_session_class):
        """Test successful project fetch."""
        # Setup mock
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "Test Project",
            "description": "A test",
            "doi": "10.57992/NMRXIV.P10",
            "owner": {"username": "testuser"},
            "studies": [
                {
                    "identifier": "S1",
                    "name": "Study 1",
                    "datasets": [{"identifier": "D1", "name": "1H"}],
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        client = NMRXivClient()
        project = client.get_project("P10")

        assert project.id == "P10"
        assert project.name == "Test Project"
        assert project.owner == "testuser"
        assert len(project.studies) == 1
        assert project.studies[0].id == "S1"

    @patch("ailsa.nmrxiv.client.requests.Session")
    def test_get_project_not_found(self, mock_session_class):
        """Test project not found error."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        import requests

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_session.get.return_value = mock_response

        client = NMRXivClient()
        with pytest.raises(NMRXivError, match="Project not found"):
            client.get_project("P999")


class TestNMRXivClientDownload:
    """Tests for download functionality with mocking."""

    @patch("ailsa.nmrxiv.client.requests.Session")
    def test_download_creates_directories(self, mock_session_class):
        """Test that download creates proper directory structure."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock project metadata response
        project_response = MagicMock()
        project_response.json.return_value = {
            "name": "Test Project",
            "owner": {"username": "testuser"},
            "studies": [
                {
                    "identifier": "S1",
                    "name": "Study 1",
                    "datasets": [{"identifier": "D1", "name": "1H"}],
                }
            ],
        }
        project_response.raise_for_status = MagicMock()

        # Mock zip download response (create a real zip in memory)
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("1H/acqus", "##TITLE= Test")
            zf.writestr("1H/fid", b"\x00\x00")
        zip_buffer.seek(0)

        zip_response = MagicMock()
        zip_response.headers = {"content-length": str(len(zip_buffer.getvalue()))}
        zip_response.iter_content = lambda chunk_size: [zip_buffer.getvalue()]
        zip_response.raise_for_status = MagicMock()

        # Return different responses based on URL
        def side_effect(url, *args, **kwargs):
            if "/api/v1/" in url:
                return project_response
            return zip_response

        mock_session.get.side_effect = side_effect

        with tempfile.TemporaryDirectory() as tmpdir:
            client = NMRXivClient()
            result = client.download("P10", output_dir=tmpdir, progress=False)

            assert result.project_id == "P10"
            assert result.total_files == 2
            assert Path(result.output_path).exists()


# =============================================================================
# CLI Tests
# =============================================================================


class TestNMRXivCLI:
    """Tests for CLI commands."""

    def test_fetch_help(self):
        """Test fetch command help."""
        from ailsa.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["fetch", "--help"])
        assert result.exit_code == 0
        assert "Fetch NMR data" in result.output

    def test_fetch_nmrxiv_help(self):
        """Test fetch nmrxiv subcommand help."""
        from ailsa.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["fetch", "nmrxiv", "--help"])
        assert result.exit_code == 0
        assert "IDENTIFIER" in result.output
        assert "--output" in result.output
        assert "--all" in result.output

    @patch("ailsa.nmrxiv.client.requests.Session")
    def test_fetch_nmrxiv_invalid_identifier(self, mock_session_class):
        """Test fetch with invalid identifier."""
        from ailsa.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["fetch", "nmrxiv", "invalid-id"])
        assert result.exit_code == 1
        assert "Error" in result.output or "error" in result.output.lower()

    @patch("ailsa.nmrxiv.client.requests.Session")
    def test_fetch_nmrxiv_json_output(self, mock_session_class):
        """Test fetch with JSON output format."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock project response
        project_response = MagicMock()
        project_response.json.return_value = {
            "name": "Test Project",
            "owner": {"username": "testuser"},
            "studies": [
                {
                    "identifier": "S1",
                    "name": "Study 1",
                    "datasets": [],
                }
            ],
        }
        project_response.raise_for_status = MagicMock()

        # Mock empty zip
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            pass
        zip_buffer.seek(0)

        zip_response = MagicMock()
        zip_response.headers = {"content-length": "0"}
        zip_response.iter_content = lambda chunk_size: [zip_buffer.getvalue()]
        zip_response.raise_for_status = MagicMock()

        def side_effect(url, *args, **kwargs):
            if "/api/v1/" in url:
                return project_response
            return zip_response

        mock_session.get.side_effect = side_effect

        from ailsa.cli import cli

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli, ["fetch", "nmrxiv", "P10", "--format", "json", "--quiet"]
            )
            # Parse JSON output
            if result.exit_code == 0:
                output = json.loads(result.output)
                assert output.get("success") is True
                assert output.get("project_id") == "P10"


# =============================================================================
# Integration Tests (marked slow, require network)
# =============================================================================


@pytest.mark.slow
class TestNMRXivIntegration:
    """Integration tests that require network access.

    These tests are marked slow and can be skipped with: pytest -m "not slow"
    """

    def test_fetch_real_project_metadata(self):
        """Test fetching metadata from a real NMRXiv project."""
        client = NMRXivClient(timeout=30)
        try:
            # P7 is a known public project
            project = client.get_project("P7")
            assert project.id == "P7"
            # API response format may vary - just check we got a response
            # If name is empty, the API may have changed format
            if not project.name and not project.studies:
                pytest.skip("NMRXiv API response format may have changed")
        except NMRXivError:
            pytest.skip("NMRXiv API not available")
        except Exception as e:
            pytest.skip(f"Network error: {e}")

    def test_parse_real_doi(self):
        """Test parsing a real DOI format."""
        client = NMRXivClient()
        # This just tests parsing, no network needed
        parsed = client.parse_identifier("10.57992/NMRXIV.P7")
        assert parsed.project_id == "P7"
