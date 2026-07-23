# Phase 101: JCAMP-DX Reader - Research

**Researched:** 2026-07-23
**Domain:** JCAMP-DX 2D NTUPLES parsing (Bruker export), ppm-axis calibration, pure-Python DIFDUP decoding
**Confidence:** HIGH (all four target areas verified directly against the real fixture files and the installed nmrglue source — not assumed)

## Summary

This research resolves the one open question CONTEXT.md flagged (SFO vs SF/SR divisor) with a
**definitive, empirically-verified answer**, and corrects two assumptions in CONTEXT.md's D-06
that would otherwise cause implementation surprises: (1) nmrglue's public `ng.jcampdx.read()`
does **not** return the 2D metadata dict at the top level — the entire dict is nested one level
down and the top-level dispatch never even reaches the NTUPLES-parsing code for 2D files; (2) the
vendored decoder is ~250 lines across 9 objects, not the ~60 lines / 5 objects D-05 estimated.
Both corrections are cheap to absorb in planning and do not change the phase's scope or decisions
— they change the concrete file list and line budget for the vendored module and the exact
metadata-access path.

The crux ppm question is now closed with high confidence: **the Hz→ppm divisor is `$SF`
(procs/proc2s "spectrometer reference frequency"), not `$SFO1`/`$SFO2` (transmitter frequency)**,
and — more important than the divisor choice — **the axis anchor is `$OFFSET` (procs/proc2s,
already given in ppm)**, not a raw Hz/frequency division from zero. This was verified to 4+
decimal places against the project's own already-trusted `BrukerReader` output on the sibling raw
Bruker dataset for the same sample (same pulse programs, `hsqcedetgpsp.3` / `zg30` / `zgpg30`).
Using CONTEXT.md's originally-proposed naive `SFO`-divisor-with-Hz=0-anchor approach introduces a
**real, measured 0.447 ppm systematic error on the F2 (¹H, direct) axis** in this exact fixture —
large enough to silently misassign every HSQC/HMBC/COSY cross-peak in the proton dimension. The F1
(¹³C, indirect) axis is far less sensitive (0.015 ppm error with the naive approach in this file)
but should use the identical correct formula for robustness, since the SF↔SFO gap is
dataset-dependent and not guaranteed to stay small.

**Primary recommendation:** Derive ppm axes as `ppm[i] = OFFSET_ppm - (FIRST_hz - hz[i]) / SF`
(anchor = `$OFFSET`, divisor = `$SF`) for both dimensions, cross-referencing dimension identity
via `.NUCLEUS` (order-guaranteed by the NTUPLES `SYMBOL` field) rather than trusting `$SF`/`$OFFSET`
list-position alone. Vendor 9 objects (not 5) from nmrglue's `jcampdx.py`. Read 2D metadata via
`jcampdx._readrawdic()` directly (not `ng.jcampdx.read()`, which silently drops all 2D metadata
into an unreachable branch) or by explicitly reaching into `dic["_datatype_NDNMRSPECTRUM"][0]`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| JCAMP-DX file parsing (blocks/keys) | Reader (pure-Python, no I/O beyond file read) | — | Self-contained parsing library concern; no network/DB/UI involved |
| DIFDUP/SQZ/DUP/PAC line decode | Reader (vendored kernel) | — | Numeric decode of already-loaded text; CPU-bound, in-process |
| ppm-axis derivation + calibration | Reader | Validation/test | The reader owns the math; the CI fixture test is the independent proof |
| 2D page-stacking (NTUPLES assembly) | Reader | — | New capability this phase adds; nmrglue provides none of it for 2D |
| Target data model (`Spectrum1D`/`Spectrum2D`) | Data model layer (`models/spectrum.py`) | — | Existing, unchanged; reader only populates it |
| Experiment-type detection | Reader (reuses `bruker.py::_detect_experiment_type`) | — | Single source of truth already established in Phase <100; JCAMP reader is a second caller, not a new implementation |
| CI fixture / correctness oracle | Test layer | Reader (fail-loud assertion) | Split per D-04: hard assertion lives in the reader; fine-grained cross-check lives in tests |

## Standard Stack

### Core
No new packages. `nmrglue` is already a core dependency (`pyproject.toml` line 33:
`"nmrglue @ git+https://github.com/jjhelmus/nmrglue.git"`, resolving to `0.12.dev0` — verified
installed at `/opt/miniconda3/lib/python3.12/site-packages/nmrglue`, imported by
`readers/bruker.py`). No packaging surface change (confirms D-11's discretion note).

### Supporting
None needed — pure stdlib (`re`) + numpy, both already project dependencies.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vendoring nmrglue's private decode functions | Reimplementing DIFDUP from scratch | Needless risk on an already-solved, already-tested problem (D-05's own reasoning, confirmed correct after reading the source) |
| Vendoring nmrglue's private decode functions | Importing `nmrglue.fileio.jcampdx._parse_data` directly (private API) | Violates JC-04's literal wording ("without depending on nmrglue's private API"); nmrglue is pre-1.0 (`0.12-dev`), no API stability guarantee |

**Installation:** none required (no new packages).

**Version verification:**
```
$ /opt/miniconda3/bin/python3 -c "import nmrglue; print(nmrglue.__version__)"
0.12-dev
$ pip show nmrglue
Version: 0.12.dev0
License: New BSD License
```
Confirmed installed and importable — `[VERIFIED: local environment]`.

## Package Legitimacy Audit

**Not applicable.** This phase introduces zero new external packages — `nmrglue` is an existing,
already-audited core dependency (imported by `readers/bruker.py` since an earlier phase). No
`slopcheck`/registry verification is needed.

