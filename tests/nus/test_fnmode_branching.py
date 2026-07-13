"""RECON-03 stubs: FnMODE-driven stage-order branching (Critical Finding 1).

Implemented in Plan 02 (`nus/runner.py::_ordering_for_fnmode`). SMILE manual
Sec.4: for echo-antiecho (complex, phase-sensitive) indirect dimensions, the
recommended and only fully-worked order is nusExpand.tcl BEFORE bruk2pipe
("expand_first"); this order explicitly "does not work" for magnitude-mode
(QF) data, which must instead run bruk2pipe BEFORE nusExpand.tcl
("convert_first"). Both HSQC (exp3, 25% density) and HMBC (exp4, 33%
density) share the FnMODE=6 echo-antiecho branch -- density does not change
the stage-order decision, only FnMODE does.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 02")
def test_echo_antiecho_expand_first() -> None:
    """FnMODE=6 (echo-antiecho, HSQC exp3 @ 25% and HMBC exp4 @ 33%) must
    resolve to the "expand_first" stage order (nusExpand.tcl before
    bruk2pipe) -- SMILE manual Sec.4's fully-worked, recommended path.

    Implementing plan: Plan 02 (`nus/runner.py::_ordering_for_fnmode`).
    """
    from lucy_ng.nus.runner import _ordering_for_fnmode

    assert _ordering_for_fnmode(6) == "expand_first"


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 02")
def test_qf_convert_first() -> None:
    """FnMODE=1 (QF/magnitude, COSY exp2) must resolve to the
    "convert_first" stage order (bruk2pipe before nusExpand.tcl) -- the
    SMILE manual explicitly states the expand-first order "does not work"
    for magnitude-mode Bruker data.

    Implementing plan: Plan 02 (`nus/runner.py::_ordering_for_fnmode`).
    """
    from lucy_ng.nus.runner import _ordering_for_fnmode

    assert _ordering_for_fnmode(1) == "convert_first"


@pytest.mark.skip(reason="Wave 0 stub — implemented in Plan 02")
def test_unknown_fnmode_raises() -> None:
    """An FnMODE outside the two verified branches (REAL_FNMODES /
    COMPLEX_FNMODES from models/nus.py) must raise NotImplementedError --
    refuse-to-guess convention, matching nus/schedule.py's
    expected_sample_count().

    Implementing plan: Plan 02 (`nus/runner.py::_ordering_for_fnmode`).
    """
    from lucy_ng.nus.runner import _ordering_for_fnmode

    with pytest.raises(NotImplementedError):
        _ordering_for_fnmode(99)
