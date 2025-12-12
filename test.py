#!/usr/bin/env python
"""Test runner script for progress_list tests."""

import sys
import subprocess


def main():
    """Run pytest with coverage."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "test_progress_list.py",
        "--cov=progress_list",
        "--cov-report=term-missing",
        "--cov-report=html",
        "-v",
    ]

    print("Running tests with coverage...\n")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n✓ All tests passed!")
        print("Coverage report: htmlcov/index.html")
    else:
        print("\n✗ Tests failed!")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
