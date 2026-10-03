"""Tests for fragment search engine (Phase 51, Plan 01).

Covers:
- expand_query_fingerprint: bit expansion with edge cases
- FragmentSearcher pre-screening: Boolean AND bitset filtering
- FragmentSearcher fine matching: DEV/AVGDEV thresholds, greedy nearest-neighbour
- Ranking: atom_count DESC, avg_deviation ASC
- End-to-end search pipeline with known SSC records
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ailsa.fragments import FragmentDatabaseManager, SSCMatch, SSCRecord
from ailsa.fragments.fingerprint import (
    FINGERPRINT_BITS,
    FINGERPRINT_BYTES,
    expand_query_fingerprint,
    shifts_to_fingerprint,
)
from ailsa.fragments.searcher import FragmentSearcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ssc(
    smiles: str,
    shifts: list[float],
    bitset: bytes | None = None,
) -> SSCRecord:
    """Build an SSCRecord with computed avg/min/max from shifts."""
    return SSCRecord(
        smiles=smiles,
        atom_count=len(shifts),
        shift_list=shifts,
        avg_shift=sum(shifts) / len(shifts) if shifts else 0.0,
        min_shift=min(shifts) if shifts else 0.0,
        max_shift=max(shifts) if shifts else 0.0,
        bitset=bitset,
    )


def _bit_at(fp: bytes, bit_index: int) -> bool:
    """Check if a specific bit is set in a fingerprint (LSB encoding)."""
    byte_idx = bit_index // 8
    bit_idx = bit_index % 8
    return bool(fp[byte_idx] & (1 << bit_idx))


def _populate_db(
    db: FragmentDatabaseManager, records: list[SSCRecord]
) -> list[int]:
    """Insert records into db and return their assigned IDs."""
    db.create_tables()
    db.insert_ssc_batch(records)
    rows = db.connection.execute("SELECT id FROM ssc ORDER BY id").fetchall()
    return [row["id"] for row in rows]


# ---------------------------------------------------------------------------
# expand_query_fingerprint
# ---------------------------------------------------------------------------


class TestExpandQueryFingerprint:
    """Tests for expand_query_fingerprint(fp, expand_bins=1) -> bytes."""

    def test_single_bit_expands_to_neighbors(self) -> None:
        """A single bit at index 10 with expand_bins=1 must set bits 9, 10, 11."""
        # Build fingerprint with only bit 10 set
        fp = shifts_to_fingerprint([20.5])  # bin 10 (20.5 / 2.0 = 10.25)
        assert _bit_at(fp, 10), "Precondition: bit 10 must be set"

        expanded = expand_query_fingerprint(fp, expand_bins=1)
        assert _bit_at(expanded, 9), "Bit 9 must be set after expansion"
        assert _bit_at(expanded, 10), "Bit 10 must remain set after expansion"
        assert _bit_at(expanded, 11), "Bit 11 must be set after expansion"
        # Bits 8 and 12 must NOT be set
        assert not _bit_at(expanded, 8), "Bit 8 must NOT be set (outside +-1 range)"
        assert not _bit_at(expanded, 12), "Bit 12 must NOT be set (outside +-1 range)"

    def test_edge_bit_0_no_wrap(self) -> None:
        """Bit 0 with expand_bins=1 must set bits 0 and 1 only (no wrap to 255)."""
        fp = shifts_to_fingerprint([0.5])  # bin 0
        assert _bit_at(fp, 0), "Precondition: bit 0 must be set"

        expanded = expand_query_fingerprint(fp, expand_bins=1)
        assert _bit_at(expanded, 0), "Bit 0 must remain set"
        assert _bit_at(expanded, 1), "Bit 1 must be set after expansion"
        assert not _bit_at(expanded, 255), "Bit 255 must NOT be set (no wrap-around)"

    def test_edge_bit_255_no_wrap(self) -> None:
        """Bit 255 with expand_bins=1 must set bits 254 and 255 only (no wrap to 0)."""
        fp = shifts_to_fingerprint([510.5])  # bin 255 (510.5 / 2.0 = 255.25)
        assert _bit_at(fp, 255), "Precondition: bit 255 must be set"

        expanded = expand_query_fingerprint(fp, expand_bins=1)
        assert _bit_at(expanded, 254), "Bit 254 must be set after expansion"
        assert _bit_at(expanded, 255), "Bit 255 must remain set"
        assert not _bit_at(expanded, 0), "Bit 0 must NOT be set (no wrap-around)"

    def test_all_zero_stays_zero(self) -> None:
        """An all-zero fingerprint must remain all-zero after expansion."""
        fp = bytes(FINGERPRINT_BYTES)  # 32 zero bytes
        expanded = expand_query_fingerprint(fp, expand_bins=1)
        assert expanded == bytes(FINGERPRINT_BYTES)

    def test_expand_bins_2(self) -> None:
        """expand_bins=2 must set 5 bits: bit-2, bit-1, bit, bit+1, bit+2."""
        fp = shifts_to_fingerprint([100.5])  # bin 50
        expanded = expand_query_fingerprint(fp, expand_bins=2)
        for offset in range(-2, 3):
            assert _bit_at(expanded, 50 + offset), (
                f"Bit {50 + offset} must be set with expand_bins=2"
            )
        assert not _bit_at(expanded, 47), "Bit 47 must NOT be set"
        assert not _bit_at(expanded, 53), "Bit 53 must NOT be set"

    def test_output_is_32_bytes(self) -> None:
        """Expanded fingerprint must always be exactly 32 bytes."""
        fp = shifts_to_fingerprint([50.0, 100.0, 200.0])
        expanded = expand_query_fingerprint(fp, expand_bins=1)
        assert len(expanded) == FINGERPRINT_BYTES


# ---------------------------------------------------------------------------
# Pre-screening
# ---------------------------------------------------------------------------


class TestPrescreening:
    """Tests for the Boolean AND pre-screening pass."""

    def test_prescreening_passes_subset(self, tmp_path: Path) -> None:
        """SSC with fingerprint bits that are a subset of the query passes screening."""
        db_path = tmp_path / "frag.db"
        # SSC has shifts at 30.0 (bin 15)
        ssc_fp = shifts_to_fingerprint([30.0])
        record = _make_ssc("CC=O", [30.0, 199.0], bitset=ssc_fp)

        with FragmentDatabaseManager(db_path) as db:
            _populate_db(db, [record])

        # Query has shifts at 30.0 AND 100.0 — superset of SSC's fingerprint
        with FragmentSearcher(db_path) as searcher:
            matches = searcher.search(
                experimental_shifts=[30.0, 100.0, 199.0],
                dev_threshold=5.0,  # lenient for this test
                avgdev_threshold=5.0,
                max_results=10,
                min_atom_count=1,  # SSC has 2 atoms
            )
            # The SSC should pass pre-screening (subset test)
            # and pass fine matching (shifts are close)
            assert len(matches) >= 1
            assert matches[0].smiles == "CC=O"

    def test_prescreening_filters_non_matching(self, tmp_path: Path) -> None:
        """SSC with fingerprint bits NOT in the query must be filtered out."""
        db_path = tmp_path / "frag.db"
        # SSC has shifts at 300.0 (bin 150)
        ssc_fp = shifts_to_fingerprint([300.0])
        record = _make_ssc("CC=O", [300.0], bitset=ssc_fp)

        with FragmentDatabaseManager(db_path) as db:
            _populate_db(db, [record])

        # Query only has shifts around 30.0 — does NOT cover bin 150
        with FragmentSearcher(db_path) as searcher:
            matches = searcher.search(
                experimental_shifts=[30.0, 31.0],
                dev_threshold=5.0,
                avgdev_threshold=5.0,
                max_results=10,
            )
            assert len(matches) == 0, "SSC with non-overlapping fingerprint must be filtered"


# ---------------------------------------------------------------------------
# Fine matching
# ---------------------------------------------------------------------------


class TestFineMatching:
    """Tests for greedy nearest-neighbour fine matching."""

    def test_fine_match_passes_within_threshold(self, tmp_path: Path) -> None:
        """Fragment shifts within DEV and AVGDEV thresholds must produce a match."""
        db_path = tmp_path / "frag.db"
        # Fragment shifts very close to query shifts
        fragment_shifts = [30.5, 130.2, 199.1]
        ssc_fp = shifts_to_fingerprint(fragment_shifts)
        record = _make_ssc("CC(=O)O", fragment_shifts, bitset=ssc_fp)

        with FragmentDatabaseManager(db_path) as db:
            _populate_db(db, [record])

        # Query shifts differ by <1 ppm
        with FragmentSearcher(db_path) as searcher:
            matches = searcher.search(
                experimental_shifts=[30.8, 130.0, 199.5],
                dev_threshold=2.0,
                avgdev_threshold=1.0,
            )
            assert len(matches) == 1
            assert matches[0].smiles == "CC(=O)O"
            assert matches[0].avg_deviation < 1.0

    def test_fine_match_rejects_high_dev(self, tmp_path: Path) -> None:
        """A single per-pair deviation > dev_threshold must reject the match."""
        db_path = tmp_path / "frag.db"
        # Fragment shift at 30.0, query will have shift at 35.0 (dev = 5.0)
        fragment_shifts = [30.0]
        ssc_fp = shifts_to_fingerprint(fragment_shifts)
        record = _make_ssc("C", fragment_shifts, bitset=ssc_fp)

        with FragmentDatabaseManager(db_path) as db:
            _populate_db(db, [record])

        with FragmentSearcher(db_path) as searcher:
            matches = searcher.search(
                experimental_shifts=[35.0],
                dev_threshold=2.0,  # max allowed per-pair deviation
                avgdev_threshold=5.0,  # lenient average
                min_atom_count=1,
            )
            # The query fp expansion (+-1 bin = +-2 ppm) won't cover
            # shift 30.0 from query 35.0 (bin 17 vs bin 15, diff=2 bins).
            # Even if it passed pre-screening, DEV would reject it.
            assert len(matches) == 0

    def test_fine_match_rejects_high_avgdev(self, tmp_path: Path) -> None:
        """Average deviation exceeding avgdev_threshold must reject the match."""
        db_path = tmp_path / "frag.db"
        # Fragment shifts: 30.0, 130.0, 200.0
        # Query shifts:    31.5, 131.5, 201.5  (each 1.5 ppm off -> avgdev=1.5)
        fragment_shifts = [30.0, 130.0, 200.0]
        ssc_fp = shifts_to_fingerprint(fragment_shifts)
        record = _make_ssc("CCC", fragment_shifts, bitset=ssc_fp)

        with FragmentDatabaseManager(db_path) as db:
            _populate_db(db, [record])

        with FragmentSearcher(db_path) as searcher:
            matches = searcher.search(
                experimental_shifts=[31.5, 131.5, 201.5],
                dev_threshold=2.0,  # per-pair OK (1.5 < 2.0)
                avgdev_threshold=1.0,  # average NOT OK (1.5 > 1.0)
            )
            assert len(matches) == 0, "avgdev 1.5 > threshold 1.0 must reject"


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class TestRanking:
    """Tests for result ranking: atom_count DESC, avg_deviation ASC."""

    def test_ranking_atom_count_then_avgdev(self, tmp_path: Path) -> None:
        """Larger fragments rank first; ties broken by lower avg_deviation."""
        db_path = tmp_path / "frag.db"

        # SSC A: 4 atoms, shifts close to query
        shifts_a = [30.0, 60.0, 130.0, 200.0]
        fp_a = shifts_to_fingerprint(shifts_a)
        rec_a = _make_ssc("CCCC", shifts_a, bitset=fp_a)

        # SSC B: 3 atoms, perfect match (avgdev=0)
        shifts_b = [30.0, 130.0, 200.0]
        fp_b = shifts_to_fingerprint(shifts_b)
        rec_b = _make_ssc("CCC", shifts_b, bitset=fp_b)

        # SSC C: 4 atoms, slightly worse avgdev than A
        shifts_c = [30.5, 60.5, 130.5, 200.5]
        fp_c = shifts_to_fingerprint(shifts_c)
        rec_c = _make_ssc("CCCO", shifts_c, bitset=fp_c)

        with FragmentDatabaseManager(db_path) as db:
            _populate_db(db, [rec_a, rec_b, rec_c])

        with FragmentSearcher(db_path) as searcher:
            matches = searcher.search(
                experimental_shifts=[30.0, 60.0, 130.0, 200.0],
                dev_threshold=2.0,
                avgdev_threshold=1.0,
                max_results=10,
                min_atom_count=3,
            )

        # atom_count 4 should rank before atom_count 3
        # Among atom_count=4, lower avgdev comes first
        assert len(matches) >= 2
        # First match should be 4-atom with lower avgdev
        assert matches[0].atom_count == 4
        # Last match should be 3-atom
        three_atom_matches = [m for m in matches if m.atom_count == 3]
        four_atom_matches = [m for m in matches if m.atom_count == 4]
        assert all(
            f.rank < t.rank
            for f in four_atom_matches
            for t in three_atom_matches
        ), "4-atom fragments must rank before 3-atom fragments"

    def test_min_atom_count_filter(self, tmp_path: Path) -> None:
        """Fragments below min_atom_count must be excluded from results."""
        db_path = tmp_path / "frag.db"

        # Small fragment: 2 atoms
        shifts_small = [30.0, 60.0]
        fp_small = shifts_to_fingerprint(shifts_small)
        rec_small = _make_ssc("CC", shifts_small, bitset=fp_small)

        # Larger fragment: 4 atoms
        shifts_large = [30.0, 60.0, 130.0, 200.0]
        fp_large = shifts_to_fingerprint(shifts_large)
        rec_large = _make_ssc("CCCC", shifts_large, bitset=fp_large)

        with FragmentDatabaseManager(db_path) as db:
            _populate_db(db, [rec_small, rec_large])

        with FragmentSearcher(db_path) as searcher:
            matches = searcher.search(
                experimental_shifts=[30.0, 60.0, 130.0, 200.0],
                dev_threshold=2.0,
                avgdev_threshold=1.0,
                min_atom_count=3,
            )

        # Only the 4-atom fragment should be in results
        assert all(m.atom_count >= 3 for m in matches)
        assert not any(m.smiles == "CC" for m in matches)


# ---------------------------------------------------------------------------
# End-to-end search
# ---------------------------------------------------------------------------


class TestSearchEndToEnd:
    """End-to-end tests for FragmentSearcher.search()."""

    def test_search_end_to_end(self, tmp_path: Path) -> None:
        """Full pipeline with known SSCs: prescreen, fine-match, rank."""
        db_path = tmp_path / "frag.db"

        # Create several SSC records with known shifts
        records = [
            # Good match (5 atoms, close shifts)
            _make_ssc(
                "c1ccccc1",
                [128.0, 128.5, 129.0, 129.5, 130.0],
                bitset=shifts_to_fingerprint([128.0, 128.5, 129.0, 129.5, 130.0]),
            ),
            # Decent match (3 atoms)
            _make_ssc(
                "CC=O",
                [30.0, 199.0, 205.0],
                bitset=shifts_to_fingerprint([30.0, 199.0, 205.0]),
            ),
            # Non-matching (shifts in completely different region)
            _make_ssc(
                "CCCCCCC",
                [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0],
                bitset=shifts_to_fingerprint([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]),
            ),
        ]

        with FragmentDatabaseManager(db_path) as db:
            _populate_db(db, records)

        query_shifts = [128.2, 128.8, 129.1, 129.3, 130.1, 30.5, 199.5, 205.5]

        with FragmentSearcher(db_path) as searcher:
            matches = searcher.search(
                experimental_shifts=query_shifts,
                dev_threshold=2.0,
                avgdev_threshold=1.0,
                max_results=5,
                min_atom_count=3,
            )

        # The aromatic fragment (5 atoms) should rank first
        assert len(matches) >= 1
        assert matches[0].smiles == "c1ccccc1"
        assert matches[0].rank == 1
        assert matches[0].atom_count == 5
        assert matches[0].avg_deviation < 1.0

        # Ranks must be sequential starting at 1
        for i, m in enumerate(matches):
            assert m.rank == i + 1

    def test_context_manager_protocol(self, tmp_path: Path) -> None:
        """FragmentSearcher must work as a context manager."""
        db_path = tmp_path / "frag.db"
        with FragmentDatabaseManager(db_path) as db:
            db.create_tables()

        with FragmentSearcher(db_path) as searcher:
            matches = searcher.search(
                experimental_shifts=[30.0, 130.0],
                dev_threshold=2.0,
                avgdev_threshold=1.0,
            )
            assert matches == []

    def test_max_results_limits_output(self, tmp_path: Path) -> None:
        """max_results must limit the number of returned matches."""
        db_path = tmp_path / "frag.db"

        # Create many matching records
        records = []
        for i in range(10):
            s = 30.0 + i * 0.1
            records.append(
                _make_ssc(
                    f"C{'C' * (i + 3)}O",
                    [s, 130.0, 200.0],
                    bitset=shifts_to_fingerprint([s, 130.0, 200.0]),
                )
            )

        with FragmentDatabaseManager(db_path) as db:
            _populate_db(db, records)

        with FragmentSearcher(db_path) as searcher:
            matches = searcher.search(
                experimental_shifts=[30.5, 130.0, 200.0],
                dev_threshold=2.0,
                avgdev_threshold=1.0,
                max_results=3,
                min_atom_count=3,
            )
            assert len(matches) <= 3

    def test_import_from_package(self) -> None:
        """FragmentSearcher must be importable from ailsa.fragments."""
        from ailsa.fragments import FragmentSearcher as FS

        assert FS is FragmentSearcher
