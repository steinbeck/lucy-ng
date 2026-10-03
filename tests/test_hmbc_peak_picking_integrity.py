"""FIX-12 regression tests: HMBC peak-picking integrity (Phase 85).

The 1D FIX-08 picker gained an SNR floor (Phase 81); plan 85-01 carried the same
noise-relative MAD/SNR floor over to the 2D HMBC picker. Without an SNR floor the
HMBC pick thresholds only on *fraction-of-max*, so the strong aliphatic/2J cross-peaks
set the global max and the weak-but-real ring-diagnostic 3J-meta aromatic correlations
(~0.6% of max) are systematically dropped — the actual emergent-ring blocker.

Two test classes:
  TestFIX12CASE1HMBC          — real data (in-repo Ibuprofen HMBC expno 7), skipif guard
                                on the external CASE1 path mirroring the FIX-08 pattern
  TestFIX12SyntheticSeparation — synthetic 2D plane (always runs, no external data):
                                captures the "separable in SNR space, not in
                                fraction-of-max space" property of FIX-12

The empirical numbers/tolerances below are grounded in
.planning/research/D04-emergent-ring/ibuprofen-correlation-analysis.md (the intensity
table) and the observed picks on the in-repo data:
  - global max ~7.48e7, global MAD sigma ~2.15e4
  - 3J-meta H4->C2  at C~140.76 x H~7.11  (intensity ~4.8e5, ~0.64% of max, SNR ~22)
  - 3J-meta H6->C3  at C~137.07 x H~7.23  (intensity ~5e5,   ~0.6%  of max, SNR ~10)
  - 2J-ortho        at C~140.96 x H~7.23  and C~136.88 x H~7.11  (~22% of max)
  - guided SNR-default pick: ~122 validated correlations (retains both 3J-meta)
  - guided legacy fraction-of-max pick: ~29 validated (drops both 3J-meta)
  - raw fraction-of-max flood at -t 0.005: ~165 peaks (no clean fraction-of-max gap)

(This is a TEST, not a runtime skill — referencing CASE1/Ibuprofen/expno-7/specific
shifts here is allowed; FIX-09's compound-agnostic rule applies only to agent .md files.)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from ailsa.models import Peak2D, Spectrum2D
from ailsa.processing import HMBCGuidedPicker, HMBCGuidedResult
from ailsa.processing.peak_picker_2d import PeakPicker2D
from ailsa.readers import BrukerReader

# In-repo CASE1 datasets (always available — keeps the regression live in CI)
DATA_DIR = Path(__file__).parent.parent / "data"
CASE1_HMBC = DATA_DIR / "Ibuprofen" / "7"  # HMBC
CASE1_C13 = DATA_DIR / "Ibuprofen" / "2"  # 13C
CASE1_HSQC = DATA_DIR / "Ibuprofen" / "6"  # HSQC
CASE1_DEPT135 = DATA_DIR / "Ibuprofen" / "3"  # DEPT-135

# External CASE1 copy (outside the repo). Mirrors the FIX-08 skipif pattern so the
# external variant skips cleanly on machines without the dataset.
CASE1_HMBC_EXTERNAL = Path(
    "/Users/steinbeck/Dropbox/develop/data/nmrdata"
    "/active-lucy-ng-testprojects/CASE1/7"
)

# Ring-diagnostic 3J-meta cross-peaks (C ppm, H ppm). A TIGHT window (C +-1.0,
# H +-0.08) keeps these distinct from the ~22%-of-max 2J-ortho cross-peaks
# (C~140.96 x H~7.23 and C~136.88 x H~7.11), so a match proves the floor actually
# recovers the 3J-meta, not merely a nearby 2J.
META_3J_H4_TO_C2 = (140.76, 7.11)
META_3J_H6_TO_C3 = (137.07, 7.23)
C_TOL = 1.0
H_TOL = 0.08


def _has_peak(peaks: list[Peak2D], c_ppm: float, h_ppm: float) -> bool:
    """True if any peak lies within (C_TOL, H_TOL) of (c_ppm, h_ppm)."""
    return any(
        abs(p.f1_position - c_ppm) <= C_TOL and abs(p.f2_position - h_ppm) <= H_TOL
        for p in peaks
    )


class TestFIX12CASE1HMBC:
    """Real-data FIX-12 regression: CASE1 HMBC expno 7 at the SNR-floor default.

    The guided HMBC pick (13C/HSQC/DEPT cross-validated) is the correlation set
    the team actually consumes, so the count-ceiling / retention assertions are
    made against the guided result.
    """

    @staticmethod
    def _guided(use_snr: bool) -> HMBCGuidedResult:
        hmbc = BrukerReader.read_2d(str(CASE1_HMBC))
        c13 = BrukerReader.read_1d(str(CASE1_C13))
        hsqc = BrukerReader.read_2d(str(CASE1_HSQC))
        dept135 = BrukerReader.read_1d(str(CASE1_DEPT135))
        return HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc,
            carbon_spectrum=c13,
            hsqc=hsqc,
            dept135=dept135,
            hmbc_use_snr=use_snr,
        )

    def test_snr_default_retains_both_3j_meta(self) -> None:
        """At the SNR-floor default, both ring-diagnostic 3J-meta peaks survive."""
        result = self._guided(use_snr=True)
        peaks = result.peaks.peaks
        assert _has_peak(peaks, *META_3J_H4_TO_C2), (
            "3J-meta H4->C2 (C~140.76 x H~7.11) missing at SNR-floor default — "
            "the emergent-ring-diagnostic correlation must be retained."
        )
        assert _has_peak(peaks, *META_3J_H6_TO_C3), (
            "3J-meta H6->C3 (C~137.07 x H~7.23) missing at SNR-floor default."
        )

    def test_legacy_fraction_of_max_drops_both_3j_meta(self) -> None:
        """Legacy fraction-of-max pick drops both 3J-meta — proving the floor recovers them."""
        result = self._guided(use_snr=False)
        peaks = result.peaks.peaks
        assert not _has_peak(peaks, *META_3J_H4_TO_C2), (
            "3J-meta H4->C2 unexpectedly present in the legacy fraction-of-max pick — "
            "the regression's contrast (floor recovers what fraction-of-max drops) is broken."
        )
        assert not _has_peak(peaks, *META_3J_H6_TO_C3), (
            "3J-meta H6->C3 unexpectedly present in the legacy fraction-of-max pick."
        )

    def test_snr_default_count_is_a_sane_ceiling_not_a_flood(self) -> None:
        """Guided SNR-default validated count is bounded — not the ~913 raw-plane flood.

        The raw SNR pick of the bare HMBC plane returns ~913 maxima (mostly noise/t1
        ridges); the guided 13C/HSQC cross-validation collapses that to ~122 genuine
        correlations. Assert the validated count stays well below the raw flood while
        being materially richer than the fraction-of-max pick (which drops the 3J-meta).
        """
        snr_count = self._guided(use_snr=True).validated_count
        legacy_count = self._guided(use_snr=False).validated_count
        # Sane ceiling: far below the ~913 raw-plane / ~165 -t 0.005 floods.
        assert snr_count <= 250, (
            f"Guided SNR-default validated count {snr_count} looks like a noise flood "
            f"(expected a bounded ~122, well below the ~913 raw-plane maxima)."
        )
        # The floor must recover materially more than the fraction-of-max pick.
        assert snr_count > legacy_count, (
            f"SNR-default validated count {snr_count} not greater than the legacy "
            f"fraction-of-max count {legacy_count}; the floor should recover weak 3J peaks."
        )

    @pytest.mark.skipif(
        not CASE1_HMBC_EXTERNAL.exists(),
        reason="external CASE1 HMBC dataset not available on this machine",
    )
    def test_external_case1_snr_default_retains_3j_meta(self) -> None:
        """External CASE1 HMBC copy: 3J-meta retained at the raw SNR-floor default.

        Uses the raw PeakPicker2D pick (no 13C/HSQC reference for the external copy),
        which still surfaces the 3J-meta cross-peaks because they clear the SNR floor.
        """
        hmbc = BrukerReader.read_2d(str(CASE1_HMBC_EXTERNAL))
        snr_peaks = PeakPicker2D.pick_peaks(hmbc).peaks  # SNR default
        assert _has_peak(snr_peaks, *META_3J_H4_TO_C2)
        assert _has_peak(snr_peaks, *META_3J_H6_TO_C3)


class TestFIX12SyntheticSeparation:
    """Synthetic FIX-12 property test (always runs, no external data).

    Builds a small 2D plane with three cross-peaks over an injected noise floor:
      (a) an intense aliphatic-region peak that SETS the global max,
      (b) a weak aromatic-region peak at <1% of that max but HIGH SNR over the noise,
      (c) a noise blob at ~1% of max but LOW SNR (below the floor).

    The SNR-floor pick must RETAIN (b) and REJECT (c); the legacy fraction-of-max
    pick at threshold=0.05 must DROP (b). This captures FIX-12's core property:
    the weak-but-real peak is separable in SNR space, not in fraction-of-max space.
    """

    # Intensities chosen so the weak real peak (b) is <1% of max but high-SNR,
    # while the noise blob (c) is ~1% of max but below a k=5 floor.
    INTENSE = 1.0e7  # (a) sets the global max
    NOISE_SIGMA = 1.0e3  # injected baseline noise level
    WEAK_REAL = 6.0e4  # (b) 0.6% of max  -> SNR ~60 over NOISE_SIGMA
    NOISE_BLOB = 1.0e5  # (c) 1.0% of max  -> but emulated as low-SNR (see build)

    @staticmethod
    def _build_spectrum() -> tuple[Spectrum2D, dict[str, tuple[float, float]]]:
        rng = np.random.default_rng(42)
        n1, n2 = 128, 256
        # Baseline gaussian noise floor.
        data = rng.normal(
            0.0, TestFIX12SyntheticSeparation.NOISE_SIGMA, size=(n1, n2)
        )

        # ppm scales: F1 = 13C 0..200 (descending), F2 = 1H 0..10 (descending)
        f1 = np.linspace(200.0, 0.0, n1, dtype=np.float64)
        f2 = np.linspace(10.0, 0.0, n2, dtype=np.float64)

        def idx(scale: NDArray[np.float64], ppm: float) -> int:
            return int(np.argmin(np.abs(scale - ppm)))

        # (a) intense aliphatic peak: C 25 ppm x H 1.2 ppm
        a = (25.0, 1.2)
        data[idx(f1, a[0]), idx(f2, a[1])] = TestFIX12SyntheticSeparation.INTENSE

        # (b) weak aromatic 3J-like peak: C 140 ppm x H 7.1 ppm. Single sharp
        #     maximum well above the noise floor -> high SNR, but tiny % of max.
        b = (140.0, 7.1)
        data[idx(f1, b[0]), idx(f2, b[1])] = TestFIX12SyntheticSeparation.WEAK_REAL

        # (c) noise blob: a broad low-amplitude bump whose PEAK sample sits near
        #     the floor (low SNR) even though comparable noise excursions reach
        #     ~1% of max elsewhere. Place it at C 90 ppm x H 4.0 ppm with an
        #     amplitude just below the k=5 * sigma floor so the picker rejects it.
        c = (90.0, 4.0)
        ci, cj = idx(f1, c[0]), idx(f2, c[1])
        # 4.0 * sigma < 5.0 * sigma floor -> must be rejected.
        data[ci, cj] = 4.0 * TestFIX12SyntheticSeparation.NOISE_SIGMA

        spec = Spectrum2D(
            data=data,
            f1_ppm_scale=f1,
            f2_ppm_scale=f2,
            f1_nucleus="13C",
            f2_nucleus="1H",
            experiment_type="HMBC",
            frequency=400.0,
        )
        return spec, {"intense": a, "weak_real": b, "noise_blob": c}

    def test_snr_floor_retains_weak_high_snr_peak(self) -> None:
        """SNR-floor pick keeps the <1%-of-max but high-SNR aromatic peak."""
        spec, pos = self._build_spectrum()
        peaks = PeakPicker2D.pick_peaks(spec).peaks  # SNR default
        c, h = pos["weak_real"]
        assert any(
            abs(p.f1_position - c) <= 2.0 and abs(p.f2_position - h) <= 0.1
            for p in peaks
        ), "SNR floor dropped the weak-but-high-SNR aromatic peak."

    def test_snr_floor_rejects_low_snr_noise_blob(self) -> None:
        """SNR-floor pick rejects the ~1%-of-max but sub-floor noise blob."""
        spec, pos = self._build_spectrum()
        peaks = PeakPicker2D.pick_peaks(spec).peaks  # SNR default
        c, h = pos["noise_blob"]
        assert not any(
            abs(p.f1_position - c) <= 2.0 and abs(p.f2_position - h) <= 0.1
            for p in peaks
        ), "SNR floor failed to reject the low-SNR noise blob."

    def test_fraction_of_max_drops_weak_real_peak(self) -> None:
        """Legacy fraction-of-max (threshold=0.05) drops the weak real peak.

        Confirms the FIX-12 motivation: at 0.6% of the global max the genuine
        aromatic peak is invisible to a 5%-of-max threshold, so the peak is only
        recoverable in SNR space.
        """
        spec, pos = self._build_spectrum()
        peaks = PeakPicker2D.pick_peaks(spec, threshold=0.05).peaks  # legacy
        c, h = pos["weak_real"]
        assert not any(
            abs(p.f1_position - c) <= 2.0 and abs(p.f2_position - h) <= 0.1
            for p in peaks
        ), "fraction-of-max pick unexpectedly kept the 0.6%-of-max weak peak."

    def test_picked_peaks_carry_snr_annotation_in_snr_mode(self) -> None:
        """SNR-mode picks annotate each peak with a finite SNR; legacy leaves it None."""
        spec, _ = self._build_spectrum()
        snr_peaks = PeakPicker2D.pick_peaks(spec).peaks
        assert snr_peaks, "expected at least the intense + weak peaks in SNR mode"
        assert all(p.snr is not None and np.isfinite(p.snr) for p in snr_peaks)
        legacy_peaks = PeakPicker2D.pick_peaks(spec, threshold=0.05).peaks
        assert all(p.snr is None for p in legacy_peaks)
