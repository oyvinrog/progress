"""Packaging regression tests."""

import re
from pathlib import Path
from typing import Set

RUNTIME_ROOT_MODULES = {
    "eff_diceware",
    "markdown_note_editor",
    "progress_crypto",
    "task_model",
}

DEV_ROOT_MODULES = {
    "bump_version",
    "run_actiondraw",
    "validate_actiondraw",
}


def _read_setuptools_py_modules() -> Set[str]:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"py-modules\s*=\s*\[(.*?)\]", pyproject, flags=re.DOTALL)
    assert match is not None, "py-modules is missing from pyproject.toml"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _repo_root_modules() -> Set[str]:
    return {path.stem for path in Path(".").glob("*.py")}


def test_all_root_modules_are_classified():
    known_modules = RUNTIME_ROOT_MODULES | DEV_ROOT_MODULES
    unclassified = _repo_root_modules() - known_modules
    assert not unclassified, f"Unclassified repo-root modules: {sorted(unclassified)}"


def test_runtime_top_level_modules_are_packaged():
    modules = _read_setuptools_py_modules()
    assert modules == RUNTIME_ROOT_MODULES, (
        "tool.setuptools.py-modules does not match audited runtime modules. "
        f"Expected {sorted(RUNTIME_ROOT_MODULES)}, got {sorted(modules)}"
    )


def test_packaged_root_modules_have_files_and_exclude_dev_scripts():
    repo_modules = _repo_root_modules()
    modules = _read_setuptools_py_modules()

    missing_files = modules - repo_modules
    assert not missing_files, f"Packaged modules missing files: {sorted(missing_files)}"

    packaged_dev_modules = modules & DEV_ROOT_MODULES
    assert not packaged_dev_modules, (
        f"Development-only modules should not be packaged: {sorted(packaged_dev_modules)}"
    )


def test_priorityplot_script_is_declared():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'priorityplot = "actiondraw.priorityplot.app:main"' in pyproject


def test_markdown_pdf_exporter_module_exists_in_package():
    assert Path("actiondraw/markdown_pdf_exporter.py").is_file()


def test_pdf_export_keeps_runtime_dependencies_qt_only():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'PySide6>=6.6,<7' in pyproject
    assert "reportlab" not in pyproject
    assert "weasyprint" not in pyproject
    assert "pandoc" not in pyproject


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
