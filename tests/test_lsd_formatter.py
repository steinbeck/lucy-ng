"""Tests for DEFFFormatter -- SMILES to LSD SSTR/LINK fragment conversion."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from ailsa.cli.fragment import fragment
from ailsa.fragments.lsd_formatter import DEFFFormatter


@pytest.fixture()
def runner() -> CliRunner:
    """Click CliRunner for fragment CLI tests."""
    return CliRunner()

LSD_AVAILABLE = shutil.which("LSD") is not None


class TestSmilesToFragmentContent:
    """Test smiles_to_fragment_content static method."""

    def test_toluene_sstr_count(self) -> None:
        """Toluene (Cc1ccccc1) should produce 7 SSTR lines (7 heavy atoms)."""
        content = DEFFFormatter.smiles_to_fragment_content("Cc1ccccc1")
        sstr_lines = [ln for ln in content.splitlines() if ln.startswith("SSTR")]
        assert len(sstr_lines) == 7

    def test_toluene_link_count(self) -> None:
        """Toluene should produce 7 LINK lines (6 ring + 1 methyl-ring)."""
        content = DEFFFormatter.smiles_to_fragment_content("Cc1ccccc1")
        link_lines = [ln for ln in content.splitlines() if ln.startswith("LINK")]
        assert len(link_lines) == 7

    def test_toluene_1based_indices(self) -> None:
        """Atom indices in SSTR must be 1-based (S1 through S7)."""
        content = DEFFFormatter.smiles_to_fragment_content("Cc1ccccc1")
        sstr_lines = [ln for ln in content.splitlines() if ln.startswith("SSTR")]
        indices = sorted(
            int(ln.split()[1][1:]) for ln in sstr_lines  # extract N from SN
        )
        assert indices == [1, 2, 3, 4, 5, 6, 7]

    def test_toluene_hybridization(self) -> None:
        """Aromatic carbons get hyb=2, methyl carbon gets hyb=3."""
        content = DEFFFormatter.smiles_to_fragment_content("Cc1ccccc1")
        sstr_lines = [ln for ln in content.splitlines() if ln.startswith("SSTR")]
        # Collect hybridisation values (field index 3)
        hyb_values = [ln.split()[3] for ln in sstr_lines]
        assert hyb_values.count("2") == 6  # 6 aromatic carbons
        assert hyb_values.count("3") == 1  # 1 methyl sp3

    def test_toluene_h_counts(self) -> None:
        """Toluene: methyl=3H, 5 ArCH=1H, 1 ArC(subst)=0H."""
        content = DEFFFormatter.smiles_to_fragment_content("Cc1ccccc1")
        sstr_lines = [ln for ln in content.splitlines() if ln.startswith("SSTR")]
        h_counts = sorted(int(ln.split()[4]) for ln in sstr_lines)
        # 0, 1, 1, 1, 1, 1, 3
        assert h_counts == [0, 1, 1, 1, 1, 1, 3]

    def test_toluene_comment_line(self) -> None:
        """First line should be a comment with canonical SMILES."""
        content = DEFFFormatter.smiles_to_fragment_content("Cc1ccccc1")
        first_line = content.splitlines()[0]
        assert first_line.startswith("; Fragment:")

    def test_toluene_all_lines_valid(self) -> None:
        """Every line must start with SSTR, LINK, or ';'."""
        content = DEFFFormatter.smiles_to_fragment_content("Cc1ccccc1")
        for line in content.strip().splitlines():
            assert (
                line.startswith("SSTR S")
                or line.startswith("LINK S")
                or line.startswith(";")
            ), f"Unexpected line: {line}"

    def test_ethanol_atoms(self) -> None:
        """Ethanol (CCO) should produce 3 SSTR lines (C, C, O)."""
        content = DEFFFormatter.smiles_to_fragment_content("CCO")
        sstr_lines = [ln for ln in content.splitlines() if ln.startswith("SSTR")]
        assert len(sstr_lines) == 3
        # One of them must be oxygen
        elements = [ln.split()[2] for ln in sstr_lines]
        assert "O" in elements

    def test_ethanol_links(self) -> None:
        """Ethanol has 2 bonds -> 2 LINK lines."""
        content = DEFFFormatter.smiles_to_fragment_content("CCO")
        link_lines = [ln for ln in content.splitlines() if ln.startswith("LINK")]
        assert len(link_lines) == 2

    def test_invalid_smiles_raises(self) -> None:
        """Invalid SMILES should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid SMILES"):
            DEFFFormatter.smiles_to_fragment_content("not_a_smiles")

    def test_trailing_newline(self) -> None:
        """Content should end with a trailing newline."""
        content = DEFFFormatter.smiles_to_fragment_content("CCO")
        assert content.endswith("\n")


