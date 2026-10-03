"""NMRShiftDB loader for 13C reference spectra."""

import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors


class HydrogenCount(IntEnum):
    """Number of attached hydrogens (from J-coupling/DEPT)."""

    C = 0  # Quaternary carbon (singlet)
    CH = 1  # Methine (doublet)
    CH2 = 2  # Methylene (triplet)
    CH3 = 3  # Methyl (quartet)


# Mapping from nmrshiftdb multiplicity codes to HydrogenCount
# Based on n+1 rule: S=singlet(0H), D=doublet(1H), T=triplet(2H), Q=quartet(3H)
MULT_TO_HCOUNT: dict[str, HydrogenCount] = {
    "S": HydrogenCount.C,
    "D": HydrogenCount.CH,
    "T": HydrogenCount.CH2,
    "Q": HydrogenCount.CH3,
}


@dataclass
class CarbonSignal:
    """A single 13C signal with shift and optional DEPT info."""

    shift: float  # Chemical shift in ppm
    hydrogen_count: HydrogenCount | None = None  # From DEPT, None if unknown
    atom_index: int | None = None  # Reference to MOL atom numbering


@dataclass
class NMRShiftDBEntry:
    """A compound entry from nmrshiftdb with 13C spectrum."""

    nmrshiftdb_id: int
    name: str
    molecular_formula: str
    carbon_count: int
    inchi: str
    inchi_key: str
    signals: list[CarbonSignal] = field(default_factory=list)

    @property
    def shifts(self) -> list[float]:
        """Return just the shift values for simple matching."""
        return [s.shift for s in self.signals]


