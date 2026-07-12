"""Tests for NUS reconstruction backend detection (NUS-01).

This dev machine has no NMRPipe installed, so `is_available()` MUST return
False without raising -- these tests exercise the "not installed" diagnostic
path. The positive/sourced path is manual-only (see 97-VALIDATION.md).
"""

import subprocess

from lucy_ng.nus.backends import get_backend, list_available_backends
from lucy_ng.nus.backends.nmrpipe_smile import NmrPipeSmileBackend


class TestNusBackendAvailability:
    """Tests for NmrPipeSmileBackend detection/availability."""

    def test_missing_tools_returns_list(self) -> None:
        """missing_tools() returns a list."""
        result = NmrPipeSmileBackend.missing_tools()
        assert isinstance(result, list)

    def test_missing_tools_includes_nmrpipe_on_this_machine(self) -> None:
        """On this dev machine (no NMRPipe), 'nmrPipe' is missing."""
        assert "nmrPipe" in NmrPipeSmileBackend.missing_tools()

    def test_required_tools_never_includes_smilenus(self) -> None:
        """REQUIRED_TOOLS must never include the non-existent 'smileNus'."""
        assert "smileNus" not in NmrPipeSmileBackend.REQUIRED_TOOLS
        assert set(NmrPipeSmileBackend.REQUIRED_TOOLS) == {
            "nmrPipe",
            "bruk2pipe",
            "nusExpand.tcl",
        }

    def test_smile_plugin_available_short_circuits_when_nmrpipe_absent(
        self, monkeypatch
    ) -> None:
        """smile_plugin_available() returns False without launching a
        subprocess when nmrPipe is absent (short-circuit)."""
        monkeypatch.setattr("shutil.which", lambda _tool: None)

        def _fail_if_called(*_args, **_kwargs):
            raise AssertionError(
                "subprocess.run should not be called when nmrPipe is absent"
            )

        monkeypatch.setattr(subprocess, "run", _fail_if_called)
        assert NmrPipeSmileBackend.smile_plugin_available() is False

    def test_smile_plugin_available_returns_bool_on_this_machine(self) -> None:
        """smile_plugin_available() returns a bool and does not raise."""
        result = NmrPipeSmileBackend.smile_plugin_available()
        assert isinstance(result, bool)

    def test_is_available_returns_bool(self) -> None:
        """is_available() returns a bool."""
        assert isinstance(NmrPipeSmileBackend.is_available(), bool)

    def test_is_available_false_on_this_machine(self) -> None:
        """is_available() is False on this machine (no NMRPipe) and never
        raises."""
        assert NmrPipeSmileBackend.is_available() is False


