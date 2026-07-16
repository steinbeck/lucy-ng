"""PICK-03 stubs: reconstruction-quality metadata embedding.

RED-by-skip (Wave 0, Phase 99 Plan 01): `lucy_ng.nus.bridge` does not exist
yet -- ships in Plan 03 (metadata block itself may land in Plan 03 or 04,
per planner discretion downstream). D-05 adds a new top-level additive
metadata block (e.g. `"reconstruction"`/`"nus_metadata"`) alongside
`experiment`/`cross_peaks`; existing per-peak keys stay structurally
unchanged. D-06 derives per-peak `confidence` from the QC verdict (PASS ->
high/medium, PARTIAL -> low), replacing the blanket `"confidence": "low"`.

Implementing plan: Plan 03/04 (`lucy_ng.nus.bridge`, metadata block
construction from `NusReconstructionResult` + `QcReport`).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 03/04")
def test_metadata_block_present(tmp_path) -> None:
    """Emitted peak JSON must carry a top-level reconstruction/nus_metadata
    block with backend, iterations, and QC verdict (D-05) -- the existing
    per-peak keys must remain structurally unchanged (schema-identical, per
    the CONTEXT.md "byte-for-byte" clarification).

    Implementing plan: Plan 03/04 (`lucy_ng.nus.bridge` metadata block, D-05).
    """
    from lucy_ng.nus.bridge import bridge_peak_pick

    result = bridge_peak_pick(tmp_path / "processed.ft2", experiment_type="HSQC")
    metadata_block = result["reconstruction"]
    assert {"backend", "iterations", "verdict"} <= set(metadata_block.keys())


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 03/04")
def test_confidence_derived_from_verdict(tmp_path) -> None:
    """Per-peak `confidence` must be derived from the QC verdict (D-06):
    PASS -> high/medium, PARTIAL -> low. FAIL peaks never reach this code
    path at all (D-07 quarantines before write) so no FAIL confidence value
    should ever be emitted.

    Implementing plan: Plan 03/04 (`lucy_ng.nus.bridge` confidence mapping, D-06).
    """
    from lucy_ng.models.nus import QcVerdict
    from lucy_ng.nus.bridge import confidence_from_verdict

    assert confidence_from_verdict(QcVerdict.PASS) in {"high", "medium"}
    assert confidence_from_verdict(QcVerdict.PARTIAL) == "low"
