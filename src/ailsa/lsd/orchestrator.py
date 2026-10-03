"""PyLSDOrchestrator: multi-run permutation engine for 4J HMBC handling.

This module implements v8.0 pyLSD-style orchestration directly in Python.
It generates 2^K LSD input files (each including/excluding a different
combination of suspect 4J HMBC correlations), runs LSD on each, converts
solutions via outlsd, and collects results.

SolutionMerger deduplicates structures across runs using InChI canonicalization
and writes a provenance-rich run_report.json.

Classes:
    PermutationResult   -- Result of one LSD run (one permutation)
    OrchestrationResult -- Aggregated result from all permutations
    MergedSolution      -- One unique solution after deduplication
    MergeResult         -- Result from SolutionMerger.merge()
    PyLSDOrchestrator   -- Generates permutations, runs LSD, collects SMILES
    SolutionMerger      -- Deduplicates solutions across permutation runs
"""

import copy
import itertools
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ailsa.lsd.generator import LSDInputGenerator
from ailsa.lsd.models import LSDCorrelation, LSDProblem
from ailsa.lsd.parser import LSDOutputParser
from ailsa.lsd.runner import LSDResult, LSDRunner, _invoke_outlsd


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class PermutationResult:
    """Result of running LSD on one permutation of the problem.

    Attributes:
        perm_index: Sequential index of this permutation (0-based)
        include_flags: Boolean list — True = suspect included with max_bonds=4
        suspect_correlations: The full list of suspect correlations
        lsd_result: Result object from LSDRunner.run_file()
        smiles_file: Path to solutions.smi (or None if outlsd not available)
        perm_dir: Directory containing this permutation's files
    """

    perm_index: int
    include_flags: list[bool]
    suspect_correlations: list[LSDCorrelation]
    lsd_result: LSDResult
    smiles_file: Path | None
    perm_dir: Path


@dataclass
class OrchestrationResult:
    """Aggregated result from all permutation runs.

    Attributes:
        base_problem: The original LSDProblem before permutation
        suspect_correlations: The suspect correlations that were permuted
        permutation_results: One PermutationResult per permutation
        output_dir: Root directory for all permutation subdirectories
    """

    base_problem: LSDProblem
    suspect_correlations: list[LSDCorrelation]
    permutation_results: list[PermutationResult]
    output_dir: Path


@dataclass
class MergedSolution:
    """A unique solution after InChI-based deduplication.

    Attributes:
        inchi_key: 27-character InChI key used as canonical identifier
        canonical_smiles: RDKit canonical SMILES for this structure
        provenance: List of dicts recording which permutation(s) produced this
    """

    inchi_key: str
    canonical_smiles: str
    provenance: list[dict] = field(default_factory=list)


@dataclass
class MergeResult:
    """Result of SolutionMerger.merge().

    Attributes:
        merged_solutions: Unique structures across all permutations
        merged_smi: Path to merged.smi (one canonical SMILES per line)
        run_report: Path to run_report.json (provenance report)
    """

    merged_solutions: list[MergedSolution]
    merged_smi: Path
    run_report: Path


# ---------------------------------------------------------------------------
# PyLSDOrchestrator
# ---------------------------------------------------------------------------


