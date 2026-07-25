"""`lucy jcamp` -- JCAMP-DX ingestion: read -> pick -> QC -> write, one command.

This module is import-safe: it does NOT import ``lucy_ng.readers.jcamp``,
``lucy_ng.nus.bridge``, ``lucy_ng.nus.qc``, ``lucy_ng.processing.jcamp_1d_bridge``,
or ``lucy_ng.models`` at the top level. All ``lucy_ng.*`` domain imports are
deferred into the command body, mirroring ``cli/nus.py``'s import-safety
convention -- even though nmrglue and click are already core deps (no new
optional extra is introduced by this command, Phase-101 D-11), keeping the
convention consistent costs nothing and future-proofs against a heavier
JCAMP-only dependency ever being added.

Phase 102 (Plan 03) adds this single top-level command: it reuses the
Phase-99 2D bridge (``nus/bridge.py::bridge_peak_pick``) and the
byte-unchanged Phase-99 QC gate (``nus/qc.py::run_qc_checks``) verbatim, plus
Plan 02's thin 1D bridge (``processing/jcamp_1d_bridge.py``) and Plan 01's
homonuclear-capable reader (``readers/jcamp.py::JcampReader``). No new
picker, no new QC check, no subprocess -- this command is glue: discovery,
routing, the staged/final two-call QC ordering ``cli/nus.py::pipeline``
already solved, and the D-07 write boundary.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import click

#: Mirrors `nus/bridge.py`'s private `_VALID_BRIDGE_EXPERIMENTS` -- do not
#: import that private name, keep this command's own copy.
SUPPORTED_2D = ("HSQC", "HMBC", "COSY")
SUPPORTED_1D = ("1H", "13C")

#: Deliberately short. The unchanged bridge interpolates this into EVERY
#: per-peak `note` (`"reconstructed via {backend}; QC verdict ..."`), so a
#: long provenance string here would multiply across hundreds of peaks and
#: burn the consuming agent's attention budget (the T-99-08 concern). Full
#: provenance goes in the additive `source` block instead (`_source_block`).
RECON_BACKEND = "jcamp"


def _source_block(path: Path) -> dict[str, str]:
    """Additive top-level `source` provenance block attached to every payload.

    Verified safe: `nus/qc.py::_load_peaks` only requires `cross_peaks` and
    `_load_1d_shifts` only reads `peaks`, so extra top-level keys are ignored
    by the unchanged gate.
    """
    return {
        "format": "JCAMP-DX",
        "file": path.name,
        "reader": "lucy_ng.readers.jcamp.JcampReader",
        "reconstruction_origin": (
            "external -- spectrum was already reconstructed outside lucy-ng "
            "(e.g. TopSpin/mddnmr compressed sensing); lucy-ng only read and "
            "peak-picked it"
        ),
    }


@click.command("jcamp")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--out",
    "out_dir",
    type=click.Path(),
    default=None,
    help=(
        "Output directory for the consumable peak lists "
        "(default: <input-dir>/analysis/nmr_peaks)."
    ),
)
@click.option(
    "--snr-floor",
    type=float,
    default=5.0,
    show_default=True,
    help="SNR floor multiplier k forwarded to both the 1D and 2D pickers.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def jcamp(
    paths: tuple[str, ...],
    out_dir: str | None,
    snr_floor: float,
    output_format: str,
) -> None:
    """Ingest JCAMP-DX spectra: read -> pick -> QC -> write in one invocation.

    PATHS is either a single directory (every `*.dx` file inside is
    auto-discovered, case-insensitively) or an explicit list of `.dx` files
    -- mixing a directory with explicit files is not supported.

    \b
    Output defaults to `<input-dir>/analysis/nmr_peaks/`, overridable with
    `--out <dir>`.

    2D HSQC/HMBC/COSY files are peak-picked via the unchanged Phase-99
    `nus/bridge.py::bridge_peak_pick`; 1D 1H/13C files via the Plan-02 thin
    1D bridge. NOESY and any other unrecognized experiment is read but NOT
    picked -- it is skipped with a visible warning naming the file and the
    reason, non-fatally (D-06). A file that fails to READ is recorded as a
    named failure distinct from a D-06 skip and forces a non-zero exit --
    malformed input is never silently treated as clean.

    The unchanged Phase-99 QC gate (`nus/qc.py::run_qc_checks`) runs EXACTLY
    ONCE over every staged 1D reference and 2D correlation together. A FAIL
    verdict writes NOTHING to the consumable output: the verdict-annotated
    payloads plus `qc_report.json` are quarantined instead, and the process
    exits non-zero (D-07 write boundary, extended from Phase 99).

    This command has no `--ridge-fail`/`--coverage-floor`/`--c13-tol`/
    `--h1-tol` threshold-override flags of its own (Assumption A3): standalone
    re-grading with custom thresholds is `lucy nus qc <out-dir>` -- the
    output schema is identical across the NUS and JCAMP paths, so no
    duplicate `lucy jcamp qc` subcommand exists (D-01).

    Honest note (Pitfall 4, document-only): with no DEPT `.dx` file present
    (the `C20H32O2-jcamp` case), `QcConfig.default()`'s
    `known_quaternary_shifts` -- the five compiled-in Sec.8 shifts (142.00,
    135.86, 79.35, 36.23, 37.86) -- is used unconditionally, so
    `classification_source` will read `"override"`. This is inherited,
    byte-unchanged `qc.py` behaviour, not a choice this command makes; no CLI
    flag here disables it, because `qc.py` is byte-protected this phase.
    """
    from lucy_ng.models import Spectrum1D, Spectrum2D
    from lucy_ng.models.nus import QcVerdict
    from lucy_ng.nus.bridge import bridge_peak_pick, write_peak_json
    from lucy_ng.nus.qc import run_qc_checks
    from lucy_ng.processing.jcamp_1d_bridge import bridge_peak_pick_1d
    from lucy_ng.readers.jcamp import JcampReader

    # STEP 1 -- resolve inputs.
    resolved = [Path(p).resolve() for p in paths]
    files: list[Path]
    if len(resolved) == 1 and resolved[0].is_dir():
        input_root = resolved[0]
        # suffix.lower() rather than glob("*.dx") so a .DX file is found
        # once and only once on a case-insensitive filesystem.
        files = sorted(
            p for p in input_root.iterdir() if p.is_file() and p.suffix.lower() == ".dx"
        )
        if not files:
            click.echo(f"No .dx files found in directory: {input_root}", err=True)
            raise SystemExit(1)
    else:
        if any(p.is_dir() for p in resolved):
            click.echo(
                "Mixing a directory with explicit files is not supported.", err=True
            )
            raise SystemExit(2)
        files = resolved
        input_root = files[0].parent

    # STEP 2 -- resolve output locations. Do NOT create out_root yet -- the
    # FAIL branch must leave it non-existent.
    out_root = Path(out_dir).resolve() if out_dir else input_root / "analysis" / "nmr_peaks"
    # The work root deliberately sits BESIDE out_root, not inside it, so
    # staged/quarantine JSON can never be picked up by a later
    # `lucy nus qc <out_root>` run (102-RESEARCH.md Pitfall 3) and so a FAIL
    # run leaves `analysis/nmr_peaks/` absent.
    work_root = out_root.parent / "jcamp_ingest"
    staged_dir = work_root / "staged"
    quarantine_dir = work_root / "qc_failed"

    # STEP 2.5 -- clear stale state left by a PRIOR invocation before
    # staging begins (CR-01). Every invocation must reflect ONLY the files
    # discovered THIS run: a prior invocation's leftovers otherwise silently
    # pollute run_qc_checks()'s directory-wide glob (a removed/renamed input
    # keeps "voting" in the current run's verdict) and, worse, a stale
    # PASS-graded consumable file can survive a later FAIL run unchanged,
    # defeating the D-07 write boundary one layer up.
    #
    # Two different clearing strategies for two different ownership scopes:
    # - `work_root` (`jcamp_ingest/staged` + `jcamp_ingest/qc_failed`) is a
    #   fixed, derived subdirectory name that ONLY this command ever writes
    #   to -- nothing else can be sitting there -- so a full `rmtree` is
    #   safe and simplest.
    # - `out_root` is different: it is directly user-specified via `--out`
    #   and may be a pre-existing directory the caller manages for other
    #   purposes, so it is never `rmtree`d wholesale. Instead only the
    #   closed set of filenames this command is ever capable of writing
    #   there (derived from `SUPPORTED_2D`/`SUPPORTED_1D`) is removed,
    #   leaving any unrelated file in that directory untouched. If that
    #   empties the directory, the (now-empty) directory is removed too,
    #   to preserve the documented "a FAIL run leaves `out_root` absent"
    #   invariant across a PASS-then-FAIL re-run.
    shutil.rmtree(work_root, ignore_errors=True)
    if out_root.is_dir():
        for own_name in (*SUPPORTED_2D, *SUPPORTED_1D):
            (out_root / f"{own_name}.json").unlink(missing_ok=True)
        try:
            out_root.rmdir()
        except OSError:
            pass  # not empty -- a file this command does not own; leave it

    # STEP 3 -- read, pick and stage every file in one pass, with no QC yet.
    staged_2d: list[tuple[Spectrum2D, str, Path]] = []
    staged_1d: list[tuple[str, dict[str, Any]]] = []
    skipped: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    staged_types: set[str] = set()

    for path in files:
        try:
            spectrum = JcampReader.read(path)
        except (ValueError, OSError, KeyError, IndexError) as exc:
            # nus/qc.py::_load_peaks idiom: one bad file never aborts the
            # batch and is never silently treated as clean.
            failed.append({"file": path.name, "error": str(exc)})
            click.echo(f"Warning: failed to read {path.name}: {exc}", err=True)
            continue

        if isinstance(spectrum, Spectrum1D):
            nucleus = spectrum.nucleus
            if nucleus not in SUPPORTED_1D:
                reason = f"unsupported 1D nucleus {nucleus}"
                skipped.append({"file": path.name, "reason": reason})
                click.echo(f"Warning: skipping {path.name}: {reason}", err=True)
                continue
            if nucleus in staged_types:
                error = f"duplicate experiment type {nucleus}"
                failed.append({"file": path.name, "error": error})
                click.echo(f"Warning: {path.name}: {error}; not written", err=True)
                continue
            payload = bridge_peak_pick_1d(spectrum, snr_floor=snr_floor)
            payload["source"] = _source_block(path)
            write_peak_json(staged_dir, nucleus, payload)
            staged_1d.append((nucleus, payload))
            staged_types.add(nucleus)
        else:
            if not isinstance(spectrum, Spectrum2D):
                # WR-01: fail loud rather than rely on `assert`, which is
                # stripped under `-O`/`-OO` -- this branch's type-narrowing
                # is load-bearing control flow, not an optional sanity check.
                raise TypeError(
                    f"Unexpected JcampReader.read() result type: {type(spectrum)!r}"
                )
            experiment_type = spectrum.experiment_type
            if experiment_type not in SUPPORTED_2D:
                reason = (
                    f"{experiment_type} is not supported by the peak-pick bridge "
                    "(D-06: read, not picked)"
                )
                skipped.append({"file": path.name, "reason": reason})
                click.echo(f"Warning: skipping {path.name}: {reason}", err=True)
                continue
            if experiment_type in staged_types:
                error = f"duplicate experiment type {experiment_type}"
                failed.append({"file": path.name, "error": error})
                click.echo(f"Warning: {path.name}: {error}; not written", err=True)
                continue
            try:
                # Belt and braces: bridge_peak_pick's own ValueError for an
                # unsupported experiment is routed to `skipped`, even though
                # the membership test above should already have prevented it.
                staged_payload = bridge_peak_pick(
                    spectrum,
                    experiment=experiment_type,
                    qc_report=None,
                    recon_meta={"backend": RECON_BACKEND, "iterations": None},
                    snr_floor=snr_floor,
                )
            except ValueError as exc:
                skipped.append({"file": path.name, "reason": str(exc)})
                click.echo(f"Warning: skipping {path.name}: {exc}", err=True)
                continue
            staged_payload["source"] = _source_block(path)
            write_peak_json(staged_dir, experiment_type, staged_payload)
            staged_2d.append((spectrum, experiment_type, path))
            staged_types.add(experiment_type)

    # STEP 4.
    if not staged_2d and not staged_1d:
        click.echo(
            f"No supported spectra staged ({len(skipped)} skipped, "
            f"{len(failed)} failed); nothing to do.",
            err=True,
        )
        raise SystemExit(1)

    # STEP 5 -- QC ONCE. This single call MUST come after every 1D and 2D
    # file has been staged, because QcReferenceData.resolve()/
    # _load_1d_shifts() glob the whole staged directory -- never invoke the
    # QC gate once per file (102-RESEARCH.md Pattern 2 anti-pattern).
    report = run_qc_checks(staged_dir)

    # STEP 6 -- write boundary.
    written: list[str] = []
    quarantine: str | None = None

    if report.verdict == QcVerdict.FAIL:
        for spectrum2d, experiment_type, path in staged_2d:
            # confidence_from_verdict() intentionally raises for FAIL, so
            # re-derive the staged (verdict-less) payload -- deterministic
            # for the same spectrum -- and hand-build the FAIL metadata,
            # exactly as cli/nus.py::pipeline's FAIL branch does.
            final_payload = bridge_peak_pick(
                spectrum2d,
                experiment=experiment_type,
                qc_report=None,
                recon_meta={"backend": RECON_BACKEND, "iterations": None},
                snr_floor=snr_floor,
            )
            final_payload["reconstruction"] = {
                "backend": RECON_BACKEND,
                "iterations": None,
                "qc_verdict": report.verdict.value,
                "violated_checks": report.violated_checks(),
                "thresholds_used": dict(report.thresholds_used),
            }
            final_payload["caveat"] = (
                f"Reconstructed via {RECON_BACKEND}. QC verdict: FAIL. "
                f"Violated checks: {', '.join(report.violated_checks())}."
            )
            final_payload["source"] = _source_block(path)
            write_peak_json(quarantine_dir, experiment_type, final_payload)
        for nucleus, payload in staged_1d:
            write_peak_json(quarantine_dir, nucleus, payload)
        (quarantine_dir / "qc_report.json").write_text(
            json.dumps(report.to_dict(), indent=2)
        )
        quarantine = str(quarantine_dir)
        click.echo(
            f"QC verdict FAIL -- critical violations: "
            f"{', '.join(report.critical_violations())}. Nothing written to {out_root}.",
            err=True,
        )
    else:
        for spectrum2d, experiment_type, path in staged_2d:
            # CAUSAL RE-BUILD -- reproduces identical cross-peaks, now with
            # the real verdict stamped in.
            final_payload = bridge_peak_pick(
                spectrum2d,
                experiment=experiment_type,
                qc_report=report,
                recon_meta={"backend": RECON_BACKEND, "iterations": None},
                snr_floor=snr_floor,
            )
            final_payload["source"] = _source_block(path)
            out_path = write_peak_json(out_root, experiment_type, final_payload)
            written.append(str(out_path))
        for nucleus, payload in staged_1d:
            # A 1D payload carries no verdict-derived field, so no rebuild
            # is needed -- write the staged payload unchanged.
            out_path = write_peak_json(out_root, nucleus, payload)
            written.append(str(out_path))
        if report.verdict == QcVerdict.PARTIAL:
            click.echo(
                f"QC verdict PARTIAL -- violated checks: "
                f"{', '.join(report.violated_checks())}.",
                err=True,
            )

    # STEP 7 -- output.
    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "verdict": report.verdict.value,
                    "out_dir": str(out_root),
                    "written": written,
                    "skipped": skipped,
                    "failed": failed,
                    "quarantine": quarantine,
                    "report": report.to_dict(),
                },
                indent=2,
            )
        )
    else:
        click.echo(
            f"Discovered {len(files)} file(s); staged 2D: {len(staged_2d)}, "
            f"staged 1D: {len(staged_1d)}."
        )
        click.echo(f"QC verdict: {report.verdict.value}")
        for out_str in written:
            click.echo(f"Written: {out_str}")
        for entry in skipped:
            click.echo(f"Skipped: {entry['file']} ({entry['reason']})")
        for entry in failed:
            click.echo(f"Failed: {entry['file']} ({entry['error']})")
        if quarantine:
            click.echo(f"Quarantined: {quarantine}")

    # STEP 8 -- exit code. FAIL always exits 1. A non-empty `failed` list
    # ALSO forces exit 1 even on PASS/PARTIAL -- a file that could not be
    # read must never be reported as a clean run. A non-empty `skipped`
    # list alone is non-fatal and exits 0 (D-06).
    if report.verdict == QcVerdict.FAIL or failed:
        raise SystemExit(1)
