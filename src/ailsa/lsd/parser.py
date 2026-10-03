"""Parser for LSD input and output files."""

import re
from dataclasses import dataclass
from pathlib import Path

from ailsa.lsd.models import Hybridization, LSDAtom, LSDCorrelation, LSDProblem


@dataclass
class LSDSolution:
    """Single solution from LSD.

    Represents one possible molecular structure found by LSD/outlsd.

    Attributes:
        index: Solution number (1-based)
        smiles: SMILES string for the structure
    """

    index: int
    smiles: str

    def summary(self) -> str:
        """Return a summary of the solution."""
        return f"Solution {self.index}: {self.smiles}"


class LSDOutputParser:
    """Parse LSD/outlsd output files.

    The primary input for ranking is a SMILES file produced by outlsd,
    containing one SMILES string per line.
    """

    @staticmethod
    def parse_smiles_file(smiles_path: Path | str) -> list[LSDSolution]:
        """Parse a SMILES file with one SMILES per line.

        This is the standard output format from outlsd. Each line contains
        one SMILES string representing an LSD solution.

        Args:
            smiles_path: Path to SMILES file (e.g., outlsd.out)

        Returns:
            List of LSDSolution objects, indexed 1, 2, 3, ...
        """
        smiles_path = Path(smiles_path)
        if not smiles_path.exists():
            raise FileNotFoundError(f"SMILES file not found: {smiles_path}")

        content = smiles_path.read_text()
        solutions = []

        for line in content.strip().split("\n"):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            # Basic SMILES validation: contains letters and possibly brackets, numbers, etc.
            if re.match(r"^[A-Za-z0-9@\[\]\(\)=#\-\+\\/\.]+$", line):
                solutions.append(
                    LSDSolution(index=len(solutions) + 1, smiles=line)
                )

        return solutions

    @staticmethod
    def parse_summary_output(output: str) -> dict:
        """Parse LSD summary output for statistics.

        Args:
            output: LSD stdout content

        Returns:
            Dictionary with parsed statistics
        """
        stats = {
            "solution_count": 0,
            "execution_time": None,
            "status": "unknown",
        }

        # Look for solution count
        count_match = re.search(r"(\d+)\s+solution", output.lower())
        if count_match:
            stats["solution_count"] = int(count_match.group(1))

        # Look for timing information
        time_match = re.search(r"(\d+\.?\d*)\s*(sec|second|ms)", output.lower())
        if time_match:
            stats["execution_time"] = float(time_match.group(1))

        # Determine status
        if "error" in output.lower():
            stats["status"] = "error"
        elif "no solution" in output.lower():
            stats["status"] = "no_solution"
        elif stats["solution_count"] > 0:
            stats["status"] = "success"

        return stats

    @staticmethod
    def solutions_to_smiles_list(solutions: list[LSDSolution]) -> list[str]:
        """Extract SMILES strings from solutions.

        Args:
            solutions: List of parsed solutions

        Returns:
            List of SMILES strings
        """
        return [s.smiles for s in solutions]


class LSDInputParser:
    """Parse LSD input files (.lsd format).

    This parser extracts structural constraints from LSD input files,
    including atom definitions (MULT) and correlations (HSQC, HMBC, COSY).
    """

    @staticmethod
    def parse_file(lsd_path: Path | str) -> LSDProblem:
        """Parse an LSD input file into an LSDProblem.

        This is a simple parser for LSD input format that extracts:
        - MULT commands (atom definitions)
        - HSQC correlations
        - HMBC correlations
        - COSY correlations

        Args:
            lsd_path: Path to .lsd input file

        Returns:
            LSDProblem object
        """
        lsd_path = Path(lsd_path)
        content = lsd_path.read_text()
        problem = LSDProblem(name=lsd_path.stem)

        for line in content.split("\n"):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith(";"):
                continue

            parts = line.split()
            if not parts:
                continue

            cmd = parts[0].upper()

            if cmd == "MULT" and len(parts) >= 5:
                # MULT atom_num element hybridization h_count [charge]
                try:
                    index = int(parts[1])
                    element = parts[2]
                    hyb_val = int(parts[3])
                    h_count = int(parts[4])
                    charge = int(parts[5]) if len(parts) > 5 else 0

                    hyb_map = {1: Hybridization.SP, 2: Hybridization.SP2, 3: Hybridization.SP3}
                    hybridization = hyb_map.get(hyb_val, Hybridization.SP3)

                    atom = LSDAtom(
                        index=index,
                        element=element,
                        hybridization=hybridization,
                        hydrogen_count=h_count,
                        charge=charge,
                    )
                    problem.add_atom(atom)
                except (ValueError, IndexError):
                    pass

            elif cmd in ("HSQC", "HMQC") and len(parts) >= 3:
                # HSQC carbon_idx proton_idx
                try:
                    atom1 = int(parts[1])
                    atom2 = int(parts[2])
                    corr = LSDCorrelation(
                        atom1_index=atom1,
                        atom2_index=atom2,
                        correlation_type="HSQC",
                    )
                    problem.add_correlation(corr)
                except ValueError:
                    pass

            elif cmd == "HMBC" and len(parts) >= 3:
                # HMBC carbon_idx proton_idx
                try:
                    atom1 = int(parts[1])
                    atom2 = int(parts[2])
                    corr = LSDCorrelation(
                        atom1_index=atom1,
                        atom2_index=atom2,
                        correlation_type="HMBC",
                    )
                    problem.add_correlation(corr)
                except ValueError:
                    pass

            elif cmd == "COSY" and len(parts) >= 3:
                # COSY h_idx1 h_idx2
                try:
                    atom1 = int(parts[1])
                    atom2 = int(parts[2])
                    corr = LSDCorrelation(
                        atom1_index=atom1,
                        atom2_index=atom2,
                        correlation_type="COSY",
                    )
                    problem.add_correlation(corr)
                except ValueError:
                    pass

        return problem
