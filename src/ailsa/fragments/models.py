"""Pydantic models for fragment (SSC) database entities."""

from __future__ import annotations

import json

from pydantic import BaseModel, field_validator


class SSCRecord(BaseModel):
    """A substructure-subspectrum correlation record.

    Stored in the ``ssc`` table of ``lucy-ng-fragments.db``.
    One record per unique substructure (deduplicated by SMILES).

    The ``shift_list`` field stores the subspectrum 13C shifts for this
    substructure. When loaded from SQLite it arrives as a JSON string;
    the ``field_validator`` parses it transparently.

    The ``bitset`` field holds the 32-byte (256-bit) fingerprint used for
    pre-screening during fragment search (Phase 51). It is ``None`` by
    default and is only populated when the bitset is explicitly needed.
    """

    id: int | None = None
    smiles: str
    atom_count: int
    shift_list: list[float]
    avg_shift: float
    min_shift: float
    max_shift: float
    bitset: bytes | None = None

    @field_validator("shift_list", mode="before")
    @classmethod
    def parse_shift_list(cls, v: object) -> list[float]:
        """Parse JSON string from database if needed.

        Accepts either a JSON string (from SQLite storage) or a Python list
        (from code). Returns ``list[float]`` in both cases.
        """
        if isinstance(v, str):
            return json.loads(v)  # type: ignore[no-any-return]
        return v  # type: ignore[return-value]

    def shift_list_as_json(self) -> str:
        """Serialize shift_list for database storage.

        Returns:
            JSON array string, e.g. ``"[30.5, 199.1]"``
        """
        return json.dumps(self.shift_list)


class SSCMatch(BaseModel):
    """Result of a fragment search — an SSC that matched the experimental spectrum.

    Produced by the FragmentSearcher (Phase 51).  Defined here in Phase 49
    so that Phases 51 and 52 can run in parallel — both depend on this model,
    not on the actual SSC data that Phase 50 extracts.
    """

    ssc_id: int
    smiles: str
    atom_count: int
    avg_deviation: float
    matched_shifts: list[float]
    fragment_shifts: list[float]
    rank: int = 0
