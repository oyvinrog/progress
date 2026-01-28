#!/usr/bin/env python3
"""Quick validation script for ActionDraw module.

This script performs basic syntax and import checks without running full tests.
Use this for quick validation during development.

Usage:
    source .venv/bin/activate  # Activate virtual environment first
    python3 validate_actiondraw.py
    
    Or:
    .venv/bin/python3 validate_actiondraw.py
"""

import sys
import ast
import subprocess
from pathlib import Path


def check_syntax(filename):
    """Check if a Python file has valid syntax."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source, filename)
        print(f"✓ {filename}: Syntax OK")
        return True
    except SyntaxError as e:
        print(f"✗ {filename}: Syntax Error")
        print(f"  Line {e.lineno}: {e.msg}")
        if e.text:
            print(f"  {e.text.rstrip()}")
            print(f"  {' ' * (e.offset - 1)}^")
        return False
    except Exception as e:
        print(f"✗ {filename}: Error - {e}")
        return False


def _is_missing_gui_dependency(error_msg):
    """Return True when an import fails due to optional GUI deps in CI."""
    return (
        "PySide6" in error_msg
        or "matplotlib" in error_msg
        or "libEGL" in error_msg
        or "libGL" in error_msg
    )


def check_imports():
    """Check if modules can be imported."""
    modules = [
        ('actiondraw', [
            'DiagramModel',
            'DiagramItem',
            'DiagramEdge',
            'DiagramItemType',
            'create_actiondraw_window',
        ]),
        ('task_model', [
            'TaskModel',
            'Task',
            'ProjectManager',
        ]),
    ]

    all_ok = True
    missing_deps = []
    
    for module_name, items in modules:
        try:
            module = __import__(module_name)
            print(f"✓ {module_name}: Module imported")
            
            for item_name in items:
                if hasattr(module, item_name):
                    print(f"  ✓ {item_name} found")
                else:
                    print(f"  ✗ {item_name} NOT found")
                    all_ok = False
        except ImportError as e:
            error_msg = str(e)
            if _is_missing_gui_dependency(error_msg):
                missing_deps.append(error_msg.split("'")[1] if "'" in error_msg else error_msg)
                print(f"⚠ {module_name}: Missing dependency (expected if .venv not activated)")
            else:
                print(f"✗ {module_name}: Import failed - {e}")
                all_ok = False
        except Exception as e:
            print(f"✗ {module_name}: Error - {e}")
            all_ok = False
    
    if missing_deps:
        print(f"\n⚠ Note: Missing dependencies detected. Activate .venv:")
        print(f"   source .venv/bin/activate")
        print(f"   or use: .venv/bin/python3 validate_actiondraw.py")

    return all_ok


def check_basic_functionality():
    """Check basic functionality without Qt."""
    try:
        from actiondraw import DiagramItem, DiagramEdge, DiagramItemType
        
        # Test DiagramItem
        item = DiagramItem(
            id="test_1",
            item_type=DiagramItemType.BOX,
            x=10.0,
            y=20.0,
            text="Test"
        )
        assert item.id == "test_1"
        assert item.text == "Test"
        print("✓ DiagramItem: Basic functionality OK")
        
        # Test DiagramEdge
        edge = DiagramEdge(id="edge_1", from_id="box_1", to_id="box_2")
        assert edge.from_id == "box_1"
        print("✓ DiagramEdge: Basic functionality OK")
        
        return True
    except ImportError as e:
        error_msg = str(e)
        if _is_missing_gui_dependency(error_msg):
            print("⚠ Basic functionality check skipped (GUI dependencies not available)")
            print("   Activate .venv to run full checks")
            return True  # Don't fail on missing deps
        print(f"✗ Basic functionality check failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"✗ Basic functionality check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def _load_pyproject_modules():
    """Load py-modules from pyproject.toml if possible."""
    try:
        import tomllib as toml
    except ImportError:
        try:
            import tomli as toml
        except ImportError:
            print("⚠ Packaging check skipped (tomllib/tomli not available)")
            return None

    try:
        with open("pyproject.toml", "rb") as f:
            data = toml.load(f)
    except Exception as e:
        print(f"⚠ Packaging check skipped ({e})")
        return None

    modules = data.get("tool", {}).get("setuptools", {}).get("py-modules", [])
    if not modules:
        print("⚠ Packaging check skipped (no tool.setuptools.py-modules)")
        return None
    return modules


def check_packaging_manifest():
    """Ensure local imports are listed in pyproject.toml py-modules."""
    modules = _load_pyproject_modules()
    if not modules:
        return True

    module_set = set(modules)
    local_modules = {p.stem for p in Path(".").glob("*.py")}
    missing = {}

    for module_name in modules:
        module_path = Path(f"{module_name}.py")
        if not module_path.exists():
            continue

        try:
            source = module_path.read_text(encoding="utf-8")
            tree = ast.parse(source, str(module_path))
        except Exception as e:
            print(f"⚠ Packaging check skipped ({module_path}: {e})")
            return True

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in local_modules and name not in module_set:
                        missing.setdefault(module_name, set()).add(name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name = node.module.split(".")[0]
                    if name in local_modules and name not in module_set:
                        missing.setdefault(module_name, set()).add(name)

    if missing:
        print("✗ Packaging manifest missing local modules:")
        for module_name in sorted(missing):
            deps = ", ".join(sorted(missing[module_name]))
            print(f"  {module_name}.py imports: {deps}")
        print("  Add them under [tool.setuptools].py-modules in pyproject.toml")
        return False

    print("✓ Packaging manifest covers local imports")
    return True


def check_actiondraw_smoke():
    """Run a smoke test for `python -m actiondraw` without entering the event loop."""
    cmd = [sys.executable, "-m", "actiondraw", "--smoke"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("✓ ActionDraw smoke test passed")
        return True

    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    error_msg = stderr or stdout
    if _is_missing_gui_dependency(error_msg):
        print("⚠ ActionDraw smoke test skipped (GUI dependencies not available)")
        return True

    print("✗ ActionDraw smoke test failed")
    if stdout:
        print(stdout)
    if stderr:
        print(stderr)
    return False


def main():
    """Run all validation checks."""
    print("ActionDraw Validation")
    print("=" * 50)
    
    files_to_check = [
        'actiondraw/__init__.py',
        'actiondraw/model.py',
        'actiondraw/qml.py',
        'task_model.py',
        'test_actiondraw.py',
    ]
    
    print("\n1. Syntax Checks")
    print("-" * 50)
    syntax_ok = all(check_syntax(f) for f in files_to_check)
    
    print("\n2. Import Checks")
    print("-" * 50)
    import_ok = check_imports()
    
    print("\n3. Basic Functionality Checks")
    print("-" * 50)
    functionality_ok = check_basic_functionality()

    print("\n4. Packaging Manifest Checks")
    print("-" * 50)
    packaging_ok = check_packaging_manifest()

    print("\n5. ActionDraw Smoke Test")
    print("-" * 50)
    smoke_ok = check_actiondraw_smoke()
    
    print("\n" + "=" * 50)
    if syntax_ok and import_ok and functionality_ok and packaging_ok and smoke_ok:
        print("✓ All validation checks passed!")
        return 0
    else:
        print("✗ Some validation checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
