"""Black-box tests for scripts/verify_case_solution.py.

Runs the verification script via subprocess so that tests remain completely
independent of ailsa internals.  No imports from ailsa are used here.

Test SMILES used:
- ``"CC(Cc1ccc(cc1)C(C)C)C(=O)O"`` — ibuprofen; C13H18O2; 6 aromatic atoms (PASS)
- ``"c1ccccc1"``                    — benzene;   C6H6;     6 aromatic atoms (aromatic but wrong formula)
- ``"CCC"``                         — propane;   C3H8;     0 aromatic atoms  (FAIL)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "verify_case_solution.py"


# ---------------------------------------------------------------------------
# Happy-path and standard FAIL branches
# ---------------------------------------------------------------------------


class TestVerifyScript:
    """Tests for scripts/verify_case_solution.py — standard branches."""

    def test_pass_aromatic_correct_formula(self, tmp_path: Path) -> None:
        """Ibuprofen SMILES at rank 1 — should PASS with exit code 0."""
        smi_file = tmp_path / "merged.smi"
        smi_file.write_text("CC(Cc1ccc(cc1)C(C)C)C(=O)O\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(smi_file), "C13H18O2"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected exit 0 (PASS), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        data = json.loads(result.stdout)
        assert data["pass"] is True

    def test_fail_no_aromatic_ring(self, tmp_path: Path) -> None:
        """Only aliphatic SMILES — should FAIL with exit code 1."""
        smi_file = tmp_path / "merged.smi"
        smi_file.write_text("CCC\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(smi_file), "C3H8"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Expected exit 1 (FAIL), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        data = json.loads(result.stdout)
        assert data["pass"] is False

    def test_fail_wrong_formula(self, tmp_path: Path) -> None:
        """Benzene has >=6 aromatic atoms but formula C6H6 != C13H18O2 — should FAIL."""
        smi_file = tmp_path / "merged.smi"
        smi_file.write_text("c1ccccc1\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(smi_file), "C13H18O2"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Expected exit 1 (FAIL — formula mismatch), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        data = json.loads(result.stdout)
        assert data["pass"] is False

    def test_fail_empty_smi_file(self, tmp_path: Path) -> None:
        """Empty merged.smi — should FAIL with exit code 1."""
        smi_file = tmp_path / "merged.smi"
        smi_file.write_text("")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(smi_file), "C13H18O2"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Expected exit 1 (FAIL — empty file), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_json_structure(self, tmp_path: Path) -> None:
        """JSON output must contain required keys; top_n_checked must equal 3."""
        smi_file = tmp_path / "merged.smi"
        smi_file.write_text("CC(Cc1ccc(cc1)C(C)C)C(=O)O\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(smi_file), "C13H18O2"],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        for key in ("pass", "checks", "formula", "top_n_checked"):
            assert key in data, f"Missing key '{key}' in JSON output: {data}"
        assert data["top_n_checked"] == 3
        assert data["formula"] == "C13H18O2"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestVerifyScriptEdgeCases:
    """Edge case and error handling tests."""

    def test_top3_only_rank4_does_not_pass(self, tmp_path: Path) -> None:
        """Aromatic + correct formula at rank 4 must NOT cause a PASS (top-3 only)."""
        smi_file = tmp_path / "merged.smi"
        # Lines 1-3: aliphatic propane (formula C3H8, no aromatic ring)
        # Line 4: ibuprofen (aromatic, C13H18O2) — must be ignored
        smi_file.write_text(
            "CCC\n"
            "CCC\n"
            "CCC\n"
            "CC(Cc1ccc(cc1)C(C)C)C(=O)O\n"
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(smi_file), "C13H18O2"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Expected exit 1 (rank-4 hit must not count), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        data = json.loads(result.stdout)
        assert data["pass"] is False

    def test_invalid_smiles_skipped_not_crash(self, tmp_path: Path) -> None:
        """Invalid SMILES on line 1 is skipped; valid benzene on line 2 becomes rank 1 and passes."""
        smi_file = tmp_path / "merged.smi"
        # "INVALID_SMILES" is not a valid SMILES — must be skipped (not crash)
        # benzene on line 2 has >=6 aromatic atoms and formula C6H6
        smi_file.write_text("INVALID_SMILES\nc1ccccc1\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(smi_file), "C6H6"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected exit 0 (invalid SMILES skipped, benzene passes), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        data = json.loads(result.stdout)
        assert data["pass"] is True

    def test_missing_smi_file(self, tmp_path: Path) -> None:
        """Nonexistent merged.smi path — should exit 1 without crashing."""
        nonexistent = tmp_path / "does_not_exist.smi"

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(nonexistent), "C13H18O2"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Expected exit 1 (missing file), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
