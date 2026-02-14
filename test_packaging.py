"""Packaging regression tests."""

import re
from pathlib import Path


def _read_setuptools_py_modules() -> set[str]:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"py-modules\s*=\s*\[(.*?)\]", pyproject, flags=re.DOTALL)
    assert match is not None, "py-modules is missing from pyproject.toml"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def test_runtime_top_level_modules_are_packaged():
    modules = _read_setuptools_py_modules()
    required = {"task_model", "markdown_note_editor", "progress_crypto"}
    missing = required - modules
    assert not missing, f"Missing py-modules in pyproject.toml: {sorted(missing)}"
