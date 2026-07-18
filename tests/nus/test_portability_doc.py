"""PORT-02 tests: `docs/NUS-PORTABILITY.md` existence + required content.

Pure documentation guard -- no runtime component. Resolves the repo root from
this test file's own location (never a hardcoded absolute path) so it works
regardless of checkout location.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PORTABILITY_DOC = _REPO_ROOT / "docs" / "NUS-PORTABILITY.md"
_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_README = _REPO_ROOT / "README.md"


def test_portability_doc_exists() -> None:
    assert _PORTABILITY_DOC.is_file(), f"missing {_PORTABILITY_DOC}"


def test_portability_doc_has_minimum_length() -> None:
    text = _PORTABILITY_DOC.read_text(encoding="utf-8")
    assert len(text.splitlines()) >= 40


def test_portability_doc_names_all_three_platforms() -> None:
    text = _PORTABILITY_DOC.read_text(encoding="utf-8").lower()
    assert "macos" in text
    assert "apple silicon" in text
    assert "linux" in text
    assert "windows" in text
    assert "wsl2" in text


def test_portability_doc_marks_wsl2_documented_untested() -> None:
    text = _PORTABILITY_DOC.read_text(encoding="utf-8")
    assert "documented, untested" in text


def test_portability_doc_calls_out_separate_smile_download() -> None:
    text = _PORTABILITY_DOC.read_text(encoding="utf-8").lower()
    assert "plugin.smile" in text
    assert "separate" in text


def test_claude_md_links_portability_doc() -> None:
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    assert "docs/NUS-PORTABILITY.md" in text


def test_readme_references_portability_doc() -> None:
    text = _README.read_text(encoding="utf-8")
    assert "NUS-PORTABILITY" in text
