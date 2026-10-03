"""HOSE code generation for NMR chemical shift prediction."""

from rdkit import Chem
from rdkit.Chem import Mol

try:
    from hosegen import HoseGenerator
    HOSEGEN_AVAILABLE = True
except ImportError:
    HOSEGEN_AVAILABLE = False
    HoseGenerator = None  # type: ignore[misc, assignment]


class HOSECodeGenerator:
    """Generate HOSE codes for carbon atoms in molecules.

    HOSE (Hierarchically Ordered Spherical Environment) codes encode the
    local chemical environment around an atom. They are used for predicting
    NMR chemical shifts by looking up similar environments in a reference database.
    """

    def __init__(self) -> None:
        """Initialize the HOSE code generator."""
        if not HOSEGEN_AVAILABLE:
            raise ImportError(
                "hosegen package not installed. Install with:\n"
                "  pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps"
            )
        self._generator = HoseGenerator()

    def generate_for_atom(self, mol: Mol, atom_idx: int, radius: int = 6) -> str:
        """Generate HOSE code for a specific atom.

        Args:
            mol: RDKit Mol object (should have explicit hydrogens)
            atom_idx: Index of the atom to generate HOSE code for
            radius: Number of spheres (default 6)

        Returns:
            HOSE code string
        """
        return self._generator.get_Hose_codes(mol, atom_idx, max_radius=radius)

    def generate_for_carbons(
        self, mol: Mol, radius: int = 6
    ) -> dict[int, str]:
        """Generate HOSE codes for all carbon atoms in a molecule.

        Args:
            mol: RDKit Mol object (should have explicit hydrogens)
            radius: Number of spheres for HOSE code (default 6)

        Returns:
            Dict mapping atom index to HOSE code for each carbon
        """
        hose_codes: dict[int, str] = {}

        for atom in mol.GetAtoms():
            if atom.GetSymbol() == "C":
                atom_idx = atom.GetIdx()
                hose_codes[atom_idx] = self._generator.get_Hose_codes(
                    mol, atom_idx, max_radius=radius
                )

        return hose_codes

    def generate_for_carbons_all_radii(
        self, mol: Mol, max_radius: int = 6
    ) -> dict[int, dict[int, str]]:
        """Generate HOSE codes at all radii for fallback lookup.

        Args:
            mol: RDKit Mol object (should have explicit hydrogens)
            max_radius: Maximum number of spheres (default 6)

        Returns:
            Dict mapping atom index to dict of {radius: HOSE code}
        """
        result: dict[int, dict[int, str]] = {}

        for atom in mol.GetAtoms():
            if atom.GetSymbol() == "C":
                atom_idx = atom.GetIdx()
                result[atom_idx] = {}
                for radius in range(1, max_radius + 1):
                    result[atom_idx][radius] = self._generator.get_Hose_codes(
                        mol, atom_idx, max_radius=radius
                    )

        return result

    @staticmethod
    def prepare_mol(smiles: str) -> Mol | None:
        """Prepare a molecule from SMILES for HOSE code generation.

        Aromaticity is explicitly (re-)perceived via ``Chem.SetAromaticity``
        so that rings supplied in Kekulé form (aromatic rings written with
        explicit alternating double bonds, as emitted by ``outlsd`` /
        ``ailsa lsd run``) are transparently aromatized before HOSE codes are
        generated. Relying on the implicit default sanitization alone is
        fragile (it could drift across RDKit versions or be silently
        defeated by a future ``sanitize=False`` refactor); enforcing it here
        pins the guarantee at the prediction choke point (FIX-11).

        Returns molecule WITHOUT explicit hydrogens (no ``AddHs``) to match
        the HOSE lookup table format (built without explicit H) — the
        no-explicit-H invariant from CLAUDE.md.

        Args:
            smiles: SMILES string

        Returns:
            RDKit Mol with aromaticity perceived and no explicit hydrogens,
            or None if parsing fails
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        # Enforce aromaticity perception explicitly (RDKit default model).
        # No AddHs — preserve the no-explicit-H HOSE invariant.
        Chem.SetAromaticity(mol)
        return mol

    @staticmethod
    def prepare_mol_from_molblock(molblock: str) -> Mol | None:
        """Prepare a molecule from MOL block for HOSE code generation.

        Args:
            molblock: MOL block string

        Returns:
            RDKit Mol without explicit hydrogens, or None if parsing fails
        """
        # Remove explicit hydrogens to match HOSE table format
        return Chem.MolFromMolBlock(molblock, removeHs=True)
