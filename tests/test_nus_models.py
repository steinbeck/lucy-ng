"""Tests for NUS acquisition-parameter and sampling-schedule models."""

import pytest

from lucy_ng.models import NusAcquisitionParams, NusSchedule


def _exp3_hsqc_kwargs() -> dict:
    """Full valid exp3 (HSQC) parameter set, verified against the real fixture.

    See .planning/phases/97-backend-integration-params-schedule/97-RESEARCH.md
    "Exact Bruker Field Names" table for the source values.
    """
    return {
        "pulse_program": "hsqcedetgpsp.3",
        "f2_nucleus": "1H",
        "f2_sfo1": 499.92164974,
        "f2_sw_h": 3750.0,
        "f2_td": 2048,
        "byte_order": 0,
        "dtype_code": 0,
        "decim": 5333.33333333333,
        "dspfvs": 20,
        "grpdly": 67.9851531982422,
        "nus_amount_pct": 25,
        "nus_seed": 54321,
        "f1_nucleus": "13C",
        "f1_sfo1": 125.715668907639,
        "f1_sw_h": 22624.4343891403,
        "f1_o1": 10684.9236386353,
        "f1_td": 100,
        "fnmode_f1": 6,
        "nus_td": 400,
        "f2_sf": 499.92,
        "f2_offset": 7.050608,
        "f1_sf": 125.704983984,
        "f1_offset": 174.9902,
    }


class TestNusAcquisitionParams:
    """Tests for NusAcquisitionParams model."""

    def test_creation_from_fixture_values(self) -> None:
        """A full valid exp3 param set constructs without error."""
        params = NusAcquisitionParams(**_exp3_hsqc_kwargs())
        assert params.f1_nucleus == "13C"
        assert params.f2_nucleus == "1H"
        assert params.fnmode_f1 == 6
        assert params.nus_td == 400
        assert params.grpdly == 67.9851531982422  # never rounded

    def test_round_trip_to_dict_from_dict(self) -> None:
        """to_dict() then from_dict() returns an equal model."""
        params = NusAcquisitionParams(**_exp3_hsqc_kwargs())
        restored = NusAcquisitionParams.from_dict(params.to_dict())
        assert restored == params

    def test_unknown_f1_nucleus_rejected(self) -> None:
        """An unrecognized f1_nucleus raises ValueError."""
        kwargs = _exp3_hsqc_kwargs()
        kwargs["f1_nucleus"] = "Xx"
        with pytest.raises(ValueError, match="Unknown nucleus"):
            NusAcquisitionParams(**kwargs)

    def test_unknown_f2_nucleus_rejected(self) -> None:
        """An unrecognized f2_nucleus raises ValueError."""
        kwargs = _exp3_hsqc_kwargs()
        kwargs["f2_nucleus"] = "Xx"
        with pytest.raises(ValueError, match="Unknown nucleus"):
            NusAcquisitionParams(**kwargs)

    def test_unrecognized_fnmode_rejected(self) -> None:
        """An FnMODE outside {1,2,4,5,6} raises ValueError."""
        kwargs = _exp3_hsqc_kwargs()
        kwargs["fnmode_f1"] = 3
        with pytest.raises(ValueError, match="FnMODE"):
            NusAcquisitionParams(**kwargs)

    def test_sf_offset_default_to_none(self) -> None:
        """A model constructed without SF/OFFSET fields validates (pre-reconstruction case)."""
        kwargs = _exp3_hsqc_kwargs()
        del kwargs["f2_sf"]
        del kwargs["f2_offset"]
        del kwargs["f1_sf"]
        del kwargs["f1_offset"]
        params = NusAcquisitionParams(**kwargs)
        assert params.f2_sf is None
        assert params.f2_offset is None
        assert params.f1_sf is None
        assert params.f1_offset is None

    def test_cosy_f1_nucleus_is_1h(self) -> None:
        """exp2 COSY has f1_nucleus=1H (differs from exp3/exp4's 13C) — never hard-code."""
        kwargs = _exp3_hsqc_kwargs()
        kwargs["f1_nucleus"] = "1H"
        kwargs["fnmode_f1"] = 1
        params = NusAcquisitionParams(**kwargs)
        assert params.f1_nucleus == "1H"
        assert params.fnmode_f1 == 1


class TestNusSchedule:
    """Tests for NusSchedule model."""

    def test_creation(self) -> None:
        """NusSchedule holds nuslist, fnmode_f1, td_f1, nus_td, n_sampled."""
        schedule = NusSchedule(
            nuslist=[0, 124, 431],
            fnmode_f1=1,
            td_f1=188,
            nus_td=750,
            n_sampled=3,
        )
        assert schedule.nuslist == [0, 124, 431]
        assert schedule.n_sampled == 3

    def test_unsorted_order_preserved(self) -> None:
        """A deliberately unsorted nuslist stays unsorted after construction."""
        unsorted_list = [0, 124, 431, 670, 369, 53, 211, 120]
        schedule = NusSchedule(
            nuslist=unsorted_list,
            fnmode_f1=1,
            td_f1=188,
            nus_td=750,
            n_sampled=len(unsorted_list),
        )
        assert schedule.nuslist == unsorted_list

    def test_to_dict_emits_nuslist_verbatim(self) -> None:
        """to_dict() emits the nuslist in the exact input order."""
        unsorted_list = [0, 124, 431, 670]
        schedule = NusSchedule(
            nuslist=unsorted_list,
            fnmode_f1=1,
            td_f1=188,
            nus_td=750,
            n_sampled=4,
        )
        assert schedule.to_dict()["nuslist"] == [0, 124, 431, 670]

    def test_round_trip_to_dict_from_dict(self) -> None:
        """to_dict() then from_dict() returns an equal model."""
        schedule = NusSchedule(
            nuslist=[0, 33, 115, 178],
            fnmode_f1=6,
            td_f1=100,
            nus_td=400,
            n_sampled=4,
        )
        restored = NusSchedule.from_dict(schedule.to_dict())
        assert restored == schedule
