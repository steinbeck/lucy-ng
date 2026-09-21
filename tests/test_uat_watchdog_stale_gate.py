"""Tests for the quota watchdog's decision on an aged usage snapshot.

`scripts/uat_watchdog.py` is the brake that keeps the benchmark from eating the
user's weekly Claude quota. It had no tests at all, which is the wrong place for
that gap: both failure directions are expensive. Too permissive and it spends
quota the user needs; too strict and the benchmark stands still through a whole
window — which is exactly what happened on 2026-09-15, when eleven hours of a
fresh window went unused.

The snapshot it reads only refreshes while the user types, so "aged" is the
normal case overnight and during holidays, not an edge case.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "uat_watchdog.py"


@pytest.fixture(scope="module")
def wd():
    spec = importlib.util.spec_from_file_location("uat_watchdog", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def snap(*, seven_pct, reset_in_hours, age_seconds, five_pct=5.0):
    """A usage snapshot with the 7-day window resetting in `reset_in_hours`.

    Negative `reset_in_hours` puts the reset in the past, i.e. the window has
    demonstrably rolled over since the reading was taken.
    """
    now = datetime.now(timezone.utc)
    reset = now + timedelta(hours=reset_in_hours)
    return {
        "five_hour": {"used_percentage": five_pct,
                      "resets_at": (now + timedelta(hours=2)).isoformat()},
        "seven_day": {"used_percentage": seven_pct, "resets_at": reset.isoformat()},
        "_age_seconds": age_seconds,
    }


def args(seven_day_max=60.0):
    return SimpleNamespace(seven_day_max=seven_day_max, five_hour_max=70.0)


class TestWindowStillOpen:
    """Nothing here changes: an aged reading accrues debt at the drift rate."""

    def test_extrapolates_from_the_last_real_reading(self, wd):
        ok, why = wd.stale_gate(snap(seven_pct=40.0, reset_in_hours=48, age_seconds=3600),
                                args(), 3600)
        assert ok is True
        assert "estimated 7d 42 %" in why

    def test_blocks_once_the_estimate_reaches_the_ceiling(self, wd):
        ok, why = wd.stale_gate(snap(seven_pct=55.0, reset_in_hours=48, age_seconds=4 * 3600),
                                args(), 4 * 3600)
        assert ok is False
        assert "ceiling" in why

    def test_refuses_beyond_the_hard_age_limit(self, wd):
        age = wd.STALE_HARD_LIMIT_S + 60
        ok, why = wd.stale_gate(snap(seven_pct=10.0, reset_in_hours=48, age_seconds=age),
                                args(), age)
        assert ok is False
        assert "hard limit" in why


class TestWindowRolledOver:
    """The new behaviour: a demonstrable reset makes the old reading obsolete.

    `resets_at` in the past is proof, not inference — the window that the stale
    percentage belonged to no longer exists, and the new one provably began at
    zero. Waiting for a human keystroke to confirm that wastes the window.
    """

    def test_runs_instead_of_waiting_for_a_keystroke(self, wd):
        # Reading is 8 h old and its window reset 2 h ago: usage restarted at 0.
        s = snap(seven_pct=82.0, reset_in_hours=-2, age_seconds=8 * 3600)
        ok, why = wd.stale_gate(s, args(), 8 * 3600)
        assert ok is True, why
        assert "82" not in why, "the pre-reset percentage must not survive the reset"

    def test_counts_from_the_reset_not_from_the_reading(self, wd):
        # 3 h since the reset at the 2 pt/h drift rate -> about 6 %.
        s = snap(seven_pct=95.0, reset_in_hours=-3, age_seconds=10 * 3600)
        ok, why = wd.stale_gate(s, args(), 10 * 3600)
        assert ok is True, why
        assert "6 %" in why

    def test_still_stops_at_the_ceiling(self, wd):
        """Even counting from zero, the ceiling still applies.

        Only reachable with a low ceiling: at 2 pt/h it takes 30 h to burn
        through 60 %, and the 12 h hard limit fires first. So the ceiling check
        in this branch is live only below STALE_HARD_LIMIT_S * drift = 24 %,
        which covers the project's standing value of 30 %... no, not even that.
        It is defence in depth for a ceiling someone may lower later, and the
        test says so rather than pretending the path is hot.
        """
        ceiling = 20.0
        hours = ceiling / wd.STALE_DRIFT_PCT_PER_HOUR + 1  # 11 h, inside the limit
        assert hours * 3600 < wd.STALE_HARD_LIMIT_S, "test would hit the hard limit first"
        s = snap(seven_pct=5.0, reset_in_hours=-hours, age_seconds=3600)
        ok, why = wd.stale_gate(s, args(seven_day_max=ceiling), 3600)
        assert ok is False
        assert "ceiling" in why

    def test_gives_up_when_the_reset_is_too_far_back(self, wd):
        # Past the hard limit the from-zero estimate is as meaningless as any
        # other, and a real reading has to be waited for after all.
        hours = wd.STALE_HARD_LIMIT_S / 3600 + 1
        s = snap(seven_pct=5.0, reset_in_hours=-hours, age_seconds=3600)
        ok, why = wd.stale_gate(s, args(), 3600)
        assert ok is False
        assert "real reading" in why


class TestResetOutranksReadingAge:
    """A reset makes the old reading's age irrelevant, however old it is.

    The hard age limit exists because extrapolating forward from a measurement
    decays: after 12 h the accumulated guess means nothing. But once the window
    has demonstrably reset, that measurement is not the basis of anything — the
    arithmetic restarts at the reset, and only the time SINCE the reset matters.
    Applying the reading's age limit to a post-reset estimate confuses the two
    clocks and blocks exactly the case the from-zero branch exists for.

    This is the realistic shape, not a corner: the user stops typing in the
    evening, the window resets at 05:00, and by morning the last reading is
    already older than the limit. The first version of this feature was dead on
    arrival for precisely that reason, and unit tests missed it because they all
    used reading ages below the limit.
    """

    def test_runs_even_when_the_reading_is_older_than_the_hard_limit(self, wd):
        age = wd.STALE_HARD_LIMIT_S + 4 * 3600      # 16 h old reading
        s = snap(seven_pct=83.0, reset_in_hours=-1, age_seconds=age)
        ok, why = wd.stale_gate(s, args(), age)
        assert ok is True, why
        assert "hard limit" not in why, "the reading's age limit must not apply after a reset"

    def test_the_morning_after_a_reset(self, wd):
        # Last keystroke 17:00, reset 05:00, checked at 06:00.
        age = 13 * 3600
        s = snap(seven_pct=83.0, reset_in_hours=-1, age_seconds=age)
        ok, why = wd.stale_gate(s, args(), age)
        assert ok is True, f"would still stand still: {why}"
        assert "2 %" in why, why


class TestTheRegressionThisPrevents:
    """The 2026-09-15 standstill, reproduced as a test."""

    def test_the_situation_that_wasted_eleven_hours(self, wd):
        # What the log actually showed: a 206-minute-old reading whose window had
        # reset in the meantime. The watchdog held for eleven hours until the user
        # typed. With the window provably reset, it should run.
        s = snap(seven_pct=79.0, reset_in_hours=-10.8, age_seconds=206 * 60)
        ok, why = wd.stale_gate(s, args(), 206 * 60)
        assert ok is True, f"still standing still: {why}"
