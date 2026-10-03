"""Fragment search engine for matching experimental shifts against SSC database.

Implements a two-phase search pipeline:

1. **Pre-screening** — Boolean AND on 256-bit fingerprints.  Each stored SSC
   fingerprint must be a bitwise subset of the (expanded) query fingerprint.
   Uses NumPy vectorised batch operations for performance.

2. **Fine matching** — Greedy nearest-neighbour assignment of fragment shifts
   to query shifts.  Rejects candidates where any per-pair deviation exceeds
   ``dev_threshold`` or the overall average deviation exceeds ``avgdev_threshold``.

Results are ranked by heavy-atom count (descending) then average deviation
(ascending), following the Wenk thesis convention.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from ailsa.fragments.db import FragmentDatabaseManager
from ailsa.fragments.fingerprint import expand_query_fingerprint, shifts_to_fingerprint
from ailsa.fragments.models import SSCMatch, SSCRecord


class FragmentSearcher:
    """Search the SSC fragment database for matches to experimental 13C shifts.

    Wraps :class:`FragmentDatabaseManager` as a context manager.  The database
    connection is **not** opened at construction time; it is opened lazily
    inside ``__enter__`` (or on first ``search`` call).

    Usage::

        with FragmentSearcher("lucy-ng-fragments.db") as searcher:
            matches = searcher.search(
                experimental_shifts=[128.0, 130.5, 199.1],
                dev_threshold=2.0,
                avgdev_threshold=1.0,
                max_results=20,
            )
    """

    _SQLITE_PARAM_LIMIT = 999  # SQLite placeholder limit per query

    def __init__(self, db_path: str | Path) -> None:
        """Store the database path without opening a connection.

        Args:
            db_path: Path to the ``lucy-ng-fragments.db`` file.
        """
        self._db_path = Path(db_path)
        self._db: FragmentDatabaseManager | None = None
        self.prescreening_count: int = 0
        self.fine_match_count: int = 0

    def __enter__(self) -> FragmentSearcher:
        """Open the database connection."""
        self._db = FragmentDatabaseManager(self._db_path)
        self._db.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Close the database connection."""
        if self._db is not None:
            self._db.__exit__(exc_type, exc_val, exc_tb)
            self._db = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        experimental_shifts: list[float],
        dev_threshold: float = 2.0,
        avgdev_threshold: float = 1.0,
        max_results: int = 20,
        min_atom_count: int = 3,
        verbose: bool = False,
    ) -> list[SSCMatch]:
        """Run the two-phase fragment search pipeline.

        1. Build and expand a query fingerprint.
        2. Pre-screen all SSC bitsets via Boolean AND.
        3. Fetch surviving candidates and fine-match each one.
        4. Rank by ``(-atom_count, avg_deviation)`` and return the top results.

        Args:
            experimental_shifts: Observed 13C chemical shifts (ppm).
            dev_threshold: Maximum per-pair deviation for fine matching (ppm).
            avgdev_threshold: Maximum average deviation for fine matching (ppm).
            max_results: Maximum number of matches to return.
            min_atom_count: Minimum fragment atom count to include.
            verbose: If ``True``, print screening statistics to stderr.

        Returns:
            Ranked list of :class:`SSCMatch` objects (best first).
        """
        if self._db is None:
            self._db = FragmentDatabaseManager(self._db_path)
            self._db.__enter__()

        # Step 1: Build and expand query fingerprint
        query_fp = shifts_to_fingerprint(experimental_shifts)
        expanded_fp = expand_query_fingerprint(query_fp)

        # Step 2: Pre-screening
        candidate_ids = self._prescreening_pass(expanded_fp, verbose=verbose)
        self.prescreening_count = len(candidate_ids)

        if verbose:
            print(
                f"Pre-screen: {len(candidate_ids)} candidates passed",
                file=sys.stderr,
            )

        if not candidate_ids:
            self.fine_match_count = 0
            return []

        # Step 3: Fine matching
        matches: list[SSCMatch] = []
        sorted_query = sorted(experimental_shifts)

        # Fetch in chunks of 999 (SQLite placeholder limit)
        for chunk_start in range(
            0, len(candidate_ids), self._SQLITE_PARAM_LIMIT
        ):
            chunk_ids = candidate_ids[
                chunk_start : chunk_start + self._SQLITE_PARAM_LIMIT
            ]
            records = self._db.get_ssc_by_id(chunk_ids)
            for record in records:
                if record.atom_count < min_atom_count:
                    continue
                match = self._fine_match_record(
                    record, sorted_query, dev_threshold, avgdev_threshold
                )
                if match is not None:
                    matches.append(match)

        self.fine_match_count = len(matches)

        if verbose:
            print(
                f"Fine match: {len(matches)} matches passed",
                file=sys.stderr,
            )

        # Step 4: Rank and assign ranks
        matches.sort(key=lambda m: (-m.atom_count, m.avg_deviation))
        for i, match in enumerate(matches):
            match.rank = i + 1

        return matches[:max_results]

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _prescreening_pass(
        self, query_fp_expanded: bytes, *, verbose: bool = False
    ) -> list[int]:
        """Return ssc_ids whose fingerprints are subsets of the expanded query.

        Uses NumPy vectorised AND within each batch from
        :meth:`FragmentDatabaseManager.iter_ssc_bitsets` for performance.

        Args:
            query_fp_expanded: Expanded 32-byte query fingerprint.
            verbose: Unused (statistics are printed by the caller).

        Returns:
            List of ``ssc_id`` values that passed pre-screening.
        """
        assert self._db is not None
        candidate_ids: list[int] = []
        q_arr = np.frombuffer(query_fp_expanded, dtype=np.uint8)  # (32,)

        batch: list[tuple[int, bytes]] = []
        for item in self._db.iter_ssc_bitsets():
            batch.append(item)
            if len(batch) >= 100_000:
                candidate_ids.extend(self._screen_batch(batch, q_arr))
                batch.clear()

        # Process remaining items
        if batch:
            candidate_ids.extend(self._screen_batch(batch, q_arr))

        return candidate_ids

    @staticmethod
    def _screen_batch(
        batch: list[tuple[int, bytes]],
        q_arr: np.ndarray[tuple[int, ...], np.dtype[np.uint8]],
    ) -> list[int]:
        """Screen a batch of (ssc_id, bitset) pairs using vectorised AND.

        Args:
            batch: List of ``(ssc_id, bitset_bytes)`` tuples.
            q_arr: Query fingerprint as NumPy uint8 array of shape ``(32,)``.

        Returns:
            List of ``ssc_id`` values whose fingerprints are subsets of the query.
        """
        if not batch:
            return []
        ids = [item[0] for item in batch]
        fps = np.array(
            [np.frombuffer(item[1], dtype=np.uint8) for item in batch]
        )  # (N, 32)
        # Boolean AND: all bits of each SSC fp must be present in query fp
        # np.asarray ensures mypy sees a concrete ndarray, not the union
        # type that np.all(..., axis=...) returns.
        mask = np.asarray(np.all((fps & q_arr) == fps, axis=1))  # (N,) bool
        return [ids[i] for i in range(len(ids)) if bool(mask[i])]

    @staticmethod
    def _fine_match_record(
        record: SSCRecord,
        sorted_query_shifts: list[float],
        dev_threshold: float,
        avgdev_threshold: float,
    ) -> SSCMatch | None:
        """Greedy nearest-neighbour matching of a single SSCRecord.

        For each fragment shift (sorted ascending), find the closest
        unmatched query shift.  If any per-pair deviation exceeds
        ``dev_threshold`` or the overall average deviation exceeds
        ``avgdev_threshold``, the match is rejected.

        Args:
            record: The SSC record to match.
            sorted_query_shifts: Experimental shifts sorted ascending.
            dev_threshold: Maximum per-pair deviation (ppm).
            avgdev_threshold: Maximum average deviation (ppm).

        Returns:
            :class:`SSCMatch` if the record passes, else ``None``.
        """
        remaining_query = list(sorted_query_shifts)
        matched_query: list[float] = []
        matched_fragment: list[float] = []

        for frag_shift in sorted(record.shift_list):
            if not remaining_query:
                return None  # Not enough query signals

            # Find closest remaining query shift
            closest_idx = min(
                range(len(remaining_query)),
                key=lambda i: abs(remaining_query[i] - frag_shift),
            )
            dev = abs(remaining_query[closest_idx] - frag_shift)
            if dev > dev_threshold:
                return None  # Per-pair deviation too large

            matched_query.append(remaining_query.pop(closest_idx))
            matched_fragment.append(frag_shift)

        if not matched_fragment:
            return None

        avg_dev = sum(
            abs(mq - mf)
            for mq, mf in zip(matched_query, matched_fragment, strict=True)
        ) / len(matched_fragment)

        if avg_dev > avgdev_threshold:
            return None

        assert record.id is not None
        return SSCMatch(
            ssc_id=record.id,
            smiles=record.smiles,
            atom_count=record.atom_count,
            avg_deviation=round(avg_dev, 6),
            matched_shifts=matched_query,
            fragment_shifts=matched_fragment,
        )