## Architecture Patterns

### System Architecture Diagram

```
  .dx file (JCAMP-DX, 2D NTUPLES, DIFDUP-compressed)
        │
        ▼
  ┌─────────────────────────────────────────┐
  │ jcampdx._readrawdic(filename)           │  ← nmrglue PUBLIC-ish helper
  │  → raw dict, keyed "_datatype_<TYPE>"   │     (module-level function, not
  │    single entry for 2D: NDNMRSPECTRUM   │     underscore-private in the
  └───────────────────┬─────────────────────┘     "double-underscore" sense —
                       │                           see Code Examples for the
                       ▼                           access-path correction)
  ┌─────────────────────────────────────────┐
  │ inner = dic["_datatype_NDNMRSPECTRUM"][0]│  ← metadata dict: SFO1/SFO2, SF,
  │  - VAR_DIM, FACTOR, FIRST/LAST (global)  │    OFFSET, NUCLEUS, PULSE SEQUENCE,
  │  - SYMBOL ("F1,F2,Y"), UNITS             │    SYMBOL, PAGE[], DATATABLE[]
  │  - PAGE[i]  = "F1=<hz>" (2048 entries)   │
  │  - DATATABLE[i] = DIFDUP-encoded row     │
  └───────────────────┬─────────────────────┘
                       │  per-page decode loop
                       ▼
  ┌─────────────────────────────────────────┐
  │ VENDORED KERNEL (readers/_jcampdx_decode.py) │
  │  _parse_data(datatable[i])              │  ← decodes ONE row string
  │   → _detect_format → _parse_pseudo /    │     to a raw intensity array
  │     _parse_affn_pac → (array, "R"/"I")  │     (needs Y-FACTOR scaling)
  └───────────────────┬─────────────────────┘
                       │  stack n_f1 rows
                       ▼
  ┌─────────────────────────────────────────┐
  │ readers/jcamp.py :: JcampReader.read_2d │
  │  - assemble (n_f1, n_f2) matrix          │
  │  - apply Y-FACTOR (SYMBOL-indexed)       │
  │  - derive f1/f2 ppm axes (OFFSET + SF)   │
  │  - fail-loud range/reversed assertion    │
  │  - map .PULSE SEQUENCE → experiment_type │
  │    (reuse bruker.py::_detect_experiment_type)
  └───────────────────┬─────────────────────┘
                       │
                       ▼
              Spectrum2D (existing model)
                       │
        (Phase 102 — OUT OF SCOPE here)
                       ▼
     PeakPicker2D → analysis/nmr_peaks/*.json → QC gate → CASE
```

### Recommended Project Structure
```
src/lucy_ng/readers/
├── bruker.py            # existing, untouched
├── jcamp.py             # NEW: JcampReader (read_1d / read_2d / read dispatcher)
└── _jcampdx_decode.py    # NEW: vendored DIFDUP/SQZ/DUP/PAC kernel (BSD attribution header)
tests/
├── readers/
│   ├── test_jcamp.py               # integration test on trimmed real fixture (D-08 layer 2)
│   └── test_jcampdx_decode.py      # hand-authored mini-vector unit test (D-08 layer 1)
└── fixtures/jcamp/
    └── C20H32O2_HSQC_trimmed.dx    # real, trimmed 2D fixture (D-07)
```

### Pattern 1: Metadata access — do NOT rely on `ng.jcampdx.read()` for 2D
**What:** `ng.jcampdx.read()`'s top-level dispatch only recognizes three `DATATYPE` buckets:
`_datatype_NMRSPECTRUM`, `_datatype_NMRFID`, `_datatype_NA`. A 2D file's `##DATA TYPE= nD NMR
SPECTRUM` normalizes (via `_getkey`) to `_datatype_NDNMRSPECTRUM` — a fourth bucket `read()` never
checks. The `try/except KeyError` around each bucket lookup means **`getdataarray()` (the function
that does NTUPLES page parsing) is never even called for 2D files** — this is the literal, exact
gap this phase fills, more precise than "the 2D assembly bails out on `data=None`" (it does return
`None`, but by never entering the 2D code path at all, not by entering it and giving up).

A second, more consequential side effect: because `correctdic` never gets set (no bucket matched),
`read()`'s "push correct dic entries to base level" step never runs. **The entire metadata dict for
a 2D file stays nested inside `dic["_datatype_NDNMRSPECTRUM"][0]`** — it is NOT promoted to the
top level the way CONTEXT.md's D-06 assumed ("returns the full metadata dict... at base level").

**When to use:** Always, for this phase's 2D path.
**Example:**
```python
# Source: verified empirically against /opt/miniconda3/lib/python3.12/site-packages/nmrglue/fileio/jcampdx.py (0.12-dev)
import nmrglue.fileio.jcampdx as jc

dic, data = jc.read(filepath)          # WRONG for 2D: data is None, AND
                                        # dic == {"_datatype_NDNMRSPECTRUM": [ {...} ]}
                                        # (metadata NOT promoted to dic's top level)

