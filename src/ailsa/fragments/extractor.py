"""BFS sphere fragmentation and resumable SSC extraction pipeline.

This module provides two layers:

1. **Pure fragmentation functions** — ``extract_fragments_for_compound`` and
   helpers extract substructure-subspectrum correlations (SSCs) from a single
   compound SMILES using RDKit BFS atom environments at radius 1-3 and
   ring-centred environments at radius 1.

2. **SSCExtractor pipeline class** — wraps the compound and fragment databases
   with checkpoint-based resumption so the multi-hour full extraction can be
   interrupted and restarted without re-processing compounds or duplicating SSC
   records.

Critical architecture decisions (from CLAUDE.md):

- **NO explicit hydrogens**: molecules are parsed with implicit H only.
  Calling ``AddHs()`` before HOSE/fragment operations causes 100 % mismatch.
- **Aromaticity standardisation**: ``Chem.SetAromaticity(mol,
  AROMATICITY_MDL)`` MUST be called before any fragmentation so that aromatic
  and Kekulé SMILES inputs produce identical canonical fragment SMILES.
- **Checkpoint ordering**: SSC batch is inserted FIRST, checkpoint saved
  AFTER — so a crash between the two replays the batch (INSERT OR IGNORE
  deduplicates safely) rather than losing data.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rdkit import Chem
from tqdm import tqdm  # type: ignore[import-untyped]

from ailsa.fragments.fingerprint import shifts_to_fingerprint
from ailsa.fragments.models import SSCRecord

if TYPE_CHECKING:
    from ailsa.database import DatabaseManager
    from ailsa.fragments.db import FragmentDatabaseManager


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RADIUS = 3  # Maximum BFS radius per Wenk thesis
MAX_RING_SIZE = 6  # Only expand ring environments for rings ≤ 6 atoms


# ---------------------------------------------------------------------------
# Pure fragmentation helpers
# ---------------------------------------------------------------------------


def _extract_atom_environment(
    mol: Chem.Mol,
    atom_idx: int,
    radius: int,
    shift_map: dict[int, float],
) -> tuple[str | None, list[float]]:
    """Extract a BFS atom-centred environment and collect shifts.

    Uses ``FindAtomEnvironmentOfRadiusN`` to obtain the bond set, then
    ``PathToSubmol`` to build the fragment molecule.

    Args:
        mol: RDKit molecule (implicit H, aromaticity standardised).
        atom_idx: Central atom index.
        radius: BFS radius (1, 2, or 3).
        shift_map: Mapping from atom index to 13C shift (only indexed atoms).

    Returns:
        ``(canonical_smiles, shifts)`` where *shifts* are the known shifts for
        atoms inside the fragment, or ``(None, [])`` on failure.
    """
    try:
        env = Chem.FindAtomEnvironmentOfRadiusN(mol, radius, atom_idx)
        if not env:
            # Radius 0 or isolated atom — return None, caller handles
            return None, []

        atom_map: dict[int, int] = {}
        fragment = Chem.PathToSubmol(mol, env, atomMap=atom_map)
        if fragment is None:
            return None, []

        canon = Chem.MolToSmiles(fragment)
        if not canon:
            return None, []

        # atom_map keys are original atom indices
        shifts = [
            shift_map[orig_idx]
            for orig_idx in atom_map
            if orig_idx in shift_map
        ]
        return canon, shifts
    except Exception:
        return None, []


def _extract_ring_environment(
    mol: Chem.Mol,
    ring_atoms: tuple[int, ...],
    shift_map: dict[int, float],
) -> tuple[str | None, list[float]]:
    """Extract a ring-centred environment (ring atoms + immediate neighbours).

    The fragment consists of all bonds between ring atoms plus all bonds
    connecting ring atoms to their direct non-ring neighbours.

    Args:
        mol: RDKit molecule (implicit H, aromaticity standardised).
        ring_atoms: Atom indices forming the ring.
        shift_map: Mapping from atom index to 13C shift.

    Returns:
        ``(canonical_smiles, shifts)`` or ``(None, [])`` on failure.
    """
    try:
        bond_indices: set[int] = set()

        # Bonds between ring atoms
        for i, a1 in enumerate(ring_atoms):
            for a2 in ring_atoms[i + 1 :]:
                bond = mol.GetBondBetweenAtoms(a1, a2)
                if bond is not None:
                    bond_indices.add(bond.GetIdx())

        # Bonds from ring atoms to immediate non-ring neighbours (radius 1)
        for atom_idx in ring_atoms:
            atom = mol.GetAtomWithIdx(atom_idx)
            for bond in atom.GetBonds():
                bond_indices.add(bond.GetIdx())

        if not bond_indices:
            return None, []

        atom_map: dict[int, int] = {}
        fragment = Chem.PathToSubmol(mol, list(bond_indices), atomMap=atom_map)
        if fragment is None:
            return None, []

        canon = Chem.MolToSmiles(fragment)
        if not canon:
            return None, []

        shifts = [
            shift_map[orig_idx]
            for orig_idx in atom_map
            if orig_idx in shift_map
        ]
        if not shifts:
            return None, []

        return canon, shifts
    except Exception:
        return None, []


def _build_ssc_record(smiles: str, shifts: list[float]) -> SSCRecord:
    """Build an SSCRecord from a fragment SMILES and its shifts.

    Args:
        smiles: Canonical fragment SMILES.
        shifts: 13C shifts for atoms in the fragment.

    Returns:
        Populated :class:`SSCRecord` with computed avg/min/max and bitset.
    """
    frag_mol = Chem.MolFromSmiles(smiles)
    atom_count = frag_mol.GetNumAtoms() if frag_mol is not None else len(smiles)
    avg_shift = sum(shifts) / len(shifts)
    min_shift = min(shifts)
    max_shift = max(shifts)
    bitset = shifts_to_fingerprint(shifts)
    return SSCRecord(
        smiles=smiles,
        atom_count=atom_count,
        shift_list=shifts,
        avg_shift=avg_shift,
        min_shift=min_shift,
        max_shift=max_shift,
        bitset=bitset,
    )


def extract_fragments_for_compound(
    smiles: str,
    atom_shifts: Sequence[tuple[int | None, float]],
) -> list[SSCRecord]:
    """Extract all SSC records from one compound using BFS fragmentation.

    Algorithm:

    1. Parse SMILES with **implicit H only** — never call ``AddHs()``.
    2. Standardise aromaticity with ``AROMATICITY_MDL`` (mandatory).
    3. Build ``shift_map`` from atom-indexed shifts (skip ``None`` indices).
    4. For each atom with a known shift, extract BFS environments at radius
       1, 2, and 3.
    5. For each ring system ≤ 6 atoms, extract the ring + neighbour
       environment.
    6. Deduplicate by canonical SMILES within the compound (in-memory set).
    7. Build :class:`SSCRecord` for each unique fragment with at least one
       known shift.

    Args:
        smiles: Compound SMILES string.
        atom_shifts: List of ``(atom_index, shift_ppm)`` tuples.  Entries
            where ``atom_index`` is ``None`` are ignored.

    Returns:
        List of unique :class:`SSCRecord` objects.  Empty if the molecule
        cannot be parsed or no atom-indexed shifts are present.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return []

    # MANDATORY: standardise aromaticity before any fragmentation
    Chem.SetAromaticity(mol, Chem.AromaticityModel.AROMATICITY_MDL)

    # Build shift_map: only include entries with integer atom_index
    shift_map: dict[int, float] = {}
    for atom_idx, shift_ppm in atom_shifts:
        if atom_idx is not None:
            shift_map[int(atom_idx)] = shift_ppm

    if not shift_map:
        return []

    seen_smiles: set[str] = set()
    records: list[SSCRecord] = []

    # --- Atom-centred BFS environments (radius 1, 2, 3) ---
    for atom_idx in shift_map:
        for radius in range(1, MAX_RADIUS + 1):
            canon, shifts = _extract_atom_environment(mol, atom_idx, radius, shift_map)
            if canon and shifts and canon not in seen_smiles:
                seen_smiles.add(canon)
                records.append(_build_ssc_record(canon, shifts))

    # --- Ring-centred environments (ring atoms + immediate neighbours) ---
    ring_info = mol.GetRingInfo()
    for ring in ring_info.AtomRings():
        if len(ring) > MAX_RING_SIZE:
            continue
        canon, shifts = _extract_ring_environment(mol, tuple(ring), shift_map)
        if canon and shifts and canon not in seen_smiles:
            seen_smiles.add(canon)
            records.append(_build_ssc_record(canon, shifts))

    return records


