"""Tests for `lucy_ng.nus.params.read_nus_params` (NUS-02)."""

from pathlib import Path

import pytest

from lucy_ng.nus.params import read_nus_params

DATA_DIR = Path(__file__).parent / "fixtures" / "nus"
EXP2_COSY = DATA_DIR / "exp2_cosy"
EXP3_HSQC = DATA_DIR / "exp3_hsqc"
EXP4_HMBC = DATA_DIR / "exp4_hmbc"


class TestNusParamsCOSY:
    """exp2 (COSY): homonuclear 1H-1H, FnMODE=1 (QF, real-only)."""

    def test_fnmode_f1(self) -> None:
        params = read_nus_params(EXP2_COSY)
        assert params.fnmode_f1 == 1

    def test_f1_td(self) -> None:
        params = read_nus_params(EXP2_COSY)
        assert params.f1_td == 188

    def test_nus_td(self) -> None:
        params = read_nus_params(EXP2_COSY)
        assert params.nus_td == 750

    def test_f1_nucleus(self) -> None:
        params = read_nus_params(EXP2_COSY)
        assert params.f1_nucleus == "1H"

    def test_f2_td(self) -> None:
        params = read_nus_params(EXP2_COSY)
        assert params.f2_td == 2048

    def test_byte_order(self) -> None:
        params = read_nus_params(EXP2_COSY)
        assert params.byte_order == 0

    def test_grpdly_is_float_not_rounded(self) -> None:
        params = read_nus_params(EXP2_COSY)
        assert params.grpdly == pytest.approx(67.9851531982422)
        assert isinstance(params.grpdly, float)

    def test_nus_amount_pct(self) -> None:
        params = read_nus_params(EXP2_COSY)
        assert params.nus_amount_pct == 25

    def test_pulse_program_stripped(self) -> None:
        params = read_nus_params(EXP2_COSY)
        assert params.pulse_program == "cosygpmfppqf"
        assert "<" not in params.pulse_program
        assert ">" not in params.pulse_program


class TestNusParamsHSQC:
    """exp3 (HSQC): heteronuclear 1H-13C, FnMODE=6 (Echo-AntiEcho)."""

    def test_fnmode_f1(self) -> None:
        params = read_nus_params(EXP3_HSQC)
        assert params.fnmode_f1 == 6

    def test_f1_td(self) -> None:
        params = read_nus_params(EXP3_HSQC)
        assert params.f1_td == 100

    def test_nus_td(self) -> None:
        params = read_nus_params(EXP3_HSQC)
        assert params.nus_td == 400

    def test_f1_nucleus(self) -> None:
        params = read_nus_params(EXP3_HSQC)
        assert params.f1_nucleus == "13C"

    def test_f1_sfo1(self) -> None:
        params = read_nus_params(EXP3_HSQC)
        assert params.f1_sfo1 == pytest.approx(125.715668907639)

    def test_nus_amount_pct(self) -> None:
        params = read_nus_params(EXP3_HSQC)
        assert params.nus_amount_pct == 25

    def test_sf_offset_from_procs_proc2s(self) -> None:
        """SF/OFFSET come from pdata/1/procs (F2) and pdata/1/proc2s (F1),
        never from acqus/acqu2s (RESEARCH.md 'SF/OFFSET live in procs' finding).
        """
        params = read_nus_params(EXP3_HSQC)
        assert params.f1_sf == pytest.approx(125.704983984)
        assert params.f1_offset == pytest.approx(174.9902)

    def test_fnmode_f1_regression_not_zero(self) -> None:
        """Regression guard: fnmode_f1 must come from acqu2s, never acqus.

        acqus also has a vestigial FnMODE key that is always 0 for every
        experiment. Reading the wrong file would silently report 0 here.
        """
        params = read_nus_params(EXP3_HSQC)
        assert params.fnmode_f1 != 0
        assert params.fnmode_f1 == 6


class TestNusParamsHMBC:
    """exp4 (HMBC): heteronuclear 1H-13C, FnMODE=6 (Echo-AntiEcho), 33% NUS."""

    def test_fnmode_f1(self) -> None:
        params = read_nus_params(EXP4_HMBC)
        assert params.fnmode_f1 == 6

    def test_f1_td(self) -> None:
        params = read_nus_params(EXP4_HMBC)
        assert params.f1_td == 232

    def test_nus_td(self) -> None:
        params = read_nus_params(EXP4_HMBC)
        assert params.nus_td == 700

    def test_f1_nucleus(self) -> None:
        params = read_nus_params(EXP4_HMBC)
        assert params.f1_nucleus == "13C"

    def test_nus_amount_pct(self) -> None:
        params = read_nus_params(EXP4_HMBC)
        assert params.nus_amount_pct == 33

    def test_fnmode_f1_regression_not_zero(self) -> None:
        """Regression guard: fnmode_f1 must come from acqu2s, never acqus."""
        params = read_nus_params(EXP4_HMBC)
        assert params.fnmode_f1 != 0


class TestNusParamsErrors:
    """Error handling: nonexistent expdir must fail loud before any nmrglue call."""

    def test_nonexistent_expdir_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_nus_params(DATA_DIR / "does_not_exist")
