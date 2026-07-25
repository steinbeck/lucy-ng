#!/usr/bin/env python3
"""Generate the trimmed JCAMP-DX HSQC fixture + copy 1D references.

Reads the real, external C20H32O2-jcamp source data (NOT committed as-is --
see SOURCE_DIR below) and writes into this directory:

  - C20H32O2_HSQC_trimmed.dx  -- 16 real F1 pages, header pruned to the keys
    the reader actually consumes (see KEEP_HEADER_PREFIXES). Byte-for-byte
    preserves the data-carrying ##PAGE=/##DATA TABLE= lines.
  - C20H32O2_1H.dx            -- whole copy of the real 1D 1H reference
  - C20H32O2_13C.dx           -- whole copy of the real 1D 13C reference

It also runs a one-page COSY/NOESY structural spot-check: throwaway/dev use
of nmrglue's own private `_readrawdic`/`_parse_data` here is fine (this is
verification tooling used only to build/validate the fixture, not shipped
reader code). This resolves RESEARCH.md Open Question 1 (do the homonuclear
2D files -- COSY/NOESY -- share HSQC's NTUPLES/PAGE/DATATABLE structure)
before Plan 04 commits to a single 2D code path. On success this prints the
exact line `COSY/NOESY SPOTCHECK PASS`.

Re-run this script any time the fixture needs regenerating:
    python tests/fixtures/jcamp/_generate_fixture.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import nmrglue.fileio.jcampdx as jc

SOURCE_DIR = (
    Path.home()
    / "Dropbox"
    / "develop"
    / "data"
    / "nmrdata"
    / "active-lucy-ng-testprojects"
    / "C20H32O2-jcamp"
)
FIXTURE_DIR = Path(__file__).parent

HSQC_SOURCE = SOURCE_DIR / "C20H32O2_HSQC.dx"
COSY_SOURCE = SOURCE_DIR / "C20H32O2_COSY.dx"
HMBC_SOURCE = SOURCE_DIR / "C20H32O2_HMBC.dx"
NOESY_SOURCE = SOURCE_DIR / "C20H32O2_NOESY.dx"
REF_1H_SOURCE = SOURCE_DIR / "C20H32O2_1H.dx"
REF_13C_SOURCE = SOURCE_DIR / "C20H32O2_13C.dx"

HSQC_TRIMMED = FIXTURE_DIR / "C20H32O2_HSQC_trimmed.dx"
COSY_TRIMMED = FIXTURE_DIR / "C20H32O2_COSY_trimmed.dx"
HMBC_TRIMMED = FIXTURE_DIR / "C20H32O2_HMBC_trimmed.dx"
NOESY_TRIMMED = FIXTURE_DIR / "C20H32O2_NOESY_trimmed.dx"
REF_1H_DEST = FIXTURE_DIR / "C20H32O2_1H.dx"
REF_13C_DEST = FIXTURE_DIR / "C20H32O2_13C.dx"

# Header keys the reader consumes (101-RESEARCH.md "Code Examples -- Fixture
# size measurement" + 101-01-PLAN.md Task 1); every other Bruker bulk `$`
# array key ($P, $D, $CNST, $SPNAM, $PLW, $SP, $GPNAM, AUDITTRAIL, ...) is
# pruned. Matched as literal line prefixes (case-sensitive, as they appear in
# the real Bruker JCAMP-DX export).
KEEP_HEADER_PREFIXES = (
    "##TITLE=",
    "##JCAMPDX=",
    "##DATA TYPE=",
    "##DATA CLASS=",
    "##NUM DIM=",
    "##.PULSE SEQUENCE=",
    "##.OBSERVE FREQUENCY=",
    "##.OBSERVE NUCLEUS=",
    "##.SHIFT REFERENCE=",
    "##.SOLVENT NAME=",
    "##$SF=",
    "##$SFO1=",
    "##$SFO2=",
    "##$BF1=",
    "##$BF2=",
    "##$OFFSET=",
    "##$NUC1=",
)

# F1 page-index window verified (101-RESEARCH.md) to contain real, non-noise
# gem-dimethyl / methyl cross-peaks (13C ~21.7-23.5 ppm, 1H ~0.96-0.99 ppm)
# used as the Plan 04 integration oracle.
PAGE_WINDOW = slice(1735, 1751)  # 16 pages

# 102-01-PLAN.md <interfaces>: verified strong-signal page windows (probed by
# decoding real pages on 2026-07-25), each a 16-page window matching PAGE_WINDOW's
# size.
# COSY: F1 ppm 1.5122 .. 1.4572; strongest cross-peak at F1=1.4792, F2=1.4796
# ppm (a genuine diagonal peak).
COSY_PAGE_WINDOW = slice(1512, 1528)  # 16 pages
# HMBC: strongest page 848, F1 ~= 36.4 ppm (13C).
HMBC_PAGE_WINDOW = slice(840, 856)  # 16 pages
# NOESY: strongest pages 824/832, F1 ~= 0.96 ppm (1H).
NOESY_PAGE_WINDOW = slice(824, 840)  # 16 pages


def _trim_header(lines: list[str]) -> list[str]:
    """Keep only pre-NTUPLES header lines the reader consumes."""
    return [line for line in lines if line.startswith(KEEP_HEADER_PREFIXES)]


def _find_ntuples_block(lines: list[str], label: str = "HSQC") -> tuple[int, int, list[int]]:
    """Return (ntuples_header_start, first_page_start, all_page_start_indices)."""
    ntuples_idx = next(i for i, line in enumerate(lines) if line.startswith("##NTUPLES="))
    page_indices = [i for i, line in enumerate(lines) if line.startswith("##PAGE=")]
    if not page_indices:
        raise ValueError(f"No ##PAGE= blocks found in source {label} file")
    return ntuples_idx, page_indices[0], page_indices


def _update_var_dim(line: str, new_f1_dim: int) -> str:
    """Replace VAR_DIM's F1 entry (first, per SYMBOL='F1,F2,Y' order)."""
    prefix, _, rest = line.partition("=")
    parts = [p.strip() for p in rest.split(",")]
    parts[0] = str(new_f1_dim)
    return f"{prefix}=   {', '.join(parts)}\n"