class TestNusBackendDiagnose:
    """Tests for NmrPipeSmileBackend.diagnose() diagnostic states."""

    def test_diagnose_returns_dict_with_required_keys(self) -> None:
        """diagnose() returns a dict with status/missing_tools/
        smile_available/hint keys."""
        result = NmrPipeSmileBackend.diagnose()
        assert isinstance(result, dict)
        for key in ("status", "missing_tools", "smile_available", "hint"):
            assert key in result

    def test_diagnose_status_on_this_machine(self) -> None:
        """On this dev machine (no NMRPipe), status is 'not_installed' or
        'installed_not_sourced', never 'available'/'smile_plugin_missing'."""
        result = NmrPipeSmileBackend.diagnose()
        assert result["status"] in {"not_installed", "installed_not_sourced"}

    def test_diagnose_hint_non_empty_with_install_url(self) -> None:
        """The hint is non-empty and contains an install URL."""
        result = NmrPipeSmileBackend.diagnose()
        assert result["hint"]
        assert "http" in result["hint"]

    def test_diagnose_not_installed_when_no_common_nmrbase_dirs(
        self, monkeypatch
    ) -> None:
        """status is 'not_installed' when no common NMRBASE dir exists."""
        monkeypatch.setattr("shutil.which", lambda _tool: None)
        monkeypatch.setattr("pathlib.Path.exists", lambda _self: False)
        result = NmrPipeSmileBackend.diagnose()
        assert result["status"] == "not_installed"
        assert result["missing_tools"] == NmrPipeSmileBackend.REQUIRED_TOOLS

    def test_diagnose_installed_not_sourced_when_nmrbase_dir_exists(
        self, monkeypatch
    ) -> None:
        """status is 'installed_not_sourced' when tools are missing from
        PATH but a common NMRBASE dir exists on disk."""
        monkeypatch.setattr("shutil.which", lambda _tool: None)
        monkeypatch.setattr("pathlib.Path.exists", lambda _self: True)
        result = NmrPipeSmileBackend.diagnose()
        assert result["status"] == "installed_not_sourced"

    def test_diagnose_smile_plugin_missing_when_tools_present_but_smile_fails(
        self, monkeypatch
    ) -> None:
        """status is 'smile_plugin_missing' when all REQUIRED_TOOLS are on
        PATH but the SMILE capability probe fails."""
        monkeypatch.setattr("shutil.which", lambda _tool: f"/usr/bin/{_tool}")
        monkeypatch.setattr(
            NmrPipeSmileBackend, "smile_plugin_available", classmethod(lambda cls: False)
        )
        result = NmrPipeSmileBackend.diagnose()
        assert result["status"] == "smile_plugin_missing"
        assert result["missing_tools"] == []
        assert result["smile_available"] is False

    def test_diagnose_available_when_tools_and_smile_present(
        self, monkeypatch
    ) -> None:
        """status is 'available' when all REQUIRED_TOOLS and the SMILE
        plugin are both present."""
        monkeypatch.setattr("shutil.which", lambda _tool: f"/usr/bin/{_tool}")
        monkeypatch.setattr(
            NmrPipeSmileBackend, "smile_plugin_available", classmethod(lambda cls: True)
        )
        result = NmrPipeSmileBackend.diagnose()
        assert result["status"] == "available"
        assert result["smile_available"] is True


class TestNusBackendSubprocessSafety:
    """Source-level safety assertions for the SMILE capability probe."""

    def test_probe_uses_fixed_arg_list_no_shell(self, monkeypatch) -> None:
        """The SMILE probe invokes subprocess.run with a fixed arg list and
        never shell=True."""
        captured: dict = {}

        def _fake_run(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

            class _Proc:
                stdout = "SMILE: Sparse Multidimensional Iterative Lineshape Enhanced."
                stderr = ""

            return _Proc()

        monkeypatch.setattr("shutil.which", lambda _tool: "/usr/bin/nmrPipe")
        monkeypatch.setattr(subprocess, "run", _fake_run)
        NmrPipeSmileBackend.smile_plugin_available()

        assert captured["args"][0] == ["nmrPipe", "-fn", "SMILE", "-help"]
        assert "shell" not in captured["kwargs"]
        assert captured["kwargs"]["timeout"] == 10


class TestNusBackendRegistry:
    """Tests for the NusBackend protocol + get_backend/list_available_backends
    registry."""

    def test_get_backend_default_returns_nmrpipe_smile(self) -> None:
        """get_backend() with no args returns NmrPipeSmileBackend."""
        backend = get_backend()
        assert backend is NmrPipeSmileBackend

    def test_get_backend_by_name(self) -> None:
        """get_backend('nmrpipe_smile') returns an object exposing
        is_available()."""
        backend = get_backend("nmrpipe_smile")
        assert hasattr(backend, "is_available")
        assert isinstance(backend.is_available(), bool)

    def test_get_backend_unknown_name_raises(self) -> None:
        """get_backend() with an unregistered name raises a clear error."""
        try:
            get_backend("does_not_exist")
        except (KeyError, ValueError) as exc:
            assert "does_not_exist" in str(exc)
        else:
            raise AssertionError("Expected KeyError or ValueError")

    def test_list_available_backends_returns_list(self) -> None:
        """list_available_backends() returns a list."""
        result = list_available_backends()
        assert isinstance(result, list)

    def test_list_available_backends_empty_on_this_machine(self) -> None:
        """On this dev machine (no NMRPipe), list_available_backends() is
        empty."""
        assert list_available_backends() == []
