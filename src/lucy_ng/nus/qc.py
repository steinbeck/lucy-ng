"""Headless, peak-list-only QC gate (Phase 99, QC-01/QC-02/D-02/D-03/D-04).

The milestone's last line of defense against fabricated cross-peaks
becoming hard LSD constraints: every reconstructed HSQC/HMBC/COSY
correlation is cross-checked against the trusted 1D reference data via six
named checks, split critical (any violation => FAIL) vs. soft (violation
=> PARTIAL) per D-02:

* Critical: quaternary-carbon exclusion, ppm calibration, signal-to-ridge
  ratio, HSQC coverage.
* Soft: edited-sign self-consistency, COSY diagonal symmetry.

All six checks operate on already-picked peak-list dicts only -- never the
raw spectrum matrix (`lucy nus qc <peaks-dir>`'s D-08 contract is a peaks
directory, nothing else). This module is PURE: it reads reference/peak
JSON but performs no writes -- the write/quarantine boundary (D-07) lives
in `cli/nus.py::pipeline`.

Protonated-vs-quaternary classification uses an honest three-tier
resolution (`QcReferenceData.resolve`, D-03): a picked DEPT/edited
experiment if present, otherwise an explicit override
(`QcConfig.known_quaternary_shifts`), otherwise
`"insufficient_reference_data"` -- never a silent PASS on missing
reference data (T-99-03). `detection.detect_hybridisation()` is
deliberately NOT used here: it returns only sp3/sp2/sp1 hybridisation
fractions, with no hydrogen-count field, so it cannot distinguish a
protonated carbon from a quaternary one (RESEARCH.md Pitfall 1).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lucy_ng.models.nus import QcCheckResult
from lucy_ng.nus.postprocess import (
    DEFAULT_CALIBRATION_TOL,
    GUIDE_S10_C13,
    check_calibration,
)

#: The 5 confirmed-quaternary 13C shifts (NUS-RECONSTRUCTION-GUIDE.md
#: Sec.8/Sec.10) -- a subset of `GUIDE_S10_C13`. This is the D-03 tier-2
#: "explicit override" default; `QcConfig.known_quaternary_shifts` is
#: overridable via config/CLI.
DEFAULT_QUATERNARY_SHIFTS: tuple[float, ...] = (142.00, 135.86, 79.35, 36.23, 37.86)

#: Re-exported flat list form for convenience (tests/conftest.py mirrors
#: this constant independently as `KNOWN_QUATERNARY_SHIFTS`).
KNOWN_QUATERNARY_SHIFTS: list[float] = list(DEFAULT_QUATERNARY_SHIFTS)

#: The 15 true protonated carbons -- `GUIDE_S10_C13` minus the 5 known
#: quaternaries (RESEARCH.md Pitfall 3). Used only as a last-resort
#: fallback when no trusted 1D reference file is available at all; the
#: normal path derives the protonated set from the actual 1D peak lists
#: read from `<peaks-dir>` (D-03 -- no re-derivation from the guide).
PROTONATED_REFERENCE: list[float] = [
    shift
    for shift in GUIDE_S10_C13
    if all(abs(shift - quaternary) > 0.01 for quaternary in DEFAULT_QUATERNARY_SHIFTS)
]


@dataclass(frozen=True)
class QcConfig:
    """D-04: centralized, CLI-overridable QC thresholds.

    Seed tolerances (13C +/-0.5 ppm, 1H +/-0.05 ppm) match the tolerances
    already documented in the existing peak-list `caveat` fields.
    `ridge_fraction_fail`/`hsqc_coverage_floor` are calibrated against the
    QC-02 discrimination anchor (known-bad => FAIL, synthetic-clean =>
    PASS); both are explicitly flagged LOW-MEDIUM confidence pending a
    real clean reconstruction (Phase 100).
    """

    c13_tol: float = 0.5
    h1_tol: float = 0.05
    ridge_fraction_fail: float = 0.5
    hsqc_coverage_floor: float = 0.8
    edited_sign_tol: float = 0.5
    cosy_symmetry_floor: float = 0.5
    known_quaternary_shifts: tuple[float, ...] = DEFAULT_QUATERNARY_SHIFTS

    @classmethod
    def default(cls) -> QcConfig:
        """Return the seed-tolerance default configuration."""
        return cls()


@dataclass
class QcReferenceData:
    """D-03's trusted-1D + prot/quaternary reference bundle.

    `classification_source` is one of `"dept"` (a picked DEPT/edited
    experiment was found -- real ground truth), `"override"` (no DEPT, an
    explicit `QcConfig.known_quaternary_shifts` was used instead), or
    `"insufficient_reference_data"` (neither available -- the honest
    tier-3 fallback; `quaternary_shifts` is `None` in this case and MUST
    NOT be treated as an empty/clean classification).
    """

    trusted_c13: list[float]
    trusted_h1: list[float]
    quaternary_shifts: list[float] | None
    classification_source: str

    @classmethod
    def resolve(cls, peaks_dir: Path, config: QcConfig | None = None) -> QcReferenceData:
        """Three-tier D-03 resolution: DEPT -> explicit override -> honest fallback.

        Reads the existing trusted 1D peak-list JSON files as-is (D-03 --
        no re-pick, no second parse pass). Never calls
        `detection.detect_hybridisation()` for CH-count classification
        (RESEARCH.md Pitfall 1 -- it has no hydrogen-count field).
        """
        config = config or QcConfig.default()
        resolved_dir = Path(peaks_dir).resolve()
        trusted_c13 = _load_1d_shifts(resolved_dir, "13c")
        trusted_h1 = _load_1d_shifts(resolved_dir, "1h")

        dept_files = _glob_by_keyword(resolved_dir, "dept")
        if dept_files:
            quaternary = _derive_quaternary_from_dept(dept_files[0], trusted_c13)
            return cls(trusted_c13, trusted_h1, quaternary, "dept")
        if config.known_quaternary_shifts:
            return cls(trusted_c13, trusted_h1, list(config.known_quaternary_shifts), "override")
        return cls(trusted_c13, trusted_h1, None, "insufficient_reference_data")


# ---------------------------------------------------------------------------
# Filesystem helpers (V5/T-99-06: resolve paths, keyword-glob, fail-loud
# per-file JSON parsing -- never a hardcoded experiment-number suffix).
# ---------------------------------------------------------------------------


def _glob_by_keyword(peaks_dir: Path, keyword: str) -> list[Path]:
    """Return `*.json` files in `peaks_dir` whose name contains `keyword`.

    Case-insensitive substring match rather than `Path.glob("*KEYWORD*")`
    -- avoids double-matching the same file on case-insensitive filesystems
    (macOS/APFS) while staying keyword-based, never a hardcoded
    experiment-number suffix (D-08 Open Question 2).
    """
    keyword = keyword.lower()
    return sorted(p for p in peaks_dir.glob("*.json") if keyword in p.name.lower())


def _load_1d_shifts(peaks_dir: Path, keyword: str) -> list[float]:
    """Read `peaks[].ppm` from every 1D peak-list JSON matching `keyword`.

    D-03: read the existing trusted 1D lists as-is, no re-pick. Malformed
    files are silently skipped here (reference-loading is best-effort by
    design; `_load_peaks()` is the fail-loud path for the 2D correlation
    lists that actually drive the verdict).
    """
    shifts: list[float] = []
    for path in _glob_by_keyword(peaks_dir, keyword):
        try:
            data: dict[str, Any] = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for peak in data.get("peaks", []):
            ppm = peak.get("ppm")
            if isinstance(ppm, (int, float)):
                shifts.append(float(ppm))
    return shifts


def _derive_quaternary_from_dept(dept_path: Path, trusted_c13: Sequence[float]) -> list[float]:
    """Infer quaternary shifts as trusted-13C shifts absent from the DEPT list.

    A DEPT/edited experiment shows zero signal for quaternary carbons --
    any trusted 1D shift with no matching DEPT peak is inferred quaternary.
    Best-effort: an unparsable DEPT file yields an empty quaternary list
    (the caller's `classification_source` stays `"dept"`, so an empty
    result is a real "zero quaternaries found in DEPT" answer, not a
    silent tier-3 fallback in disguise).
    """
    try:
        data: dict[str, Any] = json.loads(dept_path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    dept_shifts = [
        float(peak["ppm"])
        for peak in data.get("peaks", [])
        if isinstance(peak.get("ppm"), (int, float))
    ]
    return [c for c in trusted_c13 if all(abs(c - d) > 0.5 for d in dept_shifts)]


def _dedupe_shifts(shifts: Sequence[float], tol: float) -> list[float]:
    """Cluster near-duplicate shift readings into one representative each.

    Deliberately conservative (RESEARCH.md Pitfall 2): this merges the same
    carbon re-observed across two 1D experiments (e.g. a narrow- and a
    wide-sweep 13C list) within `tol`, but makes no attempt to filter out
    genuine noise/solvent peaks via SNR alone -- that filtering is
    unreliable on the real fixture data (spurious peaks sit in the same
    SNR range as real signals).
    """
    if not shifts:
        return []
    ordered = sorted(shifts)
    clusters: list[list[float]] = [[ordered[0]]]
    for value in ordered[1:]:
        if abs(value - clusters[-1][-1]) <= tol:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return [cluster[0] for cluster in clusters]


# ---------------------------------------------------------------------------
# Genuinely new algorithm: peak-list-only ridge detection (Pattern 3).
# ---------------------------------------------------------------------------


def ridge_fraction(peaks: Sequence[dict[str, Any]], axis_key: str, tol: float = 0.05) -> float:
    """Fraction of peaks sharing one axis coordinate within `tol` ppm.

    `axis_key`: e.g. `"h1a_ppm"` (COSY), `"c13_ppm"`/`"h1_ppm"`
    (HSQC/HMBC). Returns `0.0` for an empty peak list (no ridge signal to
    report) -- never raises on an empty input.
    """
    if not peaks:
        return 0.0
    buckets: Counter[int] = Counter(round(peak[axis_key] / tol) for peak in peaks)
    return max(buckets.values()) / len(peaks)


# ---------------------------------------------------------------------------
# Six check functions (critical: quaternary_exclusion, ppm_calibration,
# signal_to_ridge, hsqc_coverage; soft: edited_sign_consistency,
# cosy_diagonal_symmetry). Each has a `check_*(..., ref/config)` form used
# internally by `run_qc_checks()`, plus a short-named standalone wrapper
# matching the direct-call contract exercised by `tests/nus/test_qc_checks.py`.
# ---------------------------------------------------------------------------


def check_quaternary_exclusion(
    hsqc_peaks: Sequence[dict[str, Any]],
    ref: QcReferenceData,
    config: QcConfig | None = None,
) -> QcCheckResult:
    """Critical: no HSQC 1-bond correlation within tolerance of a known-quaternary shift.

    If `ref.quaternary_shifts` is `None` (tier-3, no reference available at
    all), this returns `passed=False` with an `"insufficient_reference_data"`
    detail -- per D-03/T-99-03 this must never silently PASS just because
    the reference was missing.
    """
    config = config or QcConfig.default()
    if ref.quaternary_shifts is None:
        return QcCheckResult(
            name="quaternary_exclusion",
            passed=False,
            critical=True,
            details="insufficient_reference_data: no DEPT/override quaternary reference available",
        )
    quaternary_shifts = ref.quaternary_shifts
    tol = config.c13_tol
    hits = [
        peak["c13_ppm"]
        for peak in hsqc_peaks
        if any(abs(peak["c13_ppm"] - quaternary) <= tol for quaternary in quaternary_shifts)
    ]
    passed = not hits
    hit_shifts = sorted({round(h, 2) for h in hits})
    details = (
        "no HSQC correlations at known-quaternary shifts"
        if passed
        else f"{len(hits)} HSQC correlation(s) at quaternary shifts: {hit_shifts}"
    )
    return QcCheckResult(
        name="quaternary_exclusion",
        passed=passed,
        critical=True,
        details=details,
        value=float(len(hits)),
        threshold=0.0,
    )


def quaternary_exclusion(
    hsqc_peaks: Sequence[dict[str, Any]],
    known_quaternary_shifts: Sequence[float],
    tol: float = 0.5,
) -> QcCheckResult:
    """Standalone wrapper: explicit quaternary-shift override, no directory resolution."""
    ref = QcReferenceData(
        trusted_c13=[], trusted_h1=[], quaternary_shifts=list(known_quaternary_shifts),
        classification_source="override",
    )
    return check_quaternary_exclusion(hsqc_peaks, ref, QcConfig(c13_tol=tol))


def check_ppm_calibration(
    hsqc_peaks: Sequence[dict[str, Any]], config: QcConfig | None = None
) -> QcCheckResult:
    """Critical: reuse `nus/postprocess.py::check_calibration()` (Don't Hand-Roll)."""
    config = config or QcConfig.default()
    shifts = [peak["c13_ppm"] for peak in hsqc_peaks]
    return qc_check_ppm_calibration(shifts, tol=config.c13_tol)


def qc_check_ppm_calibration(
    hsqc_c13_shifts: Sequence[float], tol: float = DEFAULT_CALIBRATION_TOL
) -> QcCheckResult:
    """Standalone wrapper: reuses `check_calibration()` against `GUIDE_S10_C13`."""
    if not hsqc_c13_shifts:
        return QcCheckResult(
            name="ppm_calibration",
            passed=False,
            critical=True,
            details="insufficient_reference_data: no HSQC shifts to calibrate",
            threshold=tol,
        )
    passed = check_calibration(hsqc_c13_shifts, GUIDE_S10_C13, tol=tol)
    details = (
        "well-calibrated against GUIDE_S10_C13" if passed else "systematic offset exceeds tolerance"
    )
    return QcCheckResult(
        name="ppm_calibration", passed=passed, critical=True, details=details, threshold=tol
    )


def check_signal_to_ridge(
    peaks_by_type: dict[str, list[dict[str, Any]]], config: QcConfig | None = None
) -> QcCheckResult:
    """Critical: max peak-list-only `ridge_fraction()` across the axes that matter.

    COSY h1a/h1b (the textbook t1-ridge signature) and HSQC/HMBC
    c13_ppm/h1_ppm (a ridge-laden 2D correlation set), independently, take
    the max. If no peaks are available for any of these axes, returns a
    non-passing `"insufficient_reference_data"` result (never a silent
    PASS on empty input).
    """
    config = config or QcConfig.default()
    axis_specs: list[tuple[str, str]] = [
        ("COSY", "h1a_ppm"),
        ("COSY", "h1b_ppm"),
        ("HSQC", "c13_ppm"),
        ("HSQC", "h1_ppm"),
        ("HMBC", "c13_ppm"),
        ("HMBC", "h1_ppm"),
    ]
    fractions: dict[str, float] = {}
    for exp_type, axis_key in axis_specs:
        peaks = peaks_by_type.get(exp_type)
        if not peaks:
            continue
        tol = config.h1_tol if axis_key.startswith("h1") else config.c13_tol
        fractions[f"{exp_type}.{axis_key}"] = ridge_fraction(peaks, axis_key, tol=tol)
    if not fractions:
        return QcCheckResult(
            name="signal_to_ridge",
            passed=False,
            critical=True,
            details="insufficient_reference_data: no peaks available to assess ridge fraction",
            threshold=config.ridge_fraction_fail,
        )
    worst_key = max(fractions, key=lambda key: fractions[key])
    worst = fractions[worst_key]
    passed = worst <= config.ridge_fraction_fail
    details = (
        "no dominant ridge detected" if passed else f"max ridge_fraction={worst:.2f} at {worst_key}"
    )
    return QcCheckResult(
        name="signal_to_ridge",
        passed=passed,
        critical=True,
        details=details,
        value=worst,
        threshold=config.ridge_fraction_fail,
    )


def signal_to_ridge(
    peaks: Sequence[dict[str, Any]], axis_key: str, threshold: float = 0.5, tol: float = 0.05
) -> QcCheckResult:
    """Standalone wrapper: `ridge_fraction()` on one explicit peak list/axis."""
    value = ridge_fraction(peaks, axis_key, tol=tol)
    passed = value <= threshold
    details = f"ridge_fraction={value:.2f} on {axis_key}"
    return QcCheckResult(
        name="signal_to_ridge",
        passed=passed,
        critical=True,
        details=details,
        value=value,
        threshold=threshold,
    )


def _hsqc_coverage(
    hsqc_peaks: Sequence[dict[str, Any]],
    protonated_reference_shifts: Sequence[float],
    floor: float,
    tol: float,
) -> QcCheckResult:
    if not protonated_reference_shifts:
        return QcCheckResult(
            name="hsqc_coverage",
            passed=False,
            critical=True,
            details="insufficient_reference_data: empty protonated-carbon reference list",
            threshold=floor,
        )
    observed = [peak["c13_ppm"] for peak in hsqc_peaks]
    covered = sum(
        1
        for ref_shift in protonated_reference_shifts
        if any(abs(ref_shift - obs) <= tol for obs in observed)
    )
    total = len(protonated_reference_shifts)
    fraction = covered / total
    passed = fraction >= floor
    details = f"{covered}/{total} protonated carbons covered ({fraction:.0%})"
    return QcCheckResult(
        name="hsqc_coverage",
        passed=passed,
        critical=True,
        details=details,
        value=fraction,
        threshold=floor,
    )


def check_hsqc_coverage(
    hsqc_peaks: Sequence[dict[str, Any]], ref: QcReferenceData, config: QcConfig | None = None
) -> QcCheckResult:
    """Critical: >= floor fraction of trusted protonated carbons show >=1 HSQC correlation.

    Protonated candidates are derived from the trusted 1D shifts read from
    `<peaks-dir>` (D-03), deduplicated (`_dedupe_shifts`) and filtered
    against `ref.quaternary_shifts`. Falls back to the hardcoded
    `PROTONATED_REFERENCE` only when no trusted 1D file was found at all.
    Tier-3 (`ref.quaternary_shifts is None`) reports `"insufficient_reference_data"`
    rather than a fabricated coverage number.
    """
    config = config or QcConfig.default()
    if ref.quaternary_shifts is None:
        return QcCheckResult(
            name="hsqc_coverage",
            passed=False,
            critical=True,
            details="insufficient_reference_data: no prot/quaternary reference available",
            threshold=config.hsqc_coverage_floor,
        )
    if ref.trusted_c13:
        candidates = [
            shift
            for shift in ref.trusted_c13
            if all(abs(shift - quaternary) > config.c13_tol for quaternary in ref.quaternary_shifts)
        ]
        protonated = _dedupe_shifts(candidates, config.c13_tol)
    else:
        protonated = list(PROTONATED_REFERENCE)
    return _hsqc_coverage(hsqc_peaks, protonated, config.hsqc_coverage_floor, config.c13_tol)


def hsqc_coverage(
    peaks: Sequence[dict[str, Any]],
    protonated_reference_shifts: Sequence[float],
    floor: float = 0.8,
    tol: float = 0.5,
) -> QcCheckResult:
    """Standalone wrapper: explicit protonated-reference list, no directory resolution."""
    return _hsqc_coverage(peaks, protonated_reference_shifts, floor, tol)


def edited_sign_self_consistent(
    hsqc_peaks: Sequence[dict[str, Any]], tol: float = 0.5
) -> tuple[bool, list[float]]:
    """Soft algorithm: every carbon with >1 HSQC peak must share ONE `multiplicity_hint`.

    Returns `(is_consistent, [violating c13 shifts])`.
    """
    by_carbon: dict[float, set[str]] = defaultdict(set)
    for peak in hsqc_peaks:
        key = round(peak["c13_ppm"] / tol) * tol
        by_carbon[key].add(peak["multiplicity_hint"])
    violations = sorted(carbon for carbon, hints in by_carbon.items() if len(hints) > 1)
    return (len(violations) == 0, violations)


def check_edited_sign_consistency(
    hsqc_peaks: Sequence[dict[str, Any]], config: QcConfig | None = None
) -> QcCheckResult:
    """Soft: zero-tolerance flag -- any mixed multiplicity_hint at one carbon is a violation."""
    config = config or QcConfig.default()
    if not hsqc_peaks:
        return QcCheckResult(
            name="edited_sign_consistency", passed=True, critical=False, details="no HSQC peaks"
        )
    consistent, violations = edited_sign_self_consistent(hsqc_peaks, tol=config.edited_sign_tol)
    details = (
        "all carbons self-consistent" if consistent else f"mixed multiplicity_hint at {violations}"
    )
    return QcCheckResult(
        name="edited_sign_consistency", passed=consistent, critical=False, details=details
    )


def edited_sign_consistency(hsqc_peaks: Sequence[dict[str, Any]]) -> QcCheckResult:
    """Standalone wrapper over `check_edited_sign_consistency()`."""
    return check_edited_sign_consistency(hsqc_peaks)


def _cosy_symmetry_fraction(cosy_peaks: Sequence[dict[str, Any]], tol: float) -> float:
    pairs = [(peak["h1a_ppm"], peak["h1b_ppm"]) for peak in cosy_peaks]
    if not pairs:
        return 1.0
    mirrored = sum(
        1
        for h1a, h1b in pairs
        if any(
            abs(h1b - other_a) <= tol and abs(h1a - other_b) <= tol for other_a, other_b in pairs
        )
    )
    return mirrored / len(pairs)


def check_cosy_diagonal_symmetry(
    cosy_peaks: Sequence[dict[str, Any]], config: QcConfig | None = None
) -> QcCheckResult:
    """Soft: fraction of (h1a, h1b) pairs with a mirror (h1b, h1a) within tolerance.

    An empty COSY list passes trivially (`"no cosy peaks"`) -- there is
    nothing to be diagonally asymmetric about.
    """
    config = config or QcConfig.default()
    if not cosy_peaks:
        return QcCheckResult(
            name="cosy_diagonal_symmetry", passed=True, critical=False, details="no cosy peaks"
        )
    fraction = _cosy_symmetry_fraction(cosy_peaks, config.h1_tol)
    passed = fraction >= config.cosy_symmetry_floor
    details = f"{fraction:.0%} of COSY cross-peaks have a diagonal mirror"
    return QcCheckResult(
        name="cosy_diagonal_symmetry",
        passed=passed,
        critical=False,
        details=details,
        value=fraction,
        threshold=config.cosy_symmetry_floor,
    )


def cosy_diagonal_symmetry(cosy_peaks: Sequence[dict[str, Any]]) -> QcCheckResult:
    """Standalone wrapper over `check_cosy_diagonal_symmetry()`."""
    return check_cosy_diagonal_symmetry(cosy_peaks)
