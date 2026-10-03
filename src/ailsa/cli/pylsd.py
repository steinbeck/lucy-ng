"""CLI commands for PyLSD multi-run orchestration."""

import json
import re
from pathlib import Path

import click

from ailsa.cli.lsd import _perform_ranking, _validate_and_parse_inventory
from ailsa.lsd import LSDRunner
from ailsa.lsd.models import LSDCorrelation
from ailsa.lsd.orchestrator import PyLSDOrchestrator, SolutionMerger
from ailsa.lsd.parser import LSDInputParser


# ---------------------------------------------------------------------------
# Module-level helper: suspect extraction (D-13/D-13a/D-13b/D-13c)
# ---------------------------------------------------------------------------


def _extract_suspects(lsd_path: str | Path) -> list[LSDCorrelation]:
    """Extract suspect 4J HMBC correlations from an LSD file.

    Implements the D-13 suspect resolution chain:
    1. (D-13) Read v2 inventory block → use deferred_4j pairs as suspects.
       Cross-check against ; ELIM annotations (D-13a): if both present and
       they disagree, raise SystemExit(1) with a mismatch error.
    2. (D-13b) If no inventory block: grep lsd_content for ; ELIM annotations
       and emit a warning, using those pairs as suspects.
    3. (D-13c) If both are empty: emit warning, return empty list (single-run).

    For each suspect pair found, the function tries to retrieve the matching
    LSDCorrelation from the parsed problem (to preserve bond range settings).
    If the pair is not present in the parsed correlations, a new LSDCorrelation
    is constructed with default HMBC bond range.

    Args:
        lsd_path: Path to the LSD input file.

    Returns:
        List of LSDCorrelation objects representing suspect 4J HMBC correlations.

    Raises:
        SystemExit(1): On v1 inventory detected, parse/schema failure (from
            _validate_and_parse_inventory), or inventory/annotation mismatch (D-13a).
    """
    lsd_path = Path(lsd_path)
    content = lsd_path.read_text(encoding="utf-8")

    # --- D-13: Try inventory block first ---
    inventory = _validate_and_parse_inventory(lsd_path)

    # --- Grep for ; ELIM annotations (used for cross-check and fallback) ---
    # Pattern: HMBC <atom1> <atom2> [optional bond range] ; ELIM
    elim_pattern = re.compile(r"^HMBC\s+(\d+)\s+(\d+).*;\s*ELIM", re.MULTILINE)
    elim_pairs = [
        (int(m.group(1)), int(m.group(2)))
        for m in elim_pattern.finditer(content)
    ]

    if inventory is not None:
        # D-13: use deferred_4j from inventory
        deferred = inventory.get("deferred_4j", [])
        inventory_pairs = [(entry["atom1"], entry["atom2"]) for entry in deferred]

        # D-13a: cross-check with ; ELIM annotations if both are non-empty
        if inventory_pairs and elim_pairs:
            inv_set = set(inventory_pairs)
            elim_set = set(elim_pairs)
            if inv_set != elim_set:
                click.echo(
                    "Error: Mismatch between inventory deferred_4j and ; ELIM annotations. "
                    f"Inventory pairs: {sorted(inv_set)}. "
                    f"; ELIM pairs: {sorted(elim_set)}. "
                    "Reconcile the LSD file before running pylsd.",
                    err=True,
                )
                raise SystemExit(1)

        suspect_pairs = inventory_pairs
    else:
        # No inventory block
        if elim_pairs:
            # D-13b: grep fallback
            click.echo(
                "Warning: No v2 inventory block found. "
                "Using ; ELIM annotations as suspect correlations (D-13b).",
                err=True,
            )
            suspect_pairs = elim_pairs
        else:
            # D-13c: both empty — single-run with no suspects
            click.echo(
                "Warning: No v2 inventory block and no ; ELIM annotations found. "
                "Running single LSD pass with no suspect correlations (D-13c).",
                err=True,
            )
            suspect_pairs = []

    if not suspect_pairs:
        return []

    # Resolve pairs to LSDCorrelation objects via parser
    base_problem = LSDInputParser.parse_file(lsd_path)
    parsed_hmbc = {
        (c.atom1_index, c.atom2_index): c
        for c in base_problem.correlations
        if c.correlation_type == "HMBC"
    }

    result: list[LSDCorrelation] = []
    for a1, a2 in suspect_pairs:
        if (a1, a2) in parsed_hmbc:
            result.append(parsed_hmbc[(a1, a2)])
        else:
            # Pair not found in parsed correlations — construct directly
            result.append(
                LSDCorrelation(
                    atom1_index=a1,
                    atom2_index=a2,
                    correlation_type="HMBC",
                )
            )

    return result


