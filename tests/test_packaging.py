"""Packaging regression tests."""

import re
from pathlib import Path
from typing import Set


def _read_setuptools_py_modules() -> Set[str]:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"py-modules\s*=\s*\[(.*?)\]", pyproject, flags=re.DOTALL)
    assert match is not None, "py-modules is missing from pyproject.toml"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def test_runtime_top_level_modules_are_packaged():
    modules = _read_setuptools_py_modules()
    required = {"task_model", "markdown_note_editor", "progress_crypto"}
    missing = required - modules
    assert not missing, f"Missing py-modules in pyproject.toml: {sorted(missing)}"


def test_priorityplot_script_is_declared():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'priorityplot = "actiondraw.priorityplot.app:main"' in pyproject


def test_desktop_entry_uses_packaged_icon_name():
    desktop_entry = Path("packaging/actiondraw.desktop").read_text(encoding="utf-8")
    assert "Icon=actiondraw" in desktop_entry


def test_debian_icon_assets_exist():
    for rel_path in (
        "packaging/icons/hicolor/256x256/apps/actiondraw.png",
        "packaging/icons/hicolor/512x512/apps/actiondraw.png",
    ):
        assert Path(rel_path).is_file(), f"Missing icon asset: {rel_path}"


def test_build_deb_workflow_installs_icons():
    workflow = Path(".github/workflows/build-deb.yml").read_text(encoding="utf-8")
    assert "permissions:" in workflow
    assert "contents: write" in workflow
    assert "run: ./tools/build_deb.sh" in workflow


def test_build_deb_script_installs_icons():
    script = Path("tools/build_deb.sh").read_text(encoding="utf-8")
    assert 'mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps"' in script
    assert 'mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/512x512/apps"' in script
    assert 'cp packaging/icons/hicolor/256x256/apps/actiondraw.png "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/"' in script
    assert 'cp packaging/icons/hicolor/512x512/apps/actiondraw.png "$PKG_ROOT/usr/share/icons/hicolor/512x512/apps/"' in script
