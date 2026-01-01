#!/bin/bash
# Test runner script that uses .venv

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Error: .venv directory not found. Please create it first:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements-dev.txt"
    exit 1
fi

# Use venv Python
PYTHON=".venv/bin/python3"

# Check if pytest is installed
if ! "$PYTHON" -m pytest --version > /dev/null 2>&1; then
    echo "Error: pytest not found in .venv. Installing dependencies..."
    "$PYTHON" -m pip install -r requirements-dev.txt
fi

# Run validation first
echo "Running validation..."
"$PYTHON" validate_actiondraw.py
echo ""

# Run tests
echo "Running tests..."
"$PYTHON" -m pytest "$@"



