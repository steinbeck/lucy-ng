"""Regression test: ailsa lsd run on ibuprofen_no_4j.lsd produces stable InChI set.

What this test does
-------------------
Runs ``ailsa lsd run`` (via LSDRunner) on the versioned ibuprofen LSD fixture
(no 4J correlations, classic v1 form — no inventory block, no `; ELIM`
annotations).  The resulting SMILES are converted to InChIs and compared as a
**set** against a manually-verified baseline file.  Order does not matter; only
set-equality is checked (D-16).

When this test fails after an LSD version update
-------------------------------------------------
1. Read the failing output carefully.  Compare the added/removed InChIs.
2. Verify that the new InChI set is chemically plausible: all structures should
   be C13H18O2 isomers without strained rings or other LSD artefacts.
3. If the new set is correct, regenerate the baseline **manually**:
   a. Run LSD on the fixture: ``ailsa lsd run tests/fixtures/regression/ibuprofen_no_4j.lsd``
   b. Convert solutions to SMILES with outlsd: ``outlsd 5 < compound.sol > solutions.smi``
   c. Convert SMILES to InChIs:
      ``python3 -c "from pathlib import Path; from rdkit import Chem; from rdkit.Chem.inchi import MolToInchi; ...``
   d. Commit the new baseline with a message describing the LSD version change
      and confirming manual verification (D-16a/D-16b).
4. There is **no auto-update logic** by design.  Failure on version change is
   intentional — it forces manual chemical review before committing a new baseline.

Baseline provenance
-------------------
Generated from LSD-3.4.9 run (Phase 65 sol file, May 2026).
Manually verified: all InChIs are C13H18O2 isomers (D-16a).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from rdkit import Chem
from rdkit.Chem.inchi import MolToInchi  # type: ignore[import-untyped]

from ailsa.lsd.runner import LSDRunner

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "regression"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _smiles_to_inchis(smiles_path: Path) -> set[str]:
    """Convert a SMILES file (one per line) to a set of InChI strings.

    Skips empty lines, whitespace-only lines, invalid SMILES, and
    SMILES that produce a None InChI from RDKit.

    Args:
        smiles_path: Path to file with one SMILES string per line
                     (first whitespace-delimited field is the SMILES).

    Returns:
        Set of non-None InChI strings.
    """
    inchis: set[str] = set()
    for raw_line in smiles_path.read_text().splitlines():
        # Take only the first field (SMILES); rest may be index/name
        parts = raw_line.strip().split()
        if not parts:
            continue
        smiles = parts[0]
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue
        inchi = MolToInchi(mol)
        if inchi is not None:
            inchis.add(inchi)
    return inchis


def _read_baseline(baseline_path: Path) -> set[str]:
    """Read sorted InChIs from the baseline file.

    Args:
        baseline_path: Path to baseline file (one InChI per line).

    Returns:
        Set of non-empty InChI strings.
    """
    return {
        line.strip()
        for line in baseline_path.read_text().splitlines()
        if line.strip()
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLSDRegression:
    """Regression tests for ibuprofen LSD fixture stability."""

    def test_lsd_fixture_exists(self) -> None:
        """LSD fixture is committed in classic v1 form (no inventory block, no ; ELIM)."""
        fixture = FIXTURE_DIR / "ibuprofen_no_4j.lsd"
        assert fixture.exists(), f"LSD fixture missing: {fixture}"

        content = fixture.read_text()
        assert (
            "=== CONSTRAINT INVENTORY v2 ===" not in content
        ), "Fixture must not have v2 inventory block"
        assert "; ELIM" not in content, "Fixture must not have ; ELIM annotations"

    def test_baseline_fixture_exists(self) -> None:
        """Baseline InChI file is committed and non-empty.

        This test is intentionally always-on (no skipif).  It will FAIL until
        the developer generates and commits the baseline (plan Task 2 / checkpoint).

        # Baseline: 392 InChIs from LSD-3.4.9 run of ibuprofen_no_4j.lsd (Phase 65).
        # Manually verified 2026-05-19: all 392 are C13H18O2 isomers (D-16a).
        """
        baseline_path = FIXTURE_DIR / "ibuprofen_no_4j.expected_inchis.txt"
        assert baseline_path.exists(), (
            "Baseline file missing — see plan 69-04 Task 2 for generation instructions"
        )
        non_empty_lines = [
            line
            for line in baseline_path.read_text().splitlines()
            if line.strip()
        ]
        assert len(non_empty_lines) > 0, "Baseline file is empty"

    @pytest.mark.skipif(
        shutil.which("LSD") is None,
        reason="LSD binary not installed",
    )
    def test_ibuprofen_no_4j_inchi_set_stable(self, tmp_path: Path) -> None:
        """LSD run on ibuprofen_no_4j.lsd produces the same InChI set as baseline.

        Uses set equality (order-independent) as per D-16.  Fails if the LSD
        version or constraint interpretation changes — see module docstring for
        the re-verification procedure (D-16b).
        """
        lsd_fixture = FIXTURE_DIR / "ibuprofen_no_4j.lsd"
        baseline_path = FIXTURE_DIR / "ibuprofen_no_4j.expected_inchis.txt"

        runner = LSDRunner()
        result = runner.run_file(lsd_fixture, output_dir=tmp_path, timeout=120)
        assert result.success, (
            f"LSD run failed:\n  stdout: {result.stdout[:500]}\n  stderr: {result.stderr[:500]}"
        )

        # Locate SMILES output.
        #
        # Phase 73 fix: runner now uses file-argument mode, writes {stem}.sol to
        # output_dir, and runs outlsd correctly — solutions.smi is produced by
        # the runner itself.  Use solutions.smi directly if available (Path A).
        #
        # Path B (stdin-mode workaround, pre-Phase 73):
        # LSD-3.4.9 (stdin mode) writes OUTLSD-format solution data to stdout.
        # Reconstruct a synthetic .sol from stdout and pipe to outlsd 5.
        #
        # Path C (Fallback B, pre-Phase 73):
        # .sol file exists but solutions.smi was not written; convert manually.
        outlsd_bin = shutil.which("outlsd")
        assert outlsd_bin is not None, "outlsd binary not found on PATH"
        runner_smi = tmp_path / "solutions.smi"
        fallback_smi = tmp_path / "fallback_solutions.smi"

        if runner_smi.exists() and runner_smi.stat().st_size > 0:
            # Path A: Phase 73 fixed runner produced solutions.smi directly — use it.
            smiles_path = runner_smi
        elif result.stdout.strip():
            # Path B: stdin-mode stdout with OUTLSD data (pre-Phase 73 behavior).
            stdout_lines = result.stdout.splitlines(keepends=True)
            try:
                outlsd_idx = next(
                    i for i, ln in enumerate(stdout_lines) if ln.strip() == "OUTLSD"
                )
            except StopIteration:
                outlsd_idx = None

            if outlsd_idx is not None:
                outlsd_data = "".join(stdout_lines[outlsd_idx:])
                sol_content = (
                    f"# From file: {lsd_fixture}\n"
                    + lsd_fixture.read_text()
                    + "\n#\n"
                    + outlsd_data
                )
                sol_file = tmp_path / "compound.sol"
                sol_file.write_text(sol_content)
                # WR-04: use context manager to ensure file handle is closed.
                # WR-03: check=True raises CalledProcessError on non-zero exit
                # so a failing outlsd is reported clearly rather than silently
                # writing garbage to fallback_smi and causing a misleading
                # "InChI set changed" assertion failure.
                with sol_file.open("r") as stdin_fh:
                    proc = subprocess.run(
                        [outlsd_bin, "5"],
                        stdin=stdin_fh,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=True,
                    )
                fallback_smi.write_text(proc.stdout)
                smiles_path = fallback_smi
            else:
                # stdout doesn't contain OUTLSD marker — try raw pipe.
                # WR-03: check=True so an outlsd failure is reported clearly.
                proc = subprocess.run(
                    [outlsd_bin, "5"],
                    input=result.stdout,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                )
                fallback_smi.write_text(proc.stdout)
                smiles_path = fallback_smi
        else:
            # Path C: .sol file from LSD filename-invocation without outlsd conversion.
            sol_files = list(tmp_path.glob("*.sol"))
            assert sol_files, (
                "No usable SMILES output found: result.stdout is empty "
                "and no .sol files found in tmp_path"
            )
            sol_file = sol_files[0]
            with sol_file.open("r") as stdin_fh, fallback_smi.open("w") as stdout_fh:
                subprocess.run(
                    [outlsd_bin, "5"],
                    stdin=stdin_fh,
                    stdout=stdout_fh,
                    check=True,
                    timeout=30,
                )
            smiles_path = fallback_smi

        actual_inchis = _smiles_to_inchis(smiles_path)
        # WR-03: guard against empty InChI set from a silently-failed outlsd run.
        # If check=True raised CalledProcessError we never reach here; this guard
        # catches the edge case where outlsd exited 0 but produced no parseable SMILES.
        assert actual_inchis, (
            f"No InChIs parsed from {smiles_path} — outlsd may have produced empty or "
            f"unparseable output. SMILES file content (first 200 chars): "
            f"{smiles_path.read_text()[:200]!r}"
        )
        baseline_inchis = _read_baseline(baseline_path)

        added = actual_inchis - baseline_inchis
        removed = baseline_inchis - actual_inchis

        assert actual_inchis == baseline_inchis, (
            f"InChI set changed vs baseline.\n"
            f"  Added ({len(added)} new structures not in baseline): "
            f"{sorted(added)[:5]}{'...' if len(added) > 5 else ''}\n"
            f"  Removed ({len(removed)} baseline structures now absent): "
            f"{sorted(removed)[:5]}{'...' if len(removed) > 5 else ''}\n"
            f"See module docstring for re-verification procedure (D-16b)."
        )
