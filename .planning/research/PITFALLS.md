# Pitfalls Research: Automatic Bruker NUS 2D Reconstruction

**Domain:** Fully-automatic, headless reconstruction of non-uniformly-sampled (NUS) Bruker 2D NMR (COSY/HSQC/HMBC) for CASE, cross-platform (macOS Apple Silicon / Linux / Windows)
**Researched:** 2026-07-12
**Confidence:** HIGH for schedule/parameter facts (verified directly against this project's own acqus/acqu2s/nuslist files); MEDIUM for reconstruction-algorithm behavior (peer-reviewed methods papers); MEDIUM-LOW for backend-specific CLI/install quirks (official docs + community wikis, not independently re-run here)

**Grounding note:** Several pitfalls below cite exact values read directly from
`~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/{2,3,4}/acqus`,
`acqu2s`, `nuslist` on 2026-07-12 — these are not generic claims, they are this project's
actual data.

| Exp | Type | PULPROG | FnMODE | acqus TD (F2) | acqu2s TD (F1) | nuslist lines | nuslist max index | NusTD (full grid) | Implied sampling % |
|-----|------|---------|--------|---------------|----------------|----------------|--------------------|--------------------|---------------------|
| 2 | COSY | cosygpmfppqf | 1 (QF) | 2048 | 188 | 188 | 748 | 750 | 25.07% |
| 3 | HSQC | hsqcedetgpsp.3 | 6 (Echo-AntiEcho) | 2048 | 100 | 50 | 199 | 400 | 25.00% |
| 4 | HMBC | hmbcetgpl3nd | 6 (Echo-AntiEcho) | 2048 | 232 | 116 | 349 | 700 | 33.14% |

Also verified: `BYTORDA=0` (little-endian), `DTYPA=0` (int32), `DIGTYP=12`, `DECIM=5333.33…`,
`DSPFVS=20`, `GRPDLY=67.9851531982422` (non-integer!) — identical across all three
experiments (same probe/pulse-program family, av499 spectrometer).

---

## Critical Pitfalls

### Pitfall 1: Assuming one schedule/TD relationship for all three experiments (real vs complex F1)

**What goes wrong:**
Code that derives "number of sampled F1 increments" as either `acqu2s TD` or `acqu2s TD / 2`
universally will be right for two of the three experiments and silently wrong for the third.

**Why it happens:**
`TD` in `acqu2s` always counts **real** points. For QF (`FnMODE=1`, exp2/COSY) each sampled
increment is a single real point, so `nuslist` length == `TD` (verified: 188 == 188). For
Echo-AntiEcho (`FnMODE=6`, exp3/HSQC and exp4/HMBC) each sampled increment is a **complex**
pair (N + P components), so `nuslist` length == `TD / 2` (verified: exp3 50 == 100/2; exp4
116 == 232/2). A single hard-coded divisor (e.g. "always TD/2") passes for HSQC/HMBC in this
milestone's own dataset and then silently corrupts COSY, or vice versa — exactly the kind of
per-experiment inconsistency easy to miss when the three FnMODEs (1, 6, 6) are developed and
tested one at a time rather than together.

**How to avoid:**
Derive the sampled-point count from `FnMODE` explicitly: `n_sampled = TD` when `FnMODE==1`
(and other real-only modes), `n_sampled = TD // 2` for complex modes (4, 5, 6). Assert
`n_sampled == len(nuslist)` for every experiment before any conversion step runs — a
hard-fail assertion, not a warning.

**Warning signs:**
Off-by-2x errors that don't crash — the reconstruction backend receives a schedule half (or
double) the length it expects and either truncates/pads silently or throws an opaque
dimension-mismatch error deep inside the backend rather than at lucy-ng's own conversion
boundary.

**Phase to address:** Bruker→backend conversion phase (owns nuslist/acqus/acqu2s parsing).

---

### Pitfall 2: nuslist index base (0 vs 1) and the "sorted vs acquisition-order" trap

**What goes wrong:**
Two independent index-related bugs are easy to conflate:
(a) treating Bruker's 0-based `nuslist` indices as 1-based (or vice versa) when handing them
to a reconstruction backend that expects the other convention, producing a one-increment
frequency/phase shift across the entire F1 dimension; and
(b) **sorting** the nuslist before building the sparse→full mapping. `nuslist` rows correspond
to **consecutively acquired** FID blocks in the `ser` file, in randomized acquisition order —
row *i* of `nuslist` is the t1-grid index of the *i*-th recorded FID block, not the *i*-th
smallest index. If the schedule is sorted first, `ser` block *i* gets mapped to the wrong grid
position for every row where sort-order != acquisition-order.

**Why it happens:**
Verified here: exp2's `nuslist` is *not* sorted (`0, 124, 431, 670, 369, …`) — it is in
acquisition order, matching Bruker's documented convention that "rows correspond to
consecutively acquired NUS points." Code that "cleans up" the list by sorting it (e.g. to make
debugging easier, or because a downstream tool's example script assumes ascending order) breaks
the block↔index correspondence invisibly — the resulting reconstruction still produces a
complete-looking, plausible 2D spectrum (CS/IST will "reconstruct" *something* from
scrambled input), just built from the wrong FID-to-t1-position mapping. This is the single
most dangerous class of bug in this domain because it degrades gracefully into noise/artifact
rather than crashing.
Bruker's own TopSpin GUI has a documented version of this same trap: clicking "Calculate" or
"Show table" on an already-acquired NUS list **regenerates and overwrites it as a new random
schedule**, silently invalidating any list that was supposed to describe already-recorded data
(MEDIUM confidence, community wiki).

**How to avoid:**
Never sort `nuslist` before building the sparse-to-full index map; use row order == acquisition
order == `ser` block order, always. Treat `nuslist` values as 0-based indices into a grid of
size `NusTD/2` (complex modes) or `NusTD` (real modes) — verified consistent here: exp2 max
index 748 for grid 750 (0–749); exp3 max 199 for grid 200 (0–199); exp4 max 349 for grid 350
(0–349) — i.e. Bruker's own `nuslist` is 0-based and inclusive of the full grid range, which
must be confirmed against whatever indexing convention the chosen backend's expansion tool
(e.g. `nusExpand.tcl`) expects; adapt at the conversion boundary rather than assuming they
match. Never re-derive/regenerate `nuslist` from scratch anywhere in the automated pipeline —
treat the on-disk file that was present when acquisition finished as immutable, read-only
ground truth.

**Warning signs:**
A reconstructed spectrum with plausible peak shapes but wrong relative peak positions or
diffuse, low-level noise smeared across all of F1 (rather than concentrated ridges at expected
t1-modulation frequencies) — this is qualitatively different from, and easy to confuse with,
ordinary undersampling noise.

**Phase to address:** Bruker→backend conversion phase; add a regression test fixture using
this project's own three `nuslist` files (unsorted, verified acquisition-order) asserting the
converter never sorts them.

---

### Pitfall 3: Digital filter group delay (GRPDLY) not removed, or removed with the wrong method

