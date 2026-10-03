"""Tests for CLI read commands."""

import json
from pathlib import Path

from click.testing import CliRunner

from ailsa.cli.read import read


class TestRead1D:
    """Tests for ailsa read 1d command."""

    def test_read_1d_text(self) -> None:
        """Test reading 1D spectrum with text output."""
        runner = CliRunner()
        result = runner.invoke(read, ["1d", "data/Ibuprofen/2"])  # 13C
        assert result.exit_code == 0
        assert "Nucleus: 13C" in result.output
        assert "Frequency:" in result.output
        assert "Points:" in result.output
        assert "PPM range:" in result.output

    def test_read_1d_json(self) -> None:
        """Test reading 1D spectrum with JSON output."""
        runner = CliRunner()
        result = runner.invoke(read, ["1d", "data/Ibuprofen/2", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["nucleus"] == "13C"
        assert "frequency" in data
        assert "points" in data
        assert "ppm_min" in data
        assert "ppm_max" in data

    def test_read_1d_proton(self) -> None:
        """Test reading 1H spectrum."""
        runner = CliRunner()
        result = runner.invoke(read, ["1d", "data/Ibuprofen/1"])  # 1H
        assert result.exit_code == 0
        assert "Nucleus: 1H" in result.output

    def test_read_1d_dept(self) -> None:
        """Test reading DEPT spectrum."""
        runner = CliRunner()
        result = runner.invoke(read, ["1d", "data/Ibuprofen/3"])  # DEPT-135
        assert result.exit_code == 0
        assert "Nucleus: 13C" in result.output

    def test_read_1d_invalid_path(self) -> None:
        """Test error on invalid path."""
        runner = CliRunner()
        result = runner.invoke(read, ["1d", "data/NonExistent/1"])
        assert result.exit_code != 0


class TestRead2D:
    """Tests for ailsa read 2d command."""

    def test_read_2d_hsqc_text(self) -> None:
        """Test reading HSQC spectrum with text output."""
        runner = CliRunner()
        result = runner.invoke(read, ["2d", "data/Ibuprofen/6"])  # HSQC
        assert result.exit_code == 0
        assert "Experiment: HSQC" in result.output
        assert "F1 nucleus: 13C" in result.output
        assert "F2 nucleus: 1H" in result.output
        assert "Shape:" in result.output

    def test_read_2d_hsqc_json(self) -> None:
        """Test reading HSQC spectrum with JSON output."""
        runner = CliRunner()
        result = runner.invoke(read, ["2d", "data/Ibuprofen/6", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["experiment_type"] == "HSQC"
        assert data["f1_nucleus"] == "13C"
        assert data["f2_nucleus"] == "1H"
        assert "shape" in data
        assert len(data["shape"]) == 2

    def test_read_2d_hmbc(self) -> None:
        """Test reading HMBC spectrum."""
        runner = CliRunner()
        result = runner.invoke(read, ["2d", "data/Ibuprofen/7"])  # HMBC
        assert result.exit_code == 0
        assert "Experiment: HMBC" in result.output

    def test_read_2d_cosy(self) -> None:
        """Test reading COSY spectrum."""
        runner = CliRunner()
        result = runner.invoke(read, ["2d", "data/Ibuprofen/5"])  # COSY
        assert result.exit_code == 0
        assert "Experiment: COSY" in result.output

    def test_read_2d_invalid_path(self) -> None:
        """Test error on invalid path."""
        runner = CliRunner()
        result = runner.invoke(read, ["2d", "data/NonExistent/6"])
        assert result.exit_code != 0