class PyLSDOrchestrator:
    """Multi-run permutation engine for 4J HMBC orchestration.

    Takes a base LSDProblem with suspect 4J HMBC correlations and:
    1. Validates K ≤ 3 (raises ValueError otherwise)
    2. Generates 2^K permutation LSD files (each including/excluding suspects)
    3. Runs LSD on each permutation directory
    4. Converts solutions to SMILES via the shared runner._invoke_outlsd helper
    5. Returns OrchestrationResult with all PermutationResult objects

    Solution conversion delegates to the single shared `_invoke_outlsd` helper
    in runner.py (unified in Phase 73; the earlier per-class outlsd bug is fixed).
    """

    def __init__(
        self,
        lsd_path: str | Path | None = None,
        timeout: int = 120,
    ) -> None:
        """Create orchestrator.

        Args:
            lsd_path: Path to LSD executable. None = auto-detect via PATH.
            timeout: Per-permutation LSD timeout in seconds (default: 120).
        """
        self.runner = LSDRunner(lsd_path)
        self.timeout = timeout

    def run(
        self,
        base_problem: LSDProblem,
        suspect_correlations: list[LSDCorrelation],
        output_dir: Path,
    ) -> OrchestrationResult:
        """Run permutation orchestration.

        Generates 2^K LSD runs, each with a different include/exclude
        combination of the suspect correlations.

        Args:
            base_problem: The complete LSD problem (not mutated).
            suspect_correlations: Correlations suspected as 4J HMBCs.
            output_dir: Root directory; perm_00/, perm_01/, ... created here.

        Returns:
            OrchestrationResult with all permutation results.

        Raises:
            ValueError: If len(suspect_correlations) > 3.
        """
        K = len(suspect_correlations)
        # CRITICAL: check K FIRST before any directory creation (Pitfall 4)
        if K > 3:
            raise ValueError(
                f"Too many suspect correlations: {K}. "
                f"Maximum is 3 (2^3=8 permutations). "
                f"Reduce the number of suspect correlations or handle them manually."
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        permutation_results: list[PermutationResult] = []

        # itertools.product([True, False], repeat=K) yields 2^K tuples
        # K=0 yields [()], producing exactly one run with unchanged base problem
        for perm_idx, include_flags in enumerate(
            itertools.product([True, False], repeat=K)
        ):
            perm_problem = self._build_permutation(
                base_problem, suspect_correlations, include_flags
            )
            perm_dir = output_dir / f"perm_{perm_idx:02d}"
            perm_dir.mkdir(exist_ok=True)

            # Write LSD input file for this permutation
            lsd_file = perm_dir / f"{base_problem.name}.lsd"
            LSDInputGenerator.write_file(perm_problem, lsd_file)

            # Run LSD (may fail if binary not available — handled by runner)
            lsd_result = self.runner.run_file(
                lsd_file, output_dir=perm_dir, timeout=self.timeout
            )

            # Convert solutions to SMILES via outlsd (bypass buggy _run_outlsd)
            smiles_file = self._run_outlsd(perm_dir, lsd_file)

            permutation_results.append(
                PermutationResult(
                    perm_index=perm_idx,
                    include_flags=list(include_flags),
                    suspect_correlations=suspect_correlations,
                    lsd_result=lsd_result,
                    smiles_file=smiles_file,
                    perm_dir=perm_dir,
                )
            )

        return OrchestrationResult(
            base_problem=base_problem,
            suspect_correlations=suspect_correlations,
            permutation_results=permutation_results,
            output_dir=output_dir,
        )

    def _build_permutation(
        self,
        base_problem: LSDProblem,
        suspects: list[LSDCorrelation],
        include_flags: tuple[bool, ...],
    ) -> LSDProblem:
        """Clone base problem and apply one permutation's include/exclude flags.

        Args:
            base_problem: Original problem (not mutated).
            suspects: Suspect correlations to include/exclude.
            include_flags: One bool per suspect; True = include with max_bonds=4.

        Returns:
            New LSDProblem with this permutation's correlation set.
        """
        perm = copy.deepcopy(base_problem)

        # Identify suspects by value tuple, NOT by id() (deepcopy breaks id())
        suspect_keys = {
            (s.atom1_index, s.atom2_index, s.correlation_type)
            for s in suspects
        }

        # Remove all suspect correlations from the clone
        perm.correlations = [
            c
            for c in perm.correlations
            if (c.atom1_index, c.atom2_index, c.correlation_type) not in suspect_keys
        ]

        # Add back suspects that are flagged True, with extended bond range
        for corr, include in zip(suspects, include_flags):
            if include:
                included_corr = copy.deepcopy(corr)
                included_corr.max_bonds = 4  # Extended range for 4J suspects
                perm.correlations.append(included_corr)

        return perm

    def _run_outlsd(self, perm_dir: Path, lsd_file: Path) -> Path | None:
        """Convert .sol to SMILES via the shared _invoke_outlsd helper.

        Delegates to runner._invoke_outlsd so there is a single correct
        implementation. Previously this was a private copy; Phase 73 unified them.

        Args:
            perm_dir: Directory containing the .sol file from LSD.
            lsd_file: Path to the LSD input file (used for context only).

        Returns:
            Path to solutions.smi if outlsd succeeded, else None.
        """
        outlsd_path = shutil.which("outlsd")
        if outlsd_path is None:
            return None
        sol_files = list(perm_dir.glob("*.sol"))
        if not sol_files:
            return None
        return _invoke_outlsd(Path(outlsd_path), sol_files[0], perm_dir)


# ---------------------------------------------------------------------------
# SolutionMerger
# ---------------------------------------------------------------------------


class SolutionMerger:
    """Deduplicate LSD solutions across multiple permutation runs.

    Uses InChI key as the canonical identifier — more robust than canonical
    SMILES for handling tautomers and stereochemistry variants.

    Writes:
    - merged.smi: One canonical SMILES per unique structure
    - run_report.json: Provenance data (which permutations produced each structure)
    """

    def merge(
        self,
        permutation_results: list[PermutationResult],
        output_dir: Path,
    ) -> MergeResult:
        """Merge and deduplicate solutions from all permutation results.

        Args:
            permutation_results: List of PermutationResult from orchestration.
            output_dir: Directory to write merged.smi and run_report.json.

        Returns:
            MergeResult with merged solutions, file paths, and report.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        seen: dict[str, MergedSolution] = {}

        for perm_result in permutation_results:
            if perm_result.smiles_file is None or not perm_result.smiles_file.exists():
                continue

            solutions = LSDOutputParser.parse_smiles_file(perm_result.smiles_file)
            for solution in solutions:
                inchi_key = self._smiles_to_inchi_key(solution.smiles)
                if inchi_key is None:
                    continue

                # Build provenance entry with required fields per ORCH-04
                provenance_entry = {
                    "perm_index": perm_result.perm_index,
                    "include_flags": perm_result.include_flags,
                    "original_solution_index": solution.index,
                    "active_correlations": [
                        {
                            "atom1": c.atom1_index,
                            "atom2": c.atom2_index,
                        }
                        for c, included in zip(
                            perm_result.suspect_correlations,
                            perm_result.include_flags,
                        )
                        if included
                    ],
                }

                if inchi_key not in seen:
                    canonical_smiles = self._canonicalize(solution.smiles)
                    seen[inchi_key] = MergedSolution(
                        inchi_key=inchi_key,
                        canonical_smiles=canonical_smiles or solution.smiles,
                        provenance=[provenance_entry],
                    )
                else:
                    seen[inchi_key].provenance.append(provenance_entry)

        merged_solutions = list(seen.values())

        # Write merged.smi — one canonical SMILES per unique structure
        merged_smi = output_dir / "merged.smi"
        valid_smiles = [s.canonical_smiles for s in merged_solutions if s.canonical_smiles]
        merged_smi.write_text("\n".join(valid_smiles))

        # Count total raw solutions from all permutations
        total_raw = 0
        for p in permutation_results:
            if p.smiles_file and p.smiles_file.exists():
                try:
                    total_raw += len(LSDOutputParser.parse_smiles_file(p.smiles_file))
                except Exception:
                    pass

        # Write run_report.json with provenance
        report: dict = {
            "total_permutations": len(permutation_results),
            "total_raw_solutions": total_raw,
            "unique_solutions": len(merged_solutions),
            "solutions": [
                {
                    "inchi_key": s.inchi_key,
                    "smiles": s.canonical_smiles,
                    "provenance": s.provenance,
                }
                for s in merged_solutions
            ],
        }
        report_file = output_dir / "run_report.json"
        report_file.write_text(json.dumps(report, indent=2))

        return MergeResult(
            merged_solutions=merged_solutions,
            merged_smi=merged_smi,
            run_report=report_file,
        )

    def _smiles_to_inchi_key(self, smiles: str) -> str | None:
        """Convert SMILES to InChI key for deduplication.

        Args:
            smiles: SMILES string to convert.

        Returns:
            InChI key string, or None if conversion fails.
        """
        try:
            from rdkit import Chem
            from rdkit.Chem.inchi import InchiToInchiKey, MolToInchi

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return None
            inchi = MolToInchi(mol)
            if inchi is None:
                return None
            return InchiToInchiKey(inchi)
        except Exception:
            return None

    def _canonicalize(self, smiles: str) -> str | None:
        """Get canonical SMILES via RDKit.

        Args:
            smiles: Input SMILES string.

        Returns:
            Canonical SMILES, or None if conversion fails.
        """
        try:
            from rdkit import Chem

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return None
            return Chem.MolToSmiles(mol)
        except Exception:
            return None
