#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
PKG_ROOT="${PKG_ROOT:-$ROOT_DIR/pkg-root}"

VERSION="$("$PYTHON_BIN" -c "import re; from pathlib import Path; text = Path('pyproject.toml').read_text(encoding='utf-8'); match = re.search(r'^version\\s*=\\s*\"([^\"]+)\"', text, flags=re.MULTILINE); assert match, 'project.version is missing from pyproject.toml'; print(match.group(1))")"

rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/opt/actiondraw"
mkdir -p "$PKG_ROOT/usr/bin"
mkdir -p "$PKG_ROOT/usr/share/applications"
mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/512x512/apps"

"$PYTHON_BIN" -m venv "$PKG_ROOT/opt/actiondraw/venv"
"$PKG_ROOT/opt/actiondraw/venv/bin/pip" install --upgrade pip
"$PKG_ROOT/opt/actiondraw/venv/bin/pip" install .

printf '#!/bin/bash\nexec /opt/actiondraw/venv/bin/actiondraw "$@"\n' > "$PKG_ROOT/usr/bin/actiondraw"
chmod 755 "$PKG_ROOT/usr/bin/actiondraw"

cp packaging/actiondraw.desktop "$PKG_ROOT/usr/share/applications/"
cp packaging/icons/hicolor/256x256/apps/actiondraw.png "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/"
cp packaging/icons/hicolor/512x512/apps/actiondraw.png "$PKG_ROOT/usr/share/icons/hicolor/512x512/apps/"

fpm \
  -s dir \
  -t deb \
  -n actiondraw \
  -v "$VERSION" \
  --description "Visual diagramming and task planning application" \
  --url "https://github.com/oyvinrog/progress" \
  --license MIT \
  --maintainer "oyvinrog" \
  --depends libegl1 \
  --depends libgl1 \
  --depends libpcsclite1 \
  -C "$PKG_ROOT" \
  .