**What goes wrong:**
Raw Bruker `ser`/`fid` data from a digital receiver contains a group-delay artifact at the
start of every FID (verified here: `GRPDLY=67.9851531982422`, a large, non-integer number of
points — same value across exp2/3/4). If this is not removed (or removed with a rounded /
wrong value), every time-domain point is offset from where the causal FID actually starts.
For a plain 1D FT this shows up as a large first-order phase error that a human easily
corrects by eye; for NUS reconstruction it is much worse, because IST/CS/SMILE algorithms
implicitly assume the sampled time-domain signal is a **causal, decaying** FID (this is the
same causality assumption behind the "virtual echo" trick, Pitfall 8) — an uncorrected or
mis-corrected group delay violates that assumption at the source, before reconstruction even
starts, and can manifest as reconstruction-stage artifacts that are much harder to attribute to
their root cause than a simple 1D phase error.

**Why it happens:**
`GRPDLY` here is non-integer (67.985…), so the correction requires interpolation-based removal
(e.g. nmrglue's `remove_digital_filter`/`rm_dig_filter`, which implements the Bruker DMX
protocol from Westler & Abildgaard); a naive integer-truncation or "just left-shift by
`round(GRPDLY)` points" approach loses sub-point precision and leaves a residual timing/phase
error. nmrglue's function: when a non-zero `GRPDLY` is supplied it is used directly; when
`GRPDLY < 0`, `DECIM`/`DSPFVS` are used to look up the delay in a hard-coded table instead —
mixing these two paths inconsistently across the three experiments (which do all agree here,
but need not in general) is a realistic implementation slip.

**How to avoid:**
Read `GRPDLY` directly from each experiment's own `acqus` (don't hard-code the value seen in
this dataset) and always prefer the direct `GRPDLY` path over the `DECIM`/`DSPFVS` lookup-table
fallback when `GRPDLY` is present and non-negative — it is more accurate. Apply the correction
before any further F2 processing (apodization/ZF/FT), consistently for every experiment,
including the reliable 1D references (exp1/6/7) so the ppm/phase calibration transfers
correctly (Pitfall 6).

**Warning signs:**
F2 (direct-dimension) lineshapes that look phase-twisted or asymmetric even after auto-phase
"succeeds" numerically; a constant first-order phase term that auto-phase keeps fighting
without fully resolving; or 1D projections of the 2D spectrum that don't overlay cleanly on the
genuinely reliable 1D reference spectra (exp1 ¹H, exp6/7 ¹³C).

**Phase to address:** Bruker→backend conversion phase (F2 digital-filter removal must happen
before handoff to the reconstruction backend).

---

### Pitfall 4: Byte order / data type mis-assumption when reading `ser`

**What goes wrong:**
`ser` is raw binary; reading it with the wrong byte order or word size produces a numerically
"valid" but completely garbage time-domain array — no crash, no dimension mismatch, just noise.
Fed into a CS/IST reconstruction, sparse-recovery algorithms are perfectly happy to
"sparsify" pure noise into a small number of plausible-looking peaks (this is a known failure
mode of over-iterated IST even on *correct* data, see Pitfall 7) — meaning a byte-order bug
does not reliably manifest as an obviously-broken spectrum; it can manifest as a clean-looking
spectrum with entirely fabricated peaks.

**Why it happens:**
Verified here: `BYTORDA=0` (little-endian) and `DTYPA=0` (32-bit integer) for all three
experiments — this is typical for modern Bruker consoles but is a per-experiment,
per-spectrometer parameter, not a safe global default. A converter that hard-codes
little-endian/int32 (because that's what this dataset uses) will misread data acquired on a
console configured for big-endian or a different word width.

**How to avoid:**
Always read `BYTORDA` and `DTYPA` from each experiment's own `acqus` and select the numpy
dtype/byte order dynamically (this is exactly what `nmrglue.fileio.bruker` already does when
used correctly — the risk is a hand-rolled or short-cut binary reader bypassing it).

**Warning signs:**
A "successful" conversion that yields an F2 spectrum with no resemblance to the reliable 1D
reference (wrong shape, flipped, or noise-only) — treat this as a hard-stop conversion bug, not
a reconstruction-quality issue.

**Phase to address:** Bruker→backend conversion phase; add an automated sanity check comparing
the F2 projection of every converted experiment against its own directly-acquired 1D reference
before allowing reconstruction to proceed.

---

### Pitfall 5: FnMODE mismatch — one-size-fits-all F1 processing across QF and Echo-AntiEcho

**What goes wrong:**
This milestone's own three experiments span two different F1 acquisition modes: QF (exp2/COSY,
`FnMODE=1` — real-valued, single-channel, no frequency discrimination in F1 without special
handling) and Echo-AntiEcho (exp3 HSQC, exp4 HMBC, `FnMODE=6` — gradient-selected N/P
coherence-pathway combination, complex per increment). A pipeline that applies the same F1
combination/FT logic to all three will produce COSY output that is folded/aliased or
magnitude-only instead of correctly phase-sensitive, or corrupt the P/N combination for the
Echo-AntiEcho experiments (which requires adding/subtracting the two gradient-selected
pathways in a specific way before the complex FT, distinct from a plain States/TPPI complex
FT). Either failure can still yield a spectrum with peaks in roughly plausible positions —
sign/lineshape/aliasing errors are easy to miss without a human looking at the plot.

**Why it happens:**
Developing and testing against one experiment at a time (e.g. get HSQC working first) makes it
easy to bake FnMODE=6-specific logic into what should be a general F1-processing step, then
discover COSY (`FnMODE=1`) breaks later — or the reverse.

