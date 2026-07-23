# Phase 101: JCAMP-DX Reader - Pattern Map

**Mapped:** 2026-07-23
**Files analyzed:** 5 (2 new source modules, 2 new test modules, 1 new fixture directory)
**Analogs found:** 5 / 5 (all role/data-flow matches found in-repo; one file's core logic has no
in-repo analog and is vendored from an external New-BSD source instead — noted explicitly below)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/lucy_ng/readers/jcamp.py` | reader (parser/adapter) | file-I/O → transform → CRUD-style model construction | `src/lucy_ng/readers/bruker.py` | exact (same role, same repo, same target models) |
| `src/lucy_ng/readers/_jcampdx_decode.py` | utility (numeric decoder kernel) | transform (pure function, no I/O) | *(no in-repo analog — see "No Analog Found")* | vendored (external, New-BSD) |
| `tests/readers/test_jcamp.py` | test (integration) | request-response (call reader, assert model) | `tests/test_bruker_reader.py` | exact (same role, same target reader shape) |
| `tests/readers/test_jcampdx_decode.py` | test (unit, hand-oracle) | transform | `tests/test_bruker_reader.py` (structure only; no decoder-unit-test analog exists) | role-match |
| `tests/fixtures/jcamp/` | fixture data | file-I/O (static test data) | `tests/data/Ibuprofen/{1,2}/` (Bruker dirs used by `test_bruker_reader.py`) + `tests/fixtures/{nus,regression,form_tolerance}/` | role-match |

## Pattern Assignments

### `src/lucy_ng/readers/jcamp.py` (reader, file-I/O → transform)

**Analog:** `src/lucy_ng/readers/bruker.py` (read in full, 282 lines)

**Imports pattern** (bruker.py lines 1-9):
```python
"""Bruker NMR file reader."""

from pathlib import Path
from typing import Any

import nmrglue as ng
import numpy as np

from lucy_ng.models import Spectrum1D, Spectrum2D
```
Mirror directly for `jcamp.py` — same import shape (`nmrglue as ng`, `numpy as np`, models from
`lucy_ng.models`), plus a new same-package import:
```python
from lucy_ng.readers._jcampdx_decode import parse_data
from lucy_ng.readers.bruker import _detect_experiment_type  # D-10: reuse verbatim
```

**Class/API shape to mirror** (bruker.py lines 130-134, 197-198):
```python
class BrukerReader:
    """Reader for Bruker NMR data files."""

    @staticmethod
    def read_1d(experiment_dir: str | Path) -> Spectrum1D:
        ...

    @staticmethod
    def read_2d(experiment_dir: str | Path) -> Spectrum2D:
        ...
```
Per D-09, `JcampReader` copies this exact static-method shape (`read_1d(path) -> Spectrum1D`,
`read_2d(path) -> Spectrum2D`), plus a new `read(path) -> Spectrum1D | Spectrum2D` dispatcher that
branches on `##NUM DIM` (1 vs 2) — bruker.py has no such dispatcher since Bruker experiment
directories are inherently typed by their own directory structure, but JCAMP files are not, so this
is JcampReader's one structural addition beyond the bruker.py template.

**Error/fail-loud pattern** (bruker.py lines 149-150, 162-163, 231-236 — the project's standard
"guard clause, then raise with a specific, actionable message" idiom used throughout the readers
layer):
```python
if not experiment_dir.exists():
    raise FileNotFoundError(f"Experiment directory not found: {experiment_dir}")
...
nucleus = _get_param(dic, "NUC1")
if nucleus is None:
    raise ValueError("NUC1 parameter not found in acqus")
...
if f1_nucleus is None:
    raise ValueError("NUC1 parameter not found in acqu2s (F1 dimension)")
if f2_nucleus is None:
    raise ValueError("NUC1 parameter not found in acqus (F2 dimension)")
if pulse_program is None:
    raise ValueError("PULPROG parameter not found in acqus")
```
Apply the identical idiom in `jcamp.py` for missing `##$SF`/`##$OFFSET`/`.NUCLEUS`/`##NUM DIM`
keys, plus the two NEW fail-loud checks D-04/RESEARCH require (ppm-axis plausibility + reversal —
see the `nus/runner.py::run_stage` excerpt below for the sibling fail-loud style to match on the
*numeric-assertion* side specifically).