# CORRECT: use the raw-dict helper directly, or reach into the nested bucket
raw = jc._readrawdic(filepath)         # module-level function; same one read() calls internally
inner = raw["_datatype_NDNMRSPECTRUM"][0]   # <- the actual metadata dict (417 keys in the real fixture)
pages = inner["PAGE"]                  # list of 2048 "F1=<hz>" strings
tables = inner["DATATABLE"]            # list of 2048 DIFDUP-encoded row strings
```
`_readrawdic` is a module-level function (single leading underscore, "internal" by convention but
not name-mangled) — using it is equivalent in risk profile to what D-06 already accepted for
`ng.jcampdx.read()` itself (both are "public-ish" nmrglue internals, one layer apart). Recommend
calling `_readrawdic` directly and doing the bucket lookup explicitly (searching for whichever
`_datatype_*` key is present, since 1D COSY/NOESY/1H/13C files use `_datatype_NMRSPECTRUM` while 2D
files use `_datatype_NDNMRSPECTRUM`) rather than depending on `ng.jcampdx.read()`'s dispatch table
at all, so the reader is not coupled to nmrglue's incomplete `DATATYPE` bucket list.

### Pattern 2: ppm-axis derivation — OFFSET anchor + SF divisor (the crux finding)
**What:** For both 1D and 2D files, the axis is NOT `Hz / frequency` from a zero origin. The
correct, empirically-verified formula is:
```
ppm[i] = OFFSET_ppm - (FIRST_hz - hz[i]) / SF
```
where `OFFSET_ppm` = `$OFFSET` (procs/proc2s, **already in ppm** — this is the ppm value of the
FIRST point of the axis, and it exactly matches the `##.SHIFT REFERENCE=` line's declared value),
`FIRST_hz` = the axis's `##FIRST=` Hz value (global, not a per-page value — see Pitfall 3), and
`SF` = `$SF` (procs/proc2s "spectrometer reference frequency" — **not** `$SFO1`/`$SFO2`, the
transmitter frequency).

**When to use:** Every ppm-axis computation in this phase (1D and both 2D dimensions).

**Verified evidence (worked, not assumed):**
```
# Ground truth: BrukerReader.read_1d() on the sibling RAW Bruker dataset
# (same sample, same pulse programs: exp1=zg30/1H, exp6=zgpg30/13C)
Bruker 1H  ppm range: -0.45048563680332343 .. 7.050600095995955
Bruker 13C ppm range: -10.144203910051743 .. 110.14466277438953

# JCAMP export of the SAME experiments (C20H32O2_1H.dx / C20H32O2_13C.dx):
#   $OFFSET (1H)  = 7.050608     <- matches Bruker ground-truth MAX to 5 decimals
#   $OFFSET (13C) = 110.1447     <- matches Bruker ground-truth MAX to 4 decimals
#   $SF     (1H)  = 499.92       (== $BF1 in this file; SR happens to be ~0 here)
#   $SF     (13C) = 125.704983984 (== $BF1 of the 13C acqus; again SR~0)
#   FIRST_hz(1H)=3749.94277954102, FIRST_hz(13C)=15120.9100600211, LAST_hz=0 both

# Applying ppm[i] = OFFSET - (FIRST_hz - hz[i])/SF reproduces the Bruker ground
# truth to <0.0004 ppm (residual = $OFFSET's own printed-precision rounding, not
# a model error) -- confirmed by direct computation, see Assumptions Log A1.

# THE NAIVE APPROACH (Hz/SFO from a zero anchor -- CONTEXT.md's original proposal):
naive_1H_first  = 3748.1689453125 / 499.92164974   = 7.4977 ppm   # true value: 7.0506
naive_13C_first = 21997.1407732541 / 125.715668907639 = 174.975 ppm  # true value: 174.990
#   => 0.447 ppm error on F2 (1H)   <- LARGE, silently wrong axis
#   => 0.015 ppm error on F1 (13C)  <- small in THIS file, not guaranteed small in general
```

**Dimension identity (which `$SF`/`$OFFSET` list entry belongs to F1 vs F2):** `$SF`, `$OFFSET`,
`$BF1`, `$NUC1` all appear as 2-entry lists in the merged JCAMP dict (entry 0 = `procs`/direct
dimension, entry 1 = `proc2s`/indirect dimension — confirmed by entry values matching known
`BF1`/`BF2` assignments). This ordering is a **parse-order artifact**, not a JCAMP-DX spec
guarantee — see Common Pitfall 4 for the recommended defensive cross-check using `.NUCLEUS`
(whose F1/F2 order IS guaranteed by the `SYMBOL` field convention).

**Formula for F1 (indirect/2D-only):** identical, but read `FIRST_hz`/`hz[i]` per-row directly from
the `##PAGE= F1=<hz>` values rather than from a top-level `FIRST`/`LAST`/`VAR_DIM` triple — see
Pitfall 3 and the D-07 fixture guidance below (this materially simplifies fixture trimming).

### Anti-Patterns to Avoid
- **Dividing Hz by `SFO1`/`SFO2` (or `BF1`/`BF2`) with a zero-Hz anchor:** produces a plausible-
  looking but wrong axis (both the naive and correct approaches give "reasonable" ppm windows —
  D-04's plausibility-range assertion alone will NOT catch this; only the D-03 cross-check or the
  correct-formula-by-construction will).