**How to avoid:**
Branch F1 combination/FT logic explicitly on `FnMODE` (1=QF real, 4=States, 5=States-TPPI,
6=Echo-AntiEcho) read per-experiment from `acqu2s`, matching whichever reconstruction backend's
own mode flag (e.g. SMILE/NMRPipe's `-yMODE`/`-EA` conversion-script flags) is selected in the
research/stack phase. Never assume a single default mode across all NUS CASE experiments —
future compounds may add NOESY/TOCSY with yet other FnMODEs.

**Warning signs:**
COSY cross peaks not symmetric about the diagonal (a real H–H COSY spectrum must be, within
picking tolerance — a concrete, automatable check, see Pitfall 15); HSQC/HMBC cross peaks
appearing folded/aliased relative to the known ¹³C shift range from the reliable 1D reference.

**Phase to address:** Bruker→backend conversion phase + reconstruction/processing phase
(FnMODE branching must be threaded through both conversion and F1 FT/combination).

---

### Pitfall 6: ppm axis (SFO1/SW_h/O1/OFFSET) not validated against the reliable 1D reference

**What goes wrong:**
`SFO1`, `SW_h`, and `O1` differ between the F2 (¹H, shared: `O1=1649.74`, `SFO1=499.92…`
across exp2/3/4) and F1 dimensions (different nucleus/values per experiment — e.g. exp3 F1
`SFO1=125.7157…`, `O1=10684.92…` for ¹³C; exp4 F1 `SFO1=125.7194…`, `O1=14456.07…`). Getting
the F1↔F2 axis assignment backwards, or computing the ppm-per-point scale from the wrong
`SW_h`/`SFO1` pair, silently shifts or rescales one whole axis of the 2D spectrum by a constant
— every cross peak still "looks like" a peak, just at the wrong ppm, so downstream HSQC/HMBC
picking can confidently assign correlations to the wrong carbon.

**Why it happens:**
Each of the three experiments has its own F1 nucleus-specific `SFO1`/`O1`/`SW_h` triplet in
`acqu2s`, distinct from F2's proton values in `acqus`; a converter that reuses one experiment's
calibration for another, or that doesn't carry the calibration through the reconstruction step
unchanged, produces axis errors that are invisible without a reference check.

**How to avoid:**
After every reconstruction, cross-check the resulting ¹³C shift list (from HSQC and quaternary
carbons) against the ground-truth 1D shift list already established for this compound
(NUS-RECONSTRUCTION-GUIDE.md §10: 20 known ¹³C shifts, e.g. 79.35 Cq-O, 142.00/135.86 olefinic
quaternaries) — treat any systematic offset as a hard conversion bug, not a "close enough"
tolerance issue. Carry F1/F2 calibration parameters through the pipeline explicitly tagged by
dimension and nucleus, never inferred positionally.

**Warning signs:**
Reconstructed HSQC ¹³C shifts that are all offset from the known-good 1D ¹³C list by a roughly
constant delta, or an HMBC/HSQC F1 axis whose overall span doesn't match the `SW_h`/`SFO1`
implied ppm range for the expected nucleus.

**Phase to address:** Bruker→backend conversion phase + peak-picking/QC phase (QC gate must
include the §10 ground-truth cross-check).

---

### Pitfall 7: Fabricated cross-peaks from over- or under-converged reconstruction become hard LSD constraints (the core CASE risk)

**What goes wrong:**
This is the specific failure this milestone exists to fix, and the specific new risk it must
not reintroduce in a different form. Two symmetric failure modes:
- **Under-iteration / poor convergence:** leaves residual t1-ridge artifacts along F1 — exactly
  what happened in the 2026-07-09 CASE run (documented in NUS-RECONSTRUCTION-GUIDE.md §2): an
  ad-hoc per-column IST left HMBC/COSY "too artefact-ridden (t1-Ridges)" for LSD to prune a
  ~10⁶-candidate tetracyclic diterpene search space.
- **Over-iteration:** IST-family algorithms are known to progressively "sparsify" pure noise
  into small numbers of noise-peaks once the true signal has already converged — i.e. running
  more iterations than needed does not just "waste time," it actively fabricates new,
  plausible-looking cross peaks that were never in the data (documented in the peer-reviewed
  compressed-sensing pitfalls literature, see Sources). A fabricated HMBC or COSY cross peak is
  categorically worse for CASE than a missing one: `lsd-engineer` treats these as hard
  BOND/HMBC/COSY generation constraints (per this repo's existing constraint-hardness
  philosophy, v9.0 FIX-10), so a fabricated correlation doesn't just fail to help — it can
  actively prune the *correct* structure out of LSD's candidate space, producing a confident,
  wrong, "clean" answer with no obvious symptom (exactly the class of "clean-but-wrong" failure
  the v9.1 milestone (RANK/IDENT/MULT) was built to catch at the ranking stage — this pitfall
  is the same failure pattern one stage earlier, at data ingestion).

**Why it happens:**
Automated pipelines need *some* iteration/convergence stopping rule, and a fixed iteration
count is the easiest one to implement — but the "right" number of iterations is data-dependent
(sparsity, dynamic range, noise level), and there is no way to guess it correctly for every
future NUS CASE compound without a data-driven stopping criterion. There is no human in the
loop to eyeball "does this look over-processed."

**How to avoid:**
- Prefer a residual/convergence-based stopping rule over a fixed iteration count (e.g. an
  IST-S–style "keep strict accordance with measured data" variant, or interrupt once the
  change in reconstruction residual between iterations drops below a threshold) — a fixed
  count should at most be a hard upper bound, not the primary stopping criterion.
- Hold out a fraction of the *actually sampled* points (not synthetic points) during
  reconstruction and check that the reconstruction predicts them correctly — a direct,
  data-native cross-validation check requiring no external ground truth, adaptable per NUS
  CASE run.
- Add a dedicated **QC gate between reconstruction and peak-list export** (see Pitfall 16)
  that specifically screens for the two signatures of fabricated peaks: (a) peaks with poor
  agreement to held-out sampled points, and (b) peaks inconsistent with the compound's own
  reliable 1D data (e.g. an HSQC cross peak implicating a ¹³C shift that isn't in the 1D
  ¹³C list at all).
- Never let `lsd-engineer`/CASE consume reconstruction output directly — always route through
  the QC gate, and propagate a per-peak confidence flag so low-confidence, reconstruction-only
  correlations can be treated as *soft* hints rather than hard constraints, extending this
  repo's existing constraint-hardness-guard philosophy (v9.0 FIX-10) to reconstruction-derived
  peaks specifically.

**Warning signs:**
A reconstructed HMBC/COSY that looks "too clean" — very few weak/ambiguous correlations, sharp
peaks everywhere, no residual noise floor at all — can be as much a red flag as visible ridges;
real crowded-aliphatic HMBC/COSY data (this compound has 20 carbons packed between 21–52 ppm
plus several overlapping methyls) should retain some genuine ambiguity. Any single cross peak
that, if true, would contradict the already-hard 1D-derived facts in §10 (e.g. a one-bond HSQC
correlation appearing at 79.35 or another confirmed-quaternary shift) is a definitive
reconstruction defect, not new chemistry.

**Phase to address:** Reconstruction/processing phase (stopping criterion) + a dedicated
peak-picking/QC-gate phase that must exist as its own explicit pipeline stage, not be folded
into "peak picking" as an afterthought.

---

### Pitfall 8: Skipping the "virtual echo" / causal-signal construction

**What goes wrong:**
Several widely-used reconstruction algorithms (SMILE, mddNMR's IST) rely on a virtual-echo (or
equivalent causality-exploiting) construction of the time-domain signal — reflecting/mirroring
the FID to build a purely-real, symmetric representation that matches the implicit signal model
the sparse-recovery algorithm assumes. Skipping this (or getting the mirroring/zero-filling
convention wrong) can generate spurious FID modulations from ad-hoc extrapolation of the
truncated signal tail, which shows up in the frequency domain as **peak splitting** — a
reconstructed doublet where the real spectrum has a single peak, or vice versa.

**Why it happens:**
"Virtual echo" is a backend-internal implementation detail easy to skip when hand-rolling a
NUS pipeline (as the prior ad-hoc per-column IST in this project did) rather than using an
established backend that implements it correctly.

**How to avoid:**
Use the reconstruction backend's own virtual-echo / causality option rather than reimplementing
FID extrapolation manually; verify (via the backend's documentation for the chosen tool,
established in the parallel stack-selection research) whether virtual-echo mode is on by
default or must be requested explicitly.

**Warning signs:**
Cross peaks that appear as closely-spaced doublets where only one correlation is chemically
expected (compare against the known multiplicity/DEPT pattern from the reliable 1D reference).

**Phase to address:** Reconstruction/processing phase.

---

### Pitfall 9: 25–33% sampling near the practical reliability floor for a crowded aliphatic diterpene

**What goes wrong:**
Reconstruction reliability under compressed sensing scales roughly as `m ∝ K·log(n/K)`, where
`m` is the number of sampled points, `K` is the number of significant spectral features, and
`n` is the full grid size — not simply as a flat percentage. At low `m` relative to `K`, the
*highest*-intensity peaks are recovered reliably while **lower-intensity peaks are
systematically suppressed or lost first**. This compound's HSQC/HMBC data is exactly the
adversarial case: ~17–20 protonated carbons crowded between 21–52 ppm (per §10), several
long-range HMBC correlations that are inherently weaker than one-bond HSQC correlations, and
sampling fractions of only 25% (HSQC/COSY) and 33% (HMBC) — i.e. the specific 2–3J HMBC
correlations LSD most needs to prune ring connectivity are exactly the class of signal most
at risk of being under-recovered at this sampling density.

**Why it happens:**
25–33% NUS sampling is a normal, common experimental choice (time-saving), but the
"percentage sampled" framing obscures that reliability actually depends on peak count and
dynamic range, not the percentage alone — a pitfall specific to crowded, information-dense
spectra like polycyclic diterpene skeletons, not to sparse spectra of the same sampling
percentage.

**How to avoid:**
Do not tune reconstruction parameters (thresholds, iteration counts) only against the strong
one-bond HSQC correlations; explicitly validate weak/long-range HMBC peak recovery via the
held-out cross-validation check (Pitfall 7) and treat HMBC as the experiment needing the most
conservative (least aggressive thresholding) reconstruction settings of the three. If SMILE
(or the chosen primary backend) demonstrably drops weak HMBC correlations, fall back to
hmsIST/mddnmr's virtual-echo IST, which the literature reports as more accurate for peak
*intensity* recovery specifically below ~20% sampling (MEDIUM confidence — comparative claim
from a single source; the guide's own §7 already anticipates this exact fallback need).

**Warning signs:**
An HMBC reconstruction with suspiciously few correlations per carbon relative to what a
diterpene skeleton of this size chemically implies (a devils-advocate-style expectation check,
analogous to this repo's existing aromatic-ring-awareness pattern), especially if the missing
correlations cluster around the crowded 21–37 ppm region rather than being randomly distributed.

**Phase to address:** Reconstruction/processing phase (parameter choice) + peak-picking/QC-gate
phase (weak-peak recovery check).

---

### Pitfall 10: Auto-phase failure with no human to catch it (echo-antiecho HSQC/HMBC)

**What goes wrong:**
F1 phase for gradient-selected Echo-AntiEcho experiments is largely a *deterministic* property
of the pulse sequence's coherence-selection scheme (a fixed 0°/90° recipe per the pulse
program, e.g. `hsqcedetgpsp.3`, `hmbcetgpl3nd`), not something that benefits from an amplitude-
based iterative auto-phase search. Generic auto-phase algorithms (which typically minimize
dispersive/negative-lobe content assuming clean Lorentzian lineshapes) can converge on a wrong
180°, or a wrong first-order term, especially on CS/IST-reconstructed data whose lineshapes are
not the plain FT of a real, undistorted FID — the very non-linearity that makes CS/IST powerful
also makes generic phase-search heuristics unreliable on its output. With no human in a GUI to
notice an inverted or dispersive-looking cross peak, a phase error silently propagates into
picked peak signs (directly affecting edited-HSQC CH/CH3 vs CH2 discrimination) and intensities.

**Why it happens:**
Manual NMRPipe pipelines conventionally have phase corrections "inserted by hand in processing
scripts" after a human inspects the spectrum once — a step this project must eliminate by
design (fully automatic, no GUI) but which most existing NUS processing tutorials still assume.

**How to avoid:**
Prefer deriving F1 phase deterministically from the known pulse-sequence coherence-selection
recipe over a blind numerical auto-phase search where possible. Where an automated search is
still needed (F2, or backends without a documented deterministic recipe), constrain and verify
it: cross-check F2 phase against the independently reliable, already-processed 1D reference
spectra (exp1 ¹H, exp6/7 ¹³C) — these are known-good, so F2 phase agreement with them is a hard
pass/fail check, not a heuristic. For F1, verify the phase-implied peak sign pattern
(edited-HSQC: CH/CH3 positive, CH2 negative, or the sequence's documented convention) against
the multiplicity pattern already established from the reliable 1D DEPT data.

**Warning signs:**
Edited-HSQC signs that don't self-consistently split into two clean classes matching known
DEPT CH/CH3 vs CH2 assignments; systematic dispersive "tails" on cross peaks; a phase-QC metric
(e.g. residual dispersive-component fraction, analogous to ACME-style baseline/phase quality
scores) above a fixed threshold.

**Phase to address:** Reconstruction/processing phase (phasing step) + peak-picking/QC-gate
phase (automated phase-QC check, no human fallback).

---

### Pitfall 11: NMRPipe on Apple Silicon — architecture/Rosetta failures that don't crash

**What goes wrong:**
NMRPipe ships as a large collection of small, individually-compiled C binaries chained
together via `csh`/`tcsh` pipe scripts. Historically distributed binaries target `x86_64`
macOS; on Apple Silicon (this project's primary dev platform) they require Rosetta 2
translation. If Rosetta is missing, or if even one binary in a long pipe chain is a stray
wrong-architecture or missing binary, `csh` pipeline scripts do not reliably propagate a
non-zero exit code through every stage of a `|` chain — a failed stage can leave a
truncated or empty intermediate file that a later stage in the same pipeline happily
processes as if it were valid, complete data, producing a "finished" but garbage output.
This project's own environment check (NUS-RECONSTRUCTION-GUIDE.md §4) already flags this as
an open, unresolved risk: NMRPipe/mddnmr are not yet installed on the dev Mac, and the guide
explicitly calls out "bei NMRPipe auf macOS-Binaries / Rosetta achten."

**Why it happens:**
`csh`'s exit-status/pipefail semantics are weaker than modern `bash`'s `set -o pipefail`, and
NMRPipe's own scripts were written assuming an interactive human watching terminal output for
error messages, not an unattended agent parsing structured status.

**How to avoid:**
Wrap every external NMRPipe/backend invocation from lucy-ng in an explicit post-condition
check: verify the process's own exit code AND verify the expected output file exists, is
non-empty, and matches the expected byte size (NMRPipe's binary format has a fully computable
size from its own header: point counts × 4 bytes per float32) before proceeding to the next
stage. Confirm Rosetta 2 is installed and functioning as an explicit preflight check (e.g.
`arch -x86_64 nmrPipe -help` succeeding) rather than discovering architecture failures mid-run.

**Warning signs:**
A pipeline that "completes" in implausibly short wall-clock time for the data size, or an
output file present but suspiciously small/zero bytes.

**Phase to address:** Cross-platform portability phase (own the preflight check + fail-loud
subprocess wrapper used by every other phase's external-tool calls).

---

### Pitfall 12: Windows has no csh/tcsh, and NMRPipe's install model assumes it as the login shell

**What goes wrong:**
NMRPipe's canonical install (`install.com`) and most of its example processing scripts are
`csh`/`tcsh` scripts, and multiple independent installation guides state a C-shell login shell
is a hard requirement for a smooth install. Native Windows has neither `csh` nor `tcsh`
available by default, and no native NMRPipe Windows build is documented as a first-class,
actively-maintained target (community guidance instead points to a Linux VM). A team assuming
"cross-platform" means "the same install script works everywhere" will discover this only when
they actually attempt Windows, likely late.

**Why it happens:**
NMRPipe predates modern cross-platform shell tooling and its install/processing model has
never been rewritten around it.

**How to avoid:**
Treat Windows as requiring either (a) WSL2 with a Linux NMRPipe install (inheriting the Linux
32-bit-library trap, Pitfall 13, inside WSL), (b) a Docker container running the Linux NMRPipe
build (a working reference Dockerfile for NMRPipe + mddnmr exists — see Sources), or (c) a
Python-native reconstruction backend (no NMRPipe/csh dependency at all) as the Windows-specific
fallback path — decide and document this explicitly in the portability matrix PROJECT.md
already commits to producing, rather than discovering the gap during an actual Windows run.

**Warning signs:**
None available headlessly on native Windows short of an explicit "is csh/tcsh present"
preflight check failing fast with an actionable message pointing at the WSL2/Docker/
Python-native fallback.

**Phase to address:** Cross-platform portability phase.

---

### Pitfall 13: Linux 64-bit systems missing 32-bit libraries NMRPipe binaries need

**What goes wrong:**
Multiple independent NMRPipe install guides note that many modern 64-bit Linux distributions
no longer ship 32-bit compatibility libraries by default, and that "in this case, all of the
programs will fail to run" — a whole-install failure, not a partial one, on an otherwise
plausible-looking Linux target.

**Why it happens:**
Some NMRPipe binaries were built 32-bit and never rebuilt; distros have progressively dropped
default 32-bit library support.

**How to avoid:**
Add an explicit dependency check (e.g. verifying the relevant `lib32`/`multiarch` packages, or
simply attempting to run `nmrPipe -help` as the very first automated step and checking for a
clean success) as part of environment setup/preflight, with a fail-loud, actionable error
message (which package to install) rather than a generic binary-not-found or segfault deep
inside a pipeline.

**Warning signs:**
Immediate, total failure of every NMRPipe invocation on an apparently-correct install — easy to
misdiagnose as an install-path or environment-sourcing problem instead of a missing OS-level
dependency.

**Phase to address:** Cross-platform portability phase.

---

### Pitfall 14: Silent subprocess failures inside chained backend pipelines

**What goes wrong:**
NMRPipe (and similarly, mddnmr/hmsIST) pipelines are built from chains of `|`-piped C binaries
inside `csh`/`tcsh` scripts. A failure partway through — a missing binary, a malformed flag, an
out-of-memory kill — can leave a truncated, empty, or all-zero output file that the *next*
stage in the same script reads without complaint. Because the file exists and is
format-valid-but-empty, ordinary Python file-existence checks (`os.path.exists`) pass, and the
downstream stage (FT, phasing, peak picking) can silently proceed to "successfully" pick zero
or garbage peaks from empty data — a failure mode indistinguishable, from a JSON-output
perspective, from "legitimately no peaks found."

**Why it happens:**
`csh` pipe semantics don't propagate exit codes the way `bash -o pipefail` does, and none of
these tools were designed to be driven unattended — every processing example assumes a human
watching terminal output between steps.

**How to avoid:**
Every external-tool invocation from lucy-ng (conversion, expansion, reconstruction, FT,
phasing, peak picking) must be wrapped in a helper that checks both the process return code
*and* an independent output-file sanity check (non-empty, expected byte size derivable from the
known point-count × dtype-size, or a non-all-zero spot-check) before the pipeline is allowed to
continue — fail loud with the offending stage name and captured stderr, never silently pass an
empty/garbage file forward.

**Warning signs:**
A pipeline stage that "succeeds" (exit 0) in implausibly short time, or a peak-picking stage
reporting zero peaks on an experiment where the reliable 1D reference implies dozens should
exist.

**Phase to address:** Cross-platform portability phase (owns the shared fail-loud subprocess
wrapper every other phase's external-tool calls must use) + reconstruction/processing phase
(applies it to every NMRPipe/SMILE/IST invocation).

---

### Pitfall 15: Non-reproducible reconstruction runs

**What goes wrong:**
`NusSEED=54321` (verified present in this dataset) pins the *acquisition-time* schedule
generation, but that is unrelated to any internal randomness in the *reconstruction* algorithm
itself — some CS/IST solver implementations use randomized initialization or
thread-parallelized L1 solvers whose floating-point summation order (and therefore exact
output) is not guaranteed identical run-to-run. A CASE re-run triggered mid-debugging that
silently produces a *different* peak list than the first run (different fabricated-peak
positions, different weak-peak recovery) is confusing and hard to diagnose without a human
comparing plots side by side — especially dangerous combined with Pitfall 7's fabricated-peak
risk, since "did the peak list change because of a real bug fix, or because of solver
non-determinism" becomes an open question.

**Why it happens:**
Automated, unattended pipelines are exactly the context where non-determinism goes unnoticed
longest — nobody is watching each run's plot by eye to catch drift.

**How to avoid:**
Pin/document any reconstruction-side random seed and thread count the chosen backend exposes;
if the backend offers no seed control, record backend version + exact parameters used
per run in the run's provenance metadata (this project's existing pattern: `.run_manifest.json`
from the v9.2/v9.3 webview work) so at least a change in output can be attributed to a
specific, logged configuration change.

**Warning signs:**
Two runs of the identical conversion pipeline on identical input producing different peak
counts/positions beyond floating-point-noise-level differences.

**Phase to address:** Reconstruction/processing phase; provenance logging follows the existing
`.run_manifest.json` convention.

---

### Pitfall 16: No QC gate between reconstruction and CASE handoff (the crux risk, restated as a pipeline-design pitfall)

**What goes wrong:**
Even with every pitfall above individually addressed, a pipeline that pipes reconstruction
output straight into `lucy pick hsqc/hmbc/cosy` and then straight into a CASE run has no place
where a human *would have* looked and said "wait, that doesn't look right" — the entire value
of the GUI-based workflow this milestone explicitly removes. Without a dedicated, structured QC
stage, any of Pitfalls 1–10 that produces a "looks complete" but subtly wrong spectrum flows
undetected all the way to `lsd-engineer` treating a fabricated or mis-positioned correlation as
a hard generation constraint.

**Why it happens:**
It's tempting to treat "peak picking" as the terminal step of reconstruction and "QC" as
something that happens informally during development, rather than as its own explicit,
always-run, machine-checked pipeline stage with a pass/fail exit status the CASE orchestrator
respects.

**How to avoid:**
Build a QC gate as its own pipeline stage, run automatically after every reconstruction and
before any peak list is considered eligible for a CASE run, checking (at minimum, each mapped
to the specific project ground truth already established in NUS-RECONSTRUCTION-GUIDE.md §8/§10):
1. **Protonated-carbon coverage:** every protonated ¹³C from the reliable 1D list shows exactly
   one (CH/CH3) or two diastereotopic (CH2) HSQC correlations; every confirmed-quaternary
   carbon (79.35, 36.23, 142.00, 135.86, and the MEDIUM-confidence 37.86 candidate) shows
   **zero** one-bond correlations — a direct, automatable violation check.
2. **Edited-HSQC sign self-consistency:** signs cluster into exactly two classes matching known
   DEPT CH/CH3 vs CH2 assignments (Pitfall 10).
3. **COSY diagonal symmetry:** real H–H correlations must be symmetric about the diagonal within
   picking tolerance (Pitfall 5).
4. **Held-out cross-validation:** reconstruction correctly predicts a reserved fraction of
   actually-sampled points not used during reconstruction (Pitfall 7).
5. **ppm calibration cross-check** against the §10 ground-truth 20-shift ¹³C list (Pitfall 6).
6. **Signal-to-ridge ratio** materially better than the previous ad-hoc reconstruction's own
   documented artifact level (the guide's own §8 "Quick-Check" criterion) — i.e. a regression
   test against the *known-bad* baseline, not just an absolute threshold.
Emit a structured, machine-readable pass/fail report (JSON, per this project's CLI convention)
alongside the peak lists; the CASE orchestrator must refuse to start a run when the QC report is
FAIL, exactly as it already fails loud on other precondition problems elsewhere in the
pipeline (e.g. outlsd) — and every peak, pass or fail, should carry a persisted confidence flag
so `lsd-engineer`/devils-advocate can treat low-confidence, reconstruction-only correlations as
soft hints, extending the existing v9.0 constraint-hardness-guard (FIX-10) to this new data
source.

**Warning signs:**
A "reconstruction succeeded" status with no accompanying QC artifact at all — that absence is
itself the warning sign to design against.

**Phase to address:** A dedicated peak-picking/QC-gate phase, positioned as its own pipeline
stage between reconstruction/processing and the existing `lucy pick`/CASE handoff — not folded
into either.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|--------------------|-----------------|------------------|
| Hard-coding one experiment's FnMODE/TD relationship for all NUS conversions | Faster to get first experiment (e.g. HSQC) working | Silently wrong for the other FnMODE in the *same milestone's own dataset* (verified: exp2 QF vs exp3/4 Echo-AntiEcho) | Never — this milestone's own test data already exercises both cases |
| Fixed iteration count instead of residual-based stopping for IST/CS reconstruction | Simple, deterministic runtime budget | Under-converges on some datasets (residual ridges) and over-converges on others (fabricated noise-peaks) — the exact CASE-false-connectivity risk (Pitfall 7) | Acceptable only as a conservative *upper bound* alongside a real convergence check, never as the sole stopping rule |
| Skipping the held-out cross-validation reconstruction check to save runtime | Faster dev iteration | No detection of fabricated/missing peaks before they reach LSD | Acceptable only in exploratory/manual dev runs; never in the shipped automated pipeline |
| Locking the pipeline to a single reconstruction backend (e.g. SMILE only) | Less abstraction/adapter work | The project's own guide (§7) already anticipates needing a fallback (hmsIST/mddnmr) when SMILE leaves ridges at 25% sampling on this compound | Acceptable only if the parallel stack-selection research firmly rules out ever needing a fallback (unlikely) |
| Reusing NMRPipe's default install-script behavior (writes to `.cshrc`, system paths) unmodified in an automated/CI environment | Fast setup | Non-reproducible across machines/OS, and modifies user shell config from an unattended process | Never for a "must run unattended, cross-platform" milestone — containerize or use a local, explicit prefix instead |
| Treating "peak picking succeeded" as equivalent to "reconstruction was correct" | Simpler pipeline, one fewer stage | No detection point for fabricated/missing peaks before CASE handoff (Pitfall 16) | Never — this is the specific gap this milestone must close, not carry forward |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|-----------------|--------------------|
| NMRPipe | Assuming it's pip/conda-installable | Requires free registration + manual `install.com` run + csh/tcsh environment; verify with an explicit preflight (`nmrPipe -help`, `smileNus -help`, `nusExpand.tcl -help` per the project's own guide §5) before every automated run, not just once at setup |
| Bruker `nuslist`/`acqus`/`acqu2s` | Assuming one universal schedule format/indexing across pulse programs | Derive expected schedule length and real/complex pairing from `FnMODE` + `TD` programmatically per experiment; assert against `len(nuslist)` before running anything (Pitfall 1) |
| hmsIST / mddnmr (fallback backends) | Assuming they share NMRPipe+SMILE's exact CLI/schedule conventions | Treat each backend as its own adapter with its own conversion tests — do not reuse the SMILE converter's assumptions unverified (LOW confidence on mddnmr's exact schedule indexing convention from this research pass — flag for phase-specific validation) |
| TopSpin Python API | Assuming it can run fully headless with no TopSpin/license present | Requires a live, licensed TopSpin instance exposing an embedded web service; treat as the human/GUI fallback path only (per the project's own guide §6), not part of the automated pipeline |
| nmrglue | Assuming it provides native NUS reconstruction | It is I/O-only for Bruker data; the actual sparse-recovery algorithm (SMILE/IST/MDD) must come from an external backend — this is exactly what the prior ad-hoc "per-column IST in nmrglue" got wrong (an improvised, non-standard algorithm, not a real CS/IST/SMILE implementation) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Naive full-grid zero-fill of the sparse F1 dimension before reconstruction (what the failed 2026-07-09 run did) | "Completes," produces a spectrum, but leaves t1-ridge artifacts | Use proper NUS-aware sparse expansion + mask (e.g. `nusExpand.tcl`-style) so the algorithm knows which points are real vs to-be-recovered | Breaks as soon as F1 sparsity is significant — all three of this project's experiments are 67–75% sparse |
| Fixed large iteration count applied uniformly regardless of dataset size/sparsity | Multi-hour reconstruction runtime (the 2026-07-09 CASE run already took 5.5h end-to-end) | Residual-based early stopping (Pitfall 7) | Becomes routine cost once this pipeline is "reusable by any NUS CASE run" (explicit PROJECT.md goal), not a one-off |
| Monolithic unattended script (conversion + reconstruction + phasing + picking) with no intermediate caching | Any single downstream bug (e.g. a bad peak-pick threshold) forces re-running the slow CS reconstruction step too | Persist/version intermediate NMRPipe-format spectra so QC/re-picking iteration doesn't re-pay reconstruction cost | Breaks once the pipeline is used repeatedly across compounds/iterations, not just once on C20H32O2 |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Piping NMRPipe/mddnmr install scripts directly into a shell without pinning a version/checksum | Non-reproducible or tampered installs across dev machines/CI/agents | Vendor/pin exact tarball versions with checksums; document install provenance in the portability matrix |
| Letting an automated install step modify system-wide shell config (`.cshrc`, global `PATH`) | Unintended side effects on the host running the agent, harder to reproduce/tear down | Contain install inside a Docker image or a fully user-local prefix; never let an unattended agent edit system-wide shell config |
| Baking the one-time NMRPipe registration/download step into the per-run "fully automatic" pipeline | A run silently blocks mid-pipeline waiting on a manual registration email/step that has nothing to do with actual NUS reconstruction | Do the registration + download once, during documented environment bootstrap, never inside the per-compound automated run |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|---------------|-------------------|
| Silent partial success — pipeline reports "done" after producing an empty/garbage intermediate spectrum | CASE proceeds for hours on garbage data before the failure is noticed (exactly what happened 2026-07-09) | Fail loud + structured JSON status at every pipeline stage, matching this repo's existing `--format json` CLI convention |
| No visibility into reconstruction quality until CASE convergence (or non-convergence) hours later | The only signal of a bad reconstruction is an entire wasted multi-hour CASE run | Emit a machine-readable QC report (peak-recovery/residual/symmetry/§10-cross-check metrics) immediately after reconstruction, before CASE is even allowed to start |
| Cross-platform gaps discovered only at run time, mid-pipeline | An agent kicks off a multi-hour run on Windows/Linux only to fail at step 2 for a missing csh/32-bit-lib dependency | A `lucy nus check`-style preflight command (analogous to the existing `lucy lsd check`) verifying backend availability before starting any real work |

## "Looks Done But Isn't" Checklist

- [ ] **Reconstructed spectrum:** Often missing digital-filter removal or uses the wrong
      `GRPDLY` handling path — verify F2 lineshape/ppm calibration matches the reliable 1D
      reference exactly, not just "roughly."
- [ ] **Peak-list JSON:** Often missing a per-peak QC/confidence flag distinguishing
      well-supported cross peaks from reconstruction-only, low-confidence ones — verify every
      entry carries a QC status, not just `{c13_ppm, h1_ppm}`.
- [ ] **"Fully automated" pipeline:** Often still has one hidden manual step (registration
      download, license acceptance, or a human eyeballing a plot before picking) — verify a
      true unattended re-run from raw `ser` to JSON with zero manual steps, on a clean
      environment.
- [ ] **Cross-platform support:** Often only ever exercised on the developer's own machine
      (macOS Apple Silicon) — verify an actual run (or a deliberately documented gap in the
      portability matrix) on Linux and Windows, not just "should work."
- [ ] **Phase correction:** Often "good enough by eye" during development but never re-verified
      headlessly afterward — verify an automated phase-QC metric threshold is enforced in the
      pipeline itself, not just checked once by a human during development.
- [ ] **QC gate:** Often implemented as a post-hoc visual sanity check the developer ran once,
      not a real automated gate the CASE orchestrator can refuse to proceed past — verify it
      is a hard, machine-checked precondition for starting a CASE run, not documentation.
- [ ] **Subprocess wrapping:** Often only checks process exit code — verify every external-tool
      call also validates output-file size/non-emptiness (Pitfall 14).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|------------------|
| Wrong nuslist indexing/pairing assumption (Pitfalls 1–2) | MEDIUM | Fix the conversion step only (not the full multi-hour reconstruction); add a regression test using this project's own three `nuslist` fixtures (verified unsorted/acquisition-order) to prevent recurrence |
| Fabricated cross-peaks reached LSD/CASE undetected (Pitfalls 7, 16) | HIGH | Full CASE re-run required with corrected, QC-gated peak lists — an entire multi-hour CASE run wasted, exactly as already happened 2026-07-09. Reinforces that the QC gate must sit *before* CASE handoff, never be discovered only after a failed CASE run |
| Wrong ppm calibration (Pitfall 6) | LOW–MEDIUM | If purely an axis-mapping bug downstream of a correctly-processed spectrum, recalibrate and re-pick without rerunning reconstruction; if the wrong `SW_h`/`O1` was baked into the conversion step itself, redo from `bruk2pipe` (cheap relative to reconstruction) |
| Cross-platform backend unavailable at runtime (Pitfalls 11–13) | LOW | Preflight check catches this before any real work starts; documented fallback path (alternate backend, or the TopSpin GUI human path per guide §6) rather than a silent hang |
| Non-reproducible reconstruction output between runs (Pitfall 15) | LOW–MEDIUM | Compare against logged run provenance (`.run_manifest.json`-style); rerun with pinned seed/thread count if the backend supports it, otherwise document as an accepted non-determinism with wider QC tolerance |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|--------------------|-----------------|
| 1. FnMODE→TD/nuslist-length relationship assumed uniform | Bruker→backend conversion | Automated assertion `n_sampled == len(nuslist)` per experiment, tested against all three real FnMODEs (1, 6, 6) in this project's own data |
| 2. nuslist index base / acquisition-order sorting | Bruker→backend conversion | Regression test using this project's own three (unsorted, acquisition-order) `nuslist` files as fixtures |
| 3. GRPDLY digital-filter removal | Bruker→backend conversion | F2 projection of every converted experiment compared against its own reliable 1D reference (exp1/6/7) |
| 4. Byte order / dtype mis-assumption | Bruker→backend conversion | Same F2-vs-1D-reference sanity check as above; read `BYTORDA`/`DTYPA` per-experiment, never hard-coded |
| 5. FnMODE-specific F1 processing (QF vs Echo-AntiEcho) | Bruker→backend conversion + reconstruction/processing | COSY diagonal-symmetry check; HSQC/HMBC ppm-range sanity vs known ¹³C range |
| 6. ppm axis correctness (SFO1/SW_h/O1) | Bruker→backend conversion + peak-picking/QC gate | Reconstructed ¹³C shift list cross-checked against the §10 ground-truth 20-shift list |
| 7. Fabricated/missing cross peaks (over/under-iteration) | Reconstruction/processing + peak-picking/QC gate | Held-out sampled-point cross-validation; §10 ground-truth violation check (e.g. no 1-bond correlation may appear at a confirmed-quaternary shift) |
| 8. Virtual-echo / causal-signal construction skipped | Reconstruction/processing | Peak-splitting check against known DEPT multiplicity pattern |
| 9. 25–33% sampling near reliability floor for weak/long-range peaks | Reconstruction/processing + peak-picking/QC gate | Weak-HMBC-recovery check via held-out cross-validation; conservative default parameters for HMBC specifically |
| 10. Auto-phase failure, no human fallback | Reconstruction/processing + peak-picking/QC gate | Automated phase-QC metric (dispersive-fraction threshold) + edited-HSQC sign self-consistency vs 1D DEPT |
| 11. NMRPipe on Apple Silicon / Rosetta | Cross-platform portability | Preflight `arch -x86_64 nmrPipe -help`; fail-loud subprocess wrapper checking exit code + output file size on every external call |
| 12. Windows has no csh/tcsh | Cross-platform portability | Documented portability matrix entry (WSL2 / Docker / Python-native fallback), preflight check before any Windows run starts |
| 13. Linux missing 32-bit libraries | Cross-platform portability | Preflight `nmrPipe -help` smoke test with actionable error message on failure |
| 14. Silent subprocess failures in chained pipelines | Cross-platform portability (shared wrapper) + reconstruction/processing (applies it) | Every external call checked for exit code AND output-file size/non-emptiness; zero-peak results on data with a known-nonzero 1D reference treated as a hard failure, not an empty result |
| 15. Non-reproducible reconstruction runs | Reconstruction/processing | Seed/thread-count pinned where the backend supports it; run provenance logged in `.run_manifest.json`-style metadata |
| 16. No structured QC gate before CASE handoff (crux risk) | Dedicated peak-picking/QC-gate phase (own stage, not folded into peak-picking) | CASE orchestrator refuses to start a run when the QC gate report is FAIL; per-peak confidence flag threaded through to `lsd-engineer`/devils-advocate, extending the existing v9.0 constraint-hardness-guard (FIX-10) to reconstruction-derived peaks |

## Sources

- Direct inspection of this project's own `acqus`/`acqu2s`/`nuslist` files for
  `C20H32O2` experiments 2/3/4, 2026-07-12 (HIGH confidence — primary data, not a claim from
  a third party).
- This project's own task brief: `analysis/NUS-RECONSTRUCTION-GUIDE.md` under
  `~/Dropbox/develop/data/nmrdata/active-lucy-ng-testprojects/C20H32O2/` (documenting the
  2026-07-09 CASE failure root cause and the §8/§10 verification criteria) — HIGH confidence,
  primary project source.
- Non-Uniform Sampling (NUS) in NMRPipe, IBBR/UMD official docs — https://www.ibbr.umd.edu/nmrpipe/nus.html (MEDIUM confidence; fetched via search snippet, page itself returned 404 on direct fetch at research time — re-verify URL during implementation)
- Powers Wiki, Non-Uniform Sampling — https://bionmr.unl.edu/mediawiki/index.php/Non-Uniform_Sampling (MEDIUM confidence; community wiki, but specific and consistent with official docs — source of the "NEVER click Calculate/Show table" TopSpin schedule-corruption warning and the TD-counts-real-points clarification)
- Kazimierczuk et al. (and related), "Pitfalls in compressed sensing reconstruction and how to avoid them," *J. Biomol. NMR* — https://pmc.ncbi.nlm.nih.gov/articles/PMC5504175/ (HIGH confidence; peer-reviewed methods paper, the primary source for the fabricated-noise-peak, m∝K·log(n/K), high-dynamic-range, and virtual-echo/peak-splitting pitfalls)
- NUScon: a community-driven platform for quantitative evaluation of nonuniform sampling in NMR — https://mr.copernicus.org/articles/2/843/2021/ (HIGH confidence; peer-reviewed, the primary source for the recommended QC metrics — frequency accuracy, intensity linearity, true/false positive rate — adapted into this project's QC-gate design)
- nmrglue documentation, `remove_digital_filter`/`rm_dig_filter` — https://nmrglue.readthedocs.io/en/latest/reference/generated/nmrglue.fileio.bruker.remove_digital_filter.html and https://github.com/jjhelmus/nmrglue/issues/24 (HIGH confidence; official docs of a library already used in this codebase, referencing the underlying Westler & Abildgaard DMX digital-filter protocol)
- SMILE (Sparse Multidimensional Iterative Lineshape-Enhanced) NUS reconstruction, NIH/Bax lab — https://spin.niddk.nih.gov/bax/software/smile/ (MEDIUM confidence; official tool page/manual referenced but the manual PDF could not be parsed in this research pass — re-fetch during backend-integration phase for exact `-EA`/iteration-flag syntax)
- mddNMR user manual v2.7 — http://mddnmr.spektrino.com/man (LOW-MEDIUM confidence; not independently verified for exact schedule-indexing convention in this pass, flagged for phase-specific validation)
- Comparison of NUS processing programs, mddNMR project — http://mddnmr.spektrino.com/comparisons (MEDIUM confidence; vendor-authored comparison, cited only for the general SMILE-vs-IST-vs-MDD tradeoff framing, treat as directional not definitive)
- Processing 2D/3D/4D Spectra with hmsIST, Wagner Lab, Harvard — http://gwagner.med.harvard.edu/intranet/hmsIST/234Proc.html and istHMS equivalent (MEDIUM confidence; official tool docs, source of the "Virtual Echo + CS-IST default mddnmr parameters" note)
- NMRPipe install notes (C-shell requirement, 32-bit library requirement on Linux) — via Miami University/Wyoming HPC install guides surfaced in search (MEDIUM confidence; multiple independent institutional install guides agreeing on the same csh/32-bit-library requirements)
- `tlinnet/docker_relax`, `Dockerfile_04_NMRPipe_MddNMR` — https://github.com/tlinnet/docker_relax/blob/master/Dockerfile_04_NMRPipe_MddNMR (MEDIUM confidence; working reference implementation of containerized NMRPipe+mddnmr, evidence that a Docker-based cross-platform strategy is viable, not independently rebuilt/tested in this research pass)
- Bruker TopSpin Python 3 interface — https://www.bruker.com/en/products-and-solutions/mr/nmr-software/topspin/topspin-python-interface.html (MEDIUM confidence; official product page, confirms network-based headless automation is possible but requires a live licensed TopSpin instance — supports treating TopSpin as the human/GUI fallback only, per this project's own guide §6)
- Bruker `FnMODE` parameter reference (QF/QSEQ/TPPI/States/States-TPPI/Echo-AntiEcho) — http://rmni.iqfr.csic.es/guide/man/acqref/fnmode.htm (MEDIUM confidence; third-party mirror of Bruker TopSpin parameter reference documentation, cross-checked against this project's own verified `FnMODE=1`/`FnMODE=6` values)
- This project's own decision history: v9.0 constraint-hardness guard FIX-10 (`.planning/PROJECT.md` Key Decisions table) — HIGH confidence, primary project source, the direct precedent this research recommends extending to reconstruction-derived peaks.

---
*Pitfalls research for: Automatic Bruker NUS 2D reconstruction (lucy-ng v10.0)*
*Researched: 2026-07-12*
