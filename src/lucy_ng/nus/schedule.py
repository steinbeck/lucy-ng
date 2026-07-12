"""Bruker NUS sampling-schedule (`nuslist`) parsing + FnMODE hard-fail assertion.

Reads the Bruker `nuslist` file in strict acquisition order (never sorted or
regenerated) and enforces the correctness crux of Phase 97 (NUS-03): the
FnMODE-derived `n_sampled == len(nuslist)` assertion must RAISE, never warn,
on any mismatch, and an unrecognized FnMODE must raise rather than silently
guess a real/complex relationship.

`REAL_FNMODES`/`COMPLEX_FNMODES` are imported from `lucy_ng.models.nus` so
this module and the `NusAcquisitionParams.fnmode_f1` validator never maintain
divergent allowed-FnMODE sets (97-01's design decision).

**Real-vs-complex grid note (read before "fixing" an apparent mismatch):**
`NusTD` (the authoritative full-grid size from `acqu2s`) is on the same
"real points" scale as `acqu2s TD`, not on the same scale as `nuslist`
indices for complex/echo-antiecho experiments. For exp3 (HSQC, FnMODE=6),
`max(nuslist) == 199` while `NusTD == 400` -- this is expected, not a bug:
`nuslist` indexes complex *pairs* (0-based, `NusTD // 2 == 200` slots), the
same real/complex halving that governs the `n_sampled` assertion itself,
applied one level up to the full-grid size. Do not "fix" this by inferring
grid size from `max(nuslist) + 1` -- always use `NusTD` as read from
`acqu2s`.
"""

from pathlib import Path

import nmrglue as ng

from lucy_ng.models.nus import COMPLEX_FNMODES, REAL_FNMODES, NusSchedule
from lucy_ng.nus.params import read_nus_params


def expected_sample_count(fnmode: int, td_f1: int) -> int:
    """Derive the expected `nuslist` length from FnMODE and F1 `TD`.

    Args:
        fnmode: `acqu2s FnMODE` (F1/indirect dimension) -- never `acqus`'s
            vestigial, always-0 `FnMODE`.
        td_f1: `acqu2s TD` (F1/indirect dimension).

    Returns:
        The FnMODE-derived expected sample count: `td_f1` for real-only
        modes (QF, QSEQ), `td_f1 // 2` for complex-pair modes (States,
        States-TPPI, Echo-AntiEcho).

    Raises:
        NotImplementedError: If `fnmode` is not a recognized real or
            complex mode. Refuses to guess rather than silently defaulting
            to either branch.
    """
    if fnmode in REAL_FNMODES:
        return td_f1
    if fnmode in COMPLEX_FNMODES:
        return td_f1 // 2
    raise NotImplementedError(
        f"FnMODE={fnmode} is not a recognized real/complex mode; "
        "refusing to guess a sample-count relationship."
    )


def validate_schedule(fnmode: int, td_f1: int, nuslist: list[int]) -> None:
    """Assert `nuslist` length matches the FnMODE-derived expected count.

    Args:
        fnmode: `acqu2s FnMODE` (F1/indirect dimension).
        td_f1: `acqu2s TD` (F1/indirect dimension).
        nuslist: Acquisition-ordered, 0-based sampled grid indices.

    Raises:
        NotImplementedError: Propagated from `expected_sample_count` for an
            unrecognized FnMODE.
        ValueError: If `len(nuslist)` does not match the FnMODE-derived
            expected count. This is the correctness crux (NUS-03) -- never
            sort, regenerate, or silently truncate/pad the schedule to make
            it "fit".
    """
    n_sampled = expected_sample_count(fnmode, td_f1)
    if n_sampled != len(nuslist):
        raise ValueError(
            f"NUS schedule length mismatch: FnMODE={fnmode} implies "
            f"n_sampled={n_sampled} (from TD={td_f1}), but nuslist has "
            f"{len(nuslist)} entries. Refusing to proceed -- never sort, "
            "regenerate, or silently truncate/pad the schedule."
        )


def read_nus_schedule(expdir: str | Path) -> NusSchedule:
    """Parse a Bruker NUS experiment directory into a validated `NusSchedule`.

    Reads `nuslist` directly (via `nmrglue.bruker.read_nuslist`, which parses
    the file's rows in on-disk order -- i.e. acquisition order, never
    sorted) and reads FnMODE/TD/NusTD authoritatively via
    `lucy_ng.nus.params.read_nus_params` (`acqu2s`, never `acqus`'s
    vestigial `FnMODE`). The FnMODE-derived hard assertion
    (`validate_schedule`) is run before any `NusSchedule` is constructed.

    Args:
        expdir: Path to a Bruker NUS experiment directory (contains
            `acqus`, `acqu2s`, `nuslist`).

    Returns:
        Validated `NusSchedule` with `nuslist` preserved in acquisition
        order and `n_sampled == len(nuslist)`.

    Raises:
        FileNotFoundError: If `expdir` (or the `nuslist` file within it)
            does not exist.
        NotImplementedError: If FnMODE is not a recognized real/complex
            mode.
        ValueError: If `n_sampled != len(nuslist)` (schedule/parameter
            mismatch) or a required acquisition parameter is missing.
    """
    # nmrglue's own read_nuslist() only raises OSError for a missing
    # directory; normalize to FileNotFoundError to match read_nus_params'
    # and the rest of the project's fail-loud, existence-checked-first
    # convention (T-97-01).
    resolved = Path(expdir).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"NUS experiment directory not found: {resolved}")

    params = read_nus_params(resolved)

    # nmrglue's read_nuslist() parses rows in on-disk (acquisition) order,
    # one 1-tuple per row -- flatten to a plain list[int], never sorted.
    raw_nuslist = ng.bruker.read_nuslist(str(resolved))
    nuslist = [row[0] for row in raw_nuslist]

    validate_schedule(params.fnmode_f1, params.f1_td, nuslist)

    return NusSchedule(
        nuslist=nuslist,
        fnmode_f1=params.fnmode_f1,
        td_f1=params.f1_td,
        nus_td=params.nus_td,
        n_sampled=len(nuslist),
    )