- **Trusting `ng.jcampdx.read()`'s metadata dict shape for 2D files** without checking whether
  `correctdic` promotion actually happened (it doesn't, for 2D — see Pattern 1).
- **Assuming `$SF`/`$OFFSET` list index 0 = F1** — it's actually F2 (direct) in this fixture; always
  cross-reference against `.NUCLEUS`, never hardcode the index.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DIFDUP/SQZ/DUP/PAC line decoding | A from-scratch pseudo-digit parser | Vendored `_parse_data` + its 8 dependent objects from nmrglue `jcampdx.py` (New-BSD) | Already correct, already tested upstream, exercised against this exact real file during this research session with zero decode failures across 2048 pages |
| ppm-axis Hz→ppm math | A hand-rolled `Hz/frequency` conversion using only `SFO` | The verified `OFFSET + SF` formula in Pattern 2 | The naive `Hz/frequency` approach is the single biggest correctness risk in this phase — it silently produces a plausible-but-wrong axis (0.447 ppm error observed) |
| Experiment-type detection from pulse program | A new JCAMP-specific pulse-program → experiment-type mapper | `bruker.py::_detect_experiment_type()` (reused verbatim per D-10) | Verified directly against all 4 of this fixture's 2D pulse programs (`hsqcedetgpsp.3`→HSQC, `hmbcetgpl3nd`→HMBC, `cosygpmfppqf`→COSY, `noesygpph`→NOESY) — all map correctly with zero changes needed |

**Key insight:** Every piece of "new" logic this phase needs (decode kernel, ppm math, experiment
detection) already exists correctly somewhere in the codebase or in nmrglue — the entire phase is
integration + one genuinely novel piece (2D page-stacking), not new algorithm design.

## Common Pitfalls

### Pitfall 1: `ng.jcampdx.read()` silently returns unusable 2D metadata (not `None` metadata — nested `None`-adjacent metadata)
**What goes wrong:** Code that calls `ng.jcampdx.read(path)` and checks `if data is None: <handle
1D-only>` will incorrectly conclude the file has no readable metadata either, or will try to read
`dic["VAR_DIM"]` directly and get a `KeyError` (it's nested under `dic["_datatype_NDNMRSPECTRUM"][0]["VAR_DIM"]` instead).
**Why it happens:** `read()`'s `DATATYPE` bucket dispatch has no `_datatype_NDNMRSPECTRUM` branch (Pattern 1).
**How to avoid:** Call `jc._readrawdic()` directly and search returned dict keys for whichever
`_datatype_*` bucket is present (don't hardcode `NMRSPECTRUM` vs `NDNMRSPECTRUM` — 1D files in this
project's own fixture set use `NMRSPECTRUM`; 2D files use `NDNMRSPECTRUM`).
**Warning signs:** `KeyError` on expected top-level keys; `data is None` treated as "file unreadable" rather than "2D page assembly needed."

### Pitfall 2: Y-FACTOR scaling silently drops out on files where it happens to be 1
**What goes wrong:** The real HSQC fixture's `Y_FACTOR` (from `FACTOR="11.047,1.831,1"`, `SYMBOL="F1,F2,Y"`) happens to be exactly `1`, so a reader that forgets to multiply decoded intensities by the Y-column's FACTOR will pass tests on THIS fixture but silently corrupt intensities on any file where `Y_FACTOR != 1`.
**Why it happens:** `_parse_data()` returns raw decoded integers, not calibrated intensities — nmrglue's own `getdataarray()` applies `yfactor` as a separate step afterward (see `find_yfactors()` + the `data[0] = data[0] * yfactor_r` line in `jcampdx.py`), and it's easy to skip this when hand-rolling the 2D assembly since the vendored kernel itself doesn't do it.
**How to avoid:** Explicitly locate the `Y` index in `SYMBOL` (comma-split, strip whitespace, `.index("Y")`), read the same-index entry from `FACTOR`, and multiply every decoded row by it before stacking.
**Warning signs:** A CI fixture whose `Y_FACTOR` happens to be 1 (as this one does) will not catch a missing multiplication — write the D-08 unit test's hand-authored mini-vector with `Y_FACTOR != 1` (e.g. `2.5`) specifically so this cannot go unnoticed.

### Pitfall 3: Per-page `##FIRST=` third value is NOT the axis FIRST (already flagged in CONTEXT.md — confirmed and elaborated)
**What goes wrong:** The raw dict's `"FIRST"` key is a LIST with one entry per `##PAGE=`/`##FIRST=`
occurrence (2048 entries in the real fixture), not a single global axis triple. `inner["FIRST"][0]`
is the global NTUPLES header's `F1,F2,Y` triple; `inner["FIRST"][1..2047]` are each page's own
`F1,F2,Y_first_row_value` triple (same F1/F2 repeated, only the Y-checkpoint value changes per page).
**Why it happens:** JCAMP-DX keys are not scoped to nesting level — every `##FIRST=` occurrence in
the file (whether the NTUPLES-global one or a per-page-implicit one) accumulates into the same
list under the shared key `"FIRST"`.
**How to avoid:** Either always use `inner["FIRST"][0]` for the global axis anchor (verified: F1/F2
values are identical across all 2048 entries in this fixture, only the Y-component third value
changes), OR — the recommended, more robust approach — **derive the F1 axis directly from the
`##PAGE=` list** (`inner["PAGE"]`, one authoritative `"F1=<hz>"` value per row, guaranteed to match
the actual number of decoded rows). This second approach also solves fixture trimming for free
(Pitfall/Guidance below).
**Warning signs:** An F1 axis with the correct anchor but wrong number of points after trimming a fixture, because `VAR_DIM`/global `FIRST`/`LAST` weren't updated to match a truncated page count.

### Pitfall 4: `$SF`/`$OFFSET`/`$NUC1` list-position ↔ dimension mapping is a parse-order assumption, not a spec guarantee
**What goes wrong:** Hardcoding "index 0 = F1, index 1 = F2" (or vice versa) for the 2-entry
`$SF`/`$OFFSET`/`$BF1`/`$NUC1` lists is fragile — it happens to be `[procs(F2), proc2s(F1)]` order
in this fixture (verified: `$NUC1 = ['<1H>','<13C>']`, `$BF1 = ['499.92','125.704983984']` matching
F2=1H/F1=13C), but nothing in the JCAMP-DX spec guarantees TopSpin always serializes `procs` before
`proc2s`.
**Why it happens:** These are Bruker `$`-prefixed vendor parameters, not part of the JCAMP-DX
NTUPLES vocabulary — unlike `SYMBOL`/`.NUCLEUS`, their multi-value ordering is purely an artifact of
file-write order.
**How to avoid:** Use `.NUCLEUS` (a real NTUPLES-standard field: `".NUCLEUS"= "13C, 1H"` in this
fixture) as the authoritative F1/F2 nucleus identity (its comma-split order IS guaranteed to match
`SYMBOL`'s declared `"F1,F2,Y"` dimension order). Then cross-reference: find which `$NUC1[i]`
(stripped of `<>`) equals the expected nucleus string for each dimension, and use that `i` to index
into `$SF`/`$OFFSET`/`$BF1`. Assert `len($NUC1) == len($SF) == len($OFFSET) == 2` and raise loudly
if not (fail-loud per D-04's established pattern) rather than silently indexing.
**Warning signs:** Swapped F1/F2 axes that individually look "plausible" (e.g. a 13C axis where the F2 (should be 1H) slot got the F1 SF value) — this is exactly the class of error D-03's peak cross-check exists to catch, but a `.NUCLEUS`-based construction avoids the bug entirely rather than relying on the safety net.

## Code Examples

### Vendored decoder — corrected object list and line budget
```
# Source: /opt/miniconda3/lib/python3.12/site-packages/nmrglue/fileio/jcampdx.py (nmrglue 0.12-dev, New-BSD)
# D-05 said "~60 lines: _parse_data + _parse_affn_pac + 3 digit tables" (5 objects).
# Verified actual dependency closure of _parse_data (lines 208-453, ~246 lines, 9 objects):
_DIGITS         # line 208 — plain-digit set, needed by _parse_pseudo
_SQZ_DIGITS     # line 209 — needed by _detect_format AND _parse_pseudo
_DIF_DIGITS     # line 214 — needed by _detect_format AND _parse_pseudo
_DUP_DIGITS     # line 219 — needed by _detect_format AND _parse_pseudo
_detect_format(dataline)          # line 224 — NOT in D-05's list; _parse_data calls this first
_parse_affn_pac(datalines)        # line 254 — plain-number fallback path
_append_value(data, value, isdif) # line 283 — NOT in D-05's list; helper for _finish_value
_finish_value(valuestr, mode, prev, data)  # line 294 — NOT in D-05's list; core pseudo-digit state machine
_parse_pseudo(datalines)          # line 330 — NOT in D-05's list; the actual DIFDUP/SQZ/DUP decode loop
_parse_data(datastring)           # line 432 — the public-ish entry point D-05 named
```
**License header to attribute** (from `nmrglue-0.12.dev0.dist-info/LICENSE.txt`, New-BSD,
Jonathan J. Helmus 2010-2015 — verify exact 4-clause text is reproduced in the vendored file's
docstring/header comment):
```
Copyright (c) 2010-2015 Jonathan J. Helmus
All rights reserved.
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met: ...
```

### Correct ppm-axis formula (verified, ready to implement)
```python
# Verified against BrukerReader ground truth on the sibling raw Bruker dataset (same sample).
def _ppm_scale(first_hz: float, last_hz: float, offset_ppm: float, sf: float, n: int) -> np.ndarray:
    """Bruker JCAMP-DX Hz-axis -> ppm, anchored at OFFSET (already ppm), scaled by SF (not SFO)."""
    sw_hz = first_hz - last_hz
    return np.linspace(offset_ppm, offset_ppm - sw_hz / sf, n)

# F2 (1H, direct) — verified against ground truth to <0.0004 ppm:
#   _ppm_scale(3748.1689453125, 0.0, 7.050608, 499.92, 2048)  -> [7.0506 ... -0.4469]
# F1 (13C, indirect) — verified consistent:
#   _ppm_scale(21997.1407732541, -616.246528781816, 174.9902, 125.704983984, 2048) -> [174.9902 ... -4.9023]
```

### D-08 layer 1: hand-authored, hand-traced mini-vector oracle (verified against the actual decoder)
```python
# Source: manual trace against the JCAMP-DX pseudo-digit tables
# (_SQZ_DIGITS: '@'=0,'A'=1..'I'=9,'a'=-1..'i'=-9; _DIF_DIGITS: '%'=0,'J'=1..'R'=9,'j'=-1..'r'=-9;
#  _DUP_DIGITS: 'S'=1,'T'=2..'Z'=8,'s'=9), then cross-checked by running nmrglue's own
# _parse_data() on the constructed string to confirm the manual trace was correct.
#
# Target row: intensities [100, 105, 105, 102]  (4 points)
# Encoding:
#   "0"    -> AFFN checkpoint value (ignored — first value of every DIFDUP line is a checkpoint, never data)
#   "A00"  -> SQZ: 'A'=leading digit '1', followed by literal "00"  => absolute value 100
#   "N"    -> DIF: 'N'=+5 (relative to previous)                    => 100 + 5 = 105
#   "%"    -> DIF: '%'=0 (relative to previous)                     => 105 + 0 = 105  (pending)
#   "S"    -> DUP: 'S'=repeat-count 1 -> re-emits the PENDING diff (0) once more => another 105
#   "l"    -> DIF: 'l'=-3 (relative to previous)                    => 105 - 3 = 102
# Full encoded line (header + one data line): "(F2++(Y..Y))\n0A00N%Sl"

import nmrglue.fileio.jcampdx as jc
result, dtype = jc._parse_data("(F2++(Y..Y))\n0A00N%Sl")
assert list(result) == [100.0, 105.0, 105.0, 102.0]   # confirmed by direct execution during research
assert dtype == "R"
# The lucy-ng unit test should NOT call nmrglue at all -- it should call ONLY the vendored
# lucy_ng._jcampdx_decode.parse_data() with this same string and assert the same hand-computed list,
# so a bug in the vendored copy (introduced during vendoring, or in a future edit) is caught
# independently of nmrglue ever being installed correctly.
```
Remember to also exercise `Y_FACTOR != 1` in this same test (Pitfall 2) — e.g. assert the reader
multiplies `[100,105,105,102]` by a test-supplied `Y_FACTOR=2.5` to get `[250,262.5,262.5,255]`.

### D-08 layer 2: trimmed real-fixture integration test — verified peak-oracle coordinates
```python
# Verified by decoding all 2048 real HSQC pages directly (research session) and locating genuine
# signal (not noise) via max-abs-intensity scan. Two real cross-peaks fall in the SAME narrow
# F1 (13C) page-index window, both in the classic terpenoid gem-dimethyl / methyl region:
#
#   page 1744: F1=2731.02 Hz -> 21.73 ppm (13C)   F2 col 1655/2048 = 717.77 Hz -> 0.99 ppm (1H)   |I|=372,616,478
#   page 1724: F1=2951.96 Hz -> 23.48 ppm (13C)   F2 col 1662/2048 = 704.96 Hz -> 0.96 ppm (1H)   |I|=366,457,171
#   page 1740: F1=2775.21 Hz -> 22.08 ppm (13C)   F2 col 1655/2048 = 717.77 Hz -> 0.99 ppm (1H)   |I|=86,451,229
#
# Recommendation: trim the fixture to F1 page indices [1720:1755] (35 pages -- slightly above
# D-07's 8-16 target to guarantee BOTH the 21.7ppm and 23.5ppm peaks land inside the window; if a
# strictly <=16-page fixture is preferred, use [1735:1751] (16 pages), which still contains pages
# 1740 and 1744 -- two of the three peaks above, sufficient for an independent oracle).
```

### Fixture size measurement (informs D-07's trimming approach)
```
$ head -n 9826 C20H32O2_HSQC.dx | wc -c      # header only, before first ##PAGE=
281261                                        # ~275 KB -- already exceeds the ~50-100KB target alone
$ sed -n '9827,9957p' C20H32O2_HSQC.dx | wc -c   # one page+datatable block
9016                                          # ~9 KB/page x 16-35 pages = 144-315 KB
```
**Total real header + 16-35 real pages ≈ 420-590 KB — well over the ~50-100 KB target.** The header
is dominated by large Bruker `$`-prefixed bulk arrays the reader never consumes (`$P`, `$D`,
`$CNST`, `$SPNAM`, `$PLW`, `$SP`, `$SPOAL`, `$SPOFFS`, `$SPPEX`, `$SPW`, `$GPNAM`, `AUDITTRAIL`,
etc. — many `(0..63)`-style multi-line parameter blocks). Recommend the plan strip the header down
to only the ~25-30 keys the reader actually consumes (`DATATYPE`, `DATACLASS`, `NUM DIM`, `SYMBOL`,
`VAR_DIM`, `FACTOR`, `FIRST`, `LAST`, `UNITS`, `.NUCLEUS`, `.PULSE SEQUENCE`, `.OBSERVE FREQUENCY`,
`.OBSERVE NUCLEUS`, `.SHIFT REFERENCE`, `$SF`, `$SFO1`, `$SFO2`, `$BF1`, `$BF2`, `$OFFSET`, `$NUC1`,
`TITLE`) plus the real `##PAGE=`/`##DATA TABLE=` blocks for the chosen page window — this is still
"real Bruker DIFDUP pages" per D-07's intent (the data-carrying lines are untouched byte-for-byte),
just with the unused bulk metadata pruned to hit the size target.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| n/a (no prior JCAMP support in lucy-ng) | New `readers/jcamp.py` sibling module | This phase | First binary-free spectrum ingestion path |

**Deprecated/outdated:** None — this is a greenfield reader module, no migration concerns.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `$SF`/`$OFFSET`/`$NUC1`/`$BF1` list-position order is always `[procs(direct), proc2s(indirect)]` across all 6 fixture files and any future JCAMP export from the same TopSpin pipeline (not spec-guaranteed, only empirically verified on this dataset) | Pattern 2 / Pitfall 4 | If a future file has a different write order, naive index-based dimension assignment would silently swap F1/F2 axes; MITIGATED by the recommended `.NUCLEUS`-based cross-check, which should be implemented as a hard assertion, not skipped |
| A2 | The `$OFFSET`-anchor + `$SF`-divisor formula generalizes correctly to files where `SR` (referencing shift) is non-trivial (this fixture happens to have `SF == BF`, i.e. SR≈0 for both dimensions, so the "correctness" of using SF specifically — vs. it just coincidentally equaling BF — could not be independently distinguished from "using BF would also have worked here") | Pattern 2 (Summary) | LOW risk: the formula matches nmrglue's own already-trusted native `bruker.py::add_axis_to_udic` convention (`obs=SF`) exactly, which is battle-tested on Bruker-native (non-JCAMP) files across many datasets in this project already — this is an architecture-consistency argument, not just curve-fitting to one file |
| A3 | HMBC/COSY/NOESY 2D files share the identical NTUPLES/PAGE/DATATABLE structure verified in detail only for HSQC (pulse-program and `.NUCLEUS` fields were spot-checked for all four 2D files, but full page-by-page decode was only run against HSQC) | Code Examples / additional_context item 4 | LOW-MEDIUM: HMBC (heteronuclear, like HSQC) very likely identical; COSY/NOESY (homonuclear, `.NUCLEUS="1H,1H"`) should also match the format but were not decoded end-to-end in this research session — recommend the plan's Wave 0 spot-checks one page from each of the 6 files before committing to "one code path fits all six" |
| A4 | The trimmed-fixture header-pruning approach (keep real PAGE/DATATABLE bytes, drop unused bulk `$` metadata) still counts as "real Bruker DIFDUP pages" for D-07's intent | Code Examples (fixture size) | LOW: this is a judgment call on scope, not a factual risk — flag for discuss-phase-style confirmation if the planner disagrees with pruning vs. keeping the full original header |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **Do HMBC/COSY/NOESY 2D files decode with byte-identical structure to HSQC?**
   - What we know: pulse programs and `.NUCLEUS` fields confirmed compatible with
     `_detect_experiment_type`; `DATACLASS=NTUPLES`, `NUM DIM=2` confirmed present in all four via
     spot-check grep.
   - What's unclear: whether COSY/NOESY (homonuclear, `.NUCLEUS="1H, 1H"`) have any structural
     quirk (e.g. symmetric-storage shortcuts, different `SYMBOL` ordering) not present in the
     heteronuclear HSQC file that was fully decoded.
   - Recommendation: Wave 0 should include a quick one-page decode spot-check against COSY and
     NOESY (the two homonuclear files) before assuming the HSQC-derived code path is universal;
     this is cheap (a few lines of throwaway verification script, not a plan task) and would have
     caught this exact class of surprise if HSQC's own `NDNMRSPECTRUM` bucket mismatch had been
     assumed instead of checked.

2. **Should the "frequency" field on `Spectrum1D`/`Spectrum2D` store `SF` or `SFO`/`.OBSERVE FREQUENCY`?**
   - What we know: the existing `BrukerReader` populates `frequency` from `SFO1` (transmitter freq,
     via `acqus`), not `SF`; it's only consumed downstream in `peak_picker.py` to convert a ppm
     tolerance to Hz (`ppm * spectrum.frequency`), where the SF/SFO gap (<0.01% in this fixture) is
     immaterial.
   - What's unclear: whether any future consumer relies on `frequency` for anything precision-
     sensitive.
   - Recommendation: use `SF` (or `.OBSERVE FREQUENCY`, which happens to equal `SFO1` in this
     fixture) — either choice is low-risk here; prefer `SF` for consistency with the ppm-axis math
     already using it, but this is a minor discretion item, not a blocking question.

## Environment Availability

Not applicable — no external binary, no external service. `nmrglue` (pure-Python + numpy/scipy) is
already installed and importable (`0.12-dev`, verified above). No CLI tools, databases, or network
dependencies are introduced by this phase.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing project standard, confirmed via `pytest --cov=lucy_ng` in CLAUDE.md) |
| Config file | existing project `pyproject.toml`/`pytest.ini` (unchanged by this phase) |
| Quick run command | `pytest tests/readers/test_jcamp.py tests/readers/test_jcampdx_decode.py -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| JC-01 | 2D NTUPLES (HSQC/HMBC/COSY) DIFDUP pages decode into `Spectrum2D` with correct `(n_f1, n_f2)` shape, no external binary | integration | `pytest tests/readers/test_jcamp.py::test_read_2d_shape -x` | ❌ Wave 0 |
| JC-02 | ppm axes correct, reversed, cross-checked against 1D reference | integration + reader-internal assertion | `pytest tests/readers/test_jcamp.py::test_read_2d_ppm_axes_match_1d_reference -x` | ❌ Wave 0 |
| JC-03 | 1D JCAMP (¹H, ¹³C) reads into `Spectrum1D` via the same reader module | integration | `pytest tests/readers/test_jcamp.py::test_read_1d -x` | ❌ Wave 0 |
| JC-04 | DIFDUP/SQZ/DUP/PAC decoder works without nmrglue private API, CI-runnable on committed real fixture | unit (hand-oracle) + integration (real fixture) | `pytest tests/readers/test_jcampdx_decode.py::test_hand_authored_mini_vector -x` AND `pytest tests/readers/test_jcamp.py::test_read_2d_shape -x` | ❌ Wave 0 |

### JC-02 concrete assertion bounds (fail-loud reader assertion, D-04)
```python
# In readers/jcamp.py, after computing f1_ppm_scale / f2_ppm_scale:
def _assert_plausible_ppm_axis(scale: np.ndarray, nucleus: str) -> None:
    bounds = {"1H": (-3.0, 15.0), "13C": (-15.0, 230.0),
              "15N": (-50.0, 900.0), "31P": (-200.0, 250.0)}  # generous, not tight
    lo, hi = bounds.get(nucleus, (-1e6, 1e6))  # unconstrained fallback for uncommon nuclei
    if not (lo <= scale.min() and scale.max() <= hi):
        raise ValueError(f"Implausible {nucleus} ppm axis: [{scale.min():.2f}, {scale.max():.2f}] "
                          f"outside expected [{lo}, {hi}] -- likely wrong Hz/frequency divisor")
    if not (scale[0] > scale[-1]):
        raise ValueError(f"{nucleus} ppm axis not reversed (descending) -- Bruker convention violated")
```
These bounds are deliberately wide (would NOT by themselves have caught this research's own 0.447
ppm F2 error — the naive-approach axis of `[7.4977, -0.0026]` for ¹H is still inside `[-3, 15]` and
still descending). **This is exactly why D-04 requires a second, finer check** — see below.

### JC-02 cross-check tolerance (the finer, load-bearing check)
Given this research measured a **0.447 ppm real error** from the naive-approach bug class, and
typical HSQC/HMBC ¹H linewidths/matching windows in this codebase are on the order of 0.02-0.05
ppm (much tighter than 0.447 ppm), recommend:
```python
# tests/readers/test_jcamp.py
PPM_CROSS_CHECK_TOLERANCE_1H = 0.05   # ppm; catches the 0.447ppm naive-formula bug with 9x margin
PPM_CROSS_CHECK_TOLERANCE_13C = 0.10  # ppm; 13C linewidths are broader, still 6x tighter than a
                                       # divisor-only bug would need to slip past undetected in a
                                       # dataset with a larger SF/SFO gap than this one
```
Project the 2D `Spectrum2D`'s F2 axis onto known 1D ¹H reference peak positions (from
`C20H32O2_1H.dx`, read via the same reader's 1D path) and known 1D ¹³C reference peaks (F1 axis);
assert each matched pair is within tolerance. Use the verified peak-oracle coordinates in Code
Examples (21.7-23.5 ppm / 0.96-0.99 ppm cluster) as the concrete match target for the trimmed
fixture's integration test — this is real, verified signal, not synthetic.

### Wave 0 Gaps
- [ ] `tests/readers/test_jcampdx_decode.py` — D-08 layer 1 hand-authored oracle (JC-04)
- [ ] `tests/readers/test_jcamp.py` — D-08 layer 2 integration test on trimmed fixture (JC-01, JC-02, JC-03, JC-04)
- [ ] `tests/fixtures/jcamp/` — trimmed real 2D fixture + copies of the two real 1D reference files (JC-02 cross-check needs the 1D references, per D-03)
- [ ] Spot-check one page of COSY and NOESY (Open Question 1) before finalizing "one code path for all four 2D experiment types" as a committed assumption

*(Framework itself — pytest — already exists; no new test-infrastructure install needed.)*

## Security Domain

Not applicable in the ASVS sense — this phase parses local scientific data files (JCAMP-DX text)
with no network, auth, session, or user-input-validation surface in the traditional web-security
sense. The one relevant control-family is **input validation / malformed-file handling**:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes (narrow) | Fail-loud on malformed/inconsistent NTUPLES structure (mismatched `len(PAGE) != len(DATATABLE)`, missing required keys) — same fail-loud philosophy as `nus/run_stage` |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed/truncated `.dx` file causing silent wrong data (not a crash) | Tampering (of scientific data integrity, not a security boundary) | Fail-loud assertions on shape/count consistency (`len(pages) == len(datatables) == expected VAR_DIM`), never proceed with a partially-decoded matrix |
| Extremely large `.dx` file (2048x2048 real files are ~9-19 MB) causing excessive memory use if naively loaded whole | Denial of Service (local, not attacker-controlled in this project's use case) | Not a concern for this phase's scope (local scientific files, not user-uploaded); no action needed |

## Sources

### Primary (HIGH confidence)
- `/opt/miniconda3/lib/python3.12/site-packages/nmrglue/fileio/jcampdx.py` (nmrglue 0.12-dev, installed, read in full) — decoder internals, `read()`/`getdataarray()`/`guess_udic()` behavior
- `/opt/miniconda3/lib/python3.12/site-packages/nmrglue/fileio/bruker.py::add_axis_to_udic` (read in full) — the authoritative `obs=SF`/`car=(SFO1-SF)*1e6` convention this research's ppm formula is consistent with
- `/opt/miniconda3/lib/python3.12/site-packages/nmrglue-0.12.dev0.dist-info/LICENSE.txt` — New-BSD license text for attribution
- `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2-jcamp/*.dx` (all 6 files, real data) — direct execution against real file content, not sampled/mocked
- `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/{1,3,6}/` (real sibling Bruker raw data, same sample) — ground truth via `src/lucy_ng/readers/bruker.py::BrukerReader.read_1d()`, the project's own already-trusted code
- `src/lucy_ng/models/spectrum.py`, `src/lucy_ng/readers/bruker.py` (read in full) — target model fields, validator sets, `_detect_experiment_type` reuse target

### Secondary (MEDIUM confidence)
- None used — every claim in this document was verified directly against source code or real data in this session (see Assumptions Log for the residual, honestly-flagged exceptions A1-A4).

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages, existing dependency confirmed installed and importable
- Architecture: HIGH — every pattern verified against real source + real data in this session
- ppm-axis crux question: HIGH — verified to <0.0004 ppm against the project's own already-trusted BrukerReader ground truth on the sibling raw dataset (same sample, same pulse programs)
- Pitfalls: HIGH — all four observed directly (not inferred) while running the actual decode/parse against the real fixture
- HMBC/COSY/NOESY generalization (Assumption A3): MEDIUM — spot-checked headers only, not fully decoded

**Research date:** 2026-07-23
**Valid until:** No expiry concern — findings are against a fixed local file (the fixture) and a
pinned dependency (`nmrglue @ git+...` in `pyproject.toml`); re-verify only if the fixture files or
the nmrglue pin change.