**Core 2D ppm-axis pattern to REPLACE, not copy verbatim** (bruker.py lines 246-255 — this is the
"wrong tool for JCAMP" pattern; cite it in the plan as *what NOT to structurally imitate* for the
axis math itself, while still imitating its call-site shape):
```python
udic = ng.bruker.guess_udic(dic, data)
uc_f1 = ng.fileiobase.uc_from_udic(udic, dim=0)
f1_ppm_scale = uc_f1.ppm_scale()
uc_f2 = ng.fileiobase.uc_from_udic(udic, dim=1)
f2_ppm_scale = uc_f2.ppm_scale()
```
bruker.py can lean on `ng.bruker.guess_udic` because it reads native Bruker `acqus`/`acqu2s`
directly; JCAMP's `##$SF`/`##$OFFSET` fields require the RESEARCH.md Pattern-2 formula instead
(`ppm[i] = OFFSET_ppm - (FIRST_hz - hz[i]) / SF`, verified — see RESEARCH.md Code Examples for the
ready-to-use `_ppm_scale()` helper). Do not attempt to route JCAMP data back through
`ng.bruker.guess_udic`; it is the wrong path structurally (built for native Bruker dics), even
though the *call-site shape* (compute `f1_ppm_scale`/`f2_ppm_scale`, pass into `Spectrum2D(...)`)
should mirror bruker.py's shape.

**Constructor call pattern** (bruker.py lines 272-281 — the exact shape `jcamp.py`'s `read_2d` must
produce; field names must match `Spectrum2D` verbatim):
```python
return Spectrum2D(
    data=np.array(data, dtype=np.float64),
    f1_ppm_scale=np.array(f1_ppm_scale, dtype=np.float64),
    f2_ppm_scale=np.array(f2_ppm_scale, dtype=np.float64),
    f1_nucleus=f1_nucleus,
    f2_nucleus=f2_nucleus,
    experiment_type=experiment_type,
    frequency=float(frequency),
    metadata=metadata,
)
```
and the 1D equivalent (bruker.py lines 188-195):
```python
return Spectrum1D(
    data=np.array(data, dtype=np.float64),
    ppm_scale=np.array(ppm_scale, dtype=np.float64),
    nucleus=nucleus,
    frequency=float(frequency),
    solvent=solvent,
    metadata=metadata,
)
```

**Experiment-type detection — reuse verbatim, do not copy** (D-10): import
`_detect_experiment_type` directly from `lucy_ng.readers.bruker` rather than duplicating its body.
Signature (bruker.py lines 51-64):
```python
def _detect_experiment_type(pulse_program: str, f1_nucleus: str, f2_nucleus: str) -> str:
    """Detect 2D NMR experiment type from pulse program and nuclei. ...
    Returns: HSQC, HMBC, COSY, TOCSY, NOESY, or ROESY.
    Raises: ValueError if experiment type cannot be determined.
    """
```
Verified (RESEARCH.md) to correctly map all four fixture pulse programs
(`hsqcedetgpsp.3`→HSQC, `hmbcetgpl3nd`→HMBC, `cosygpmfppqf`→COSY, `noesygpph`→NOESY) with zero
changes — call it exactly as bruker.py does (bruker.py line 239):
```python
experiment_type = _detect_experiment_type(pulse_program, f1_nucleus, f2_nucleus)
```

