#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/tmp/local-deb-build}"

mkdir -p "$OUTPUT_DIR"

docker run --rm \
  -v "$ROOT_DIR:/workspace" \
  -v "$OUTPUT_DIR:/out" \
  -w /workspace \
  ubuntu:22.04 \
  bash -lc '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y python3 python3-venv ruby ruby-dev build-essential libegl1 libgl1 libpcsclite-dev pcscd pkg-config swig
    gem install --no-document fpm
    PYTHON_BIN=python3 PKG_ROOT=/tmp/pkg-root ./tools/build_deb.sh
    cp ./*.deb /out/
  '

echo "Built packages:"
find "$OUTPUT_DIR" -maxdepth 1 -name '*.deb' -print | sort
