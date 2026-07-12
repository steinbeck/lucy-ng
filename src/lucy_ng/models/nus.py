"""Data models for NUS (Non-Uniform Sampling) acquisition parameters and schedules.

D-04 superset: `NusAcquisitionParams` captures both the raw NUS
conversion parameters (SFO1, SW_h, TD per dimension, FnMODE, GRPDLY/DECIM,
byte order/dtype, NusAMOUNT, NusSEED) and the ppm-calibration parameters
Phase-98 processing will need (SF, OFFSET, per dimension) -- parsed once here
rather than forcing a second parse pass later.

The F1 (indirect, acqu2s) and F2 (direct, acqus) dimensions must never be
conflated: `acqus` carries a vestigial `FnMODE` key that is always `0` and is
NOT the value that governs sampling-schedule length -- only `acqu2s`'s
`FnMODE` (`fnmode_f1` here) matters. Field names in this module are chosen to
make that split unambiguous.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

# Nucleus set shared with Spectrum1D/Spectrum2D (models/spectrum.py) for
# consistency across the models package.
VALID_NUCLEI = {"1H", "13C", "15N", "31P", "19F", "2H"}

# Recognized Bruker FnMODE values for the indirect (F1) dimension.
# 1 (QF), 2 (QSEQ) are real-only; 4 (States), 5 (States-TPPI), 6
# (Echo-AntiEcho) are complex-pair modes. Any other value is refused rather
# than guessed -- shared with nus/schedule.py so the two never diverge.
REAL_FNMODES = {1, 2}
COMPLEX_FNMODES = {4, 5, 6}
VALID_FNMODES = REAL_FNMODES | COMPLEX_FNMODES


class NusAcquisitionParams(BaseModel):
    """Validated Bruker NUS acquisition + processing/calibration parameters.

    Populated per-experiment from `acqus`/`acqu2s` (acquisition) and
    `pdata/1/procs`/`pdata/1/proc2s` (processing/calibration, present even
    before NUS reconstruction). SF/OFFSET fields default to `None` because
    they describe a *processed* calibration that may not exist yet.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pulse_program: str

    # F2 (direct dimension, acqus)
    f2_nucleus: str
    f2_sfo1: float
    f2_sw_h: float
    f2_td: int

    # Digital-filter / data-type parameters (acqus)
    byte_order: int
    dtype_code: int
    decim: float
    dspfvs: int
    grpdly: float  # non-integer in practice -- never round

    # NUS acquisition parameters (acqus)
    nus_amount_pct: int
    nus_seed: int

    # F1 (indirect dimension, acqu2s)
    f1_nucleus: str
    f1_sfo1: float
    f1_sw_h: float
    f1_o1: float
    f1_td: int
    fnmode_f1: int  # read from acqu2s, NEVER acqus (acqus FnMODE is vestigial 0)
    nus_td: int  # authoritative full-grid size; never inferred from max(nuslist)+1

    # Processing/calibration -- from pdata/1/procs (F2) / pdata/1/proc2s (F1).
    # None is a legitimate pre-reconstruction state, not a parse failure.
    f2_sf: float | None = None
    f2_offset: float | None = None
    f1_sf: float | None = None
    f1_offset: float | None = None

    @field_validator("f1_nucleus", "f2_nucleus")
    @classmethod
    def validate_nucleus(cls, v: str) -> str:
        """Validate nucleus is a known NMR-active nucleus."""
        if v not in VALID_NUCLEI:
            raise ValueError(f"Unknown nucleus: {v}. Valid: {VALID_NUCLEI}")
        return v

    @field_validator("fnmode_f1")
    @classmethod
    def validate_fnmode_f1(cls, v: int) -> int:
        """Validate FnMODE (F1/indirect dimension) is a recognized real/complex mode."""
        if v not in VALID_FNMODES:
            raise ValueError(f"Unknown FnMODE: {v}. Valid: {sorted(VALID_FNMODES)}")
        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "pulse_program": self.pulse_program,
            "f2_nucleus": self.f2_nucleus,
            "f2_sfo1": self.f2_sfo1,
            "f2_sw_h": self.f2_sw_h,
            "f2_td": self.f2_td,
            "byte_order": self.byte_order,
            "dtype_code": self.dtype_code,
            "decim": self.decim,
            "dspfvs": self.dspfvs,
            "grpdly": self.grpdly,
            "nus_amount_pct": self.nus_amount_pct,
            "nus_seed": self.nus_seed,
            "f1_nucleus": self.f1_nucleus,
            "f1_sfo1": self.f1_sfo1,
            "f1_sw_h": self.f1_sw_h,
            "f1_o1": self.f1_o1,
            "f1_td": self.f1_td,
            "fnmode_f1": self.fnmode_f1,
            "nus_td": self.nus_td,
            "f2_sf": self.f2_sf,
            "f2_offset": self.f2_offset,
            "f1_sf": self.f1_sf,
            "f1_offset": self.f1_offset,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NusAcquisitionParams":
        """Create from dictionary."""
        return cls(**d)


class NusSchedule(BaseModel):
    """Validated NUS sampling schedule.

    `nuslist` is the acquisition-ordered list of sampled grid indices --
    never sorted (acquisition order matters for downstream reconstruction
    tooling). `nus_td` is the authoritative full-grid size (on the same
    real/complex-point scale as `td_f1`; see 97-RESEARCH.md's `nuslist`
    acquisition-order verification note for the real-vs-complex distinction
    between `nuslist` indices and `nus_td`). `n_sampled` must equal
    `len(nuslist)` -- asserted at build time in `nus/schedule.py`, not
    re-derived here.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    nuslist: list[int]  # acquisition order, never sorted
    fnmode_f1: int
    td_f1: int
    nus_td: int
    n_sampled: int  # == len(nuslist), asserted at build time in schedule.py

    @field_validator("fnmode_f1")
    @classmethod
    def validate_fnmode_f1(cls, v: int) -> int:
        """Validate FnMODE (F1/indirect dimension) is a recognized real/complex mode."""
        if v not in VALID_FNMODES:
            raise ValueError(f"Unknown FnMODE: {v}. Valid: {sorted(VALID_FNMODES)}")
        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "nuslist": list(self.nuslist),
            "fnmode_f1": self.fnmode_f1,
            "td_f1": self.td_f1,
            "nus_td": self.nus_td,
            "n_sampled": self.n_sampled,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NusSchedule":
        """Create from dictionary."""
        return cls(**d)
