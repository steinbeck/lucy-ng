"""COCONUT database loader for 13C reference spectra with streaming support."""

import re
from pathlib import Path

from rdkit import Chem

from .nmrshiftdb import CarbonSignal, HydrogenCount, NMRShiftDBEntry


class CoconutLoader:
    """Loader for COCONUT predicted 13C NMR SD file data.

    Supports streaming mode for large databases - only parses entries
    matching the target molecular formula instead of loading everything.
    """

    def __init__(self, sd_file_path: str | Path):
        """Initialize with path to SD file.

        Args:
            sd_file_path: Path to COCONUT SD file with predicted 13C spectra
        """
        self.sd_file_path = Path(sd_file_path)
        self._entries: list[NMRShiftDBEntry] = []
        self._formula_index: dict[str, list[NMRShiftDBEntry]] = {}
        self._loaded = False

    def load(self) -> list[NMRShiftDBEntry]:
        """Parse entire SD file and return all entries with 13C spectra.

        Warning: For large files like COCONUT (~895K entries), this loads
        everything into memory. Prefer get_by_formula() for targeted queries.

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

            entry = self._parse_mol_to_entry(mol, entry_id)
            if entry is None:
                continue

            self._entries.append(entry)

            # Index by formula
            normalized_formula = self._normalize_formula(entry.molecular_formula)
            if normalized_formula not in self._formula_index:
                self._formula_index[normalized_formula] = []
            self._formula_index[normalized_formula].append(entry)

            entry_id += 1

        self._loaded = True
        return self._entries

    def get_by_formula(self, formula: str) -> list[NMRShiftDBEntry]:
        """Get all entries matching a molecular formula using streaming.

        This method streams through the SD file and only fully parses
        entries that match the target formula. Much faster and more
        memory-efficient than load() for large databases.

        Args:
            formula: Molecular formula (e.g., "C13H18O2")

        Returns:
            List of entries with matching molecular formula
        """
        normalized = self._normalize_formula(formula)

        # If already fully loaded, use the index
        if self._loaded:
            return self._formula_index.get(normalized, [])

        # Check if we've already streamed this formula
        if normalized in self._formula_index:
            return self._formula_index[normalized]

        # Stream and filter by formula
        entries = self._stream_by_formula(normalized)
        self._formula_index[normalized] = entries
        return entries

    def _stream_by_formula(self, normalized_formula: str) -> list[NMRShiftDBEntry]:
        """Stream SD file and parse only entries matching the formula.

        Args:
            normalized_formula: Normalized molecular formula to match

        Returns:
            List of matching entries
        """
        if not self.sd_file_path.exists():
            raise FileNotFoundError(f"SD file not found: {self.sd_file_path}")

        entries: list[NMRShiftDBEntry] = []
        entry_id = 0

        # Read file and split into SD blocks
        current_block: list[str] = []

        with open(self.sd_file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                current_block.append(line)

                # End of entry marker
                if line.strip() == "$$$$":
                    block_text = "".join(current_block)

                    # Quick check: does this block contain our formula?
                    if self._block_matches_formula(block_text, normalized_formula):
                        # Parse with RDKit
                        entry = self._parse_block(block_text, entry_id)
                        if entry is not None:
                            # Double-check formula after parsing
                            if self._normalize_formula(entry.molecular_formula) == normalized_formula:
                                entries.append(entry)
                                entry_id += 1

                    current_block = []

        return entries

    def _block_matches_formula(self, block: str, normalized_formula: str) -> bool:
        """Quick check if an SD block might contain the target formula.

        Args:
            block: Raw SD file block text
            normalized_formula: Normalized formula to match

        Returns:
            True if block might contain matching formula
        """
        # Look for Formula property in the block
        # Format: >  <Formula>\nC13H18O2\n (note: variable whitespace after >)
        match = re.search(r">\s+<Formula>\n([^\n]+)", block)
        if not match:
            return False

        block_formula = self._normalize_formula(match.group(1).strip())
        return block_formula == normalized_formula

    def _parse_block(self, block: str, entry_id: int) -> NMRShiftDBEntry | None:
        """Parse a single SD block into an entry.

        Args:
            block: Raw SD file block text
            entry_id: ID to assign to this entry

        Returns:
            NMRShiftDBEntry or None if parsing fails
        """
        # Use RDKit to parse the MOL block
        mol = Chem.MolFromMolBlock(block, removeHs=False)
        if mol is None:
            return None

        # Extract properties from the text (more reliable than RDKit for some fields)
        props = self._extract_properties(block)

        # Check for 13C spectrum data
        spectrum_field = props.get("CNMR_SHIFTS", "")
        if not spectrum_field:
            return None

        # Get multiplicity info
        quaternaries = self._parse_multiplicity_field(props.get("Quaternaries", ""))
        tertiaries = self._parse_multiplicity_field(props.get("Tertiaries", ""))
        secondaries = self._parse_multiplicity_field(props.get("Secondaries", ""))
        primaries = self._parse_multiplicity_field(props.get("Primaries", ""))

        # Build atom index to multiplicity mapping
        mult_map: dict[int, HydrogenCount] = {}
        for atom_idx in quaternaries:
            mult_map[atom_idx] = HydrogenCount.C
        for atom_idx in tertiaries:
            mult_map[atom_idx] = HydrogenCount.CH
        for atom_idx in secondaries:
            mult_map[atom_idx] = HydrogenCount.CH2
        for atom_idx in primaries:
            mult_map[atom_idx] = HydrogenCount.CH3

        # Parse spectrum with multiplicity info
        signals = self._parse_coconut_spectrum(spectrum_field, mult_map)
        if not signals:
            return None

        # Get molecule name (first line of block)
        name = block.split("\n")[0].strip()

        # Get molecular formula
        mol_formula = props.get("Formula", "")
        if not mol_formula:
            return None

        # Count carbons from formula
        carbon_count = self._count_carbons(mol_formula)

        # COCONUT doesn't have InChI in the file, but we can generate it
        try:
            inchi = Chem.MolToInchi(mol) if mol else ""
        except Exception:
            inchi = ""

        try:
            inchi_key = Chem.MolToInchiKey(mol) if mol and inchi else ""
        except Exception:
            inchi_key = ""

        return NMRShiftDBEntry(
            nmrshiftdb_id=entry_id,
            name=name,
            molecular_formula=mol_formula,
            carbon_count=carbon_count,
            inchi=inchi,
            inchi_key=inchi_key,
            signals=signals,
        )

    @staticmethod
    def _extract_properties(block: str) -> dict[str, str]:
        """Extract all properties from an SD block.

        Args:
            block: Raw SD file block text

        Returns:
            Dictionary of property name to value
        """
        props: dict[str, str] = {}

        # Pattern: >  <PropertyName>\nvalue\n (note: variable whitespace, value can be multiline)
        pattern = r">\s+<([^>]+)>\n((?:(?!>\s+<)(?!\$\$\$\$).)*)"
        matches = re.findall(pattern, block, re.DOTALL)

        for name, value in matches:
            props[name.strip()] = value.strip()

        return props

    def _parse_mol_to_entry(self, mol: Chem.Mol, entry_id: int) -> NMRShiftDBEntry | None:
        """Parse an RDKit Mol object into an NMRShiftDBEntry.

        Args:
            mol: RDKit Mol object
            entry_id: ID to assign to this entry

        Returns:
            NMRShiftDBEntry or None if parsing fails
        """
        # Check for 13C spectrum data (COCONUT uses CNMR_SHIFTS)
        spectrum_field = mol.GetProp("CNMR_SHIFTS") if mol.HasProp("CNMR_SHIFTS") else None
        if not spectrum_field:
            return None

        # Get multiplicity info from separate fields
        quaternaries = self._parse_multiplicity_field(
            mol.GetProp("Quaternaries") if mol.HasProp("Quaternaries") else ""
        )
        tertiaries = self._parse_multiplicity_field(
            mol.GetProp("Tertiaries") if mol.HasProp("Tertiaries") else ""
        )
        secondaries = self._parse_multiplicity_field(
            mol.GetProp("Secondaries") if mol.HasProp("Secondaries") else ""
        )
        primaries = self._parse_multiplicity_field(
            mol.GetProp("Primaries") if mol.HasProp("Primaries") else ""
        )

        # Build atom index to multiplicity mapping
        mult_map: dict[int, HydrogenCount] = {}
        for atom_idx in quaternaries:
            mult_map[atom_idx] = HydrogenCount.C
        for atom_idx in tertiaries:
            mult_map[atom_idx] = HydrogenCount.CH
        for atom_idx in secondaries:
            mult_map[atom_idx] = HydrogenCount.CH2
        for atom_idx in primaries:
            mult_map[atom_idx] = HydrogenCount.CH3

        # Parse spectrum with multiplicity info
        signals = self._parse_coconut_spectrum(spectrum_field, mult_map)
        if not signals:
            return None

        # Get molecule name (CNP ID from header)
        name = mol.GetProp("_Name") if mol.HasProp("_Name") else ""

        # Get molecular formula directly from Formula field
        mol_formula = mol.GetProp("Formula") if mol.HasProp("Formula") else ""
        if not mol_formula:
            return None

        # Count carbons from formula
        carbon_count = self._count_carbons(mol_formula)

        # Generate InChI
        try:
            inchi = Chem.MolToInchi(mol)
        except Exception:
            inchi = ""

        try:
            inchi_key = Chem.MolToInchiKey(mol) if inchi else ""
        except Exception:
            inchi_key = ""

        return NMRShiftDBEntry(
            nmrshiftdb_id=entry_id,
            name=name,
            molecular_formula=mol_formula,
            carbon_count=carbon_count,
            inchi=inchi,
            inchi_key=inchi_key,
            signals=signals,
        )

    @staticmethod
    def _parse_coconut_spectrum(
        field: str, mult_map: dict[int, HydrogenCount]
    ) -> list[CarbonSignal]:
        """Parse COCONUT CNMR_SHIFTS field format.

        Format: 'idx:atom|shift;idx:atom|shift;...'
        Example: '0:2|73.89;1:3|101.13;2:5|154.84'

        Args:
            field: The CNMR_SHIFTS field string from SD file
            mult_map: Mapping from atom index to hydrogen count

        Returns:
            List of CarbonSignal objects
        """
        signals = []

        # Split by semicolon to get individual signals
        parts = field.strip().split(";")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Format: idx:atom|shift
            # Split by pipe first to get shift
            pipe_parts = part.split("|")
            if len(pipe_parts) != 2:
                continue

            try:
                shift = float(pipe_parts[1])
            except ValueError:
                continue

            # Parse atom index from idx:atom format
            atom_index = None
            colon_parts = pipe_parts[0].split(":")
            if len(colon_parts) >= 2:
                try:
                    atom_index = int(colon_parts[1])
                except ValueError:
                    pass

            # Get multiplicity from map
            hydrogen_count = mult_map.get(atom_index) if atom_index is not None else None

            signals.append(
                CarbonSignal(
                    shift=shift,
                    hydrogen_count=hydrogen_count,
                    atom_index=atom_index,
                )
            )

        return signals

    @staticmethod
    def _parse_multiplicity_field(field: str) -> list[int]:
        """Parse COCONUT multiplicity field (Quaternaries, Tertiaries, etc.).

        Format: 'atom_idx\\tshift\\n...'
        Example: '5\\t154.84\\n6\\t108.70'

        Args:
            field: The multiplicity field string

        Returns:
            List of atom indices
        """
        atom_indices = []
        if not field:
            return atom_indices

        for line in field.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Format: atom_idx\tshift
            parts = line.split("\t")
            if parts:
                try:
                    atom_idx = int(parts[0])
                    atom_indices.append(atom_idx)
                except ValueError:
                    pass

        return atom_indices

    @staticmethod
    def _count_carbons(formula: str) -> int:
        """Extract carbon count from molecular formula.

        Args:
            formula: Molecular formula (e.g., "C13H18O2")

        Returns:
            Number of carbons in the formula
        """
        # Match C followed by optional number, but not Cl, Ca, Co, Cr, Cu, Cs, Ce, etc.
        match = re.search(r"C(?![laroudsefgmnptb])(\d*)", formula)
        if not match:
            return 0

        count_str = match.group(1)
        if count_str == "":
            return 1  # Just "C" means 1 carbon
        return int(count_str)

    @staticmethod
    def _normalize_formula(formula: str) -> str:
        """Normalize molecular formula for consistent comparison.

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
