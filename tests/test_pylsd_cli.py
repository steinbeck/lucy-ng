"""CLI integration tests for ailsa pylsd run."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from click.testing import CliRunner

from ailsa.cli.pylsd import pylsd, _extract_suspects
from ailsa.lsd.orchestrator import (
    MergeResult,
    MergedSolution,
    OrchestrationResult,
    PermutationResult,
)


# ---------------------------------------------------------------------------
# Helper: minimal v2 inventory JSON with deferred_4j entries
# ---------------------------------------------------------------------------


def _make_deferred_4j_entry(atom1: int, atom2: int) -> dict:
    """Return a minimal valid deferred_4j entry with required schema fields.

    The annotation field MUST be "; ELIM" (const in schema).
    """
    return {
        "atom1": atom1,
        "atom2": atom2,
        "shift1": 130.0,
        "shift2": 45.0,
        "correlation_type": "HMBC",
        "annotation": "; ELIM",
    }


def _minimal_v2_inventory_json(deferred_4j: list | None = None) -> str:
    """Return a minimal valid v2 inventory JSON string."""
    return json.dumps(
        {
            "version": 2,
            "iteration": 1,
            "formula": "C13H18O2",
            "timestamp": "2026-01-01T00:00:00Z",
            "mult_count": 13,
            "hsqc_count": 10,
            "hmbc_batches": [],
            "hmbc_total": 0,
            "pylsd_mode": False,
            "elim_annotated": False,
            "deferred_4j": deferred_4j or [],
        },
        indent=2,
    )


def _make_v2_lsd_content(inventory_json: str, lsd_commands: str = "") -> str:
    """Wrap inventory JSON in LSD v2 block delimiters."""
    lines = [
        "; === CONSTRAINT INVENTORY v2 ===",
    ]
    for line in inventory_json.splitlines():
        lines.append(f"; {line}")
    lines.append("; === END CONSTRAINT INVENTORY ===")
    if lsd_commands:
        lines.append("")
        lines.append(lsd_commands)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Shared mock setup helper
# ---------------------------------------------------------------------------


def _make_mock_results(
    tmp_path: Path,
    merged_solutions: list | None = None,
) -> tuple:
    """Create mock OrchestrationResult and MergeResult for tests.

    Returns:
        Tuple of (mock_orch_result, mock_merge_result, MockOrch context, MockMerger context).
    """
    mock_orch_result = MagicMock(spec=OrchestrationResult)
    mock_orch_result.permutation_results = []

    mock_merge_result = MagicMock(spec=MergeResult)
    mock_merge_result.merged_solutions = merged_solutions if merged_solutions is not None else []
    merged_smi = tmp_path / "merged.smi"
    merged_smi.write_text("")
    run_report = tmp_path / "run_report.json"
    run_report.write_text("{}")
    mock_merge_result.merged_smi = merged_smi
    mock_merge_result.run_report = run_report

    return mock_orch_result, mock_merge_result


# ---------------------------------------------------------------------------
# TestPylsdRunCLI: basic invocations with mocked orchestrator + merger
# ---------------------------------------------------------------------------


class TestPylsdRunCLI:
    """Basic invocations of `ailsa pylsd run` with mocked PyLSDOrchestrator + SolutionMerger."""

    def test_no_rank_exits_0(self, tmp_path):
        """--no-rank path must exit 0 and echo merged.smi path to stdout."""
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text("; minimal\nEXIT\n")

        # Provide a non-empty solution so the no-rank path is taken (not the empty-set path)
        merged_solution = MagicMock(spec=MergedSolution)
        merged_solution.canonical_smiles = "CC"
        mock_orch_result, mock_merge_result = _make_mock_results(
            tmp_path, merged_solutions=[merged_solution]
        )

        with (
            patch("ailsa.cli.pylsd.PyLSDOrchestrator") as MockOrch,
            patch("ailsa.cli.pylsd.SolutionMerger") as MockMerger,
            patch("ailsa.cli.pylsd.LSDRunner.is_available", return_value=True),
        ):
            MockOrch.return_value.run.return_value = mock_orch_result
            MockMerger.return_value.merge.return_value = mock_merge_result

            runner = CliRunner()
            result = runner.invoke(
                pylsd, ["run", str(lsd_file), "--no-rank"], catch_exceptions=False
            )

        assert result.exit_code == 0, (
            f"Expected exit 0, got {result.exit_code}. Output: {result.output}"
        )
        assert "merged.smi" in result.output

    def test_shifts_required_without_no_rank(self, tmp_path):
        """Missing --shifts without --no-rank must exit 1 with clear error message."""
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text("; minimal\nEXIT\n")

        with patch("ailsa.cli.pylsd.LSDRunner.is_available", return_value=True):
            runner = CliRunner()
            result = runner.invoke(pylsd, ["run", str(lsd_file)])

        assert result.exit_code == 1, (
            f"Expected exit 1 for missing --shifts, got {result.exit_code}. Output: {result.output}"
        )
        assert "--shifts" in result.output or "--shifts" in (result.output + (result.stderr or ""))

    def test_format_json_structure(self, tmp_path):
        """--format json output must contain {permutations, merged_count, ranked_solutions, run_report_path}."""
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text("; minimal\nEXIT\n")

        merged_solution = MagicMock(spec=MergedSolution)
        merged_solution.canonical_smiles = "CC"
        mock_orch_result, mock_merge_result = _make_mock_results(
            tmp_path, merged_solutions=[merged_solution]
        )
        mock_orch_result.permutation_results = [MagicMock()]

        ranking_data = {
            "total_solutions": 1,
            "ranked_count": 1,
            "skipped_count": 0,
            "experimental_shifts": [25.0],
            "tolerance": 3.0,
            "solutions": [
                {
                    "rank": 1,
                    "solution_index": 0,
                    "smiles": "CC",
                    "mae": 1.0,
                    "quality": "good",
                    "deviations": [1.0],
                    "within_3ppm": 1,
                    "within_5ppm": 1,
                    "total_carbons": 2,
                    "max_deviation": 1.0,
                    "prediction_rate": 1.0,
                    "matched_count": 1,
                    "has_aromatic_ring": False,
                }
            ],
            "warnings": [],
        }

        with (
            patch("ailsa.cli.pylsd.PyLSDOrchestrator") as MockOrch,
            patch("ailsa.cli.pylsd.SolutionMerger") as MockMerger,
            patch("ailsa.cli.pylsd.LSDRunner.is_available", return_value=True),
            patch("ailsa.cli.pylsd._perform_ranking", return_value=ranking_data),
        ):
            MockOrch.return_value.run.return_value = mock_orch_result
            MockMerger.return_value.merge.return_value = mock_merge_result

            # Use mix_stderr=False so stderr (warnings) don't corrupt stdout JSON
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                pylsd,
                ["run", str(lsd_file), "--shifts", "25.0", "--format", "json"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0, (
            f"Expected exit 0, got {result.exit_code}. Output: {result.output}"
        )
        data = json.loads(result.output)
        assert "permutations" in data, f"Missing 'permutations' key. Data: {data}"
        assert "merged_count" in data, f"Missing 'merged_count' key. Data: {data}"
        assert "ranked_solutions" in data, f"Missing 'ranked_solutions' key. Data: {data}"
        assert "run_report_path" in data, f"Missing 'run_report_path' key. Data: {data}"

    def test_no_solutions_exits_0(self, tmp_path):
        """Empty merged solutions must produce exit 0 (not an error per CASE workflow)."""
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text("; minimal\nEXIT\n")

        mock_orch_result, mock_merge_result = _make_mock_results(
            tmp_path, merged_solutions=[]
        )

        with (
            patch("ailsa.cli.pylsd.PyLSDOrchestrator") as MockOrch,
            patch("ailsa.cli.pylsd.SolutionMerger") as MockMerger,
            patch("ailsa.cli.pylsd.LSDRunner.is_available", return_value=True),
        ):
            MockOrch.return_value.run.return_value = mock_orch_result
            MockMerger.return_value.merge.return_value = mock_merge_result

            runner = CliRunner()
            result = runner.invoke(
                pylsd, ["run", str(lsd_file), "--no-rank"], catch_exceptions=False
            )

        assert result.exit_code == 0, (
            f"Expected exit 0 for empty solutions, got {result.exit_code}. Output: {result.output}"
        )
        assert "No solutions" in result.output

    def test_k_gt_3_exits_1(self, tmp_path):
        """Orchestrator raising ValueError (K > 3) must produce exit 1."""
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text("; minimal\nEXIT\n")

        with (
            patch("ailsa.cli.pylsd.PyLSDOrchestrator") as MockOrch,
            patch("ailsa.cli.pylsd.SolutionMerger"),
            patch("ailsa.cli.pylsd.LSDRunner.is_available", return_value=True),
        ):
            MockOrch.return_value.run.side_effect = ValueError(
                "Too many suspect correlations: 4. Maximum is 3."
            )

            runner = CliRunner()
            result = runner.invoke(
                pylsd, ["run", str(lsd_file), "--no-rank"]
            )

        assert result.exit_code == 1, (
            f"Expected exit 1 for K>3, got {result.exit_code}. Output: {result.output}"
        )

    def test_lsd_unavailable_exits_1(self, tmp_path):
        """LSDRunner.is_available() returning False must produce exit 1."""
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text("; minimal\nEXIT\n")

        with patch("ailsa.cli.pylsd.LSDRunner.is_available", return_value=False):
            runner = CliRunner()
            result = runner.invoke(pylsd, ["run", str(lsd_file), "--no-rank"])

        assert result.exit_code == 1, (
            f"Expected exit 1 when LSD unavailable, got {result.exit_code}. Output: {result.output}"
        )
        assert "LSD" in result.output


# ---------------------------------------------------------------------------
# TestSuspectExtraction: D-13 inventory/grep fallback logic
# ---------------------------------------------------------------------------


class TestSuspectExtraction:
    """Tests for _extract_suspects D-13/D-13a/D-13b/D-13c branching."""

    def test_inventory_primary_used(self, tmp_path):
        """LSD file with v2 block with deferred_4j must extract suspects from inventory (D-13)."""
        inventory_json = _minimal_v2_inventory_json(
            deferred_4j=[
                _make_deferred_4j_entry(4, 8),
                _make_deferred_4j_entry(6, 9),
            ]
        )
        lsd_content = _make_v2_lsd_content(
            inventory_json,
            lsd_commands="MULT 1 C 2 0\nHMBC 4 8\nHMBC 6 9\n",
        )
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text(lsd_content)

        suspects = _extract_suspects(lsd_file)

        assert len(suspects) == 2, f"Expected 2 suspects, got {len(suspects)}: {suspects}"
        pairs = {(s.atom1_index, s.atom2_index) for s in suspects}
        assert (4, 8) in pairs
        assert (6, 9) in pairs

    def test_elim_annotation_mismatch_exits_1(self, tmp_path):
        """Mismatch between inventory deferred_4j and ; ELIM annotations must exit 1 (D-13a)."""
        inventory_json = _minimal_v2_inventory_json(
            deferred_4j=[_make_deferred_4j_entry(4, 8)]
        )
        # Inventory says (4,8) but the ; ELIM annotation says (5,9)
        lsd_content = _make_v2_lsd_content(
            inventory_json,
            lsd_commands="HMBC 5 9 ; ELIM\n",
        )
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text(lsd_content)

        with pytest.raises(SystemExit) as exc_info:
            _extract_suspects(lsd_file)
        assert exc_info.value.code == 1

    def test_grep_fallback_when_no_inventory(self, tmp_path):
        """No v2 block + ; ELIM annotations must emit warning and use grep fallback (D-13b)."""
        lsd_content = (
            "; Plain LSD file without inventory block\n"
            "MULT 1 C 2 0\n"
            "HMBC 4 8 ; ELIM\n"
            "HMBC 6 9 ; ELIM\n"
        )
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text(lsd_content)

        suspects = _extract_suspects(lsd_file)

        assert len(suspects) == 2, f"Expected 2 suspects from grep fallback, got {len(suspects)}: {suspects}"
        pairs = {(s.atom1_index, s.atom2_index) for s in suspects}
        assert (4, 8) in pairs
        assert (6, 9) in pairs

    def test_single_run_when_both_empty(self, tmp_path):
        """No block + no ; ELIM must emit warning and return empty list (single-run, D-13c)."""
        lsd_content = "; Plain LSD file, no suspects\nMULT 1 C 2 0\n"
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text(lsd_content)

        suspects = _extract_suspects(lsd_file)

        assert suspects == [], f"Expected empty suspects list, got: {suspects}"


# ---------------------------------------------------------------------------
# TestRankingIntegration: _perform_ranking called as Python function (D-14)
# ---------------------------------------------------------------------------


class TestRankingIntegration:
    """Verify _perform_ranking is called as a Python function (not subprocess)."""

    def test_perform_ranking_called_not_subprocess(self, tmp_path):
        """With --shifts provided, _perform_ranking must be called with correct args."""
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text("; minimal\nEXIT\n")

        merged_solution = MagicMock(spec=MergedSolution)
        merged_solution.canonical_smiles = "CC"
        mock_orch_result, mock_merge_result = _make_mock_results(
            tmp_path, merged_solutions=[merged_solution]
        )

        with (
            patch("ailsa.cli.pylsd.PyLSDOrchestrator") as MockOrch,
            patch("ailsa.cli.pylsd.SolutionMerger") as MockMerger,
            patch("ailsa.cli.pylsd.LSDRunner.is_available", return_value=True),
            patch("ailsa.cli.pylsd._perform_ranking", return_value=None) as mock_rank,
        ):
            MockOrch.return_value.run.return_value = mock_orch_result
            MockMerger.return_value.merge.return_value = mock_merge_result

            runner = CliRunner()
            result = runner.invoke(
                pylsd,
                ["run", str(lsd_file), "--shifts", "180.5,140.8"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0, (
            f"Expected exit 0, got {result.exit_code}. Output: {result.output}"
        )
        mock_rank.assert_called_once()
        call_args = mock_rank.call_args
        # Verify merged_smi path was passed as first positional arg
        assert call_args[0][0] == mock_merge_result.merged_smi
        # Verify experimental shifts were parsed correctly
        assert call_args[0][1] == [180.5, 140.8]

    def test_format_json_passes_silent_true(self, tmp_path):
        """With --format json, _perform_ranking must be called with _silent=True (CR-01 fix).

        Verifies the fix that prevents double-JSON echo: pylsd_run suppresses
        the inner click.echo from _perform_ranking by passing _silent=True, then
        echoes a single outer wrapper JSON itself.
        """
        lsd_file = tmp_path / "compound.lsd"
        lsd_file.write_text("; minimal\nEXIT\n")

        merged_solution = MagicMock(spec=MergedSolution)
        merged_solution.canonical_smiles = "CC"
        mock_orch_result, mock_merge_result = _make_mock_results(
            tmp_path, merged_solutions=[merged_solution]
        )
        mock_orch_result.permutation_results = [MagicMock()]

        ranking_data = {
            "total_solutions": 1,
            "ranked_count": 1,
            "skipped_count": 0,
            "experimental_shifts": [25.0],
            "tolerance": 3.0,
            "solutions": [],
            "warnings": [],
        }

        with (
            patch("ailsa.cli.pylsd.PyLSDOrchestrator") as MockOrch,
            patch("ailsa.cli.pylsd.SolutionMerger") as MockMerger,
            patch("ailsa.cli.pylsd.LSDRunner.is_available", return_value=True),
            patch("ailsa.cli.pylsd._perform_ranking", return_value=ranking_data) as mock_rank,
        ):
            MockOrch.return_value.run.return_value = mock_orch_result
            MockMerger.return_value.merge.return_value = mock_merge_result

            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                pylsd,
                ["run", str(lsd_file), "--shifts", "25.0", "--format", "json"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        mock_rank.assert_called_once()
        call_kwargs = mock_rank.call_args.kwargs
        assert call_kwargs.get("_silent") is True, (
            f"_perform_ranking must be called with _silent=True when --format json. "
            f"Actual kwargs: {call_kwargs}"
        )

        # stdout must be exactly one parseable JSON document (not two concatenated)
        data = json.loads(result.output)
        assert "permutations" in data
        assert "ranked_solutions" in data


# ---------------------------------------------------------------------------
# TestMalformedInventory: WR-01 — START without END exits 1
# ---------------------------------------------------------------------------


class TestMalformedInventory:
    """Tests for _extract_suspects and _validate_and_parse_inventory with malformed inventory."""

    def test_malformed_inventory_start_without_end_exits_1(self, tmp_path):
        """LSD file with START delimiter but no END delimiter must exit 1 (WR-01 fix)."""
        from ailsa.cli.lsd import _validate_and_parse_inventory

        # Construct a file that has the START delimiter but no END delimiter
        lsd_content = (
            "; === CONSTRAINT INVENTORY v2 ===\n"
            '; { "version": 2,\n'
            ';   "truncated": true\n'
            "; -- file was truncated before END delimiter --\n"
            "MULT 1 C 2 0\n"
        )
        lsd_file = tmp_path / "truncated.lsd"
        lsd_file.write_text(lsd_content)

        with pytest.raises(SystemExit) as exc_info:
            _validate_and_parse_inventory(lsd_file)
        assert exc_info.value.code == 1

    def test_absent_inventory_returns_none(self, tmp_path):
        """LSD file with no inventory block at all must return None (not an error)."""
        from ailsa.cli.lsd import _validate_and_parse_inventory

        lsd_content = "; Plain LSD file without any inventory\nMULT 1 C 2 0\n"
        lsd_file = tmp_path / "no_inventory.lsd"
        lsd_file.write_text(lsd_content)

        result = _validate_and_parse_inventory(lsd_file)
        assert result is None

    def test_extract_suspects_propagates_malformed_exit(self, tmp_path):
        """_extract_suspects must propagate SystemExit(1) for malformed inventory (WR-01)."""
        lsd_content = (
            "; === CONSTRAINT INVENTORY v2 ===\n"
            '; { "version": 2, "truncated": true\n'
            "MULT 1 C 2 0\n"
        )
        lsd_file = tmp_path / "truncated.lsd"
        lsd_file.write_text(lsd_content)

        with pytest.raises(SystemExit) as exc_info:
            _extract_suspects(lsd_file)
        assert exc_info.value.code == 1