# ---------------------------------------------------------------------------
# Click group
# ---------------------------------------------------------------------------


@click.group()
def pylsd() -> None:
    """PyLSD multi-run orchestration for 4J HMBC handling."""
    pass


# ---------------------------------------------------------------------------
# pylsd run command
# ---------------------------------------------------------------------------


@pylsd.command("run")
@click.argument("lsd_file", type=click.Path(exists=True))
@click.option(
    "--shifts",
    type=str,
    default=None,
    help="Comma-separated 13C shifts in ppm.",
)
@click.option(
    "--no-rank",
    is_flag=True,
    default=False,
    help="Skip ranking; print output file paths.",
)
@click.option(
    "--working-dir",
    type=click.Path(),
    default=None,
    help="Directory for permutation files. Defaults to <lsd_file_dir>/pylsd_run.",
)
@click.option(
    "--timeout",
    type=int,
    default=120,
    help="Per-permutation LSD timeout in seconds.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def pylsd_run(
    lsd_file: str,
    shifts: str | None,
    no_rank: bool,
    working_dir: str | None,
    timeout: int,
    output_format: str,
) -> None:
    """Run PyLSD orchestration (DEPRECATED — use ailsa lsd run with ELIM escalation per D-05)."""
    click.echo(
        "Warning: ailsa pylsd run is deprecated (Phase 80 D-05). "
        "Use ailsa lsd run with ELIM escalation instead. "
        "See .planning/phases/80-long-range-4j-hmbc-connectivity-defect/80-CONTEXT.md",
        err=True,
    )
    # --- Guard: LSD must be available ---
    if not LSDRunner.is_available():
        click.echo("Error: LSD is not installed or not in PATH", err=True)
        raise SystemExit(1)

    # --- D-14b: --shifts required when ranking is active ---
    if not no_rank and not shifts:
        click.echo(
            "Error: --shifts is required unless --no-rank is specified.",
            err=True,
        )
        raise SystemExit(1)

    lsd_path = Path(lsd_file)

    # --- D-13: Extract suspect correlations ---
    suspect_correlations = _extract_suspects(lsd_path)

    # --- Parse base problem ---
    base_problem = LSDInputParser.parse_file(lsd_path)

    # --- Resolve working directory ---
    if working_dir is not None:
        output_dir = Path(working_dir)
    else:
        output_dir = lsd_path.parent / "pylsd_run"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Orchestrate: 2^K permutation runs ---
    try:
        orch_result = PyLSDOrchestrator(timeout=timeout).run(
            base_problem, suspect_correlations, output_dir
        )
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

    # --- Merge: deduplicate solutions across permutations ---
    merge_result = SolutionMerger().merge(orch_result.permutation_results, output_dir)

    # --- Check for empty solution set (exit 0 per CASE workflow) ---
    if not merge_result.merged_solutions:
        click.echo("No solutions found after merging permutation results.")
        return

    # --- --no-rank: just print file paths ---
    if no_rank:
        click.echo(str(merge_result.merged_smi))
        click.echo(str(merge_result.run_report))
        return

    # --- Parse shifts (T-69-02-01: guarded float parse) ---
    assert shifts is not None  # guaranteed by D-14b guard above
    try:
        experimental_shifts = [float(s.strip()) for s in shifts.split(",")]
    except ValueError:
        click.echo(
            "Error: Invalid shifts format. Use comma-separated numbers.",
            err=True,
        )
        raise SystemExit(1)

    # --- Rank via _perform_ranking (D-14: direct Python call, no subprocess) ---
    K = len(orch_result.permutation_results)
    N = len(merge_result.merged_solutions)

    if output_format == "json":
        # Pass _silent=True to suppress the inner click.echo from _perform_ranking;
        # we echo the outer D-14c wrapper below instead (CR-01 fix).
        rank_data = _perform_ranking(
            merge_result.merged_smi,
            experimental_shifts,
            output_format="json",
            _silent=True,
        )
        # Wrap in outer D-14c shape
        outer: dict = {
            "permutations": K,
            "merged_count": N,
            "ranked_solutions": rank_data["solutions"] if rank_data else [],
            "run_report_path": str(merge_result.run_report),
        }
        click.echo(json.dumps(outer, indent=2))
    else:
        # _perform_ranking echoes text output internally, returns None
        _perform_ranking(
            merge_result.merged_smi,
            experimental_shifts,
            output_format="text",
        )