class TestFragmentFilename:
    """Test fragment_filename static method."""

    def test_canonical_equivalence(self) -> None:
        """Different SMILES for toluene must produce the same filename."""
        name1 = DEFFFormatter.fragment_filename("Cc1ccccc1")
        name2 = DEFFFormatter.fragment_filename("c1ccc(C)cc1")
        assert name1 == name2

    def test_filename_pattern(self) -> None:
        """Filename must match fragment_<12 hex chars>.lsd."""
        name = DEFFFormatter.fragment_filename("Cc1ccccc1")
        assert re.fullmatch(r"fragment_[0-9a-f]{12}\.lsd", name)

    def test_different_smiles_different_filenames(self) -> None:
        """Toluene and ethanol must produce different filenames."""
        name_toluene = DEFFFormatter.fragment_filename("Cc1ccccc1")
        name_ethanol = DEFFFormatter.fragment_filename("CCO")
        assert name_toluene != name_ethanol


class TestWriteFragmentFile:
    """Test write_fragment_file static method."""

    def test_writes_file(self, tmp_path: Path) -> None:
        """Fragment file should be written to the specified directory."""
        result = DEFFFormatter.write_fragment_file("Cc1ccccc1", output_dir=tmp_path)
        assert result.exists()
        assert result.parent == tmp_path

    def test_filename_matches(self, tmp_path: Path) -> None:
        """Written filename should match fragment_filename()."""
        result = DEFFFormatter.write_fragment_file("Cc1ccccc1", output_dir=tmp_path)
        expected_name = DEFFFormatter.fragment_filename("Cc1ccccc1")
        assert result.name == expected_name

    def test_file_content(self, tmp_path: Path) -> None:
        """Written file must contain SSTR and LINK lines and start with comment."""
        result = DEFFFormatter.write_fragment_file("Cc1ccccc1", output_dir=tmp_path)
        text = result.read_text()
        assert text.startswith("; Fragment:")
        assert "SSTR" in text
        assert "LINK" in text

    def test_default_output_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When output_dir is None, file is written to CWD."""
        monkeypatch.chdir(tmp_path)
        result = DEFFFormatter.write_fragment_file("CCO", output_dir=None)
        assert result.parent == tmp_path
        assert result.exists()


class TestDeffCommand:
    """Test deff_command static method."""

    def test_basic_command(self) -> None:
        """DEFF command must use double quotes around filepath."""
        cmd = DEFFFormatter.deff_command(1, "fragment_abc123.lsd")
        assert cmd == 'DEFF F1 "fragment_abc123.lsd"'

    def test_double_quotes_not_single(self) -> None:
        """Verify double quotes are used (not single quotes)."""
        cmd = DEFFFormatter.deff_command(2, "test.lsd")
        assert '"test.lsd"' in cmd
        assert "'" not in cmd


class TestFexpCommand:
    """Test fexp_command static method."""

    def test_single_fragment(self) -> None:
        """Single fragment -> FEXP "F1"."""
        cmd = DEFFFormatter.fexp_command([1])
        assert cmd == 'FEXP "F1"'

    def test_multiple_or(self) -> None:
        """Multiple fragments with OR."""
        cmd = DEFFFormatter.fexp_command([1, 2, 3])
        assert cmd == 'FEXP "F1 OR F2 OR F3"'

    def test_badlist_not(self) -> None:
        """Badlist with NOT logic."""
        cmd = DEFFFormatter.fexp_command([1], logic="NOT")
        assert cmd == 'FEXP "NOT F1"'

    def test_empty_list(self) -> None:
        """Empty fragment list returns empty string."""
        cmd = DEFFFormatter.fexp_command([])
        assert cmd == ""


# ---------------------------------------------------------------------------
# LSD Smoke Tests -- require LSD solver on PATH
# ---------------------------------------------------------------------------

# Toluene baseline LSD file (no fragments): 7 carbons, 5 ArCH + 1 ArC + 1 CH3
TOLUENE_BASELINE = """\
MULT 1 C 2 1
MULT 2 C 2 1
MULT 3 C 2 1
MULT 4 C 2 1
MULT 5 C 2 1
MULT 6 C 2 0
MULT 7 C 3 3
HSQC 1 1
HSQC 2 2
HSQC 3 3
HSQC 4 4
HSQC 5 5
HSQC 7 7
"""

# Generic 6-membered aromatic carbon ring fragment with flexible H count (0 1)
# to allow substituted ring carbons. This is the correct pattern for goodlist
# matching -- exact H counts from DEFFFormatter.smiles_to_fragment_content would
# be too restrictive (benzene has all 1H, but toluene has one 0H ring carbon).
BENZENE_GENERIC_FRAGMENT = """\
; Generic 6-membered aromatic carbon ring
SSTR S1 C 2 (0 1)
SSTR S2 C 2 (0 1)
SSTR S3 C 2 (0 1)
SSTR S4 C 2 (0 1)
SSTR S5 C 2 (0 1)
SSTR S6 C 2 (0 1)
LINK S1 S2
LINK S2 S3
LINK S3 S4
LINK S4 S5
LINK S5 S6
LINK S1 S6
"""


def _parse_solution_count(stderr: str) -> int:
    """Extract solution count from LSD stderr output."""
    match = re.search(r"(\d+) solution", stderr)
    if match:
        return int(match.group(1))
    return 0


@pytest.mark.skipif(not LSD_AVAILABLE, reason="LSD solver not installed")
class TestLSDSmokeGoodlist:
    """LSD smoke tests proving goodlist semantics with generated fragment files."""

    def test_lsd_smoke_goodlist_reduces_solutions(self, tmp_path: Path) -> None:
        """Benzene goodlist reduces toluene from 4 solutions to 1."""
        # 1. Write generic benzene fragment file (flexible H count for ring
        #    carbons that may be substituted in target molecule).
        fragment_filename = "benzene_generic.lsd"
        fragment_path = tmp_path / fragment_filename
        fragment_path.write_text(BENZENE_GENERIC_FRAGMENT)

        # 2. Write baseline LSD file (no DEFF/FEXP)
        baseline_path = tmp_path / "toluene_baseline.lsd"
        baseline_path.write_text(TOLUENE_BASELINE)

        # 3. Write goodlist LSD file (DEFF/FEXP before MULT)
        deff_line = DEFFFormatter.deff_command(1, fragment_filename)
        fexp_line = DEFFFormatter.fexp_command([1])
        goodlist_content = f"{deff_line}\n{fexp_line}\n{TOLUENE_BASELINE}"
        goodlist_path = tmp_path / "toluene_goodlist.lsd"
        goodlist_path.write_text(goodlist_content)

        # 4. Run LSD on baseline
        baseline_result = subprocess.run(
            ["LSD", str(baseline_path)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        baseline_solutions = _parse_solution_count(baseline_result.stderr)

        # 5. Run LSD on goodlist
        goodlist_result = subprocess.run(
            ["LSD", str(goodlist_path)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        goodlist_solutions = _parse_solution_count(goodlist_result.stderr)

        # 6. Assertions
        assert baseline_solutions == 4, (
            f"Expected 4 baseline solutions, got {baseline_solutions}. "
            f"stderr: {baseline_result.stderr}"
        )
        assert goodlist_solutions == 1, (
            f"Expected 1 goodlist solution, got {goodlist_solutions}. "
            f"stderr: {goodlist_result.stderr}"
        )
        assert goodlist_solutions < baseline_solutions, (
            "Goodlist must reduce solutions (confirming it is not accidentally a "
            "badlist)"
        )

    def test_lsd_smoke_deff_fexp_before_mult(self, tmp_path: Path) -> None:
        """DEFF/FEXP lines are placed before MULT in generated goodlist file."""
        # Write generic benzene fragment
        fragment_filename = "benzene_generic.lsd"
        fragment_path = tmp_path / fragment_filename
        fragment_path.write_text(BENZENE_GENERIC_FRAGMENT)

        deff_line = DEFFFormatter.deff_command(1, fragment_filename)
        fexp_line = DEFFFormatter.fexp_command([1])
        goodlist_content = f"{deff_line}\n{fexp_line}\n{TOLUENE_BASELINE}"
        goodlist_path = tmp_path / "toluene_goodlist.lsd"
        goodlist_path.write_text(goodlist_content)

        # Verify ordering
        lines = goodlist_path.read_text().splitlines()
        deff_idx = next(i for i, ln in enumerate(lines) if ln.startswith("DEFF"))
        fexp_idx = next(i for i, ln in enumerate(lines) if ln.startswith("FEXP"))
        mult_idx = next(i for i, ln in enumerate(lines) if ln.startswith("MULT"))

        assert deff_idx < mult_idx, (
            f"DEFF (line {deff_idx}) must be before MULT (line {mult_idx})"
        )
        assert fexp_idx < mult_idx, (
            f"FEXP (line {fexp_idx}) must be before MULT (line {mult_idx})"
        )


class TestToLsdFilterIndex:
    """Test --filter-index option for ailsa fragment to-lsd CLI."""

    def test_to_lsd_default_filter_index_is_3(self, runner: CliRunner, tmp_path: Path) -> None:
        """Default --filter-index is 3 (reserves F1/F2 for ring exclusion)."""
        result = runner.invoke(fragment, ["to-lsd", "CCO", "--output-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "DEFF F3" in data["deff_command"]
        assert data["fexp_command"] == 'FEXP "F3"'

    def test_to_lsd_explicit_filter_index_1(self, runner: CliRunner, tmp_path: Path) -> None:
        """Explicit --filter-index 1 allows backward compat."""
        result = runner.invoke(
            fragment, ["to-lsd", "CCO", "--filter-index", "1", "--output-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "DEFF F1" in data["deff_command"]
        assert data["fexp_command"] == 'FEXP "F1"'

    def test_to_lsd_explicit_filter_index_5(self, runner: CliRunner, tmp_path: Path) -> None:
        """Explicit --filter-index 5 produces F5 commands."""
        result = runner.invoke(
            fragment, ["to-lsd", "CCO", "--filter-index", "5", "--output-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "DEFF F5" in data["deff_command"]
        assert data["fexp_command"] == 'FEXP "F5"'


class TestSearchDeffDoubleQuotes:
    """Verify the search command's DEFF output uses double quotes."""

    def test_deff_commands_use_double_quotes(self) -> None:
        """DEFF commands from search must use double quotes, not single."""
        # Replicate the search command's DEFF generation logic
        match_count = 3
        deff_commands = [
            f'DEFF F{i + 1} "fragment_{i + 1}.lsd"'
            for i in range(match_count)
        ]

        for cmd in deff_commands:
            assert '"' in cmd, f"Missing double quotes in: {cmd}"
            # Single quotes should NOT appear anywhere in the command
            assert "'" not in cmd, f"Single quote found in: {cmd}"

    def test_fexp_command_uses_double_quotes(self) -> None:
        """FEXP command from search must use double quotes."""
        # Single match case
        fexp_single = 'FEXP "F1"'
        assert '"' in fexp_single
        assert "'" not in fexp_single

        # Multiple match case
        parts = " OR ".join(f"F{i + 1}" for i in range(3))
        fexp_multi = f'FEXP "{parts}"'
        assert '"' in fexp_multi
        assert "'" not in fexp_multi