class NMRShiftDBLoader:
    """Loader for nmrshiftdb SD file data."""

    def __init__(self, sd_file_path: str | Path):
        """Initialize with path to SD file.

        Args:
            sd_file_path: Path to nmrshiftdb SD file with 13C spectra
        """
        self.sd_file_path = Path(sd_file_path)
        self._entries: list[NMRShiftDBEntry] = []
        self._formula_index: dict[str, list[NMRShiftDBEntry]] = {}
        self._loaded = False

    def load(self) -> list[NMRShiftDBEntry]:
        """Parse SD file and return all entries with 13C spectra.

        Returns:
            List of NMRShiftDBEntry objects with 13C spectrum data
        """
        if self._loaded:
            return self._entries

        if not self.sd_file_path.exists():
            raise FileNotFoundError(f"SD file not found: {self.sd_file_path}")

        supplier = Chem.SDMolSupplier(str(self.sd_file_path))
        entry_id = 0

        for mol in supplier:
            if mol is None:
                continue

            # Check for 13C spectrum data
            spectrum_field = mol.GetProp("Spectrum 13C 0") if mol.HasProp("Spectrum 13C 0") else None
            if not spectrum_field:
                continue

            # Parse spectrum
            signals = self.parse_spectrum_field(spectrum_field)
            if not signals:
                continue

            # Get molecule name (from SD file header)
            name = mol.GetProp("_Name") if mol.HasProp("_Name") else ""

            # Get InChI info
            inchi = mol.GetProp("INChI") if mol.HasProp("INChI") else ""
            inchi_key = mol.GetProp("INChI key") if mol.HasProp("INChI key") else ""

            # Get molecular formula from InChI (more reliable than CalcMolFormula)
            mol_formula = self._extract_formula_from_inchi(inchi)
            if not mol_formula:
                # Fallback to RDKit calculation (may be missing hydrogens)
                mol_formula = rdMolDescriptors.CalcMolFormula(mol)

            # Count carbons from formula
            carbon_count = self.count_carbons(mol_formula)

            entry = NMRShiftDBEntry(
                nmrshiftdb_id=entry_id,
                name=name,
                molecular_formula=mol_formula,
                carbon_count=carbon_count,
                inchi=inchi,
                inchi_key=inchi_key,
                signals=signals,
            )
            self._entries.append(entry)

            # Index by formula
            normalized_formula = self._normalize_formula(mol_formula)
            if normalized_formula not in self._formula_index:
                self._formula_index[normalized_formula] = []
            self._formula_index[normalized_formula].append(entry)

            entry_id += 1

        self._loaded = True
        return self._entries

    def get_by_formula(self, formula: str) -> list[NMRShiftDBEntry]:
        """Get all entries matching a molecular formula.

        Args:
            formula: Molecular formula (e.g., "C13H18O2")

        Returns:
            List of entries with matching molecular formula
        """
        if not self._loaded:
            self.load()

        normalized = self._normalize_formula(formula)
        return self._formula_index.get(normalized, [])

    @staticmethod
    def parse_spectrum_field(field: str) -> list[CarbonSignal]:
        """Parse nmrshiftdb spectrum field format.

        Format: 'shift;mult;atom|shift;mult;atom|...'
        Example: '17.6;0.0Q;1|22.4;0.0T;2|...'

        Multiplicity codes (n+1 rule): S=C(0H), D=CH(1H), T=CH2(2H), Q=CH3(3H)

        Args:
            field: The spectrum field string from SD file

        Returns:
            List of CarbonSignal objects
        """
        signals = []

        # Split by pipe to get individual signals
        parts = field.strip().split("|")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Split by semicolon: shift;mult;atom
            components = part.split(";")
            if len(components) < 1:
                continue

            try:
                shift = float(components[0])
            except ValueError:
                continue

            # Parse multiplicity if present
            hydrogen_count = None
            if len(components) >= 2:
                mult_str = components[1]
                # Extract letter code from format like "0.0Q" or "Q"
                match = re.search(r"([SDTQ])$", mult_str.upper())
                if match:
                    mult_code = match.group(1)
                    hydrogen_count = MULT_TO_HCOUNT.get(mult_code)

            # Parse atom index if present
            atom_index = None
            if len(components) >= 3:
                try:
                    atom_index = int(components[2])
                except ValueError:
                    pass

            signals.append(
                CarbonSignal(
                    shift=shift,
                    hydrogen_count=hydrogen_count,
                    atom_index=atom_index,
                )
            )

        return signals

    @staticmethod
    def count_carbons(formula: str) -> int:
        """Extract carbon count from molecular formula.

        Args:
            formula: Molecular formula (e.g., "C13H18O2")

        Returns:
            Number of carbons in the formula
        """
        # Match C followed by optional number, but not Cl, Ca, Co, Cr, Cu, Cs, Ce, etc.
        # Use negative lookahead to exclude other elements starting with C
        match = re.search(r"C(?![laroudsefgmnptb])(\d*)", formula)
        if not match:
            return 0

        count_str = match.group(1)
        if count_str == "":
            return 1  # Just "C" means 1 carbon
        return int(count_str)

    @staticmethod
    def _extract_formula_from_inchi(inchi: str) -> str | None:
        """Extract molecular formula from InChI string.

        InChI format: InChI=1S/C15H22O3/c.../h.../...
        The formula is the second component after the version.

        Args:
            inchi: InChI string

        Returns:
            Molecular formula or None if not extractable
        """
        if not inchi or not inchi.startswith("InChI="):
            return None

        # Split by '/' and get the formula part (second element after version)
        parts = inchi.split("/")
        if len(parts) < 2:
            return None

        # The formula is the second part (index 1)
        formula = parts[1]

        # Validate it looks like a formula (starts with element symbol)
        if not formula or not formula[0].isupper():
            return None

        return formula

    @staticmethod
    def _normalize_formula(formula: str) -> str:
        """Normalize molecular formula for consistent comparison.

        Handles subscript characters, whitespace, etc.

        Args:
            formula: Molecular formula in any format

        Returns:
            Normalized formula string
        """
        # Replace subscript digits with regular digits
        subscript_map = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
        formula = formula.translate(subscript_map)

        # Remove whitespace
        formula = formula.replace(" ", "")

        return formula
