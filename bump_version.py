#!/usr/bin/env python3
"""Bump the version in pyproject.toml.

Usage:
  python bump_version.py            # bump patch
  python bump_version.py minor      # bump minor
  python bump_version.py major      # bump major
  python bump_version.py --set 1.2.3
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Tuple


VERSION_RE = re.compile(
    r'^(?P<prefix>version\s*=\s*")(?P<version>\d+\.\d+\.\d+)(?P<suffix>")',
    re.MULTILINE,
)


def parse_version(value: str) -> Tuple[int, int, int]:
    parts = value.strip().split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid version: {value}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def bump_version(version: str, part: str) -> str:
    major, minor, patch = parse_version(version)
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown bump part: {part}")
    return f"{major}.{minor}.{patch}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump version in pyproject.toml.")
    parser.add_argument(
        "part",
        nargs="?",
        choices=["major", "minor", "patch"],
        default="patch",
        help="Version part to bump (default: patch).",
    )
    parser.add_argument("--set", dest="set_version", help="Set an explicit version (x.y.z).")
    parser.add_argument(
        "--file",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: pyproject.toml).",
    )
    args = parser.parse_args()

    target = Path(args.file)
    if not target.exists():
        print(f"File not found: {target}", file=sys.stderr)
        return 1

    content = target.read_text(encoding="utf-8")
    match = VERSION_RE.search(content)
    if not match:
        print("Could not find version entry in pyproject.toml.", file=sys.stderr)
        return 1

    current = match.group("version")
    if args.set_version:
        try:
            parse_version(args.set_version)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        new_version = args.set_version
    else:
        try:
            new_version = bump_version(current, args.part)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    updated = VERSION_RE.sub(
        rf'\g<prefix>{new_version}\g<suffix>',
        content,
        count=1,
    )
    target.write_text(updated, encoding="utf-8")
    print(f"Version bumped: {current} -> {new_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
