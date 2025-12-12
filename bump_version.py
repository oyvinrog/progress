#!/usr/bin/env python3
"""
Version bumping script for the progress-list project.

This script helps bump the version number in pyproject.toml following semantic versioning.
Usage:
    python bump_version.py [major|minor|patch]
    python bump_version.py <specific_version>

Examples:
    python bump_version.py patch    # 0.1.0 -> 0.1.1
    python bump_version.py minor    # 0.1.0 -> 0.2.0
    python bump_version.py major    # 0.1.0 -> 1.0.0
    python bump_version.py 1.2.3    # Set specific version
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Tuple


def parse_version(version: str) -> Tuple[int, int, int]:
    """Parse a semantic version string into major, minor, patch components."""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-.*)?(?:\+.*)?$', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(current_version: str, bump_type: str) -> str:
    """
    Bump the version number based on the bump type.
    
    Args:
        current_version: Current version string (e.g., "0.1.0")
        bump_type: Type of bump ("major", "minor", "patch")
    
    Returns:
        New version string
    """
    major, minor, patch = parse_version(current_version)
    
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}. Use 'major', 'minor', or 'patch'")
    
    return f"{major}.{minor}.{patch}"


def get_current_version(pyproject_path: Path) -> str:
    """Extract the current version from pyproject.toml."""
    content = pyproject_path.read_text()
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def update_version_in_file(pyproject_path: Path, new_version: str) -> None:
    """Update the version in pyproject.toml."""
    content = pyproject_path.read_text()
    updated_content = re.sub(
        r'^version\s*=\s*["\'][^"\']+["\']',
        f'version = "{new_version}"',
        content,
        flags=re.MULTILINE
    )
    pyproject_path.write_text(updated_content)


def main():
    parser = argparse.ArgumentParser(
        description="Bump version number in pyproject.toml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s patch          Bump patch version (0.1.0 -> 0.1.1)
  %(prog)s minor          Bump minor version (0.1.0 -> 0.2.0)
  %(prog)s major          Bump major version (0.1.0 -> 1.0.0)
  %(prog)s 1.2.3          Set specific version to 1.2.3
  %(prog)s --dry-run patch  Show what would change without modifying files
        """
    )
    parser.add_argument(
        "version",
        help="Version bump type (major, minor, patch) or specific version (e.g., 1.2.3)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying files"
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).parent / "pyproject.toml",
        help="Path to pyproject.toml (default: ./pyproject.toml)"
    )
    
    args = parser.parse_args()
    
    # Check if pyproject.toml exists
    if not args.file.exists():
        print(f"Error: {args.file} not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Get current version
        current_version = get_current_version(args.file)
        print(f"Current version: {current_version}")
        
        # Determine new version
        version_input = args.version.lower()
        if version_input in ("major", "minor", "patch"):
            new_version = bump_version(current_version, version_input)
        else:
            # Validate the provided version format
            try:
                parse_version(args.version)
                new_version = args.version
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                print("Version must be in format X.Y.Z (e.g., 1.2.3)", file=sys.stderr)
                sys.exit(1)
        
        print(f"New version:     {new_version}")
        
        if args.dry_run:
            print("\n[DRY RUN] No files were modified")
        else:
            # Update version in pyproject.toml
            update_version_in_file(args.file, new_version)
            print(f"\n✓ Updated {args.file}")
            print("\nNext steps:")
            print(f"  1. Review changes: git diff {args.file}")
            print(f"  2. Commit changes: git commit -am 'Bump version to {new_version}'")
            print(f"  3. Create tag: git tag v{new_version}")
            print(f"  4. Push changes: git push && git push --tags")
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
