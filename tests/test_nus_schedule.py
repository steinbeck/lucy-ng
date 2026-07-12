"""Tests for `lucy_ng.nus.schedule` (NUS-03).

Covers the FnMODE-derived hard-fail assertion (`expected_sample_count`,
`validate_schedule`), acquisition-order-preserving `nuslist` parsing
(`read_nus_schedule`), and the unrecognized-FnMODE raise path.
"""

from pathlib import Path

import pytest

from lucy_ng.nus.schedule import (
    expected_sample_count,
    read_nus_schedule,
    validate_schedule,
)

DATA_DIR = Path(__file__).parent / "fixtures" / "nus"
EXP2_COSY = DATA_DIR / "exp2_cosy"
EXP3_HSQC = DATA_DIR / "exp3_hsqc"
EXP4_HMBC = DATA_DIR / "exp4_hmbc"


class TestExpectedSampleCount:
    """FnMODE -> sampled-count derivation rule (real vs complex modes)."""

    def test_qf_real_mode_exp2(self) -> None:
        assert expected_sample_count(1, 188) == 188

    def test_echo_antiecho_complex_mode_exp3(self) -> None:
        assert expected_sample_count(6, 100) == 50

    def test_echo_antiecho_complex_mode_exp4(self) -> None:
        assert expected_sample_count(6, 232) == 116

    def test_qseq_real_mode(self) -> None:
        assert expected_sample_count(2, 188) == 188

    def test_states_complex_mode(self) -> None:
        assert expected_sample_count(4, 100) == 50

    def test_states_tppi_complex_mode(self) -> None:
        assert expected_sample_count(5, 100) == 50

    def test_unrecognized_fnmode_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            expected_sample_count(3, 100)


class TestValidateSchedule:
    """Hard-fail assertion: n_sampled == len(nuslist), raises on mismatch."""

    def test_exp2_cosy_passes(self) -> None:
        validate_schedule(1, 188, list(range(188)))

    def test_exp3_hsqc_passes(self) -> None:
        validate_schedule(6, 100, list(range(50)))

    def test_exp4_hmbc_passes(self) -> None:
        validate_schedule(6, 232, list(range(116)))

    def test_length_mismatch_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="schedule length mismatch"):
            validate_schedule(1, 188, list(range(187)))

    def test_truncated_nuslist_raises_value_error(self) -> None:
        """A truncated (shorter than expected) nuslist must raise, never pad."""
        with pytest.raises(ValueError):
            validate_schedule(6, 100, list(range(49)))

    def test_unrecognized_fnmode_propagates_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            validate_schedule(3, 100, list(range(100)))


class TestReadNusScheduleCOSY:
    """exp2 (COSY): homonuclear 1H-1H, FnMODE=1 (QF, real-only)."""

    def test_n_sampled_matches_nuslist_length(self) -> None:
        schedule = read_nus_schedule(EXP2_COSY)
        assert schedule.n_sampled == 188
        assert len(schedule.nuslist) == 188

    def test_fnmode_and_td(self) -> None:
        schedule = read_nus_schedule(EXP2_COSY)
        assert schedule.fnmode_f1 == 1
        assert schedule.td_f1 == 188

    def test_nus_td_authoritative(self) -> None:
        """NusTD read from acqu2s, never inferred from max(nuslist)+1."""
        schedule = read_nus_schedule(EXP2_COSY)
        assert schedule.nus_td == 750

    def test_acquisition_order(self) -> None:
        """Regression: nuslist must be in acquisition order, NOT sorted."""
        schedule = read_nus_schedule(EXP2_COSY)
        assert schedule.nuslist[:8] == [0, 124, 431, 670, 369, 53, 211, 120]
        assert schedule.nuslist != sorted(schedule.nuslist)


class TestReadNusScheduleHSQC:
    """exp3 (HSQC): heteronuclear 1H-13C, FnMODE=6 (Echo-AntiEcho)."""

    def test_n_sampled_matches_nuslist_length(self) -> None:
        schedule = read_nus_schedule(EXP3_HSQC)
        assert schedule.n_sampled == 50
        assert len(schedule.nuslist) == 50

    def test_n_sampled_is_td_over_two(self) -> None:
        schedule = read_nus_schedule(EXP3_HSQC)
        assert schedule.n_sampled == schedule.td_f1 // 2

    def test_nus_td_real_vs_complex_grid_note(self) -> None:
        """NusTD=400 while max(nuslist)=199 is expected (complex-pair grid,
        see module docstring), not a bug -- never inferred from nuslist.
        """
        schedule = read_nus_schedule(EXP3_HSQC)
        assert schedule.nus_td == 400
        assert max(schedule.nuslist) == 199

    def test_acquisition_order(self) -> None:
        """Regression: nuslist parsed in acquisition order, NOT sorted."""
        schedule = read_nus_schedule(EXP3_HSQC)
        assert schedule.nuslist[:8] == [0, 33, 115, 178, 98, 14, 199, 56]
        assert schedule.nuslist != sorted(schedule.nuslist)


class TestReadNusScheduleHMBC:
    """exp4 (HMBC): heteronuclear 1H-13C, FnMODE=6 (Echo-AntiEcho), 33% NUS."""

    def test_n_sampled_matches_nuslist_length(self) -> None:
        schedule = read_nus_schedule(EXP4_HMBC)
        assert schedule.n_sampled == 116
        assert len(schedule.nuslist) == 116

    def test_n_sampled_is_td_over_two(self) -> None:
        schedule = read_nus_schedule(EXP4_HMBC)
        assert schedule.n_sampled == schedule.td_f1 // 2

    def test_nus_td_authoritative(self) -> None:
        schedule = read_nus_schedule(EXP4_HMBC)
        assert schedule.nus_td == 700

    def test_acquisition_order(self) -> None:
        """Regression: nuslist parsed in acquisition order, NOT sorted."""
        schedule = read_nus_schedule(EXP4_HMBC)
        assert schedule.nuslist[:8] == [0, 58, 201, 312, 172, 24, 348, 98]
        assert schedule.nuslist != sorted(schedule.nuslist)


class TestReadNusScheduleErrors:
    """Error handling: nonexistent expdir must fail loud."""

    def test_nonexistent_expdir_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_nus_schedule(DATA_DIR / "does_not_exist")
