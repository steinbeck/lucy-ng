"""GET /api/status router — live run status with graceful degradation.

Degradation tiers (D-01 through D-04):
  1. timing.json (finalized)  → state "complete", frozen total_duration_s
  2. timing.jsonl (live)      → state "running", derived iteration + elapsed
  3. CASE-PROGRESS.md headers → state "running", iteration from ## Iteration N
  4. no data at all           → state "waiting" HTTP 200 (never 500)

WV-08 import-safety: this module imports fastapi at module level, which is
permitted because it is ONLY ever imported from inside create_app() and
from test bodies.  It must NOT be imported from webview/__init__.py,
webview/server.py, or webview/state.py.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter


def make_router(analysis_dir: Path) -> APIRouter:
    """Return an APIRouter(prefix='/api') with a GET /status route.

    Args:
        analysis_dir: Path to the CASE analysis directory (already resolved
            by create_app; do NOT call .resolve() here again).

    Returns:
        An APIRouter with GET /status closed over analysis_dir.
    """
    router = APIRouter(prefix="/api")

    @router.get("/status")
    def get_status() -> dict[str, Any]:
        return _derive_status(analysis_dir)

    return router


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _derive_status(analysis_dir: Path) -> dict[str, Any]:
    """Derive status payload; always returns a dict, never raises.

    Tier 1 – timing.json (finalized, only present after run end):
      Return state="complete" with elapsed_s == total_duration_s.

    Tier 2 – timing.jsonl (append-only, present during live run):
      Parse line-by-line, skipping partial/truncated lines (Pitfall 7).
      Return state="running" with iteration and elapsed_s.

    Tier 3 – CASE-PROGRESS.md headers (fallback when timing lags):
      Parse ## Iteration N and ### <Agent> headers.
      Return state="running" with elapsed_s=None.

    Tier 4 – no data at all:
      Return state="waiting" with all fields None.
    """
    # ------------------------------------------------------------------
    # Tier 1: finalized timing.json
    # ------------------------------------------------------------------
    timing_json = analysis_dir / "timing.json"
    if timing_json.exists():
        try:
            data = json.loads(timing_json.read_text(encoding="utf-8"))
            phases = data.get("phases", [])
            max_iter = 0
            for ph in phases:
                m = re.match(r"lsd-iteration-(\d+)$", ph.get("phase", ""))
                if m:
                    max_iter = max(max_iter, int(m.group(1)))
            return {
                "state": "complete",
                "iteration": max_iter if max_iter > 0 else None,
                "active_phase": None,
                "elapsed_s": data.get("total_duration_s"),
            }
        except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
            pass  # fall through to timing.jsonl

    # ------------------------------------------------------------------
    # Tier 2: live timing.jsonl
    # ------------------------------------------------------------------
    timing_jsonl = analysis_dir / "timing.jsonl"
    if timing_jsonl.exists():
        try:
            raw = timing_jsonl.read_text(encoding="utf-8")
            events: list[dict[str, Any]] = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # skip partial last line (mid-write, Pitfall 7)
            if events:
                return _status_from_events(events)
        except OSError:
            pass  # file disappeared mid-read — fall through

    # ------------------------------------------------------------------
    # Tier 3: CASE-PROGRESS.md header parse (fallback)
    # ------------------------------------------------------------------
    progress_md = analysis_dir / "CASE-PROGRESS.md"
    if progress_md.exists():
        try:
            return _status_from_progress_md(progress_md.read_text(encoding="utf-8"))
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Tier 4: no data
    # ------------------------------------------------------------------
    return {"state": "waiting", "iteration": None, "active_phase": None, "elapsed_s": None}


def _status_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive run status from a parsed list of timing.jsonl events.

    Epoch values are JSON strings from the shell printf %s — always cast
    with int() before arithmetic (Pitfall 4).

    Active phase = last phase_start event whose phase has no matching
    phase_end (D-01).

    Iteration = parsed from the active phase name (e.g. lsd-iteration-03 → 3).
    Non-iteration phases (peak-picking, etc.) return iteration=0.
    """
    # Find run_start epoch
    run_start_epoch: int | None = None
    for ev in events:
        if ev.get("event") == "run_start":
            try:
                run_start_epoch = int(ev["epoch"])  # epoch is a string (Pitfall 4)
            except (KeyError, ValueError, TypeError):
                pass
            break  # only the first run_start matters

    # Collect phase_start and phase_end events in order
    phase_starts: list[str] = []
    phase_ends: set[str] = set()
    for ev in events:
        event_type = ev.get("event", "")
        phase = ev.get("phase", "")
        if event_type == "phase_start" and phase:
            phase_starts.append(phase)
        elif event_type == "phase_end" and phase:
            phase_ends.add(phase)

    # Active phase = last phase_start with no matching phase_end
    active_phase: str | None = None
    for phase in reversed(phase_starts):
        if phase not in phase_ends:
            active_phase = phase
            break

    # Iteration from active phase name (lsd-iteration-NN → int, Pitfall 5)
    iteration = 0
    if active_phase:
        m = re.match(r"lsd-iteration-(\d+)$", active_phase)
        if m:
            iteration = int(m.group(1))

    # Compute elapsed_s = now − run_start_epoch (D-03)
    elapsed_s: int | None = None
    if run_start_epoch is not None:
        now_epoch = int(datetime.now(tz=timezone.utc).timestamp())
        # Clamp: NTP step-back or VM resume can make now < run_start.
        elapsed_s = max(0, now_epoch - run_start_epoch)

    return {
        "state": "running",
        "iteration": iteration,
        "active_phase": active_phase,
        "elapsed_s": elapsed_s,
    }


def _status_from_progress_md(content: str) -> dict[str, Any]:
    """Extract iteration and active agent from CASE-PROGRESS.md headers.

    Used as the D-02 fallback when timing.jsonl is missing or empty.
    elapsed_s is always None (no timestamps in the MD source).
    """
    iteration = 0
    active_phase: str | None = None

    for line in content.splitlines():
        m = re.match(r"^## Iteration (\d+)", line)
        if m:
            iteration = int(m.group(1))
        m2 = re.match(r"^### (.+)$", line)
        if m2:
            header = m2.group(1).strip()
            # Skip coordinator and timing-summary headers
            if header not in ("Coordinator", "Timing Summary"):
                active_phase = header.lower().replace(" ", "_").replace("-", "_")

    return {
        "state": "running",
        "iteration": iteration,
        "active_phase": active_phase,
        "elapsed_s": None,
        "source": "progress_md_fallback",
    }