**Param-string cleanup helper — reuse pattern, not import** (bruker.py lines 12-16; JCAMP's own
`.NUCLEUS`/`$NUC1` values arrive caret-prefixed, e.g. `^1H`/`^13C`, not angle-bracket-wrapped like
Bruker's `<1H>`, so this exact helper does not apply verbatim, but its shape — a tiny
strip-wrapping-characters function called once per extracted string field — is the pattern to
replicate for the caret-strip Claude's-Discretion item):
```python
def _strip_brackets(value: str) -> str:
    """Strip angle brackets from Bruker parameter strings."""
    if value.startswith("<") and value.endswith(">"):
        return value[1:-1]
    return value
```
New JCAMP-specific equivalent (author fresh, following this exact shape):
```python
def _strip_caret(value: str) -> str:
    """Strip a leading caret (^) from JCAMP-DX .NUCLEUS values (e.g. '^1H' -> '1H')."""
    return value.lstrip("^")
```

**Metadata dict-building pattern** (bruker.py lines 179-186, 257-270 — conditionally populate a
plain dict, only including keys that have a non-None/non-empty value):
```python
metadata: dict[str, Any] = {}
if pulse_program:
    metadata["pulse_program"] = pulse_program
if num_scans is not None:
    metadata["num_scans"] = num_scans
if temperature is not None:
    metadata["temperature"] = temperature
```
Reuse this exact idiom in `jcamp.py` for solvent/pulse_program/frequency-source metadata.

---

### `src/lucy_ng/readers/_jcampdx_decode.py` (utility, transform / pure numeric decode)

**No in-repo analog** — see "No Analog Found" below. This is a vendored external module, not an
adaptation of existing lucy-ng code.

**Provenance (attribute exactly as follows, per D-05):**
Source: `nmrglue.fileio.jcampdx` (nmrglue `0.12-dev` / `0.12.dev0`, New-BSD, Copyright (c) 2010-2015
Jonathan J. Helmus), installed at
`/opt/miniconda3/lib/python3.12/site-packages/nmrglue/fileio/jcampdx.py`, lines 208-453. Verified
license text (from `nmrglue-0.12.dev0.dist-info/LICENSE.txt`):
```
Copyright (c) 2010-2015 Jonathan J. Helmus
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

a. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
b. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.
c. Neither the name of the author nor the names of contributors may
   be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES ... [full 4-clause New-BSD text]
```
Reproduce the full license block verbatim in the vendored file's module docstring, plus a one-line
provenance note (e.g. `# Vendored from nmrglue.fileio.jcampdx (0.12-dev), lines 208-453.`).

**9 objects to vendor (verified dependency closure, per RESEARCH — NOT the 5 D-05 originally
estimated):**
```
_DIGITS          # line 208
_SQZ_DIGITS      # line 209
_DIF_DIGITS      # line 214
_DUP_DIGITS      # line 219
_detect_format(dataline)                    # line 224
_parse_affn_pac(datalines)                  # line 254
_append_value(data, value, isdif)           # line 283
_finish_value(valuestr, mode, prev, data)   # line 294
_parse_pseudo(datalines)                    # line 330
_parse_data(datastring)                     # line 432 -- public-ish entry point
```
Copy these 9 objects byte-identical (rename `_parse_data` to a public `parse_data` if the plan
wants a non-underscore public entry point for the module — Claude's Discretion) — do not "clean up"
or refactor during vendoring; a byte-identical copy is what makes the D-08 hand-oracle unit test a
valid independent check (any accidental behavior change during vendoring must be caught by that
test, not hidden by simultaneous refactoring).

**Exact source excerpt (entry point + one dependency, verified present at these lines):**
```python
def _detect_format(dataline):
    '''
    Detects and returns digit format:
    0  Normal
    1  Pseudodigits
    -1 Error
    '''
    firstvalue_re = re.compile(
        r"(\s)*([+-]?\d+\.?\d*|[+-]?\.\d+)([eE][+-]?\d+)?(\s)*")
    index = firstvalue_re.match(dataline).end()
    ...

def _parse_data(datastring):
    '''
    Creates numpy array from datalines
    '''
    datalines = datastring.split("\n")
    headerline = datalines[0]
    datatype = "R"
    if "I..I" in headerline:
        datatype = "I"
    datalines = datalines[1:]  # get rid of the header line (e.g. (X++(Y..Y)))
    mode = _detect_format(datalines[0])
    if mode == 1:
        data = _parse_pseudo(datalines)
    elif mode == 0:
        data = _parse_affn_pac(datalines)
    else:
        return None
    if data is None:
        return None
    return np.asarray(data, dtype="float64"), datatype
```
Required import for the vendored module: `import re`, `from warnings import warn`, `import numpy as np`
(all already project dependencies — no new packaging surface, confirming D-11's discretion note).

---

### `tests/readers/test_jcamp.py` (test, integration)

**Analog:** `tests/test_bruker_reader.py` (read in full, 100+ lines)

**Structure to mirror** (class-per-nucleus-or-concern, method-per-assertion; lines 1-13, 16-52):
```python
"""Tests for Bruker NMR file reader."""

from pathlib import Path

import numpy as np
import pytest

from lucy_ng.readers.bruker import BrukerReader

# Test data paths
DATA_DIR = Path(__file__).parent.parent / "data"
IBUPROFEN_1H = DATA_DIR / "Ibuprofen" / "1"
IBUPROFEN_13C = DATA_DIR / "Ibuprofen" / "2"


class TestBrukerReader1H:
    """Tests for reading 1H NMR spectra."""

    def test_read_1h_spectrum_nucleus(self) -> None:
        """Test that 1H spectrum has correct nucleus."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        assert spectrum.nucleus == "1H"

    def test_read_1h_ppm_scale_range(self) -> None:
        """Test that 1H ppm range is reasonable (roughly -1 to 14 ppm)."""
        spectrum = BrukerReader.read_1d(IBUPROFEN_1H)
        ppm_min = spectrum.ppm_scale.min()
        ppm_max = spectrum.ppm_scale.max()
        assert ppm_min > -5
        assert ppm_max < 20
```
Apply this exact class-per-concern shape for `test_jcamp.py`: `TestJcampReader1D`,
`TestJcampReader2D`, `TestJcampReaderPpmCrossCheck` (JC-02's D-03 finer check),
`TestJcampReaderErrors` — mirroring `TestBrukerReaderErrors` (bruker.py test file lines 97-100+):
```python
class TestBrukerReaderErrors:
    """Tests for error handling."""

    def test_invalid_directory(self) -> None:
```
Use RESEARCH.md's exact test IDs/targets (already specified in its "Phase Requirements → Test Map"
table): `test_read_2d_shape`, `test_read_2d_ppm_axes_match_1d_reference`, `test_read_1d`.

**Fixture-path constant pattern** (mirror exactly, new module-level constants):
```python
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "jcamp"
HSQC_TRIMMED = FIXTURE_DIR / "C20H32O2_HSQC_trimmed.dx"
REF_1H = FIXTURE_DIR / "C20H32O2_1H.dx"
REF_13C = FIXTURE_DIR / "C20H32O2_13C.dx"
```

**Cross-check tolerance constants (from RESEARCH.md, ready to copy verbatim):**
```python
PPM_CROSS_CHECK_TOLERANCE_1H = 0.05   # ppm
PPM_CROSS_CHECK_TOLERANCE_13C = 0.10  # ppm
```

---

### `tests/readers/test_jcampdx_decode.py` (test, unit / hand-oracle)

**Analog:** `tests/test_bruker_reader.py` (structure/import-style only — no existing decoder-unit
test exists in-repo for this role; RESEARCH.md's own worked example is the load-bearing content).

**Content to copy near-verbatim (RESEARCH.md Code Examples — already hand-traced and verified by
direct execution against the real nmrglue decoder during research):**
```python
# Target row: intensities [100, 105, 105, 102] (4 points)
# Encoding: "0"=AFFN checkpoint (ignored) "A00"=SQZ abs 100 "N"=DIF +5->105
#           "%"=DIF +0->105(pending) "S"=DUP repeat-1->105 "l"=DIF -3->102
# Full encoded line: "(F2++(Y..Y))\n0A00N%Sl"

from lucy_ng.readers._jcampdx_decode import parse_data  # the VENDORED copy, not nmrglue's

def test_hand_authored_mini_vector() -> None:
    result, dtype = parse_data("(F2++(Y..Y))\n0A00N%Sl")
    assert list(result) == [100.0, 105.0, 105.0, 102.0]
    assert dtype == "R"
```
Critical: this test must import ONLY `lucy_ng.readers._jcampdx_decode`, never
`nmrglue.fileio.jcampdx` — the entire point (per RESEARCH.md) is an oracle independent of nmrglue
ever being installed/working correctly, so a vendoring bug is caught even if nmrglue itself is
absent or broken.

Also required (Pitfall 2, Y-FACTOR): a second test asserting the reader-level multiplication step
(not the vendored decoder itself, which returns raw un-scaled integers) — e.g. assert that
`[100,105,105,102]` scaled by a test-supplied `Y_FACTOR=2.5` yields `[250,262.5,262.5,255]`. This
belongs wherever `jcamp.py` applies the Y-FACTOR (likely `test_jcamp.py` instead, if the
multiplication lives in `jcamp.py` proper rather than the decode module — Claude's Discretion on
exact test-file placement, per RESEARCH.md's own wording).

---

### `tests/fixtures/jcamp/` (fixture data)

**Analog for placement convention:** `tests/data/Ibuprofen/{1,2}/` (existing Bruker fixture dirs
referenced by `tests/test_bruker_reader.py`'s `DATA_DIR` constant) and the existing
`tests/fixtures/{nus,regression,form_tolerance}/` directories (established convention: fixtures
live under `tests/fixtures/<domain>/`, separate from `tests/data/` which holds full Bruker
experiment directories).

**Convention to follow:** `tests/fixtures/jcamp/` (new subdirectory, following the existing
`tests/fixtures/<domain>/` naming pattern already used for `nus/`, `regression/`,
`form_tolerance/`). Per D-07/RESEARCH.md's fixture-size guidance, commit:
- `C20H32O2_HSQC_trimmed.dx` — real 2D fixture, header pruned to ~25-30 consumed keys (see
  RESEARCH.md Code Examples "Fixture size measurement" for the exact key list to retain), F1 pages
  trimmed to indices `[1720:1755]` or `[1735:1751]` (both windows verified to contain real,
  non-noise cross-peaks usable as the D-08 layer-2 oracle).
- `C20H32O2_1H.dx`, `C20H32O2_13C.dx` — the two real 1D reference files, copied whole (needed for
  the D-03/JC-02 cross-check; RESEARCH.md measured these as small enough to commit as-is).

---

## Shared Patterns

### Fail-loud assertion idiom (applies to `jcamp.py`'s D-04 ppm-axis check)
**Source:** `src/lucy_ng/nus/runner.py::run_stage` (lines 51-100, the phase-99/100-established
project convention for "the tool claims success but the output is wrong" checks) and
`src/lucy_ng/nus/qc.py` (six PASS/PARTIAL/FAIL checks, same philosophy applied to scientific-data
plausibility rather than subprocess exit codes).
**Apply to:** `jcamp.py`'s post-computation ppm-axis validation (D-04) and any NTUPLES
structural-consistency check (`len(PAGE) == len(DATATABLE) == expected VAR_DIM`).
```python
# nus/runner.py:88-99 -- the general shape: guard, then raise with full diagnostic context
if proc.returncode != 0:
    raise RuntimeError(
        f"NUS stage '{name}' failed (exit {proc.returncode}): "
        f"{proc.stderr[:500]!r}"
    )
if not expected_output.exists() or expected_output.stat().st_size == 0:
    raise RuntimeError(
        f"NUS stage '{name}' reported success but output file "
        f"{expected_output} is missing or empty -- refusing to "
        "continue (csh-piped NMRPipe stages can silently pass through "
        "truncated data, Pitfall 14)."
    )
```
RESEARCH.md already supplies the concrete `jcamp.py`-specific version of this pattern, ready to
copy near-verbatim:
```python
def _assert_plausible_ppm_axis(scale: np.ndarray, nucleus: str) -> None:
    bounds = {"1H": (-3.0, 15.0), "13C": (-15.0, 230.0),
              "15N": (-50.0, 900.0), "31P": (-200.0, 250.0)}
    lo, hi = bounds.get(nucleus, (-1e6, 1e6))
    if not (lo <= scale.min() and scale.max() <= hi):
        raise ValueError(f"Implausible {nucleus} ppm axis: [{scale.min():.2f}, {scale.max():.2f}] "
                          f"outside expected [{lo}, {hi}] -- likely wrong Hz/frequency divisor")
    if not (scale[0] > scale[-1]):
        raise ValueError(f"{nucleus} ppm axis not reversed (descending) -- Bruker convention violated")
```

### Guard-clause + specific-message raise idiom (applies to all readers)
**Source:** `src/lucy_ng/readers/bruker.py` (throughout `read_1d`/`read_2d`).
**Apply to:** every required-parameter check in `jcamp.py`'s `read_1d`/`read_2d`/`read`.
```python
if not experiment_dir.exists():
    raise FileNotFoundError(f"Experiment directory not found: {experiment_dir}")
...
if nucleus is None:
    raise ValueError("NUC1 parameter not found in acqus")
```

### Target-model constructor contract (applies to both reader paths)
**Source:** `src/lucy_ng/models/spectrum.py` (`Spectrum1D` lines 10-53, `Spectrum2D` lines 56-157).
**Apply to:** `jcamp.py`'s `read_1d`/`read_2d` return values — field names and validator constraints
are non-negotiable.
```python
# Spectrum1D required fields: data, ppm_scale, nucleus, frequency, solvent(optional), metadata
# Spectrum2D required fields: data, f1_ppm_scale, f2_ppm_scale, f1_nucleus, f2_nucleus,
#                             experiment_type, frequency, metadata
# nucleus validator (both models): {"1H", "13C", "15N", "31P", "19F", "2H"} -- strip "^" prefix first
# experiment_type validator (Spectrum2D only): {"HSQC", "HMBC", "COSY", "TOCSY", "NOESY", "ROESY"}
```

### Experiment-type detection (single source of truth)
**Source:** `src/lucy_ng/readers/bruker.py::_detect_experiment_type` (lines 51-99).
**Apply to:** import and call directly from `jcamp.py` — do not reimplement (D-10).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/lucy_ng/readers/_jcampdx_decode.py` | utility (numeric decoder) | transform | No pseudo-digit/DIFDUP decoder exists anywhere in lucy-ng — this is a genuinely new capability class (compressed-line numeric decoding), sourced instead from the external `nmrglue.fileio.jcampdx` module (New-BSD) per D-05. Planner should treat RESEARCH.md's "Code Examples — Vendored decoder" section as the authoritative source-of-truth, not search further for an in-repo analog. |

## Metadata

**Analog search scope:** `src/lucy_ng/readers/` (bruker.py — full read), `src/lucy_ng/models/`
(spectrum.py — full read), `src/lucy_ng/nus/` (runner.py partial read — fail-loud excerpt only,
qc.py function-signature grep only), `tests/test_bruker_reader.py` (partial read — first 100
lines), `tests/fixtures/` (directory listing only), external
`/opt/miniconda3/lib/python3.12/site-packages/nmrglue/fileio/jcampdx.py` (targeted reads: lines
1-80 header + lines 208-453 decoder closure) and its `LICENSE.txt` (partial read, license header).
**Files scanned:** 7 (2 in-repo source, 1 in-repo test, 1 external vendored source, 1 external
license file, plus directory listings of `tests/fixtures/` and `tests/readers/`).
**Pattern extraction date:** 2026-07-23