# ---------------------------------------------------------------------------
# SSCExtractor pipeline
# ---------------------------------------------------------------------------


@dataclass
class SSCExtractionResult:
    """Result summary from an SSC extraction run."""

    compounds_processed: int
    compounds_skipped: int
    sscs_extracted: int
    sscs_duplicate: int
    start_compound_id: int
    end_compound_id: int


class SSCExtractor:
    """Resumable SSC extraction pipeline.

    Iterates all compounds in the compound database (optionally from a
    checkpoint), extracts fragments for each, and inserts them into the
    fragment database in chunks.  A checkpoint is saved after each chunk so
    the pipeline can be safely interrupted and resumed.

    Checkpoint ordering guarantee: SSC batch is inserted FIRST, checkpoint
    saved AFTER.  A crash between the two will replay the batch on the next
    resume; ``INSERT OR IGNORE`` deduplicates silently.

    Attributes:
        CK_LAST_ID: schema_meta key for the last processed compound ID.
        CK_PROCESSED: schema_meta key for cumulative processed count.
        CK_SKIPPED: schema_meta key for cumulative skipped count.
        CK_EXTRACTED: schema_meta key for cumulative extracted SSC count.
        CK_DUPLICATE: schema_meta key for cumulative duplicate SSC count.
    """

    CK_LAST_ID = "checkpoint_ssc_last_compound_id"
    CK_PROCESSED = "checkpoint_ssc_compounds_processed"
    CK_SKIPPED = "checkpoint_ssc_compounds_skipped"
    CK_EXTRACTED = "checkpoint_ssc_sscs_extracted"
    CK_DUPLICATE = "checkpoint_ssc_sscs_duplicate"

    def __init__(
        self,
        compound_db: DatabaseManager,
        fragment_db: FragmentDatabaseManager,
    ) -> None:
        """Initialise with open database managers.

        Args:
            compound_db: Open :class:`DatabaseManager` pointing to the
                compound database (e.g. ``lucy-ng-derep.db``).
            fragment_db: Open :class:`FragmentDatabaseManager` pointing to
                the fragment database (e.g. ``lucy-ng-fragments.db``).
        """
        self._compound_db = compound_db
        self._fragment_db = fragment_db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_checkpoint(self, key: str, default: int = 0) -> int:
        """Load an integer checkpoint value, returning *default* if absent."""
        raw = self._fragment_db.get_checkpoint(key)
        return int(raw) if raw is not None else default

    def _save_all_checkpoints(
        self,
        last_id: int,
        processed: int,
        skipped: int,
        extracted: int,
        duplicate: int,
    ) -> None:
        """Persist all five checkpoint counters atomically."""
        fdb = self._fragment_db
        fdb.set_checkpoint(self.CK_LAST_ID, str(last_id))
        fdb.set_checkpoint(self.CK_PROCESSED, str(processed))
        fdb.set_checkpoint(self.CK_SKIPPED, str(skipped))
        fdb.set_checkpoint(self.CK_EXTRACTED, str(extracted))
        fdb.set_checkpoint(self.CK_DUPLICATE, str(duplicate))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        chunk_size: int = 1000,
        sample: int | None = None,
        resume: bool = True,
        fresh: bool = False,
    ) -> SSCExtractionResult:
        """Run the SSC extraction pipeline.

        Args:
            chunk_size: Number of compounds processed per checkpoint batch.
            sample: If set, stop after processing this many compounds (for
                bin-size validation and testing).
            resume: If ``True`` (default), load the last checkpoint and
                continue from where extraction stopped.  Ignored when
                ``fresh=True``.
            fresh: If ``True``, truncate all SSC data and checkpoints before
                starting.  Takes priority over *resume*.

        Returns:
            :class:`SSCExtractionResult` with cumulative counters.
        """
        # --- Handle fresh vs resume ---
        if fresh:
            self._fragment_db.clear_ssc_data()
            start_id = 0
            cum_processed = 0
            cum_skipped = 0
            cum_extracted = 0
            cum_duplicate = 0
        elif resume:
            start_id = self._load_checkpoint(self.CK_LAST_ID, 0)
            cum_processed = self._load_checkpoint(self.CK_PROCESSED, 0)
            cum_skipped = self._load_checkpoint(self.CK_SKIPPED, 0)
            cum_extracted = self._load_checkpoint(self.CK_EXTRACTED, 0)
            cum_duplicate = self._load_checkpoint(self.CK_DUPLICATE, 0)
        else:
            start_id = 0
            cum_processed = 0
            cum_skipped = 0
            cum_extracted = 0
            cum_duplicate = 0

        start_compound_id = start_id
        last_id = start_id
        chunk_batch: list[SSCRecord] = []
        chunk_compound_count = 0

        with tqdm(desc="Extracting SSCs", unit="compound") as pbar:
            for compound_id, smiles, shifts in self._compound_db.iter_compounds_with_shifts_from(
                start_id=start_id
            ):
                # Check if ALL shifts lack an atom index
                indexed = [(idx, ppm) for idx, ppm in shifts if idx is not None]
                if not indexed:
                    print(
                        f"SKIPPED: compound_id={compound_id} (no atom-indexed shifts)",
                        file=sys.stderr,
                    )
                    cum_skipped += 1
                    last_id = compound_id
                    pbar.update(1)
                    continue

                # Extract fragments
                fragments = extract_fragments_for_compound(smiles, indexed)
                chunk_batch.extend(fragments)
                cum_processed += 1
                last_id = compound_id
                chunk_compound_count += 1
                pbar.update(1)

                # Checkpoint after each chunk_size compounds processed
                if chunk_compound_count >= chunk_size:
                    if chunk_batch:
                        inserted, skipped = self._fragment_db.insert_ssc_batch(chunk_batch)
                        cum_extracted += inserted
                        cum_duplicate += skipped
                        chunk_batch = []
                    # Save checkpoint AFTER insert (Pitfall 4)
                    self._save_all_checkpoints(
                        last_id, cum_processed, cum_skipped, cum_extracted, cum_duplicate
                    )
                    chunk_compound_count = 0

                # Sample mode: stop after N compounds processed
                if sample is not None and cum_processed >= sample:
                    break

            # Insert remaining batch
            if chunk_batch:
                inserted, skipped = self._fragment_db.insert_ssc_batch(chunk_batch)
                cum_extracted += inserted
                cum_duplicate += skipped

            # Final checkpoint save
            self._save_all_checkpoints(
                last_id, cum_processed, cum_skipped, cum_extracted, cum_duplicate
            )

        return SSCExtractionResult(
            compounds_processed=cum_processed,
            compounds_skipped=cum_skipped,
            sscs_extracted=cum_extracted,
            sscs_duplicate=cum_duplicate,
            start_compound_id=start_compound_id,
            end_compound_id=last_id,
        )

    def validate_self_search(self, sample_size: int = 100) -> float:
        """Validate bin size by checking self-search recall.

        Takes up to *sample_size* compounds from the compound database that
        have atom-indexed shifts, builds a query fingerprint from their shifts,
        and checks whether at least one SSC in the fragment database has a
        bitset that is a subset of the query fingerprint (Boolean-AND
        pre-screening).

        A recall below 99 % suggests the 2 ppm bin size is too coarse or the
        extraction is incomplete.

        Args:
            sample_size: Number of compounds to test (default 100).

        Returns:
            Recall as a float in ``[0.0, 1.0]``.  Returns ``0.0`` if no
            compounds are available or the fragment DB is empty.
        """
        # Collect all bitsets from the fragment DB
        bitsets = list(self._fragment_db.iter_ssc_bitsets())
        if not bitsets:
            return 0.0

        hits = 0
        total = 0

        for _compound_id, _smiles, shifts in self._compound_db.iter_compounds_with_shifts_from(
            start_id=0
        ):
            indexed = [(idx, ppm) for idx, ppm in shifts if idx is not None]
            if not indexed:
                continue

            shift_values = [ppm for _, ppm in indexed]
            query_fp = shifts_to_fingerprint(shift_values)

            # Check if any stored bitset is a subset of the query fingerprint
            matched = False
            for _ssc_id, ssc_bitset in bitsets:
                # ssc_bitset subset of query_fp iff (query_fp & ssc_bitset) == ssc_bitset
                if len(query_fp) == len(ssc_bitset):
                    match = all(
                        (query_fp[i] & ssc_bitset[i]) == ssc_bitset[i]
                        for i in range(len(query_fp))
                    )
                    if match:
                        matched = True
                        break

            if matched:
                hits += 1
            total += 1

            if total >= sample_size:
                break

        return hits / total if total > 0 else 0.0
