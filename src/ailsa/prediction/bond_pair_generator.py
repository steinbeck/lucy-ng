"""Generate hetero-hetero bond pair statistics from compound database."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors
from tqdm import tqdm

from ailsa.database.models import BondPairStatsRecord, CompoundRecord

if TYPE_CHECKING:
    from ailsa.database import DatabaseManager


def extract_hetero_hetero_bonds(mol: Chem.Mol) -> set[tuple[str, str]]:
    """Extract unique heteroatom-heteroatom bond pairs from molecule.

    Only considers bonds where BOTH atoms are non-carbon and non-hydrogen.
    Pairs are canonicalized (alphabetically sorted).

    Args:
        mol: RDKit molecule

    Returns:
        Set of (element1, element2) tuples where element1 <= element2

    Examples:
        Hydrazine (H2N-NH2): {("N", "N")}
        Hydroxylamine (HO-NH2): {("N", "O")}
        Methanol (CH3-OH): set() (C-O is not hetero-hetero)
    """
    pairs = set()
    for bond in mol.GetBonds():
        begin_atom = mol.GetAtomWithIdx(bond.GetBeginAtomIdx())
        end_atom = mol.GetAtomWithIdx(bond.GetEndAtomIdx())

        elem1 = begin_atom.GetSymbol()
        elem2 = end_atom.GetSymbol()

        # Skip if either is carbon
        if elem1 == "C" or elem2 == "C":
            continue
        # Skip if either is hydrogen
        if elem1 == "H" or elem2 == "H":
            continue

        # Canonicalize pair (alphabetical order)
        pair = tuple(sorted([elem1, elem2]))
        pairs.add(pair)

    return pairs


class BondPairStatsGenerator:
    """Generate bond pair statistics from compound database."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize the generator.

        Args:
            db_manager: Database manager for compound iteration and stats insertion
        """
        self.db_manager = db_manager
        self._compounds_processed = 0
        self._compounds_failed = 0

    def generate_all(
        self, progress: bool = True
    ) -> tuple[dict[tuple[str, str, str], int], dict[str, int]]:
        """Generate bond pair statistics from all compounds.

        Args:
            progress: Show progress bar

        Returns:
            Tuple of:
            - bond_counts: {(formula_normalized, elem1, elem2): compound_count}
            - formula_totals: {formula_normalized: total_compound_count}
        """
        # Reset statistics
        self._compounds_processed = 0
        self._compounds_failed = 0

        # Aggregation dictionaries
        bond_counts: dict[tuple[str, str, str], int] = defaultdict(int)
        formula_totals: dict[str, int] = defaultdict(int)

        # Get total count for progress bar
        total = self.db_manager.get_compound_count()

        # Iterate through compounds
        compound_iter = self.db_manager.iter_compounds_with_shifts()
        if progress:
            compound_iter = tqdm(
                compound_iter,
                total=total,
                desc="Generating bond pair stats",
                unit=" compounds",
            )

        for _compound_id, smiles, _shifts in compound_iter:
            self._compounds_processed += 1

            # Parse SMILES to RDKit mol
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                self._compounds_failed += 1
                continue

            # Compute formula
            formula = rdMolDescriptors.CalcMolFormula(mol)

            # Normalize formula
            formula_norm = CompoundRecord._normalize_formula(formula)

            # Increment formula total
            formula_totals[formula_norm] += 1

            # Extract hetero-hetero bonds
            hhb_pairs = extract_hetero_hetero_bonds(mol)

            # Increment bond counts
            for elem1, elem2 in hhb_pairs:
                bond_counts[(formula_norm, elem1, elem2)] += 1

        return dict(bond_counts), dict(formula_totals)

    def populate_database(self, progress: bool = True) -> int:
        """Generate statistics and insert into database.

        Args:
            progress: Show progress bar

        Returns:
            Number of bond pair entries inserted
        """
        # Generate statistics
        bond_counts, formula_totals = self.generate_all(progress=progress)

        # Convert to BondPairStatsRecord list
        records = []
        for (formula_norm, elem1, elem2), compound_count in bond_counts.items():
            total_compounds = formula_totals[formula_norm]
            frequency = compound_count / total_compounds if total_compounds > 0 else 0.0

            records.append(
                BondPairStatsRecord(
                    formula_normalized=formula_norm,
                    element1=elem1,
                    element2=elem2,
                    compound_count=compound_count,
                    total_compounds=total_compounds,
                    frequency=frequency,
                )
            )

        # Insert into database
        count = self.db_manager.insert_bond_pair_stats_batch(records)

        return count

    @property
    def compounds_processed(self) -> int:
        """Number of compounds processed in last run."""
        return self._compounds_processed

    @property
    def compounds_failed(self) -> int:
        """Number of compounds that failed parsing in last run."""
        return self._compounds_failed
