---
phase: 103-end-to-end-validation-c20h32o2-jcamp
reviewed: 2026-07-28T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - src/lucy_ng/readers/jcamp.py
  - src/lucy_ng/cli/jcamp.py
  - tests/readers/test_jcamp.py
  - tests/test_cli_jcamp.py
findings:
  critical: 3
  warning: 12
  info: 4
  total: 19
status: issues_found
---

# Phase 103: Code Review Report

**Reviewed:** 2026-07-28
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 103 changed two source files: a one-line widening of the 13C ppm plausibility
ceiling (`readers/jcamp.py`, 230.0 -> 250.0) and a new repeatable `KEY=value` knob
layer in `cli/jcamp.py` (`--threshold` / `--snr-floor`, module-level
`_parse_keyed_option`, four bridge call sites). The 51 tests in the two test files
pass, `ruff` is clean, and `mypy` reports no new errors in either source file.

What is genuinely correct: all four bridge call sites (1D staging, 2D staging, FAIL
rebuild, PASS/PARTIAL rebuild) do receive both knobs — verified live by spying on
`bridge_peak_pick`/`bridge_peak_pick_1d` during a real fixture run (6 x 2D calls =
3 staging + 3 rebuild, each carrying the resolved `(threshold, snr_floor)` triple;
2 x 1D calls likewise). Key normalization (`.strip().upper()`) works for both
experiment and nucleus keys, unrecognized keys do exit non-zero, and the QC gate is
still invoked exactly once.

What is not correct: the parser has a proven **silent-ignore precedence hole** — a
*bare* `--threshold` silently discards every *keyed* `--snr-floor`, because
`bridge_peak_pick` decides mode via `use_snr = threshold is None` and the ambiguity
guard only compares keyed-vs-keyed. Separately, the pre-existing STEP 2.5 output
purge is a live data-loss path: it deletes pre-existing `HSQC.json`/`13C.json`/…
from a user-supplied `--out` directory *before* any input is read, so a run in which
every input fails still destroys prior results and writes nothing; and an `--out`
directory literally named `jcamp_ingest` is `rmtree`d wholesale, unrelated files
included. Both were reproduced against the committed fixtures.