def build_trimmed_2d(source: Path, dest: Path, page_window: slice, label: str) -> None:
    """Read a real source 2D .dx file and write a page-windowed trimmed fixture.

    Generic across HSQC/COSY/HMBC/NOESY -- the header trim, ``##VAR_DIM=``
    rewrite, NTUPLES-header copy, page-window slicing, two-line
    ``##END NTUPLES=nD NMR SPECTRUM``/``##END=`` footer, and ``latin-1``
    encoding are identical regardless of which experiment is being trimmed.
    """
    if not source.exists():
        raise FileNotFoundError(
            f"Real source {label} file not found: {source}. "
            "This script requires the external C20H32O2-jcamp dataset."
        )
    lines = source.read_text(encoding="latin-1").splitlines(keepends=True)

    ntuples_idx, first_page_idx, page_indices = _find_ntuples_block(lines, label)
    if len(page_indices) < page_window.stop:
        raise ValueError(
            f"Source has only {len(page_indices)} pages; need at least {page_window.stop}"
        )

    header = _trim_header(lines[:ntuples_idx])

    # NTUPLES block header: from ##NTUPLES= up to (not including) the first ##PAGE=.
    ntuples_header = [
        _update_var_dim(line, page_window.stop - page_window.start)
        if line.startswith("##VAR_DIM=")
        else line
        for line in lines[ntuples_idx:first_page_idx]
    ]

    end_idx = next(i for i, line in enumerate(lines) if line.startswith("##END NTUPLES"))
    selected_indices = page_indices[page_window]

    page_blocks: list[str] = []
    for start in selected_indices:
        pos_in_all = page_indices.index(start)
        stop = page_indices[pos_in_all + 1] if pos_in_all + 1 < len(page_indices) else end_idx
        page_blocks.extend(lines[start:stop])

    footer = ["##END NTUPLES=nD NMR SPECTRUM\n", "##END=\n"]

    out_lines = header + ntuples_header + page_blocks + footer
    dest.write_text("".join(out_lines), encoding="latin-1")


def build_trimmed_hsqc() -> None:
    """Read the real source HSQC .dx and write the trimmed committed fixture."""
    build_trimmed_2d(HSQC_SOURCE, HSQC_TRIMMED, PAGE_WINDOW, "HSQC")


def build_trimmed_cosy() -> None:
    """Read the real source COSY .dx and write the trimmed committed fixture."""
    build_trimmed_2d(COSY_SOURCE, COSY_TRIMMED, COSY_PAGE_WINDOW, "COSY")


def build_trimmed_hmbc() -> None:
    """Read the real source HMBC .dx and write the trimmed committed fixture."""
    build_trimmed_2d(HMBC_SOURCE, HMBC_TRIMMED, HMBC_PAGE_WINDOW, "HMBC")


def build_trimmed_noesy() -> None:
    """Read the real source NOESY .dx and write the trimmed committed fixture."""
    build_trimmed_2d(NOESY_SOURCE, NOESY_TRIMMED, NOESY_PAGE_WINDOW, "NOESY")


def copy_1d_references() -> None:
    """Copy the two real 1D reference files whole into the fixture dir."""
    for source, dest in ((REF_1H_SOURCE, REF_1H_DEST), (REF_13C_SOURCE, REF_13C_DEST)):
        if not source.exists():
            raise FileNotFoundError(f"Real source 1D reference not found: {source}")
        shutil.copyfile(source, dest)


def spotcheck_cosy_noesy() -> None:
    """Decode one real page each from COSY and NOESY, fail loud if either is unreadable.

    Resolves 101-RESEARCH.md Open Question 1: confirms homonuclear 2D files
    (.NUCLEUS = "1H, 1H") share the same NTUPLES/PAGE/DATATABLE structure as
    the heteronuclear HSQC file before Plan 04 assumes one 2D code path.
    """
    for name, path in (("COSY", COSY_SOURCE), ("NOESY", NOESY_SOURCE)):
        if not path.exists():
            raise FileNotFoundError(f"Real source {name} file not found: {path}")
        raw = jc._readrawdic(str(path))
        datatype_keys = [key for key in raw if key.startswith("_datatype_")]
        if not datatype_keys:
            raise RuntimeError(f"{name}: no _datatype_* bucket found in raw dict")
        inner = raw[datatype_keys[0]][0]
        tables = inner.get("DATATABLE")
        if not tables:
            raise RuntimeError(f"{name}: no DATATABLE entries found")
        result = jc._parse_data(tables[0])
        if result is None:
            raise RuntimeError(f"{name}: _parse_data returned None for page 0")
        array, _dtype = result
        if array is None:
            raise RuntimeError(f"{name}: decoded array is None")

    print("COSY/NOESY SPOTCHECK PASS")


def main() -> int:
    build_trimmed_hsqc()
    build_trimmed_cosy()
    build_trimmed_hmbc()
    build_trimmed_noesy()
    copy_1d_references()
    spotcheck_cosy_noesy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
