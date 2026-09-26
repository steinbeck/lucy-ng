# Phase 101: JCAMP-DX Reader - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-23
**Phase:** 101-jcamp-dx-reader
**Areas discussed:** ppm-axes & F1 frequency (JC-02), Decoder strategy (JC-04), CI fixture (JC-04), Reader API & experiment detection

---

## ppm-axes & F1 frequency (JC-02)

### Frequency source for Hz→ppm
| Option | Description | Selected |
|--------|-------------|----------|
| In-file `##$SFO1`/`##$SFO2` (or BF) | Both freqs present in the .dx (F2=SFO1 ¹H, F1=SFO2 ¹³C); reader self-contained | ✓ |
| Standard `.OBSERVE FREQUENCY` + gamma | Only direct-dim ¹H freq; derive ¹³C via gyromagnetic ratio — fragile | |
| From sibling 1D ¹³C reference file | Couples files; fails if only 2D present | |

### Cross-check for JC-02
| Option | Description | Selected |
|--------|-------------|----------|
| Auto vs 1D-reference peaks | Project 2D onto axes, match peaks to 1D ¹H/¹³C .dx within tolerance | ✓ |
| Axis range vs expected windows | Only min/max check — catches gross errors, not calibration | |
| §10 ground-truth shifts | Strongest chemistry check but dataset-specific → JVAL/Phase 103, not a generic reader test | |

### Where the check lives
| Option | Description | Selected |
|--------|-------------|----------|
| Both: hard range assertion (reader) + test cross-check | Fail-loud + provable | ✓ |
| Test only | Lean reader, no field self-defense | |
| Reader assertion only | Partly conflicts with the JC-04 CI-fixture requirement | |

**User's choice:** In-file SFO1/SFO2 · Auto vs 1D peaks · Both.
**Notes:** During discussion the ¹³C frequency was confirmed present in-file as `##$SFO2= 125.7157` / `##$BF2= 125.705` (the standard `.OBSERVE FREQUENCY` carries only ¹H). A research flag was recorded: SFO (transmitter) vs referenced SF/SR as the divisor — the auto cross-check is the safety net.

---

## Decoder strategy (JC-04)

### Line-decoder acquisition
| Option | Description | Selected |
|--------|-------------|----------|
| Vendor (~60 lines) | Copy `_parse_data`+`_parse_affn_pac`+digit tables with BSD attribution; satisfies JC-04 literally | ✓ |
| Wrap private funcs | Least code but depends on nmrglue private API (0.12-dev) → violates JC-04 wording | |
| Reimplement from scratch | IP-cleanest but most effort/risk on a solved problem | |

### Header/metadata parsing
| Option | Description | Selected |
|--------|-------------|----------|
| Public `ng.jcampdx.read()` for dict + own page assembly | Public API for header (works, data=None on 2D); only page-stacking+decode is ours | ✓ |
| Fully own JCAMP parser | Zero nmrglue dependency but reinvents header parsing | |

**User's choice:** Vendor the decoder · Public read() for metadata + own assembly.
**Notes:** Decoder confirmed small (`_parse_data` 22 lines, `_parse_affn_pac` 27 lines, digit tables present); nmrglue is New-BSD → vendoring with attribution is fine.

---

## CI fixture (JC-04)

### Fixture form
| Option | Description | Selected |
|--------|-------------|----------|
| Real 2D .dx trimmed to a few F1 pages | ~50–100 KB, real DIFDUP pages, realistic assembly | ✓ |
| Tiny synthetic 2D (4×8) | Minimal but requires hand-encoding (only decoder vendored) | |
| 1D-only fixture | Does not test the 2D assembly (the actual novelty) — insufficient | |

### Correctness oracle
| Option | Description | Selected |
|--------|-------------|----------|
| Hand-spec mini-vector (independent) + real integration | Spec-derived integers = independent oracle for the kernel; plus real trimmed-2D integration test | ✓ |
| Freeze our decoder output as golden | Catches regressions but not the initial decode bug (circular) | |
| Shape/spot-checks only | Cheapest, weakest guarantee | |

**User's choice:** Trimmed real 2D · Hand-spec mini-vector + real integration.
**Notes:** Directly applies the Phase-100 lesson that mock-only "verified" gave false confidence.

---

## Reader API & experiment detection

### API shape
| Option | Description | Selected |
|--------|-------------|----------|
| `JcampReader` class, `read_1d`/`read_2d` + `read()` dispatch | Mirrors `BrukerReader`; easy Phase-102 wiring | ✓ |
| Free functions | Slightly leaner but breaks the BrukerReader pattern | |
| Single `read()` auto-dispatch only | Phase 102 may want to target 1D/2D explicitly | |

### Experiment-type detection
| Option | Description | Selected |
|--------|-------------|----------|
| `##.PULSE SEQUENCE` via existing `_detect_experiment_type` | One source of truth, no new code | ✓ |
| From `##TITLE` | Free-form, fragile | |
| From filename | Relies on naming convention, not content | |

### 1D data path
| Option | Description | Selected |
|--------|-------------|----------|
| nmrglue-public data for 1D, vendored decoder only for 2D pages | Minimal code; each path uses the strongest tool | ✓ |
| 1D also through the vendored decoder | One symmetric codepath but duplicates what nmrglue already does for 1D | |

**User's choice:** JcampReader class + read() dispatch · `##.PULSE SEQUENCE` detector · nmrglue-public 1D data / vendored 2D only.

---

## Claude's Discretion
- Caret nucleus-prefix stripping (`^1H`→`1H`), solvent/metadata mapping, exact module/file names, fixture storage location under `tests/`.
- No new optional extra needed — nmrglue is already a core dependency.

## Deferred Ideas
- NOESY consumption by the CASE constraint model (JC-F1) — NOESY still reads fine here.
- JCAMP writing/export (JC-F3); other vendor formats (JC-F2).
- RECON-F1 (hmsIST/mddnmr NUS self-reconstruction, carried from v10.0).
