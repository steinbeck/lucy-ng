"""Bruker NUS acquisition + calibration parameter extraction.

Reads `acqus`/`acqu2s` (acquisition) and `pdata/1/procs`/`pdata/1/proc2s`
(processing/calibration) into a validated `NusAcquisitionParams` (D-04
superset), reusing `readers/bruker.py`'s `_get_param_2d`/`_strip_brackets`
helpers so the parsing convention stays identical to the rest of the
project's Bruker I/O.

**Deviation from the literal RESEARCH.md/PLAN code example (documented,
Rule 1 -- bug fix):** the research's reference implementation calls
`ng.bruker.read(expdir)`. That entry point requires a raw binary file
(`fid`/`ser`) to be present in `expdir` -- it uses the file to determine
data shape/endianness and reads it unconditionally. The D-03 test fixtures
(`tests/fixtures/nus/{exp2_cosy,exp3_hsqc,exp4_hmbc}/`) intentionally
contain *only* the small text metadata files (`acqus`, `acqu2s`, `nuslist`,
`pdata/1/procs`, `pdata/1/proc2s`) -- no `ser` -- per D-03's own rationale
("params/schedule parsing reads only the text metadata, so `ser` is
unnecessary weight here"). Calling `ng.bruker.read()` against those fixtures
raises `OSError: No Bruker binary file could be found`, which would make
NUS-02/NUS-04's fixture-verification requirement unsatisfiable as literally
specified.

This module therefore uses nmrglue's lower-level, metadata-only readers
(`ng.bruker.read_acqus_file()`, `ng.bruker.read_procs_file()`) instead of
the monolithic `ng.bruker.read()`. These read exactly the same underlying
files (`acqus`, `acqu2s`, `pdata/1/procs`, `pdata/1/proc2s`) with identical
bracket-stripping/numeric-coercion behavior (verified directly against all
three real fixtures) and have zero dependency on a binary file being
present -- correct for both the text-only test fixtures and real,
not-yet-reconstructed NUS experiment directories (which also lack a
processed binary; see `models/nus.py`'s docstring on `f2_sf`/`f1_sf`/etc.
being legitimately `None` pre-reconstruction). `ng.bruker.read_pdata()` is
never used here (NUS dirs have no `1r`/`2rr`; that call would also raise
`OSError`) -- see 97-RESEARCH.md's own Anti-Patterns section.
"""

from pathlib import Path
from typing import Any

import nmrglue as ng

from lucy_ng.models.nus import NusAcquisitionParams
from lucy_ng.readers.bruker import _get_param_2d


def read_nus_params(expdir: str | Path) -> NusAcquisitionParams:
    """Parse a Bruker NUS experiment directory into `NusAcquisitionParams`.

    Args:
        expdir: Path to a Bruker NUS experiment directory (contains
            `acqus`, `acqu2s`, `pdata/1/procs`, `pdata/1/proc2s`).

    Returns:
        Validated `NusAcquisitionParams` (D-04 superset: acquisition +
        calibration parameters).

    Raises:
        FileNotFoundError: If `expdir` does not exist.
        ValueError: If a genuinely-required acquisition field (FnMODE, TD,
            etc.) is missing. SF/OFFSET (calibration) fields are exempt --
            `None` is a legitimate pre-reconstruction state, not a parse
            failure.
    """
    resolved = Path(expdir).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"NUS experiment directory not found: {resolved}")

    # Metadata-only readers -- no fid/ser binary required. See module
    # docstring for why this diverges from ng.bruker.read().
    dic: dict[str, Any] = ng.bruker.read_acqus_file(str(resolved))
    dic.update(ng.bruker.read_procs_file(str(resolved)))

    def require(param_dict: str, key: str) -> Any:
        value = _get_param_2d(dic, param_dict, key)
        if value is None:
            raise ValueError(
                f"{key} parameter not found in {param_dict}: {resolved}"
            )
        return value

    pulse_program = require("acqus", "PULPROG")

    # F2 (direct dimension, acqus)
    f2_nucleus = require("acqus", "NUC1")
    f2_sfo1 = require("acqus", "SFO1")
    f2_sw_h = require("acqus", "SW_h")
    f2_td = require("acqus", "TD")

    # Digital-filter / data-type parameters (acqus)
    byte_order = require("acqus", "BYTORDA")
    dtype_code = require("acqus", "DTYPA")
    decim = require("acqus", "DECIM")
    dspfvs = require("acqus", "DSPFVS")
    grpdly = require("acqus", "GRPDLY")  # non-integer -- never round

    # NUS acquisition parameters (acqus)
    nus_amount_pct = require("acqus", "NusAMOUNT")
    nus_seed = require("acqus", "NusSEED")

    # F1 (indirect dimension, acqu2s) -- fnmode_f1/nus_td MUST come from
    # acqu2s. acqus also carries a vestigial FnMODE key that is always 0
    # for every experiment; reading it here instead would silently make
    # every experiment look like a real-only (QF) acquisition.
    f1_nucleus = require("acqu2s", "NUC1")
    f1_sfo1 = require("acqu2s", "SFO1")
    f1_sw_h = require("acqu2s", "SW_h")
    f1_o1 = require("acqu2s", "O1")
    f1_td = require("acqu2s", "TD")
    fnmode_f1 = require("acqu2s", "FnMODE")
    nus_td = require("acqu2s", "NusTD")

    # Processing/calibration -- separate files (procs/proc2s), legitimately
    # absent pre-reconstruction (no processed binary exists for NUS data
    # until Phase 98). Do not raise; leave as None.
    f2_sf = _get_param_2d(dic, "procs", "SF")
    f2_offset = _get_param_2d(dic, "procs", "OFFSET")
    f1_sf = _get_param_2d(dic, "proc2s", "SF")
    f1_offset = _get_param_2d(dic, "proc2s", "OFFSET")

    return NusAcquisitionParams(
        pulse_program=pulse_program,
        f2_nucleus=f2_nucleus,
        f2_sfo1=f2_sfo1,
        f2_sw_h=f2_sw_h,
        f2_td=f2_td,
        byte_order=byte_order,
        dtype_code=dtype_code,
        decim=decim,
        dspfvs=dspfvs,
        grpdly=grpdly,
        nus_amount_pct=nus_amount_pct,
        nus_seed=nus_seed,
        f1_nucleus=f1_nucleus,
        f1_sfo1=f1_sfo1,
        f1_sw_h=f1_sw_h,
        f1_o1=f1_o1,
        f1_td=f1_td,
        fnmode_f1=fnmode_f1,
        nus_td=nus_td,
        f2_sf=f2_sf,
        f2_offset=f2_offset,
        f1_sf=f1_sf,
        f1_offset=f1_offset,
    )
