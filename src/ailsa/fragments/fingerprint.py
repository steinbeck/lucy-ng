"""256-bit fingerprint encoding for subspectrum shifts.

A fingerprint compactly encodes a set of 13C chemical shifts as a 256-bit
(32-byte) bitset.  Each bit represents a 2 ppm wide bin:

    bin N covers [N * bin_ppm, (N+1) * bin_ppm)

With the default ``bin_ppm=2.0`` and 256 bins, the range is 0–511 ppm.
Shifts outside [0, 512) ppm are silently ignored.

The fingerprint is used for fast Boolean-AND pre-screening during SSC lookup
in Phase 51: the query fingerprint is AND-ed against each stored bitset; a
zero result means no overlap, eliminating the candidate without finer matching.
"""

from __future__ import annotations

import numpy as np

BIN_SIZE_PPM = 2.0
FINGERPRINT_BITS = 256
FINGERPRINT_BYTES = 32  # 256 / 8


def shifts_to_fingerprint(
    shifts: list[float], bin_ppm: float = BIN_SIZE_PPM
) -> bytes:
    """Encode 13C shifts as a 256-bit fingerprint (32 bytes).

    Each bit represents a 2 ppm bin.  Bin N covers
    ``[N * bin_ppm, (N+1) * bin_ppm)`` ppm.  With the default ``bin_ppm=2.0``,
    the valid range is 0–511 ppm (256 bins × 2 ppm = 512 ppm range).

    Shifts outside ``[0, 512)`` ppm are silently ignored.  Setting the same
    bit twice (two shifts in the same bin) is idempotent via bitwise OR.

    Args:
        shifts: List of 13C chemical shift values in ppm.
        bin_ppm: Bin width in ppm (default 2.0).

    Returns:
        32-byte fingerprint as a :class:`bytes` object.
    """
    fp = np.zeros(FINGERPRINT_BYTES, dtype=np.uint8)
    for shift in shifts:
        if 0.0 <= shift < FINGERPRINT_BITS * bin_ppm:
            bin_idx = int(shift / bin_ppm)
            fp[bin_idx // 8] |= np.uint8(1 << (bin_idx % 8))
    return fp.tobytes()


def expand_query_fingerprint(fp: bytes, expand_bins: int = 1) -> bytes:
    """Expand a query fingerprint by setting neighbouring bits.

    For each set bit in *fp*, the ``expand_bins`` neighbours on each side are
    also set.  This compensates for bin-boundary effects: a stored SSC shift
    at 45.1 ppm (bin 22) will match a query shift at 44.9 ppm (also bin 22
    but near the edge) thanks to the ±1 bin tolerance.

    Expansion is applied **only** to the query fingerprint.  Stored SSC
    fingerprints in the database are never expanded.

    Edge handling: bits at index 0 do not wrap to 255 and vice versa.

    Args:
        fp: 32-byte fingerprint from :func:`shifts_to_fingerprint`.
        expand_bins: Number of neighbouring bins to set on each side
            (default 1, giving ±1 bin = ±2 ppm tolerance).

    Returns:
        32-byte expanded fingerprint as a :class:`bytes` object.
    """
    bits = np.unpackbits(
        np.frombuffer(fp, dtype=np.uint8), bitorder="little"
    )
    expanded = bits.copy()
    set_indices = np.nonzero(bits)[0]
    for idx in set_indices:
        lo = max(0, idx - expand_bins)
        hi = min(FINGERPRINT_BITS - 1, idx + expand_bins)
        expanded[lo : hi + 1] = 1
    return np.packbits(expanded, bitorder="little").tobytes()
