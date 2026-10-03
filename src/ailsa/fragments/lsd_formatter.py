"""Convert fragment SMILES to LSD SSTR/LINK fragment file format.

This module provides the :class:`DEFFFormatter` class, which translates RDKit
molecular data into LSD-native fragment definition syntax (SSTR/LINK).

Fragment files are referenced from the main LSD input via ``DEFF``/``FEXP``
commands.  LSD 3.4.9 requires **double quotes** around file paths in DEFF
commands.

Example::

    from ailsa.fragments.lsd_formatter import DEFFFormatter

    content = DEFFFormatter.smiles_to_fragment_content("Cc1ccccc1")
    path = DEFFFormatter.write_fragment_file("Cc1ccccc1", output_dir=Path("."))
    deff = DEFFFormatter.deff_command(1, path.name)
    fexp = DEFFFormatter.fexp_command([1])
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from rdkit import Chem
from rdkit.Chem.rdchem import HybridizationType


class DEFFFormatter:
    """Convert fragment SMILES to LSD DEFF fragment files.

    All methods are static -- no instance state is needed.
    """

    @staticmethod
    def smiles_to_fragment_content(smiles: str) -> str:
        """Convert SMILES to LSD SSTR/LINK fragment file content.

        Each heavy atom becomes an ``SSTR`` command with its element symbol,
        hybridization (1=sp, 2=sp2/aromatic, 3=sp3), and hydrogen count.
        Each bond becomes a ``LINK`` command.

        Args:
            smiles: Valid SMILES string for the fragment.

        Returns:
            Multi-line string with SSTR/LINK commands, ending with a newline.

        Raises:
            ValueError: If *smiles* cannot be parsed by RDKit.
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            msg = f"Invalid SMILES: {smiles}"
            raise ValueError(msg)

        canonical = Chem.MolToSmiles(mol)
        lines: list[str] = [f"; Fragment: {canonical}"]

        # SSTR commands -- one per heavy atom
        for atom in mol.GetAtoms():  # type: ignore[no-untyped-call]
            idx = atom.GetIdx() + 1  # LSD uses 1-based numbering
            symbol: str = atom.GetSymbol()
            nh: int = atom.GetTotalNumHs()

            hyb = atom.GetHybridization()
            if atom.GetIsAromatic() or hyb == HybridizationType.SP2:
                lsd_hyb = "2"
            elif hyb == HybridizationType.SP3:
                lsd_hyb = "3"
            elif hyb == HybridizationType.SP:
                lsd_hyb = "1"
            else:
                lsd_hyb = "(2 3)"  # fallback: allow both

            lines.append(f"SSTR S{idx} {symbol} {lsd_hyb} {nh}")

        # LINK commands -- one per bond
        for bond in mol.GetBonds():  # type: ignore[no-untyped-call]
            a1 = bond.GetBeginAtomIdx() + 1
            a2 = bond.GetEndAtomIdx() + 1
            lines.append(f"LINK S{a1} S{a2}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def fragment_filename(smiles: str) -> str:
        """Generate a deterministic filename from fragment SMILES.

        The SMILES is first canonicalised with RDKit so that any input
        variant (e.g. ``"Cc1ccccc1"`` vs ``"c1ccc(C)cc1"``) maps to the
        same filename.

        Args:
            smiles: Valid SMILES string.

        Returns:
            Filename of the form ``fragment_<12-hex-chars>.lsd``.

        Raises:
            ValueError: If *smiles* cannot be parsed by RDKit.
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            msg = f"Invalid SMILES: {smiles}"
            raise ValueError(msg)

        canonical: str = Chem.MolToSmiles(mol)
        hash_prefix = hashlib.sha256(canonical.encode()).hexdigest()[:12]
        return f"fragment_{hash_prefix}.lsd"

    @staticmethod
    def write_fragment_file(
        smiles: str,
        output_dir: Path | None = None,
    ) -> Path:
        """Write a SSTR/LINK fragment file and return its path.

        Args:
            smiles: Valid SMILES string for the fragment.
            output_dir: Directory to write the file into.  Defaults to the
                current working directory.

        Returns:
            Absolute path to the written file.

        Raises:
            ValueError: If *smiles* cannot be parsed by RDKit.
        """
        content = DEFFFormatter.smiles_to_fragment_content(smiles)
        filename = DEFFFormatter.fragment_filename(smiles)
        directory = output_dir if output_dir is not None else Path.cwd()
        path = directory / filename
        path.write_text(content)
        return path

    @staticmethod
    def deff_command(fragment_number: int, filepath: str) -> str:
        """Generate a ``DEFF`` command referencing a fragment file.

        LSD 3.4.9 requires **double quotes** around the file path.
        Single quotes cause error 160.

        Args:
            fragment_number: Fragment identifier (e.g. 1 for F1).
            filepath: Path to the fragment ``.lsd`` file.

        Returns:
            A ``DEFF`` command string, e.g. ``DEFF F1 "fragment.lsd"``.
        """
        return f'DEFF F{fragment_number} "{filepath}"'

    @staticmethod
    def fexp_command(
        fragment_numbers: list[int],
        logic: str = "OR",
    ) -> str:
        """Generate an ``FEXP`` command combining fragment references.

        Args:
            fragment_numbers: List of fragment identifiers (e.g. ``[1, 2]``).
            logic: Combination logic -- ``"OR"``, ``"AND"``, or ``"NOT"``
                (badlist, single fragment only).

        Returns:
            An ``FEXP`` command string, or ``""`` if the list is empty.
        """
        if not fragment_numbers:
            return ""

        if logic == "NOT":
            return f'FEXP "NOT F{fragment_numbers[0]}"'

        if len(fragment_numbers) == 1:
            return f'FEXP "F{fragment_numbers[0]}"'

        parts = f" {logic} ".join(f"F{n}" for n in fragment_numbers)
        return f'FEXP "{parts}"'
