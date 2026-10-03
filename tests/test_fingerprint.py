"""Tests for the fingerprint encoding utility (Phase 50, Plan 01).

Covers:
- shifts_to_fingerprint() output type, length, and bit encoding
- Edge cases: empty input, negative shifts, out-of-range shifts, boundary values
- Same-bin idempotency, multi-bin encoding, roundtrip verification
"""

from __future__ import annotations

import numpy as np
import pytest

from ailsa.fragments import shifts_to_fingerprint


class TestShiftsToFingerprint:
    """Tests for shifts_to_fingerprint(shifts, bin_ppm=2.0) -> bytes."""

    def test_empty_shifts_returns_zero_bytes(self) -> None:
        """shifts_to_fingerprint([]) must return 32 zero bytes."""
        result = shifts_to_fingerprint([])
        assert result == bytes(32)
        assert len(result) == 32

    def test_single_shift_sets_correct_bit(self) -> None:
        """Shift 18.1 ppm -> bin 9 -> byte[1] bit 1 must be set.

        bin_idx = int(18.1 / 2.0) = 9
        byte index = 9 // 8 = 1
        bit index  = 9 %  8 = 1
        byte value = 1 << 1 = 2 = 0b00000010
        """
        result = shifts_to_fingerprint([18.1])
        fp = np.frombuffer(result, dtype=np.uint8)
        # Byte 1 must have bit 1 set (value 2)
        assert fp[1] & (1 << 1), "Bit 9 (byte 1, bit 1) must be set for shift 18.1 ppm"
        # All other bytes must be zero
        mask = np.zeros(32, dtype=np.uint8)
        mask[1] = 1 << 1
        assert np.array_equal(fp, mask)

    def test_two_shifts_in_same_bin(self) -> None:
        """Shifts 18.1 and 18.9 are both in bin 9 -> same result as single shift."""
        single = shifts_to_fingerprint([18.1])
        double = shifts_to_fingerprint([18.1, 18.9])
        assert single == double, "Two shifts in same bin must produce identical fingerprint (OR is idempotent)"

    def test_two_shifts_in_different_bins(self) -> None:
        """Shifts 18.1 (bin 9) and 57.5 (bin 28) must both be set.

        57.5 / 2.0 = 28.75 -> bin 28
        byte index = 28 // 8 = 3
        bit index  = 28 %  8 = 4
        byte value = 1 << 4 = 16
        """
        result = shifts_to_fingerprint([18.1, 57.5])
        fp = np.frombuffer(result, dtype=np.uint8)
        # Bit 9 set (byte 1, bit 1)
        assert fp[1] & (1 << 1), "Bit 9 must be set for shift 18.1"
        # Bit 28 set (byte 3, bit 4)
        assert fp[3] & (1 << 4), "Bit 28 must be set for shift 57.5"
        # Exactly two bytes non-zero
        non_zero = np.count_nonzero(fp)
        assert non_zero == 2, f"Exactly 2 bytes should be non-zero, got {non_zero}"

    def test_output_is_32_bytes(self) -> None:
        """Any input must produce exactly 32 bytes."""
        assert len(shifts_to_fingerprint([])) == 32
        assert len(shifts_to_fingerprint([100.0])) == 32
        assert len(shifts_to_fingerprint([10.0, 20.0, 130.0])) == 32

    def test_shift_at_zero(self) -> None:
        """Shift 0.5 -> bin 0 -> byte[0] bit 0 must be set."""
        result = shifts_to_fingerprint([0.5])
        fp = np.frombuffer(result, dtype=np.uint8)
        assert fp[0] & 1, "Bit 0 (byte 0, bit 0) must be set for shift 0.5 ppm"

    def test_shift_near_max(self) -> None:
        """Shift 510.0 -> bin 255 -> byte[31] bit 7 must be set.

        510.0 / 2.0 = 255 -> bin 255
        byte index = 255 // 8 = 31
        bit index  = 255 %  8 = 7
        byte value = 1 << 7 = 128
        """
        result = shifts_to_fingerprint([510.0])
        fp = np.frombuffer(result, dtype=np.uint8)
        assert fp[31] & (1 << 7), "Bit 255 (byte 31, bit 7) must be set for shift 510.0 ppm"

    def test_negative_shift_ignored(self) -> None:
        """Negative shifts must be silently ignored -> all zero bytes."""
        result = shifts_to_fingerprint([-5.0])
        assert result == bytes(32), "Negative shift must produce all-zero fingerprint"

    def test_shift_at_512_ignored(self) -> None:
        """Shift >= 512.0 is out of range and must be ignored.

        512.0 / 2.0 = 256, which would be bin 256 (out of 0-255 range).
        """
        result = shifts_to_fingerprint([512.0])
        assert result == bytes(32), "Shift 512.0 must produce all-zero fingerprint (out of range)"

    def test_roundtrip_bit_check(self) -> None:
        """For shifts [30.5, 130.2, 199.1], verify each expected bin bit is set.

        30.5  / 2.0 = 15.25 -> bin 15  -> byte 1, bit 7
        130.2 / 2.0 = 65.1  -> bin 65  -> byte 8, bit 1
        199.1 / 2.0 = 99.55 -> bin 99  -> byte 12, bit 3
        """
        shifts = [30.5, 130.2, 199.1]
        result = shifts_to_fingerprint(shifts)
        fp = np.frombuffer(result, dtype=np.uint8)

        expected_bins = [int(s / 2.0) for s in shifts]
        for shift, bin_idx in zip(shifts, expected_bins):
            byte_idx = bin_idx // 8
            bit_idx = bin_idx % 8
            assert fp[byte_idx] & (1 << bit_idx), (
                f"Bit {bin_idx} (byte {byte_idx}, bit {bit_idx}) must be set "
                f"for shift {shift} ppm"
            )