On the reader: the widened ceiling is *necessary* (the real HMBC window is real), but
the new comment's justification for why the guard "remains meaningful" is unsound.
`_ppm_scale` always returns `scale[0] == offset_ppm` verbatim from the file, so
`scale.max() <= hi` never tests the computed math at all — only `lo <= scale.min()`
does, and only for divisor-too-*small* errors. A divisor-too-*large* error (SF taken
in Hz instead of MHz, or the wrong dimension's SF) collapses the axis to near-zero
width and passes the guard cleanly.

Test-layer honesty is uneven: two assertions in the new knob suite are provably
vacuous (they cannot fail on the outcome they claim to pin), and the precedence hole
above has no test at all.

## Critical Issues

### CR-01: A bare `--threshold` silently discards every keyed `--snr-floor`

**File:** `src/lucy_ng/cli/jcamp.py:228-242` (guard at 228-236, resolvers at 238-242)

**Issue:** The mutual-exclusion guard only rejects a *keyed* threshold colliding with
a *keyed* snr-floor (`set(threshold_by_exp) & set(snr_by_exp)`). A **bare**
`--threshold` is invisible to it, yet `_resolved_threshold(name)` falls back to
`threshold_bare` for *every* experiment, and `nus/bridge.py:343` selects mode with
`use_snr = threshold is None`. An explicitly keyed `--snr-floor` for that experiment
is therefore accepted, forwarded, and then ignored by the picker — with no warning
and exit code 0/1 as if honoured.

Reproduced live against the committed fixtures:

```
$ lucy jcamp <dir> --threshold 0.02 --snr-floor cosy=7
recorded 2D bridge calls:
  ('COSY', 0.02, 7.0)   <-- threshold wins; snr_floor=7.0 silently dead
  ('HMBC', 0.02, 5.0)
  ('HSQC', 0.02, 5.0)
```

This is exactly the failure class the phase brief says must not exist ("unrecognized
experiment keys must exit non-zero, not be silently ignored") — here a *recognized*
key is silently ignored, which is worse, because the user gets no signal at all. The
same hole exists for bare-vs-bare (`--threshold 0.02 --snr-floor 7`: the snr-floor is
dead everywhere).

**Fix:** Make the guard test the *resolved* mode, not just the keyed sets:

```python
# after _resolved_threshold/_resolved_snr_floor are defined
shadowed = sorted(
    name for name in snr_by_exp if _resolved_threshold(name) is not None
)
if shadowed:
    raise click.BadParameter(
        f"--snr-floor was given for {', '.join(shadowed)}, but a --threshold "
        "(bare or keyed) also applies there; --threshold switches that "
        "experiment to fraction-of-max mode, so the --snr-floor would be "
        "silently ignored. Scope the --threshold with KEY=value, or drop the "
        "--snr-floor for those experiments."
    )
if threshold_bare is not None and snr_bare_was_given:
    raise click.BadParameter(... same reasoning for the bare/bare case ...)
```

(`snr_bare_was_given` must be tracked separately from the 5.0 default, i.e. keep the
raw `None` from `_parse_keyed_option` before applying the default at line 226.)

### CR-02: `--out` purge destroys pre-existing peak files before any input is read

**File:** `src/lucy_ng/cli/jcamp.py:299-306`

**Issue:** STEP 2.5 unlinks the closed set `HSQC.json`/`HMBC.json`/`COSY.json`/
`1H.json`/`13C.json` from `out_root` *before* STEP 3 reads a single file. Those exact
filenames and schema are also what `lucy nus pipeline` writes, so pointing `--out` at
an existing `analysis/nmr_peaks/` directory destroys the previous (possibly
PASS-graded, possibly NUS-derived) results even when this run produces nothing at
all. Reproduced:

```
out/ before:  HSQC.json (from `lucy nus pipeline`), 13C.json, unrelated.txt
$ lucy jcamp <dir-containing-only-a-malformed-.dx> --out out/
exit: 1
HSQC.json still there? False
13C.json  still there? False
unrelated.txt still there? True
```

Nothing was written, one file failed to read, and the user's prior results are gone.
The design comment argues the purge is needed so a FAIL run leaves `out_root` absent —
but that invariant only needs to hold once a verdict exists, not before reading.

**Fix:** Move the `out_root` half of STEP 2.5 to after the STEP 4 "nothing staged"
bail-out (the `work_root` `rmtree` can stay where it is, since staging writes there):

```python
# STEP 4 (unchanged bail-out) ...
if not staged_2d and not staged_1d:
    ...
    raise SystemExit(1)

# STEP 4.5 -- only now is it safe to invalidate prior consumable output
if out_root.is_dir():
    for own_name in (*SUPPORTED_2D, *SUPPORTED_1D):
        (out_root / f"{own_name}.json").unlink(missing_ok=True)
    try:
        out_root.rmdir()
    except OSError:
        pass
```

Optionally also refuse to purge a file whose `source.format` is not `"JCAMP-DX"`, so
foreign output in a shared directory is never this command's to delete.

### CR-03: `--out <…>/jcamp_ingest` silently `rmtree`s the entire user-specified directory

**File:** `src/lucy_ng/cli/jcamp.py:273` and `:299`

**Issue:** `work_root = out_root.parent / "jcamp_ingest"` is derived, not validated.
If the caller passes `--out /some/where/jcamp_ingest`, then `work_root == out_root`
and line 299's `shutil.rmtree(work_root, ignore_errors=True)` deletes the whole
user-named output directory — including files this command does not own and would
never have written. Reproduced:

```
$ mkdir -p x/jcamp_ingest && echo "do not delete" > x/jcamp_ingest/my_important_notes.txt
$ lucy jcamp <dir> --out x/jcamp_ingest
exit: 1
unrelated file survived? False
```

The same collision also breaks the documented D-07 invariant: after a FAIL run the
directory still exists, now containing `staged/` and `qc_failed/` plus their
verdict-less JSON (verified: `out_root` present with `staged/HSQC.json` etc.).

**Fix:** Fail loud on the collision before any deletion:

```python
work_root = out_root.parent / "jcamp_ingest"
if work_root == out_root or work_root in out_root.parents or out_root in work_root.parents:
    raise click.BadParameter(
        f"--out {out_root} collides with the derived working directory "
        f"{work_root}; choose a different output directory."
    )
```

## Warnings

### WR-01: `_parse_keyed_option` accepts `nan`, `inf` and negative values

**File:** `src/lucy_ng/cli/jcamp.py:85-97`

**Issue:** The only validation is `float()`, which happily returns `nan`/`inf`.
Verified: `_parse_keyed_option(("hsqc=nan","hmbc=-3","cosy=inf"), …)` returns
`{'HSQC': nan, 'HMBC': -3.0, 'COSY': inf}`, and `--snr-floor nan` yields
`bare = nan`. A `nan` snr-floor makes every downstream comparison `False` (silently
picking nothing or everything, depending on the picker's comparison direction), and a
negative fraction-of-max threshold is meaningless. All of it lands in the QC-graded
output with no diagnostic.

**Fix:**

```python
import math
value = float(value_raw)
if not math.isfinite(value) or value <= 0.0:
    raise click.BadParameter(
        f"{option_name} value must be a finite positive number, got {value_raw!r}"
    )
```

Apply to both the keyed and the bare branch.

### WR-02: Repeated keys silently last-wins while unrecognized keys fail loud

**File:** `src/lucy_ng/cli/jcamp.py:85` (`by_key[key] = float(value_raw)`)

**Issue:** The docstring's fail-loud, never-first-match posture is applied only to
unknown keys. `--threshold hsqc=0.01 --threshold HSQC=0.99` silently keeps `0.99`
(verified: returns `{'HSQC': 0.99}`), which is precisely the shape of a copy-paste
mistake in a long knob-matrix invocation — the kind Phase 103's own validation runs
use. Silently discarding one of two explicit user requests contradicts the stated
design.

**Fix:**

```python
if key in by_key:
    raise click.BadParameter(
        f"{option_name} given more than once for key {key!r} "
        f"({by_key[key]} then {value_raw}) -- give it at most once"
    )
```

### WR-03: Bare knobs silently reconfigure the 1D reference lists the QC gate trusts

**File:** `src/lucy_ng/cli/jcamp.py:337-341`, help text at `:143-154`

**Issue:** A bare `--threshold 0.02`, which a user will reach for to tune 2D picking,
is also applied to the 1D 1H/13C picks (verified: 1D calls recorded
`('13C', 0.02, 5.0)` and `('1H', 0.02, 5.0)`). That flips `bridge_peak_pick_1d` out
of SNR mode (`use_snr = threshold is None`), sets `snr_floor_used: null`, and thereby
changes the *trusted 1D reference* against which `hsqc_coverage` and `ppm_calibration`
are graded. The verdict can move for a reason the user never intended. The
`--threshold` help text does not mention the 1D blast radius.

**Fix:** At minimum document it in the option help ("a bare value also re-picks the 1D
13C/1H reference lists the QC gate grades against"). Better: restrict bare values to
the 2D experiments and require an explicit `13C=`/`1H=` key to touch the reference
lists.

### WR-04: 1D pick/serialize failures abort the whole batch with a traceback

**File:** `src/lucy_ng/cli/jcamp.py:337-344` (1D), `:368-383` (2D)

**Issue:** Only `JcampReader.read()` is wrapped (`:317-323`). The documented contract
is "one bad file never aborts the batch and is never silently treated as clean", but
any exception from `bridge_peak_pick_1d` or `write_peak_json` escapes and kills the
run with an unhandled traceback. Verified by injecting a failing 1D bridge: the CLI
surfaced `RuntimeError('picker exploded')` instead of a named `failed` entry. The 2D
path is narrower than it looks too — it catches only `ValueError`, so a picker
`IndexError`/`ZeroDivisionError` on one odd spectrum takes down the batch.

**Fix:** Wrap both pick/write blocks the same way the read is wrapped:

```python
try:
    payload = bridge_peak_pick_1d(spectrum, threshold=..., snr_floor=...)
    payload["source"] = _source_block(path)
    write_peak_json(staged_dir, nucleus, payload)
except (ValueError, OSError, KeyError, IndexError, ArithmeticError) as exc:
    failed.append({"file": path.name, "error": f"1D pick failed: {exc}"})
    click.echo(f"Warning: failed to pick {path.name}: {exc}", err=True)
    continue
```

### WR-05: `rmtree(..., ignore_errors=True)` can silently fail to clear stale state

**File:** `src/lucy_ng/cli/jcamp.py:299`

**Issue:** The purge exists specifically to fix Phase 102's CR-01 (stale staged JSON
polluting `run_qc_checks`'s directory-wide glob). `ignore_errors=True` means a
permission error, a busy NFS handle, or a read-only mount leaves the stale files in
place *and* produces no message — the exact bug re-appears silently, and the run still
reports a verdict as if the staged set were clean.

**Fix:** Drop `ignore_errors` and translate a real failure into a fatal, named error:

```python
try:
    shutil.rmtree(work_root)
except FileNotFoundError:
    pass
except OSError as exc:
    raise click.ClickException(
        f"could not clear stale working directory {work_root}: {exc}"
    ) from exc
```

### WR-06: The plausibility guard's upper bound tests a file field, not the computed axis

**File:** `src/lucy_ng/readers/jcamp.py:166-171` (with `_ppm_scale` at `:145-146`)

**Issue:** `_ppm_scale` returns `np.linspace(offset_ppm, offset_ppm - sw_hz/sf, n)`,
so `scale[0]` is *always* `$OFFSET` read verbatim from the file. Consequently
`scale.max() <= hi` only ever re-validates a field the file already states in ppm; it
can never detect a divisor error. Only `lo <= scale.min()` exercises the computed
half, and only in one direction — a divisor that is too *small* (no division at all:
`234.81 - 30091 = -29856`). A divisor that is too *large* is invisible:

- `$SF` taken in **Hz** instead of MHz (125 705 000): width becomes 0.00024 ppm, axis
  = `[234.8062 … 234.8060]` — inside `(-15, 250)`, still strictly descending, guard
  passes. Every peak then collapses onto one ppm value downstream.
- The **wrong dimension's** `$SF` (1H's 499.92 for a 13C axis): width 60.2 ppm instead
  of 239.4, axis `[174.6, 234.81]` — passes.

The second case is exactly the failure `_resolve_dim`'s `procs_index` convention
exists to prevent, so the coarse net provides no defence-in-depth for it.

**Fix:** Add a width check alongside the endpoint check, e.g.

```python
_PPM_WIDTH_BOUNDS: dict[str, tuple[float, float]] = {
    "1H": (0.5, 25.0), "13C": (5.0, 300.0),
}
width = float(scale[0] - scale[-1])
w_lo, w_hi = _PPM_WIDTH_BOUNDS.get(nucleus, (0.0, float("inf")))
if not (w_lo <= width <= w_hi):
    raise ValueError(
        f"Implausible {nucleus} ppm sweep width {width:.4f} ppm (expected "
        f"[{w_lo}, {w_hi}]) -- likely wrong Hz/frequency divisor or units"
    )
```

### WR-07: The new bound comment's rationale is factually wrong and contradicts the guard's own docstring

**File:** `src/lucy_ng/readers/jcamp.py:46-53`

**Issue:** The comment justifies 250.0 by saying it stays "far below the Hz-scale
magnitudes (~29,500) a genuine **SFO/SF-divisor bug** produces, so the guard remains
meaningful." Two errors:

1. An SFO-vs-SF divisor bug is a ~0.4 % (~0.447 ppm) error, not a 29 500-magnitude
   one — `_assert_plausible_ppm_axis`'s own docstring at `:151-157` states plainly
   that this guard "would NOT by itself catch the naive SFO-divisor bug". The comment
   asserts the opposite of the function it annotates.
2. The ~29 500 magnitude of a *forgot-to-divide* bug appears in the axis **minimum**
   (`offset - sw_hz`), never in the maximum (which is `$OFFSET`, see WR-06). The
   ceiling the comment is defending is not what catches that class; the floor is.

A future maintainer reading this comment will over-trust the guard.

**Fix:** Rewrite the comment to state what is true: the ceiling admits the real HMBC
`$OFFSET` anchor; the *floor* (`-15.0`) is what rejects an undivided Hz axis; and
neither bound detects a wrong-but-in-range divisor (that is the JC-02 1D cross-check's
job, plus WR-06's width check if adopted).

### WR-08: Unknown nuclei silently disable the fail-loud guard

**File:** `src/lucy_ng/readers/jcamp.py:60`, `:166`

**Issue:** `_PPM_PLAUSIBILITY_BOUNDS.get(nucleus, _PPM_PLAUSIBILITY_FALLBACK)` with a
fallback of `(-1e6, 1e6)` turns the guard into a no-op for any nucleus outside the
four-entry table — a real 19F/29Si dataset, or (more likely) a nucleus label that
`_clean_nucleus_label` fails to normalize (e.g. an unexpected wrapping producing
`"13C "` after an upstream change). A guard that silently switches itself off is the
same silent-failure class the module elsewhere refuses to accept.

**Fix:** Emit a visible warning when the fallback is used, so the degraded check is
observable:

```python
bounds = _PPM_PLAUSIBILITY_BOUNDS.get(nucleus)
if bounds is None:
    warnings.warn(
        f"No ppm plausibility bounds for nucleus {nucleus!r}; axis check degraded "
        "to a units-only sanity range",
        stacklevel=2,
    )
    bounds = _PPM_PLAUSIBILITY_FALLBACK
lo, hi = bounds
```

### WR-09: `test_keyed_threshold_with_bare_snr_floor_is_legal` cannot fail

**File:** `tests/test_cli_jcamp.py:895-905`

**Issue:** The only assertion is
`assert result.exception is None or isinstance(result.exception, SystemExit)`. Click
converts a `BadParameter` raised in the command body into `SystemExit(2)` under
`standalone_mode`, so the test passes just as happily when the combination is
*rejected*. Verified directly: invoking the deliberately illegal keyed/keyed pair
yields `exit_code=2, exception=SystemExit(2)`, and this test's assertion evaluates
`True`. It therefore pins nothing about "legal".

**Fix:**

```python
calls_2d, _ = self._spy_bridges(monkeypatch)
result = runner.invoke(jcamp, [str(tmp_path), "--threshold", "hsqc=0.02",
                              "--snr-floor", "5.0"])
assert result.exit_code in (0, 1), result.output   # never 2 (usage error)
assert self._by_experiment(calls_2d)["HSQC"] == {(0.02, 5.0)}
```

### WR-10: `assert "unrecognized key" not in result.output` is vacuous under `mix_stderr=False`

**File:** `tests/test_cli_jcamp.py:838`

**Issue:** With `CliRunner(mix_stderr=False)`, `result.output` is stdout only, while
click writes usage errors to stderr. Verified: for a genuinely rejected key, stdout is
`''`, so the substring can never appear — the assertion would pass even if
case-insensitive keys were being rejected outright. (The following `calls_2d`/
`calls_1d` assertions do carry the test, but this line contributes false assurance.)

**Fix:** Assert on the real channel, or drop the line:

```python
assert "unrecognized key" not in result.stderr
```

### WR-11: No test pins the bare-threshold / keyed-snr-floor precedence (CR-01)

**File:** `tests/test_cli_jcamp.py:680-943` (class `TestJcampKnobOptions`)

**Issue:** The suite covers bare-only, keyed-only, keyed-beats-bare-for-snr, keyed
both (ambiguous), and keyed-threshold + bare-snr. The one combination that is actually
broken — bare `--threshold` with keyed `--snr-floor` — is untested, which is why
CR-01 shipped. The mirror-image case is tested (`test_keyed_beats_bare_for_the_named_experiment`),
making the omission look accidental rather than deliberate.

**Fix:** Add the negative test alongside the CR-01 fix:

```python
def test_bare_threshold_with_keyed_snr_floor_is_rejected(self, tmp_path):
    _copy_fixtures(tmp_path)
    result = CliRunner().invoke(
        jcamp, [str(tmp_path), "--threshold", "0.02", "--snr-floor", "cosy=7"]
    )
    assert result.exit_code == 2
    assert "COSY" in result.output
```

### WR-12: The "staging and rebuild identically" test asserts a set, so a deleted rebuild call still passes

**File:** `tests/test_cli_jcamp.py:782-815` (assertions at 812-815); same pattern at `:751-766`

**Issue:** `_by_experiment` collapses calls into a `set`, so
`by_experiment["HSQC"] == {(0.01, 5.0)}` is satisfied by *one* call just as well as by
the two the docstring claims are proven ("the staging call and the … rebuild call for
the SAME experiment record the identical triple"). If a future refactor drops the
rebuild call site entirely — the exact regression this test names — it stays green.
(It does still catch a rebuild that passes *different* knobs.) Relatedly,
`test_bare_snr_floor_applies_to_every_experiment_backwards_compatible` guards
`calls_2d` with `assert calls_2d` but iterates `calls_1d` (`:764-766`) without the
same non-empty guard, so the 1D half of that test vacuously passes if the 1D bridge is
never invoked.

**Fix:** Assert the call count as well as the values:

```python
per_experiment = Counter(name for name, _, _ in calls_2d)
assert per_experiment["HSQC"] == 2, "expected one staging + one rebuild call"
assert by_experiment["HSQC"] == {(0.01, 5.0)}
...
assert calls_1d, "no 1D bridge calls recorded"
```

## Info

### IN-01: The raw-Hz negative control trips both bounds, so it cannot pin which one fired

**File:** `tests/readers/test_jcamp.py:78-79`

**Issue:** `np.array([29516.31, -574.76])` violates the ceiling *and* the floor, so
the test passes even if the ceiling check were removed — it does not isolate the
"forgot to divide by SF" mechanism it documents (which, per WR-06, is actually a
floor-side catch).

**Fix:** Use `pytest.raises(ValueError, match="Implausible 13C ppm axis")` and add a
control that only violates the floor (e.g. `[234.81, -29856.0]`, the real
undivided-axis shape) so the intended mechanism is the one being asserted.

### IN-02: The widened bound has no fixture-backed exercise

**File:** `tests/readers/test_jcamp.py:39-79`

**Issue:** Everything about the 230 -> 250 change is asserted against synthetic arrays.
No committed fixture produces an axis anywhere near 234.81 ppm (the trimmed HMBC
fixture's F1 axis is rebased to its 16-page window), so nothing proves the real
motivation — "the real HMBC file now reads" — inside CI. That is an accepted
consequence of the uncommitted dataset, but it should be stated in the test docstring
so a future reader does not assume real-data coverage exists.

**Fix:** Add one line to the class/test docstring recording that the real-data
evidence lives in `103-VALIDATION.md`, not in CI.

### IN-03: A missing `=` produces an unhelpful error message

**File:** `src/lucy_ng/cli/jcamp.py:91-97`

**Issue:** `--threshold hsqc` (user forgot the `=value`) falls into the bare branch and
reports `non-numeric value for --threshold: 'hsqc'`, which never mentions that
`hsqc` *is* a recognized key and that `KEY=value` was probably intended.

**Fix:** When the bare `float()` fails and `item.strip().upper()` is in `accepted`,
raise a targeted message: `"--threshold hsqc looks like a key without a value -- use --threshold hsqc=<number>"`.

### IN-04: Zero-length axis produces a cryptic numpy error

**File:** `src/lucy_ng/readers/jcamp.py:167`

**Issue:** `scale.min()` on an empty array raises
`ValueError: zero-size array to reduction operation minimum` — a `ValueError`, so it
propagates through `cli/jcamp.py`'s handler as a `failed` entry, but with a message
that says nothing about the JCAMP file being empty.

**Fix:** Guard at the top of `_assert_plausible_ppm_axis`:

```python
if scale.size == 0:
    raise ValueError(f"Empty {nucleus} ppm axis -- JCAMP-DX file has no data points")
```

---

_Reviewed: 2026-07-28_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
