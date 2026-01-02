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
        ('progress_list', [
            'TaskModel',
            'Task',
            'ActionDrawManager',
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
            if 'PySide6' in error_msg or 'matplotlib' in error_msg:
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
        if 'PySide6' in error_msg:
            print("⚠ Basic functionality check skipped (PySide6 not available)")
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


def main():
    """Run all validation checks."""
    print("ActionDraw Validation")
    print("=" * 50)
    
    files_to_check = [
        'actiondraw.py',
        'progress_list.py',
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
    
    print("\n" + "=" * 50)
    if syntax_ok and import_ok and functionality_ok:
        print("✓ All validation checks passed!")
        return 0
    else:
        print("✗ Some validation checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

